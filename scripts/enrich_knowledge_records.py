#!/usr/bin/env python3
"""Resolve source_refs in extracted knowledge records and attach page media."""
import argparse, json
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description='补充知识记录的来源文本、页码和图片')
    parser.add_argument('--input-dir',default='data/knowledge/DHO804/chapter_results')
    parser.add_argument('--pattern',default='chapter_*/knowledge_records.jsonl')
    parser.add_argument('--docling',default='data/parsed/DHO804/docling_document.json')
    parser.add_argument('--output',default='data/knowledge/DHO804/knowledge_records.jsonl')
    args=parser.parse_args()
    root=Path(args.input_dir); document=json.loads(Path(args.docling).read_text(encoding='utf-8')); elements={}
    for key in ('texts','tables','pictures'):
        for item in document.get(key,[]): elements[item.get('self_ref')]=item
    pictures_by_page={}
    image_root=Path(args.docling).parent/'docling_images'
    for index,picture in enumerate(document.get('pictures',[]),1):
        path=image_root/f'figure_{index:04d}.png'
        item={'picture_ref':picture.get('self_ref'),'path':str(path) if path.exists() else None,'pages':sorted({p.get('page_no') for p in picture.get('prov',[]) if p.get('page_no') is not None}),'bbox':[p.get('bbox') for p in picture.get('prov',[]) if p.get('bbox') is not None]}
        for page in item['pages']: pictures_by_page.setdefault(page,[]).append(item)
    files=sorted(root.glob(args.pattern)); total=0; all_rows=[]
    for path in files:
        rows=[]
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line.strip(): continue
            record=json.loads(line); refs=record.get('source_refs',[]); source_elements=[]; pages=set(); source_images=[]; source_tables=[]; source_text=[]
            for ref in refs:
                item=elements.get(ref)
                if not item:
                    source_elements.append({'source_ref':ref,'status':'missing'}); continue
                provenance=item.get('prov',[]); item_pages=sorted({p.get('page_no') for p in provenance if p.get('page_no') is not None}); pages.update(item_pages)
                kind='text' if ref.startswith('#/texts/') else 'table' if ref.startswith('#/tables/') else 'picture' if ref.startswith('#/pictures/') else 'unknown'
                entry={'source_ref':ref,'type':kind,'pages':item_pages,'bbox':[p.get('bbox') for p in provenance if p.get('bbox') is not None]}
                if kind=='text': entry['text']=item.get('text') or item.get('orig') or ''; source_text.append(entry)
                elif kind=='table':
                    cells=item.get('data',{}).get('table_cells',[]); entry['rows']=[cell.get('text','') for cell in cells]; source_tables.append(entry)
                elif kind=='picture': source_images.extend(x for x in pictures_by_page.get(item_pages[0],[]) if x['picture_ref']==ref) if item_pages else None
                source_elements.append(entry)
            page_images=[]
            for page in sorted(pages):
                page_images.extend(pictures_by_page.get(page,[]))
            unique={x['picture_ref']:x for x in [*source_images,*page_images] if x.get('path')}
            record['source_elements']=source_elements; record['source_pages']=sorted(pages); record['source_text']=source_text; record['source_tables']=source_tables; record['source_images']=source_images; record['page_context_images']=list(unique.values()); rows.append(record); all_rows.append(record); total+=1
    output=Path(args.output); output.parent.mkdir(parents=True,exist_ok=True); output.write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in all_rows)+'\n',encoding='utf-8')
    print(json.dumps({'files':len(files),'records':total,'output':str(output)},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
