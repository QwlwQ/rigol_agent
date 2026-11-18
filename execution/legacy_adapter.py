"""Convert internal Task objects to the original executor's taskList format."""
from pathlib import Path
import yaml
from models.planning import AgentError, Task

class LegacyTaskAdapter:
    def __init__(self, mapping_path=None, allow_provisional=False):
        if mapping_path is None:
            mapping_path = Path(__file__).resolve().parents[1] / "data" / "knowledge" / "legacy" / "tasklist_mapping.yaml"
        data = yaml.safe_load(Path(mapping_path).read_text(encoding="utf-8"))
        self.category_id = data["category_id"]
        self.category_name = data["category_name"]
        self.components = data["components"]
        self.allow_provisional = allow_provisional

    def convert(self, task: Task) -> dict:
        result = {"taskList": []}
        for subtask in task.tasks:
            for step in subtask.steps:
                if step.action != "click":
                    raise AgentError(f"旧执行器暂不支持动作：{step.action}")
                item = self.components.get(step.component)
                if not item:
                    raise AgentError(f"旧格式缺少组件映射：{step.component}")
                if item.get("provisional") and not self.allow_provisional:
                    raise AgentError(f"组件映射仍是临时值，不能导出：{step.component}")
                result["taskList"].append({
                    "angle": 0,
                    "category_id": self.category_id,
                    "name_id": item["name_id"],
                    "points": [],
                    "regex": "",
                    "targetName": f"{self.category_name}({self.category_id}):{item['target']}({item['name_id']})",
                    "taskName": item["task_name"],
                    "taskType": 0,
                    "useCord": 0,
                    "x": 0,
                    "y": 0,
                })
        return result
