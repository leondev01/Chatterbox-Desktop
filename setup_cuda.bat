@echo off
setlocal
cd /d "%~dp0"

if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY=%~dp0.venv\Scripts\python.exe"
) else if exist "%~dp0..\.venv\Scripts\python.exe" (
    set "PY=%~dp0..\.venv\Scripts\python.exe"
) else (
    echo [ERROR] Keine .venv gefunden.
    exit /b 1
)

echo Installing CUDA-enabled PyTorch for NVIDIA GPUs...
"%PY%" -m pip uninstall torch torchaudio -y
"%PY%" -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128 || exit /b 1

echo.
echo Checking CUDA...
"%PY%" -c "import torch; print('Torch:', torch.__version__); print('CUDA:', torch.version.cuda); print('CUDA available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NONE')" || exit /b 1
pause
