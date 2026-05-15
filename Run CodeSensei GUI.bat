@echo off
setlocal

REM Launch CodeSensei GUI with one double-click from Windows Explorer.
REM This script expects to live in the project root.

set "ROOT=%~dp0"
for %%I in ("%ROOT%.") do set "ROOT=%%~fI"
cd /d "%ROOT%"

if not exist ".venv\Scripts\python.exe" (
    echo [CodeSensei GUI] Missing virtual environment Python at .venv\Scripts\python.exe
    echo Create it with: python -m venv .venv
    echo Then install deps with: .venv\Scripts\python.exe -m pip install -e ".[dev]"
    pause
    exit /b 1
)

set "PYTHONPATH=src"

".venv\Scripts\python.exe" -c "import PyQt6" >nul 2>&1
if errorlevel 1 (
    echo [CodeSensei GUI] PyQt6 is not installed in this virtual environment.
    echo Install with: .venv\Scripts\python.exe -m pip install PyQt6
    pause
    exit /b 1
)

REM Prefer pythonw to avoid opening an extra console window.
if exist ".venv\Scripts\pythonw.exe" (
    start "CodeSensei GUI" /D "%ROOT%" ".venv\Scripts\pythonw.exe" -m code_sensei.cli gui -p "%ROOT%"
) else (
    start "CodeSensei GUI" /D "%ROOT%" ".venv\Scripts\python.exe" -m code_sensei.cli gui -p "%ROOT%"
)

exit /b 0
