#!/usr/bin/env python3
"""Extract structured knowledge from source chunks grouped by manual chapters."""
import argparse, json, os, time
from pathlib import Path
import httpx, yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError

class KnowledgeRecord(BaseModel):
    model_config=ConfigDict(extra="forbid")
    record_type:str; id:str=Field(min_length=1); name:str=""; description:str=""; data:dict=Field(default_factory=dict); source_refs:list[str]=Field(min_length=1); pages:list[int]=Field(default_factory=list); confidence:float=Field(ge=0,le=1); verification_status:str="llm_extracted"; chapter_id:str=""; chapter_title:str=""

def parse_json(text):
    text=text.strip().strip('`').strip()
    if text.lower().startswith('json'): text=text[4:].strip()
    return json.loads(text)

def extract(http,model,batch,chapter):
    schema={"records":[{"record_type":"component|function|relationship|operation|state|parameter|workflow","id":"stable_snake_case_id","name":"","description":"","data":{},"source_refs":["#/texts/1"],"pages":[1],"confidence":0.0,"verification_status":"llm_extracted"}]}
    prompt=f'''你是 Rigol DHO804 说明书知识提取器。当前章节是 {chapter['id']}：{chapter.get('title','')}。只从来源 chunks 中提取明确出现或明确描述的设备知识，不要补充常识，不要猜测，不要把用户设备状态当作说明书事实。Return valid json only。
可以提取 record_type：component、function、relationship、operation、state、parameter、workflow。
每条记录必须保留 source_refs；source_refs 只能使用输入 chunks 的 source_refs；pages 使用输入页面；没有可靠知识时返回空 records；不要输出 Markdown。
输出格式：{json.dumps(schema,ensure_ascii=False)}
来源 chunks：{json.dumps(batch,ensure_ascii=False)}'''
    response=http.post('chat/completions',json={"model":model,"messages":[{"role":"system","content":"你是严谨的设备说明书知识提取器。"},{"role":"user","content":prompt}],"response_format":{"type":"json_object"}}); response.raise_for_status(); return parse_json(response.json()['choices'][0]['message']['content'])

def chapter_for(page,chapters):
    for chapter in chapters:
        if any(int(a)<=page<=int(b) for a,b in chapter.get('page_ranges',[])): return chapter
    return None

def main():
    p=argparse.ArgumentParser(description='按 manual.yaml 章节提取 DHO804 结构化知识'); p.add_argument('--input',default='data/index/DHO804/source_chunks.jsonl'); p.add_argument('--config',default='config/manual.yaml'); p.add_argument('--output-dir',default='data/knowledge/DHO804/manual_extracted'); p.add_argument('--chunks-per-request',type=int,default=5); p.add_argument('--chapters',default=''); p.add_argument('--dry-run',action='store_true'); args=p.parse_args(); load_dotenv()
    chunks=[json.loads(line) for line in Path(args.input).read_text(encoding='utf-8').splitlines() if line]; config=yaml.safe_load(Path(args.config).read_text(encoding='utf-8')) or {}; chapters=config.get('normalize_scope',{}).get('chapters',[]); selected={x.strip() for x in args.chapters.split(',') if x.strip()}; chapters=[x for x in chapters if not selected or x.get('id') in selected]
    grouped={chapter['id']:[] for chapter in chapters}; unassigned=[]
    for chunk in chunks:
        pages=chunk.get('pages',[]); chapter=chapter_for(pages[0],chapters) if pages else None
        if chapter: grouped[chapter['id']].append(chunk)
        else: unassigned.append(chunk)
    if args.dry_run:
        print(json.dumps({'chapters':{x:len(y) for x,y in grouped.items()},'unassigned':len(unassigned)},ensure_ascii=False,indent=2)); return
    key=os.getenv('RIGOL_API_KEY'); base=(os.getenv('RIGOL_BASE_URL') or '').rstrip('/')+'/'; model=os.getenv('RIGOL_MODEL')
    if not key or not model: raise SystemExit('请配置 RIGOL_API_KEY 和 RIGOL_MODEL')
    output_dir=Path(args.output_dir); output_dir.mkdir(parents=True,exist_ok=True); http=httpx.Client(base_url=base,headers={'Authorization':f'Bearer {key}'},timeout=120); all_records=[]; report={}
    try:
        for chapter in chapters:
            chapter_id=chapter['id']; chapter_chunks=grouped[chapter_id]; chapter_path=output_dir/f'knowledge_{chapter_id}.jsonl'; chapter_records=[]; chapter_errors=[]
            if chapter_path.exists(): chapter_path.unlink()
            stream=chapter_path.open('a',encoding='utf-8')
            try:
                for start in range(0,len(chapter_chunks),args.chunks_per_request):
                    batch=chapter_chunks[start:start+args.chunks_per_request]; allowed={ref for chunk in batch for ref in chunk.get('source_refs',[])}
                    try:
                        result=extract(http,model,batch,chapter)
                        for raw in result.get('records',[]):
                            if not set(raw.get('source_refs',[])) <= allowed: raise ValueError('source_refs 不属于当前章节 batch')
                            raw['chapter_id']=chapter_id; raw['chapter_title']=chapter.get('title',''); record=KnowledgeRecord.model_validate(raw).model_dump(mode='json'); chapter_records.append(record); all_records.append(record); stream.write(json.dumps(record,ensure_ascii=False)+'\n'); stream.flush()
                        print(f'{chapter_id}: {min(start+args.chunks_per_request,len(chapter_chunks))}/{len(chapter_chunks)} records={len(result.get("records",[]))}')
                    except httpx.HTTPStatusError as exc:
                        detail=exc.response.text[:1000].replace(key,'<redacted>'); chapter_errors.append({'start':start,'error':f'HTTP {exc.response.status_code}: {detail}'}); print(f'{chapter_id}: HTTP {exc.response.status_code}')
                    except (httpx.HTTPError,KeyError,TypeError,ValueError,ValidationError) as exc:
                        chapter_errors.append({'start':start,'error':str(exc)}); print(f'{chapter_id}: error {exc}')
                    time.sleep(.2)
            finally: stream.close()
            report[chapter_id]={'title':chapter.get('title',''),'chunks':len(chapter_chunks),'records':len(chapter_records),'errors':chapter_errors,'output':str(chapter_path)}
    finally: http.close()
    merged=output_dir/'knowledge_records.jsonl'; merged.write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in all_records)+'\n',encoding='utf-8'); (output_dir/'knowledge_records.report.json').write_text(json.dumps({'chapters':report,'unassigned_chunks':len(unassigned),'total_records':len(all_records)},ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'output':str(merged),'records':len(all_records),'unassigned_chunks':len(unassigned)},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
