from __future__ import annotations

from pathlib import Path
from typing import Optional

import torch


class TTSEngine:
    """Small wrapper around Resemble AI ChatterboxTTS."""

    def __init__(self, device: str = "cuda") -> None:
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA wurde angefordert, ist aber nicht verfügbar. "
                "Installiere eine passende CUDA/PyTorch-Version und prüfe deinen NVIDIA-Treiber."
            )

        try:
            from chatterbox.tts import ChatterboxTTS
        except ImportError as exc:
            raise RuntimeError(
                "Chatterbox TTS ist nicht installiert. "
                "Installiere es mit: pip install chatterbox-tts"
            ) from exc

        self.device = device
        self.model = ChatterboxTTS.from_pretrained(device=device)

    @property
    def sample_rate(self) -> int:
        return int(self.model.sr)

    def generate(
        self,
        text: str,
        exaggeration: float,
        cfg_weight: float,
        audio_prompt_path: Optional[str] = None,
    ):
        # Clamp again in the engine so UI changes can never violate the API range.
        exaggeration = max(0.0, min(1.0, float(exaggeration)))
        cfg_weight = max(0.0, min(1.0, float(cfg_weight)))

        prompt = audio_prompt_path if audio_prompt_path else None
        return self.model.generate(
            text,
            audio_prompt_path=prompt,
            exaggeration=exaggeration,
            cfg_weight=cfg_weight,
        )

    def save_waveform(self, waveform, path: str | Path) -> None:
        import torchaudio

        tensor = waveform.detach().cpu()
        if tensor.ndim == 1:
            tensor = tensor.unsqueeze(0)

        torchaudio.save(str(path), tensor, self.sample_rate)
