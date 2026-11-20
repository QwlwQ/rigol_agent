"""Compile retrieved manual knowledge into a stepwise operation plan."""
from __future__ import annotations

import json
import re

from execution.capabilities import capability_for_request
from knowledge.retrieval.knowledge_retriever import KnowledgeRetriever
from knowledge.visual_knowledge import load_visual_knowledge
from models.operation import OperationPlan, OperationStep, StateExpectation


class OperationPlanner:
    def __init__(self, retriever: KnowledgeRetriever | None = None, llm=None):
        self.retriever = retriever or KnowledgeRetriever()
        self.llm = llm
        self.visual_knowledge = load_visual_knowledge()

    def plan(self, goal: str, context=None, *, use_llm: bool = True) -> OperationPlan:
        plan = self._compile(goal, context=context)
        if use_llm and self.llm is not None and hasattr(self.llm, "plan_operation"):
            return self.llm.plan_operation(self.prompt_messages(goal, plan))
        return plan

    def _compile(self, goal: str, context=None) -> OperationPlan:
        notice = capability_for_request(goal)
        if not notice.supported:
            return OperationPlan(
                goal=goal,
                operation="manual_completion",
                steps=[OperationStep(
                    step_id="manual-1", target=goal, action="manual",
                    instruction=notice.message,
                )],
                requires_manual_completion=True,
                notes=[notice.message],
            )

        observation_plan = self.retriever.observation_plan(goal)
        names = [item.target for item in observation_plan.targets]
        summaries = self.retriever.operation_summaries(goal)
        records = [record.id for record in summaries]
        steps: list[OperationStep] = []

        def add(target, instruction, expected=None, screen=None, condition=None, preconditions=None):
            expected_changes = []
            if expected or screen:
                expected_changes.append(StateExpectation(target=target, observed_state=expected, screen_state=screen))
            steps.append(OperationStep(
                step_id=f"step-{len(steps) + 1}", target=target, action="click",
                instruction=instruction, condition=condition,
                preconditions=preconditions or [],
                expected_changes=expected_changes, knowledge_record_ids=records,
            ))

        for target in names:
            if re.fullmatch(r"CH[1-4]", target, flags=re.I):
                add(target, f"仅当观察到 {target} 为 off 时点击通道卡片", expected="on", condition="observed_state == off", preconditions=[StateExpectation(target=target, observed_state="off")])
        if "Measure" in names:
            add("Measure", "点击测量入口", screen="measurement_panel")
        for category, screen in (("Vertical", "measurement_vertical"), ("Horizontal", "measurement_horizontal"), ("Other", "measurement_other")):
            if category in names:
                add(category, f"点击测量分类 {category}", screen=screen, preconditions=[StateExpectation(target="screen", screen_state="measurement_panel")])
        parameter_targets = {"Peak-to-Peak", "Maximum", "Minimum", "Amplitude", "Frequency", "Period", "Delay", "Delay(r-f)"}
        for target in names:
            if target in parameter_targets:
                add(target, f"点击测量项 {target}", expected="on", preconditions=[StateExpectation(target="screen", screen_state="measurement_vertical" if "Vertical" in names else "measurement_panel")])

        if not steps:
            target = names[0] if names else goal
            add(target, f"定位并点击目标组件 {target}")
        return OperationPlan(
            goal=goal,
            operation="measurement" if "Measure" in names else "device_operation",
            steps=steps,
            knowledge=summaries,
            notes=["每一步执行前重新观察当前图片；执行后按 expected_changes 验证。"],
        )

    @staticmethod
    def prompt_messages(goal: str, plan: OperationPlan):
        operation_hints = load_visual_knowledge().get("operations", {})
        return [
            {
                "role": "system",
                "content": (
                    "你是 Rigol DHO804 操作规划器。根据用户目标和精简后的说明书证据生成 OperationPlan。"
                    "只规划屏幕组件/物理按钮点击；旋钮旋转、插拔、接线必须 action=manual。"
                    "每个 click 步骤必须写 target、instruction、前置条件和 expected_changes。"
                    "不要输出 bbox；bbox 由视觉模型根据最新相机画面定位。"
                    "设备操作提示如下，必须遵守：" + json.dumps(operation_hints, ensure_ascii=False),
                ),
            },
            {"role": "user", "content": json.dumps({"goal": goal, "draft_plan": plan.model_dump(mode="json")}, ensure_ascii=False)},
        ]
