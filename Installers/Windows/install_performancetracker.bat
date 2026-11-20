@echo off
setlocal enabledelayedexpansion
title PerformanceTracker Windows Installer

echo ==================================================
echo   PerformanceTracker Windows Installer v1.0.0
echo ==================================================
echo.

set "SOURCE_EXE=%~dp0PerformanceTracker.exe"
if not exist "!SOURCE_EXE!" (
    if exist "%~dp0dist\PerformanceTracker.exe" (
        set "SOURCE_EXE=%~dp0dist\PerformanceTracker.exe"
    ) else (
        echo [!] Error: PerformanceTracker.exe not found!
        echo Please ensure PerformanceTracker.exe is in the same directory as this installer.
        pause
        exit /b 1
    )
)

set "TARGET_DIR=%LOCALAPPDATA%\Programs\PerformanceTracker"
echo [*] Installing to: !TARGET_DIR!...

powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Process -Name PerformanceTracker -ErrorAction SilentlyContinue | Stop-Process -Force" >nul 2>&1

if not exist "!TARGET_DIR!" mkdir "!TARGET_DIR!" 2>nul
copy /Y "!SOURCE_EXE!" "!TARGET_DIR!\PerformanceTracker.exe" >nul
if !errorlevel! neq 0 (
    echo [!] Failed to copy executable to: !TARGET_DIR!
    echo Please make sure you have permissions and the app is not currently running.
    pause
    exit /b 1
)

echo [*] Creating Desktop and Start Menu Shortcuts...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $desk = $ws.SpecialFolders.Item('Desktop'); if (-not $desk -or -not (Test-Path $desk)) { $desk = [Environment]::GetFolderPath('Desktop') }; if (-not $desk -or -not (Test-Path $desk)) { $desk = [Environment]::GetFolderPath('CommonDesktopDirectory') }; if (-not (Test-Path $desk)) { New-Item -ItemType Directory -Path $desk -Force | Out-Null }; $targetExe = Join-Path '%TARGET_DIR%' 'PerformanceTracker.exe'; $deskLink = Join-Path $desk 'PerformanceTracker.lnk'; $s = $ws.CreateShortcut($deskLink); $s.TargetPath = $targetExe; $s.WorkingDirectory = '%TARGET_DIR%'; $s.Description = 'PerformanceTracker - System Performance Monitor'; $s.Save(); Write-Host '[*] Desktop Shortcut created at:' $deskLink; $programs = [Environment]::GetFolderPath('Programs'); if (-not $programs -or -not (Test-Path $programs)) { $programs = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs' }; if (Test-Path $programs) { $smLink = Join-Path $programs 'PerformanceTracker.lnk'; $s2 = $ws.CreateShortcut($smLink); $s2.TargetPath = $targetExe; $s2.WorkingDirectory = '%TARGET_DIR%'; $s2.Description = 'PerformanceTracker - System Performance Monitor'; $s2.Save(); Write-Host '[*] Start Menu Shortcut created at:' $smLink }"

echo.
echo ==================================================
echo   [OK] Installation completed successfully!
echo ==================================================
echo Launch PerformanceTracker anytime from:
echo   - Your Desktop shortcut
echo   - Windows Start Menu / Search ("PerformanceTracker")
echo   - Directly: "!TARGET_DIR!\PerformanceTracker.exe"
echo.
pause
