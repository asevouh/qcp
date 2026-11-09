#!/bin/bash
cd "$(dirname "$0")"
echo "=== Qudurat Exam Builder - first-time setup ==="
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is not installed. Install it from https://www.python.org/downloads/ then run this file again."
  read -r -p "Press Enter to close"; exit 1
fi
[ -x .venv/bin/python ] || python3 -m venv .venv || { echo "Could not create environment"; read -r; exit 1; }
.venv/bin/python -m pip install --upgrade pip >/dev/null
.venv/bin/python -m pip install -r requirements.txt || { echo "Installing components failed"; read -r; exit 1; }
.venv/bin/python -m playwright install chromium || echo "Chromium download failed - Google Chrome will be used if installed."
chmod +x start_mac.command run_tests_mac.command 2>/dev/null
echo "Setup complete. Run start_mac.command to start the program."
read -r -p "Press Enter to close"
