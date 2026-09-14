# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_dynamic_libs


# Chatterbox and the Qt/ML stack use dynamic imports and package data.
datas = [("app_icon.ico", ".")]
binaries = []
hiddenimports = []

# Bundle FFmpeg when the developer places it in the project.
from pathlib import Path
if Path("ffmpeg.exe").is_file():
    binaries.append(("ffmpeg.exe", "."))
elif Path("third_party/ffmpeg.exe").is_file():
    binaries.append(("third_party/ffmpeg.exe", "third_party"))

for package in ("chatterbox", "qfluentwidgets", "torch", "torchaudio"):
    try:
        d, b, h = collect_all(package)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

for package in ("chatterbox", "transformers", "diffusers", "safetensors"):
    try:
        hiddenimports += collect_submodules(package)
    except Exception:
        pass

try:
    binaries += collect_dynamic_libs("torch")
except Exception:
    pass

# Remove duplicates while keeping order.
datas = list(dict.fromkeys(datas))
binaries = list(dict.fromkeys(binaries))
hiddenimports = list(dict.fromkeys(hiddenimports))


a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ChatterboxDesktop",
    icon="app_icon.ico",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
