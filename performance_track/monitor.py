"""
monitor.py - High-performance system metrics collector for Ubuntu.
Reads directly from Linux /proc and /sys with zero external dependencies.
Tracks CPU, RAM, Swap, Network, Disk I/O, Load Average, Temperatures, and Processes.
"""

import os
import glob
import time
import subprocess
from collections import deque

class SystemMonitor:
    def __init__(self, history_size=60):
        self.history_size = history_size
        
        # History buffers for sparklines and graphical charts
        self.cpu_history = deque(maxlen=history_size)
        self.ram_history = deque(maxlen=history_size)
        self.net_rx_history = deque(maxlen=history_size)
        self.net_tx_history = deque(maxlen=history_size)
        self.disk_read_history = deque(maxlen=history_size)
        self.disk_write_history = deque(maxlen=history_size)
        
        # Previous state trackers for delta calculations
        self._prev_time = time.time()
        self._prev_cpu_stats = {}      # name -> (idle, total)
        self._prev_net_rx = 0
        self._prev_net_tx = 0
        self._prev_disk_read = 0
        self._prev_disk_write = 0
        self._first_run = True

        # Static hardware info
        self.model_name = "Unknown CPU"
        self.logical_cores = 1
        self.physical_cores = 1
        self._detect_cpu_info()
        
        # Initial probe
        self.update()

    def _detect_cpu_info(self):
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
            else:
                self.physical_cores = self.logical_cores
        except Exception:
            pass

    def _read_cpu_raw(self):
        """Read /proc/stat and return {name: (idle, total)} for all cpu rows."""
        cores = {}
        try:
            with open('/proc/stat', 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('cpu'):
                        parts = line.strip().split()
                        name = parts[0]
                        # fields: user, nice, system, idle, iowait, irq, softirq, steal, guest, guest_nice
                        values = [int(x) for x in parts[1:]]
                        idle = values[3] + (values[4] if len(values) > 4 else 0)
                        total = sum(values)
                        cores[name] = (idle, total)
        except Exception:
            pass
        return cores

    def _read_net_bytes(self):
        """Read total rx and tx bytes from /proc/net/dev excluding lo."""
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

    def _read_disk_bytes(self):
        """Read total bytes read and written across storage disks from /proc/diskstats."""
        read_bytes, write_bytes = 0, 0
        try:
            with open('/proc/diskstats', 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 14:
                        dev = parts[2]
                        # Filter to main disks and avoid counting partitions twice
                        # e.g., nvme0n1, sda, vda, mmcblk0
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

    def _read_meminfo(self):
        """Read /proc/meminfo and return memory metrics in bytes."""
        info = {}
        try:
            with open('/proc/meminfo', 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.split(':')
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val_str = parts[1].strip().split()[0]
                        info[key] = int(val_str) * 1024  # convert kB to Bytes
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

    def _read_cpu_freq_and_temp(self):
        """Read current average CPU frequency in MHz and temperature in Celsius."""
        freqs = []
        for p in glob.glob('/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq'):
            try:
                with open(p, 'r') as f:
                    freqs.append(int(f.read().strip()) / 1000.0)
            except Exception:
                pass
        avg_freq = (sum(freqs) / len(freqs)) if freqs else 0.0

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
        avg_temp = (sum(temps) / len(temps)) if temps else None

        return avg_freq, avg_temp

    def _read_load_avg(self):
        try:
            with open('/proc/loadavg', 'r', encoding='utf-8') as f:
                parts = f.read().split()
                return [float(parts[0]), float(parts[1]), float(parts[2])]
        except Exception:
            return [0.0, 0.0, 0.0]

    def _read_uptime(self):
        try:
            with open('/proc/uptime', 'r', encoding='utf-8') as f:
                seconds = float(f.read().split()[0])
            mins, sec = divmod(int(seconds), 60)
            hours, mins = divmod(mins, 60)
            days, hours = divmod(hours, 24)
            if days > 0:
                return f"{days}d {hours}h {mins}m"
            elif hours > 0:
                return f"{hours}h {mins}m"
            else:
                return f"{mins}m {sec}s"
        except Exception:
            return "Unknown"

    def get_top_processes(self, count=5, sort_by='cpu'):
        """
        Get top processes by CPU or Memory.
        sort_by: 'cpu' or 'mem'
        """
        procs = []
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
        except Exception:
            pass
        return procs

    def update(self):
        """
        Calculate current metrics snapshot and update rolling history buffers.
        Returns a dictionary with comprehensive system metrics.
        """
        now = time.time()
        time_delta = max(0.001, now - self._prev_time)
        self._prev_time = now

        # 1. CPU Usage
        current_cpu_stats = self._read_cpu_raw()
        cpu_overall = 0.0
        cpu_cores = {}

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

        # 2. RAM and Swap
        mem = self._read_meminfo()

        # 3. Network Throughput
        net_rx, net_tx = self._read_net_bytes()
        net_rx_rate = 0.0
        net_tx_rate = 0.0
        if not self._first_run and net_rx >= self._prev_net_rx and net_tx >= self._prev_net_tx:
            net_rx_rate = (net_rx - self._prev_net_rx) / time_delta
            net_tx_rate = (net_tx - self._prev_net_tx) / time_delta
        self._prev_net_rx = net_rx
        self._prev_net_tx = net_tx

        # 4. Disk I/O Throughput
        disk_r, disk_w = self._read_disk_bytes()
        disk_r_rate = 0.0
        disk_w_rate = 0.0
        if not self._first_run and disk_r >= self._prev_disk_read and disk_w >= self._prev_disk_write:
            disk_r_rate = (disk_r - self._prev_disk_read) / time_delta
            disk_w_rate = (disk_w - self._prev_disk_write) / time_delta
        self._prev_disk_read = disk_r
        self._prev_disk_write = disk_w

        # 5. CPU Frequency, Temperature, Load, Uptime
        freq, temp = self._read_cpu_freq_and_temp()
        load = self._read_load_avg()
        uptime = self._read_uptime()

        # Update History Buffers
        self.cpu_history.append(cpu_overall)
        self.ram_history.append(mem['percent'])
        self.net_rx_history.append(net_rx_rate)
        self.net_tx_history.append(net_tx_rate)
        self.disk_read_history.append(disk_r_rate)
        self.disk_write_history.append(disk_w_rate)

        self._first_run = False

        return {
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
                'net_total_rx': net_rx,
                'net_total_tx': net_tx,
                'disk_read_rate': disk_r_rate,
                'disk_write_rate': disk_w_rate,
                'disk_total_read': disk_r,
                'disk_total_write': disk_w,
                'net_rx_history': list(self.net_rx_history),
                'net_tx_history': list(self.net_tx_history),
                'disk_read_history': list(self.disk_read_history),
                'disk_write_history': list(self.disk_write_history)
            },
            'system': {
                'uptime': uptime,
                'hostname': os.uname().nodename,
                'kernel': os.uname().release
            }
        }
