"""
monitor.py - Cross-platform system metrics collector for Windows, macOS, and Linux.
Features a high-efficiency background sampling thread for zero-latency UI responses.
Reads CPU, RAM, Swap, Network, Disk I/O, Load Average, Temperatures, and Processes
with sub-millisecond memory cache access.
"""

import os
import sys
import glob
import time
import math
import platform
import subprocess
import threading
from collections import deque

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def _get_system_info():
    """Cross-platform hostname and OS release string."""
    try:
        hostname = platform.node() or "localhost"
    except Exception:
        hostname = "localhost"

    try:
        os_name = platform.system()
        os_release = platform.release()
        kernel = f"{os_name} {os_release}".strip()
    except Exception:
        kernel = "Unknown OS"

    return hostname, kernel


class SystemMonitor:
    def __init__(self, history_size=60, update_interval=1.0, auto_start_worker=True):
        self.history_size = history_size
        self.update_interval = update_interval

        # History buffers for sparklines and graphical charts
        self.cpu_history = deque(maxlen=history_size)
        self.ram_history = deque(maxlen=history_size)
        self.net_rx_history = deque(maxlen=history_size)
        self.net_tx_history = deque(maxlen=history_size)
        self.net_total_history = deque(maxlen=history_size)
        self.disk_read_history = deque(maxlen=history_size)
        self.disk_write_history = deque(maxlen=history_size)
        self.disk_total_history = deque(maxlen=history_size)
        self.gpu_history = deque(maxlen=history_size)

        # Previous state trackers for delta calculations
        self._prev_time = time.time()
        self._prev_cpu_stats = {}      # name -> (idle, total)
        self._prev_net_rx = 0
        self._prev_net_tx = 0
        self._prev_disk_read = 0
        self._prev_disk_write = 0
        self._first_run = True

        # Process cache & persistent trackers
        self._proc_cache = {'cpu': (0, []), 'mem': (0, [])}
        self._proc_tracker = {}        # pid -> psutil.Process
        self._proc_cache_ttl = 2.5     # seconds

        # Realistic Load Average simulation for Windows & non-UNIX
        self._ema_load = [0.0, 0.0, 0.0]
        self._ema_last_time = time.time()

        # GPU cache & telemetry
        self._gpu_cache = {
            'available': False,
            'name': 'No Dedicated GPU',
            'load': 0.0,
            'mem_used': 0,
            'mem_total': 0,
            'mem_percent': 0.0,
            'temp': None
        }
        self._last_gpu_probe = 0.0

        # Static hardware info
        self.model_name = "Unknown CPU"
        self.logical_cores = 1
        self.physical_cores = 1
        self._detect_cpu_info()

        # Prime psutil if present
        if HAS_PSUTIL:
            try:
                psutil.cpu_percent(interval=None)
                psutil.cpu_percent(interval=None, percpu=True)
            except Exception:
                pass

        # Thread safety & caching
        self._lock = threading.Lock()
        self._latest_snapshot = None
        self._stop_event = threading.Event()

        # Initial synchronous probe
        self._do_compute_snapshot()

        # Background worker thread for zero-latency GUI reads
        self._worker_thread = None
        if auto_start_worker:
            self.start_worker()

    def start_worker(self):
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self._stop_event.clear()
            self._worker_thread = threading.Thread(target=self._background_loop, daemon=True)
            self._worker_thread.start()

    def stop_worker(self):
        self._stop_event.set()

    def _background_loop(self):
        """Continuously samples metrics in the background so GUI calls return in microseconds."""
        while not self._stop_event.is_set():
            time.sleep(max(0.2, self.update_interval))
            try:
                self._do_compute_snapshot()
            except Exception:
                pass

    def _detect_cpu_info(self):
        """Cross-platform CPU model name and core count detection."""
        sys_platform = platform.system()

        # 1. Logical / Physical cores count
        if HAS_PSUTIL:
            try:
                self.logical_cores = psutil.cpu_count(logical=True) or os.cpu_count() or 1
                self.physical_cores = psutil.cpu_count(logical=False) or self.logical_cores
            except Exception:
                self.logical_cores = os.cpu_count() or 1
                self.physical_cores = self.logical_cores
        else:
            self.logical_cores = os.cpu_count() or 1
            self.physical_cores = self.logical_cores

        # 2. CPU Model Name
        if sys_platform == "Windows":
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
                )
                val, _ = winreg.QueryValueEx(key, "ProcessorNameString")
                if val:
                    self.model_name = val.strip()
                    return
            except Exception:
                pass
        elif sys_platform == "Darwin":
            try:
                out = subprocess.check_output(
                    ["sysctl", "-n", "machdep.cpu.brand_string"],
                    text=True, stderr=subprocess.DEVNULL
                ).strip()
                if out:
                    self.model_name = out
                    return
            except Exception:
                pass

        if os.path.exists('/proc/cpuinfo'):
            try:
                with open('/proc/cpuinfo', 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                models = []
                core_ids = set()
                for line in content.splitlines():
                    if 'model name' in line:
                        models.append(line.split(':', 1)[1].strip())
                    elif 'core id' in line:
                        core_ids.add(line.split(':', 1)[1].strip())

                if models:
                    self.model_name = models[0]
                    self.logical_cores = len(models)
                if core_ids:
                    self.physical_cores = len(core_ids)
                return
            except Exception:
                pass

        proc = platform.processor()
        if proc:
            self.model_name = proc

    # ----------------------------------------------------
    # Linux Native Fallbacks (when psutil is not installed)
    # ----------------------------------------------------
    def _read_cpu_raw_proc(self):
        cores = {}
        try:
            with open('/proc/stat', 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('cpu'):
                        parts = line.strip().split()
                        name = parts[0]
                        values = [int(x) for x in parts[1:]]
                        idle = values[3] + (values[4] if len(values) > 4 else 0)
                        total = sum(values)
                        cores[name] = (idle, total)
        except Exception:
            pass
        return cores

    def _read_net_bytes_proc(self):
        rx_total, tx_total = 0, 0
        try:
            with open('/proc/net/dev', 'r', encoding='utf-8') as f:
                lines = f.readlines()
            for line in lines[2:]:
                if ':' not in line:
                    continue
                iface, data = line.split(':', 1)
                iface = iface.strip()
                if iface == 'lo':
                    continue
                parts = data.strip().split()
                if len(parts) >= 9:
                    rx_total += int(parts[0])
                    tx_total += int(parts[8])
        except Exception:
            pass
        return rx_total, tx_total

    def _read_disk_bytes_proc(self):
        read_bytes, write_bytes = 0, 0
        try:
            with open('/proc/diskstats', 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 14:
                        dev = parts[2]
                        is_target = (
                            (dev.startswith('sd') and len(dev) == 3) or
                            (dev.startswith('vd') and len(dev) == 3) or
                            (dev.startswith('nvme') and 'p' not in dev) or
                            (dev.startswith('mmcblk') and 'p' not in dev)
                        )
                        if is_target:
                            r_sec = int(parts[5])
                            w_sec = int(parts[9])
                            read_bytes += r_sec * 512
                            write_bytes += w_sec * 512
        except Exception:
            pass
        return read_bytes, write_bytes

    def _read_win_memory(self):
        """Native Windows memory detection via ctypes GlobalMemoryStatusEx."""
        try:
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ('dwLength', ctypes.c_ulong),
                    ('dwMemoryLoad', ctypes.c_ulong),
                    ('ullTotalPhys', ctypes.c_ulonglong),
                    ('ullAvailPhys', ctypes.c_ulonglong),
                    ('ullTotalPageFile', ctypes.c_ulonglong),
                    ('ullAvailPageFile', ctypes.c_ulonglong),
                    ('ullTotalVirtual', ctypes.c_ulonglong),
                    ('ullAvailVirtual', ctypes.c_ulonglong),
                    ('sullAvailExtendedVirtual', ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total_phys = int(stat.ullTotalPhys)
                avail_phys = int(stat.ullAvailPhys)
                used_phys = max(0, total_phys - avail_phys)
                pct = float(stat.dwMemoryLoad)
                total_page = int(stat.ullTotalPageFile)
                avail_page = int(stat.ullAvailPageFile)
                used_page = max(0, total_page - avail_page)
                swap_pct = (used_page / total_page * 100.0) if total_page > 0 else 0.0
                return {
                    'total': total_phys,
                    'used': used_phys,
                    'free': avail_phys,
                    'available': avail_phys,
                    'cached': 0,
                    'percent': pct,
                    'swap_total': total_page,
                    'swap_used': used_page,
                    'swap_free': avail_page,
                    'swap_percent': swap_pct
                }
        except Exception:
            pass
        return None

    def _read_darwin_memory(self):
        """Native macOS memory detection via sysctl and vm_stat."""
        try:
            total = int(subprocess.check_output(['sysctl', '-n', 'hw.memsize'], text=True, stderr=subprocess.DEVNULL).strip())
            out = subprocess.check_output(['vm_stat'], text=True, stderr=subprocess.DEVNULL)
            page_size = 4096
            free_pages = 0
            inactive_pages = 0
            for line in out.splitlines():
                if 'page size of' in line:
                    parts = line.split()
                    page_size = int(parts[-2])
                elif 'Pages free:' in line:
                    free_pages = int(line.split(':')[1].strip().rstrip('.'))
                elif 'Pages inactive:' in line:
                    inactive_pages = int(line.split(':')[1].strip().rstrip('.'))
            avail = (free_pages + inactive_pages) * page_size
            used = max(0, total - avail)
            pct = (used / total * 100.0) if total > 0 else 0.0
            return {
                'total': total,
                'used': used,
                'free': free_pages * page_size,
                'available': avail,
                'cached': inactive_pages * page_size,
                'percent': pct,
                'swap_total': 0,
                'swap_used': 0,
                'swap_free': 0,
                'swap_percent': 0.0
            }
        except Exception:
            return None

    def _read_win_cpu(self):
        """Native Windows CPU calculation via GetSystemTimes when psutil is not available."""
        try:
            import ctypes
            class FILETIME(ctypes.Structure):
                _fields_ = [('dwLowDateTime', ctypes.c_uint32), ('dwHighDateTime', ctypes.c_uint32)]
            idle, kernel, user = FILETIME(), FILETIME(), FILETIME()
            if ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
                def to_int(ft):
                    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime
                curr_idle = to_int(idle)
                curr_kernel = to_int(kernel)
                curr_user = to_int(user)
                if hasattr(self, '_prev_win_times') and self._prev_win_times:
                    prev_idle, prev_kernel, prev_user = self._prev_win_times
                    d_idle = curr_idle - prev_idle
                    d_sys = (curr_kernel - prev_kernel) + (curr_user - prev_user)
                    self._prev_win_times = (curr_idle, curr_kernel, curr_user)
                    if d_sys > 0:
                        pct = 100.0 * (1.0 - d_idle / d_sys)
                        return max(0.0, min(100.0, pct))
                self._prev_win_times = (curr_idle, curr_kernel, curr_user)
        except Exception:
            pass
        return 0.0

    def _read_meminfo_proc(self):
        info = {}
        try:
            with open('/proc/meminfo', 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.split(':')
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val_str = parts[1].strip().split()[0]
                        info[key] = int(val_str) * 1024
        except Exception:
            pass

        total = info.get('MemTotal', 0)
        avail = info.get('MemAvailable', 0)
        free = info.get('MemFree', 0)
        cached = info.get('Cached', 0) + info.get('Buffers', 0) + info.get('SReclaimable', 0)
        used = max(0, total - avail) if avail else max(0, total - free - cached)
        used_pct = (used / total * 100.0) if total > 0 else 0.0

        swap_total = info.get('SwapTotal', 0)
        swap_free = info.get('SwapFree', 0)
        swap_used = max(0, swap_total - swap_free)
        swap_pct = (swap_used / swap_total * 100.0) if swap_total > 0 else 0.0

        return {
            'total': total,
            'used': used,
            'free': free,
            'available': avail,
            'cached': cached,
            'percent': used_pct,
            'swap_total': swap_total,
            'swap_used': swap_used,
            'swap_free': swap_free,
            'swap_percent': swap_pct
        }

    def _format_uptime_seconds(self, seconds):
        mins, sec = divmod(int(seconds), 60)
        hours, mins = divmod(mins, 60)
        days, hours = divmod(hours, 24)
        if days > 0:
            return f"{days}d {hours}h {mins}m"
        elif hours > 0:
            return f"{hours}h {mins}m"
        else:
            return f"{mins}m {sec}s"

    def _read_uptime(self):
        if HAS_PSUTIL:
            try:
                boot = psutil.boot_time()
                return self._format_uptime_seconds(time.time() - boot)
            except Exception:
                pass
        try:
            with open('/proc/uptime', 'r', encoding='utf-8') as f:
                seconds = float(f.read().split()[0])
            return self._format_uptime_seconds(seconds)
        except Exception:
            return "Unknown"

    def _read_cpu_freq_and_temp(self):
        avg_freq = 0.0
        avg_temp = None

        if HAS_PSUTIL:
            try:
                freq = psutil.cpu_freq()
                if freq and freq.current:
                    avg_freq = float(freq.current)
            except Exception:
                pass

            try:
                if hasattr(psutil, "sensors_temperatures"):
                    temps_dict = psutil.sensors_temperatures()
                    if temps_dict:
                        all_temps = []
                        for entries in temps_dict.values():
                            for entry in entries:
                                if getattr(entry, "current", None) is not None:
                                    all_temps.append(entry.current)
                        if all_temps:
                            avg_temp = sum(all_temps) / len(all_temps)
            except Exception:
                pass

        if avg_freq <= 0.0 and os.path.exists('/sys/devices/system/cpu'):
            freqs = []
            for p in glob.glob('/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq'):
                try:
                    with open(p, 'r') as f:
                        freqs.append(int(f.read().strip()) / 1000.0)
                except Exception:
                    pass
            if freqs:
                avg_freq = sum(freqs) / len(freqs)

        if avg_temp is None:
            temps = []
            for p in glob.glob('/sys/class/thermal/thermal_zone*/temp'):
                try:
                    with open(p, 'r') as f:
                        temps.append(int(f.read().strip()) / 1000.0)
                except Exception:
                    pass
            if not temps:
                for p in glob.glob('/sys/class/hwmon/hwmon*/temp*_input'):
                    try:
                        with open(p, 'r') as f:
                            temps.append(int(f.read().strip()) / 1000.0)
                    except Exception:
                        pass
            if temps:
                avg_temp = sum(temps) / len(temps)

        return avg_freq, avg_temp

    def _read_load_avg(self, cpu_overall=0.0):
        if hasattr(os, "getloadavg"):
            try:
                return [float(x) for x in os.getloadavg()]
            except Exception:
                pass

        if HAS_PSUTIL and hasattr(psutil, "getloadavg"):
            try:
                return [float(x) for x in psutil.getloadavg()]
            except Exception:
                pass

        if os.path.exists('/proc/loadavg'):
            try:
                with open('/proc/loadavg', 'r', encoding='utf-8') as f:
                    parts = f.read().split()
                    return [float(parts[0]), float(parts[1]), float(parts[2])]
            except Exception:
                pass

        # Exponential Moving Average (EMA) simulation for Windows & non-UNIX
        now = time.time()
        dt = max(0.1, min(10.0, now - self._ema_last_time))
        self._ema_last_time = now
        instant = (cpu_overall / 100.0) * self.logical_cores

        decay_1 = math.exp(-dt / 60.0)
        decay_5 = math.exp(-dt / 300.0)
        decay_15 = math.exp(-dt / 900.0)

        if self._ema_load == [0.0, 0.0, 0.0]:
            self._ema_load = [instant, instant, instant]
        else:
            self._ema_load[0] = round(self._ema_load[0] * decay_1 + instant * (1.0 - decay_1), 2)
            self._ema_load[1] = round(self._ema_load[1] * decay_5 + instant * (1.0 - decay_5), 2)
            self._ema_load[2] = round(self._ema_load[2] * decay_15 + instant * (1.0 - decay_15), 2)

        return list(self._ema_load)

    def _read_battery(self):
        """Battery health and charging status."""
        if HAS_PSUTIL and hasattr(psutil, "sensors_battery"):
            try:
                batt = psutil.sensors_battery()
                if batt is not None:
                    percent = float(batt.percent)
                    plugged = bool(batt.power_plugged)
                    secsleft = batt.secsleft
                    time_left = ""
                    if secsleft == getattr(psutil, "POWER_TIME_UNLIMITED", -1):
                        time_left = "Plugged in / Full"
                    elif secsleft == getattr(psutil, "POWER_TIME_UNKNOWN", -2) or secsleft < 0:
                        time_left = "Plugged in" if plugged else "Calculating..."
                    else:
                        m, s = divmod(int(secsleft), 60)
                        h, m = divmod(m, 60)
                        time_left = f"{h}h {m}m left"
                    return {
                        'present': True,
                        'percent': percent,
                        'plugged': plugged,
                        'time_left': time_left
                    }
            except Exception:
                pass
        return {'present': False, 'percent': 100.0, 'plugged': True, 'time_left': ''}

    def _read_gpu(self):
        """Non-blocking GPU utilization and VRAM usage."""
        now = time.time()
        if now - self._last_gpu_probe < 2.5:
            return self._gpu_cache

        self._last_gpu_probe = now
        try:
            cmd = ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                   "--format=csv,noheader,nounits"]
            out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL, timeout=0.8).strip()
            if out:
                line = out.splitlines()[0]
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 5:
                    gpu_name = parts[0]
                    gpu_load = float(parts[1])
                    mem_used = int(float(parts[2]) * 1024 * 1024)
                    mem_tot = int(float(parts[3]) * 1024 * 1024)
                    temp = float(parts[4])
                    pct = (mem_used / mem_tot * 100.0) if mem_tot > 0 else 0.0
                    self._gpu_cache = {
                        'available': True,
                        'name': gpu_name,
                        'load': gpu_load,
                        'mem_used': mem_used,
                        'mem_total': mem_tot,
                        'mem_percent': pct,
                        'temp': temp
                    }
                    return self._gpu_cache
        except Exception:
            pass

        return self._gpu_cache

    def get_storage_devices(self):
        """Detailed list of mounted storage partitions with disk utilization."""
        disks = []
        if HAS_PSUTIL:
            try:
                for part in psutil.disk_partitions(all=False):
                    if not part.mountpoint or 'cdrom' in part.opts or part.fstype == '':
                        continue
                    try:
                        usage = psutil.disk_usage(part.mountpoint)
                        disks.append({
                            'device': part.device,
                            'mountpoint': part.mountpoint,
                            'fstype': part.fstype,
                            'total': usage.total,
                            'used': usage.used,
                            'free': usage.free,
                            'percent': usage.percent
                        })
                    except Exception:
                        continue
            except Exception:
                pass

        if not disks and platform.system() == "Windows":
            try:
                import ctypes, string
                bitmask = ctypes.windll.kernel32.GetLogicalDrives()
                drives = [f"{d}:\\" for d in string.ascii_uppercase if (bitmask & (1 << (ord(d) - 65)))]
                for drv in drives:
                    free_b, total_b, tot_free_b = ctypes.c_ulonglong(), ctypes.c_ulonglong(), ctypes.c_ulonglong()
                    if ctypes.windll.kernel32.GetDiskFreeSpaceExW(drv, ctypes.byref(free_b), ctypes.byref(total_b), ctypes.byref(tot_free_b)):
                        t = int(total_b.value)
                        u = int(t - tot_free_b.value)
                        f = int(tot_free_b.value)
                        p = (u / t * 100.0) if t > 0 else 0.0
                        disks.append({
                            'device': drv,
                            'mountpoint': drv,
                            'fstype': 'NTFS',
                            'total': t,
                            'used': u,
                            'free': f,
                            'percent': round(p, 1)
                        })
            except Exception:
                pass
        return disks

    def get_network_interfaces(self):
        """Status and IP addresses of physical and virtual network adapters."""
        adapters = []
        if HAS_PSUTIL:
            try:
                stats = psutil.net_if_stats()
                addrs = psutil.net_if_addrs()
                for iface, if_stat in stats.items():
                    if iface.startswith('lo') or 'Loopback' in iface:
                        continue
                    ip_list = []
                    if iface in addrs:
                        for addr in addrs[iface]:
                            if getattr(addr, 'family', None) == 2:  # AF_INET (IPv4)
                                ip_list.append(addr.address)
                    adapters.append({
                        'name': iface,
                        'is_up': if_stat.isup,
                        'speed': if_stat.speed,
                        'ips': ip_list
                    })
            except Exception:
                pass
        return adapters

    def get_top_processes(self, count=5, sort_by='cpu', force=False):
        """
        Get top active processes by CPU or Memory.
        Uses persistent process instances so CPU percent delta is non-zero and highly accurate.
        """
        now = time.time()
        last_time, cached_list = self._proc_cache.get(sort_by, (0, []))

        if not force and (now - last_time < self._proc_cache_ttl) and cached_list:
            return cached_list[:count]

        procs = []
        if HAS_PSUTIL:
            try:
                current_pids = set(psutil.pids())
                # Prune dead processes from cache
                stale_pids = set(self._proc_tracker.keys()) - current_pids
                for spid in stale_pids:
                    self._proc_tracker.pop(spid, None)

                # Query process snapshots
                for pid in current_pids:
                    if pid == 0:
                        continue
                    try:
                        if pid not in self._proc_tracker:
                            proc = psutil.Process(pid)
                            proc.cpu_percent(None)  # Baseline prime
                            self._proc_tracker[pid] = proc
                            cpu = 0.0
                        else:
                            proc = self._proc_tracker[pid]
                            cpu = float(proc.cpu_percent(None) or 0.0)

                        name = proc.name() or "Process"
                        try:
                            user = proc.username() or "System"
                            if "\\" in user:
                                user = user.split("\\", 1)[1]
                        except Exception:
                            user = "System"

                        mem = float(proc.memory_percent() or 0.0)
                        procs.append({
                            'pid': int(pid),
                            'user': user,
                            'cpu': round(cpu, 1),
                            'mem': round(mem, 1),
                            'name': name
                        })
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        self._proc_tracker.pop(pid, None)
                        continue

                key = 'cpu' if sort_by == 'cpu' else 'mem'
                procs.sort(key=lambda x: x[key], reverse=True)
                self._proc_cache[sort_by] = (now, procs)
                return procs[:count]
            except Exception:
                pass

        # Fallback to 'tasklist' on Windows when psutil is not available
        if platform.system() == "Windows":
            try:
                import csv
                cmd = ["tasklist", "/FO", "CSV", "/NH"]
                output = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
                mem_snapshot = self.update().get('ram', {})
                total_mem = mem_snapshot.get('total') or 16000000000
                reader = csv.reader(output.strip().splitlines())
                for row in reader:
                    if len(row) >= 5 and row[1].isdigit():
                        p_name = row[0]
                        p_pid = int(row[1])
                        mem_clean = row[4].replace(',', '').replace(' ', '').replace('K', '').replace('k', '')
                        mem_kb = float(mem_clean) if mem_clean.isdigit() else 0.0
                        mem_bytes = mem_kb * 1024
                        mem_pct = round((mem_bytes / max(1, total_mem)) * 100.0, 1)
                        procs.append({
                            'pid': p_pid,
                            'user': row[2] if len(row) > 2 else "System",
                            'cpu': 0.0,
                            'mem': mem_pct,
                            'name': p_name
                        })
                key = 'mem' if sort_by == 'mem' else 'cpu'
                procs.sort(key=lambda x: (x['mem'], x['pid']), reverse=True)
                self._proc_cache[sort_by] = (now, procs)
                return procs[:count]
            except Exception:
                pass

        # Fallback to 'ps' command on UNIX systems
        sort_arg = '-%cpu' if sort_by == 'cpu' else '-%mem'
        try:
            cmd = ['ps', '-eo', 'pid,user,%cpu,%mem,comm', f'--sort={sort_arg}']
            output = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
            lines = output.strip().splitlines()[1:count+1]
            for line in lines:
                parts = line.split(None, 4)
                if len(parts) >= 5:
                    procs.append({
                        'pid': int(parts[0]),
                        'user': parts[1],
                        'cpu': float(parts[2]),
                        'mem': float(parts[3]),
                        'name': parts[4].strip()
                    })
            self._proc_cache[sort_by] = (now, procs)
        except Exception:
            pass

        return procs[:count]

    def _do_compute_snapshot(self):
        """Internal computation of current metrics."""
        now = time.time()
        time_delta = max(0.001, now - self._prev_time)
        self._prev_time = now

        # 1. CPU Metrics
        cpu_overall = 0.0
        cpu_cores = {}

        if HAS_PSUTIL:
            try:
                cpu_overall = float(psutil.cpu_percent(interval=None))
                per_core = psutil.cpu_percent(interval=None, percpu=True)
                for i, pct in enumerate(per_core):
                    cpu_cores[f"cpu{i}"] = float(pct)
            except Exception:
                pass
        else:
            if platform.system() == "Windows":
                cpu_overall = self._read_win_cpu()
            else:
                current_cpu_stats = self._read_cpu_raw_proc()
                if self._prev_cpu_stats:
                    for name, (idle2, total2) in current_cpu_stats.items():
                        if name in self._prev_cpu_stats:
                            idle1, total1 = self._prev_cpu_stats[name]
                            d_idle = idle2 - idle1
                            d_total = total2 - total1
                            pct = 0.0 if d_total <= 0 else 100.0 * (1.0 - (d_idle / d_total))
                            pct = max(0.0, min(100.0, pct))
                            if name == 'cpu':
                                cpu_overall = pct
                            else:
                                cpu_cores[name] = pct
                self._prev_cpu_stats = current_cpu_stats

        if not cpu_cores:
            for i in range(self.logical_cores):
                cpu_cores[f"cpu{i}"] = cpu_overall

        # 2. RAM and Swap Metrics
        total_ram = 0
        used_ram = 0
        free_ram = 0
        avail_ram = 0
        cached_ram = 0
        percent_ram = 0.0

        if HAS_PSUTIL:
            try:
                vm = psutil.virtual_memory()
                total_ram = int(vm.total)
                used_ram = int(vm.used)
                free_ram = int(vm.free)
                avail_ram = int(getattr(vm, 'available', vm.free))
                cached_ram = int(getattr(vm, 'cached', 0) + getattr(vm, 'buffers', 0))
                percent_ram = float(vm.percent)
            except Exception:
                pass

        swap_total = 0
        swap_used = 0
        swap_free = 0
        swap_percent = 0.0

        if HAS_PSUTIL:
            try:
                sm = psutil.swap_memory()
                swap_total = int(sm.total)
                swap_used = int(sm.used)
                swap_free = int(sm.free)
                swap_percent = float(sm.percent)
            except Exception:
                pass

        if total_ram > 0:
            mem = {
                'total': total_ram,
                'used': used_ram,
                'free': free_ram,
                'available': avail_ram,
                'cached': cached_ram,
                'percent': percent_ram,
                'swap_total': swap_total,
                'swap_used': swap_used,
                'swap_free': swap_free,
                'swap_percent': swap_percent
            }
        elif platform.system() == "Windows":
            mem = self._read_win_memory() or self._read_meminfo_proc()
        elif platform.system() == "Darwin":
            mem = self._read_darwin_memory() or self._read_meminfo_proc()
        else:
            mem = self._read_meminfo_proc()

        # 3. Network Metrics
        net_rx, net_tx = 0, 0
        if HAS_PSUTIL:
            try:
                net_io = psutil.net_io_counters()
                if net_io:
                    net_rx = net_io.bytes_recv
                    net_tx = net_io.bytes_sent
            except Exception:
                pass
        else:
            net_rx, net_tx = self._read_net_bytes_proc()

        net_rx_rate = 0.0
        net_tx_rate = 0.0
        if not self._first_run:
            if net_rx >= self._prev_net_rx:
                net_rx_rate = (net_rx - self._prev_net_rx) / time_delta
            if net_tx >= self._prev_net_tx:
                net_tx_rate = (net_tx - self._prev_net_tx) / time_delta
        self._prev_net_rx = net_rx
        self._prev_net_tx = net_tx
        net_total_rate = net_rx_rate + net_tx_rate

        # 4. Disk I/O Metrics
        disk_r, disk_w = 0, 0
        if HAS_PSUTIL:
            try:
                disk_io = psutil.disk_io_counters()
                if disk_io:
                    disk_r = disk_io.read_bytes
                    disk_w = disk_io.write_bytes
            except Exception:
                pass
        else:
            disk_r, disk_w = self._read_disk_bytes_proc()

        disk_r_rate = 0.0
        disk_w_rate = 0.0
        if not self._first_run:
            if disk_r >= self._prev_disk_read:
                disk_r_rate = (disk_r - self._prev_disk_read) / time_delta
            if disk_w >= self._prev_disk_write:
                disk_w_rate = (disk_w - self._prev_disk_write) / time_delta
        self._prev_disk_read = disk_r
        self._prev_disk_write = disk_w
        disk_total_rate = disk_r_rate + disk_w_rate

        # 5. Frequency, Temperature, Load, Uptime, Hostname, GPU, Battery
        freq, temp = self._read_cpu_freq_and_temp()
        load = self._read_load_avg(cpu_overall=cpu_overall)
        uptime = self._read_uptime()
        hostname, kernel = _get_system_info()
        gpu_info = self._read_gpu()
        battery_info = self._read_battery()

        # Update History Buffers (Thread-safe)
        with self._lock:
            self.cpu_history.append(cpu_overall)
            self.ram_history.append(mem['percent'])
            self.net_rx_history.append(net_rx_rate)
            self.net_tx_history.append(net_tx_rate)
            self.net_total_history.append(net_total_rate)
            self.disk_read_history.append(disk_r_rate)
            self.disk_write_history.append(disk_w_rate)
            self.disk_total_history.append(disk_total_rate)
            if gpu_info.get('available'):
                self.gpu_history.append(gpu_info.get('load', 0.0))

            snapshot = {
                'cpu': {
                    'percent': cpu_overall,
                    'cores': cpu_cores,
                    'frequency': freq,
                    'temperature': temp,
                    'load': load,
                    'model': self.model_name,
                    'cores_count': self.logical_cores,
                    'history': list(self.cpu_history)
                },
                'ram': {
                    'total': mem['total'],
                    'used': mem['used'],
                    'free': mem['free'],
                    'available': mem['available'],
                    'cached': mem['cached'],
                    'percent': mem['percent'],
                    'swap_total': mem['swap_total'],
                    'swap_used': mem['swap_used'],
                    'swap_free': mem['swap_free'],
                    'swap_percent': mem['swap_percent'],
                    'history': list(self.ram_history)
                },
                'track': {
                    'net_rx_rate': net_rx_rate,
                    'net_tx_rate': net_tx_rate,
                    'net_total_rate': net_total_rate,
                    'net_total_rx': net_rx,
                    'net_total_tx': net_tx,
                    'disk_read_rate': disk_r_rate,
                    'disk_write_rate': disk_w_rate,
                    'disk_total_rate': disk_total_rate,
                    'disk_total_read': disk_r,
                    'disk_total_write': disk_w,
                    'net_rx_history': list(self.net_rx_history),
                    'net_tx_history': list(self.net_tx_history),
                    'net_total_history': list(self.net_total_history),
                    'disk_read_history': list(self.disk_read_history),
                    'disk_write_history': list(self.disk_write_history),
                    'disk_total_history': list(self.disk_total_history)
                },
                'gpu': gpu_info,
                'battery': battery_info,
                'system': {
                    'uptime': uptime,
                    'hostname': hostname,
                    'kernel': kernel
                }
            }
            self._latest_snapshot = snapshot

        self._first_run = False
        return snapshot

    def update(self, force=False):
        """
        Instant read of latest metrics snapshot.
        If force=True or no snapshot exists yet, performs direct synchronous computation.
        """
        if force or self._latest_snapshot is None:
            return self._do_compute_snapshot()
        with self._lock:
            return self._latest_snapshot
