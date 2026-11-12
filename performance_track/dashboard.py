"""
dashboard.py - Full GTK3 Graphical Dashboard Window for Performance Track.
Provides live Cairo graphs, per-core meters, memory breakdown, process manager, and settings.
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk, Pango
import cairo
import os
import signal
import subprocess

try:
    from .sparkline import format_bytes, format_rate
except (ImportError, ValueError):
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from performance_track.sparkline import format_bytes, format_rate

class HistoryGraph(Gtk.DrawingArea):
    """Custom Cairo widget that draws real-time multi-series line charts with gradient fills."""
    def __init__(self, title, series_configs, max_val=100.0, unit="%"):
        super().__init__()
        self.title = title
        # series_configs: list of {"name": str, "color": (r, g, b), "get_data": callable}
        self.series_configs = series_configs
        self.max_val = max_val
        self.unit = unit
        self.set_size_request(300, 150)
        self.connect("draw", self.on_draw)

    def on_draw(self, widget, cr):
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()

        # Background
        cr.set_source_rgb(0.12, 0.13, 0.15)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        pad_left = 45
        pad_right = 15
        pad_top = 28
        pad_bottom = 20

        plot_w = max(10, width - pad_left - pad_right)
        plot_h = max(10, height - pad_top - pad_bottom)

        # Draw grid lines and labels
        cr.set_line_width(1.0)
        cr.set_source_rgba(0.3, 0.33, 0.38, 0.5)

        for step in [0.25, 0.5, 0.75, 1.0]:
            y = pad_top + plot_h * (1.0 - step)
            cr.move_to(pad_left, y)
            cr.line_to(pad_left + plot_w, y)
            cr.stroke()

            # Axis label
            val_text = f"{int(self.max_val * step)}{self.unit}"
            cr.set_source_rgba(0.7, 0.7, 0.7, 0.8)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(9)
            cr.move_to(8, y + 3)
            cr.show_text(val_text)
            cr.set_source_rgba(0.3, 0.33, 0.38, 0.5)

        # Title
        cr.set_source_rgb(0.9, 0.9, 0.9)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(11)
        cr.move_to(pad_left, 18)
        cr.show_text(self.title)

        # Legend (top right)
        legend_x = pad_left + 160
        for s in self.series_configs:
            r, g, b = s["color"]
            cr.set_source_rgb(r, g, b)
            cr.rectangle(legend_x, 9, 8, 8)
            cr.fill()
            cr.set_source_rgb(0.8, 0.8, 0.8)
            cr.set_font_size(9)
            cr.move_to(legend_x + 12, 16)
            cr.show_text(s["name"])
            legend_x += 80

        # Draw series data
        for s in self.series_configs:
            data = s["get_data"]()
            if not data or len(data) < 2:
                continue

            r, g, b = s["color"]
            n = len(data)
            dx = plot_w / max(1, n - 1)

            points = []
            for i, val in enumerate(data):
                px = pad_left + i * dx
                ratio = max(0.0, min(1.0, float(val) / max(0.001, self.max_val)))
                py = pad_top + plot_h * (1.0 - ratio)
                points.append((px, py))

            # Filled area under the curve
            cr.move_to(points[0][0], pad_top + plot_h)
            for px, py in points:
                cr.line_to(px, py)
            cr.line_to(points[-1][0], pad_top + plot_h)
            cr.close_path()
            cr.set_source_rgba(r, g, b, 0.18)
            cr.fill()

            # Line stroke
            cr.set_source_rgb(r, g, b)
            cr.set_line_width(2.0)
            cr.move_to(points[0][0], points[0][1])
            for px, py in points[1:]:
                cr.line_to(px, py)
            cr.stroke()

        # Border around plot
        cr.set_source_rgba(0.4, 0.45, 0.5, 0.8)
        cr.set_line_width(1.0)
        cr.rectangle(pad_left, pad_top, plot_w, plot_h)
        cr.stroke()

        return False


class DashboardWindow(Gtk.Window):
    def __init__(self, monitor, config, on_config_changed=None):
        super().__init__(title="Ubuntu Performance Track Dashboard")
        self.monitor = monitor
        self.config = config
        self.on_config_changed = on_config_changed

        self.set_default_size(840, 600)
        self.set_position(Gtk.WindowPosition.CENTER)

        # Setup HeaderBar
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title("Performance Track")
        header.set_subtitle(f"{os.uname().nodename} ({os.uname().release})")
        self.set_titlebar(header)

        # Header buttons
        btn_refresh = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        btn_refresh.set_tooltip_text("Refresh Metrics Now")
        btn_refresh.connect("clicked", lambda _: self.update_ui())
        header.pack_start(btn_refresh)

        btn_sysmon = Gtk.Button.new_with_label("GNOME System Monitor")
        btn_sysmon.set_tooltip_text("Open GNOME System Monitor")
        btn_sysmon.connect("clicked", lambda _: subprocess.Popen(["gnome-system-monitor"]))
        header.pack_end(btn_sysmon)

        # Main notebook
        self.notebook = Gtk.Notebook()
        self.add(self.notebook)

        # Tab 1: Overview & Graphs
        self.notebook.append_page(self._build_overview_tab(), Gtk.Label(label="Overview & Graphs"))

        # Tab 2: CPU Cores
        self.notebook.append_page(self._build_cpu_tab(), Gtk.Label(label="CPU Details"))

        # Tab 3: Memory & Storage
        self.notebook.append_page(self._build_memory_tab(), Gtk.Label(label="Memory & Storage"))

        # Tab 4: Process Monitor
        self.notebook.append_page(self._build_process_tab(), Gtk.Label(label="Processes"))

        # Tab 5: Preferences
        self.notebook.append_page(self._build_preferences_tab(), Gtk.Label(label="Preferences"))

        # Timer for UI refresh
        self._timer_id = GLib.timeout_add(1000, self._on_timer)
        self.connect("destroy", self._on_destroy)

        # Initial UI update
        self.update_ui()

    def _on_timer(self):
        self.update_ui()
        return True

    def _on_destroy(self, *args):
        if self._timer_id:
            GLib.source_remove(self._timer_id)
            self._timer_id = None

    def _create_card(self, title, initial_val="0%", color="#3182ce"):
        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(14)
        box.set_margin_end(14)

        lbl_title = Gtk.Label()
        lbl_title.set_markup(f"<small><b>{title}</b></small>")
        lbl_title.set_xalign(0.0)

        lbl_val = Gtk.Label()
        lbl_val.set_markup(f"<span size='xx-large' weight='bold' foreground='{color}'>{initial_val}</span>")
        lbl_val.set_xalign(0.0)

        lbl_sub = Gtk.Label(label="")
        lbl_sub.set_xalign(0.0)

        box.pack_start(lbl_title, False, False, 0)
        box.pack_start(lbl_val, False, False, 0)
        box.pack_start(lbl_sub, False, False, 0)
        frame.add(box)
        return frame, lbl_val, lbl_sub

    def _build_overview_tab(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_top(14)
        main_box.set_margin_bottom(14)
        main_box.set_margin_start(14)
        main_box.set_margin_end(14)

        # Top 4 summary cards
        cards_grid = Gtk.Grid()
        cards_grid.set_column_spacing(10)
        cards_grid.set_column_homogeneous(True)

        self.card_cpu, self.lbl_cpu_val, self.lbl_cpu_sub = self._create_card("CPU UTILIZATION", "0%", "#e53e3e")
        self.card_ram, self.lbl_ram_val, self.lbl_ram_sub = self._create_card("RAM UTILIZATION", "0%", "#3182ce")
        self.card_net, self.lbl_net_val, self.lbl_net_sub = self._create_card("NETWORK TRACK", "0 B/s", "#38a169")
        self.card_disk, self.lbl_disk_val, self.lbl_disk_sub = self._create_card("DISK I/O TRACK", "0 B/s", "#805ad5")

        cards_grid.attach(self.card_cpu, 0, 0, 1, 1)
        cards_grid.attach(self.card_ram, 1, 0, 1, 1)
        cards_grid.attach(self.card_net, 2, 0, 1, 1)
        cards_grid.attach(self.card_disk, 3, 0, 1, 1)
        main_box.pack_start(cards_grid, False, False, 0)

        # Graphs
        graphs_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # Graph 1: CPU & RAM
        self.cpu_ram_graph = HistoryGraph(
            title="CPU & RAM Performance Track",
            series_configs=[
                {"name": "CPU", "color": (0.9, 0.25, 0.25), "get_data": lambda: self.monitor.cpu_history},
                {"name": "RAM", "color": (0.2, 0.5, 0.85), "get_data": lambda: self.monitor.ram_history}
            ],
            max_val=100.0,
            unit="%"
        )
        graphs_box.pack_start(self.cpu_ram_graph, True, True, 0)

        # Graph 2: Network & Disk
        self.io_graph = HistoryGraph(
            title="I/O Throughput Track (MB/s)",
            series_configs=[
                {"name": "Net Download", "color": (0.22, 0.7, 0.4), "get_data": lambda: [x / (1024*1024) for x in self.monitor.net_rx_history]},
                {"name": "Disk Write", "color": (0.6, 0.35, 0.8), "get_data": lambda: [x / (1024*1024) for x in self.monitor.disk_write_history]}
            ],
            max_val=10.0,
            unit="M"
        )
        graphs_box.pack_start(self.io_graph, True, True, 0)

        main_box.pack_start(graphs_box, True, True, 0)
        return main_box

    def _build_cpu_tab(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_margin_top(14)
        box.set_margin_bottom(14)
        box.set_margin_start(16)
        box.set_margin_end(16)

        # CPU info header
        self.lbl_cpu_model = Gtk.Label()
        self.lbl_cpu_model.set_xalign(0.0)
        self.lbl_cpu_model.set_markup("<b>Processor:</b> Loading...")
        box.pack_start(self.lbl_cpu_model, False, False, 0)

        self.lbl_cpu_stats = Gtk.Label()
        self.lbl_cpu_stats.set_xalign(0.0)
        box.pack_start(self.lbl_cpu_stats, False, False, 0)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        box.pack_start(sep, False, False, 4)

        lbl_cores_title = Gtk.Label()
        lbl_cores_title.set_markup("<b>Individual Core Utilization</b>")
        lbl_cores_title.set_xalign(0.0)
        box.pack_start(lbl_cores_title, False, False, 0)

        # Grid for core progress bars
        self.cores_grid = Gtk.Grid()
        self.cores_grid.set_column_spacing(18)
        self.cores_grid.set_row_spacing(10)
        self.cores_grid.set_column_homogeneous(True)
        box.pack_start(self.cores_grid, True, True, 0)

        self.core_widgets = {}  # name -> (label, progress_bar)

        scrolled.add(box)
        return scrolled

    def _build_memory_tab(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(18)
        box.set_margin_end(18)

        # RAM section
        lbl_ram_title = Gtk.Label()
        lbl_ram_title.set_markup("<b>Physical Memory (RAM)</b>")
        lbl_ram_title.set_xalign(0.0)
        box.pack_start(lbl_ram_title, False, False, 0)

        self.ram_progress = Gtk.ProgressBar()
        self.ram_progress.set_show_text(True)
        box.pack_start(self.ram_progress, False, False, 0)

        self.lbl_ram_details = Gtk.Label()
        self.lbl_ram_details.set_xalign(0.0)
        box.pack_start(self.lbl_ram_details, False, False, 0)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        box.pack_start(sep, False, False, 8)

        # Swap section
        lbl_swap_title = Gtk.Label()
        lbl_swap_title.set_markup("<b>Swap Space</b>")
        lbl_swap_title.set_xalign(0.0)
        box.pack_start(lbl_swap_title, False, False, 0)

        self.swap_progress = Gtk.ProgressBar()
        self.swap_progress.set_show_text(True)
        box.pack_start(self.swap_progress, False, False, 0)

        self.lbl_swap_details = Gtk.Label()
        self.lbl_swap_details.set_xalign(0.0)
        box.pack_start(self.lbl_swap_details, False, False, 0)

        return box

    def _build_process_tab(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(12)
        box.set_margin_end(12)

        # Controls bar
        ctrl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_sort = Gtk.Label(label="Sort by:")
        self.combo_sort = Gtk.ComboBoxText()
        self.combo_sort.append("cpu", "CPU Usage (%)")
        self.combo_sort.append("mem", "Memory Usage (%)")
        self.combo_sort.set_active(0)
        self.combo_sort.connect("changed", lambda _: self._update_processes())

        btn_kill = Gtk.Button.new_with_label("End Selected Process")
        btn_kill.connect("clicked", self._on_kill_clicked)

        ctrl_box.pack_start(lbl_sort, False, False, 0)
        ctrl_box.pack_start(self.combo_sort, False, False, 0)
        ctrl_box.pack_end(btn_kill, False, False, 0)
        box.pack_start(ctrl_box, False, False, 0)

        # Process TreeView
        # Columns: PID (int), User (str), Name (str), CPU (float), Mem (float)
        self.proc_store = Gtk.ListStore(int, str, str, float, float)
        self.proc_tree = Gtk.TreeView(model=self.proc_store)

        for i, col_title in enumerate(["PID", "User", "Process Name", "% CPU", "% RAM"]):
            renderer = Gtk.CellRendererText()
            if i in [3, 4]:
                col = Gtk.TreeViewColumn(col_title, renderer, text=i)
                col.set_cell_data_func(renderer, lambda c, r, m, it, idx=i: r.set_property('text', f"{m.get_value(it, idx):.1f}%"))
            else:
                col = Gtk.TreeViewColumn(col_title, renderer, text=i)
            col.set_sort_column_id(i)
            col.set_resizable(True)
            self.proc_tree.append_column(col)

        scrolled = Gtk.ScrolledWindow()
        scrolled.add(self.proc_tree)
        box.pack_start(scrolled, True, True, 0)

        return box

    def _build_preferences_tab(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(18)
        box.set_margin_end(18)

        grid = Gtk.Grid()
        grid.set_column_spacing(16)
        grid.set_row_spacing(12)

        # Display Mode
        lbl_mode = Gtk.Label(label="Topbar Display Format:")
        lbl_mode.set_xalign(0.0)
        self.combo_mode = Gtk.ComboBoxText()
        modes = [
            ("balanced", "Balanced (CPU, RAM, Net/Disk)"),
            ("sparkline", "Sparkline Track (Live Unicode Wave)"),
            ("compact", "Compact (Short rates)"),
            ("minimal", "Minimal (CPU & RAM only)"),
            ("detailed", "Detailed (Frequencies & Full rates)")
        ]
        for m_id, m_label in modes:
            self.combo_mode.append(m_id, m_label)
        self.combo_mode.set_active_id(self.config.get("display_mode", "balanced"))
        self.combo_mode.connect("changed", self._on_pref_changed)

        grid.attach(lbl_mode, 0, 0, 1, 1)
        grid.attach(self.combo_mode, 1, 0, 1, 1)

        # Refresh Interval
        lbl_interval = Gtk.Label(label="Update Interval (seconds):")
        lbl_interval.set_xalign(0.0)
        self.spin_interval = Gtk.SpinButton.new_with_range(1.0, 10.0, 0.5)
        self.spin_interval.set_value(float(self.config.get("update_interval", 2.0)))
        self.spin_interval.connect("value-changed", self._on_pref_changed)

        grid.attach(lbl_interval, 0, 1, 1, 1)
        grid.attach(self.spin_interval, 1, 1, 1, 1)

        # Autostart
        lbl_auto = Gtk.Label(label="Launch automatically on Ubuntu login:")
        lbl_auto.set_xalign(0.0)
        self.switch_auto = Gtk.Switch()
        self.switch_auto.set_active(self.config.get("autostart", False))
        self.switch_auto.connect("notify::active", self._on_autostart_toggled)

        grid.attach(lbl_auto, 0, 2, 1, 1)
        grid.attach(self.switch_auto, 1, 2, 1, 1)

        box.pack_start(grid, False, False, 0)
        return box

    def _on_pref_changed(self, *args):
        mode = self.combo_mode.get_active_id()
        interval = self.spin_interval.get_value()
        self.config.set("display_mode", mode)
        self.config.set("update_interval", interval)
        if self.on_config_changed:
            self.on_config_changed()

    def _on_autostart_toggled(self, switch, gparam):
        active = switch.get_active()
        self.config.set("autostart", active)
        self.config.sync_autostart()

    def _on_kill_clicked(self, *args):
        selection = self.proc_tree.get_selection()
        model, treeiter = selection.get_selected()
        if treeiter:
            pid = model.get_value(treeiter, 0)
            name = model.get_value(treeiter, 2)
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK_CANCEL,
                text=f"Terminate process {name} (PID: {pid})?"
            )
            dialog.format_secondary_text("This will send SIGTERM to safely end the process.")
            response = dialog.run()
            dialog.destroy()
            if response == Gtk.ResponseType.OK:
                try:
                    os.kill(pid, signal.SIGTERM)
                except Exception as e:
                    err_dlg = Gtk.MessageDialog(
                        transient_for=self,
                        flags=0,
                        message_type=Gtk.MessageType.ERROR,
                        buttons=Gtk.ButtonsType.OK,
                        text=f"Failed to terminate process: {e}"
                    )
                    err_dlg.run()
                    err_dlg.destroy()
                self._update_processes()

    def _update_processes(self):
        sort_by = self.combo_sort.get_active_id() or 'cpu'
        procs = self.monitor.get_top_processes(count=15, sort_by=sort_by)
        self.proc_store.clear()
        for p in procs:
            self.proc_store.append([p['pid'], p['user'], p['name'], p['cpu'], p['mem']])

    def update_ui(self):
        data = self.monitor.update()

        # Update summary cards
        cpu_pct = data['cpu']['percent']
        ram_pct = data['ram']['percent']
        net_rx = data['track']['net_rx_rate']
        net_tx = data['track']['net_tx_rate']
        disk_rw = data['track']['disk_read_rate'] + data['track']['disk_write_rate']

        self.lbl_cpu_val.set_markup(f"<span size='xx-large' weight='bold' foreground='#e53e3e'>{cpu_pct:.1f}%</span>")
        freq_str = f"{data['cpu']['frequency']:.0f} MHz" if data['cpu']['frequency'] else ""
        temp_str = f" | {data['cpu']['temperature']:.1f}°C" if data['cpu']['temperature'] else ""
        self.lbl_cpu_sub.set_text(f"{freq_str}{temp_str} (Load: {data['cpu']['load'][0]:.2f})")

        used_ram = format_bytes(data['ram']['used'])
        total_ram = format_bytes(data['ram']['total'])
        self.lbl_ram_val.set_markup(f"<span size='xx-large' weight='bold' foreground='#3182ce'>{ram_pct:.1f}%</span>")
        self.lbl_ram_sub.set_text(f"{used_ram} / {total_ram} used")

        self.lbl_net_val.set_markup(f"<span size='xx-large' weight='bold' foreground='#38a169'>{format_rate(net_rx)}</span>")
        self.lbl_net_sub.set_text(f"↑ {format_rate(net_tx)}")

        self.lbl_disk_val.set_markup(f"<span size='xx-large' weight='bold' foreground='#805ad5'>{format_rate(disk_rw)}</span>")
        self.lbl_disk_sub.set_text(f"R: {format_rate(data['track']['disk_read_rate'])} | W: {format_rate(data['track']['disk_write_rate'])}")

        # Redraw Cairo graphs
        max_io = max(1.0, max(self.monitor.net_rx_history or [0]) / (1024*1024), max(self.monitor.disk_write_history or [0]) / (1024*1024))
        self.io_graph.max_val = max(5.0, max_io * 1.25)
        self.cpu_ram_graph.queue_draw()
        self.io_graph.queue_draw()

        # Update CPU cores grid
        self.lbl_cpu_model.set_markup(f"<b>Processor:</b> {data['cpu']['model']} ({data['cpu']['cores_count']} logical cores)")
        self.lbl_cpu_stats.set_markup(
            f"<b>Average Frequency:</b> {data['cpu']['frequency']:.0f} MHz  |  "
            f"<b>Load Average:</b> 1m: {data['cpu']['load'][0]:.2f}, 5m: {data['cpu']['load'][1]:.2f}, 15m: {data['cpu']['load'][2]:.2f}  |  "
            f"<b>Uptime:</b> {data['system']['uptime']}"
        )

        cores = data['cpu']['cores']
        row = 0
        col = 0
        for name in sorted(cores.keys(), key=lambda x: int(x.replace('cpu', '')) if x.replace('cpu', '').isdigit() else 999):
            val = cores[name]
            if name not in self.core_widgets:
                c_lbl = Gtk.Label()
                c_lbl.set_xalign(0.0)
                c_prog = Gtk.ProgressBar()
                c_prog.set_show_text(True)
                box_core = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                box_core.pack_start(c_lbl, False, False, 0)
                box_core.pack_start(c_prog, False, False, 0)
                self.cores_grid.attach(box_core, col, row, 1, 1)
                box_core.show_all()
                self.core_widgets[name] = (c_lbl, c_prog)

                col += 1
                if col >= 3:
                    col = 0
                    row += 1

            lbl_w, prog_w = self.core_widgets[name]
            lbl_w.set_text(f"Core {name.replace('cpu', '')}: {val:.1f}%")
            prog_w.set_fraction(max(0.0, min(1.0, val / 100.0)))

        # Update Memory tab
        self.ram_progress.set_fraction(max(0.0, min(1.0, data['ram']['percent'] / 100.0)))
        self.ram_progress.set_text(f"{data['ram']['percent']:.1f}% ({used_ram} / {total_ram})")
        self.lbl_ram_details.set_markup(
            f"<b>Total:</b> {total_ram}   |   "
            f"<b>Used:</b> {used_ram}   |   "
            f"<b>Available:</b> {format_bytes(data['ram']['available'])}   |   "
            f"<b>Cached/Buffers:</b> {format_bytes(data['ram']['cached'])}   |   "
            f"<b>Free:</b> {format_bytes(data['ram']['free'])}"
        )

        swap_used = format_bytes(data['ram']['swap_used'])
        swap_total = format_bytes(data['ram']['swap_total'])
        self.swap_progress.set_fraction(max(0.0, min(1.0, data['ram']['swap_percent'] / 100.0)))
        self.swap_progress.set_text(f"{data['ram']['swap_percent']:.1f}% ({swap_used} / {swap_total})")
        self.lbl_swap_details.set_markup(
            f"<b>Swap Total:</b> {swap_total}   |   "
            f"<b>Swap Used:</b> {swap_used}   |   "
            f"<b>Swap Free:</b> {format_bytes(data['ram']['swap_free'])}"
        )

        # Update Processes
        self._update_processes()
