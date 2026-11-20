"""Load device-specific visual and prompt tuning data."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_visual_knowledge(path: str | Path | None = None) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    source = Path(path) if path else root / "data" / "knowledge" / "DHO804" / "visual_knowledge.yaml"
    if not source.is_file():
        return {}
    return yaml.safe_load(source.read_text(encoding="utf-8")) or {}

