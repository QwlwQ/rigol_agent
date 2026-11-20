from knowledge.retrieval.knowledge_retriever import KnowledgeRetriever
from models.operation import OperationPlan
from models.operation import OperationStep, StateExpectation
from models.observation import Observation
from agent.phase3_loop import Phase3Loop
import httpx
from PIL import Image
from perception.vlm_client import Qwen3VLClient
from perception.target_knowledge import TargetKnowledge
from planning.operation_planner import OperationPlanner


def test_operation_plan_contains_stateful_click_steps():
    plan = OperationPlanner().plan("测量 CH2 的峰峰值", use_llm=False)
    assert isinstance(plan, OperationPlan)
    assert [step.target for step in plan.steps] == ["CH2", "Measure", "Vertical", "Peak-to-Peak"]
    assert plan.steps[0].condition == "observed_state == off"
    assert plan.steps[0].expected_changes[0].observed_state == "on"
    assert plan.steps[1].expected_changes[0].screen_state == "measurement_panel"
    assert {item.id for item in plan.knowledge} >= {"select_measurement_parameters", "peak_to_peak"}


def test_amplitude_is_a_distinct_vertical_measurement_target():
    plan = KnowledgeRetriever().observation_plan("测量当前通道的幅度值")
    assert [item.target for item in plan.targets] == ["Measure", "Vertical", "Amplitude"]


def test_chinese_channel_request_generates_channel_and_measure_targets():
    plan = KnowledgeRetriever().observation_plan("打开通道2,打开测量界面")
    assert [item.target for item in plan.targets] == ["CH2", "Measure"]


def test_unsupported_physical_operation_becomes_manual_step():
    plan = OperationPlanner().plan("旋转水平 SCALE 旋钮", use_llm=False)
    assert plan.requires_manual_completion is True
    assert plan.steps[0].action == "manual"
    assert "手动完成" in plan.steps[0].instruction


def test_operation_summaries_are_compact():
    summaries = KnowledgeRetriever().operation_summaries("测量 CH2 的峰峰值", limit=5)
    assert len(summaries) <= 5
    assert all(not item.source_pages or isinstance(item.source_pages[0], int) for item in summaries)
    assert all(len(item.description) <= 320 for item in summaries)


def test_phase3_loop_skips_already_satisfied_conditional_click():
    plan = OperationPlan(
        goal="打开 CH2", operation="device_operation", steps=[OperationStep(
            step_id="1", target="CH2", action="click", instruction="点击 CH2",
            condition="observed_state == off",
            preconditions=[StateExpectation(target="CH2", observed_state="off")],
            expected_changes=[StateExpectation(target="CH2", observed_state="on")],
        )],
    )

    class Planner:
        def plan(self, _):
            return plan

    class Observer:
        def observe_step(self, image, step, **kwargs):
            return Observation(image=str(image), image_size=(100, 80), components=[
                {"target": step.target, "bbox": [1, 1, 10, 10], "observed_state": "on", "confidence": 0.9}
            ])

    clicks = []
    result = Phase3Loop(Planner(), Observer()).run(
        "打开 CH2", image_provider=lambda: "current.jpg",
        click_executor=clicks.append, target_size=(100, 80),
    )
    assert result.status == "success"
    assert result.completed_steps == 1
    assert clicks == []


def test_qwen_common_1000_bbox_is_mapped_to_original_pixels(tmp_path, monkeypatch):
    image = tmp_path / "screen.jpg"
    Image.new("RGB", (1290, 810)).save(image)
    monkeypatch.delenv("QWEN_VL_COORDINATE_MODE", raising=False)

    def handler(_request):
        return httpx.Response(200, json={"choices": [{"message": {"content": (
            '{"found":true,"target":"Amplitude","image_size":[1290,810],'
            '"candidates":[{"bbox":[650,440,730,530],"confidence":0.9}]}'
        )}}]})

    client = Qwen3VLClient(api_key="test", base_url="http://test/v1", model="test", transport=httpx.MockTransport(handler))
    result = client.locate(image, "Amplitude")
    client.close()
    box = result.candidates[0].bbox
    assert round(box.x_min, 1) == 838.5
    assert round(box.x_max, 1) == 941.7


def test_visual_vocabulary_can_be_extended_in_yaml(tmp_path):
    path = tmp_path / "visual_knowledge.yaml"
    path.write_text(
        "targets:\n  CustomButton:\n    aliases: [自定义按钮]\n    visual_description: 找到自定义按钮\n",
        encoding="utf-8",
    )
    knowledge = TargetKnowledge(path=path, components_path=tmp_path / "missing.yaml")
    assert knowledge.resolve("自定义按钮") == "CustomButton"
    assert "找到自定义按钮" in knowledge.describe("CustomButton")

