"""Structured observations shared by knowledge, vision, and execution layers."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .perception import BoundingBox


ScreenState = Literal[
    "main_screen",
    "measurement_panel",
    "measurement_vertical",
    "measurement_horizontal",
    "measurement_other",
    "unknown",
]


class ScreenRecognition(BaseModel):
    """VLM classification of the current interface, independent of a target."""

    model_config = ConfigDict(extra="forbid")

    screen_state: ScreenState = "unknown"
    confidence: float = Field(ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)
    visible_components: list[str] = Field(default_factory=list)
    reason: str | None = None


class ObservationComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str = Field(min_length=1)
    bbox: BoundingBox
    observed_state: str = "unknown"
    confidence: float = Field(ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)
    source_record_ids: list[str] = Field(default_factory=list)


class Observation(BaseModel):
    """One image observation in the original image coordinate system."""

    model_config = ConfigDict(extra="forbid")

    image: str = Field(min_length=1)
    screen_state: ScreenState = "unknown"
    coordinate_space: Literal["original_image"] = "original_image"
    image_size: tuple[int, int] = (Field(ge=1), Field(ge=1))
    components: list[ObservationComponent] = Field(default_factory=list)
    required_observations: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_boxes(self) -> "Observation":
        width, height = self.image_size
        if width <= 0 or height <= 0:
            raise ValueError("image_size 必须为正数")
        for component in self.components:
            box = component.bbox
            if box.x_max > width or box.y_max > height:
                raise ValueError("观察组件 bbox 超出原始图片范围")
        return self


# A descriptive alias makes call sites read naturally while retaining one schema.
ObservationResult = Observation

