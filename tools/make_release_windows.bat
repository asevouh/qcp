@echo off
chcp 65001 >nul
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
set PYTHONDONTWRITEBYTECODE=1
set PY=
if exist ".venv\Scripts\python.exe" set PY=".venv\Scripts\python.exe"
if not defined PY (
  where py >nul 2>nul && set PY=py -3
)
if not defined PY (
  where python >nul 2>nul && set PY=python
)
if not defined PY (
  echo Python was not found. Run setup_windows.bat first.
  pause
  exit /b 1
)
%PY% "tools\make_release.py"
echo.
pause
