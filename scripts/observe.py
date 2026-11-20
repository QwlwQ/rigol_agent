#!/usr/bin/env python3
"""Knowledge-driven observation of one current oscilloscope image.

The command only retrieves knowledge and locates targets.  It never sends a
click to the robot.
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

from knowledge.retrieval.knowledge_retriever import KnowledgeRetriever
from perception.component_locator import ComponentLocator
from perception.knowledge_observer import KnowledgeDrivenObserver
from perception.vlm_client import Qwen3VLClient, VisionClientError


def main():
    parser = argparse.ArgumentParser(description="说明书知识驱动的示波器视觉观察")
    parser.add_argument("--image", required=True)
    parser.add_argument("--query", required=True, help="用户自然语言目标")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--output", default="data/perception_results/observation.json")
    args = parser.parse_args()
    load_dotenv()
    client = None
    started = time.perf_counter()
    try:
        client = Qwen3VLClient()
        observer = KnowledgeDrivenObserver(ComponentLocator(client), KnowledgeRetriever())
        plan = observer.plan(args.query, limit=args.limit)
        result = observer.observe(args.image, args.query, limit=args.limit)
        payload = result.model_dump(mode="json")
        payload["query"] = args.query
        payload["observation_targets"] = [target.model_dump(mode="json") for target in plan.targets]
        payload["inference_ms"] = round((time.perf_counter() - started) * 1000, 2)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(args.image) as source:
            annotated = source.convert("RGB")
            draw = ImageDraw.Draw(annotated)
            for component in result.components:
                box = component.bbox
                draw.rectangle((box.x_min, box.y_min, box.x_max, box.y_max), outline="red", width=3)
            annotated_path = output.with_name(output.stem + "_annotated.jpg")
            annotated.save(annotated_path)
        payload["annotated_image"] = str(annotated_path)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except (VisionClientError, OSError, ValueError) as exc:
        print(f"观察失败：{exc}")
        raise SystemExit(2)
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    main()

