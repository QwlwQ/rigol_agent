"""Knowledge-driven visual observation for one current image."""
from __future__ import annotations

from pathlib import Path

from knowledge.retrieval.knowledge_retriever import KnowledgeRetriever
from models.observation import Observation, ObservationComponent, ScreenRecognition


class KnowledgeDrivenObserver:
    """Retrieve the operation context, then ask the locator for each target.

    This class performs observation only.  It does not click, rotate, retry, or
    hand an unverified coordinate to a robot adapter.
    """

    def __init__(self, locator, retriever: KnowledgeRetriever | None = None):
        self.locator = locator
        self.retriever = retriever or KnowledgeRetriever()

    def plan(self, query: str, *, limit: int = 5):
        return self.retriever.observation_plan(query, limit=limit)

    def observe(self, image: str | Path, query: str, *, state: str = "any", limit: int = 5, context: str = "") -> Observation:
        plan = self.plan(query, limit=limit)
        path = Path(image)
        # The locator validates existence and reads the original dimensions;
        # this read keeps the observation object useful with fake locators too.
        image_size = self._image_size(path)
        components: list[ObservationComponent] = []
        reasons: list[str] = []
        screen_result = self._recognize_screen(path, context=context)
        for target in plan.targets:
            result = self.locator.locate(path, target.target, state=state if state != "any" else target.state, context=self._context(plan, target, context))
            if getattr(result, "image_size", None):
                image_size = tuple(result.image_size)
            for candidate in result.candidates:
                components.append(ObservationComponent(
                    target=candidate.target,
                    bbox=candidate.bbox,
                    observed_state=candidate.observed_state or "unknown",
                    confidence=candidate.confidence,
                    evidence=candidate.evidence,
                    source_record_ids=target.source_record_ids,
                ))
            if not result.found and result.reason:
                reasons.append(f"{target.target}: {result.reason}")
        return Observation(
            image=str(image),
            image_size=image_size,
            screen_state=screen_result.screen_state if screen_result else self._screen_state(plan),
            components=components,
            required_observations=[target.target for target in plan.targets],
            confidence=min((item.confidence for item in components), default=None),
            reason="；".join(reasons) if reasons else None,
            metadata={
                "knowledge_record_ids": [record.id for record in plan.records],
                "screen_evidence": screen_result.model_dump(mode="json") if screen_result else {},
            },
        )

    def observe_step(self, image: str | Path, step, *, state: str = "any") -> Observation:
        """Observe exactly one planned step target on the latest image."""
        path = Path(image)
        # Preconditions describe how the LLM should interpret the observation;
        # they must not hide an already-satisfied state from the VLM.  Initial
        # step observations therefore remain unconstrained unless the caller
        # explicitly asks for a verification state.
        result = self.locator.locate(path, step.target, state=state, context=getattr(step, "visual_target_description", getattr(step, "instruction", "")))
        image_size = tuple(result.image_size)
        components = [ObservationComponent(
            target=candidate.target,
            bbox=candidate.bbox,
            observed_state=candidate.observed_state or "unknown",
            confidence=candidate.confidence,
            evidence=candidate.evidence,
        ) for candidate in result.candidates]
        screen_result = self._recognize_screen(path, context=getattr(step, "instruction", ""))
        return Observation(
            image=str(image), image_size=image_size,
            screen_state=screen_result.screen_state if screen_result else self._screen_state_for_target(step.target), components=components,
            required_observations=[step.target],
            confidence=min((item.confidence for item in components), default=None),
            reason=result.reason,
            metadata={"screen_evidence": screen_result.model_dump(mode="json") if screen_result else {}},
        )

    def _recognize_screen(self, path: Path, *, context: str = "") -> ScreenRecognition | None:
        client = getattr(self.locator, "client", None)
        recognize = getattr(client, "recognize_screen", None)
        if recognize is None:
            return None
        try:
            knowledge = getattr(self.locator, "target_knowledge", None)
            configured = knowledge.screen_prompt() if knowledge is not None and hasattr(knowledge, "screen_prompt") else ""
            merged = "\n".join(item for item in (configured, context) if item)
            return recognize(path, context=merged)
        except Exception:
            # A screen-state failure must not discard a valid component bbox.
            return None

    @staticmethod
    def _screen_state_for_target(target: str) -> str:
        return {
            "Measure": "measurement_panel",
            "Vertical": "measurement_vertical",
            "Horizontal": "measurement_horizontal",
            "Other": "measurement_other",
        }.get(str(target), "unknown")

    @staticmethod
    def _image_size(path: Path) -> tuple[int, int]:
        try:
            from PIL import Image
            with Image.open(path) as image:
                return image.size
        except (OSError, ValueError):
            # A fake locator can return a fully formed result in tests; a real
            # locator will produce a more specific missing-image error.
            return (1, 1)

    @staticmethod
    def _screen_state(plan, ) -> str:
        targets = {target.target.casefold() for target in plan.targets}
        if "vertical" in targets:
            return "measurement_vertical"
        if "horizontal" in targets:
            return "measurement_horizontal"
        if "other" in targets:
            return "measurement_other"
        if "measure" in targets:
            return "measurement_panel"
        return "unknown"

    @staticmethod
    def _context(plan, target, extra: str) -> str:
        target_text = target.target.casefold()
        snippets = []
        for record in plan.records:
            record_text = f"{record.id} {record.name} {record.description} {record.data}".casefold()
            if target_text in record_text and record.description:
                snippets.append(record.description)
        context = "相关说明书知识：" + "；".join(snippets[:2]) if snippets else ""
        if target.description:
            context += "\n目标说明：" + target.description
        if extra:
            context += "\n" + extra
        return context

