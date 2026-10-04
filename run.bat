@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Creating a local Python environment...
    py -3 -m venv .venv
    if errorlevel 1 (
        echo Python 3 was not found. Install it from https://www.python.org/ and try again.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Could not install the audio libraries.
        pause
        exit /b 1
    )
)
start "DON SYN" /D "%~dp0" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py"
exit /b 0
