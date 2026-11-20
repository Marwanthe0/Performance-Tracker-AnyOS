"""
dashboard_tk.py - High-Performance Universal GUI Dashboard Window for Performance Track.
Features a modern Cyberpunk/Slate dark UI, hardware-accelerated canvas graphs,
smooth per-core progress bars, and a searchable/filterable process manager.
"""

import os
import sys
import time
import platform
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

try:
    from .sparkline import format_bytes, format_rate
except (ImportError, ValueError):
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from performance_track.sparkline import format_bytes, format_rate

SYS_NAME = platform.system()


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
        print(f"Failed to open native task manager: {e}", file=sys.stderr)


class TkHistoryGraph(tk.Canvas):
    """Real-time multi-series line chart with grid lines, numeric scale, and gradient area fills."""
    def __init__(self, parent, title, series_configs, max_val=100.0, unit="%", **kwargs):
        super().__init__(parent, bg="#0d111a", highlightthickness=0, **kwargs)
        self.title = title
        self.series_configs = series_configs
        self.max_val = max_val
        self.unit = unit
        self.bind("<Configure>", lambda e: self.redraw())

    def redraw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 50 or h < 50:
            return

        pad_left = 54
        pad_right = 20
        pad_top = 28
        pad_bottom = 22

        plot_w = max(10, w - pad_left - pad_right)
        plot_h = max(10, h - pad_top - pad_bottom)

        # Draw grid lines & numeric scale
        for step in [0.25, 0.5, 0.75, 1.0]:
            y = pad_top + plot_h * (1.0 - step)
            self.create_line(pad_left, y, pad_left + plot_w, y, fill="#1c2333", width=1, dash=(3, 3))
            val_num = int(self.max_val * step) if self.max_val >= 4 else round(self.max_val * step, 1)
            val_text = f"{val_num}{self.unit}"
            self.create_text(pad_left - 8, y, text=val_text, fill="#64748b", font=("Helvetica", 8), anchor="e")

        # Bottom baseline
        self.create_line(pad_left, pad_top + plot_h, pad_left + plot_w, pad_top + plot_h, fill="#2a3449", width=1)

        # Title
        self.create_text(pad_left, 14, text=self.title, fill="#f1f5f9", font=("Helvetica", 10, "bold"), anchor="w")

        # Legend
        legend_x = max(pad_left + 150, w - pad_right - (len(self.series_configs) * 110))
        for s in self.series_configs:
            self.create_rectangle(legend_x, 8, legend_x + 10, 18, fill=s["color"], outline="")
            self.create_text(legend_x + 14, 13, text=s["name"], fill="#cbd5e1", font=("Helvetica", 8, "bold"), anchor="w")
            legend_x += 105

        # Plot series lines and area
        for s in self.series_configs:
            data = s["get_data"]()
            if not data or len(data) < 2:
                continue

            n = len(data)
            dx = plot_w / max(1, n - 1)
            points = []
            for i, val in enumerate(data):
                px = pad_left + i * dx
                ratio = max(0.0, min(1.0, float(val) / max(0.0001, self.max_val)))
                py = pad_top + plot_h * (1.0 - ratio)
                points.append((px, py))

            # Filled area
            poly_points = [pad_left, pad_top + plot_h]
            for px, py in points:
                poly_points.extend([px, py])
            poly_points.extend([points[-1][0], pad_top + plot_h])

            fill_c = s.get("fill_color", "#162032")
            self.create_polygon(poly_points, fill=fill_c, outline="")

            # Stroke curve
            flat_pts = []
            for px, py in points:
                flat_pts.extend([px, py])
            self.create_line(flat_pts, fill=s["color"], width=2, smooth=True)

        # Border
        self.create_rectangle(pad_left, pad_top, pad_left + plot_w, pad_top + plot_h, outline="#232d40", width=1)


class UniversalDashboardWindow(tk.Toplevel):
    def __init__(self, monitor, config, on_config_changed=None, master=None):
        super().__init__(master)
        self.monitor = monitor
        self.config = config
        self.on_config_changed = on_config_changed

        self.title("Performance Track Dashboard")
        self.geometry("920x650")
        self.minsize(780, 520)
        self.configure(bg="#080b12")

        # Intercept close button: Hide instead of destroy so the Desktop Bar stays alive
        self.protocol("WM_DELETE_WINDOW", self.hide)

        if SYS_NAME == "Windows":
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                pass

        self._search_query = ""
        self._setup_styles()
        self._build_header()
        self._build_tabs()

        self._timer_running = True
        self._update_loop()

    def _setup_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("TNotebook", background="#080b12", borderwidth=0)
        style.configure("TNotebook.Tab", background="#121724", foreground="#94a3b8",
                        padding=[18, 9], font=("Helvetica", 9, "bold"), borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", "#1e293b"), ("active", "#182133")],
                  foreground=[("selected", "#38bdf8"), ("active", "#f1f5f9")])

        style.configure("Treeview",
                        background="#0d111a",
                        foreground="#e2e8f0",
                        fieldbackground="#0d111a",
                        rowheight=26,
                        font=("Helvetica", 9),
                        borderwidth=0)
        style.configure("Treeview.Heading",
                        background="#182030",
                        foreground="#94a3b8",
                        font=("Helvetica", 9, "bold"),
                        borderwidth=1,
                        relief="flat")
        style.map("Treeview",
                  background=[("selected", "#2563eb")],
                  foreground=[("selected", "#ffffff")])

        style.configure("Horizontal.TProgressbar",
                        troughcolor="#131926",
                        background="#38bdf8",
                        borderwidth=0,
                        thickness=14)

    def _build_header(self):
        header_frame = tk.Frame(self, bg="#0d121e", height=54)
        header_frame.pack(fill="x", side="top")

        left_box = tk.Frame(header_frame, bg="#0d121e")
        left_box.pack(side="left", padx=18, pady=10)

        lbl_app = tk.Label(left_box, text="⚡ Performance Track", font=("Helvetica", 14, "bold"),
                           fg="#38bdf8", bg="#0d121e")
        lbl_app.pack(side="left")

        self.lbl_host = tk.Label(left_box, text="", font=("Helvetica", 9), fg="#64748b", bg="#0d121e")
        self.lbl_host.pack(side="left", padx=12)

        right_box = tk.Frame(header_frame, bg="#0d121e")
        right_box.pack(side="right", padx=18, pady=10)

        btn_refresh = tk.Button(right_box, text="🔄 Refresh", font=("Helvetica", 9, "bold"),
                                bg="#1e293b", fg="#e2e8f0", activebackground="#334155",
                                activeforeground="#ffffff", relief="flat", bd=0, padx=12, pady=4,
                                command=self.update_ui)
        btn_refresh.pack(side="left", padx=6)

        sys_label = "Task Manager" if SYS_NAME == "Windows" else ("Activity Monitor" if SYS_NAME == "Darwin" else "System Monitor")
        btn_sys = tk.Button(right_box, text=f"🖥 {sys_label}", font=("Helvetica", 9, "bold"),
                            bg="#1e293b", fg="#38bdf8", activebackground="#334155",
                            activeforeground="#ffffff", relief="flat", bd=0, padx=12, pady=4,
                            command=_open_native_task_manager)
        btn_sys.pack(side="left", padx=6)

    def _build_tabs(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=10)

        self.tab_overview = tk.Frame(self.notebook, bg="#080b12")
        self.tab_cpu = tk.Frame(self.notebook, bg="#080b12")
        self.tab_memory = tk.Frame(self.notebook, bg="#080b12")
        self.tab_processes = tk.Frame(self.notebook, bg="#080b12")
        self.tab_prefs = tk.Frame(self.notebook, bg="#080b12")

        self.notebook.add(self.tab_overview, text=" Overview & Graphs ")
        self.notebook.add(self.tab_cpu, text=" CPU Details ")
        self.notebook.add(self.tab_memory, text=" Memory & Storage ")
        self.notebook.add(self.tab_processes, text=" Processes ")
        self.notebook.add(self.tab_prefs, text=" Preferences ")

        self._build_overview_tab()
        self._build_cpu_tab()
        self._build_memory_tab()
        self._build_processes_tab()
        self._build_preferences_tab()

    def _create_card(self, parent, title, color="#38bdf8"):
        card = tk.Frame(parent, bg="#111724", bd=1, relief="solid")
        card.config(highlightbackground="#1c2538")

        lbl_t = tk.Label(card, text=title, font=("Helvetica", 8, "bold"), fg="#94a3b8", bg="#111724")
        lbl_t.pack(anchor="w", padx=14, pady=(12, 2))

        lbl_val = tk.Label(card, text="0%", font=("Helvetica", 20, "bold"), fg=color, bg="#111724")
        lbl_val.pack(anchor="w", padx=14, pady=(0, 2))

        lbl_sub = tk.Label(card, text="", font=("Helvetica", 8), fg="#64748b", bg="#111724")
        lbl_sub.pack(anchor="w", padx=14, pady=(0, 12))

        return card, lbl_val, lbl_sub

    def _build_overview_tab(self):
        cards_frame = tk.Frame(self.tab_overview, bg="#080b12")
        cards_frame.pack(fill="x", padx=6, pady=8)
        cards_frame.columnconfigure((0, 1, 2, 3), weight=1, uniform="cards")

        c1, self.lbl_card_cpu, self.lbl_sub_cpu = self._create_card(cards_frame, "CPU UTILIZATION", "#ff3366")
        c2, self.lbl_card_ram, self.lbl_sub_ram = self._create_card(cards_frame, "RAM UTILIZATION", "#00e5ff")
        c3, self.lbl_card_net, self.lbl_sub_net = self._create_card(cards_frame, "NETWORK THROUGHPUT", "#00e676")
        c4, self.lbl_card_disk, self.lbl_sub_disk = self._create_card(cards_frame, "DISK I/O ACTIVITY", "#b388ff")

        c1.grid(row=0, column=0, padx=6, sticky="nsew")
        c2.grid(row=0, column=1, padx=6, sticky="nsew")
        c3.grid(row=0, column=2, padx=6, sticky="nsew")
        c4.grid(row=0, column=3, padx=6, sticky="nsew")

        graphs_frame = tk.Frame(self.tab_overview, bg="#080b12")
        graphs_frame.pack(fill="both", expand=True, padx=6, pady=6)

        self.graph_cpu_ram = TkHistoryGraph(
            graphs_frame,
            title="CPU & RAM Performance Track",
            series_configs=[
                {"name": "CPU Usage", "color": "#ff3366", "fill_color": "#28121c", "get_data": lambda: list(self.monitor.cpu_history)},
                {"name": "RAM Usage", "color": "#00e5ff", "fill_color": "#0c2534", "get_data": lambda: list(self.monitor.ram_history)}
            ],
            max_val=100.0,
            unit="%",
            height=155
        )
        self.graph_cpu_ram.pack(fill="both", expand=True, pady=4)

        self.graph_io = TkHistoryGraph(
            graphs_frame,
            title="I/O Throughput Track (MB/s)",
            series_configs=[
                {"name": "Net Download", "color": "#00e676", "fill_color": "#0e291e",
                 "get_data": lambda: [x / (1024 * 1024) for x in self.monitor.net_rx_history]},
                {"name": "Disk Activity", "color": "#b388ff", "fill_color": "#231636",
                 "get_data": lambda: [x / (1024 * 1024) for x in self.monitor.disk_write_history]}
            ],
            max_val=10.0,
            unit="M",
            height=155
        )
        self.graph_io.pack(fill="both", expand=True, pady=4)

    def _build_cpu_tab(self):
        wrap = tk.Frame(self.tab_cpu, bg="#080b12")
        wrap.pack(fill="both", expand=True, padx=18, pady=14)

        self.lbl_cpu_name = tk.Label(wrap, text="Processor: Detecting...", font=("Helvetica", 12, "bold"),
                                     fg="#f8fafc", bg="#080b12", anchor="w")
        self.lbl_cpu_name.pack(fill="x", pady=2)

        self.lbl_cpu_details = tk.Label(wrap, text="", font=("Helvetica", 9), fg="#94a3b8", bg="#080b12", anchor="w")
        self.lbl_cpu_details.pack(fill="x", pady=2)

        tk.Frame(wrap, height=1, bg="#1e2536").pack(fill="x", pady=12)

        tk.Label(wrap, text="Individual CPU Core Load Trajectory", font=("Helvetica", 10, "bold"),
                 fg="#e2e8f0", bg="#080b12", anchor="w").pack(fill="x", pady=(4, 8))

        canvas_cores = tk.Canvas(wrap, bg="#080b12", highlightthickness=0)
        v_scroll = tk.Scrollbar(wrap, orient="vertical", command=canvas_cores.yview, bg="#121724")
        self.cores_inner_frame = tk.Frame(canvas_cores, bg="#080b12")

        self.cores_inner_frame.bind(
            "<Configure>",
            lambda e: canvas_cores.configure(scrollregion=canvas_cores.bbox("all"))
        )
        canvas_cores.create_window((0, 0), window=self.cores_inner_frame, anchor="nw")
        canvas_cores.configure(yscrollcommand=v_scroll.set)

        canvas_cores.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")

        self.core_widgets = {}

    def _build_memory_tab(self):
        wrap = tk.Frame(self.tab_memory, bg="#080b12")
        wrap.pack(fill="both", expand=True, padx=22, pady=18)

        tk.Label(wrap, text="Physical Memory (RAM)", font=("Helvetica", 11, "bold"),
                 fg="#f8fafc", bg="#080b12", anchor="w").pack(fill="x", pady=(4, 6))

        self.ram_prog_var = tk.DoubleVar()
        ram_bar = ttk.Progressbar(wrap, variable=self.ram_prog_var, maximum=100.0,
                                  style="Horizontal.TProgressbar")
        ram_bar.pack(fill="x", pady=4)

        self.lbl_ram_breakdown = tk.Label(wrap, text="", font=("Helvetica", 9), fg="#94a3b8", bg="#080b12", anchor="w")
        self.lbl_ram_breakdown.pack(fill="x", pady=4)

        tk.Frame(wrap, height=1, bg="#1e2536").pack(fill="x", pady=16)

        tk.Label(wrap, text="Swap / Pagefile Storage", font=("Helvetica", 11, "bold"),
                 fg="#f8fafc", bg="#080b12", anchor="w").pack(fill="x", pady=(4, 6))

        self.swap_prog_var = tk.DoubleVar()
        swap_bar = ttk.Progressbar(wrap, variable=self.swap_prog_var, maximum=100.0,
                                   style="Horizontal.TProgressbar")
        swap_bar.pack(fill="x", pady=4)

        self.lbl_swap_breakdown = tk.Label(wrap, text="", font=("Helvetica", 9), fg="#94a3b8", bg="#080b12", anchor="w")
        self.lbl_swap_breakdown.pack(fill="x", pady=4)

    def _build_processes_tab(self):
        wrap = tk.Frame(self.tab_processes, bg="#080b12")
        wrap.pack(fill="both", expand=True, padx=14, pady=10)

        # Controls & Search Bar
        ctrl_bar = tk.Frame(wrap, bg="#080b12")
        ctrl_bar.pack(fill="x", pady=(2, 8))

        tk.Label(ctrl_bar, text="Search:", font=("Helvetica", 9, "bold"), fg="#94a3b8", bg="#080b12").pack(side="left", padx=(4, 4))
        self.search_entry = tk.Entry(ctrl_bar, font=("Helvetica", 9), bg="#141a28", fg="#f1f5f9", insertbackground="#38bdf8",
                                     relief="flat", bd=4, width=18)
        self.search_entry.pack(side="left", padx=(0, 12))
        self.search_entry.bind("<KeyRelease>", self._on_search_typed)

        tk.Label(ctrl_bar, text="Sort by:", font=("Helvetica", 9), fg="#94a3b8", bg="#080b12").pack(side="left", padx=4)

        self.sort_var = tk.StringVar(value="cpu")
        sort_combo = ttk.Combobox(ctrl_bar, textvariable=self.sort_var, values=["CPU Usage (%)", "RAM Usage (%)"],
                                  state="readonly", width=16)
        sort_combo.current(0)
        sort_combo.bind("<<ComboboxSelected>>", lambda e: self._update_processes())
        sort_combo.pack(side="left", padx=6)

        btn_kill = tk.Button(ctrl_bar, text="✕ End Process", font=("Helvetica", 9, "bold"),
                             bg="#be123c", fg="#ffffff", activebackground="#e11d48",
                             activeforeground="#ffffff", relief="flat", bd=0, padx=12, pady=4,
                             command=self._kill_selected_process)
        btn_kill.pack(side="right", padx=4)

        columns = ("pid", "user", "name", "cpu", "mem")
        self.proc_tree = ttk.Treeview(wrap, columns=columns, show="headings", selectmode="browse")

        self.proc_tree.heading("pid", text="PID", anchor="center")
        self.proc_tree.heading("user", text="User", anchor="w")
        self.proc_tree.heading("name", text="Process Name", anchor="w")
        self.proc_tree.heading("cpu", text="% CPU", anchor="e")
        self.proc_tree.heading("mem", text="% RAM", anchor="e")

        self.proc_tree.column("pid", width=70, anchor="center")
        self.proc_tree.column("user", width=130, anchor="w")
        self.proc_tree.column("name", width=340, anchor="w")
        self.proc_tree.column("cpu", width=90, anchor="e")
        self.proc_tree.column("mem", width=90, anchor="e")

        tree_scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.proc_tree.yview)
        self.proc_tree.configure(yscrollcommand=tree_scroll.set)

        self.proc_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

    def _build_preferences_tab(self):
        wrap = tk.Frame(self.tab_prefs, bg="#080b12")
        wrap.pack(fill="both", expand=True, padx=26, pady=20)

        tk.Label(wrap, text="Application Preferences", font=("Helvetica", 13, "bold"),
                 fg="#f8fafc", bg="#080b12", anchor="w").pack(fill="x", pady=(0, 16))

        # Desktop Bar Options
        tk.Label(wrap, text="Always-On Desktop HUD Bar (Top / Bottom of Screen):", font=("Helvetica", 9, "bold"),
                 fg="#38bdf8", bg="#080b12", anchor="w").pack(fill="x", pady=2)

        self.bar_pos_var = tk.StringVar(value=self.config.get("bar_position", "top"))
        bar_frame = tk.Frame(wrap, bg="#080b12")
        bar_frame.pack(fill="x", padx=8, pady=4)

        for p_id, p_label in [("top", "Dock at Top of Screen"), ("bottom", "Dock at Bottom of Screen")]:
            rb = tk.Radiobutton(bar_frame, text=p_label, variable=self.bar_pos_var, value=p_id,
                                fg="#cbd5e1", bg="#080b12", selectcolor="#1e2430",
                                activebackground="#080b12", activeforeground="#38bdf8",
                                font=("Helvetica", 9), command=self._on_bar_pos_changed)
            rb.pack(side="left", padx=10)

        tk.Frame(wrap, height=1, bg="#1e2536").pack(fill="x", pady=14)

        # Display Mode
        tk.Label(wrap, text="Telemetry Display Format:", font=("Helvetica", 9, "bold"),
                 fg="#94a3b8", bg="#080b12", anchor="w").pack(fill="x", pady=2)

        self.mode_var = tk.StringVar(value=self.config.get("display_mode", "balanced"))
        modes = [
            ("balanced", "Balanced (CPU, RAM, Net/Disk)"),
            ("sparkline", "Sparkline Track (Unicode wave)"),
            ("compact", "Compact (Short rates)"),
            ("minimal", "Minimal (CPU & RAM only)"),
            ("detailed", "Detailed (Frequencies & full totals)")
        ]
        for m_id, m_text in modes:
            rb = tk.Radiobutton(wrap, text=m_text, variable=self.mode_var, value=m_id,
                                fg="#cbd5e1", bg="#080b12", selectcolor="#1e2430",
                                activebackground="#080b12", activeforeground="#38bdf8",
                                font=("Helvetica", 9), command=self._on_pref_changed)
            rb.pack(anchor="w", padx=8, pady=2)

        tk.Frame(wrap, height=1, bg="#1e2536").pack(fill="x", pady=14)

        # Autostart
        self.auto_var = tk.BooleanVar(value=self.config.get("autostart", False))
        auto_cb = tk.Checkbutton(wrap, text=f"Launch Performance Track automatically on {SYS_NAME} login",
                                 variable=self.auto_var, fg="#f8fafc", bg="#080b12",
                                 selectcolor="#1e2430", activebackground="#080b12",
                                 activeforeground="#38bdf8", font=("Helvetica", 9, "bold"),
                                 command=self._on_autostart_toggle)
        auto_cb.pack(anchor="w", padx=8, pady=4)

    def _on_bar_pos_changed(self):
        new_pos = self.bar_pos_var.get()
        self.config.set("bar_position", new_pos)
        if self.on_config_changed:
            self.on_config_changed()

    def _on_search_typed(self, event):
        self._search_query = self.search_entry.get().strip().lower()
        self._update_processes()

    def _on_pref_changed(self):
        self.config.set("display_mode", self.mode_var.get())
        if self.on_config_changed:
            self.on_config_changed()

    def _on_autostart_toggle(self):
        val = self.auto_var.get()
        self.config.set("autostart", val)
        self.config.sync_autostart()

    def _kill_selected_process(self):
        sel = self.proc_tree.selection()
        if not sel:
            messagebox.showinfo("Select Process", "Please select a process from the list first.")
            return

        item = self.proc_tree.item(sel[0])
        pid = item["values"][0]
        name = item["values"][2]

        if messagebox.askyesno("Confirm Terminate", f"Terminate process {name} (PID: {pid})?"):
            try:
                import psutil
                p = psutil.Process(int(pid))
                p.terminate()
            except Exception:
                try:
                    if SYS_NAME == "Windows":
                        subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=True)
                    else:
                        os.kill(int(pid), 15)
                except Exception as e:
                    messagebox.showerror("Error", f"Could not terminate process {pid}: {e}")
            self._update_processes()

    def _update_processes(self):
        # Only query processes if Processes tab is visible or search active
        sort_by = "mem" if "RAM" in self.sort_var.get() else "cpu"
        procs = self.monitor.get_top_processes(count=30, sort_by=sort_by)

        if self._search_query:
            procs = [p for p in procs if self._search_query in p["name"].lower() or self._search_query in str(p["pid"])]

        for row in self.proc_tree.get_children():
            self.proc_tree.delete(row)

        for p in procs:
            self.proc_tree.insert("", "end", values=(
                p["pid"],
                p["user"],
                p["name"],
                f"{p['cpu']:.1f}%",
                f"{p['mem']:.1f}%"
            ))

    def update_ui(self):
        data = self.monitor.update()

        self.lbl_host.config(text=f"({data['system']['hostname']} — {data['system']['kernel']})")

        # 1. Cards
        cpu_pct = data['cpu']['percent']
        ram_pct = data['ram']['percent']
        net_rx = data['track']['net_rx_rate']
        net_tx = data['track']['net_tx_rate']
        disk_rw = data['track']['disk_read_rate'] + data['track']['disk_write_rate']

        self.lbl_card_cpu.config(text=f"{cpu_pct:.1f}%")
        freq_str = f"{data['cpu']['frequency']:.0f} MHz" if data['cpu']['frequency'] else ""
        self.lbl_sub_cpu.config(text=f"{freq_str} | Load: {data['cpu']['load'][0]:.2f}")

        used_ram = format_bytes(data['ram']['used'])
        total_ram = format_bytes(data['ram']['total'])
        self.lbl_card_ram.config(text=f"{ram_pct:.1f}%")
        self.lbl_sub_ram.config(text=f"{used_ram} / {total_ram}")

        self.lbl_card_net.config(text=format_rate(net_rx))
        self.lbl_sub_net.config(text=f"↑ {format_rate(net_tx)}")

        self.lbl_card_disk.config(text=format_rate(disk_rw))
        self.lbl_sub_disk.config(text=f"R: {format_rate(data['track']['disk_read_rate'])} | W: {format_rate(data['track']['disk_write_rate'])}")

        # 2. Graphs
        max_io = max(1.0, max(self.monitor.net_rx_history or [0]) / (1024 * 1024),
                     max(self.monitor.disk_write_history or [0]) / (1024 * 1024))
        self.graph_io.max_val = max(5.0, max_io * 1.25)
        self.graph_cpu_ram.redraw()
        self.graph_io.redraw()

        # 3. CPU Details
        self.lbl_cpu_name.config(text=f"Processor: {data['cpu']['model']} ({data['cpu']['cores_count']} logical cores)")
        self.lbl_cpu_details.config(
            text=f"Average Frequency: {data['cpu']['frequency']:.0f} MHz  |  "
                 f"Load Average: 1m: {data['cpu']['load'][0]:.2f}, 5m: {data['cpu']['load'][1]:.2f}, 15m: {data['cpu']['load'][2]:.2f}  |  "
                 f"Uptime: {data['system']['uptime']}"
        )

        cores = data['cpu']['cores']
        row = 0
        col = 0
        for name in sorted(cores.keys(), key=lambda x: int(x.replace('cpu', '')) if x.replace('cpu', '').isdigit() else 999):
            val = cores[name]
            if name not in self.core_widgets:
                cell = tk.Frame(self.cores_inner_frame, bg="#111724", padx=10, pady=8, bd=1, relief="solid")
                cell.config(highlightbackground="#1c2538")

                lbl = tk.Label(cell, text=f"Core {name.replace('cpu', '')}: {val:.1f}%", font=("Helvetica", 9),
                               fg="#cbd5e1", bg="#111724", anchor="w")
                lbl.pack(fill="x")

                p_var = tk.DoubleVar(value=val)
                pbar = ttk.Progressbar(cell, variable=p_var, maximum=100.0, style="Horizontal.TProgressbar")
                pbar.pack(fill="x", pady=2)

                cell.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
                self.cores_inner_frame.columnconfigure(col, weight=1)
                self.core_widgets[name] = (lbl, p_var, pbar)

                col += 1
                if col >= 3:
                    col = 0
                    row += 1
            else:
                lbl, p_var, _ = self.core_widgets[name]
                lbl.config(text=f"Core {name.replace('cpu', '')}: {val:.1f}%")
                p_var.set(val)

        # 4. Memory Tab
        self.ram_prog_var.set(ram_pct)
        self.lbl_ram_breakdown.config(
            text=f"Total: {total_ram}   |   Used: {used_ram}   |   Available: {format_bytes(data['ram']['available'])}   |   Free: {format_bytes(data['ram']['free'])}"
        )
        self.swap_prog_var.set(data['ram']['swap_percent'])
        self.lbl_swap_breakdown.config(
            text=f"Total Swap: {format_bytes(data['ram']['swap_total'])}   |   Used: {format_bytes(data['ram']['swap_used'])}   |   Free: {format_bytes(data['ram']['swap_free'])}"
        )

        # 5. Process list: ONLY update if Processes tab is actually selected
        try:
            current_tab_idx = self.notebook.index("current")
            if current_tab_idx == 3:  # Processes tab
                self._update_processes()
        except Exception:
            pass

    def _update_loop(self):
        if not self._timer_running:
            return
        if self.state() != "withdrawn":
            try:
                self.update_ui()
            except Exception:
                pass

        self.after(1000, self._update_loop)

    def show(self):
        self.deiconify()
        self.lift()
        self.focus_force()
        self.update_ui()

    def hide(self):
        self.withdraw()

    def close(self):
        self._timer_running = False
        self.destroy()
