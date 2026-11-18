from enum import Enum
from typing import Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field
class Model(BaseModel): model_config=ConfigDict(extra="forbid")
class Status(str,Enum):
    CREATED="CREATED"; VALIDATED="VALIDATED"; CONFIRMED="CONFIRMED"; RUNNING="RUNNING"; SUCCESS="SUCCESS"; FAILED="FAILED"; CANCELLED="CANCELLED"
class Step(Model): component:str=Field(min_length=1); action:str=Field(min_length=1)
class Intent(Model):
    workflow:str|None=None; parameters:dict[str,str]=Field(default_factory=dict); steps:list[Step]|None=None
    @property
    def is_dynamic(self): return self.workflow=="dynamic_steps" or self.steps is not None
class Proposal(Model): task_name:str=Field(min_length=1,max_length=120); description:str=""; tasks:list[Intent]=Field(min_length=1,max_length=64)
class Subtask(Model): task_name:str; workflow:str; parameters:dict[str,str]; steps:list[Step]=Field(min_length=1)
class Task(Model):
    schema_version:Literal["1.0"]="1.0"; task_id:UUID=Field(default_factory=uuid4); task_name:str=Field(min_length=1,max_length=120); description:str=""; knowledge_profile:str; knowledge_digest:str; status:Status=Status.CREATED; tasks:list[Subtask]=Field(min_length=1,max_length=64)
class AgentError(ValueError): pass
class Clarification(AgentError):
    def __init__(self,message,proposal): super().__init__(message); self.proposal=proposal
