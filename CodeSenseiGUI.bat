@echo off
REM CodeSensei GUI Launcher
REM This script launches the GUI application

setlocal enabledelayedexpansion

REM Get the directory where this batch file is located
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%.") do set "SCRIPT_DIR=%%~fI"

REM Activate the virtual environment
call "%SCRIPT_DIR%\.venv\Scripts\activate.bat"

REM Launch the GUI
python -m code_sensei.cli gui --project-dir "%SCRIPT_DIR%"

REM Pause if there was an error
if not %ERRORLEVEL% equ 0 (
    pause
)
