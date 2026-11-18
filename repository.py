import json
from pathlib import Path
from models.planning import AgentError, Status, Task
class TaskRepository:
 def __init__(self, root="data/tasks"): self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
 def save(self, task):
  task=Task.model_validate(task.model_dump()); task.status=Status.VALIDATED
  path=self.root/f"{task.task_name}_{str(task.task_id)[:8]}.json"
  path.write_text(json.dumps(task.model_dump(mode="json"),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
  loaded=Task.model_validate_json(path.read_text(encoding="utf-8"))
  return path,loaded
 def load(self,path):
  try: return Task.model_validate_json(Path(path).read_text(encoding="utf-8"))
  except (OSError,ValueError) as e: raise AgentError("任务文件读取或 Schema 校验失败") from e
