#!/usr/bin/env python3
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

def main():
    parser=argparse.ArgumentParser(description="Qwen3-VL 示波器屏幕 ROI 组件定位 MVP")
    parser.add_argument("--image", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--state", choices=["any", "on", "off"], default="any")
    parser.add_argument("--context", default="")
    parser.add_argument("--output", default="data/perception_results/locate_result.json")
    args=parser.parse_args(); load_dotenv()
    client=Qwen3VLClient(); start=time.perf_counter()
    try:
        result=ComponentLocator(client).locate(args.image,args.target,state=args.state,context=args.context)
        elapsed_ms=round((time.perf_counter()-start)*1000,2)
        payload=result.model_dump(mode="json"); payload["inference_ms"]=elapsed_ms; payload["image"] = str(Path(args.image))
        payload["requested_state"] = args.state
        Path(args.output).parent.mkdir(parents=True,exist_ok=True)
        with Image.open(args.image) as source:
            annotated = source.convert("RGB")
            draw = ImageDraw.Draw(annotated)
            for candidate in result.candidates:
                b = candidate.bbox
                draw.rectangle((b.x_min, b.y_min, b.x_max, b.y_max), outline="red", width=3)
            annotated_path = Path(args.output).with_name(Path(args.output).stem + "_annotated.jpg")
            annotated.save(annotated_path)
        payload["annotated_image"] = str(annotated_path)
        Path(args.output).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(payload,ensure_ascii=False,indent=2))
    except VisionClientError as exc:
        print(f"定位失败：{exc}"); raise SystemExit(2)
    finally: client.close()
if __name__ == "__main__": main()
