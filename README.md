# Rigol Visual Agent

面向 Rigol DHO804 的知识驱动视觉观察 Agent。当前仓库聚焦 Phase 3：把说明书知识、LLM 操作计划和 Qwen3-VL 图片识别连接起来，输出当前界面状态、目标组件 bbox 和可验证的状态变化。

## 当前主链路

```text
自然语言目标
  → 说明书知识检索
  → OperationPlan
  → 当前图片和单步目标
  → Qwen3-VL 界面/组件识别
  → 原图 bbox、observed_state、evidence
  → 点击坐标准备和前后状态验证
```

当前只做识别和动作准备。已支持只读订阅外部视觉端的裁切屏幕帧；暂不发布 ROS2 点击或连接机械臂执行。旋钮旋转、插拔和接线会返回人工完成提示。

## 主要入口

```bash
# 查看知识摘要
python3 scripts/search_knowledge.py "测量 CH2 的峰峰值" --type operation --limit 5

# 生成操作计划
python3 scripts/plan_operation.py "测量 CH2 的峰峰值"

# 识别界面并框选目标
python3 scripts/inspect_agent.py \
  --image /home/ubuntu/RIGOL/datasets/images/000001.jpg \
  --query "打开通道2,打开测量界面"

# 从外部视觉端 /vision_srv/camera/rgb_screen 捕获一帧后识别
python3 scripts/inspect_agent.py \
  --live \
  --query "打开通道2,打开测量界面"

# 单目标定位
python3 scripts/locate_component.py \
  --image /home/ubuntu/RIGOL/datasets/images/000001.jpg \
  --target CH2 \
  --state any
```

识别结果保存为 JSON 和带框图片，默认位于 `data/perception_results/`。

## 配置

`.env` 中配置 Qwen3-VL：

```env
QWEN_VL_API_KEY=
QWEN_VL_BASE_URL=
QWEN_VL_MODEL=
QWEN_VL_COORDINATE_MODE=auto
```

`auto` 兼容当前 Qwen 服务常见的 0～1000 bbox 坐标；供应商明确返回原图像素时可设置为 `pixel`。

## 视觉知识配置

设备相关的别名、中文标签、组件布局、状态规则、界面状态提示和操作 prompt 位于：

```text
data/knowledge/DHO804/visual_knowledge.yaml
```

新增组件或调整视觉 prompt 优先修改这个 YAML。`perception/target_knowledge.py` 和 `knowledge/visual_knowledge.py` 负责加载配置。

## 目录

```text
agent/       LLM 和 Phase 3 闭环编排
execution/   点击准备、能力边界、状态验证
knowledge/   说明书知识记录、检索和视觉知识加载
models/      Observation、OperationPlan、视觉数据模型
perception/  Qwen3-VL、目标描述、单步观察、坐标转换
planning/    OperationPlanner
scripts/     说明书处理、知识检索、计划和视觉测试命令
integration/ 外部 ROS2 视觉帧只读桥接
data/        PDF、解析结果、知识记录和视觉配置
docs/        Phase 1、Phase 2、Phase 3 文档
tests/       当前 Phase 3 自动测试
```

说明书处理流程见 [docs/PHASE2_MANUAL_KNOWLEDGE.md](docs/PHASE2_MANUAL_KNOWLEDGE.md)，Phase 3 总结见 [docs/PHASE3_KNOWLEDGE_PERCEPTION.md](docs/PHASE3_KNOWLEDGE_PERCEPTION.md)。

迁移到旧设备时查看 [docs/MIGRATION_HANDOFF.md](docs/MIGRATION_HANDOFF.md)。

## 验证

```bash
python3 -m pytest -q tests/test_knowledge_retrieval.py tests/test_phase3_operation.py
python3 -m compileall -q agent execution knowledge models perception planning tools scripts
```
