@echo off
setlocal enabledelayedexpansion
title PerformanceTracker Windows Uninstaller

echo ==================================================
echo   PerformanceTracker Windows Uninstaller v1.0.0
echo ==================================================
echo.

set "TARGET_DIR=%LOCALAPPDATA%\Programs\PerformanceTracker"

echo [*] Closing any running PerformanceTracker instances...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Process -Name PerformanceTracker -ErrorAction SilentlyContinue | Stop-Process -Force" >nul 2>&1

echo [*] Removing shortcuts...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $desk = $ws.SpecialFolders.Item('Desktop'); if (-not $desk -or -not (Test-Path $desk)) { $desk = [Environment]::GetFolderPath('Desktop') }; if ($desk) { $l = Join-Path $desk 'PerformanceTracker.lnk'; if (Test-Path $l) { Remove-Item $l -Force } }; $programs = [Environment]::GetFolderPath('Programs'); if (-not $programs -or -not (Test-Path $programs)) { $programs = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs' }; if ($programs) { $l2 = Join-Path $programs 'PerformanceTracker.lnk'; if (Test-Path $l2) { Remove-Item $l2 -Force } }"

echo [*] Removing application files from: !TARGET_DIR!...
if exist "!TARGET_DIR!" (
    rmdir /S /Q "!TARGET_DIR!" 2>nul
)

echo.
echo ==================================================
echo   [OK] PerformanceTracker was uninstalled successfully.
echo ==================================================
echo.
pause
