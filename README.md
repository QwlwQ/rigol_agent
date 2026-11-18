# Rigol Visual Agent

面向 Rigol DHO804 的自然语言和视觉定位 Agent。当前开发按照 `new.md` 分阶段推进，当前重点是 Phase 1：使用阿里云百炼 Qwen3-VL 对示波器屏幕图片进行组件定位。

## 当前目录

```text
agent/          DeepSeek、对话和 Agent 编排
planning/       任务规划边界与当前 Planner
perception/     Qwen3-VL 图片定位
knowledge/      知识代码与扩展边界
models/         规划、视觉和执行数据模型
execution/      旧执行器适配及未来执行边界
tools/          Tool Registry
workflows/      工作流扩展边界
config/         环境无关配置
data/knowledge/ DHO804 设备知识和视觉知识
data/manuals/   说明书原始资料（待补充）
scripts/        实验和命令行脚本
tests/          自动化测试
```

根目录 `models.py` 与 `models/` 同时存在会产生路径冲突，因此当前统一使用 `models/` 包。

## Phase 1：Qwen3-VL 定位

当前链路：

```text
屏幕图片
  → Qwen3-VL
  → LocateResult
  → Bounding Box
  → JSON 和带框图片
```

当前不接入 ROS2、机械臂和旧 taskList 执行。

配置 `.env`：

```env
QWEN_VL_API_KEY=新的百炼API_Key
QWEN_VL_BASE_URL=https://ws-yf6bxq3k6up1o5y5.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
QWEN_VL_MODEL=qwen3-vl-plus
```

单图定位：

```bash
python3 scripts/locate_component.py \\
  --image /home/ubuntu/RIGOL/datasets/images/000001.jpg \\
  --target "CH2"
```

批量定性测试：

```bash
python3 scripts/evaluate_perception.py \\
  --images /home/ubuntu/RIGOL/datasets/images \\
  --targets CH2 Measure Vertical Maximum \\
  --limit 20
```

结果写入 `data/perception_eval/`。当前没有人工 Ground Truth，因此只进行人工核对，不计算正式 IoU 或准确率。

## 当前知识

当前 DHO804 知识位于：

```text
data/knowledge/DHO804/
├── components.yaml
├── operations.yaml
├── workflows.yaml
├── constraints.yaml
├── metadata.yaml
└── visual_targets.yaml
```

其中：

- `components.yaml`：逻辑组件、别名和组件类型；
- `operations.yaml`：原子动作；
- `workflows.yaml`：经过确认的高层操作流程；
- `constraints.yaml`：任务约束；
- `visual_targets.yaml`：逻辑组件到图像视觉证据的映射。

旧 `taskList` 映射位于：

```text
data/knowledge/legacy/tasklist_mapping.yaml
```

它只服务未来旧执行器兼容，不参与 Phase 1 Qwen3-VL 定位。

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

启动当前 Agent CLI：

```bash
python3 main.py
```

或安装后：

```bash
pip install -e '.[test]'
rigol-agent
```

## 测试

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q
```

ROS2、机械臂、说明书解析、OCR、状态识别和闭环执行仍按 `new.md` 的后续 Phase 实现。
