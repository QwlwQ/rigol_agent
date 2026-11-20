# Phase 2：DHO804 说明书解析与知识提取

## 1. 当前目标

Phase 2 当前目标是：

~~~text
DHO804 PDF
  → PyMuPDF/Docling 解析
  → 页面和图片证据保留
  → source_chunks.jsonl
  → DeepSeek 知识提取
  → knowledge_records.jsonl
  → 基础知识检索
~~~

当前不执行：

- DeepSeek 文档结构归一化；
- ROS2、Qt 和机械臂执行；
- Qwen3-VL 状态闭环；
- 正式知识审核工作流。

文档结构归一化曾经测试过，但结果对当前 PDF 改善不明显，并且部分标题和内容出现错乱，因此暂时停用。原始 Docling JSON 保留，不再使用归一化结果作为 Phase 2 主流程。

## 2. 输入和依赖

PDF：

~~~text
data/manuals/DHO804/DHO804.pdf
~~~

依赖：

~~~text
Docling 2.150.1
PyMuPDF 1.28.2
~~~

## 3. 原始解析和 PyMuPDF 预处理

解析：

~~~bash
python3 scripts/parse_manual.py --pdf data/manuals/DHO804/DHO804.pdf --config config/manual.yaml --output data/parsed/DHO804 --docling
~~~

预处理：

~~~bash
python3 scripts/clean_manual.py --input data/parsed/DHO804 --output data/parsed/DHO804_clean --copy-selected-images
~~~

PyMuPDF 结果保存页面、文本块、图片、bbox、哈希和来源。原始解析目录不覆盖。

## 4. 生成 source chunks

当前 source chunks 位于：

~~~text
data/index/DHO804/source_chunks.jsonl
~~~

每行一个 JSON chunk，保留文本、页面、source_refs、表格、图片引用和 verification_status。

## 5. DeepSeek 知识提取

知识提取脚本：

~~~text
scripts/extract_knowledge.py
~~~

脚本按 config/manual.yaml 的章节范围分组，每章单独提取，结果保存在：

~~~text
data/knowledge/DHO804/manual_extracted/chapter_results/
~~~

DeepSeek 配置：

~~~env
RIGOL_API_KEY=新的DeepSeek_API_Key
RIGOL_MODEL=deepseek-flash
RIGOL_BASE_URL=https://api.deepseek.com
~~~

知识提取命令：

~~~bash
python3 scripts/extract_knowledge.py --input data/index/DHO804/source_chunks.jsonl --config config/manual.yaml --output-dir data/knowledge/DHO804/manual_extracted --chunks-per-request 5
~~~

输出记录包含 record_type、id、name、description、data、chapter_id、chapter_title、source_refs、pages、confidence 和 verification_status。

## 6. 来源补全

说明书提取结果通过 source_refs 关联回原始 Docling JSON：

~~~bash
python3 scripts/enrich_knowledge_records.py --input-dir data/knowledge/DHO804/manual_extracted/chapter_results --pattern 'chapter_*/knowledge_records.jsonl' --docling data/parsed/DHO804/docling_document.json --output data/knowledge/DHO804/manual_extracted/knowledge_records.jsonl
~~~

最终知识文件：

~~~text
data/knowledge/DHO804/manual_extracted/knowledge_records.jsonl
~~~

记录会补充 source_elements、source_pages、source_text、source_tables、source_images 和 page_context_images。

Phase 2 不设置 verified 中间层，当前直接使用 manual_extracted/knowledge_records.jsonl。

## 7. 基础知识检索

~~~bash
python3 scripts/search_knowledge.py "测量 峰峰值" --type operation --limit 5
~~~

检索代码：

~~~text
knowledge/manual_repository.py
knowledge/retrieval/knowledge_retriever.py
~~~

当前是关键词检索，后续再根据需要增加语义检索和操作 Schema 约束。

## 8. 当前 Phase 2 状态

已完成：

- PDF 解析；
- PyMuPDF 页面和图片证据；
- Docling 原始结构；
- source chunks；
- 按章节 DeepSeek 知识提取；
- 说明书知识记录；
- 来源文本、表格、页码和图片上下文补全；
- 基础知识检索。

暂缓：

- DeepSeek Docling 结构归一化；
- Fuse；
- 复杂知识审核；
- 向量检索。

## 9. Phase 3 入口

Phase 3 的正式文档见：[PHASE3_KNOWLEDGE_PERCEPTION.md](PHASE3_KNOWLEDGE_PERCEPTION.md)。

Phase 3 将读取：

~~~text
data/knowledge/DHO804/manual_extracted/knowledge_records.jsonl
~~~

流程：

~~~text
用户自然语言
  → Knowledge Retriever
  → 找到 operation/function/state/component
  → 生成 required_observations
  → Qwen3-VL 定位组件和状态
  → 判断界面是否满足前置条件
~~~

Phase 3 的第一步是把知识记录统一为可检索的 Operation、State 和 Observation 结构。
