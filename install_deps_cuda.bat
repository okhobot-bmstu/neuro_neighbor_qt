@echo off
setlocal enabledelayedexpansion

set VENV_DIR=venv

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv %VENV_DIR%
    if !errorlevel! neq 0 (
        pause
        exit /b !errorlevel!
    )
)

call "%VENV_DIR%\Scripts\activate.bat"
echo.

:: Определяем версию CUDA
set CUDA_VER=
where nvidia-smi >nul 2>nul
if !errorlevel! equ 0 (
    for /f "tokens=3 delims=<>" %%a in ('nvidia-smi -q -x ^| findstr /C:"<cuda_version>"') do set CUDA_VER=%%a
)

if "%CUDA_VER%"=="" (
    echo [WARN] nvidia-smi not found or CUDA not detected.
    echo [WARN] Installing CPU version instead.
    call install_deps.bat
    exit /b
)

echo Detected CUDA version: %CUDA_VER%

for /f "tokens=1,2 delims=." %%a in ("%CUDA_VER%") do (
    set CUDA_MAJOR=%%a
    set CUDA_MINOR=%%b
)

:: PyTorch index
set TORCH_INDEX=
if "%CUDA_MAJOR%"=="12" (
    if !CUDA_MINOR! GEQ 6 (
        set TORCH_INDEX=https://download.pytorch.org/whl/cu126
    ) else if !CUDA_MINOR! GEQ 4 (
        set TORCH_INDEX=https://download.pytorch.org/whl/cu124
    ) else (
        set TORCH_INDEX=https://download.pytorch.org/whl/cu121
    )
)
if "%CUDA_MAJOR%"=="11" (
    if !CUDA_MINOR! GEQ 8 (
        set TORCH_INDEX=https://download.pytorch.org/whl/cu118
    )
)

set PIP_OPTS=--trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host download.pytorch.org

echo.
echo Installing PyTorch with CUDA...
if not "%TORCH_INDEX%"=="" (
    pip install %PIP_OPTS% torch torchvision torchaudio --index-url %TORCH_INDEX%
) else (
    pip install %PIP_OPTS% torch torchvision torchaudio
)

echo.
echo Installing other dependencies...
pip install %PIP_OPTS% -r requirements.txt

echo.
echo Installing llama-cpp-python with CUDA...

:: Короткий TMP — стандартный workaround для Windows MAX_PATH
set "ORIG_TMP=%TMP%"
set "ORIG_TEMP=%TEMP%"
if not exist "C:\tmp" mkdir C:\tmp 2>nul
set "TMP=C:\tmp"
set "TEMP=C:\tmp"

set CMAKE_ARGS=-DLLAMA_CUDA=on
pip install %PIP_OPTS% llama-cpp-python

if !errorlevel! neq 0 (
    echo.
    echo [WARN] pip install failed. Retrying via git clone...
    if exist "C:\tmp\llama-cpp-python" rmdir /s /q "C:\tmp\llama-cpp-python"
    git clone --recurse-submodules --depth 1 https://github.com/abetlen/llama-cpp-python C:\tmp\llama-cpp-python
    if !errorlevel! equ 0 (
        pushd C:\tmp\llama-cpp-python
        set CMAKE_ARGS=-DLLAMA_CUDA=on
        pip install %PIP_OPTS% .
        popd
    )
    rmdir /s /q "C:\tmp\llama-cpp-python" 2>nul
)

set "TMP=%ORIG_TMP%"
set "TEMP=%ORIG_TEMP%"

echo.
echo Installing ai_nn...
pip install -e ai_nn --no-deps

echo.
echo Done!
pause
