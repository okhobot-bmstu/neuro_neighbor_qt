#!/usr/bin/env bash
set -euo pipefail

VENV_DIR=venv

if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "Creating virtual environment..."
    python -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
echo

echo "Installing dependencies (CPU)..."
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt || \
    pip install -r requirements.txt

echo
echo "Installing llama-cpp-python (CPU)..."

pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org llama-cpp-python || {
    echo
    echo "[WARN] pip install failed. Retrying via git clone..."
    rm -rf /tmp/llama-cpp-python
    git clone --recurse-submodules --depth 1 https://github.com/abetlen/llama-cpp-python /tmp/llama-cpp-python
    if [ $? -eq 0 ]; then
        pushd /tmp/llama-cpp-python
        pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org .
        popd
    fi
    rm -rf /tmp/llama-cpp-python
}

echo
echo "Installing ai_nn..."
pip install -e ai_nn --no-deps

echo
echo "Done!"
