@echo off
setlocal enabledelayedexpansion
title PC Performance Tracker - 1-Click Windows Installer
cd /d "%~dp0"

echo ==================================================
echo   PC Performance Tracker - 1-Click Windows Installer
echo ==================================================
echo.

:: 1. Find the compiled executable
set "SOURCE_EXE="
if exist "%~dp0Installers\Windows\PerformanceTracker.exe" (
    set "SOURCE_EXE=%~dp0Installers\Windows\PerformanceTracker.exe"
) else if exist "%~dp0PerformanceTracker.exe" (
    set "SOURCE_EXE=%~dp0PerformanceTracker.exe"
) else if exist "%~dp0dist\PerformanceTracker.exe" (
    set "SOURCE_EXE=%~dp0dist\PerformanceTracker.exe"
)

if "!SOURCE_EXE!"=="" (
    echo [!] Standalone executable not found in Installers\Windows\
    echo [*] Checking Python to run or build...
    call "%~dp0run.bat"
    exit /b 0
)

set "TARGET_DIR=%LOCALAPPDATA%\Programs\PerformanceTracker"
echo [*] Installing to: !TARGET_DIR!...

:: Stop any running instance before updating
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Process -Name PerformanceTracker -ErrorAction SilentlyContinue | Stop-Process -Force" >nul 2>&1

if not exist "!TARGET_DIR!" mkdir "!TARGET_DIR!" 2>nul
copy /Y "!SOURCE_EXE!" "!TARGET_DIR!\PerformanceTracker.exe" >nul
if !errorlevel! neq 0 (
    echo [!] Failed to copy executable to: !TARGET_DIR!
    echo Please make sure the app is not currently running.
    pause
    exit /b 1
)

echo [*] Creating Desktop and Start Menu Shortcuts...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell; " ^
  "$desk = $ws.SpecialFolders.Item('Desktop'); " ^
  "if (-not $desk -or -not (Test-Path $desk)) { $desk = [Environment]::GetFolderPath('Desktop') }; " ^
  "if (-not $desk -or -not (Test-Path $desk)) { $desk = [Environment]::GetFolderPath('CommonDesktopDirectory') }; " ^
  "if (-not (Test-Path $desk)) { New-Item -ItemType Directory -Path $desk -Force | Out-Null }; " ^
  "$targetExe = Join-Path '%TARGET_DIR%' 'PerformanceTracker.exe'; " ^
  "$deskLink = Join-Path $desk 'PC Performance Tracker.lnk'; " ^
  "$s = $ws.CreateShortcut($deskLink); " ^
  "$s.TargetPath = $targetExe; " ^
  "$s.WorkingDirectory = '%TARGET_DIR%'; " ^
  "$s.Description = 'PC Performance Tracker - Real-time System Monitor'; " ^
  "$s.Save(); " ^
  "Write-Host '[*] Desktop Shortcut created at:' $deskLink; " ^
  "$programs = [Environment]::GetFolderPath('Programs'); " ^
  "if (-not $programs -or -not (Test-Path $programs)) { $programs = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs' }; " ^
  "if (Test-Path $programs) { " ^
  "  $smLink = Join-Path $programs 'PC Performance Tracker.lnk'; " ^
  "  $s2 = $ws.CreateShortcut($smLink); " ^
  "  $s2.TargetPath = $targetExe; " ^
  "  $s2.WorkingDirectory = '%TARGET_DIR%'; " ^
  "  $s2.Description = 'PC Performance Tracker - Real-time System Monitor'; " ^
  "  $s2.Save(); " ^
  "  Write-Host '[*] Start Menu Shortcut created at:' $smLink; " ^
  "}"

echo.
echo ==================================================
echo   [OK] Installation completed successfully!
echo ==================================================
echo.
echo Launch PC Performance Tracker anytime from:
echo   - Your Desktop shortcut: 'PC Performance Tracker'
echo   - Windows Start Menu / Search: 'PC Performance Tracker'
echo   - Directly: "!TARGET_DIR!\PerformanceTracker.exe"
echo.
echo [*] Launching PC Performance Tracker now...
start "" "!TARGET_DIR!\PerformanceTracker.exe"
echo.
pause
