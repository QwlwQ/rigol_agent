#!/usr/bin/env python3
"""Qualitative batch evaluation on existing oscilloscope images.

This script deliberately does not read external labels or calculate IoU. It records
Qwen3-VL outputs for later human review.
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
from perception.component_locator import ComponentLocator
from perception.vlm_client import Qwen3VLClient, VisionClientError

DEFAULT_TARGETS = ["CH2", "Measure", "Vertical", "Maximum"]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

def annotate(image_path, result, output_path):
    with Image.open(image_path) as source:
        image = source.convert("RGB")
        draw = ImageDraw.Draw(image)
        for candidate in result.candidates:
            box = candidate.bbox
            draw.rectangle((box.x_min, box.y_min, box.x_max, box.y_max), outline="red", width=3)
        image.save(output_path)

def main():
    parser = argparse.ArgumentParser(description="Qwen3-VL qualitative evaluation")
    parser.add_argument("--images", default="/home/ubuntu/RIGOL/datasets/images")
    parser.add_argument("--targets", nargs="+", default=DEFAULT_TARGETS)
    parser.add_argument("--limit", type=int, default=0, help="0 means all images")
    parser.add_argument("--output-dir", default="data/perception_eval")
    parser.add_argument("--sample-every", type=int, default=1)
    args = parser.parse_args()
    load_dotenv()

    image_dir = Path(args.images)
    images = sorted(p for p in image_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)
    images = images[::max(1, args.sample_every)]
    if args.limit > 0:
        images = images[:args.limit]
    if not images:
        raise SystemExit(f"没有找到图片：{image_dir}")

    output_dir = Path(args.output_dir)
    annotated_dir = output_dir / "annotated"
    output_dir.mkdir(parents=True, exist_ok=True)
    annotated_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "results.jsonl"
    summary_path = output_dir / "summary.json"

    client = Qwen3VLClient()
    locator = ComponentLocator(client)
    records = []
    started = time.perf_counter()
    try:
        with results_path.open("w", encoding="utf-8") as stream:
            total = len(images) * len(args.targets)
            index = 0
            for image_path in images:
                for target in args.targets:
                    index += 1
                    row = {"image": str(image_path), "target": target}
                    try:
                        result = locator.locate(image_path, target)
                        annotated_path = annotated_dir / f"{image_path.stem}__{target}.jpg"
                        annotate(image_path, result, annotated_path)
                        row.update(result.model_dump(mode="json"))
                        row["annotated_image"] = str(annotated_path)
                    except (VisionClientError, OSError, ValueError) as exc:
                        row.update({"found": False, "error": str(exc)})
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                    stream.flush()
                    records.append(row)
                    print(f"[{index}/{total}] {image_path.name} | {target} | {row.get('found', False)}")
    finally:
        client.close()

    found = sum(1 for row in records if row.get("found") is True)
    errors = sum(1 for row in records if "error" in row)
    summary = {
        "images": len(images),
        "targets": args.targets,
        "requests": len(records),
        "found": found,
        "not_found": len(records) - found - errors,
        "errors": errors,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "evaluation_type": "qualitative_without_ground_truth",
        "labels_used": False,
        "results": str(results_path),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
