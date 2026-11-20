#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from knowledge.manual_repository import ManualKnowledgeRepository
from knowledge.retrieval.knowledge_retriever import KnowledgeRetriever

def main():
    p=argparse.ArgumentParser(description="检索 DHO804 说明书提取知识")
    p.add_argument("query"); p.add_argument("--type",dest="record_type"); p.add_argument("--chapter"); p.add_argument("--limit",type=int,default=10)
    p.add_argument("--full",action="store_true",help="输出完整原始记录；默认只输出精简摘要")
    p.add_argument("--plan",action="store_true",help="同时输出供 Agent 使用的观察目标计划")
    args=p.parse_args()
    repo=ManualKnowledgeRepository()
    retriever = KnowledgeRetriever(repo)
    if args.plan:
        plan = retriever.observation_plan(args.query, record_type=args.record_type, limit=args.limit)
        # Do not dump page images/tables here; this command is an inspection
        # helper and the Agent consumes compact evidence instead.
        result = {
            "query": plan.query,
            "records": [item.model_dump(mode="json") for item in retriever.operation_summaries(args.query, limit=args.limit)] if args.record_type == "operation" else [
                {key: record.get(key) for key in ("record_type", "id", "name", "description", "data", "source_pages", "confidence", "verification_status")}
                for record in repo.search(args.query, record_type=args.record_type, chapter_id=args.chapter, limit=args.limit)
            ],
            "required_observations": [item.model_dump(mode="json") for item in plan.targets],
        }
    elif args.full:
        result=repo.search(args.query,record_type=args.record_type,chapter_id=args.chapter,limit=args.limit)
    else:
        result=[item.model_dump(mode="json") for item in retriever.operation_summaries(args.query,limit=args.limit)] if args.record_type == "operation" else [
            {key: record.get(key) for key in ("record_type","id","name","description","data","source_pages","confidence","verification_status")}
            for record in repo.search(args.query,record_type=args.record_type,chapter_id=args.chapter,limit=args.limit)
        ]
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
