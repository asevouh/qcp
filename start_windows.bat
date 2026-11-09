@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Please run setup_windows.bat first.
  pause
  exit /b 1
)
set PYTHONIOENCODING=utf-8
echo Starting Qudurat Exam Builder... keep this window open while using the program.
".venv\Scripts\python.exe" app\server.py %*
pause
