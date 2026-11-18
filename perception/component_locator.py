from pathlib import Path
from models.perception import LocateResult
from .target_knowledge import TargetKnowledge
from .vlm_client import Qwen3VLClient

class ComponentLocator:
    def __init__(self, client: Qwen3VLClient, target_knowledge: TargetKnowledge | None = None):
        self.client = client
        self.target_knowledge = target_knowledge or TargetKnowledge()

    def locate(self, image_path: str | Path, target: str, state: str = "any", context: str = "") -> LocateResult:
        target = self.target_knowledge.resolve(target)
        visual_description = self.target_knowledge.describe(target, state=state)
        merged_context = f"逻辑目标：{target}\n期望状态：{state}\n逻辑目标的设备视觉描述：{visual_description}"
        if context:
            merged_context += "\n补充上下文：" + context
        return self.client.locate(image_path, target, context=merged_context)
