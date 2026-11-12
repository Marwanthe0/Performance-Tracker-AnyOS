"""
app.py - Main entry point and AppIndicator topbar controller for Ubuntu Performance Track.
Integrates live CPU, RAM, and Performance Tracking directly onto the Ubuntu GNOME top bar.
"""

import sys
import os
import argparse
import ctypes
import subprocess

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

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
    from .dashboard import DashboardWindow
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
    from performance_track.dashboard import DashboardWindow

APP_ID = "ubuntu-performance-track"
APP_VERSION = "1.0.0"

class PerformanceTrackApp:
    def __init__(self, start_with_dashboard=False):
        self.config = Config()
        self.monitor = SystemMonitor(history_size=self.config.get("history_size", 60))
        self.dashboard_window = None
        self._timer_id = None
        self.indicator = None
        self.lib = None

        self._init_app_indicator()
        self._build_menu()
        self._schedule_timer()

        if start_with_dashboard:
            self.show_dashboard()

    def _init_app_indicator(self):
        """Load libayatana-appindicator3.so.1 and create topbar indicator."""
        try:
            self.lib = ctypes.CDLL('libayatana-appindicator3.so.1')
        except OSError:
            try:
                self.lib = ctypes.CDLL('libappindicator3.so.1')
            except OSError as e:
                print(f"[Error] Neither libayatana-appindicator3 nor libappindicator3 found: {e}", file=sys.stderr)
                sys.exit(1)

        # Function signatures
        self.lib.app_indicator_new.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
        self.lib.app_indicator_new.restype = ctypes.c_void_p

        self.lib.app_indicator_set_status.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.lib.app_indicator_set_label.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
        self.lib.app_indicator_set_menu.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        # Category: 0 (APPLICATION_STATUS), Status: 1 (ACTIVE)
        self.indicator = self.lib.app_indicator_new(
            APP_ID.encode('utf-8'),
            b"utilities-system-monitor-symbolic",
            0
        )
        self.lib.app_indicator_set_status(self.indicator, 1)

    def _build_menu(self):
        """Construct the rich dropdown menu displayed when clicking the topbar indicator."""
        self.menu = Gtk.Menu()

        # 1. Header & Open Dashboard
        self.item_header = Gtk.MenuItem(label="📊 Ubuntu Performance Track — Open Dashboard")
        self.item_header.connect("activate", lambda _: self.show_dashboard())
        self.menu.append(self.item_header)

        self.menu.append(Gtk.SeparatorMenuItem())

        # 2. CPU Usage & Submenu
        self.item_cpu = Gtk.MenuItem(label="⚡ CPU: Calculating...")
        self.cpu_sub = Gtk.Menu()
        self.cpu_core_items = []
        for i in range(self.monitor.logical_cores):
            c_item = Gtk.MenuItem(label=f"Core {i}: 0%")
            self.cpu_sub.append(c_item)
            self.cpu_core_items.append(c_item)
        self.item_cpu.set_submenu(self.cpu_sub)
        self.menu.append(self.item_cpu)

        # 3. RAM & Swap Usage & Submenu
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

        # 4. Performance Track (Network & Disk) & Submenu
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

        # 5. Top Processes Submenu
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

        # 6. Display Format Selector
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

        # 7. Update Interval Selector
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

        # 8. Autostart Toggle
        self.item_autostart = Gtk.CheckMenuItem(label="🚀 Launch on Ubuntu Startup")
        self.item_autostart.set_active(self.config.get("autostart", False))
        self.item_autostart.connect("toggled", self._on_autostart_toggle)
        self.menu.append(self.item_autostart)

        self.menu.append(Gtk.SeparatorMenuItem())

        # 9. Quick Actions
        item_sysmon = Gtk.MenuItem(label="🖥 Open GNOME System Monitor")
        item_sysmon.connect("activate", lambda _: subprocess.Popen(["gnome-system-monitor"]))
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
        """Read metrics and update topbar indicator label and menu items."""
        data = self.monitor.update()

        # Format Topbar Label based on current mode
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

        # Update Dropdown Menu Labels
        freq_info = f" (Avg {data['cpu']['frequency']:.0f} MHz)" if data['cpu']['frequency'] else ""
        self.item_cpu.set_label(f"⚡ CPU: {cpu_pct:.1f}%{freq_info}  {generate_bar(cpu_pct, 8)}")

        # Cores submenu
        cores = data['cpu']['cores']
        for i, (name, c_item) in enumerate(zip(sorted(cores.keys()), self.cpu_core_items)):
            c_pct = cores.get(name, 0.0)
            c_item.set_label(f"Core {i}: {c_pct:.1f}%  {generate_bar(c_pct, 6)}")

        # RAM menu
        used_bytes = data['ram']['used']
        tot_bytes = data['ram']['total']
        self.item_ram.set_label(f"💾 RAM: {format_bytes(used_bytes)} / {format_bytes(tot_bytes)} ({ram_pct:.1f}%)")
        self.item_ram_used.set_label(f"Used: {format_bytes(used_bytes)} ({ram_pct:.1f}%)")
        self.item_ram_avail.set_label(f"Available: {format_bytes(data['ram']['available'])}")
        self.item_ram_cached.set_label(f"Cached/Buffers: {format_bytes(data['ram']['cached'])}")
        self.item_swap.set_label(f"Swap: {format_bytes(data['ram']['swap_used'])} / {format_bytes(data['ram']['swap_total'])}")

        # Performance Track menu
        self.item_track.set_label(f"🌐 Track: ↓ {format_rate(net_rx)} | Disk {format_rate(disk_rw)}")
        self.item_net_detail.set_label(f"Network: ↓ {format_rate(net_rx)} | ↑ {format_rate(net_tx)}")
        self.item_net_totals.set_label(f"Total RX: {format_bytes(data['track']['net_total_rx'])} | TX: {format_bytes(data['track']['net_total_tx'])}")
        self.item_disk_detail.set_label(f"Disk I/O: Read {format_rate(data['track']['disk_read_rate'])} | Write {format_rate(data['track']['disk_write_rate'])}")

        # Top processes menu
        procs = self.monitor.get_top_processes(count=5, sort_by='cpu')
        for p, item in zip(procs, self.proc_items):
            item.set_label(f"{p['name']} (PID {p['pid']}): {p['cpu']:.1f}% CPU | {p['mem']:.1f}% RAM")

        # If dashboard window is open, update its UI
        if self.dashboard_window and self.dashboard_window.get_visible():
            self.dashboard_window.update_ui()

    def show_dashboard(self):
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
        dialog.set_program_name("Ubuntu Performance Track")
        dialog.set_version(APP_VERSION)
        dialog.set_comments("A lightweight, real-time RAM, CPU, and Performance Tracking indicator for Ubuntu topbar.")
        dialog.set_website("https://github.com/ubuntu/performance-track")
        dialog.set_authors(["Ubuntu Performance Track Team", "Antigravity"])
        dialog.set_logo_icon_name("utilities-system-monitor")
        dialog.run()
        dialog.destroy()

    def quit(self):
        if self._timer_id:
            GLib.source_remove(self._timer_id)
        if self.dashboard_window:
            self.dashboard_window.destroy()
        Gtk.main_quit()


def main():
    parser = argparse.ArgumentParser(description="Ubuntu Performance Track Topbar Application")
    parser.add_argument("--dashboard", action="store_true", help="Launch with the GUI Dashboard window open")
    parser.add_argument("--version", action="version", version=f"%(prog)s {APP_VERSION}")
    args = parser.parse_args()

    app = PerformanceTrackApp(start_with_dashboard=args.dashboard)
    try:
        Gtk.main()
    except KeyboardInterrupt:
        app.quit()

if __name__ == "__main__":
    main()
