# Knowledge

```text
data/knowledge/DHO804/
├── components.yaml
├── operations.yaml
├── workflows.yaml
├── constraints.yaml
├── metadata.yaml
└── visual_targets.yaml
```

`DHO804` 是当前设备知识。`visual_targets.yaml` 服务 Qwen3-VL，将逻辑组件映射到图像中的视觉证据。

旧执行器兼容映射位于：

```text
data/knowledge/legacy/tasklist_mapping.yaml
```

它不参与 Phase 1 视觉定位。

说明书解析完成后，来源、组件关系、界面状态和视觉示例应进入 `data/knowledge/DHO804/` 或检索索引，不要直接把整本说明书拼入 Prompt。
