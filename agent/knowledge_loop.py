"""Small knowledge-tool loop used by an Agent or CLI integration."""
from __future__ import annotations

from knowledge.retrieval.knowledge_retriever import KnowledgeRetriever


class KnowledgeToolLoop:
    """Search manual knowledge before asking vision to inspect the image."""

    def __init__(self, retriever: KnowledgeRetriever | None = None, observer=None):
        self.retriever = retriever or KnowledgeRetriever()
        self.observer = observer

    def prepare(self, query: str, *, limit: int = 5) -> dict:
        return self.retriever.observation_plan(query, limit=limit).model_dump(mode="json")

    def observe(self, image, query: str, *, limit: int = 5, state: str = "any"):
        if self.observer is None:
            raise RuntimeError("未配置视觉观察器")
        return self.observer.observe(image, query, limit=limit, state=state)

