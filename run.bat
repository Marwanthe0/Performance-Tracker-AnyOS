@echo off
setlocal enabledelayedexpansion
title Performance Tracker Launcher
cd /d "%~dp0"

echo ==================================================
echo    Launching Performance Tracker...
echo ==================================================

:: 1. If compiled standalone executable exists, launch it directly!
if exist "%~dp0Installers\Windows\PerformanceTracker.exe" (
    echo [*] Found standalone executable: %~dp0Installers\Windows\PerformanceTracker.exe
    start "" "%~dp0Installers\Windows\PerformanceTracker.exe" %*
    exit /b 0
)
if exist "%~dp0PerformanceTracker.exe" (
    echo [*] Found standalone executable: %~dp0PerformanceTracker.exe
    start "" "%~dp0PerformanceTracker.exe" %*
    exit /b 0
)
if exist "%~dp0dist\PerformanceTracker.exe" (
    echo [*] Found standalone executable: %~dp0dist\PerformanceTracker.exe
    start "" "%~dp0dist\PerformanceTracker.exe" %*
    exit /b 0
)
if exist "%LOCALAPPDATA%\Programs\PerformanceTracker\PerformanceTracker.exe" (
    echo [*] Found installed executable: %LOCALAPPDATA%\Programs\PerformanceTracker\PerformanceTracker.exe
    start "" "%LOCALAPPDATA%\Programs\PerformanceTracker\PerformanceTracker.exe" %*
    exit /b 0
)

:: 2. Search for available Python executable
set "PY_EXE="

:: Check python on PATH
where python >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_EXE=python"
    goto :run_py
)

:: Check py launcher
where py >nul 2>&1
if !errorlevel! equ 0 (
    py -c "import sys" >nul 2>&1
    if !errorlevel! equ 0 (
        set "PY_EXE=py"
        goto :run_py
    )
)

:: Check standard LocalAppData Python locations
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto :run_py
)
if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    goto :run_py
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    goto :run_py
)
if exist "C:\Python312\python.exe" (
    set "PY_EXE=C:\Python312\python.exe"
    goto :run_py
)

echo [!] Error: No Python installation or dist\PerformanceTracker.exe was found!
echo Please install Python or run build.py to compile the executable.
pause
exit /b 1

:run_py
echo [*] Launching using: "!PY_EXE!"
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
start "" "!PY_EXE!" -m performance_track.app %*
exit /b 0
