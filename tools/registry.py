from dataclasses import dataclass
from typing import Any, Callable
from models.planning import AgentError
@dataclass(frozen=True)
class Tool:
 name:str; description:str; parameters:dict; handler:Callable[...,Any]; requires_confirmation:bool=False
 def schema(self): return {"type":"function","function":{"name":self.name,"description":self.description,"parameters":self.parameters,"strict":True}}
class ToolRegistry:
 def __init__(self): self._tools={}
 def register(self,tool):
  if tool.name in self._tools: raise AgentError("工具重复注册："+tool.name)
  self._tools[tool.name]=tool
 def get(self,name):
  if name not in self._tools: raise AgentError("未知工具："+name)
  return self._tools[name]
 def schemas(self): return [t.schema() for t in self._tools.values()]
 def call(self,name,arguments): return self.get(name).handler(**arguments)
def create_registry(planner,validator,repository,adapter=None,executor=None,observer=None):
 r=ToolRegistry()
 r.register(Tool("create_task","根据已解析提案展开任务模板",{"type":"object","properties":{"proposal":{"type":"object"}},"required":["proposal"]},lambda proposal: planner.build(proposal)))
 r.register(Tool("validate_task","验证任务 Schema、组件、动作、顺序和约束",{"type":"object","properties":{"task":{"type":"object"}},"required":["task"]},lambda task: validator.validate(task)))
 r.register(Tool("save_task","验证后保存任务文件",{"type":"object","properties":{"task":{"type":"object"}},"required":["task"]},lambda task: repository.save(validator.validate(task)),requires_confirmation=True))
 if adapter:
  r.register(Tool("export_legacy_task","将已验证任务转换为 Qt/视觉系统 taskList JSON",{"type":"object","properties":{"task":{"type":"object"}},"required":["task"]},lambda task: adapter.convert(validator.validate(task))))
 if adapter and executor:
  r.register(Tool("execute_task","通过 ROS2 顺序执行已验证的点击任务并等待闭环反馈",{"type":"object","properties":{"task":{"type":"object"}},"required":["task"]},lambda task: executor.execute(adapter.convert(validator.validate(task))),requires_confirmation=True))
 if observer:
  r.register(Tool("observe_screen","读取当前画面中的组件、像素位置和相机三维点，不触发动作",{"type":"object","properties":{},"required":[]},lambda: observer.observe()))
 return r
