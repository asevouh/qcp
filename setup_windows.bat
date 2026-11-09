@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo   Qudurat Exam Builder - first-time setup
echo ============================================================
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY goto nopython
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
if errorlevel 1 goto nopython
if exist ".venv\Scripts\python.exe" goto install
echo Creating private Python environment...
%PY% -m venv .venv
if errorlevel 1 (
  echo [!] Could not create the environment.
  pause
  exit /b 1
)
:install
echo Installing components (needs internet, one time only)...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [!] Installing components failed. Check the internet connection and run again.
  pause
  exit /b 1
)
echo Installing the PDF rendering engine (Chromium)...
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 echo [i] Chromium download failed - the program will use Microsoft Edge instead.
echo.
echo ============================================================
echo   Setup complete. Double-click start_windows.bat to run the program.
echo ============================================================
pause
exit /b 0
:nopython
echo.
echo [!] Python 3.9+ was not found.
echo     Install Python from https://www.python.org/downloads/
echo     and tick "Add python.exe to PATH" during installation, then run this file again.
pause
exit /b 1
