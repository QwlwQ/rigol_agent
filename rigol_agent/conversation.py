from dataclasses import dataclass,field
@dataclass
class Conversation:
 messages:list[dict]=field(default_factory=list)
 def add(self,role,content): self.messages.append({"role":role,"content":content})
 def model_messages(self,limit=12): return self.messages[-limit:]
