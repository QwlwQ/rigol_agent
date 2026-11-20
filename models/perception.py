from pydantic import BaseModel, ConfigDict, Field, model_validator
class VisionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
class BoundingBox(VisionModel):
    x_min: float = Field(ge=0); y_min: float = Field(ge=0); x_max: float = Field(ge=0); y_max: float = Field(ge=0)
    @model_validator(mode="before")
    @classmethod
    def accept_sequence(cls, value):
        if isinstance(value, (list, tuple)):
            if len(value) != 4:
                raise ValueError("bbox 必须包含四个坐标")
            return {"x_min": value[0], "y_min": value[1], "x_max": value[2], "y_max": value[3]}
        return value
    @model_validator(mode="after")
    def ordered(self):
        if self.x_max <= self.x_min or self.y_max <= self.y_min: raise ValueError("bbox 坐标顺序无效")
        return self
class VisionCandidate(VisionModel):
    target: str = Field(min_length=1); bbox: BoundingBox; confidence: float = Field(ge=0, le=1); evidence: list[str] = Field(default_factory=list); observed_state: str | None = None
class LocateResult(VisionModel):
    found: bool; target: str = Field(min_length=1); image_size: tuple[int, int] = (Field(ge=1), Field(ge=1)); candidates: list[VisionCandidate] = Field(default_factory=list); reason: str | None = None
    @model_validator(mode="after")
    def validate_result(self):
        width,height=self.image_size
        if width <= 0 or height <= 0:
            raise ValueError("image_size 必须为正数")
        for candidate in self.candidates:
            box=candidate.bbox
            if box.x_max > width or box.y_max > height: raise ValueError("bbox 超出原始图片范围")
        if self.found and not self.candidates: raise ValueError("found=true 时必须返回候选框")
        return self
