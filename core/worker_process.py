from __future__ import annotations

import contextlib
import json
import sys
import threading
import traceback
from pathlib import Path


def send(kind: str, **data) -> None:
    payload = {"type": kind, **data}
    print("CBMSG:" + json.dumps(payload, ensure_ascii=False), flush=True)


def main() -> int:
    # Import/load Chatterbox only in the child process. The Qt parent therefore
    # remains responsive even when CUDA/model initialization takes minutes.
    try:
        from core.tts_engine import TTSEngine
        with contextlib.redirect_stdout(sys.stderr):
            engine = TTSEngine(device="cuda")
        send("ready")
    except Exception as exc:
        send("error", message=str(exc))
        return 1

    generating = {"active": False}

    def do_generate(command: dict) -> None:
        if generating["active"]:
            send("error", message="Es läuft bereits eine Generierung.")
            return
        generating["active"] = True
        temp_wav = None
        try:
            text = str(command.get("text", "")).strip()
            if not text:
                raise ValueError("Bitte gib zuerst einen Text ein.")

            output_dir = Path(str(command["output_dir"]))
            output_dir.mkdir(parents=True, exist_ok=True)
            number = int(command["number"])
            output_mp3 = output_dir / f"Voiceover({number}).mp3"
            import uuid
            temp_wav = output_dir / f".chatterbox_{uuid.uuid4().hex}.wav"

            voice_path = str(command.get("voice_path", ""))
            exaggeration = max(0.0, min(1.0, float(command.get("exaggeration", 0.5))))
            cfg_weight = max(0.0, min(1.0, float(command.get("cfg_weight", 0.5))))
            speed = float(command.get("speed", 1.0))

            send("status", message="Audio wird geriert.")
            # The first transformer forward pass happens before Chatterbox's sampling loop and can take several seconds.
            # Use an indeterminate bar for that phase instead of leaving the UI at 5%.
            send("progress_mode", mode="busy")

            sampling_started = {"sent": False}

            def on_progress(value: float) -> None:
                if not sampling_started["sent"]:
                    sampling_started["sent"] = True
                    send("progress_mode", mode="determinate")
                    send("progress", value=0)
                send("progress", value=int(max(0.0, min(1.0, value)) * 90))

            with contextlib.redirect_stdout(sys.stderr):
                wav = engine.generate(
                    text=text,
                    exaggeration=exaggeration,
                    cfg_weight=cfg_weight,
                    audio_prompt_path=voice_path or None,
                    progress_callback=on_progress,
                )

            send("progress", value=95)
            send("status", message="Audio fertig · MP3 wird exportiert …")
            engine.save_waveform(wav, temp_wav)

            from core.audio_export import export_mp3_with_speed, ffmpeg_available
            if not ffmpeg_available():
                raise RuntimeError("FFmpeg wurde nicht gefunden. Lege ffmpeg.exe neben die App oder füge FFmpeg zum PATH hinzu.")
            export_mp3_with_speed(temp_wav, output_mp3, speed)
            send("progress", value=100)
            send("finished", path=str(output_mp3))
        except Exception as exc:
            send("error", message=str(exc))
            # Keep a useful traceback in the developer console, not in the UI protocol.
            traceback.print_exc(file=sys.stderr)
        finally:
            generating["active"] = False
            if temp_wav:
                try:
                    Path(temp_wav).unlink(missing_ok=True)
                except OSError:
                    pass

    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            command = json.loads(raw)
        except json.JSONDecodeError:
            continue
        name = command.get("command")
        if name == "generate":
            threading.Thread(target=do_generate, args=(command,), daemon=True).start()
        elif name == "shutdown":
            return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
