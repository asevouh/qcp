#!/bin/bash
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { echo "Please run setup_mac.command first."; read -r; exit 1; }
export PYTHONIOENCODING=utf-8
.venv/bin/python app/server.py "$@"
