# Ubuntu Performance Track

A high-performance, real-time system performance monitor designed specifically for **Ubuntu** (tested on Ubuntu 24.04 LTS and GNOME 46). It seamlessly displays live **CPU**, **RAM**, and **Performance Track (Network & Disk I/O throughput)** right on the **Ubuntu top bar**.

![Ubuntu Performance Track](performance_track/icons/performance-track.svg)

---

## 📦 Downloadable Installer Packages

All ready-to-use downloadable installers and uninstallers are built and available in the `dist/` folder:

| File | Description | How to Install | How to Uninstall |
| :--- | :--- | :--- | :--- |
| **`dist/ubuntu-performance-track-installer.run`** | **Single-File Self-Extracting Installer** (Recommended for portable use, no root needed) | `bash ubuntu-performance-track-installer.run` | `ubuntu-performance-track-uninstall` or run `ubuntu-performance-track-uninstaller.sh` |
| **`dist/ubuntu-performance-track_1.0.0_all.deb`** | **Native Debian Package** (Double-click or apt/dpkg) | `sudo apt install ./ubuntu-performance-track_1.0.0_all.deb` | `sudo apt remove ubuntu-performance-track` |
| **`dist/ubuntu-performance-track-v1.0.0.tar.gz`** | **Portable Source Archive** | Extract and run `./install.sh` | Run `./uninstall.sh` |
| **`dist/ubuntu-performance-track-uninstaller.sh`** | **Standalone Uninstaller Script** | — | `bash ubuntu-performance-track-uninstaller.sh` |

---

## 🚀 Installation Guide for Any User

### Option 1: Self-Extracting Installer (`.run`) — Recommended
This single file contains everything needed:
```bash
# Download and install:
chmod +x ubuntu-performance-track-installer.run
./ubuntu-performance-track-installer.run
```
- Installs into `~/.local/share/ubuntu-performance-track/`
- Installs command `ubuntu-performance-track` into `~/.local/bin/`
- Creates desktop shortcuts and enables auto-start on login
- Launches the topbar monitor immediately

To uninstall anytime:
```bash
ubuntu-performance-track-uninstall
```

---

### Option 2: Native Ubuntu Debian Package (`.deb`)
```bash
# Install with apt or dpkg:
sudo apt install ./ubuntu-performance-track_1.0.0_all.deb
```
Or double-click the `.deb` file to install via Ubuntu App Center / Software Center.

To uninstall:
```bash
sudo apt remove ubuntu-performance-track
```

---

### Option 3: From Source Directory
```bash
# Install user-level (no sudo required):
./install.sh

# Or install system-wide:
sudo ./install.sh --system

# To uninstall:
./uninstall.sh
```

---

## ✨ Features

- **Top Bar Integration**:
  - **Live CPU Usage**: Displays percentage, average frequency, and load average.
  - **Live RAM Usage**: Real-time memory consumption, available memory, and total capacity.
  - **Performance Track**: Real-time network throughput (download/upload rates) and disk I/O activity.
  - **Dynamic Sparklines**: Live Unicode sparkline tracks (` ▂▃▄▅▆▇█`) rendering live load trajectories directly inside the topbar.

- **Interactive Dropdown Menu** (Click to reveal):
  - **⚡ CPU Section**: Overall percentage, visual progress bar, CPU frequency, and a dedicated **Per-Core Submenu** showing individual usage for every core.
  - **💾 RAM & Swap Section**: Used, Available, Free, Cached/Buffers, and Swap breakdown.
  - **🌐 Performance Track Section**: Download/Upload speeds, cumulative transfer totals, and Disk Read/Write rates.
  - **🔥 Top Processes Track**: Live view of the top 5 CPU and Memory-consuming processes.
  - **🎨 Display Modes**: Switch on the fly between *Balanced*, *Sparkline Track*, *Compact*, *Minimal*, and *Detailed*.
  - **⏱ Update Speed**: Configure refresh rate (1s, 2s, 3s, 5s).
  - **🚀 Autostart**: Enable/disable automatic startup on Ubuntu login with one click.
  - **🖥 GNOME System Monitor Launcher**: Quick 1-click shortcut to the default Ubuntu system monitor.

- **Full GUI Dashboard Window**:
  - Live anti-aliased **Cairo graphical charts** for CPU, RAM, Network, and Disk I/O history.
  - Visual core grid with animated progress bars for all CPU cores.
  - Sortable and searchable **Process Manager** with ability to safely terminate runaway tasks.
  - Preferences editor.

---

## 🎨 Topbar Display Modes

You can switch the topbar layout anytime via the indicator menu:

| Mode | Topbar Display Example |
| :--- | :--- |
| **Balanced (Default)** | `CPU 14%  \|  RAM 28% (4.2G)  \|  ↓ 1.2M/s ↑ 80K/s` |
| **Sparkline Track** | `CPU 14%  ▂▃  \|  RAM 28% ▄▅  \|  1.2M/s` |
| **Compact** | `C:14% R:28% P:1.2M` |
| **Minimal** | `14% CPU  28% RAM` |
| **Detailed** | `CPU: 14.2% (3.9GHz) \| RAM: 4.2G/15.0G (28%) \| ↓1.2M ↑80K` |

---

## 📁 Project Structure

```
Usage/
├── build_dist.sh                       # Build script to generate all release installers
├── dist/                               # Downloadable installer packages
│   ├── ubuntu-performance-track-installer.run      # Single-file self-extracting installer
│   ├── ubuntu-performance-track_1.0.0_all.deb      # Native Debian (.deb) package
│   ├── ubuntu-performance-track-uninstaller.sh    # Standalone uninstaller script
│   └── ubuntu-performance-track-v1.0.0.tar.gz      # Portable source archive
├── run.sh                              # Instant launcher script
├── install.sh                          # Universal installer
├── uninstall.sh                        # Universal uninstaller
├── ubuntu-performance-track.desktop    # XDG Desktop application launcher
├── README.md                           # Documentation
├── performance_track/
│   ├── __init__.py                     # Package initialization
│   ├── app.py                          # AppIndicator & menu controller
│   ├── monitor.py                      # /proc & /sys metrics collector
│   ├── dashboard.py                    # GTK3 Dashboard Window & Cairo charts
│   ├── config.py                       # User settings & autostart management
│   ├── sparkline.py                    # Unicode block sparklines & formatting
│   └── icons/
│       ├── performance-track.svg       # Full-color scalable application icon
│       └── performance-track-symbolic.svg # GNOME symbolic monochrome icon
├── gnome-extension/                    # Native GNOME Shell 45/46 Extension
│   ├── metadata.json
│   ├── extension.js
│   ├── stylesheet.css
│   └── install_extension.sh
└── tests/
    └── test_monitor.py                 # Automated verification test suite
```

---

## 🧪 Testing

Run the automated test suite to verify metric collection, rate calculations, and sparkline rendering:
```bash
python3 tests/test_monitor.py
```
