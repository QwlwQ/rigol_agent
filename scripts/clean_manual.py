#!/usr/bin/env python3
"""Clean manual artifacts without modifying raw parsed output."""
import argparse, hashlib, json, shutil
from collections import Counter
from pathlib import Path
from PIL import Image

EXTENSIONS={".jpg",".jpeg",".png",".bmp",".webp"}
def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""): h.update(block)
    return h.hexdigest()
def main():
    p=argparse.ArgumentParser(description="清洗 DHO804 说明书解析产物"); p.add_argument("--input",default="data/parsed/DHO804"); p.add_argument("--output",default="data/parsed/DHO804_clean"); p.add_argument("--min-width",type=int,default=40); p.add_argument("--min-height",type=int,default=40); p.add_argument("--min-area",type=int,default=2000); p.add_argument("--max-aspect",type=float,default=12); p.add_argument("--copy-selected-images",action="store_true"); args=p.parse_args()
    source=Path(args.input); output=Path(args.output); (output/"pages").mkdir(parents=True,exist_ok=True); (output/"text").mkdir(exist_ok=True); (output/"images_selected").mkdir(exist_ok=True)
    texts=sorted((source/"text").glob("page_*.txt")); counts=Counter()
    for path in texts:
        counts.update(set(" ".join(line.split()).strip() for line in path.read_text(encoding="utf-8",errors="ignore").splitlines() if 3<=len(line.strip())<=120))
    repeated={x for x,n in counts.items() if n>=max(3,int(len(texts)*.3))}; page_images={}; records=[]; hashes=Counter()
    raw_images=source/"images"; raw_image_boxes={}
    for raw_page in sorted((source/"pages").glob("page_*.json")) if (source/"pages").exists() else []:
        try:
            page_data=json.loads(raw_page.read_text(encoding="utf-8"));
            for image in page_data.get("images",[]): raw_image_boxes[str(Path(image.get("path","")))]=image.get("bbox")
        except Exception: pass
    image_paths=[x for x in raw_images.rglob("*")] if raw_images.exists() else []
    for path in image_paths:
        if path.suffix.lower() in EXTENSIONS: hashes[digest(path)]+=1
    repeated_hashes={x for x,n in hashes.items() if n>3}
    for path in texts:
        lines=[line for line in path.read_text(encoding="utf-8",errors="ignore").splitlines() if " ".join(line.split()).strip() not in repeated]
        (output/"text"/path.name).write_text("\n".join(lines)+"\n",encoding="utf-8")
    for path in image_paths:
        if path.suffix.lower() not in EXTENSIONS: continue
        page=int(path.name.split("page_")[1].split("_")[0]) if "page_" in path.name else None
        try:
            with Image.open(path) as image: width,height=image.size
        except Exception as exc:
            record={"path":str(path),"page":page,"status":"invalid","reason":type(exc).__name__}; records.append(record); continue
        area=width*height; aspect=max(width/height,height/width) if height else 999; reasons=[]
        if width<args.min_width or height<args.min_height or area<args.min_area: reasons.append("small")
        if aspect>args.max_aspect: reasons.append("thin_or_line")
        image_hash=digest(path)
        if image_hash in repeated_hashes: reasons.append("repeated_asset")
        status="likely_decoration" if reasons else "selected"
        record={"path":str(path),"page":page,"width":width,"height":height,"area":area,"aspect_ratio":round(aspect,3),"sha256":image_hash,"bbox":raw_image_boxes.get(str(path)),"status":status,"reason":reasons}; records.append(record); page_images.setdefault(page,[]).append(record)
        if status=="selected" and args.copy_selected_images: shutil.copy2(path,output/"images_selected"/path.name)
    for raw_page in sorted((source/"pages").glob("page_*.json")) if (source/"pages").exists() else []:
        page=json.loads(raw_page.read_text(encoding="utf-8")); number=page.get("page_number"); page["cleaning"]={"removed_repeated_lines":len(repeated),"image_manifest":page_images.get(number,[])}; (output/"pages"/raw_page.name).write_text(json.dumps(page,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
    (output/"image_manifest.jsonl").write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in records)+"\n",encoding="utf-8")
    summary={"input":str(source),"output":str(output),"page_count":len(texts),"image_count":len(records),"selected_images":sum(x.get("status")=="selected" for x in records),"filtered_images":sum(x.get("status")=="likely_decoration" for x in records),"removed_repeated_lines":len(repeated)}; (output/"cleaning_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
