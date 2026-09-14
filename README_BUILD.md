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
