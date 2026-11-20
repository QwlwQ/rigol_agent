"""Explicit image-coordinate conversion for robot adapters.

Vision results always use the original image pixels.  A robot camera or an
existing adapter may use a resized or cropped image, so conversion is kept in
one small, testable object instead of being hidden in a model prompt.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from models.perception import BoundingBox


@dataclass(frozen=True)
class CoordinateTransform:
    source_size: tuple[int, int]
    target_size: tuple[int, int]
    offset: tuple[float, float] = (0.0, 0.0)

    def __post_init__(self) -> None:
        if len(self.source_size) != 2 or len(self.target_size) != 2:
            raise ValueError("图像尺寸必须是(width, height)")
        if min(*self.source_size, *self.target_size) <= 0:
            raise ValueError("图像尺寸必须为正数")

    @property
    def scale(self) -> tuple[float, float]:
        return (self.target_size[0] / self.source_size[0], self.target_size[1] / self.source_size[1])

    def point(self, x: float, y: float) -> tuple[float, float]:
        sx, sy = self.scale
        return (x * sx + self.offset[0], y * sy + self.offset[1])

    def bbox(self, box: BoundingBox | Iterable[float]) -> BoundingBox:
        if not isinstance(box, BoundingBox):
            values = list(box)
            if len(values) != 4:
                raise ValueError("bbox 必须包含四个坐标")
            box = BoundingBox(x_min=values[0], y_min=values[1], x_max=values[2], y_max=values[3])
        x1, y1 = self.point(box.x_min, box.y_min)
        x2, y2 = self.point(box.x_max, box.y_max)
        return BoundingBox(x_min=x1, y_min=y1, x_max=x2, y_max=y2)

    def center(self, box: BoundingBox | Iterable[float]) -> tuple[float, float]:
        transformed = self.bbox(box)
        return ((transformed.x_min + transformed.x_max) / 2, (transformed.y_min + transformed.y_max) / 2)

