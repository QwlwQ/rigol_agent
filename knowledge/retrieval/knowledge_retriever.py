"""Keyword retrieval over the extracted manual records.

The repository deliberately stays file based for this phase.  This retriever
adds Chinese text handling and a small knowledge-to-observation bridge so the
vision prompt can be driven by retrieved records without inventing fixed
workflows.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

from knowledge.manual_repository import ManualKnowledgeRepository
from knowledge.schemas import KnowledgeRecord
from models.operation import KnowledgeSummary
from .observation_targets import ObservationPlan, ObservationTarget, build_observation_plan


class KnowledgeRetriever:
    def __init__(self, repository=None):
        self.repository = repository or ManualKnowledgeRepository()

    def search(self, query, *, record_type=None, chapter_id=None, limit=10):
        return self.repository.search(query, record_type=record_type, chapter_id=chapter_id, limit=limit)

    def records(self, query, *, record_type=None, chapter_id=None, limit=10) -> list[KnowledgeRecord]:
        return [KnowledgeRecord.model_validate(item) for item in self.search(query, record_type=record_type, chapter_id=chapter_id, limit=limit)]

    def observation_plan(self, query: str, *, record_type: str | None = "operation", limit: int = 5) -> ObservationPlan:
        records = self.records(query, record_type=record_type, limit=limit)
        # An operation often refers to a parameter defined by a separate
        # function record (for example ``峰峰值``).  Add only a few semantic
        # neighbours so the VLM receives the definition and its provenance.
        supplements: list[KnowledgeRecord] = []
        for phrase in re.findall(r"CH\s*[1-4]|峰峰值|最大值|最小值|幅度值|频率|周期|延迟(?:\([^)]*\))?", query, re.I):
            for record in self._semantic_matches(phrase, limit=2):
                if record.id not in {item.id for item in records + supplements}:
                    supplements.append(record)
        records.extend(supplements[: max(0, limit)])
        return build_observation_plan(query, records)

    def _semantic_matches(self, phrase: str, *, limit: int = 2) -> list[KnowledgeRecord]:
        phrase = phrase.casefold()
        priority = {"function": 0, "component": 1, "state": 2, "operation": 3, "workflow": 4, "parameter": 5}
        matches = []
        for raw in self.repository.all():
            semantic = " ".join(str(raw.get(key, "")) for key in ("name", "description", "data")).casefold()
            if phrase not in semantic:
                continue
            record = KnowledgeRecord.model_validate(raw)
            exact_name = phrase in str(raw.get("name", "")).casefold()
            matches.append((0 if exact_name else 1, priority.get(record.record_type, 9), -(record.confidence or 0), record))
        matches.sort(key=lambda item: item[:3])
        return [item[3] for item in matches[:limit]]

    def required_observations(self, query: str, *, record_type: str | None = "operation", limit: int = 5) -> list[ObservationTarget]:
        return self.observation_plan(query, record_type=record_type, limit=limit).targets

    def operation_summaries(self, query: str, *, limit: int = 5) -> list[KnowledgeSummary]:
        """Return compact evidence for an LLM prompt, without page payloads."""
        plan = self.observation_plan(query, record_type="operation", limit=limit)
        operations = [record for record in plan.records if record.record_type == "operation"]
        supplements = [record for record in plan.records if record.record_type != "operation"]
        # Keep the operation path, then include the most relevant function or
        # parameter definition instead of unrelated source/channel matches.
        query_text = query.casefold()
        supplements.sort(key=lambda record: (
            0 if any(term in f"{record.id} {record.name} {record.description} {record.data}".casefold() for term in re.findall(r"峰峰值|频率|周期|延迟|相位|最大值|最小值|幅度值", query_text)) else 1,
            -(record.confidence or 0),
        ))
        selected = (operations[: max(1, limit - 2)] + supplements[:2])[:limit]
        return [KnowledgeSummary(
            id=record.id,
            record_type=record.record_type,
            name=record.name,
            description=record.description[:320],
            data=self._compact_data(record.data),
            source_pages=record.source_pages or record.pages,
            confidence=record.confidence,
        ) for record in selected]

    @staticmethod
    def _compact_data(data: dict) -> dict:
        """Keep useful operation parameters while dropping source-heavy blobs."""
        result = {}
        for key, value in (data or {}).items():
            if key.casefold() in {"source", "source_text", "source_tables", "source_images", "page_context_images"}:
                continue
            text = str(value)
            result[key] = value if len(text) <= 280 else text[:277] + "..."
        return result
