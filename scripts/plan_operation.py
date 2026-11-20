#!/usr/bin/env python3
"""Generate the compact operation plan consumed by the Agent."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planning.operation_planner import OperationPlanner


def main():
    parser = argparse.ArgumentParser(description="生成 DHO804 知识驱动操作计划")
    parser.add_argument("query")
    args = parser.parse_args()
    plan = OperationPlanner().plan(args.query, use_llm=False)
    print(json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

