# Rigol Agent 迁移交接：新设备 → 旧设备

本文给旧设备上的 Codex 使用。当前仓库工作区包含大量 Phase 2/3 改动和有意删除的旧代码，迁移时不要执行 `git reset --hard`，也不要恢复旧 workflow/taskList 文件。

## 1. 目标路径

旧设备用户名是 `cjailab`。迁移后的路径约定：

```text
Agent 项目：
/home/cjailab/rigol_agent

数据集：
/home/cjailab/RIGOL/datasets/images

Qt 客户端：
/home/cjailab/RIGOL/RIGOL_AITestClient-deploy

视觉端 ROS2 工作空间：
/home/cjailab/RIGOL/ws_siasun-1.3

机械臂控制端：
/home/cjailab/grasp_demo
```

当前文档中的 `/home/ubuntu` 是新设备上的示例路径。旧设备运行命令时统一替换为 `/home/cjailab`。

## 2. 当前项目状态

当前 Phase 3 主链路已经完成：

```text
自然语言目标
  → KnowledgeRetriever
  → ObservationTarget
  → OperationPlan
  → Qwen3-VL 界面状态识别
  → 目标组件 bbox、observed_state、confidence、evidence
```

当前支持：

- 说明书 JSONL 知识检索；
- 中文别名，例如“通道2”→ `CH2`；
- 操作顺序和预期状态生成；
- Qwen3-VL 界面状态识别；
- Qwen3-VL 组件 bbox 定位；
- 原图坐标和 Qwen 0～1000 坐标转换；
- 前后状态验证模型；
- 只读 ROS2 裁切屏幕帧读取；
- 旋钮、插拔和接线动作的人工完成提示。

当前不做：

- 自动点击；
- ROS2 `/vision_srv/click_task` 发布；
- 机械臂动作；
- 旋钮旋转和插拔；
- 自动失败恢复。

## 3. 关键入口

```bash
cd /home/cjailab/rigol_agent
source .venv/bin/activate

# 静态图片识别
python3 scripts/inspect_agent.py \
  --image /home/cjailab/RIGOL/datasets/images/000001.jpg \
  --query "打开通道2,打开测量界面"

# 生成操作计划
python3 scripts/plan_operation.py "测量 CH2 的峰峰值"

# 知识检索
python3 scripts/search_knowledge.py \
  "测量 CH2 的峰峰值" \
  --type operation \
  --limit 5
```

Qwen 配置在 `.env`，迁移时需要安全复制或重新配置：

```env
QWEN_VL_API_KEY=
QWEN_VL_BASE_URL=
QWEN_VL_MODEL=
QWEN_VL_COORDINATE_MODE=auto
```

不要把 `.env` 提交到 Git。

## 4. 当前视觉配置

设备组件别名、中文标签、布局描述、状态规则和 prompt 调优在：

```text
data/knowledge/DHO804/visual_knowledge.yaml
```

发现目标描述不准时，优先修改 YAML，不要先改 Python。

## 5. 外部视觉端接入

Agent 的只读实时帧桥接位于：

```text
integration/vision_frame_source.py
```

它订阅：

```text
/vision_srv/camera/rgb_screen
```

启动视觉工作空间后运行：

```bash
source /opt/ros/humble/setup.bash
source /home/cjailab/RIGOL/ws_siasun-1.3/ws_siasun-1.3/install/setup.bash

ros2 topic list | grep '/vision_srv/camera/rgb_screen'
ros2 topic hz /vision_srv/camera/rgb_screen
```

有帧后运行 Agent：

```bash
cd /home/cjailab/rigol_agent
source .venv/bin/activate
python3 scripts/inspect_agent.py \
  --live \
  --query "打开通道2,打开测量界面"
```

此命令只读取帧并调用 Qwen，不发布点击和机械臂任务。

## 6. 视觉端和硬件注意事项

新设备上的启动失败原因已经确认：

- RealSense 和 MindVision 都挂在 USB 2.0 的 480M 链路；
- RealSense 请求 1280×720 深度和彩色 30 FPS，需要 USB 3.x；
- MindVision 的 udev 规则损坏，SDK 枚举不到相机；
- 视觉二进制依赖特定 ONNX Runtime 和 RealSense ABI。

旧设备启动前先检查：

```bash
lsusb -t
lsusb
```

RealSense 应该位于 USB 3.x 控制器（通常显示 `5000M` 或 `10000M`），不要接在 USB 2.0 Hub 后面。

视觉端外部代码位置：

```text
/home/cjailab/RIGOL/ws_siasun-1.3
```

启动命令和动态库说明见：

```text
docs/PHASE3_KNOWLEDGE_PERCEPTION.md
```

## 7. 当前已确认的 ROS2 接口

视觉端发布：

```text
/vision_srv/camera/rgb_screen
/vision_srv/camera/rgbd_screen
/vision_srv/detected_components
/vision_srv/movement_info
/vision_srv/subtask_status
```

视觉端接收点击：

```text
/vision_srv/click_task
```

点击消息支持：

```text
category_id
class_id
is_used_cord
pt.x
pt.y
```

当前 Agent 还没有发布这个消息。

## 8. 代码结构

```text
agent/       LLM 和 Phase 3 闭环编排
execution/   点击坐标准备、能力边界、状态验证
integration/ 外部 ROS2 视觉帧只读读取
knowledge/   说明书知识、检索、视觉配置加载
models/      Observation、OperationPlan、视觉数据模型
perception/  Qwen3-VL、单步观察、坐标转换
planning/    OperationPlanner
scripts/     解析、检索、计划和识别入口
tests/       当前 Phase 3 测试
```

旧 CLI、旧固定 workflow、旧 taskList、旧 ROS2 executor、旧 OCR/感知空模块已经删除，这是有意清理，不要从旧设备 Git 历史恢复。

## 9. 迁移后第一轮检查

```bash
cd /home/cjailab/rigol_agent
source .venv/bin/activate
python3 -m pytest -q
python3 -m compileall -q agent execution integration knowledge models perception planning tools scripts
```

然后先用静态图片验证 Agent，再启动视觉端测试 `--live`。只有实时帧、界面状态和 bbox 都符合预期后，才进入点击消息接入。

