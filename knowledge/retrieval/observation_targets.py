"""Turn manual search results and user wording into visual targets."""
from __future__ import annotations

import re
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field

from knowledge.schemas import KnowledgeRecord


class ObservationTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str = Field(min_length=1)
    state: str = "any"
    description: str = ""
    source_record_ids: list[str] = Field(default_factory=list)


class ObservationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    records: list[KnowledgeRecord] = Field(default_factory=list)
    targets: list[ObservationTarget] = Field(default_factory=list)


_TARGET_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"峰峰值|峰-峰|peak\s*to\s*peak|p-p", "Peak-to-Peak"),
    (r"最大值|maximum|max\b", "Maximum"),
    (r"最小值|minimum|min\b", "Minimum"),
    (r"幅度值|amplitude", "Amplitude"),
    (r"频率|frequency", "Frequency"),
    (r"周期|period", "Period"),
    (r"延迟\s*\(?r\s*[-到]\s*f\)?|delay\s*\(?r[- ]f\)?", "Delay(r-f)"),
    (r"延迟|delay", "Delay"),
)


def _record_targets(record: KnowledgeRecord) -> list[str]:
    """Read explicit observation/component hints when an extractor provides them."""
    values: list[str] = []
    data: dict[str, Any] = record.data or {}
    for key, value in data.items():
        normalized = key.casefold().replace("-", "_")
        if normalized not in {"required_observation", "required_observations", "required_component", "required_components", "observation_targets"}:
            continue
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, (list, tuple)):
            values.extend(str(item) for item in value if isinstance(item, (str, int, float)))
    return values


def build_observation_plan(query: str, records: Iterable[KnowledgeRecord]) -> ObservationPlan:
    records = list(records)
    record_ids = [record.id for record in records]
    targets: list[ObservationTarget] = []

    def add(target: str, description: str = "") -> None:
        if not target or any(item.target.casefold() == target.casefold() for item in targets):
            return
        targets.append(ObservationTarget(target=target, description=description, source_record_ids=record_ids))

    # Explicit extracted hints have priority over heuristics.
    for record in records:
        for value in _record_targets(record):
            add(value, record.description)

    text = str(query or "")
    channels = re.findall(r"\bCH\s*([1-4])\b|通道\s*([1-4])|第\s*([一二三四1-4])\s*通道", text, flags=re.I)
    chinese_channels = {"一": "1", "二": "2", "三": "3", "四": "4"}
    for match in channels:
        channel = next((item for item in match if item), "")
        channel = chinese_channels.get(channel, channel)
        add(f"CH{channel}", "示波器模拟通道控制卡片")
    if re.search(r"测量|measure|measurement", text, flags=re.I):
        add("Measure", "测量面板入口或测量按钮")
    category = None
    if re.search(r"垂直|vertical", text, flags=re.I):
        category = "Vertical"
    elif re.search(r"水平|horizontal", text, flags=re.I):
        category = "Horizontal"
    elif re.search(r"其它|其他|other", text, flags=re.I):
        category = "Other"
    # A parameter's category is present in the retrieved manual data even if
    # the user only names the parameter (for example ``峰峰值``).
    if category is None:
        if re.search(r"峰峰值|最大值|最小值|顶端值|底端值|幅度值|平均值|有效值|过冲|预冲|面积", text, re.I):
            category = "Vertical"
        elif re.search(r"频率|周期|上升时间|下降时间|脉宽|占空比|frequency|period", text, re.I):
            category = "Horizontal"
        elif re.search(r"延迟|相位|delay|phase|上升沿到下降沿", text, re.I):
            category = "Other"
    if category is None:
        for record in records:
            blob = f"{record.name} {record.description} {record.data}" 
            if "垂直" in blob and any(re.search(pattern, text, re.I) for pattern, _ in _TARGET_PATTERNS):
                category = "Vertical"
                break
            if "水平" in blob and re.search(r"频率|周期|frequency|period", text, re.I):
                category = "Horizontal"
                break
    if category:
        add(category, "测量面板分类标签")
    if re.search(r"上升沿到下降沿|上升沿.*下降沿", text, re.I):
        add("Delay(r-f)", "其它测量参数项：上升沿到下降沿")
    for pattern, label in _TARGET_PATTERNS:
        if label == "Delay" and any(item.target == "Delay(r-f)" for item in targets):
            continue
        if re.search(pattern, text, flags=re.I):
            add(label, "测量参数项")

    # If the query is a generic operation, keep the retrieved operation's
    # target/name available to the VLM rather than returning no targets.
    if not targets:
        for record in records:
            add(record.name or record.id, record.description)
    return ObservationPlan(query=text, records=records, targets=targets)

