#!/usr/bin/env bash
set -euo pipefail

VENV_DIR=venv

if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "Creating virtual environment..."
    python -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
echo

# Detect CUDA version
CUDA_VER=""
if command -v nvidia-smi &>/dev/null; then
    CUDA_VER=$(nvidia-smi -q -x 2>/dev/null | grep -oP '<cuda_version>\K[^<]+' || true)
fi

if [ -z "$CUDA_VER" ]; then
    echo "[WARN] nvidia-smi not found or CUDA not detected."
    echo "[WARN] Installing CPU version instead."
    bash install_deps.sh
    exit
fi

echo "Detected CUDA version: $CUDA_VER"

CUDA_MAJOR=$(echo "$CUDA_VER" | cut -d. -f1)
CUDA_MINOR=$(echo "$CUDA_VER" | cut -d. -f2)

# PyTorch index
TORCH_INDEX=""
if [ "$CUDA_MAJOR" = "12" ]; then
    if [ "$CUDA_MINOR" -ge 6 ] 2>/dev/null; then
        TORCH_INDEX="https://download.pytorch.org/whl/cu126"
    elif [ "$CUDA_MINOR" -ge 4 ] 2>/dev/null; then
        TORCH_INDEX="https://download.pytorch.org/whl/cu124"
    else
        TORCH_INDEX="https://download.pytorch.org/whl/cu121"
    fi
elif [ "$CUDA_MAJOR" = "11" ]; then
    if [ "$CUDA_MINOR" -ge 8 ] 2>/dev/null; then
        TORCH_INDEX="https://download.pytorch.org/whl/cu118"
    fi
fi

PIP_OPTS="--trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host download.pytorch.org"

echo
echo "Installing PyTorch with CUDA..."
if [ -n "$TORCH_INDEX" ]; then
    pip install $PIP_OPTS torch torchvision torchaudio --index-url "$TORCH_INDEX"
else
    pip install $PIP_OPTS torch torchvision torchaudio
fi

echo
echo "Installing other dependencies..."
pip install $PIP_OPTS -r requirements.txt

echo
echo "Installing llama-cpp-python with CUDA..."

export CMAKE_ARGS="-DLLAMA_CUDA=on"
pip install $PIP_OPTS llama-cpp-python || {
    echo
    echo "[WARN] pip install failed. Retrying via git clone..."
    rm -rf /tmp/llama-cpp-python
    git clone --recurse-submodules --depth 1 https://github.com/abetlen/llama-cpp-python /tmp/llama-cpp-python
    if [ $? -eq 0 ]; then
        pushd /tmp/llama-cpp-python
        CMAKE_ARGS="-DLLAMA_CUDA=on" pip install $PIP_OPTS .
        popd
    fi
    rm -rf /tmp/llama-cpp-python
}

echo
echo "Installing ai_nn..."
pip install -e ai_nn --no-deps

echo
echo "Done!"
