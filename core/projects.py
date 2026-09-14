from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def safe_project_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]+', "_", name.strip()).strip(". ")
    return name or "Projekt"


def project_path(projects_dir: Path, name: str) -> Path:
    return projects_dir / f"{safe_project_name(name)}.json"


def save_project(projects_dir: Path, name: str, payload: dict[str, Any]) -> Path:
    projects_dir.mkdir(parents=True, exist_ok=True)
    path = project_path(projects_dir, name)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_project(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
