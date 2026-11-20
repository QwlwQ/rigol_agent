from knowledge.manual_repository import ManualKnowledgeRepository
from knowledge.retrieval.knowledge_retriever import KnowledgeRetriever
from tools.registry import ToolRegistry, Tool

def test_manual_repository_search_returns_source_records(tmp_path):
    path=tmp_path/'knowledge.jsonl'
    path.write_text('{"record_type":"operation","id":"measure_peak","name":"测量峰峰值","chapter_id":"chapter_10","source_refs":["#/texts/1"],"confidence":0.9}\n',encoding='utf-8')
    records=ManualKnowledgeRepository(path).search('测量 峰峰值',record_type='operation')
    assert records[0]['id']=='measure_peak'

def test_knowledge_search_tool_schema_and_call():
    retriever=KnowledgeRetriever.__new__(KnowledgeRetriever)
    retriever.search=lambda query,**kwargs: [{"id":"x","query":query}]
    registry=ToolRegistry()
    from tools.registry import Tool
    registry.register(Tool('search_knowledge','search',{'type':'object'},lambda query,record_type=None,chapter_id=None,limit=5: retriever.search(query)))
    assert registry.call('search_knowledge',{'query':'测量','record_type':None,'chapter_id':None,'limit':5})[0]['id']=='x'
