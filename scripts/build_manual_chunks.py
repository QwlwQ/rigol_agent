#!/usr/bin/env python3
"""Build source-preserving chunks from the full Docling document by default."""
import argparse
import json
import re
from pathlib import Path

def matches(text, include, exclude):
    lower=text.casefold()
    return (not include or any(term.casefold() in lower for term in include)) and not any(term.casefold() in lower for term in exclude)

def build_from_docling(path, output, include, exclude, page_range, max_chars):
    document=json.loads(path.read_text(encoding="utf-8")); texts=document.get("texts", [])
    section_stack=[]; chunks=[]; buffer=[]; pages=set(); counter=0
    def flush():
        nonlocal buffer,pages,counter
        text="\n".join(buffer).strip()
        if text:
            counter+=1; chunks.append({"chunk_id":f"docling_{counter:05d}","device":"DHO804","section_path":list(section_stack),"pages":sorted(pages),"text":text,"source":{"file":"data/manuals/DHO804/DHO804.pdf","pages":sorted(pages)},"verification_status":"unprocessed"})
        buffer=[]; pages=set()
    for item in texts:
        text=str(item.get("text") or item.get("orig") or "").strip()
        if not text: continue
        provenance=item.get("prov") or []; item_pages={int(p.get("page_no")) for p in provenance if p.get("page_no") is not None}
        label=item.get("label", "")
        if label in {"section_header", "title"}:
            flush(); level=int(item.get("level") or 1); section_stack=section_stack[:max(0,level-1)]; section_stack.append(text); continue
        if page_range and item_pages and not any(page_range[0] <= page <= page_range[1] for page in item_pages): continue
        if not matches(text,include,exclude): continue
        if sum(len(x) for x in buffer)+len(text)+1 > max_chars: flush()
        buffer.append(text); pages.update(item_pages)
    flush(); output.write_text("\n".join(json.dumps(row,ensure_ascii=False) for row in chunks)+"\n",encoding="utf-8"); return len(chunks)

def build_from_pymupdf(path, output, include, exclude, page_range, max_chars):
    chunks=[]; counter=0
    for text_path in sorted((path/"text").glob("page_*.txt")):
        page=int(re.search(r"page_(\d+)",text_path.name).group(1)); text=text_path.read_text(encoding="utf-8",errors="ignore").strip()
        if page_range and not page_range[0] <= page <= page_range[1]: continue
        if not matches(text,include,exclude): continue
        for index in range(0,len(text),max_chars):
            part=text[index:index+max_chars].strip()
            if part:
                counter+=1; chunks.append({"chunk_id":f"pymupdf_{counter:05d}","device":"DHO804","section_path":[],"pages":[page],"text":part,"source":{"file":"data/manuals/DHO804/DHO804.pdf","pages":[page]},"verification_status":"unprocessed"})
    output.write_text("\n".join(json.dumps(row,ensure_ascii=False) for row in chunks)+"\n",encoding="utf-8"); return len(chunks)

def build_from_fused(path, output, include, exclude, page_range, max_chars):
    data=json.loads(Path(path).read_text(encoding="utf-8")); chunks=[]; counter=0
    for page in data.get("pages",[]):
        number=int(page["page_number"])
        if page_range and not page_range[0] <= number <= page_range[1]: continue
        parts=[]; media=[]
        for element in page.get("elements",[]):
            if element.get("type") in {"text","table"}: parts.append(element.get("text", ""))
            elif element.get("type")=="image": media.append({"path":element.get("path"),"bbox":element.get("bbox"),"source":element.get("source")})
        text="\n".join(parts).strip()
        if not text or not matches(text,include,exclude): continue
        for index in range(0,len(text),max_chars):
            part=text[index:index+max_chars].strip()
            if part:
                counter+=1; chunks.append({"chunk_id":f"fused_{counter:05d}","device":"DHO804","section_path":page.get("section_path",[]),"pages":[number],"text":part,"media":media,"source":{"file":"data/manuals/DHO804/DHO804.pdf","pages":[number]},"verification_status":"unprocessed"})
    output.write_text("\n".join(json.dumps(row,ensure_ascii=False) for row in chunks)+"\n",encoding="utf-8"); return len(chunks)

def main():
    parser=argparse.ArgumentParser(description="生成整本说明书来源保留的知识块")
    parser.add_argument("--input",default="data/parsed/DHO804"); parser.add_argument("--output",default="data/index/DHO804/chunks.jsonl"); parser.add_argument("--source",choices=["auto","fused","docling","pymupdf"],default="auto")
    parser.add_argument("--include",action="append",default=[]); parser.add_argument("--exclude",action="append",default=[]); parser.add_argument("--pages",default=""); parser.add_argument("--max-chars",type=int,default=5000); args=parser.parse_args()
    root=Path(args.input); output=Path(args.output); output.parent.mkdir(parents=True,exist_ok=True); page_range=None
    if args.pages:
        start,end=args.pages.split("-",1); page_range=(int(start),int(end))
    fused=root/"fused_document.json"; docling=root/"docling_document.json"; source="fused" if args.source=="auto" and fused.exists() else ("docling" if args.source=="auto" and docling.exists() else args.source)
    if source=="fused": count=build_from_fused(fused,output,args.include,args.exclude,page_range,args.max_chars)
    elif source=="docling": count=build_from_docling(docling,output,args.include,args.exclude,page_range,args.max_chars)
    else: count=build_from_pymupdf(root,output,args.include,args.exclude,page_range,args.max_chars)
    print(json.dumps({"output":str(output),"source":source,"chunks":count,"filtered":bool(args.include or args.exclude or args.pages)},ensure_ascii=False,indent=2))
if __name__=="__main__": main()
