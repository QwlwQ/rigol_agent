from .conversation import Conversation
import json
from pathlib import Path
from .models import AgentError, Clarification, Task
class Agent:
 def __init__(self,planner,validator,repository,conversation=None): self.planner=planner; self.validator=validator; self.repository=repository; self.conversation=conversation or Conversation(); self.pending=None
 def handle(self,text,save=False):
  self.conversation.add("user",text)
  try:
   proposal=self.planner.parse(text,self.conversation.model_messages()[:-1]); task=self.validator.validate(self.planner.build(proposal)); self.pending=task
   lines=[f"我理解你的需求：{task.description or task.task_name}","","计划操作："]
   i=1
   for sub in task.tasks:
    lines.append(f"[{sub.task_name}]")
    for step in sub.steps: lines.append(f"{i}. {step.action} {step.component}"); i+=1
   if save:
    path,task=self.repository.save(task); lines += ["",f"任务已保存：{path}"]
   else: lines += ["","输入“保存”以写入任务文件。"]
   answer="\n".join(lines); self.conversation.add("assistant",answer); return answer
  except Clarification as e: self.pending=e.proposal; return str(e)
  except AgentError as e: return f"无法创建任务：{e}"
 def _pending_task(self):
  if isinstance(self.pending,Task): return self.validator.validate(self.pending)
  return self.validator.validate(self.planner.build(self.pending))
 def save_pending(self):
  if not self.pending: return "当前没有待保存任务。"
  try:
   task=self._pending_task(); path,_=self.repository.save(task); return f"任务已保存：{path}（仍可继续导出或执行）"
  except AgentError as e: return f"无法保存任务：{e}"
 def export_pending(self,adapter,root="data/legacy_tasks"):
  if not self.pending: return "当前没有待导出任务。"
  try:
   task=self._pending_task(); payload=adapter.convert(task)
   directory=Path(root); directory.mkdir(parents=True,exist_ok=True)
   path=directory/f"{task.task_name}_{str(task.task_id)[:8]}_legacy.json"
   path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
   return f"旧系统任务已导出：{path}"
  except (AgentError,OSError) as e: return f"无法导出任务：{e}"
 def execute_pending(self,adapter,executor,progress=None,status=None):
  if not self.pending: return "当前没有待执行任务。"
  try:
   task=self._pending_task(); payload=adapter.convert(task)
   result=executor.execute(payload,progress=progress,status=status)
   self.pending=None
   return f"任务执行完成：{result.completed_steps}/{result.total_steps} 步"
  except AgentError as e: return f"无法执行任务：{e}"
