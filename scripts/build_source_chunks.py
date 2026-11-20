#!/usr/bin/env python3
"""Build source-preserving chunks from normalized_document.json."""
import argparse, json
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description="生成后续知识提取使用的来源知识块")
    parser.add_argument("--input",default="data/parsed/DHO804_structure/normalized_document.json"); parser.add_argument("--output",default="data/index/DHO804/source_chunks.jsonl"); parser.add_argument("--max-chars",type=int,default=5000); args=parser.parse_args()
    document=json.loads(Path(args.input).read_text(encoding="utf-8")); chunks=[]; counter=0
    for page in document.get("pages",[]):
        texts=[]; tables=[]; images=[]; refs=[]
        for element in page.get("elements",[]):
            refs.append(element.get("source_ref"))
            if element.get("type")=="text": texts.append(element.get("text", ""))
            elif element.get("type")=="table": tables.append(element.get("rows",[]))
            elif element.get("type")=="image": images.append({"path":element.get("path"),"bbox":element.get("bbox"),"source_ref":element.get("source_ref")})
        text="\n".join(x for x in texts if x).strip()
        if not text and not tables and not images: continue
        for start in range(0,max(len(text),1),args.max_chars):
            part=text[start:start+args.max_chars].strip()
            if not part and start>0: continue
            counter+=1; chunks.append({"chunk_id":f"source_{counter:05d}","device":"DHO804","pages":[page["page_number"]],"text":part,"tables":tables if start==0 else [],"images":images if start==0 else [],"source_refs":sorted(set(x for x in refs if x)),"verification_status":"unprocessed"})
    output=Path(args.output); output.parent.mkdir(parents=True,exist_ok=True); output.write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in chunks)+"\n",encoding="utf-8"); print(json.dumps({"output":str(output),"chunks":len(chunks)},ensure_ascii=False,indent=2))
if __name__=="__main__": main()
