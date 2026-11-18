"""Knowledge record schemas for future manual parsing and provenance."""
from pydantic import BaseModel, ConfigDict
class KnowledgeRecord(BaseModel):
    model_config=ConfigDict(extra="forbid")
    id: str
    verification_status: str = "unverified"
