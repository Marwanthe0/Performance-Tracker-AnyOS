"""
app.py - Main application controller for Performance Track.
Cross-platform support for Windows, macOS, and Linux.
- On Linux (Ubuntu/GNOME): Integrates directly with topbar AppIndicator and GTK3.
- On Windows, macOS, and other desktop environments: Provides a sleek System Tray
  monitor (via pystray) with interactive menus and full Tkinter GUI Dashboard.
- Headless / Terminal: Provides a live CLI monitor with unicode sparklines.
"""

import sys
import os
import time
import argparse
import platform
import subprocess
import threading

try:
    from .monitor import SystemMonitor
    from .config import Config
    from .sparkline import (
        generate_sparkline,
        generate_bar,
        format_bytes,
        format_rate,
        format_short_rate
    )
except (ImportError, ValueError):
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from performance_track.monitor import SystemMonitor
    from performance_track.config import Config
    from performance_track.sparkline import (
        generate_sparkline,
        generate_bar,
        format_bytes,
        format_rate,
        format_short_rate
    )

APP_ID = "performance-track"
APP_NAME = "Performance Track"
APP_VERSION = "1.0.0"
SYS_NAME = platform.system()

# Check for Linux GTK3 and AppIndicator libraries
HAS_GTK = False
HAS_APPINDICATOR = False
lib_appindicator = None

if SYS_NAME == "Linux":
    try:
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk, GLib
        HAS_GTK = True

        import ctypes
        for libname in ['libayatana-appindicator3.so.1', 'libappindicator3.so.1']:
            try:
                lib_appindicator = ctypes.CDLL(libname)
                HAS_APPINDICATOR = True
                break
            except OSError:
                continue
    except Exception:
        HAS_GTK = False
        HAS_APPINDICATOR = False

# Check for pystray & PIL for cross-platform system tray
HAS_PYSTRAY = False
try:
    import pystray
    from pystray import MenuItem as pystray_item, Menu as pystray_menu
    from PIL import Image, ImageDraw, ImageFont
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False


def _open_native_task_manager():
    """Launch the host operating system's native task manager."""
    try:
        if SYS_NAME == "Windows":
            subprocess.Popen(["taskmgr"])
        elif SYS_NAME == "Darwin":
            subprocess.Popen(["open", "-a", "Activity Monitor"])
        else:
            for cmd in [["gnome-system-monitor"], ["plasma-systemmonitor"], ["mate-system-monitor"], ["xfce4-taskmanager"], ["top"]]:
                try:
                    subprocess.Popen(cmd)
                    return
                except FileNotFoundError:
                    continue
    except Exception as e:
        print(f"Failed to open task manager: {e}", file=sys.stderr)


# ============================================================================
# 1. Cross-Platform System Tray & Tkinter Dashboard Application
# ============================================================================
class CrossPlatformApp:
    def __init__(self, start_with_dashboard=False):
        try:
            import tkinter as tk
        except ImportError:
            print("[!] Error: Tkinter is required for the desktop interface.", file=sys.stderr)
            if SYS_NAME == "Linux":
                print("[*] On Ubuntu/Debian, install it with: sudo apt install python3-tk", file=sys.stderr)
            print("[*] Falling back to CLI live monitor mode...\n", file=sys.stderr)
            cli = CliMonitorApp()
            cli.run()
            sys.exit(0)

        from performance_track.dashboard_tk import UniversalDashboardWindow
        from performance_track.desktop_bar import DesktopBarWidget

        self.config = Config()
        self.monitor = SystemMonitor(
            history_size=self.config.get("history_size", 60),
            update_interval=float(self.config.get("update_interval", 1.0)),
            auto_start_worker=True
        )

        # Root hidden Tkinter instance for window management
        self.root = tk.Tk()
        self.root.withdraw()

        # 1. Full Detailed GUI Dashboard Window
        self.dashboard_window = UniversalDashboardWindow(
            self.monitor,
            self.config,
            on_config_changed=self._on_config_changed,
            on_quit=self.quit,
            master=self.root
        )

        # 2. Always-Visible Desktop Topbar / Bottombar HUD Widget
        self.desktop_bar = DesktopBarWidget(
            self.monitor,
            self.config,
            on_open_dashboard=self.show_dashboard,
            on_quit=self.quit,
            master=self.root
        )

        self.tray_icon = None
        self._running = True
        self._tray_thread = None

        # Cached metrics for menu labels
        self.curr_cpu_label = "⚡ CPU: Calculating..."
        self.curr_ram_label = "💾 RAM: Calculating..."
        self.curr_track_label = "🌐 Track: Calculating..."
        self.curr_net_sub = "Network: ↓ 0 B/s | ↑ 0 B/s"
        self.curr_disk_sub = "Disk I/O: R: 0 B/s | W: 0 B/s"
        self.curr_proc_labels = ["..."] * 5
        self.curr_cores_labels = []

        # Show desktop HUD bar by default
        if self.config.get("show_desktop_bar", True):
            self.desktop_bar.show()

        if HAS_PYSTRAY:
            self._init_pystray()

        if start_with_dashboard or not HAS_PYSTRAY:
            self.show_dashboard()

        # Schedule lightweight tick loop
        self._schedule_tick()

    def toggle_desktop_bar(self):
        if self.desktop_bar.state() == "withdrawn":
            self.desktop_bar.show()
            self.config.set("show_desktop_bar", True)
        else:
            self.desktop_bar.hide()
            self.config.set("show_desktop_bar", False)

    def _create_tray_image(self, cpu_pct=0, ram_pct=0):
        """Render a crisp, modern tray badge with dynamic activity indicator."""
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        draw.rounded_rectangle([2, 2, 62, 62], radius=14, fill=(9, 13, 22, 240), outline=(56, 189, 248, 255), width=3)
        cpu_h = int(max(4, min(44, (cpu_pct / 100.0) * 44)))
        draw.rounded_rectangle([12, 54 - cpu_h, 24, 54], radius=4, fill=(255, 51, 102, 255))
        ram_h = int(max(4, min(44, (ram_pct / 100.0) * 44)))
        draw.rounded_rectangle([28, 54 - ram_h, 40, 54], radius=4, fill=(0, 229, 255, 255))
        draw.ellipse([46, 12, 54, 20], fill=(0, 230, 118, 255))

        return img

    def _build_pystray_menu(self):
        """Construct the context menu for the system tray icon."""
        def make_mode_setter(m_id):
            return lambda: self._set_display_mode(m_id)

        core_items = [pystray_item(lbl, None) for lbl in (self.curr_cores_labels or ["Calculating..."])]
        proc_items = [pystray_item(lbl, None) for lbl in self.curr_proc_labels]

        modes = [
            ("balanced", "Balanced (CPU, RAM, Net/Disk)"),
            ("sparkline", "Sparkline Track"),
            ("compact", "Compact"),
            ("minimal", "Minimal"),
            ("detailed", "Detailed")
        ]
        mode_items = [
            pystray_item(m_text, make_mode_setter(m_id), checked=lambda it, mid=m_id: mid == self.config.get("display_mode", "balanced"))
            for m_id, m_text in modes
        ]

        task_mgr_title = "Task Manager" if SYS_NAME == "Windows" else ("Activity Monitor" if SYS_NAME == "Darwin" else "System Monitor")

        return pystray_menu(
            pystray_item(f"⚡ {APP_NAME} — Open Dashboard", lambda: self.show_dashboard(), default=True),
            pystray_item("📍 Toggle Desktop Topbar / Bottombar", lambda: self.toggle_desktop_bar()),
            pystray_menu.SEPARATOR,
            pystray_item(lambda text: self.curr_cpu_label, pystray_menu(*core_items)),
            pystray_item(lambda text: self.curr_ram_label, None),
            pystray_item(lambda text: self.curr_track_label, pystray_menu(
                pystray_item(lambda text: self.curr_net_sub, None),
                pystray_item(lambda text: self.curr_disk_sub, None)
            )),
            pystray_item("🔥 Top Active Processes", pystray_menu(*proc_items)),
            pystray_menu.SEPARATOR,
            pystray_item("🎨 Display Mode", pystray_menu(*mode_items)),
            pystray_item("🚀 Launch on Startup", self._toggle_autostart,
                         checked=lambda it: self.config.get("autostart", False)),
            pystray_menu.SEPARATOR,
            pystray_item(f"🖥 Open {task_mgr_title}", lambda: _open_native_task_manager()),
            pystray_item("🔄 Refresh Now", lambda: self._on_tick()),
            pystray_item("ℹ About", lambda: self.show_about()),
            pystray_item("✕ Quit", lambda: self.quit())
        )

    def _run_tray_safe(self):
        try:
            if self.tray_icon:
                self.tray_icon.run()
        except Exception:
            self.tray_icon = None
            self.show_dashboard()

    def _init_pystray(self):
        try:
            img = self._create_tray_image(0, 0)
            self.tray_icon = pystray.Icon(
                APP_ID,
                img,
                APP_NAME,
                menu=self._build_pystray_menu()
            )
            self._tray_thread = threading.Thread(target=self._run_tray_safe, daemon=True)
            self._tray_thread.start()
        except Exception:
            self.tray_icon = None

    def _set_display_mode(self, mode_id):
        self.config.set("display_mode", mode_id)
        if self.tray_icon:
            self.tray_icon.update_menu()
        self.desktop_bar.update_telemetry()
        self._on_tick()

    def _toggle_autostart(self):
        curr = self.config.get("autostart", False)
        self.config.set("autostart", not curr)
        self.config.sync_autostart()
        if self.tray_icon:
            self.tray_icon.update_menu()

    def _on_config_changed(self):
        new_interval = float(self.config.get("update_interval", 1.0))
        self.monitor.update_interval = new_interval
        if self.tray_icon:
            self.tray_icon.update_menu()
        self.desktop_bar._position_bar()
        self.desktop_bar.update_telemetry()
        self._on_tick()

    def _schedule_tick(self):
        if not self._running:
            return
        self._on_tick()
        interval_ms = int(float(self.config.get("update_interval", 1.0)) * 1000)
        self.root.after(max(400, interval_ms), self._schedule_tick)

    def _on_tick(self):
        # Non-blocking read from memory snapshot (2 microseconds)
        data = self.monitor.update()

        cpu_pct = data['cpu']['percent']
        ram_pct = data['ram']['percent']
        net_rx = data['track']['net_rx_rate']
        net_tx = data['track']['net_tx_rate']
        disk_rw = data['track']['disk_read_rate'] + data['track']['disk_write_rate']

        used_g = f"{data['ram']['used'] / (1024**3):.1f}G"
        tooltip = f"CPU: {cpu_pct:.0f}% | RAM: {ram_pct:.0f}% ({used_g}) | Net: ↓{format_short_rate(net_rx)}/s ↑{format_short_rate(net_tx)}/s"

        # Update cached labels for pystray menu
        freq_info = f" ({data['cpu']['frequency']:.0f} MHz)" if data['cpu']['frequency'] else ""
        self.curr_cpu_label = f"⚡ CPU: {cpu_pct:.1f}%{freq_info}  {generate_bar(cpu_pct, 8)}"
        self.curr_ram_label = f"💾 RAM: {format_bytes(data['ram']['used'])} / {format_bytes(data['ram']['total'])} ({ram_pct:.1f}%)"
        self.curr_track_label = f"🌐 Track: ↓ {format_rate(net_rx)} | Disk {format_rate(disk_rw)}"
        self.curr_net_sub = f"Network: ↓ {format_rate(net_rx)} | ↑ {format_rate(net_tx)}"
        self.curr_disk_sub = f"Disk I/O: R: {format_rate(data['track']['disk_read_rate'])} | W: {format_rate(data['track']['disk_write_rate'])}"

        # Cores labels
        cores = data['cpu']['cores']
        c_labels = []
        for i, name in enumerate(sorted(cores.keys())):
            cp = cores[name]
            c_labels.append(f"Core {i}: {cp:.1f}%  {generate_bar(cp, 6)}")
        self.curr_cores_labels = c_labels

        # Update tooltip
        if self.tray_icon:
            try:
                self.tray_icon.title = tooltip
            except Exception:
                pass

        # Update desktop bar
        if self.desktop_bar and self.desktop_bar.state() != "withdrawn":
            try:
                self.desktop_bar.update_telemetry()
            except Exception:
                pass

        # Update dashboard if visible
        if self.dashboard_window and self.dashboard_window.state() != "withdrawn":
            try:
                self.dashboard_window.update_ui()
            except Exception:
                pass

    def show_dashboard(self):
        self.root.after(0, self.dashboard_window.show)

    def show_about(self):
        import tkinter.messagebox as mb
        msg = f"{APP_NAME} v{APP_VERSION}\n\n" \
              f"Real-time System Performance Tracker\n" \
              f"Cross-Platform Support for Windows, macOS, and Linux.\n\n" \
              f"Features Always-On Desktop HUD Bar, System Tray, and Full Dashboard."
        mb.showinfo(f"About {APP_NAME}", msg)

    def quit(self):
        self._running = False
        self.monitor.stop_worker()
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        try:
            self.desktop_bar.close()
            self.dashboard_window.close()
            self.root.destroy()
        except Exception:
            pass
        sys.exit(0)

    def run(self):
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.quit()


# ============================================================================
# 2. Ubuntu AppIndicator & GTK3 Native Backend (Linux GNOME)
# ============================================================================
class UbuntuAppIndicatorApp:
    def __init__(self, start_with_dashboard=False):
        try:
            from .dashboard import DashboardWindow
        except (ImportError, ValueError):
            from performance_track.dashboard import DashboardWindow

        self.config = Config()
        self.monitor = SystemMonitor(history_size=self.config.get("history_size", 60))
        self.dashboard_window = None
        self._timer_id = None
        self.indicator = None
        self.lib = lib_appindicator

        self._init_app_indicator()
        self._build_menu()
        self._schedule_timer()

        if start_with_dashboard:
            self.show_dashboard()

    def _init_app_indicator(self):
        self.lib.app_indicator_new.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
        self.lib.app_indicator_new.restype = ctypes.c_void_p

        self.lib.app_indicator_set_status.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.lib.app_indicator_set_label.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
        self.lib.app_indicator_set_menu.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        self.indicator = self.lib.app_indicator_new(
            APP_ID.encode('utf-8'),
            b"utilities-system-monitor-symbolic",
            0
        )
        self.lib.app_indicator_set_status(self.indicator, 1)

    def _build_menu(self):
        self.menu = Gtk.Menu()

        self.item_header = Gtk.MenuItem(label=f"📊 {APP_NAME} — Open Dashboard")
        self.item_header.connect("activate", lambda _: self.show_dashboard())
        self.menu.append(self.item_header)

        self.menu.append(Gtk.SeparatorMenuItem())

        # CPU Menu
        self.item_cpu = Gtk.MenuItem(label="⚡ CPU: Calculating...")
        self.cpu_sub = Gtk.Menu()
        self.cpu_core_items = []
        for i in range(self.monitor.logical_cores):
            c_item = Gtk.MenuItem(label=f"Core {i}: 0%")
            self.cpu_sub.append(c_item)
            self.cpu_core_items.append(c_item)
        self.item_cpu.set_submenu(self.cpu_sub)
        self.menu.append(self.item_cpu)

        # RAM Menu
        self.item_ram = Gtk.MenuItem(label="💾 RAM: Calculating...")
        self.ram_sub = Gtk.Menu()
        self.item_ram_used = Gtk.MenuItem(label="Used: 0 GB")
        self.item_ram_avail = Gtk.MenuItem(label="Available: 0 GB")
        self.item_ram_cached = Gtk.MenuItem(label="Cached/Buffers: 0 GB")
        self.item_swap = Gtk.MenuItem(label="Swap: 0 GB")
        self.ram_sub.append(self.item_ram_used)
        self.ram_sub.append(self.item_ram_avail)
        self.ram_sub.append(self.item_ram_cached)
        self.ram_sub.append(self.item_swap)
        self.item_ram.set_submenu(self.ram_sub)
        self.menu.append(self.item_ram)

        # Track Menu
        self.item_track = Gtk.MenuItem(label="🌐 Track: Calculating...")
        self.track_sub = Gtk.Menu()
        self.item_net_detail = Gtk.MenuItem(label="Net: ↓ 0 B/s | ↑ 0 B/s")
        self.item_net_totals = Gtk.MenuItem(label="Total RX: 0 GB | TX: 0 GB")
        self.item_disk_detail = Gtk.MenuItem(label="Disk: R: 0 B/s | W: 0 B/s")
        self.track_sub.append(self.item_net_detail)
        self.track_sub.append(self.item_net_totals)
        self.track_sub.append(self.item_disk_detail)
        self.item_track.set_submenu(self.track_sub)
        self.menu.append(self.item_track)

        # Processes Menu
        self.item_procs = Gtk.MenuItem(label="🔥 Top Active Processes")
        self.procs_sub = Gtk.Menu()
        self.proc_items = []
        for _ in range(5):
            p_item = Gtk.MenuItem(label="...")
            self.procs_sub.append(p_item)
            self.proc_items.append(p_item)
        self.item_procs.set_submenu(self.procs_sub)
        self.menu.append(self.item_procs)

        self.menu.append(Gtk.SeparatorMenuItem())

        # Display Mode Selector
        item_modes = Gtk.MenuItem(label="🎨 Topbar Display Mode")
        modes_sub = Gtk.Menu()
        mode_options = [
            ("balanced", "Balanced: CPU 12% | RAM 28% | ↓1.2M ↑80K"),
            ("sparkline", "Sparkline Track: CPU 12% ▂ | RAM 28% ▄ | NET 1.2M"),
            ("compact", "Compact: C:12% R:28% P:1.2M"),
            ("minimal", "Minimal: 12% CPU  28% RAM"),
            ("detailed", "Detailed: CPU: 12% (3.9GHz) | RAM: 4.3G/15G | Net: 1.2M")
        ]
        self.mode_menu_items = {}
        curr_mode = self.config.get("display_mode", "balanced")
        for m_id, m_text in mode_options:
            check_item = Gtk.CheckMenuItem(label=m_text)
            check_item.set_active(m_id == curr_mode)
            check_item.connect("toggled", self._make_mode_handler(m_id))
            modes_sub.append(check_item)
            self.mode_menu_items[m_id] = check_item
        item_modes.set_submenu(modes_sub)
        self.menu.append(item_modes)

        # Update Interval Selector
        item_intervals = Gtk.MenuItem(label="⏱ Update Speed")
        intervals_sub = Gtk.Menu()
        curr_interval = float(self.config.get("update_interval", 2.0))
        for sec in [1.0, 2.0, 3.0, 5.0]:
            i_item = Gtk.CheckMenuItem(label=f"{sec:.1f} second" + ("s" if sec > 1 else ""))
            i_item.set_active(abs(sec - curr_interval) < 0.1)
            i_item.connect("toggled", self._make_interval_handler(sec))
            intervals_sub.append(i_item)
        item_intervals.set_submenu(intervals_sub)
        self.menu.append(item_intervals)

        # Autostart Toggle
        self.item_autostart = Gtk.CheckMenuItem(label="🚀 Launch on System Startup")
        self.item_autostart.set_active(self.config.get("autostart", False))
        self.item_autostart.connect("toggled", self._on_autostart_toggle)
        self.menu.append(self.item_autostart)

        self.menu.append(Gtk.SeparatorMenuItem())

        # Task Manager
        item_sysmon = Gtk.MenuItem(label="🖥 Open System Monitor")
        item_sysmon.connect("activate", lambda _: _open_native_task_manager())
        self.menu.append(item_sysmon)

        item_refresh = Gtk.MenuItem(label="🔄 Refresh Now")
        item_refresh.connect("activate", lambda _: self.update_tick())
        self.menu.append(item_refresh)

        item_about = Gtk.MenuItem(label="ℹ About Performance Track")
        item_about.connect("activate", lambda _: self.show_about())
        self.menu.append(item_about)

        item_quit = Gtk.MenuItem(label="✕ Quit")
        item_quit.connect("activate", lambda _: self.quit())
        self.menu.append(item_quit)

        self.menu.show_all()
        self.lib.app_indicator_set_menu(self.indicator, hash(self.menu))

    def _make_mode_handler(self, mode_id):
        def handler(widget):
            if widget.get_active():
                self.config.set("display_mode", mode_id)
                for m_id, item in self.mode_menu_items.items():
                    if m_id != mode_id and item.get_active():
                        item.set_active(False)
                self.update_tick()
        return handler

    def _make_interval_handler(self, sec):
        def handler(widget):
            if widget.get_active():
                self.config.set("update_interval", sec)
                self._schedule_timer()
        return handler

    def _on_autostart_toggle(self, widget):
        active = widget.get_active()
        self.config.set("autostart", active)
        self.config.sync_autostart()

    def _schedule_timer(self):
        if self._timer_id:
            GLib.source_remove(self._timer_id)
        interval_ms = int(float(self.config.get("update_interval", 2.0)) * 1000)
        self._timer_id = GLib.timeout_add(max(500, interval_ms), self._on_timer)

    def _on_timer(self):
        self.update_tick()
        return True

    def update_tick(self):
        data = self.monitor.update()

        mode = self.config.get("display_mode", "balanced")
        cpu_pct = data['cpu']['percent']
        ram_pct = data['ram']['percent']
        net_rx = data['track']['net_rx_rate']
        net_tx = data['track']['net_tx_rate']
        disk_rw = data['track']['disk_read_rate'] + data['track']['disk_write_rate']

        if mode == "sparkline":
            cpu_spark = generate_sparkline(self.monitor.cpu_history[-8:], 0, 100) or " "
            ram_spark = generate_sparkline(self.monitor.ram_history[-8:], 0, 100) or " "
            topbar_text = f"CPU {cpu_pct:.0f}% {cpu_spark} | RAM {ram_pct:.0f}% {ram_spark} | {format_short_rate(net_rx)}/s"
        elif mode == "compact":
            topbar_text = f"C:{cpu_pct:.0f}% R:{ram_pct:.0f}% P:{format_short_rate(net_rx)}"
        elif mode == "minimal":
            topbar_text = f"{cpu_pct:.0f}% CPU  {ram_pct:.0f}% RAM"
        elif mode == "detailed":
            freq_str = f" ({data['cpu']['frequency']:.0f}MHz)" if data['cpu']['frequency'] else ""
            used_g = f"{data['ram']['used'] / (1024**3):.1f}G"
            tot_g = f"{data['ram']['total'] / (1024**3):.1f}G"
            topbar_text = f"CPU: {cpu_pct:.1f}%{freq_str} | RAM: {used_g}/{tot_g} ({ram_pct:.0f}%) | ↓{format_short_rate(net_rx)} ↑{format_short_rate(net_tx)}"
        else:  # "balanced"
            used_g = f"{data['ram']['used'] / (1024**3):.1f}G"
            topbar_text = f"CPU {cpu_pct:.0f}%  |  RAM {ram_pct:.0f}% ({used_g})  |  ↓ {format_short_rate(net_rx)}/s ↑ {format_short_rate(net_tx)}/s"

        guide_text = "CPU 100%  |  RAM 100% (99.9G)  |  ↓ 999.9M/s ↑ 999.9M/s"
        self.lib.app_indicator_set_label(
            self.indicator,
            topbar_text.encode('utf-8'),
            guide_text.encode('utf-8')
        )

        freq_info = f" (Avg {data['cpu']['frequency']:.0f} MHz)" if data['cpu']['frequency'] else ""
        self.item_cpu.set_label(f"⚡ CPU: {cpu_pct:.1f}%{freq_info}  {generate_bar(cpu_pct, 8)}")

        cores = data['cpu']['cores']
        for i, (name, c_item) in enumerate(zip(sorted(cores.keys()), self.cpu_core_items)):
            c_pct = cores.get(name, 0.0)
            c_item.set_label(f"Core {i}: {c_pct:.1f}%  {generate_bar(c_pct, 6)}")

        used_bytes = data['ram']['used']
        tot_bytes = data['ram']['total']
        self.item_ram.set_label(f"💾 RAM: {format_bytes(used_bytes)} / {format_bytes(tot_bytes)} ({ram_pct:.1f}%)")
        self.item_ram_used.set_label(f"Used: {format_bytes(used_bytes)} ({ram_pct:.1f}%)")
        self.item_ram_avail.set_label(f"Available: {format_bytes(data['ram']['available'])}")
        self.item_ram_cached.set_label(f"Cached/Buffers: {format_bytes(data['ram']['cached'])}")
        self.item_swap.set_label(f"Swap: {format_bytes(data['ram']['swap_used'])} / {format_bytes(data['ram']['swap_total'])}")

        self.item_track.set_label(f"🌐 Track: ↓ {format_rate(net_rx)} | Disk {format_rate(disk_rw)}")
        self.item_net_detail.set_label(f"Network: ↓ {format_rate(net_rx)} | ↑ {format_rate(net_tx)}")
        self.item_net_totals.set_label(f"Total RX: {format_bytes(data['track']['net_total_rx'])} | TX: {format_bytes(data['track']['net_total_tx'])}")
        self.item_disk_detail.set_label(f"Disk I/O: Read {format_rate(data['track']['disk_read_rate'])} | Write {format_rate(data['track']['disk_write_rate'])}")

        procs = self.monitor.get_top_processes(count=5, sort_by='cpu')
        for p, item in zip(procs, self.proc_items):
            item.set_label(f"{p['name']} (PID {p['pid']}): {p['cpu']:.1f}% CPU | {p['mem']:.1f}% RAM")

        if self.dashboard_window and self.dashboard_window.get_visible():
            self.dashboard_window.update_ui()

    def show_dashboard(self):
        try:
            from .dashboard import DashboardWindow
        except (ImportError, ValueError):
            from performance_track.dashboard import DashboardWindow

        if not self.dashboard_window:
            self.dashboard_window = DashboardWindow(
                self.monitor,
                self.config,
                on_config_changed=self._on_dashboard_config_changed
            )
            self.dashboard_window.connect("destroy", self._on_dashboard_closed)
        self.dashboard_window.present()

    def _on_dashboard_config_changed(self):
        self._schedule_timer()
        self.update_tick()

    def _on_dashboard_closed(self, *args):
        self.dashboard_window = None

    def show_about(self):
        dialog = Gtk.AboutDialog()
        dialog.set_program_name(APP_NAME)
        dialog.set_version(APP_VERSION)
        dialog.set_comments("A lightweight, real-time RAM, CPU, and Performance Tracking indicator.")
        dialog.set_authors(["Performance Track Contributors"])
        dialog.set_logo_icon_name("utilities-system-monitor")
        dialog.run()
        dialog.destroy()

    def quit(self):
        if self._timer_id:
            GLib.source_remove(self._timer_id)
        if self.dashboard_window:
            self.dashboard_window.destroy()
        Gtk.main_quit()

    def run(self):
        try:
            Gtk.main()
        except KeyboardInterrupt:
            self.quit()


# ============================================================================
# 3. Terminal CLI Live Monitor (for SSH / Headless / Containers)
# ============================================================================
class CliMonitorApp:
    def __init__(self):
        self.monitor = SystemMonitor(history_size=30)
        self.config = Config()

    def run(self):
        print(f"=== {APP_NAME} CLI Monitor v{APP_VERSION} ===")
        print("Press Ctrl+C to stop.\n")
        time.sleep(0.5)

        try:
            while True:
                data = self.monitor.update()
                cpu_p = data['cpu']['percent']
                ram_p = data['ram']['percent']
                net_rx = data['track']['net_rx_rate']
                net_tx = data['track']['net_tx_rate']
                disk_rw = data['track']['disk_read_rate'] + data['track']['disk_write_rate']

                cpu_spark = generate_sparkline(self.monitor.cpu_history[-10:], 0, 100) or " "
                ram_spark = generate_sparkline(self.monitor.ram_history[-10:], 0, 100) or " "

                status_line = (
                    f"\r[CPU {cpu_p:4.1f}% {cpu_spark}] "
                    f"[RAM {ram_p:4.1f}% {ram_spark} ({format_bytes(data['ram']['used'])}/{format_bytes(data['ram']['total'])})] "
                    f"[NET ↓ {format_short_rate(net_rx)}/s ↑ {format_short_rate(net_tx)}/s] "
                    f"[DISK {format_short_rate(disk_rw)}/s] "
                )
                sys.stdout.write(status_line)
                sys.stdout.flush()

                interval = float(self.config.get("update_interval", 1.5))
                time.sleep(max(0.5, interval))
        except KeyboardInterrupt:
            print("\nMonitor stopped.")


# ============================================================================
# Main Entry Point
# ============================================================================
def main():
    # Set High-DPI Awareness on Windows before any GUI window is created
    if SYS_NAME == "Windows":
        try:
            import ctypes
            # Per-Monitor v2 DPI awareness (Windows 10 1703+)
            ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
        except Exception:
            try:
                # Per-Monitor DPI awareness (Windows 8.1+)
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass

    parser = argparse.ArgumentParser(description=f"{APP_NAME} - Real-Time Performance Monitor")
    parser.add_argument("--dashboard", action="store_true", help="Launch with GUI Dashboard window opened immediately")
    parser.add_argument("--cli", action="store_true", help="Run lightweight terminal CLI live monitor mode")
    parser.add_argument("--version", action="version", version=f"%(prog)s {APP_VERSION}")
    args = parser.parse_args()

    # 1. CLI Mode requested
    if args.cli:
        cli_app = CliMonitorApp()
        cli_app.run()
        return

    # 2. Linux GNOME AppIndicator Mode
    if HAS_APPINDICATOR and HAS_GTK:
        app = UbuntuAppIndicatorApp(start_with_dashboard=args.dashboard)
        app.run()
        return

    # 3. Cross-Platform Desktop Mode (Windows, macOS, Linux fallback)
    app = CrossPlatformApp(start_with_dashboard=args.dashboard)
    app.run()


if __name__ == "__main__":
    main()
