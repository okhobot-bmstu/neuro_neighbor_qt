@echo off

set VENV_DIR=venv

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Virtual environment not found. Run install_deps.bat or install_deps_cuda.bat first.
    pause
    exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat"
python main.py

pause
