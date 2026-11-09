#!/bin/bash
cd "$(dirname "$0")"
export PYTHONIOENCODING=utf-8
.venv/bin/python tests/run_all.py
open test_report.html 2>/dev/null || xdg-open test_report.html 2>/dev/null
read -r -p "Press Enter to close"
