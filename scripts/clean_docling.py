#!/usr/bin/env python3
"""Create a conservative cleaned copy of Docling JSON."""
import argparse, json
from collections import Counter
from pathlib import Path
import re
HEADING_NUMBER=re.compile(r'^(\d+(?:\.\d+)*)(?:\s+|[、.．])')
NON_HEADING_PREFIXES=('警告','注意','提示','注：','说明：','·','•','-','1.','2.','3.','4.')
def normalize_heading(item, text):
    label=item.get('label',''); match=HEADING_NUMBER.match(text)
    if match:
        return 'heading', len(match.group(1).split('.')), 'numbered_heading'
    if label not in {'section_header','title'}: return 'body', None, 'docling_label'
    if any(text.startswith(prefix) for prefix in NON_HEADING_PREFIXES): return 'body', None, 'excluded_prefix'
    if len(text)>40 or any(mark in text for mark in ('。','；','：','……')): return 'body', None, 'sentence_like'
    if text in {'警告','注意','提示'}: return 'body', None, 'notice_label'
    return 'heading_candidate', None, 'unumbered_candidate'
def main():
    p=argparse.ArgumentParser(description="清洗 Docling 文档结构"); p.add_argument("--input",default="data/parsed/DHO804/docling_document.json"); p.add_argument("--output",default="data/parsed/DHO804_clean/docling_document_clean.json"); args=p.parse_args()
    data=json.loads(Path(args.input).read_text(encoding="utf-8")); texts=data.get("texts",[]); counts=Counter(str(x.get("text") or x.get("orig") or "").strip() for x in texts); removed=0; cleaned=[]
    for item in texts:
        copy=dict(item); text=str(item.get("text") or item.get("orig") or "").strip(); status="kept"
        if len(text)<=120 and counts[text]>=20: status="repeated_template_text"; removed+=1
        role,level,reason=normalize_heading(item,text)
        copy["cleaning_status"]=status; copy["normalized_role"]=role; copy["normalized_level"]=level; copy["normalization_reason"]=reason; cleaned.append(copy)
    data["texts"]=cleaned; data["cleaning_summary"]={"text_items":len(texts),"marked_repeated_template_text":removed,"tables_preserved":len(data.get("tables",[]))}; output=Path(args.output); output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps(data["cleaning_summary"],ensure_ascii=False,indent=2))
if __name__=="__main__": main()
