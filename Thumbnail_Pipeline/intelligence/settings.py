from __future__ import annotations
import json
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "intelligence.json"

def load_settings(path: Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else CONFIG_PATH
    value = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("intelligence config must be an object")
    return value
