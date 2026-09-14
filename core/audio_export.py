from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class FFmpegError(RuntimeError):
    pass


def _bundled_ffmpeg() -> Path | None:
    """Return the FFmpeg shipped next to the packaged application, if present."""
    candidates = [
        Path(__file__).resolve().parent.parent / "ffmpeg.exe",
        Path(__file__).resolve().parent.parent / "third_party" / "ffmpeg.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def ffmpeg_executable() -> str | None:
    bundled = _bundled_ffmpeg()
    if bundled:
        return str(bundled)
    return shutil.which("ffmpeg")


def ffmpeg_available() -> bool:
    return ffmpeg_executable() is not None


def ffmpeg_version() -> str:
    executable = ffmpeg_executable()
    if not executable:
        return ""

    result = subprocess.run(
        [executable, "-version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.stdout.splitlines()[0] if result.stdout else ""


def export_mp3_with_speed(
    source_wav: str | Path,
    output_mp3: str | Path,
    speed: float,
) -> None:
    """Apply pitch-preserving speed change with FFmpeg and export MP3."""
    executable = ffmpeg_executable()
    if not executable:
        raise FFmpegError(
            "FFmpeg wurde nicht gefunden. Die fertige App bringt FFmpeg "
            "normalerweise bereits mit. Bei einer Entwicklungsinstallation "
            "muss ffmpeg.exe im PATH liegen."
        )

    speed = float(speed)
    if not 0.5 <= speed <= 2.0:
        raise ValueError("Die Geschwindigkeit muss zwischen 0.5x und 2.0x liegen.")

    source_wav = Path(source_wav)
    output_mp3 = Path(output_mp3)
    output_mp3.parent.mkdir(parents=True, exist_ok=True)

    command = [
        executable,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source_wav),
        "-filter:a",
        f"atempo={speed:.6f}",
        "-codec:a",
        "libmp3lame",
        "-q:a",
        "2",
        str(output_mp3),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if result.returncode != 0:
        raise FFmpegError(
            "FFmpeg konnte die Audiodatei nicht exportieren.\n\n"
            + (result.stderr.strip() or "Unbekannter FFmpeg-Fehler.")
        )
