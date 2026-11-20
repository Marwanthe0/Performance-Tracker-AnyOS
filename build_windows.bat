@echo off
REM build_windows.bat - Compile Performance Track into a standalone Windows Executable
setlocal
echo ==================================================
echo   Building Performance Track for Windows
echo ==================================================

py build.py --target windows 2>nul || python build.py --target windows
pause
