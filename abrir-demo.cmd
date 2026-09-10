@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
  if errorlevel 1 exit /b 1
)
.venv\Scripts\python.exe -m pip install -e ".[test]"
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m energia_observada demo --launch --port 8502
pause
