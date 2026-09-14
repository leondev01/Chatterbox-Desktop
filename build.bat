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

echo [1/6] Checking app dependencies...
"%PY%" -c "import PySide6, qfluentwidgets, chatterbox, torch, torchaudio; print('Dependencies OK')" || exit /b 1

echo [2/6] Checking CUDA...
"%PY%" -c "import torch; assert torch.cuda.is_available(), 'CUDA ist nicht verfügbar'; print('CUDA OK:', torch.cuda.get_device_name(0))" || exit /b 1

echo [3/6] Checking FFmpeg...
if exist "%~dp0ffmpeg.exe" (
    echo Bundled FFmpeg gefunden.
) else if exist "%~dp0third_party\ffmpeg.exe" (
    echo Bundled FFmpeg gefunden.
) else (
    echo [ERROR] ffmpeg.exe fehlt.
    echo Lege eine Windows-64-bit ffmpeg.exe in diesen Projektordner oder unter third_party\ffmpeg.exe.
    exit /b 1
)

echo [4/6] Installing/updating PyInstaller...
"%PY%" -m pip install -U pyinstaller || exit /b 1

echo [5/6] Building application...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
"%PY%" -m PyInstaller --noconfirm --clean ChatterboxDesktop.spec || exit /b 1

echo [6/6] Done.
echo.
echo Output: %~dp0dist\ChatterboxDesktop\
echo Start:  %~dp0dist\ChatterboxDesktop\ChatterboxDesktop.exe
pause
