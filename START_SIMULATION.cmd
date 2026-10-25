@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m rovo cli --config config\simulation.json
) else (
  python -m rovo cli --config config\simulation.json
)
pause
