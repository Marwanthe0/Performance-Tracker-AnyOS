"""
desktop_bar.py - Always-Visible Floating Desktop Topbar / Bottombar Widget.
A sleek, modern HUD bar docked at the top or bottom of the screen (or freely draggable).
Displays live CPU, RAM, Network throughput, and Disk I/O continuously even when the main window is closed.
"""

import sys
import os
import platform
import tkinter as tk
from tkinter import ttk

try:
    from .sparkline import generate_sparkline, generate_bar, format_bytes, format_rate, format_short_rate
except (ImportError, ValueError):
    from performance_track.sparkline import generate_sparkline, generate_bar, format_bytes, format_rate, format_short_rate

SYS_NAME = platform.system()


class DesktopBarWidget(tk.Toplevel):
    def __init__(self, monitor, config, on_open_dashboard=None, master=None):
        super().__init__(master)
        self.monitor = monitor
        self.config = config
        self.on_open_dashboard = on_open_dashboard

        # Window styling: Frameless, Always on Top, Acrylic Dark Glass
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            self.attributes("-alpha", float(self.config.get("bar_opacity", 0.95)))
        except Exception:
            pass

        self.configure(bg="#090d16")

        # Dimensions
        self.bar_width = 820
        self.bar_height = 38
        self._drag_start_x = 0
        self._drag_start_y = 0

        self._build_ui()
        self._position_bar()

        # Bind dragging & double-click
        self._bind_mouse_events()

        # Auto-refresh loop
        self._running = True
        self._update_loop()

    def _build_ui(self):
        # Outer border frame
        self.border_frame = tk.Frame(self, bg="#1e293b", bd=1)
        self.border_frame.pack(fill="both", expand=True)

        self.main_bar = tk.Frame(self.border_frame, bg="#090d16")
        self.main_bar.pack(fill="both", expand=True, padx=1, pady=1)

        # 1. Left Drag Handle & App Icon
        drag_box = tk.Frame(self.main_bar, bg="#090d16", cursor="fleur")
        drag_box.pack(side="left", padx=(10, 6))

        lbl_icon = tk.Label(drag_box, text="⚡", font=("Segoe UI Emoji", 11, "bold"), fg="#38bdf8", bg="#090d16")
        lbl_icon.pack(side="left")

        self.lbl_title = tk.Label(drag_box, text="TRACK", font=("Helvetica", 8, "bold"), fg="#64748b", bg="#090d16")
        self.lbl_title.pack(side="left", padx=(4, 6))

        # Separator
        tk.Label(self.main_bar, text="|", font=("Helvetica", 9), fg="#1e293b", bg="#090d16").pack(side="left", padx=2)

        # 2. CPU Telemetry Box
        self.box_cpu = tk.Frame(self.main_bar, bg="#090d16", cursor="hand2")
        self.box_cpu.pack(side="left", padx=8)

        self.lbl_cpu_title = tk.Label(self.box_cpu, text="CPU", font=("Helvetica", 8, "bold"), fg="#94a3b8", bg="#090d16")
        self.lbl_cpu_title.pack(side="left", padx=(0, 4))

        self.lbl_cpu_val = tk.Label(self.box_cpu, text="0%", font=("Helvetica", 9, "bold"), fg="#ff3366", bg="#090d16")
        self.lbl_cpu_val.pack(side="left")

        self.lbl_cpu_spark = tk.Label(self.box_cpu, text="", font=("Courier", 8), fg="#ff6699", bg="#090d16")
        self.lbl_cpu_spark.pack(side="left", padx=(4, 0))

        # Separator
        tk.Label(self.main_bar, text="|", font=("Helvetica", 9), fg="#1e293b", bg="#090d16").pack(side="left", padx=2)

        # 3. RAM Telemetry Box
        self.box_ram = tk.Frame(self.main_bar, bg="#090d16", cursor="hand2")
        self.box_ram.pack(side="left", padx=8)

        self.lbl_ram_title = tk.Label(self.box_ram, text="RAM", font=("Helvetica", 8, "bold"), fg="#94a3b8", bg="#090d16")
        self.lbl_ram_title.pack(side="left", padx=(0, 4))

        self.lbl_ram_val = tk.Label(self.box_ram, text="0%", font=("Helvetica", 9, "bold"), fg="#00e5ff", bg="#090d16")
        self.lbl_ram_val.pack(side="left")

        self.lbl_ram_sub = tk.Label(self.box_ram, text="", font=("Helvetica", 8), fg="#7dd3fc", bg="#090d16")
        self.lbl_ram_sub.pack(side="left", padx=(4, 0))

        # Separator
        tk.Label(self.main_bar, text="|", font=("Helvetica", 9), fg="#1e293b", bg="#090d16").pack(side="left", padx=2)

        # 4. Network Throughput Box
        self.box_net = tk.Frame(self.main_bar, bg="#090d16", cursor="hand2")
        self.box_net.pack(side="left", padx=8)

        self.lbl_net_title = tk.Label(self.box_net, text="NET", font=("Helvetica", 8, "bold"), fg="#94a3b8", bg="#090d16")
        self.lbl_net_title.pack(side="left", padx=(0, 4))

        self.lbl_net_val = tk.Label(self.box_net, text="↓ 0B/s ↑ 0B/s", font=("Helvetica", 8, "bold"), fg="#00e676", bg="#090d16")
        self.lbl_net_val.pack(side="left")

        # Separator
        tk.Label(self.main_bar, text="|", font=("Helvetica", 9), fg="#1e293b", bg="#090d16").pack(side="left", padx=2)

        # 5. Disk I/O Box
        self.box_disk = tk.Frame(self.main_bar, bg="#090d16", cursor="hand2")
        self.box_disk.pack(side="left", padx=8)

        self.lbl_disk_title = tk.Label(self.box_disk, text="DISK", font=("Helvetica", 8, "bold"), fg="#94a3b8", bg="#090d16")
        self.lbl_disk_title.pack(side="left", padx=(0, 4))

        self.lbl_disk_val = tk.Label(self.box_disk, text="0 B/s", font=("Helvetica", 8, "bold"), fg="#b388ff", bg="#090d16")
        self.lbl_disk_val.pack(side="left")

        # 6. Right Actions Bar
        actions_box = tk.Frame(self.main_bar, bg="#090d16")
        actions_box.pack(side="right", padx=(4, 8))

        # Dashboard Button
        btn_dash = tk.Button(actions_box, text="📊 Dashboard", font=("Helvetica", 8, "bold"),
                             bg="#1e293b", fg="#38bdf8", activebackground="#334155",
                             activeforeground="#ffffff", relief="flat", bd=0, padx=8, pady=2,
                             command=self._on_dashboard_clicked)
        btn_dash.pack(side="left", padx=4)

        # Toggle Dock Button (Top <-> Bottom)
        self.btn_dock = tk.Button(actions_box, text="📍 Top", font=("Helvetica", 8),
                                  bg="#161e2e", fg="#94a3b8", activebackground="#334155",
                                  activeforeground="#ffffff", relief="flat", bd=0, padx=6, pady=2,
                                  command=self._toggle_dock_position)
        self.btn_dock.pack(side="left", padx=2)

        # Hide / Minimize Button
        btn_min = tk.Button(actions_box, text="–", font=("Helvetica", 9, "bold"),
                            bg="#090d16", fg="#64748b", activebackground="#334155",
                            activeforeground="#ffffff", relief="flat", bd=0, padx=6, pady=0,
                            command=self.hide)
        btn_min.pack(side="left", padx=2)

    def _position_bar(self):
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        pos = self.config.get("bar_position", "top")

        if pos == "bottom":
            x = (screen_w - self.bar_width) // 2
            y = max(10, screen_h - self.bar_height - 48)  # above taskbar
            self.btn_dock.config(text="📍 Bottom")
        elif pos == "custom" and self.config.get("bar_x") is not None:
            x = int(self.config.get("bar_x"))
            y = int(self.config.get("bar_y"))
            self.btn_dock.config(text="📍 Custom")
        else:  # "top"
            x = (screen_w - self.bar_width) // 2
            y = 8
            self.btn_dock.config(text="📍 Top")

        self.geometry(f"{self.bar_width}x{self.bar_height}+{x}+{y}")

    def _toggle_dock_position(self):
        curr = self.config.get("bar_position", "top")
        new_pos = "bottom" if curr == "top" else "top"
        self.config.set("bar_position", new_pos)
        self._position_bar()

    def _bind_mouse_events(self):
        # Click & drag to reposition
        for widget in [self, self.border_frame, self.main_bar, self.box_cpu, self.box_ram, self.box_net, self.box_disk]:
            widget.bind("<Button-1>", self._on_drag_start)
            widget.bind("<B1-Motion>", self._on_dragging)
            widget.bind("<Double-Button-1>", lambda e: self._on_dashboard_clicked())
            widget.bind("<Button-3>", self._show_context_menu)

    def _on_drag_start(self, event):
        self._drag_start_x = event.x_root - self.winfo_x()
        self._drag_start_y = event.y_root - self.winfo_y()

    def _on_dragging(self, event):
        new_x = event.x_root - self._drag_start_x
        new_y = event.y_root - self._drag_start_y
        self.geometry(f"+{new_x}+{new_y}")
        self.config.set("bar_position", "custom")
        self.config.set("bar_x", new_x)
        self.config.set("bar_y", new_y)
        self.btn_dock.config(text="📍 Custom")

    def _show_context_menu(self, event):
        menu = tk.Menu(self, tearoff=0, bg="#161b26", fg="#e2e8f0", activebackground="#2563eb",
                       activeforeground="#ffffff", font=("Helvetica", 9), bd=1)
        menu.add_command(label="📊 Open Full Dashboard", command=self._on_dashboard_clicked)
        menu.add_separator()
        menu.add_command(label="📍 Dock to Top of Screen", command=lambda: self._set_position("top"))
        menu.add_command(label="📍 Dock to Bottom of Screen", command=lambda: self._set_position("bottom"))
        menu.add_separator()

        # Display Mode Submenu
        sub_modes = tk.Menu(menu, tearoff=0, bg="#161b26", fg="#e2e8f0", activebackground="#2563eb",
                            activeforeground="#ffffff", font=("Helvetica", 9))
        for m_id, m_text in [("balanced", "Balanced"), ("sparkline", "Sparkline Track"), ("compact", "Compact"), ("minimal", "Minimal"), ("detailed", "Detailed")]:
            sub_modes.add_command(label=m_text, command=lambda mid=m_id: self._set_mode(mid))
        menu.add_cascade(label="🎨 Display Mode", menu=sub_modes)

        menu.add_command(label="– Hide to Tray", command=self.hide)
        menu.add_command(label="✕ Close Application", command=self._quit_app)

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _set_position(self, pos):
        self.config.set("bar_position", pos)
        self._position_bar()

    def _set_mode(self, mode_id):
        self.config.set("display_mode", mode_id)
        self.update_telemetry()

    def _on_dashboard_clicked(self):
        if self.on_open_dashboard:
            self.on_open_dashboard()

    def _quit_app(self):
        self._running = False
        self.master.destroy()

    def update_telemetry(self):
        """Instant non-blocking telemetry refresh from cached monitor snapshot."""
        data = self.monitor.update()

        cpu_pct = data['cpu']['percent']
        ram_pct = data['ram']['percent']
        net_rx = data['track']['net_rx_rate']
        net_tx = data['track']['net_tx_rate']
        disk_rw = data['track']['disk_read_rate'] + data['track']['disk_write_rate']

        mode = self.config.get("display_mode", "balanced")

        # 1. Update CPU
        self.lbl_cpu_val.config(text=f"{cpu_pct:.0f}%")
        # Shift color to glowing amber/red if high load
        if cpu_pct >= 85:
            self.lbl_cpu_val.config(fg="#ff1744")
        elif cpu_pct >= 60:
            self.lbl_cpu_val.config(fg="#ff9100")
        else:
            self.lbl_cpu_val.config(fg="#ff3366")

        if mode == "sparkline":
            spark = generate_sparkline(self.monitor.cpu_history[-6:], 0, 100) or " "
            self.lbl_cpu_spark.config(text=spark)
        elif mode == "detailed" and data['cpu']['frequency']:
            self.lbl_cpu_spark.config(text=f"({data['cpu']['frequency']:.0f}MHz)")
        else:
            self.lbl_cpu_spark.config(text="")

        # 2. Update RAM
        used_g = f"{data['ram']['used'] / (1024**3):.1f}G"
        tot_g = f"{data['ram']['total'] / (1024**3):.1f}G"
        self.lbl_ram_val.config(text=f"{ram_pct:.0f}%")
        if mode == "detailed":
            self.lbl_ram_sub.config(text=f"({used_g}/{tot_g})")
        elif mode == "minimal":
            self.lbl_ram_sub.config(text="")
        else:
            self.lbl_ram_sub.config(text=f"({used_g})")

        # 3. Update Network
        if mode == "compact":
            self.lbl_net_val.config(text=f"{format_short_rate(net_rx)}")
        else:
            self.lbl_net_val.config(text=f"↓ {format_short_rate(net_rx)}/s ↑ {format_short_rate(net_tx)}/s")

        # 4. Update Disk
        self.lbl_disk_val.config(text=f"{format_short_rate(disk_rw)}/s")

    def _update_loop(self):
        if not self._running:
            return
        if self.state() != "withdrawn":
            try:
                self.update_telemetry()
            except Exception:
                pass

        interval_ms = int(float(self.config.get("update_interval", 1.0)) * 1000)
        self.after(max(400, interval_ms), self._update_loop)

    def show(self):
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.update_telemetry()

    def hide(self):
        self.withdraw()

    def close(self):
        self._running = False
        self.destroy()
