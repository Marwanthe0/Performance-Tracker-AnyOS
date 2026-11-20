# PC Performance Tracker (AnyOS)

[![Auto-Build](https://github.com/Marwanthe0/Performance-Tracker-AnyOS/actions/workflows/auto-build.yml/badge.svg)](https://github.com/Marwanthe0/Performance-Tracker-AnyOS/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A high-performance, real-time system performance monitor designed to run seamlessly on **any personal OS** — **Windows**, **macOS**, and **Linux** (including Ubuntu and GNOME).

It tracks and displays live **CPU**, **RAM**, **GPU**, **Network Throughput (Upload & Download)**, **Disk I/O (Read & Write)**, **Multi-Drive Partitions**, and **Battery Health** directly in your desktop top bar or system tray, accompanied by an always-on floating desktop HUD bar and a full cyber-styled real-time GUI Dashboard window.

---

## ⚡ 1-Click Installers (Windows, Linux, macOS)
> **Looking to install? Everything is right here at the front of the folder!**

| Operating System | 1-Click Installer (Root Folder) | Dedicated Package Folder | Direct Downloads |
| :--- | :--- | :--- | :--- |
| **🪟 Windows (10 / 11)** | Double-click [`INSTALL_WINDOWS.bat`](INSTALL_WINDOWS.bat) | [`Installers/Windows/`](Installers/Windows/) | [Standalone .EXE](Installers/Windows/PerformanceTracker.exe) • [Portable .ZIP](Installers/Windows/PerformanceTracker-Windows-x64.zip) |
| **🐧 Linux / Ubuntu** | Run `bash INSTALL_LINUX.sh` | [`Installers/Linux/`](Installers/Linux/) | [Debian .DEB](Installers/Linux/ubuntu-performance-track_1.0.0_all.deb) • [Self-Extracting .RUN](Installers/Linux/ubuntu-performance-track-installer.run) • [.TAR.GZ](Installers/Linux/ubuntu-performance-track-v1.0.0.tar.gz) |
| **🍎 macOS** | Run `bash INSTALL_MACOS.sh` | [`Installers/macOS/`](Installers/macOS/) | [macOS App Bundle .ZIP](Installers/macOS/PerformanceTracker-macOS.zip) |

*(To launch instantly on Windows without installing, just double-click [`RUN_APP.bat`](RUN_APP.bat))*

---

## 📦 Ready-to-Use Packages by Operating System

### 🪟 Windows (10 / 11)
| File | Description | How to Run / Install |
| :--- | :--- | :--- |
| **`INSTALL_WINDOWS.bat`** | **1-Click Windows Desktop & Start Menu Installer** (Supports OneDrive & Win 11) | Double-click `INSTALL_WINDOWS.bat` |
| **`Installers/Windows/PerformanceTracker.exe`** | **Standalone Windows Executable** (Zero installation, double-click to launch) | Double-click `PerformanceTracker.exe` |
| **`Installers/Windows/PerformanceTracker-Windows-x64.zip`** | **Portable Archive** | Extract anywhere and run `PerformanceTracker.exe` |
| **`Installers/Windows/Uninstall-Windows.bat`** | **1-Click Clean Uninstaller** | Double-click `Uninstall-Windows.bat` |

### 🐧 Linux & Ubuntu
| File | Description | How to Install | How to Uninstall |
| :--- | :--- | :--- | :--- |
| **`INSTALL_LINUX.sh`** | **1-Click Linux Installer** (Auto-detects deb/apt or standalone) | `bash INSTALL_LINUX.sh` | `bash Installers/Linux/Uninstall-Linux.sh` |
| **`Installers/Linux/ubuntu-performance-track-installer.run`** | **Single-File Self-Extracting Installer** (No root needed) | `bash Installers/Linux/ubuntu-performance-track-installer.run` | `ubuntu-performance-track-uninstall` |
| **`Installers/Linux/ubuntu-performance-track_1.0.0_all.deb`** | **Native Debian Package** (Ubuntu Software / apt) | `sudo apt install ./Installers/Linux/ubuntu-performance-track_1.0.0_all.deb` | `sudo apt remove ubuntu-performance-track` |
| **`Installers/Linux/ubuntu-performance-track-v1.0.0.tar.gz`** | **Portable Source Tarball** | Extract and run `./install.sh` | Run `./uninstall.sh` |

### 🍎 macOS
| File | Description | How to Run / Install |
| :--- | :--- | :--- |
| **`INSTALL_MACOS.sh`** | **1-Click macOS Installer** | `bash INSTALL_MACOS.sh` |
| **`Installers/macOS/PerformanceTracker-macOS.zip`** | **macOS Application Bundle** | Extract and drag `PerformanceTracker.app` to Applications |

---

## 🚀 How to Build for Any Personal OS

The project includes a universal build pipeline (`build.py`) as well as platform-specific build scripts:

### Build on Windows:
```cmd
# One-click batch build:
build_windows.bat

# Or using Python:
python build.py --target windows
```
*Generates `dist/PerformanceTracker.exe`, `dist/PerformanceTracker-Windows-x64.zip`, and `dist/install_performancetracker.bat`.*

### Build on Linux:
```bash
# Using universal builder:
python3 build.py --target linux

# Or legacy bash script:
./build_dist.sh
```
*Generates `.deb`, `.run`, `.tar.gz`, and Linux binaries.*

### Build on macOS:
```bash
# Using universal builder:
python3 build.py --target macos

# Or helper script:
./build_macos.sh
```
*Generates `PerformanceTracker.app` and `.zip`.*

### Build All:
```bash
python build.py --target all
```

---

## ⚡ GitHub Actions Auto-Build Pipeline

The repository includes a complete CI/CD workflow in [`.github/workflows/auto-build.yml`](.github/workflows/auto-build.yml) that automatically runs multi-OS build matrix on every push and release tag:
- **Windows runner** (`windows-latest`): Builds Windows `.exe` and `.zip`.
- **Linux runner** (`ubuntu-latest`): Builds Debian `.deb`, `.run`, and source tarball.
- **macOS runner** (`macos-latest`): Builds macOS application bundle and zip.
- Automatically tests metric collectors and uploads release artifacts.

---

## 💻 Running from Source

You can run Performance Track directly from source on any OS:

```bash
# Install dependencies:
pip install psutil pystray pillow

# Launch on Windows:
run.bat

# Launch on Linux / macOS:
./run.sh

# Or directly with Python:
python -m performance_track.app

# Open directly with GUI Dashboard:
python -m performance_track.app --dashboard

# Run in lightweight terminal / SSH mode:
python -m performance_track.app --cli
```

---

## ✨ Features

- **Always-Visible Desktop HUD Bar (Top / Bottom Dock)**:
  - Sleek, semi-translucent floating monitor bar that docks to the top or bottom of your screen.
  - Displays live CPU %, RAM %, Network Download / Upload speeds, and Disk I/O at all times even when the main dashboard is closed.
  - 1-click dock switch between screen Top and Bottom edge, or drag anywhere on desktop.
  - Click to expand to full Dashboard or minimize to tray.

- **Cross-Platform System Tray / Topbar Integration**:
  - **Ubuntu GNOME**: Native AppIndicator in top bar with live metrics and Unicode sparkline tracks (` ▂▃▄▅▆▇█`).
  - **Windows & macOS**: Dynamic System Tray indicator with real-time badges, hover tooltips, and interactive menus.
  - **Live CPU Usage**: Overall percentage, frequency, load average, and per-core submenus.
  - **Live RAM Usage**: Real-time memory consumption, available memory, cached, and swap breakdown.
  - **Performance Track**: Real-time network throughput (download/upload rates) and disk I/O rates.

- **Full GUI Dashboard Window**:
  - Interactive multi-series real-time Canvas charts for CPU & RAM, and Network & Disk I/O.
  - Per-core progress grid displaying utilization for all CPU cores.
  - Sortable and searchable **Process Manager** with ability to safely terminate runaway tasks.
  - Preferences editor (switch display mode between *Balanced*, *Sparkline Track*, *Compact*, *Minimal*, and *Detailed*).
  - 1-click launcher for host OS Task Manager (`taskmgr` on Windows, `Activity Monitor` on macOS, `gnome-system-monitor` on Linux).
  - Autostart on system login toggle for Windows, macOS, and Linux.

---

## 🧪 Testing & Verification

Run the automated test suite across all platforms:
```bash
python tests/test_monitor.py
```
Verifies metric collectors, sparkline generation, platform detection, and config synchronization.
