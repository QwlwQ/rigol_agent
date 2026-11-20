"""Schemas for records extracted from the instrument manual.

The extractor intentionally keeps the source payload intact.  The fields below
cover the stable envelope used by the current JSONL export while ``data`` and
the provenance collections remain open to additions made by later extraction
runs.
"""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    record_type: str = "unknown"
    id: str
    name: str = ""
    description: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    chapter_id: str | None = None
    chapter_title: str | None = None
    source_refs: list[str] = Field(default_factory=list)
    source_pages: list[int] = Field(default_factory=list)
    pages: list[int] = Field(default_factory=list)
    source_text: list[Any] | str = Field(default_factory=list)
    source_tables: list[Any] = Field(default_factory=list)
    source_images: list[Any] = Field(default_factory=list)
    page_context_images: list[Any] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    verification_status: str = "unverified"

    @property
    def provenance(self) -> dict[str, Any]:
        """Return only source metadata, useful when building a vision prompt."""
        return {
            "source_refs": self.source_refs,
            "source_pages": self.source_pages or self.pages,
            "chapter_id": self.chapter_id,
            "chapter_title": self.chapter_title,
            "verification_status": self.verification_status,
        }

    @property
    def required_observations(self) -> list[str]:
        """Return explicit observation hints when an extractor supplied them."""
        values: list[str] = []
        for key, value in self.data.items():
            if not any(token in key.casefold().replace("-", "_") for token in ("required_observation", "required_component")):
                continue
            if isinstance(value, str):
                values.append(value)
            elif isinstance(value, (list, tuple)):
                values.extend(str(item) for item in value)
        return values
