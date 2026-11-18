# Phase 2：DHO804 说明书解析与知识块准备

Phase 2 当前只完成到 LLM 结构化知识提取之前。

当前目标是：

```text
DHO804 PDF
  → PyMuPDF 原始页面证据
  → Docling 文档结构
  → 分别清洗
  → 页面级融合
  → 人工 Markdown 预览
  → 生成完整知识块
```

当前不执行：

- LLM 结构化知识提取；
- 自动写入正式组件、操作或状态知识；

文档中的 Shell 多行命令使用单个反斜杠作为续行符：

```bash
python3 scripts/parse_manual.py \
  --pdf data/manuals/DHO804/DHO804.pdf \
  --output data/parsed/DHO804
```

反斜杠必须是每一行最后一个字符，不能写成 `\\`。
- ROS2、Qt 或机械臂操作。

## 1. 原始 PDF

文件位置：

```text
data/manuals/DHO804/DHO804.pdf
```

原始 PDF 不修改。解析和清洗结果放在 `data/parsed/DHO804/` 及其派生目录。

## 2. 解析工具职责

当前 Docling 解析入口已显式开启：

- `heading_hierarchy_options`：使用书签、章节编号和字体样式推断标题层级；
- `generate_picture_images`：导出图片元素；
- `generate_page_images`：保留页面渲染图；
- `use_embedded_picture_images`：适用时使用 PDF 内嵌图片；
- `do_table_structure`：解析表格结构。

当前 Docling 版本中标题层级推断默认关闭，因此不能直接信任原始 `level=1`；重新解析时应使用当前入口配置，再结合 `clean_docling.py` 的归一化结果。

当前解析入口还会：

- 使用 `ImageRefMode.REFERENCED` 导出 Markdown 图片引用；
- 将 Docling 图片保存到 `data/parsed/DHO804/docling_images/`；
- 保留原始 Docling JSON，不覆盖原始解析结果。

### PyMuPDF

负责底层页面证据：

- 页码；
- 页面文本；
- 文本块和坐标；
- 嵌入图片；
- 图片页面 bbox；
- 原始页面来源。

### Docling

负责文档结构：

- 标题和章节层级；
- 正文元素；
- 表格；
- 图片元素；
- 元素 provenance；
- Docling JSON。

两者不是二选一：PyMuPDF 保存页面级证据，Docling 提供结构，之后通过 `fuse_manual.py` 合并。

## 3. 解析命令

安装 Phase 2 依赖：

```bash
source .venv/bin/activate
pip install -r requirements-phase2.txt
```

解析 PDF：

```bash
python3 scripts/parse_manual.py \
  --pdf data/manuals/DHO804/DHO804.pdf \
  --config config/manual.yaml \
  --output data/parsed/DHO804
```

如果还没有 Docling JSON，则运行：

```bash
python3 scripts/parse_manual.py \
  --pdf data/manuals/DHO804/DHO804.pdf \
  --config config/manual.yaml \
  --output data/parsed/DHO804 \
  --docling
```

原始解析输出：

```text
data/parsed/DHO804/
├── pages/
├── text/
├── images/
├── pymupdf_summary.json
├── docling_document.json
└── document.md
```

`document.md` 只用于初步人工浏览，不是最终知识输入。

重新解析 Docling 后应检查：

```text
data/parsed/DHO804/docling_document.json
data/parsed/DHO804/document.md
data/parsed/DHO804/docling_images/
```

重点检查标题 `level` 是否出现 1、2、3 等层级，Markdown 是否包含图片引用，以及图片文件是否实际生成。

## Docling 是否需要 GPU

GPU 不是 Docling 的必需条件。CPU 可以完成 PDF 解析，但 DHO804 这类 234 页、图片和表格较多的说明书，Docling 运行较慢是正常现象。

当前配置中：

```text
do_ocr=False
do_table_structure=True
generate_page_images=True
generate_picture_images=True
```

主要耗时来源包括页面布局分析、表格结构识别、图片/页面渲染、图片写入以及模型首次下载和加载。

先检查当前虚拟环境是否有可用 CUDA：

```bash
python3 -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

判断原则：

```text
CUDA 不可用
  → 使用 CPU，功能不受影响，只是更慢

CUDA 可用且需要反复解析
  → 建议配置 GPU

只解析一次且 PDF 为数字文本
  → 可以先用 CPU 完成
```

当前 DHO804 PDF 是数字说明书，已经关闭 OCR，因此不需要为了 OCR 单独配置 GPU。GPU 配置仍应根据当前 Docling 版本的 `accelerator_options` 确认，不能直接套用其他版本参数。

## 4. 清洗

### 4.1 清洗 PyMuPDF 结果

```bash
python3 scripts/clean_manual.py \
  --input data/parsed/DHO804 \
  --output data/parsed/DHO804_clean \
  --copy-selected-images
```

清洗结果保留页面关系：

```text
data/parsed/DHO804_clean/
├── pages/
├── text/
├── images_selected/
├── image_manifest.jsonl
└── cleaning_summary.json
```

图片过滤只标记或复制筛选结果，不修改原始图片。过滤依据包括：尺寸、面积、长宽比和重复哈希。小图标、横线、语言标志和重复模板图片通常会被标记为 `likely_decoration`。

### 4.2 清洗 Docling 结果

```bash
python3 scripts/clean_docling.py \
  --input data/parsed/DHO804/docling_document.json \
  --output data/parsed/DHO804_clean/docling_document_clean.json
```

该步骤保留 Docling JSON 的结构，并标记高频重复模板文本。Docling 的表格不会在此阶段删除。

清洗阶段不会直接信任 Docling 原始的 `level`。当前 PDF 中候选标题的原始 level 可能全部为 `1`，并且部分“警告”“注意”、项目符号句子或表格标题会被标成 `section_header`。

因此 `clean_docling.py` 会增加：

```text
normalized_role
normalized_level
normalization_reason
```

归一化规则优先使用章节编号：

```text
1          → level 1
1.1        → level 2
4.3.1      → level 3
```

同时排除明显的提示语、项目符号和句子型文本。原始 `label`、`level` 和文本仍然保留，归一化结果只作为 Fuse 和章节路径生成的输入。

## 5. 人工预览

在融合前查看 Docling 清洗结果：

```bash
python3 scripts/export_manual_preview.py \
  --input data/parsed/DHO804_clean/docling_document_clean.json \
  --output data/parsed/DHO804_clean/docling_clean_preview.md \
  --format docling
```

融合后再次查看页面级结果：

```bash
python3 scripts/export_manual_preview.py \
  --input data/parsed/DHO804_fused/fused_document.json \
  --output data/parsed/DHO804_fused/fused_preview.md \
  --format fused
```

Markdown 预览用于检查：

- 目录是否被误当成正文；
- 章节层级是否合理；
- 页眉、页脚和重复文本是否过多；
- 表格内容是否保留；
- 图片是否关联到正确页码；
- 图片过滤是否误删有用示例；
- PyMuPDF 和 Docling 内容是否正确合并。

Markdown 不是最终知识库来源。

## 6. 融合

```bash
python3 scripts/fuse_manual.py \
  --pymupdf data/parsed/DHO804_clean \
  --docling data/parsed/DHO804_clean/docling_document_clean.json \
  --output data/parsed/DHO804_fused/fused_document.json
```

输出：

```text
data/parsed/DHO804_fused/fused_document.json
```

这是一个完整的 JSON 文件，按页面保存：

```text
页面编号
章节路径
文本元素
表格元素
图片元素
bbox
来源工具
```

融合原则：

1. 通过 PDF 页码对齐 PyMuPDF 和 Docling；
2. Docling 提供章节、文本和表格结构；
3. PyMuPDF 提供原始页面和图片证据；
4. 不覆盖原始结果；
5. 每个元素保留来源；
6. 图片只保留筛选后的图片引用；
7. 发现冲突时保留来源并标记，不静默覆盖。

## 7. 创建完整知识块

融合完成并人工检查通过后，生成整本说明书的知识块：

```bash
python3 scripts/build_manual_chunks.py \
  --input data/parsed/DHO804_fused \
  --output data/index/DHO804/chunks.jsonl
```

当前脚本默认处理完整说明书，不限制“测量”或其他章节。

可选的范围过滤只用于实验：

```bash
python3 scripts/build_manual_chunks.py \
  --input data/parsed/DHO804_fused \
  --output data/index/DHO804/chunks_measurement.jsonl \
  --include 测量 \
  --include Measurement \
  --exclude 维修 \
  --pages 40-70
```

## 8. JSON 和 JSONL 的区别

当前最终输出不是一个单独的 `chunks.json`，而是：

```text
data/index/DHO804/chunks.jsonl
```

它是 JSON Lines 格式：

```text
第 1 行：一个 JSON chunk
第 2 行：一个 JSON chunk
第 3 行：一个 JSON chunk
```

例如：

```json
{"chunk_id":"fused_00001","pages":[1],"text":"..."}
{"chunk_id":"fused_00002","pages":[2],"text":"..."}
```

选择 JSONL 是因为它适合：

- 按行读取；
- 分批调用 LLM；
- 单个 chunk 失败后重试；
- 后续建立检索索引；
- 追加处理结果。

两者的定位不同：

```text
fused_document.json
    完整页面级融合文档，一个 JSON

chunks.jsonl
    面向后续 LLM 提取的多个知识块，每行一个 JSON
```

## 9. LLM 提取之前的最终检查

在执行 LLM 知识提取前，应确认：

```text
docling_clean_preview.md   已检查
fused_preview.md           已检查
fused_document.json        已生成
chunks.jsonl               已生成
```

此时才进入：

```text
chunks.jsonl
  → DeepSeek 结构化提取
  → Pydantic Schema 校验
  → 人工审核
  → 正式 DHO804 知识库
```
