# DHO804 说明书资料

请将 Rigol DHO804 的原始 PDF 放在本目录，例如：

```text
data/manuals/DHO804/Rigol_DHO804_User_Guide.pdf
```

建议同时保留原始 PDF、文件版本和下载来源、说明书语言、下载日期、适用设备型号和固件版本。

不要把解析后的 Markdown、图片或索引文件放在这里。解析产物分别放到：

```text
data/parsed/DHO804/
data/index/DHO804/
data/knowledge/DHO804/
```

Phase 2 支持两种章节范围：

```text
parse scope      解析时选择哪些章节或页码
retrieval scope  检索时限定哪些章节或来源
```

默认建议先解析全部章节并保留来源信息，再在检索时限定范围。如果 PDF 很大或只希望先做测量功能，也可以先解析指定章节。
