#!/usr/bin/env python3
"""Export cleaned Docling or fused JSON into a human-review Markdown preview."""
import argparse
import json
from pathlib import Path

def docling_preview(data, output):
    lines=["# DHO804 Docling 清洗结果预览", "", "> 本文件只用于人工检查，不作为最终知识库。", ""]
    current=[]
    for item in data.get("texts",[]):
        if item.get("cleaning_status")=="repeated_template_text": continue
        text=str(item.get("text") or item.get("orig") or "").strip()
        if not text: continue
        label=item.get("label","")
        if label in {"title","section_header"}:
            level=min(6,int(item.get("level") or 2)); lines += ["#"*level+" "+text, ""]
        else:
            pages=sorted({p.get("page_no") for p in item.get("prov",[]) if p.get("page_no") is not None})
            lines += [f"{text}  ", f"<!-- pages: {pages} -->", ""]
    lines += ["## 表格统计", "", f"Docling tables: {len(data.get('tables',[]))}", ""]
    output.write_text("\n".join(lines),encoding="utf-8")

def fused_preview(data, output):
    lines=["# DHO804 融合文档预览", "", "> 本文件用于人工检查 PyMuPDF 与 Docling 融合结果，不作为最终知识库。", ""]
    for page in data.get("pages",[]):
        number=page.get("page_number"); section=" / ".join(page.get("section_path",[])) or "未识别章节"
        lines += [f"## 第 {number} 页：{section}", ""]
        for element in page.get("elements",[]):
            kind=element.get("type")
            if kind in {"text","table"}:
                text=str(element.get("text","")).strip()
                if text: lines += [f"### {kind}", text, ""]
            elif kind=="image":
                path=element.get("path"); status=element.get("status")
                lines += [f"### image ({status})", f"`{path}`", ""]
    output.write_text("\n".join(lines),encoding="utf-8")

def main():
    parser=argparse.ArgumentParser(description="导出说明书 JSON 的人工检查 Markdown")
    parser.add_argument("--input",required=True); parser.add_argument("--output",required=True); parser.add_argument("--format",choices=["docling","fused"],required=True); args=parser.parse_args()
    data=json.loads(Path(args.input).read_text(encoding="utf-8")); output=Path(args.output); output.parent.mkdir(parents=True,exist_ok=True)
    if args.format=="docling": docling_preview(data,output)
    else: fused_preview(data,output)
    print(output)
if __name__=="__main__": main()
