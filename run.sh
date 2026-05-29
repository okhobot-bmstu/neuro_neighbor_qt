#!/usr/bin/env bash
set -euo pipefail

VENV_DIR=venv

if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "Virtual environment not found. Run install_deps.sh or install_deps_cuda.sh first."
    read -p "Press any key to continue..."
    exit 1
fi

source "$VENV_DIR/bin/activate"
python main.py

read -p "Press any key to continue..."
