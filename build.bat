@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo   Chatterbox Desktop - Windows Build
echo ========================================
echo.

if exist "%~dp0.venv\Scripts\python.exe" (set "PY=%~dp0.venv\Scripts\python.exe") else if exist "%~dp0..\.venv\Scripts\python.exe" (set "PY=%~dp0..\.venv\Scripts\python.exe") else (echo [ERROR] Keine .venv gefunden.&echo Erstelle zuerst: py -3.11 -m venv .venv&exit /b 1)

echo [1/7] Checking Python environment...
"%PY%" --version || goto :error

echo.
echo [2/7] Installing project dependencies...
"%PY%" -m pip install --upgrade pip || goto :error
"%PY%" -m pip install -r "%~dp0requirements.txt" || goto :error

echo.
echo [3/7] Installing CUDA-enabled PyTorch...
"%PY%" -m pip install --upgrade torch torchaudio --index-url https://download.pytorch.org/whl/cu128 || goto :error
"%PY%" -c "import torch; assert torch.cuda.is_available(), 'CUDA ist nicht verfügbar'; print('CUDA OK:', torch.cuda.get_device_name(0))" || goto :error

echo.
echo [4/7] Checking FFmpeg...
if exist "%~dp0ffmpeg.exe" goto :ffmpeg_ok
if exist "%~dp0third_party\ffmpeg.exe" goto :ffmpeg_ok
where ffmpeg.exe >nul 2>&1
if not errorlevel 1 goto :ffmpeg_ok

echo FFmpeg nicht gefunden. Lade automatisch einen Windows Essentials Build...
set "FFMPEG_ZIP=%TEMP%\chatterbox_ffmpeg.zip"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile '%FFMPEG_ZIP%'" || goto :error
powershell -NoProfile -ExecutionPolicy Bypass -Command "$tmp=Join-Path $env:TEMP 'chatterbox_ffmpeg_extract'; if(Test-Path $tmp){Remove-Item $tmp -Recurse -Force}; Expand-Archive -LiteralPath '%FFMPEG_ZIP%' -DestinationPath $tmp -Force; $exe=Get-ChildItem $tmp -Recurse -Filter ffmpeg.exe | Select-Object -First 1; if(-not $exe){exit 1}; Copy-Item $exe.FullName '%~dp0ffmpeg.exe' -Force" || goto :error
del /q "%FFMPEG_ZIP%" >nul 2>&1
if not exist "%~dp0ffmpeg.exe" goto :error
:ffmpeg_ok
if not exist "%~dp0app_icon.ico" (echo [ERROR] app_icon.ico fehlt.&goto :error)

echo.
echo [5/7] Verifying application dependencies...
"%PY%" -c "import PySide6, qfluentwidgets, chatterbox, torch, torchaudio; print('All application dependencies OK')" || goto :error

echo.
echo [6/7] Installing/updating PyInstaller...
"%PY%" -m pip install --upgrade pyinstaller || goto :error

echo.
echo [7/7] Building Chatterbox Desktop...
if exist "%~dp0build" rmdir /s /q "%~dp0build"
if exist "%~dp0dist" rmdir /s /q "%~dp0dist"
"%PY%" -m PyInstaller --noconfirm --clean "%~dp0ChatterboxDesktop.spec" || goto :error

echo.
echo ========================================
echo   BUILD SUCCESSFUL
echo ========================================
echo Output: %~dp0dist\ChatterboxDesktop\
echo EXE: %~dp0dist\ChatterboxDesktop\ChatterboxDesktop.exe
pause
exit /b 0
:error
echo.
echo ========================================
echo   BUILD FAILED
echo ========================================
pause
exit /b 1
