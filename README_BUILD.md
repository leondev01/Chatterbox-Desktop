# Windows EXE Build

The application is built as a PyInstaller **onedir** package. This is intentional:
PyTorch/Chatterbox are large ML dependencies and onedir is more reliable than a
single-file executable for this stack.

## Build

1. Use Python 3.11.
2. Create/activate the project venv.
3. Make sure CUDA PyTorch works.
4. Put `ffmpeg.exe` next to `build.bat` (or in `third_party\\ffmpeg.exe`).
5. Run `build.bat`.

The finished application is in `dist\\ChatterboxDesktop\\`.
Run `ChatterboxDesktop.exe` from that folder.

The generated app contains Python, PySide6, QFluentWidgets, PyTorch,
Torchaudio and Chatterbox, so the target PC does not need Python/pip or the
Python packages installed separately. A compatible NVIDIA driver is still
required for CUDA inference.

The Chatterbox model itself may still be downloaded on first launch by the
Hugging Face/model-loading mechanism unless the model cache is distributed too.


## Version 0.0.2

The 0.0.1 build uses a responsive scrollable content area so controls are not clipped in smaller windows. The final PyInstaller build is intended as a Windows onedir application and bundles Python dependencies and FFmpeg.

Before building, place a Windows x64 `ffmpeg.exe` next to `build.bat` or in `third_party\ffmpeg.exe`. The target PC still needs a compatible NVIDIA driver for CUDA.


### Performance and CUDA

The app requires CUDA-enabled PyTorch for GPU generation. Do not run `pip install -r requirements.txt` as a replacement for the CUDA Torch install; install CUDA Torch separately using the command documented in `requirements.txt`. The engine enables safe TF32 settings on CUDA and caches the selected reference-voice conditionals so the same WAV is not analyzed again for every generation.

The original Chatterbox model can still take several seconds or longer depending on text, voice reference and hardware. A 20-minute generation on an RTX 4060 is not expected; if that happens, first verify `torch.cuda.is_available()` is `True` inside the app's `.venv`.
