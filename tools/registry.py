"""Small registry for the active Phase 3 knowledge and observation tools."""
from dataclasses import dataclass
from typing import Any, Callable

from models.errors import AgentError


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Callable[..., Any]

    def schema(self):
        return {"type": "function", "function": {"name": self.name, "description": self.description, "parameters": self.parameters, "strict": True}}


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise AgentError("工具重复注册：" + tool.name)
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise AgentError("未知工具：" + name)
        return self._tools[name]

    def schemas(self) -> list[dict]:
        return [tool.schema() for tool in self._tools.values()]

    def call(self, name: str, arguments: dict):
        return self.get(name).handler(**arguments)


def register_phase3_tools(*, retriever=None, observer=None, operation_planner=None) -> ToolRegistry:
    """Create only the tools used by the current knowledge/vision pipeline."""
    registry = ToolRegistry()
    if retriever is not None:
        registry.register(Tool(
            "search_knowledge", "检索 DHO804 说明书知识摘要",
            {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 20}}, "required": ["query", "limit"]},
            lambda query, limit=5: retriever.operation_summaries(query, limit=limit),
        ))
        if hasattr(retriever, "observation_plan"):
            registry.register(Tool(
                "plan_observation", "把用户目标转换成视觉观察目标",
                {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 20}}, "required": ["query", "limit"]},
                lambda query, limit=5: retriever.observation_plan(query, limit=limit).model_dump(mode="json"),
            ))
    if operation_planner is not None:
        registry.register(Tool(
            "plan_operation", "根据用户目标生成分步操作计划，不生成 bbox",
            {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            lambda query: operation_planner.plan(query).model_dump(mode="json"),
        ))
    if observer is not None:
        registry.register(Tool(
            "observe_screen", "读取当前图片的界面状态和目标组件，不触发动作",
            {"type": "object", "properties": {"image": {"type": "string"}, "query": {"type": "string"}}, "required": ["image", "query"]},
            lambda image, query: observer.observe(image, query).model_dump(mode="json"),
        ))
    return registry
