from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

APP_NAME = "ChatterboxDesktopApp"


class SettingsManager:
    """Persistent application data under %APPDATA%/ChatterboxDesktopApp."""

    def __init__(self) -> None:
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        self.base_dir = Path(appdata) / APP_NAME
        self.config_path = self.base_dir / "config.json"
        self.voices_dir = self.base_dir / "voices"
        self.projects_dir = self.base_dir / "projects"
        self.history_path = self.base_dir / "history.json"
        self.data: dict[str, Any] = {
            "selected_voice": "",
            "safe_location": "",
            "counter": 0,
            "exaggeration": 50,
            "cfg_weight": 50,
            "speed": 100,
            "favorite_voices": [],
        }
        self.load()

    def ensure_directories(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> None:
        self.ensure_directories()
        if not self.config_path.exists():
            return
        try:
            loaded = json.loads(self.config_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self.data.update(loaded)
        except (OSError, json.JSONDecodeError):
            pass

    def save(self) -> None:
        self.ensure_directories()
        tmp_path = self.config_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
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
    def favorite_voices(self) -> list[str]:
        value = self.data.get("favorite_voices", [])
        return [str(x) for x in value] if isinstance(value, list) else []

    def toggle_favorite(self, path: str) -> None:
        favorites = self.favorite_voices
        if path in favorites:
            favorites.remove(path)
        else:
            favorites.append(path)
        self.data["favorite_voices"] = favorites
        self.save()

    def is_favorite(self, path: str) -> bool:
        return path in self.favorite_voices

    def remove_favorite(self, path: str) -> None:
        favorites = self.favorite_voices
        if path in favorites:
            favorites.remove(path)
            self.data["favorite_voices"] = favorites
            self.save()

    def get_slider_value(self, key: str, default: int) -> int:
        try:
            return max(0, min(200, int(self.data.get(key, default))))
        except (TypeError, ValueError):
            return default

    def set_slider_value(self, key: str, value: int) -> None:
        self.data[key] = int(value)
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

    def load_history(self) -> list[dict[str, Any]]:
        if not self.history_path.exists():
            return []
        try:
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def save_history(self, history: list[dict[str, Any]]) -> None:
        self.ensure_directories()
        self.history_path.write_text(json.dumps(history[-100:], indent=2, ensure_ascii=False), encoding="utf-8")
