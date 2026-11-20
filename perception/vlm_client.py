"""Alibaba Model Studio Qwen3-VL OpenAI-compatible HTTP adapter."""
import base64
import json
import mimetypes
import os
import re
from pathlib import Path
import httpx
from PIL import Image
from models.perception import LocateResult
from models.observation import ScreenRecognition

class VisionClientError(RuntimeError):
    pass


def _load_project_env() -> None:
    """Load a local .env when python-dotenv is not installed.

    The project lists python-dotenv as a dependency, but the current runtime
    may execute directly from the system interpreter.  Values already present
    in the process always win.
    """
    try:
        from dotenv import load_dotenv
        load_dotenv()
        return
    except ImportError:
        pass
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value

def _content_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts)
    return ""

def _json_payload(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    # Some vision responses contain an accidental numeric/markdown key inside
    # an otherwise usable JSON object. Remove only that non-schema noise.
    text = text.replace("`", "")
    text = re.sub(r'"[\s"]+(x_min|y_min|x_max|y_max)"', r'"\1"', text)
    text = re.sub(r',?\s*[" ]+\d+[" ]*\s*:\s*0\s*,?', ',', text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for index, char in enumerate(text):
            if char == "{":
                try:
                    value, _ = decoder.raw_decode(text[index:])
                    return value
                except json.JSONDecodeError:
                    continue
    raise ValueError("响应中没有 JSON 对象")

def _normalize_payload(raw, target, width, height):
    if not isinstance(raw, dict):
        raise ValueError("定位响应不是 JSON 对象")
    candidates = raw.get("candidates")
    if candidates is None:
        candidates = raw.get("results", [])
    if isinstance(candidates, dict):
        candidates = [candidates]
    if not candidates and isinstance(raw.get("bbox"), list):
        candidates = [{"target": target, "bbox": raw["bbox"], "confidence": raw.get("confidence", 0.0), "evidence": raw.get("evidence", [])}]
    normalized = []
    for candidate in candidates or []:
        if not isinstance(candidate, dict):
            continue
        box = candidate.get("bbox", candidate.get("box"))
        if isinstance(box, list) and len(box) == 4:
            box = {"x_min": box[0], "y_min": box[1], "x_max": box[2], "y_max": box[3]}
        elif isinstance(box, dict):
            aliases = {
                "x_min": ("x_min", "xmin", "x1", "left"),
                "y_min": ("y_min", "ymin", "y1", "top"),
                "x_max": ("x_max", "xmax", "x2", "right"),
                "y_max": ("y_max", "ymax", "y2", "bottom"),
            }
            box = {standard: next((box[key] for key in names if key in box), None) for standard, names in aliases.items()}
        if not isinstance(box, dict):
            continue
        if any(box.get(key) is None for key in ("x_min", "y_min", "x_max", "y_max")):
            continue
        normalized.append({
            "target": candidate.get("target", target),
            "bbox": box,
            "confidence": candidate.get("confidence", raw.get("confidence", 0.0)),
            "evidence": candidate.get("evidence", []),
            "observed_state": candidate.get("observed_state", candidate.get("state")),
        })
    found = bool(raw.get("found", bool(normalized)))
    reason = raw.get("reason")
    # A model may say found=true while refusing to provide a trustworthy box.
    # The schema must represent the actionable truth: no bbox means not found
    # for the purpose of a click.
    if found and not normalized:
        found = False
        reason = reason or "模型确认目标存在，但未提供可执行的 bbox"
    return {"found": found, "target": raw.get("target", target), "image_size": [width, height], "candidates": normalized, "reason": reason}

class Qwen3VLClient:
    def __init__(self, *, api_key=None, base_url=None, model=None, timeout=60, transport=None):
        _load_project_env()
        self.api_key = api_key or os.getenv("QWEN_VL_API_KEY")
        self.base_url = (base_url or os.getenv("QWEN_VL_BASE_URL", "")).rstrip("/") + "/"
        self.model = model or os.getenv("QWEN_VL_MODEL")
        if not self.api_key or not self.base_url.strip("/") or not self.model:
            raise VisionClientError("请配置 QWEN_VL_API_KEY、QWEN_VL_BASE_URL 和 QWEN_VL_MODEL")
        self.http = httpx.Client(base_url=self.base_url, headers={"Authorization": f"Bearer {self.api_key}"}, timeout=timeout, transport=transport)

    @staticmethod
    def data_url(path: Path) -> str:
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    def locate(self, image_path: str | Path, target: str, *, state: str = "any", context: str = "") -> LocateResult:
        path = Path(image_path)
        if not path.is_file():
            raise VisionClientError(f"图片不存在：{path}")
        with Image.open(path) as image:
            actual_width, actual_height = image.size
        state_rule = "对于 off 状态，即使没有波形或高亮，也要定位仍然存在的通道卡片；不要因为没有波形就返回 found=false。" if state == "off" else ""
        state_rule += "对于 any 状态，只判断目标组件是否存在；如果状态无法确定，返回 observed_state=unknown，但仍要返回组件框。" if state == "any" else ""
        instruction = f'''你是示波器图像定位器。请在这张 Rigol DHO804 屏幕 ROI 中定位逻辑目标“{target}”，期望状态为“{state}”。{state_rule}{context}
输入图片的实际像素尺寸是 [{actual_width}, {actual_height}]。
只返回 JSON，不要 Markdown。格式：
{{"found": true/false, "target": "{target}", "image_size": [{actual_width}, {actual_height}], "candidates": [{{"target": "{target}", "bbox": {{"x_min": 0, "y_min": 0, "x_max": 0, "y_max": 0}}, "confidence": 0.0, "observed_state": "on/off/unknown", "evidence": []}}], "reason": null}}
坐标必须是输入图片原始像素坐标 [左,上,右,下]。如果模型内部缩放图片，仍必须换算回 [{actual_width}, {actual_height}]。找不到或无法确认时返回 found=false、空 candidates，并说明 reason。不要编造坐标。'''
        payload = {"model": self.model, "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": self.data_url(path)}},
            {"type": "text", "text": instruction},
        ]}], "response_format": {"type": "json_object"}}
        try:
            response = self.http.post("chat/completions", json=payload)
            response.raise_for_status()
            body = response.json()
            content = _content_text(body["choices"][0]["message"].get("content"))
            raw = _json_payload(content)
            reported_size = raw.get("image_size") or [actual_width, actual_height]
            raw = _normalize_payload(raw, target, actual_width, actual_height)
            reported_width, reported_height = int(reported_size[0]), int(reported_size[1])
            if reported_width > 0 and reported_height > 0:
                scale_x = actual_width / reported_width
                scale_y = actual_height / reported_height
                coordinate_mode = os.getenv("QWEN_VL_COORDINATE_MODE", "auto").casefold()
                boxes = [c["bbox"] for c in raw.get("candidates", [])]
                values = [float(box[key]) for box in boxes for key in ("x_min", "y_min", "x_max", "y_max")]
                # Qwen vision responses sometimes use the common 0-1000
                # normalized coordinate convention despite a pixel prompt.
                exceeds_reported = any(
                    box.get("x_max", 0) > reported_width or box.get("y_max", 0) > reported_height
                    for box in boxes
                )
                if values and max(values) <= 1 and reported_width > 1 and reported_height > 1:
                    # Some gateways return 0..1 normalized boxes while still
                    # echoing the pixel image size.
                    scale_x, scale_y = actual_width, actual_height
                elif coordinate_mode in {"pixel", "pixels"}:
                    # Explicit override for a provider that obeys the pixel
                    # coordinate instruction.
                    scale_x, scale_y = actual_width / reported_width, actual_height / reported_height
                elif coordinate_mode in {"normalized", "normalized_1000", "1000"} or (
                    coordinate_mode == "auto" and values and max(values) <= 1000 and reported_width == actual_width and reported_height == actual_height
                ) or (values and max(values) <= 1000 and exceeds_reported):
                    # Qwen-compatible gateways commonly return 0..1000 boxes
                    # even when they echo the original pixel image_size.
                    scale_x, scale_y = actual_width / 1000, actual_height / 1000
                for candidate in raw.get("candidates", []):
                    box = candidate.get("bbox", {})
                    for key in ("x_min", "x_max"):
                        if key in box:
                            box[key] = float(box[key]) * scale_x
                    for key in ("y_min", "y_max"):
                        if key in box:
                            box[key] = float(box[key]) * scale_y
            raw["image_size"] = [actual_width, actual_height]
            return LocateResult.model_validate(raw)
        except httpx.HTTPError as exc:
            raise VisionClientError(f"Qwen3-VL 请求失败：{exc}") from None
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            detail = str(exc)
            diagnostic = ""
            if "bbox" in detail and isinstance(locals().get("raw"), dict):
                diagnostic = "；归一化后的候选框=" + json.dumps(raw.get("candidates", []), ensure_ascii=False)
            elif "没有 JSON" in detail and isinstance(locals().get("content"), str):
                diagnostic = "；模型文本摘要=" + content[:500].replace("\n", " ")
            elif isinstance(locals().get("raw"), dict):
                diagnostic = "；模型 JSON 摘要=" + json.dumps(raw, ensure_ascii=False)[:1200]
            raise VisionClientError(f"Qwen3-VL 返回结果无法解析：{detail}{diagnostic}") from None

    def recognize_screen(self, image_path: str | Path, *, context: str = "") -> ScreenRecognition:
        """Classify the current UI without requiring a target component."""
        path = Path(image_path)
        if not path.is_file():
            raise VisionClientError(f"图片不存在：{path}")
        with Image.open(path) as image:
            width, height = image.size
        instruction = f'''你是 Rigol DHO804 示波器界面状态识别器。请判断输入图片当前最符合的界面状态。
可选状态只能是：main_screen、measurement_panel、measurement_vertical、measurement_horizontal、measurement_other、unknown。
判断依据包括测量面板、垂直/水平/其它分类标签、结果窗口和明显的主界面布局。若测量面板打开且能看到当前选中的垂直标签及其参数网格，优先返回 measurement_vertical；水平和其它同理。只有测量面板打开但无法确认具体分类时才返回 measurement_panel。无法确认时返回 unknown，不要猜测。{context}
只返回 JSON，不要 Markdown：
{{"screen_state":"unknown","confidence":0.0,"evidence":[],"visible_components":[],"reason":null}}
图片原始尺寸为 [{width}, {height}]。'''
        payload = {"model": self.model, "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": self.data_url(path)}},
            {"type": "text", "text": instruction},
        ]}], "response_format": {"type": "json_object"}}
        try:
            response = self.http.post("chat/completions", json=payload)
            response.raise_for_status()
            body = response.json()
            content = _content_text(body["choices"][0]["message"].get("content"))
            raw = _json_payload(content)
            if not isinstance(raw, dict):
                raise ValueError("界面状态响应不是 JSON 对象")
            return ScreenRecognition.model_validate(raw)
        except httpx.HTTPError as exc:
            raise VisionClientError(f"Qwen3-VL 界面识别请求失败：{exc}") from None
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise VisionClientError(f"Qwen3-VL 界面识别结果无法解析：{exc}") from None

    def close(self):
        self.http.close()
