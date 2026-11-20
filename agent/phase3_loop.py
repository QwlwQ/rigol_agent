"""Knowledge → LLM plan → per-step VLM → click → validation loop.

The loop accepts callbacks for image capture and clicking, so it can be used
with the existing touch-pen system without assuming a ROS2 message type.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from execution.action_dispatcher import TouchPenActionDispatcher
from execution.capabilities import MANUAL_COMPLETION_MESSAGE
from execution.state_validator import StateValidator
from models.operation import OperationPlan, OperationStep


@dataclass
class Phase3RunResult:
    status: str
    plan: OperationPlan
    completed_steps: int = 0
    message: str = ""
    observations: list[object] = field(default_factory=list)


class Phase3Loop:
    def __init__(self, planner, observer, *, dispatcher=None, validator=None):
        self.planner = planner
        self.observer = observer
        self.dispatcher = dispatcher or TouchPenActionDispatcher()
        self.validator = validator or StateValidator()

    def plan(self, goal: str) -> OperationPlan:
        return self.planner.plan(goal)

    def run(
        self,
        goal: str,
        *,
        image_provider: Callable[[], str | Path],
        click_executor: Callable[[dict], object],
        target_size: tuple[int, int],
    ) -> Phase3RunResult:
        plan = self.plan(goal)
        observations: list[object] = []
        completed = 0
        for step in plan.steps:
            if step.action == "manual":
                return Phase3RunResult("manual_required", plan, completed, step.instruction, observations)
            if step.action != "click":
                return Phase3RunResult("failed", plan, completed, f"暂不支持动作：{step.action}", observations)

            before_image = image_provider()
            before = self.observer.observe_step(before_image, step)
            observations.append(before)
            component = next((item for item in before.components if item.target.casefold() == step.target.casefold()), None)
            if component is None:
                return Phase3RunResult("failed", plan, completed, f"未定位到组件：{step.target}", observations)
            if not self._preconditions_met(step, before):
                # A conditional click, such as turning CH2 on, is already
                # satisfied when the component is not in the requested state.
                if step.condition and step.expected_changes and self._expected_present(step, before):
                    completed += 1
                    continue
                return Phase3RunResult("failed", plan, completed, f"前置状态不满足：{step.target}", observations)

            action = self.dispatcher.dispatch("click", component.bbox, image_size=before.image_size, target_size=target_size)
            click_executor(action)

            after_image = image_provider()
            expected_state = next((item.observed_state for item in step.expected_changes if item.observed_state), None)
            after = self.observer.observe_step(after_image, step, state=expected_state or "any")
            observations.append(after)
            if not self._expected_present(step, after):
                return Phase3RunResult("failed", plan, completed, f"操作后状态未达到预期：{step.target}", observations)
            completed += 1
        return Phase3RunResult("success", plan, completed, "操作完成", observations)

    def _preconditions_met(self, step: OperationStep, observation) -> bool:
        for expected in step.preconditions:
            if expected.target.casefold() == "screen":
                if expected.screen_state and observation.screen_state != expected.screen_state:
                    return False
                continue
            if expected.observed_state:
                if not any(item.target.casefold() == expected.target.casefold() and item.observed_state.casefold() == expected.observed_state.casefold() for item in observation.components):
                    return False
        return True

    @staticmethod
    def _expected_present(step: OperationStep, observation) -> bool:
        for expected in step.expected_changes:
            if expected.observed_state:
                if not any(item.target.casefold() == expected.target.casefold() and item.observed_state.casefold() == expected.observed_state.casefold() for item in observation.components):
                    return False
            if expected.screen_state and observation.screen_state != expected.screen_state:
                return False
        return True

