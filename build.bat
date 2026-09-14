@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo   Chatterbox Desktop - Windows Build
echo ========================================


if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY=%~dp0.venv\Scripts\python.exe"
) else if exist "%~dp0..\.venv\Scripts\python.exe" (
    set "PY=%~dp0..\.venv\Scripts\python.exe"
) else (
    echo [ERROR] Keine .venv gefunden.
    echo Erstelle zuerst: py -3.11 -m venv .venv
    exit /b 1
)

echo [1/6] Installing app dependencies...
"%PY%" -m pip install -r requirements.txt || exit /b 1

echo [2/6] Installing CUDA PyTorch...
"%PY%" -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128 || exit /b 1

echo [3/6] Checking CUDA...
"%PY%" -c "import torch; assert torch.cuda.is_available(), 'CUDA ist nicht verfügbar'; print('CUDA OK:', torch.cuda.get_device_name(0))" || exit /b 1

echo [4/6] Installing PyInstaller...
"%PY%" -m pip install -U pyinstaller || exit /b 1

if not exist "%~dp0ffmpeg.exe" if not exist "%~dp0third_party\ffmpeg.exe" (
    echo.
    echo [WARNING] ffmpeg.exe wurde nicht gefunden.
    echo Lege ffmpeg.exe neben build.bat oder unter third_party\ffmpeg.exe.
    echo Der Build laeuft weiter, aber MP3-Export ist in der fertigen App ohne FFmpeg nicht moeglich.
    echo.
)

echo [5/6] Building application...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
"%PY%" -m PyInstaller --noconfirm --clean ChatterboxDesktop.spec || exit /b 1

echo [6/6] Done.
echo.
echo Output: %~dp0dist\ChatterboxDesktop\
echo Start:  %~dp0dist\ChatterboxDesktop\ChatterboxDesktop.exe
pause
