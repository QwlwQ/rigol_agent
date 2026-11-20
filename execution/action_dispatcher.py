"""Action dispatch boundary for a touch-pen robot.

This prepares a transformed click point for an existing robot adapter.  It
does not send hardware commands, and deliberately leaves knob/cable skills as
an explicit manual-completion placeholder.
"""
from __future__ import annotations

from models.perception import BoundingBox
from perception.coordinates import CoordinateTransform
from .capabilities import MANUAL_COMPLETION_MESSAGE, UnsupportedCapabilityError, ensure_action_supported


class ActionDispatcher:
    def dispatch(self, action, target):
        raise NotImplementedError


class TouchPenActionDispatcher(ActionDispatcher):
    def __init__(self, transform: CoordinateTransform | None = None):
        self.transform = transform

    def dispatch(self, action: str, target: BoundingBox | dict, *, image_size=None, target_size=None):
        ensure_action_supported(action)
        if isinstance(target, BoundingBox):
            box = target
        elif isinstance(target, (list, tuple)):
            if len(target) != 4:
                raise ValueError("bbox 必须包含四个坐标")
            box = BoundingBox(x_min=target[0], y_min=target[1], x_max=target[2], y_max=target[3])
        else:
            box = BoundingBox.model_validate(target)
        transform = self.transform
        if transform is None:
            if image_size is None or target_size is None:
                raise ValueError("坐标点击需要提供 image_size 和 target_size，避免把原图坐标误传给机械臂")
            transform = CoordinateTransform(tuple(image_size), tuple(target_size))
        transformed = transform.bbox(box)
        center = transform.center(box)
        return {
            "action": "click",
            "bbox": transformed.model_dump(),
            "point": {"x": center[0], "y": center[1]},
            "coordinate_space": "robot_image",
        }
