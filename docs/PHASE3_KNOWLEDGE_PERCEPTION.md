# Rigol Visual Agent：Phase 3 知识驱动操作与视觉观察

Phase 1 的单图定位和 Phase 2 的说明书解析、知识提取已经完成，本文只记录 Phase 3 如何消费这些既有产出。前置阶段的详细过程分别见 `docs/PHASE1_TEST_COMMANDS.md` 和 `docs/PHASE2_MANUAL_KNOWLEDGE.md`。

## 1. Phase 3 范围和输入

Phase 3 的输入是：

```text
用户自然语言目标
+ data/knowledge/DHO804/manual_extracted/knowledge_records.jsonl
+ 当前示波器图片
```

Phase 3 的输出是：

```text
LLM 操作计划
→ 每一步的观察目标、前置状态和预期变化
→ Qwen3-VL 界面状态和组件 bbox
→ observed_state、confidence、evidence
→ 可供点击适配器转换的原图坐标
```

当前阶段完成识别、规划和点击坐标准备；真实相机采集、ROS2 和机械臂执行仍由设备侧回调接入。

## 2. 知识检索的两种用途

### 2.1 人工检查原始记录

默认输出精简摘要：

```bash
python3 scripts/search_knowledge.py \
  "测量 CH2 的峰峰值" \
  --type operation \
  --limit 5
```

需要完整原始文本、表格和图片证据时使用：

```bash
python3 scripts/search_knowledge.py \
  "测量 CH2 的峰峰值" \
  --type operation \
  --limit 5 \
  --full
```

完整记录只用于人工审查，不应直接拼进每次 LLM prompt。

### 2.2 生成 Agent 观察目标

```bash
python3 scripts/search_knowledge.py \
  "测量 CH2 的峰峰值" \
  --type operation \
  --limit 5 \
  --plan
```

计划会把用户目标转换为：

```text
CH2
Measure
Vertical
Peak-to-Peak
```

每个目标包含逻辑名称、初始状态 `any`、视觉描述和说明书来源 ID。

中文目标会先转换为统一逻辑名称，例如：

```text
通道2 / 第二通道 → CH2
幅度值 → Amplitude
峰峰值 → Peak-to-Peak
测量 → Measure
```

逻辑目标的别名和视觉描述由设备视觉知识文件维护：

```text
data/knowledge/DHO804/visual_knowledge.yaml
```

发现同义词、中文标签、组件布局描述、状态规则或界面识别提示不准确时，优先修改这个 YAML。文件还可以维护 `screen_states`、`operations` 和通用 `prompt_rules`；其中 `operations` 会注入 LLM 操作计划 prompt。`knowledge/visual_knowledge.py` 负责加载配置，`perception/target_knowledge.py` 负责目标视觉描述。只有新增一种自然语言意图或操作类型时，才需要同步修改目标解析或操作规划代码。

## 3. LLM 操作计划

Phase 3 将“需要观察什么”和“需要怎么操作”分开。

### 3.1 LLM 负责的内容

LLM 或 `OperationPlanner` 负责：

- 理解用户目标；
- 从说明书知识中选择相关操作；
- 规划操作顺序；
- 指定每一步要观察的逻辑组件；
- 指定前置状态；
- 指定操作后的预期状态变化；
- 判断动作是点击还是需要人工完成。

LLM 不生成图片坐标。

### 3.2 操作计划示例

```bash
python3 scripts/plan_operation.py "测量 CH2 的峰峰值"
```

计划的核心步骤为：

```text
1. 观察 CH2；如果 CH2=off，点击 CH2；期望 CH2=on
2. 观察 Measure；点击后期望进入 measurement_panel
3. 观察 Vertical；点击后期望进入 measurement_vertical
4. 观察 Peak-to-Peak；点击后期望测量项启用
```

结构位于 `models/operation.py`，每个 `OperationStep` 包含：

```text
target
action
instruction
condition
preconditions
expected_changes
knowledge_record_ids
```

如果配置了文本 LLM，`agent.llm.LLMClient.plan_operation` 会让 LLM 根据精简知识摘要修正操作草案。默认 `scripts/plan_operation.py` 使用本地草案模式，不会发起网络请求。当前操作计划只描述点击、观察和人工完成，不生成图片坐标。

## 4. 单步 VLM 识别

每一步都重新获取当前图片，只向 VLM 发送当前目标和当前图片：

```text
当前图片 + 当前步骤目标描述
  → Qwen3-VL
  → 当前组件 bbox
  → observed_state
  → confidence
  → evidence
```

`KnowledgeDrivenObserver.observe_step(image, step)` 是单步接口。点击后不能复用旧图片或旧坐标，必须重新调用。`scripts/inspect_agent.py` 是不执行动作的整图识别入口。

## 5. 用真实图片做只读试验

假设图片是：

```text
/home/ubuntu/RIGOL/datasets/images/000061.jpg
```

### 5.1 识别界面并框选一个目标

```bash
python3 scripts/inspect_agent.py \
  --image /home/ubuntu/RIGOL/datasets/images/000061.jpg \
  --target CH2
```

### 5.2 同时框选多个目标

```bash
python3 scripts/inspect_agent.py \
  --image /home/ubuntu/RIGOL/datasets/images/000061.jpg \
  --target CH2 \
  --target Measure \
  --target Vertical
```

### 5.3 直接使用自然语言目标

```bash
python3 scripts/inspect_agent.py \
  --image /home/ubuntu/RIGOL/datasets/images/000061.jpg \
  --query "测量 CH2 的峰峰值"
```

主界面上的中文目标也可以直接识别：

```bash
python3 scripts/inspect_agent.py \
  --image /home/ubuntu/RIGOL/datasets/images/000001.jpg \
  --query "打开通道2,打开测量界面"
```

作为人工核对参考，当前 `000061.jpg` 画面可以看到测量面板、`Vertical` 分类和高亮的 `Maximum` 测量项，信源显示为 `CH1`；底部通道卡片中 `CH1` 处于高亮状态。该描述只用于检查 VLM 输出，不作为程序内置答案或 Ground Truth。

脚本输出：

- `screen_state`：当前界面状态；
- `components`：目标组件及 bbox；
- `observed_state`：目标当前状态；
- `confidence`：模型置信度；
- `evidence`：视觉证据；
- `annotated_image`：带框图片路径。

结果默认保存到：

```text
data/perception_results/inspect.json
data/perception_results/inspect_annotated.jpg
```

已用真实图片做过以下只读验证：

| 图片和目标 | 结果 |
| --- | --- |
| `000061.jpg` / `测量 CH2 的峰峰值` | 识别为 `measurement_vertical`，成功框出 `Measure`、`Vertical`、`Peak-to-Peak`；当前画面无法可靠确认 `CH2`，返回空 bbox 和原因说明 |
| `000001.jpg` / `打开通道2,打开测量界面` | 识别为 `main_screen`，成功框出底部关闭状态的 `CH2` 和右上角 `Measure` 按钮 |

`main_screen` 表示当前图片仍是主界面，`Measure` 框是下一步可以点击的入口，不代表测量面板已经打开。识别命令不会执行这两个动作。

脚本只做识别，不点击、不接入 ROS2、不移动机械臂。

## 6. Observation Schema

核心结构位于 `models/observation.py`：

```json
{
  "image": "000061.jpg",
  "screen_state": "measurement_vertical",
  "coordinate_space": "original_image",
  "image_size": [1290, 810],
  "components": [
    {
      "target": "CH2",
      "bbox": {
        "x_min": 100,
        "y_min": 600,
        "x_max": 250,
        "y_max": 760
      },
      "observed_state": "off",
      "confidence": 0.95,
      "evidence": ["识别到第二通道卡片"]
    }
  ]
}
```

当前支持：

```text
main_screen
measurement_panel
measurement_vertical
measurement_horizontal
measurement_other
unknown
```

状态含义按当前图片解释：

- `main_screen`：主波形和通道控制区可见，测量面板尚未展开；
- `measurement_panel`：测量面板已打开，但当前分类无法可靠确认；
- `measurement_vertical`：测量面板打开且垂直分类被选中；
- `measurement_horizontal`：测量面板打开且水平分类被选中；
- `measurement_other`：测量面板打开且其它分类被选中；
- `unknown`：图片不足以确认界面状态。

状态判断和目标定位是两次独立的视觉结果。目标组件存在时，`observed_state` 仍可能是 `unknown`；这表示位置可以确认，但开关或选中状态不够清晰。

## 7. 当前设备侧边界

当前机械臂只有触摸笔，支持：

- 屏幕组件点击；
- 示波器前面板物理按钮点击/按下。

暂不支持：

- 旋钮旋转；
- 插入或拔出探头、电缆；
- 接线、连接鳄鱼夹；
- 其他需要真实机械动作的操作。

遇到这些动作时返回：

```text
当前机械臂暂不具备该功能，请手动完成后再继续。
```

设备侧接入通过 `agent.phase3_loop.Phase3Loop` 的两个回调完成：

```text
image_provider()  → 返回最新图片路径
click_executor()  → 接收转换后的点击坐标
```

当前先使用识别命令验证 Agent 的界面理解、状态判断和目标框选能力。

### 7.1 外部视觉端只读接入

视觉工作空间 `/home/ubuntu/RIGOL/ws_siasun-1.3` 已发布裁切后的示波器屏幕话题：

```text
/vision_srv/camera/rgb_screen   sensor_msgs/msg/Image
/vision_srv/camera/rgbd_screen  sensor_msgs/msg/Image
```

当前 Phase 3 先订阅 `rgb_screen`，保存一帧后复用已有识别流程：

```bash
source /home/ubuntu/RIGOL/ws_siasun-1.3/ws_siasun-1.3/install/setup.bash

python3 scripts/inspect_agent.py \
  --live \
  --query "打开通道2,打开测量界面"
```

对应代码为 `integration/vision_frame_source.py`。它只读取 `/vision_srv/camera/rgb_screen`，不会发布点击或机械臂动作。

外部工程接口已确认：视觉端接受 `/vision_srv/click_task`，点击消息包含 `category_id`、`class_id`、`is_used_cord` 和屏幕坐标 `pt`；动作完成后发布 `/vision_srv/subtask_status`。这两个接口暂时不在只读测试命令中使用。

三个外部工程位置：

```text
/home/ubuntu/RIGOL/RIGOL_AITestClient-deploy   Qt/rosbridge 客户端
/home/ubuntu/RIGOL/ws_siasun-1.3              视觉端 ROS2 工作空间
/home/ubuntu/grasp_demo                       机械臂控制和 MoveIt 工作空间
```

### 7.2 完整运行指令

先启动一个终端，加载 ROS2 和视觉工作空间：

```bash
source /opt/ros/humble/setup.bash
source /home/ubuntu/RIGOL/ws_siasun-1.3/ws_siasun-1.3/install/setup.bash
```

检查相机：

```bash
lsusb
/tmp/librealsense-2.56.5/build/Release/rs-enumerate-devices
```

当前视觉二进制需要一组隔离的兼容动态库。若这些文件仍在 `/tmp/rigol_runtime`，设置：

```bash
export LD_LIBRARY_PATH=/tmp/rigol_runtime:\
/home/ubuntu/RIGOL/ws_siasun-1.3/ws_siasun-1.3/install/vision_test/lib/vision_test:\
/home/ubuntu/RIGOL/ws_siasun-1.3/ws_siasun-1.3/install/vision_test_msgs/lib:\
/home/ubuntu/RIGOL/ws_siasun-1.3/ws_siasun-1.3/src/vision_test/3rdparty/mindvision/linux/lib/x64:\
/usr/local/lib:$LD_LIBRARY_PATH
```

启动视觉端：

```bash
ros2 run vision_test vision_test_module
```

另开第二个终端，加载项目环境并确认裁切屏幕话题：

```bash
source /opt/ros/humble/setup.bash
source /home/ubuntu/RIGOL/ws_siasun-1.3/ws_siasun-1.3/install/setup.bash
ros2 topic list | grep '/vision_srv/camera/rgb_screen'
ros2 topic hz /vision_srv/camera/rgb_screen
```

确认话题有数据后，在同一个第二终端运行 Agent，只做识别：

```bash
cd /home/ubuntu/rigol_agent
source .venv/bin/activate

python3 scripts/inspect_agent.py \
  --live \
  --query "打开通道2,打开测量界面"
```

也可以指定组件：

```bash
python3 scripts/inspect_agent.py \
  --live \
  --target CH2 \
  --target Measure \
  --target Vertical
```

识别结果默认保存到：

```text
data/perception_results/inspect.json
data/perception_results/inspect_annotated.jpg
data/vision_frames/screen_*.jpg
```

当前命令不会发布 `/vision_srv/click_task`，不会发布 `/vision_srv/movement_info`，也不会驱动机械臂。停止视觉端时在第一个终端按 `Ctrl+C`；如果进程没有退出，可以使用：

```bash
pkill -INT vision_test_module
```

如果启动时出现 `libonnxruntime.so`、RealSense API version、MindVision camera 或 `Couldn't resolve requests` 错误，说明设备或外部运行库尚未就绪。此时可以先使用 `--image` 静态图片模式，不要继续发送动作命令。

## 8. 坐标转换和状态验证

视觉结果最终统一为 `original_image` 坐标。Qwen3-VL 实际可能返回三种坐标形式：

- 原始像素坐标；
- `0～1` 归一化坐标；
- 常见的 `0～1000` 归一化坐标。

`perception.vlm_client.Qwen3VLClient` 会根据 `QWEN_VL_COORDINATE_MODE` 自动还原到原图尺寸。默认值是 `auto`，兼容当前 Qwen 服务返回的 `0～1000` 坐标；确认供应商返回原始像素时可以设置：

```env
QWEN_VL_COORDINATE_MODE=pixel
```

还原后的 bbox 才能交给后续坐标转换。使用 `CoordinateTransform` 转换到机械臂图像尺寸：

```python
from perception.coordinates import CoordinateTransform

transform = CoordinateTransform((1290, 810), (852, 540))
robot_bbox = transform.bbox(vision_bbox)
robot_point = transform.center(vision_bbox)
```

例如 `1290×810` 原图中的 Qwen 坐标 `[650, 440, 730, 530]`，按 `0～1000` 规则还原后约为 `[838.5, 356.4, 941.7, 429.3]`。

状态验证流程：

```text
获取图片 A
→ 观察组件和状态
→ 判断前置条件
→ 定位并点击
→ 获取图片 B
→ 重新观察
→ 验证 expected_changes
```

## 9. 环境配置

Qwen3-VL：

```env
QWEN_VL_API_KEY=
QWEN_VL_BASE_URL=
QWEN_VL_MODEL=
# auto（默认，兼容 Qwen 常见的 0~1000 bbox）/pixel
QWEN_VL_COORDINATE_MODE=auto
```

DeepSeek：

```env
RIGOL_API_KEY=
RIGOL_BASE_URL=
RIGOL_MODEL=
```

API Key 不写入仓库。未配置 Qwen 时，识别命令会明确报配置错误，不会生成伪造 bbox。

## 10. 验证命令

```bash
python3 -m pytest -q \
  tests/test_knowledge_retrieval.py \
  tests/test_phase3_operation.py

python3 -m compileall -q \
  agent execution knowledge models perception planning tools scripts
```

当前自动测试覆盖知识检索、中文通道和测量目标解析、精简操作摘要、操作计划、人工能力提示、单步闭环条件判断、Qwen `0～1000` bbox 还原和坐标点击准备。最近一次结果为 `9 passed`。真实 Qwen 识别需要配置 API 后执行第 5 节命令。

## 11. 当前实现文件

| 功能 | 主要文件 |
| --- | --- |
| 说明书记录和检索 | `knowledge/manual_repository.py`、`knowledge/retrieval/knowledge_retriever.py` |
| 设备视觉词汇和 prompt 调优 | `data/knowledge/DHO804/visual_knowledge.yaml`、`knowledge/visual_knowledge.py` |
| 观察目标生成 | `knowledge/retrieval/observation_targets.py` |
| 操作计划 | `models/operation.py`、`planning/operation_planner.py` |
| LLM 操作计划输出 | `agent/llm.py` |
| 界面和组件视觉识别 | `perception/vlm_client.py`、`perception/component_locator.py` |
| 单步观察 | `perception/knowledge_observer.py` |
| 识别命令 | `scripts/inspect_agent.py`、`scripts/observe.py` |
| 外部视觉帧读取 | `integration/vision_frame_source.py` |
| 操作闭环边界 | `agent/phase3_loop.py` |
| 坐标转换 | `perception/coordinates.py`、`execution/action_dispatcher.py` |
| 状态验证 | `execution/state_validator.py` |
| 人工完成占位 | `execution/capabilities.py` |

## 12. 当前实际验证结果

已使用以下真实图片完成验证：

```text
/home/ubuntu/RIGOL/datasets/images/000061.jpg
/home/ubuntu/RIGOL/datasets/images/000001.jpg
```

实际识别结果：

- `000061.jpg`：`measurement_vertical`；成功框出 `Measure`、`Vertical`、`Peak-to-Peak`；`CH2` 无法可靠确认，返回空 bbox；
- `000001.jpg`：`main_screen`；成功框出底部关闭状态的 `CH2` 和右上角 `Measure` 入口按钮；
- `Amplitude`：经过 `0～1000` 坐标还原后，框落在第一行最右侧“幅度值”区域。

结果保存于：

```text
data/perception_results/inspect_000061_query_v2.json
data/perception_results/inspect_000061_query_v2_annotated.jpg
data/perception_results/inspect_000001_channel2_measure_fixed.json
data/perception_results/inspect_000001_channel2_measure_fixed_annotated.jpg
data/perception_results/inspect_000061_amplitude_fixed.json
data/perception_results/inspect_000061_amplitude_fixed_annotated.jpg
```

这证明当前链路可以完成：

```text
自然语言目标
  → 说明书知识检索
  → 操作/观察目标生成
  → 当前界面识别
  → 组件 bbox 和状态输出
```

## 13. 已知限制和下一步

当前限制：

- 操作记录的 `required_observations` 仍有部分需要从说明书记录中进一步结构化；
- 界面状态识别依赖 Qwen3-VL，无法确认时应返回 `unknown`；
- 还没有接入真实相机回调和机械臂点击回调；
- 还没有 OCR、向量检索、自动重试、取消和失败恢复；
- 旧的固定 YAML workflow 和旧 taskList 映射不再作为当前知识源。
- 测量网格中的小中文标签仍可能出现视觉框偏差，不能仅凭 VLM 置信度直接执行点击；后续可增加 OCR、局部裁剪放大或第二次视觉校验；
- “当前通道”等泛化查询可能检索到多个无关 operation 来源记录，当前不影响 bbox，但需要继续优化检索排序和来源归因。

下一步先使用真实图片验证：

1. 当前界面状态是否识别正确；
2. 指定组件是否能稳定框选；
3. `observed_state` 是否能区分 on/off/selected；
4. 多目标观察是否与操作计划一致；
5. 再决定是否接入设备侧回调。

