@echo off
title CapRecut — CapCut Companion Plugin & Video Descrambler
color 0b
cd /d "%~dp0"

:: If a file is dragged and dropped onto this .bat file
if not "%~1"=="" (
    echo [CapRecut] Processing dropped video file: %~1
    python "%~dp0caprecut_capcut.py" repair-file "%~1"
    echo.
    pause
    exit /b
)

:: Otherwise open interactive menu
python "%~dp0caprecut_capcut.py"
echo.
pause

