@echo off
setlocal

REM Debug launcher for CodeSensei GUI.
REM Keeps console open and prints startup errors.

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

echo Launching GUI from: %ROOT%
".venv\Scripts\python.exe" -m code_sensei.cli gui -p "%ROOT%"
set "EXITCODE=%ERRORLEVEL%"
echo.
echo GUI process exited with code: %EXITCODE%
pause
exit /b %EXITCODE%
