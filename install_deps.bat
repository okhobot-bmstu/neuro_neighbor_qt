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

echo Installing dependencies (CPU)...
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
if !errorlevel! neq 0 (
    pip install -r requirements.txt
)

echo.
echo Installing llama-cpp-python (CPU)...

:: Короткий TMP — workaround для Windows MAX_PATH
set "ORIG_TMP=%TMP%"
set "ORIG_TEMP=%TEMP%"
if not exist "C:\tmp" mkdir C:\tmp 2>nul
set "TMP=C:\tmp"
set "TEMP=C:\tmp"

pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org llama-cpp-python

if !errorlevel! neq 0 (
    echo.
    echo [WARN] pip install failed. Retrying via git clone...
    if exist "C:\tmp\llama-cpp-python" rmdir /s /q "C:\tmp\llama-cpp-python"
    git clone --recurse-submodules --depth 1 https://github.com/abetlen/llama-cpp-python C:\tmp\llama-cpp-python
    if !errorlevel! equ 0 (
        pushd C:\tmp\llama-cpp-python
        pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org .
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
