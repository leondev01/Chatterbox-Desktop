from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class FFmpegError(RuntimeError):
    pass


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def ffmpeg_version() -> str:
    executable = shutil.which("ffmpeg")
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
    """
    Apply pitch-preserving speed change using FFmpeg's atempo filter,
    then encode the result as MP3.

    The UI range is 0.5x..2.0x, which is exactly within one atempo filter's
    supported range.
    """
    if not ffmpeg_available():
        raise FFmpegError(
            "FFmpeg wurde nicht gefunden. Bitte FFmpeg installieren und "
            "ffmpeg.exe zum PATH hinzufügen."
        )

    speed = float(speed)
    if not 0.5 <= speed <= 2.0:
        raise ValueError("Die Geschwindigkeit muss zwischen 0.5x und 2.0x liegen.")

    source_wav = Path(source_wav)
    output_mp3 = Path(output_mp3)
    output_mp3.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "ffmpeg",
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
