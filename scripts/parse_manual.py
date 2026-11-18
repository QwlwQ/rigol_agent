#!/usr/bin/env python3
"""Phase 2 manual parser: PyMuPDF extraction with optional Docling output."""
import argparse, json
from pathlib import Path
import yaml

def in_ranges(page, ranges): return not ranges or any(int(a) <= page <= int(b) for a,b in ranges)
def matches(text, include, exclude):
    lower=text.casefold()
    return (not include or any(str(x).casefold() in lower for x in include)) and not any(str(x).casefold() in lower for x in exclude)

def pymupdf_parse(pdf, out, scope):
    try: import fitz
    except ImportError as exc: raise RuntimeError("请安装 requirements-phase2.txt 中的 PyMuPDF") from exc
    pages=out/'pages'; texts=out/'text'; images=out/'images'
    for directory in (pages,texts,images): directory.mkdir(parents=True,exist_ok=True)
    records=[]
    with fitz.open(pdf) as document:
        for index,page in enumerate(document):
            number=index+1; text=page.get_text('text')
            if not in_ranges(number,scope.get('page_ranges',[])) or not matches(text,scope.get('include_patterns',[]),scope.get('exclude_patterns',[])): continue
            extracted=[]; seen=set()
            for image_index, info in enumerate(page.get_image_info(xrefs=True),1):
                xref=info.get('xref')
                if xref in seen: continue
                seen.add(xref); image=document.extract_image(xref)
                path=images/f'page_{number:04d}_image_{image_index:03d}.{image["ext"]}'; path.write_bytes(image['image'])
                extracted.append({'path':str(path),'xref':xref,'bbox':list(info.get('bbox',())),'width':info.get('width'),'height':info.get('height')})
            record={'source_file':str(pdf),'page_number':number,'text':text,'text_blocks':page.get_text('blocks'),'images':extracted,'source':{'file':str(pdf),'page':number}}
            (pages/f'page_{number:04d}.json').write_text(json.dumps(record,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
            (texts/f'page_{number:04d}.txt').write_text(text,encoding='utf-8')
            records.append({'page_number':number,'text_chars':len(text),'image_count':len(extracted)})
    summary={'source_file':str(pdf),'pages_selected':len(records),'pages':records,'scope':scope}; (out/'pymupdf_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); return summary

def docling_parse(pdf,out):
    try:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions, HeadingHierarchyOptions
        from docling_core.types.doc import ImageRefMode
    except ImportError as exc: raise RuntimeError("请安装 requirements-phase2.txt 中的 Docling") from exc
    pipeline=PdfPipelineOptions(do_ocr=False,do_table_structure=True,generate_page_images=True,generate_picture_images=True,use_embedded_picture_images=True,images_scale=1.5,heading_hierarchy_options=HeadingHierarchyOptions(enabled=True,use_bookmarks=True,use_numbering=True,use_style=True,use_font_style=True))
    converter=DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline)})
    document=converter.convert(str(pdf)).document
    (out/'docling_document.json').write_text(json.dumps(document.export_to_dict(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    document.save_as_markdown(out/'document.md',image_mode=ImageRefMode.REFERENCED)
    figures=out/'docling_images'; figures.mkdir(parents=True,exist_ok=True)
    for index,picture in enumerate(document.pictures,1):
        image=picture.get_image(document)
        if image is not None: image.save(figures/f'figure_{index:04d}.png')

def main():
    parser=argparse.ArgumentParser(description='解析 DHO804 说明书'); parser.add_argument('--pdf',default='data/manuals/DHO804/DHO804.pdf'); parser.add_argument('--config',default='config/manual.yaml'); parser.add_argument('--output',default='data/parsed/DHO804'); parser.add_argument('--docling',action='store_true'); args=parser.parse_args()
    pdf=Path(args.pdf); out=Path(args.output); config=yaml.safe_load(Path(args.config).read_text(encoding='utf-8')) or {}
    if not pdf.is_file(): raise SystemExit(f'PDF 不存在：{pdf}')
    summary=pymupdf_parse(pdf,out,config.get('parse_scope',{}))
    if args.docling: docling_parse(pdf,out); summary['docling']=True
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
