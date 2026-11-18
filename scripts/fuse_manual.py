#!/usr/bin/env python3
"""Fuse cleaned Docling structure with PyMuPDF page/image evidence."""
import argparse, json
from pathlib import Path
def main():
    p=argparse.ArgumentParser(description="融合 PyMuPDF 和 Docling 页面证据"); p.add_argument("--pymupdf",default="data/parsed/DHO804_clean"); p.add_argument("--docling",default="data/parsed/DHO804_clean/docling_document_clean.json"); p.add_argument("--output",default="data/parsed/DHO804_fused/fused_document.json"); args=p.parse_args()
    data=json.loads(Path(args.docling).read_text(encoding="utf-8")); pages={}; section=[]
    for item in data.get("texts",[]):
        text=str(item.get("text") or item.get("orig") or "").strip();
        if not text or item.get("cleaning_status")=="repeated_template_text": continue
        label=item.get("label",""); role=item.get("normalized_role", "body")
        if role in {"heading","heading_candidate"}:
            level=item.get("normalized_level")
            if level is None: level=min(6,len(section)+1)
            section=section[:max(0,int(level)-1)]; section.append(text)
        for prov in item.get("prov",[]):
            number=prov.get("page_no")
            if number is not None: pages.setdefault(int(number),{"page_number":int(number),"section_path":list(section),"elements":[]})["elements"].append({"type":"text","text":text,"label":label,"normalized_role":role,"normalized_level":item.get("normalized_level"),"bbox":prov.get("bbox"),"source":"docling"})
    for index, table in enumerate(data.get("tables", []), 1):
        cells=table.get("data",{}).get("table_cells",[]); table_text=" | ".join(str(cell.get("text", "")).strip() for cell in cells if str(cell.get("text", "")).strip())
        for prov in table.get("prov", []):
            number=prov.get("page_no")
            if number is not None: pages.setdefault(int(number),{"page_number":int(number),"section_path":[],"elements":[]})["elements"].append({"type":"table","table_id":f"table_{index:04d}","text":table_text,"bbox":prov.get("bbox"),"source":"docling"})
    manifest=Path(args.pymupdf)/"image_manifest.jsonl"
    if manifest.exists():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line: continue
            image=json.loads(line); number=image.get("page")
            if number is not None and image.get("status")=="selected": pages.setdefault(int(number),{"page_number":int(number),"section_path":[],"elements":[]})["elements"].append({"type":"image","path":image.get("path"),"status":image.get("status"),"reason":image.get("reason"),"bbox":image.get("bbox"),"source":"pymupdf"})
    output=Path(args.output); output.parent.mkdir(parents=True,exist_ok=True); payload={"source_file":"data/manuals/DHO804/DHO804.pdf","pages":[pages[x] for x in sorted(pages)],"fusion":{"docling":str(args.docling),"pymupdf":str(args.pymupdf)}}; output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps({"output":str(output),"pages":len(payload["pages"]),"elements":sum(len(x["elements"]) for x in payload["pages"])},ensure_ascii=False,indent=2))
if __name__=="__main__": main()
