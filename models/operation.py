"""Compact operation plans exchanged between the LLM, VLM, and executor."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StateExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str = Field(min_length=1)
    observed_state: str | None = None
    screen_state: str | None = None


class KnowledgeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    record_type: str
    name: str = ""
    description: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    source_pages: list[int] = Field(default_factory=list)
    confidence: float | None = None


class OperationStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(min_length=1)
    target: str = Field(min_length=1)
    action: Literal["click", "manual", "observe"]
    instruction: str = Field(min_length=1)
    condition: str | None = None
    preconditions: list[StateExpectation] = Field(default_factory=list)
    expected_changes: list[StateExpectation] = Field(default_factory=list)
    knowledge_record_ids: list[str] = Field(default_factory=list)

    @property
    def visual_target_description(self) -> str:
        """Text passed to the VLM for this step only."""
        return self.instruction


class OperationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    steps: list[OperationStep] = Field(min_length=1)
    knowledge: list[KnowledgeSummary] = Field(default_factory=list)
    requires_manual_completion: bool = False
    notes: list[str] = Field(default_factory=list)

