#!/usr/bin/env python3
"""Inspect one image: screen state plus one or more requested components.

This is a read-only Phase 3 smoke test.  It never clicks or connects to ROS2.
"""
import argparse
import json
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(): pass

from models.observation import Observation, ObservationComponent
from perception.component_locator import ComponentLocator
from perception.knowledge_observer import KnowledgeDrivenObserver
from perception.vlm_client import Qwen3VLClient, VisionClientError
from knowledge.retrieval.knowledge_retriever import KnowledgeRetriever


def main():
    parser = argparse.ArgumentParser(description="识别示波器当前界面、状态并框选指定组件")
    image_group = parser.add_mutually_exclusive_group(required=True)
    image_group.add_argument("--image", help="已有图片路径")
    image_group.add_argument("--live", action="store_true", help="从 /vision_srv/camera/rgb_screen 捕获一帧")
    parser.add_argument("--target", action="append", help="组件目标，可重复指定")
    parser.add_argument("--query", help="自然语言目标，例如：测量 CH2 的峰峰值")
    parser.add_argument("--state", choices=["any", "on", "off"], default="any")
    parser.add_argument("--output", default="data/perception_results/inspect.json")
    args = parser.parse_args()
    if not args.target and not args.query:
        parser.error("至少需要 --target 或 --query")
    load_dotenv()
    try:
        if args.live:
            from integration.vision_frame_source import Ros2VisionFrameSource
            frame = Ros2VisionFrameSource().capture()
            image = frame.path
        else:
            image = Path(args.image)
    except (RuntimeError, TimeoutError, OSError) as exc:
        print(f"获取视觉帧失败：{exc}")
        raise SystemExit(2)
    client = None
    locator = None
    started = time.perf_counter()
    try:
        client = Qwen3VLClient()
        locator = ComponentLocator(client)
        if args.query:
            result = KnowledgeDrivenObserver(locator, KnowledgeRetriever()).observe(image, args.query, state=args.state)
            requested = [args.query]
        else:
            with Image.open(image) as source:
                image_size = source.size
            screen = client.recognize_screen(image)
            components = []
            reasons = []
            for target in args.target:
                located = locator.locate(image, target, state=args.state)
                if not located.found:
                    reasons.append(f"{target}: {located.reason or '未找到'}")
                components.extend(ObservationComponent(
                    target=item.target, bbox=item.bbox,
                    observed_state=item.observed_state or "unknown",
                    confidence=item.confidence, evidence=item.evidence,
                ) for item in located.candidates)
            result = Observation(
                image=str(image), image_size=image_size,
                screen_state=screen.screen_state, components=components,
                required_observations=args.target,
                confidence=min((item.confidence for item in components), default=screen.confidence),
                reason="；".join(reasons) if reasons else screen.reason,
                metadata={"screen_evidence": screen.model_dump(mode="json")},
            )
            requested = args.target
        payload = result.model_dump(mode="json")
        payload["requested"] = requested
        payload["inference_ms"] = round((time.perf_counter() - started) * 1000, 2)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(image) as source:
            annotated = source.convert("RGB")
            draw = ImageDraw.Draw(annotated)
            for item in result.components:
                box = item.bbox
                draw.rectangle((box.x_min, box.y_min, box.x_max, box.y_max), outline="red", width=3)
            annotated_path = output.with_name(output.stem + "_annotated.jpg")
            annotated.save(annotated_path)
        payload["annotated_image"] = str(annotated_path)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except (VisionClientError, OSError, ValueError) as exc:
        print(f"识别失败：{exc}")
        raise SystemExit(2)
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    main()

