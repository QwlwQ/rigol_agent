"""Minimal image validation for the Phase 1 file-based MVP."""
from pathlib import Path
from PIL import Image

def image_size(path: str | Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size
