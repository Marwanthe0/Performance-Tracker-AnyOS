#!/usr/bin/env python3
"""
build.py - Universal Cross-Platform Build & Distribution Pipeline for Performance Track.
Supports building standalone executables and distributable packages for:
  - Windows (Standalone .exe, Portable .zip, Windows Installer)
  - Linux (Native .deb, Self-extracting .run, .tar.gz, Linux x64 binary)
  - macOS (.app Application Bundle, .dmg / .zip)
"""

import os
import sys
import shutil
import zipfile
import tarfile
import platform
import argparse
import subprocess

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
DIST_DIR = os.path.join(PROJECT_ROOT, "dist")
INSTALLERS_DIR = os.path.join(PROJECT_ROOT, "Installers")
APP_NAME = "PerformanceTracker"
VERSION = "1.0.0"
SYS_NAME = platform.system()


def run_cmd(cmd, cwd=None):
    """Run a shell command and stream output."""
    print(f"--> Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    subprocess.check_call(cmd, cwd=cwd or PROJECT_ROOT, shell=isinstance(cmd, str))


def ensure_dependencies():
    """Verify required build dependencies are installed in the active Python environment, or auto-install them."""
    required = ["PyInstaller", "psutil", "pystray", "PIL"]
    missing = []
    for mod in required:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod.lower())

    if missing:
        pkg_map = {"pil": "pillow", "pyinstaller": "pyinstaller", "psutil": "psutil", "pystray": "pystray"}
        pkgs_to_install = [pkg_map.get(m, m) for m in missing]
        print(f"[*] Missing build dependencies: {missing}. Installing automatically...")
        run_cmd([sys.executable, "-m", "pip", "install", *pkgs_to_install])


def build_windows():
    """Build Windows standalone executable and installer packages."""
    print("==================================================")
    print(" Building for Windows (x64)...")
    print("==================================================")
    ensure_dependencies()
    os.makedirs(DIST_DIR, exist_ok=True)

    # Terminate any running instance before building
    try:
        subprocess.run(["taskkill", "/F", "/IM", f"{APP_NAME}.exe"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.5)
    except Exception:
        pass

    icon_path = os.path.join(PROJECT_ROOT, "performance_track", "icons", "performance-track.ico")
    app_entry = os.path.join(PROJECT_ROOT, "performance_track", "app.py")

    # 1. PyInstaller single-file build
    pyinstaller_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name", APP_NAME,
        "--icon", icon_path,
        "--add-data", f"{os.path.join(PROJECT_ROOT, 'performance_track', 'icons')};performance_track/icons",
        "--hidden-import", "pystray",
        "--hidden-import", "PIL",
        "--hidden-import", "psutil",
        app_entry
    ]

    run_cmd(pyinstaller_cmd)

    exe_file = os.path.join(DIST_DIR, f"{APP_NAME}.exe")
    if not os.path.isfile(exe_file):
        raise FileNotFoundError(f"Expected build artifact not found: {exe_file}")

    print(f"[✓] Created Standalone Windows Executable: {exe_file}")

    # 2. Create Windows Installer & Uninstaller Scripts (.bat)
    installer_bat = os.path.join(DIST_DIR, f"install_{APP_NAME.lower()}.bat")
    with open(installer_bat, "w", encoding="utf-8") as f:
        f.write(f"""@echo off
setlocal enabledelayedexpansion
title {APP_NAME} Windows Installer

echo ==================================================
echo   {APP_NAME} Windows Installer v{VERSION}
echo ==================================================
echo.

set "SOURCE_EXE=%~dp0{APP_NAME}.exe"
if not exist "!SOURCE_EXE!" (
    if exist "%~dp0dist\\{APP_NAME}.exe" (
        set "SOURCE_EXE=%~dp0dist\\{APP_NAME}.exe"
    ) else (
        echo [!] Error: {APP_NAME}.exe not found!
        echo Please ensure {APP_NAME}.exe is in the same directory as this installer.
        pause
        exit /b 1
    )
)

set "TARGET_DIR=%LOCALAPPDATA%\\Programs\\{APP_NAME}"
echo [*] Installing to: !TARGET_DIR!...

powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Process -Name {APP_NAME} -ErrorAction SilentlyContinue | Stop-Process -Force" >nul 2>&1

if not exist "!TARGET_DIR!" mkdir "!TARGET_DIR!" 2>nul
copy /Y "!SOURCE_EXE!" "!TARGET_DIR!\\{APP_NAME}.exe" >nul
if !errorlevel! neq 0 (
    echo [!] Failed to copy executable to: !TARGET_DIR!
    echo Please make sure you have permissions and the app is not currently running.
    pause
    exit /b 1
)

echo [*] Creating Desktop and Start Menu Shortcuts...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $desk = $ws.SpecialFolders.Item('Desktop'); if (-not $desk -or -not (Test-Path $desk)) {{ $desk = [Environment]::GetFolderPath('Desktop') }}; if (-not $desk -or -not (Test-Path $desk)) {{ $desk = [Environment]::GetFolderPath('CommonDesktopDirectory') }}; if (-not (Test-Path $desk)) {{ New-Item -ItemType Directory -Path $desk -Force | Out-Null }}; $targetExe = Join-Path '%TARGET_DIR%' '{APP_NAME}.exe'; $deskLink = Join-Path $desk '{APP_NAME}.lnk'; $s = $ws.CreateShortcut($deskLink); $s.TargetPath = $targetExe; $s.WorkingDirectory = '%TARGET_DIR%'; $s.Description = '{APP_NAME} - System Performance Monitor'; $s.Save(); Write-Host '[*] Desktop Shortcut created at:' $deskLink; $programs = [Environment]::GetFolderPath('Programs'); if (-not $programs -or -not (Test-Path $programs)) {{ $programs = Join-Path $env:APPDATA 'Microsoft\\Windows\\Start Menu\\Programs' }}; if (Test-Path $programs) {{ $smLink = Join-Path $programs '{APP_NAME}.lnk'; $s2 = $ws.CreateShortcut($smLink); $s2.TargetPath = $targetExe; $s2.WorkingDirectory = '%TARGET_DIR%'; $s2.Description = '{APP_NAME} - System Performance Monitor'; $s2.Save(); Write-Host '[*] Start Menu Shortcut created at:' $smLink }}"

echo.
echo ==================================================
echo   [OK] Installation completed successfully!
echo ==================================================
echo Launch {APP_NAME} anytime from:
echo   - Your Desktop shortcut
echo   - Windows Start Menu / Search ("{APP_NAME}")
echo   - Directly: "!TARGET_DIR!\\{APP_NAME}.exe"
echo.
pause
""")
    print(f"[✓] Created Windows Installer Script: {installer_bat}")

    uninstaller_bat = os.path.join(DIST_DIR, f"uninstall_{APP_NAME.lower()}.bat")
    with open(uninstaller_bat, "w", encoding="utf-8") as f:
        f.write(f"""@echo off
setlocal enabledelayedexpansion
title {APP_NAME} Windows Uninstaller

echo ==================================================
echo   {APP_NAME} Windows Uninstaller v{VERSION}
echo ==================================================
echo.

set "TARGET_DIR=%LOCALAPPDATA%\\Programs\\{APP_NAME}"

echo [*] Closing any running {APP_NAME} instances...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Process -Name {APP_NAME} -ErrorAction SilentlyContinue | Stop-Process -Force" >nul 2>&1

echo [*] Removing shortcuts...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $desk = $ws.SpecialFolders.Item('Desktop'); if (-not $desk -or -not (Test-Path $desk)) {{ $desk = [Environment]::GetFolderPath('Desktop') }}; if ($desk) {{ $l = Join-Path $desk '{APP_NAME}.lnk'; if (Test-Path $l) {{ Remove-Item $l -Force }} }}; $programs = [Environment]::GetFolderPath('Programs'); if (-not $programs -or -not (Test-Path $programs)) {{ $programs = Join-Path $env:APPDATA 'Microsoft\\Windows\\Start Menu\\Programs' }}; if ($programs) {{ $l2 = Join-Path $programs '{APP_NAME}.lnk'; if (Test-Path $l2) {{ Remove-Item $l2 -Force }} }}"

echo [*] Removing application files from: !TARGET_DIR!...
if exist "!TARGET_DIR!" (
    rmdir /S /Q "!TARGET_DIR!" 2>nul
)

echo.
echo ==================================================
echo   [OK] {APP_NAME} was uninstalled successfully.
echo ==================================================
echo.
pause
""")
    print(f"[✓] Created Windows Uninstaller Script: {uninstaller_bat}")

    # 3. Build Portable ZIP archive (including installer & run.bat)
    zip_path = os.path.join(DIST_DIR, f"{APP_NAME}-Windows-x64.zip")
    print(f"--> Creating Portable ZIP: {zip_path}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(exe_file, arcname=f"{APP_NAME}.exe")
        zf.write(installer_bat, arcname=os.path.basename(installer_bat))
        zf.write(uninstaller_bat, arcname=os.path.basename(uninstaller_bat))
        for extra in ["README.md", "run.bat"]:
            extra_p = os.path.join(PROJECT_ROOT, extra)
            if os.path.exists(extra_p):
                zf.write(extra_p, arcname=extra)

    print(f"[✓] Created Portable Windows ZIP: {zip_path}")

    # 4. Sync to primary Installers/Windows directory
    win_installer_dir = os.path.join(INSTALLERS_DIR, "Windows")
    try:
        os.makedirs(win_installer_dir, exist_ok=True)
        for item in [exe_file, installer_bat, uninstaller_bat, zip_path]:
            if os.path.exists(item):
                shutil.copy2(item, win_installer_dir)
        print(f"[✓] Synced Windows installables to: {win_installer_dir}")
    except Exception as e:
        print(f"[!] Note: Could not sync to {win_installer_dir}: {e}")


def build_linux():
    """Build Linux native packages and standalone binary."""
    print("==================================================")
    print(" Building for Linux...")
    print("==================================================")
    os.makedirs(DIST_DIR, exist_ok=True)

    # 1. Portable Tarball (.tar.gz)
    tar_name = f"ubuntu-performance-track-v{VERSION}.tar.gz"
    tar_path = os.path.join(DIST_DIR, tar_name)
    print(f"--> Building portable archive: {tar_name}...")

    tar_temp = os.path.join(PROJECT_ROOT, "build", "tar_content", "ubuntu-performance-track")
    if os.path.exists(tar_temp):
        shutil.rmtree(tar_temp)
    os.makedirs(tar_temp, exist_ok=True)

    for item in ["performance_track", "gnome-extension", "run.sh", "run.bat", "install.sh", "uninstall.sh", "ubuntu-performance-track.desktop", "README.md"]:
        src = os.path.join(PROJECT_ROOT, item)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(tar_temp, item), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        elif os.path.isfile(src):
            shutil.copy2(src, os.path.join(tar_temp, item))

    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(tar_temp, arcname="ubuntu-performance-track")

    print(f"[✓] Created Portable Tarball: {tar_path}")

    # 2. Self-Extracting Installer (.run)
    run_file = os.path.join(DIST_DIR, "ubuntu-performance-track-installer.run")
    print(f"--> Building self-extracting installer: {run_file}...")
    run_header = f"""#!/usr/bin/env bash
# Performance Track - Self Extracting Universal Installer
set -e
echo "=================================================="
echo "    Performance Track Universal Installer         "
echo "=================================================="
TMP_DIR=$(mktemp -d /tmp/upt_setup_XXXXXX)
trap 'rm -rf "$TMP_DIR"' EXIT
ARCHIVE_LINE=$(awk '/^__ARCHIVE_PAYLOAD_BELOW__/ {{print NR + 1; exit 0; }}' "$0")
echo "--> Extracting installer files..."
tail -n +"$ARCHIVE_LINE" "$0" | tar -xz -C "$TMP_DIR"
bash "$TMP_DIR/ubuntu-performance-track/install.sh" "$@"
exit 0
__ARCHIVE_PAYLOAD_BELOW__
"""
    with open(run_file, "wb") as f_out:
        f_out.write(run_header.encode("utf-8"))
        with open(tar_path, "rb") as f_in:
            shutil.copyfileobj(f_in, f_out)

    try:
        os.chmod(run_file, 0o755)
    except Exception:
        pass
    print(f"[✓] Created Self-Extracting Installer: {run_file}")

    # 3. Standalone Uninstaller
    uninstaller_sh = os.path.join(DIST_DIR, "ubuntu-performance-track-uninstaller.sh")
    with open(uninstaller_sh, "w", encoding="utf-8") as f:
        f.write("""#!/usr/bin/env bash
# Standalone Uninstaller for Performance Track
echo "=================================================="
echo "    Uninstalling Performance Track                "
echo "=================================================="
pkill -f "performance_track.app" 2>/dev/null || true
USER_DIR="$HOME/.local/share/ubuntu-performance-track"
if [ -d "$USER_DIR" ]; then
    echo "--> Removing user installation from $USER_DIR..."
    rm -rf "$USER_DIR"
fi
rm -f "$HOME/.local/bin/ubuntu-performance-track"
rm -f "$HOME/.local/bin/performance-track"
rm -f "$HOME/.local/share/applications/ubuntu-performance-track.desktop"
rm -f "$HOME/.config/autostart/ubuntu-performance-track.desktop"
rm -f "$HOME/.config/autostart/performance-track.desktop"
echo "[OK] Uninstallation complete!"
""")
    try:
        os.chmod(uninstaller_sh, 0o755)
    except Exception:
        pass
    print(f"[✓] Created Standalone Uninstaller: {uninstaller_sh}")

    # 4. If running on Linux with dpkg-deb, build native .deb package
    if shutil.which("dpkg-deb"):
        try:
            deb_build_dir = os.path.join(PROJECT_ROOT, "build", "deb_content")
            if os.path.exists(deb_build_dir):
                shutil.rmtree(deb_build_dir)
            os.makedirs(os.path.join(deb_build_dir, "DEBIAN"), exist_ok=True)
            os.makedirs(os.path.join(deb_build_dir, "usr", "bin"), exist_ok=True)
            os.makedirs(os.path.join(deb_build_dir, "usr", "lib", "ubuntu-performance-track"), exist_ok=True)
            os.makedirs(os.path.join(deb_build_dir, "usr", "share", "applications"), exist_ok=True)

            with open(os.path.join(deb_build_dir, "DEBIAN", "control"), "w", encoding="utf-8") as f:
                f.write(f"""Package: ubuntu-performance-track
Version: {VERSION}
Section: utils
Priority: optional
Architecture: all
Maintainer: Performance Track Contributors <info@example.com>
Description: High-performance real-time CPU, RAM, and Performance Tracker
 Seamless live system performance monitoring right in your topbar.
""")
            # Copy sources
            for item in ["performance_track", "run.sh"]:
                src = os.path.join(PROJECT_ROOT, item)
                dst = os.path.join(deb_build_dir, "usr", "lib", "ubuntu-performance-track", item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)

            # Wrapper in /usr/bin
            with open(os.path.join(deb_build_dir, "usr", "bin", "ubuntu-performance-track"), "w", encoding="utf-8") as f:
                f.write("#!/bin/sh\nexec python3 /usr/lib/ubuntu-performance-track/run.sh \"$@\"\n")
            os.chmod(os.path.join(deb_build_dir, "usr", "bin", "ubuntu-performance-track"), 0o755)

            # Desktop file
            shutil.copy2(os.path.join(PROJECT_ROOT, "ubuntu-performance-track.desktop"),
                         os.path.join(deb_build_dir, "usr", "share", "applications"))

            deb_out = os.path.join(DIST_DIR, f"ubuntu-performance-track_{VERSION}_all.deb")
            run_cmd(["dpkg-deb", "--build", deb_build_dir, deb_out])
            print(f"[✓] Created Debian Package: {deb_out}")
        except Exception as e:
            print(f"[!] Note: Debian package build skipped: {e}")

    # 5. Build PyInstaller binary if on Linux
    if SYS_NAME == "Linux":
        try:
            run_cmd([
                sys.executable, "-m", "PyInstaller",
                "--noconfirm", "--clean", "--onefile",
                "--name", f"{APP_NAME}-Linux-x64",
                os.path.join(PROJECT_ROOT, "performance_track", "app.py")
            ])
            print(f"[✓] Created Linux Binary: dist/{APP_NAME}-Linux-x64")
        except Exception as e:
            print(f"[!] PyInstaller Linux build note: {e}")

    # Sync to primary Installers/Linux directory
    lin_installer_dir = os.path.join(INSTALLERS_DIR, "Linux")
    try:
        os.makedirs(lin_installer_dir, exist_ok=True)
        for f in os.listdir(DIST_DIR):
            if f.startswith("ubuntu") or f.endswith((".deb", ".run", ".tar.gz", "uninstaller.sh")):
                shutil.copy2(os.path.join(DIST_DIR, f), lin_installer_dir)
        print(f"[✓] Synced Linux installables to: {lin_installer_dir}")
    except Exception as e:
        print(f"[!] Note: Could not sync to {lin_installer_dir}: {e}")


def build_macos():
    """Build macOS application bundle and zip."""
    print("==================================================")
    print(" Building for macOS...")
    print("==================================================")
    os.makedirs(DIST_DIR, exist_ok=True)

    app_entry = os.path.join(PROJECT_ROOT, "performance_track", "app.py")
    png_icon = os.path.join(PROJECT_ROOT, "performance_track", "icons", "performance-track.png")

    if SYS_NAME == "Darwin":
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm", "--clean", "--windowed",
            "--name", APP_NAME,
            "--osx-bundle-identifier", "com.performancetrack.app",
            "--hidden-import", "pystray",
            "--hidden-import", "PIL",
            "--hidden-import", "psutil",
            app_entry
        ]
        if os.path.exists(png_icon):
            cmd.extend(["--icon", png_icon])
        run_cmd(cmd)

        app_bundle = os.path.join(DIST_DIR, f"{APP_NAME}.app")
        zip_out = os.path.join(DIST_DIR, f"{APP_NAME}-macOS.zip")
        run_cmd(["zip", "-r", "-y", zip_out, f"{APP_NAME}.app"], cwd=DIST_DIR)
        print(f"[✓] Created macOS Application Zip: {zip_out}")
    else:
        print("[!] Note: macOS .app bundles can only be packaged natively on macOS.")
        print("[!] Use the provided GitHub Actions workflow (.github/workflows/auto-build.yml) to auto-build for macOS!")

    # Sync to primary Installers/macOS directory
    mac_installer_dir = os.path.join(INSTALLERS_DIR, "macOS")
    try:
        os.makedirs(mac_installer_dir, exist_ok=True)
        for f in os.listdir(DIST_DIR):
            if "macOS" in f or "Darwin" in f or f.endswith(".dmg"):
                shutil.copy2(os.path.join(DIST_DIR, f), mac_installer_dir)
        print(f"[✓] Synced macOS installables to: {mac_installer_dir}")
    except Exception as e:
        print(f"[!] Note: Could not sync to {mac_installer_dir}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Build Performance Track distributables.")
    parser.add_argument("--target", choices=["windows", "linux", "macos", "all", "current"],
                        default="current", help="Operating system target to build for")
    args = parser.parse_args()

    target = args.target
    if target == "current":
        if SYS_NAME == "Windows":
            target = "windows"
        elif SYS_NAME == "Darwin":
            target = "macos"
        else:
            target = "linux"

    if target in ["windows", "all"]:
        build_windows()

    if target in ["linux", "all"]:
        build_linux()

    if target in ["macos", "all"]:
        build_macos()

    print("\n==================================================")
    print(" All Requested Builds Completed!")
    print(f" Artifacts are located in: {DIST_DIR}")
    print("==================================================")


if __name__ == "__main__":
    main()
