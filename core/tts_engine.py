from __future__ import annotations

import copy
from pathlib import Path
from typing import Optional

import torch


class TTSEngine:
    """Chatterbox TTS wrapper with CUDA checks and voice-condition caching."""

    def __init__(self, device: str = "cuda") -> None:
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA ist in dieser virtuellen Umgebung nicht verfügbar.\n\n"
                f"Python: {__import__('sys').executable}\n"
                f"PyTorch: {torch.__version__}\n"
                f"CUDA-Build: {torch.version.cuda}\n\n"
                "Installiere die CUDA-Version von PyTorch in dieser .venv "
                "und starte die App danach erneut."
            )

        try:
            from chatterbox.tts import ChatterboxTTS
        except ImportError as exc:
            raise RuntimeError(
                "Chatterbox TTS ist nicht installiert. "
                "Installiere es mit: python -m pip install chatterbox-tts"
            ) from exc

        self.device = device

        # Small, safe CUDA performance tweaks. They do not change the model/API.
        if device == "cuda":
            torch.set_float32_matmul_precision("high")
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True

        self.model = ChatterboxTTS.from_pretrained(device=device)
        self._cached_voice_path: str | None = None
        self._cached_voice_mtime_ns: int | None = None
        self._cached_conditionals = None

    @property
    def sample_rate(self) -> int:
        return int(self.model.sr)

    def _voice_key(self, audio_prompt_path: str) -> tuple[str, int]:
        path = Path(audio_prompt_path).resolve()
        return str(path), path.stat().st_mtime_ns

    def _clone_conditionals(self):
        # Chatterbox mutates self.model.conds when exaggeration changes. Keep a
        # private cached copy so the expensive reference-audio analysis is only
        # performed once per voice file during the lifetime of the app.
        return copy.deepcopy(self._cached_conditionals)

    def prepare_voice(self, audio_prompt_path: str, exaggeration: float = 0.5) -> None:
        path, mtime_ns = self._voice_key(audio_prompt_path)
        if (
            self._cached_conditionals is not None
            and self._cached_voice_path == path
            and self._cached_voice_mtime_ns == mtime_ns
        ):
            self.model.conds = self._clone_conditionals()
            return

        self.model.prepare_conditionals(path, exaggeration=float(max(0.0, min(1.0, exaggeration))))
        self._cached_conditionals = copy.deepcopy(self.model.conds)
        self._cached_voice_path = path
        self._cached_voice_mtime_ns = mtime_ns

    def generate(
        self,
        text: str,
        exaggeration: float,
        cfg_weight: float,
        audio_prompt_path: Optional[str] = None,
    ):
        exaggeration = max(0.0, min(1.0, float(exaggeration)))
        cfg_weight = max(0.0, min(1.0, float(cfg_weight)))

        if audio_prompt_path:
            self.prepare_voice(audio_prompt_path, exaggeration=exaggeration)
            # Conditions are already on the model. Calling generate without the
            # path prevents Chatterbox from decoding/analyzing the reference WAV
            # a second time in the same generation.
            audio_prompt_path = None

        with torch.inference_mode():
            return self.model.generate(
                text,
                audio_prompt_path=audio_prompt_path,
                exaggeration=exaggeration,
                cfg_weight=cfg_weight,
            )

    def save_waveform(self, waveform, path: str | Path) -> None:
        import torchaudio

        tensor = waveform.detach().cpu()
        if tensor.ndim == 1:
            tensor = tensor.unsqueeze(0)

        torchaudio.save(str(path), tensor, self.sample_rate)
