from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


APP_NAME = "ChatterboxDesktopApp"


class SettingsManager:
    """Persistent JSON configuration under %APPDATA%/ChatterboxDesktopApp."""

    def __init__(self) -> None:
        appdata = os.environ.get("APPDATA")
        if not appdata:
            appdata = str(Path.home() / "AppData" / "Roaming")

        self.base_dir = Path(appdata) / APP_NAME
        self.config_path = self.base_dir / "config.json"
        self.voices_dir = self.base_dir / "voices"

        self.data: dict[str, Any] = {
            "selected_voice": "",
            "safe_location": "",
            "counter": 0,
        }
        self.load()

    def ensure_directories(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.voices_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> None:
        self.ensure_directories()
        if not self.config_path.exists():
            return

        try:
            loaded = json.loads(self.config_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self.data.update(loaded)
        except (OSError, json.JSONDecodeError):
            # A broken config should not prevent the app from starting.
            pass

    def save(self) -> None:
        self.ensure_directories()
        tmp_path = self.config_path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp_path.replace(self.config_path)

    @property
    def selected_voice(self) -> str:
        return str(self.data.get("selected_voice", ""))

    @selected_voice.setter
    def selected_voice(self, value: str) -> None:
        self.data["selected_voice"] = value
        self.save()

    @property
    def safe_location(self) -> str:
        return str(self.data.get("safe_location", ""))

    @safe_location.setter
    def safe_location(self, value: str) -> None:
        self.data["safe_location"] = value
        self.save()

    @property
    def counter(self) -> int:
        try:
            return max(0, int(self.data.get("counter", 0)))
        except (TypeError, ValueError):
            return 0

    @counter.setter
    def counter(self, value: int) -> None:
        self.data["counter"] = max(0, int(value))
        self.save()

    def reserve_next_number(self, output_dir: str | Path) -> int:
        """
        Finds the highest Voiceover(N).mp3 in the output folder and config,
        then reserves the next number immediately.
        """
        directory = Path(output_dir)
        highest_on_disk = 0

        if directory.exists():
            for path in directory.glob("Voiceover(*).mp3"):
                name = path.stem
                if name.startswith("Voiceover(") and name.endswith(")"):
                    number_text = name[len("Voiceover("):-1]
                    if number_text.isdigit():
                        highest_on_disk = max(highest_on_disk, int(number_text))

        next_number = max(self.counter, highest_on_disk) + 1
        self.counter = next_number
        return next_number
