# Rigol Visual Agent（历史总体设计）

> 本文件保留项目早期总体设计和后续设想，不是当前代码结构的权威入口。当前实现以 `README.md`、`docs/PHASE1_TEST_COMMANDS.md`、`docs/PHASE2_MANUAL_KNOWLEDGE.md` 和 `docs/PHASE3_KNOWLEDGE_PERCEPTION.md` 为准。

## 项目开发说明与总体架构

**项目名称：** Rigol Visual Agent

**目标设备：** Rigol DHO804 数字示波器

**开发周期：** 3～4 个月

**核心方向：** 基于大语言模型、视觉语言模型、设备说明书知识和机械臂的视觉闭环智能体。

# 1. 项目背景与目标

本项目旨在开发一个能够通过自然语言理解示波器操作需求，并利用视觉感知和机械臂完成实际设备操作的智能体。

与传统基于固定 Workflow 和目标检测的自动化系统不同，本项目希望让 Agent 具备以下能力：

1. 理解用户自然语言需求。
2. 理解示波器官方说明书中的设备功能和操作逻辑。
3. 根据用户需求识别需要操作的设备组件。
4. 根据当前相机画面定位目标组件。
5. 根据当前界面状态规划下一步操作。
6. 调用现有视觉机械臂系统执行点击、滑动等动作。
7. 操作后重新获取相机画面。
8. 判断操作是否成功。
9. 如果实际界面与预期不符，重新分析并调整操作计划。
10. 最终完成完整的示波器操作任务并返回结果。

项目不以开发新的通用视觉检测模型为目标，而是重点研究：

**如何利用设备说明书和多模态大模型，让 Agent 理解专业设备，并在动态变化的 GUI 环境中完成多步骤操作。**

## 1.1 当前已有基础

项目已经具备或正在建设以下能力：

- Python Agent 基础框架。
- LLM HTTP 调用模块。
- 基于 Pydantic 的数据结构。
- 机械臂视觉操作系统。
- ROS2 机械臂控制接口。
- 相机图像获取能力。
- 传统视觉组件识别接口。
- 原有机械臂任务 JSON 格式。
- Qt 客户端，可以管理任务 JSON、相机参数、机械臂参数以及当前可识别组件。

已有代码必须优先检查和复用。

不允许在没有阅读现有代码的情况下直接重写整个项目。

# 2. 核心设计理念

## 2.1 说明书驱动的设备知识

以 Rigol DHO804 官方说明书 PDF 作为主要设备知识来源。

通过 PDF 解析和大模型知识提取，建立：

- Component Knowledge：组件知识。
- Function Knowledge：设备功能知识。
- Relationship Knowledge：组件关系知识。
- Operation Knowledge：操作知识。
- State Knowledge：界面状态知识。
- Workflow Knowledge：经过验证的操作流程。

说明书是 Agent 的长期知识来源，而不是每次执行任务时都重新上传整本 PDF。

## 2.2 零样本视觉定位

第一阶段不要求人工标注完整组件数据集，也不要求训练 NanoDet。

优先使用视觉语言模型，根据自然语言和当前相机图像直接定位目标组件。

例如：

用户：

找到未开启的 CH2。

输入：

- 当前相机图像。
- 目标描述。
- 可选的设备知识。

输出：

```
{
  "found": true,
  "target": "CH2",
  "bbox": [x_min, y_min, x_max, y_max],
  "image_size": [width, height],
  "confidence": 0.95
}
```

坐标必须映射回原始图像坐标系。

如果目标无法确认，允许返回 found=false。

不能为了满足输出格式而编造坐标。

## 2.3 视觉闭环执行

Agent 不应该在任务开始时一次性生成所有点击步骤。

正确方式：

观察 → 理解 → 规划 → 定位 → 执行 → 验证 → 再规划。

每次机械臂操作后，都必须重新获取相机画面。

后续操作必须基于最新画面，而不是使用旧图像中的坐标。

## 2.4 分层规划

明确以下概念：

### Device Operation

面向用户的高级设备操作。

例如：

- 测量 CH2 电压峰峰值。
- 测量 CH1 频率。
- 开启 CH2。
- 设置触发模式。
- 调整时基。

### Robot Action

执行 Device Operation 所需的底层机械臂动作。

例如：

- click
- slide
- drag

Device Operation 与 Robot Action 是上下层关系，不是并列关系。

### System Action

独立于示波器屏幕操作的系统管理能力。

例如：

- load_task
- save_task
- list_tasks
- set_camera_parameter
- set_robot_parameter
- get_components
- refresh_components
- get_robot_status

复杂任务可以同时包含 Device Operation 和 System Action。

# 3. 模型与技术选型

第一版采用云端 API 为主，不急于本地部署大型模型。

模型必须通过独立 Adapter 调用，避免业务逻辑与具体模型供应商绑定。

## 3.1 DeepSeek：Agent 推理模型

职责：

- 用户意图理解。
- Task Planner。
- Operation Planner。
- Interaction Planner。
- Replanner。
- 说明书文本知识提取。
- 复杂任务拆解。
- 对话上下文管理。

保留当前项目的 llm.py。

当前 LLMClient 采用标准 HTTP 接口，不依赖厂商 SDK。

继续保持这一设计。

DeepSeek 负责思考和决策，不负责机械臂底层执行。

## 3.2 Qwen3-VL：视觉语言模型

作为第一版主要视觉模型。

职责：

- 示波器图像理解。
- 根据自然语言定位组件。
- Bounding Box 输出。
- 菜单层级理解。
- 组件空间关系理解。
- 当前界面状态识别。
- 操作后的界面变化分析。

重点测试以下组件：

- CH1。
- CH2。
- CH3。
- CH4。
- Measure。
- 垂直选项。
- 水平选项。
- 其它选项。
- 延迟(r-f)。

注意：

Qwen3-VL 的实际 API 名称、模型版本、请求格式和结构化输出能力必须根据所使用的服务商文档确认。

不能直接假设云端模型与本地开源模型的调用接口一致。

视觉模型调用独立放在 perception 模块，不要混入 llm.py。

## 3.3 PaddleOCR：文字识别

主要用途：

- 中文菜单识别。
- CH1～CH4 标签识别。
- 英文缩写识别。
- 按钮文字识别。
- OCR 文字区域 Bounding Box 输出。

OCR 作为视觉定位的辅助模块，不负责设备语义推理。

## 3.4 Docling + PyMuPDF：说明书解析

Docling：

- PDF 结构解析。
- 章节提取。
- 表格提取。
- 文档布局解析。

PyMuPDF：

- PDF 页面信息。
- 图片提取。
- 原始文本提取。
- 页码关联。

两者结合使用，尽量保留原始页面、图片和章节关系。

## 3.5 OpenCV

用途：

- 图片缩放。
- ROI 裁剪。
- 图像增强。
- 透视校正。
- 畸变校正。
- Bounding Box 绘制。
- 图像差异分析。

不要默认对每张图片执行所有预处理。

先根据实际相机图像测试再决定。

## 3.6 Grounding DINO

暂时不作为第一阶段必需依赖。

如果 Qwen3-VL 对某些组件定位不稳定，再引入 Grounding DINO 作为开放词汇检测辅助模型。

特别关注中文 UI、小尺寸组件和相似通道之间的区分能力。

## 3.7 模型职责总表

| 模型/工具      | 主要职责           | 优先级 |
| -------------- | ------------------ | ------ |
| DeepSeek       | Agent 推理与规划   | 必需   |
| Qwen3-VL       | 视觉理解与定位     | 必需   |
| PaddleOCR      | 文字识别           | 推荐   |
| Docling        | PDF 解析           | 必需   |
| PyMuPDF        | PDF 图片和文本处理 | 必需   |
| OpenCV         | 图像处理           | 推荐   |
| Grounding DINO | 辅助视觉定位       | 暂缓   |

# 4. 系统整体架构

```
                       Rigol Agent
                            |
             +--------------+--------------+
             |                             |
             v                             v
        Task Planner                 Knowledge Base
             |                             |
             |                      +------+------+
             |                      |      |      |
             |                      v      v      v
             |                  Component Function Operation
             |                   Knowledge Knowledge Knowledge
             |                      |      |      |
             +----------------------+------+
                            |
                            v
                    Interaction Planner
                            |
                            v
                     Perception Module
                            |
                  +---------+---------+
                  |         |         |
                  v         v         v
                 VLM       OCR     Image Processing
                  |         |         |
                  +---------+---------+
                            |
                            v
                      Bounding Box
                            |
                            v
                      Action Executor
                            |
                            v
                  Existing Robot System
                            |
                            v
                        New Image
                            |
                            v
                      State Validator
                            |
                     +------+------+
                     |             |
                     v             v
                   Success       Failure
                     |             |
                     v             v
                Next Action      Replanner
                     |             |
                     +-------------+
```

# 5. 项目目录结构

以当前代码为基础逐步演进为：

```
rigol_agent/
│
├── agent/
│   ├── agent.py
│   ├── llm.py
│   ├── conversation.py
│   └── context_manager.py
│
├── planning/
│   ├── task_planner.py
│   ├── operation_planner.py
│   ├── interaction_planner.py
│   ├── workflow_matcher.py
│   ├── replanner.py
│   └── task_validator.py
│
├── perception/
│   ├── perception_manager.py
│   ├── image_processor.py
│   ├── component_locator.py
│   ├── vlm_client.py
│   ├── ocr_client.py
│   └── state_recognizer.py
│
├── knowledge/
│   ├── manual_parser/
│   │   ├── pdf_parser.py
│   │   ├── image_extractor.py
│   │   ├── table_extractor.py
│   │   └── structure_extractor.py
│   │
│   ├── extraction/
│   │   ├── component_extractor.py
│   │   ├── function_extractor.py
│   │   ├── operation_extractor.py
│   │   └── state_extractor.py
│   │
│   ├── retrieval/
│   │   ├── knowledge_retriever.py
│   │   └── manual_retriever.py
│   │
│   ├── repository.py
│   └── schemas.py
│
├── execution/
│   ├── executor.py
│   ├── action_dispatcher.py
│   ├── feedback.py
│   └── state_validator.py
│
├── tools/
│   ├── registry.py
│   ├── robot_tools/
│   ├── client_tools/
│   └── file_tools/
│
├── workflows/
│   ├── repository.py
│   └── schemas.py
│
├── models/
│   ├── proposal.py
│   ├── perception.py
│   ├── planning.py
│   └── execution.py
│
├── config/
│   ├── agent.yaml
│   ├── llm.yaml
│   ├── vision.yaml
│   └── device.yaml
│
├── data/
│   ├── manuals/
│   │   └── DHO804/
│   │
│   ├── parsed/
│   │   └── DHO804/
│   │
│   ├── knowledge/
│   │   └── DHO804/
│   │
│   ├── images/
│   │   └── DHO804/
│   │
│   └── index/
│       └── DHO804/
│
├── scripts/
│   ├── parse_manual.py
│   ├── extract_knowledge.py
│   ├── test_vlm.py
│   ├── locate_component.py
│   ├── recognize_state.py
│   └── run_agent.py
│
├── tests/
│   ├── test_llm.py
│   ├── test_knowledge.py
│   ├── test_perception.py
│   ├── test_planning.py
│   └── test_execution.py
│
├── main.py
├── models.py
├── repository.py
├── cli.py
├── pyproject.toml
├── .env.example
└── README.md
```

这是目标结构，不要求一次性创建全部文件。

每个阶段只实现当前真正需要的模块。

# 6. Knowledge Base：说明书知识库

## 6.1 输入资料

主要输入：

1. DHO804 官方用户手册 PDF。
2. 可选的快速入门手册。
3. 可选的编程手册。
4. 实际相机拍摄的示波器图片。

第一阶段不需要人工标注完整组件数据集。

图片用于验证零样本定位能力。

## 6.2 PDF 解析流程

```
Original PDF
     |
     v
Docling + PyMuPDF
     |
     +----------+----------+
     |          |          |
     v          v          v
    Text      Images      Tables
     |          |          |
     +----------+----------+
                |
                v
        Structure Extraction
                |
                v
           LLM Analysis
                |
                v
        Structured Knowledge
```

必须保留：

- 原始页码。
- 章节名称。
- 原始文本。
- 图片文件。
- 表格信息。
- 图片附近的文字。
- 知识来源。

不能只生成普通 Markdown 摘要。

## 6.3 知识结构

至少支持五类。

### Component Knowledge

```
components:
  - id: channel_2
    name: CH2
    aliases:
      - 通道2
      - 第二通道
    type: channel_control
    description: 示波器第二模拟通道
    source:
      manual_pages: []
```

### Function Knowledge

```
functions:
  - id: voltage_measurement
    name: 电压测量
    description: 测量信号电压相关参数
```

### Relationship Knowledge

```
relationships:
  - parent: measurement_panel
    children:
      - vertical_tab
      - horizontal_tab
      - other_tab
```

### Operation Knowledge

```
operations:
  - id: measure_delay_r_f
    name: 延迟上升沿到下降沿测量
    required_components:
      - measurement_panel
      - vertical_tab
      - delay_r_f
```

### State Knowledge

```
states:
  - id: main_screen
    description: 示波器主界面

  - id: measurement_panel
    description: 测量面板

  - id: measurement_vertical
    description: 测量面板垂直分类
```

以上仅为结构示例。

所有具体知识必须根据实际 DHO804 说明书和设备验证结果提取。

不能让模型将推测内容当作说明书事实。

每个知识条目应该支持：

- source_file。
- source_page。
- source_text。
- source_image。
- extraction_method。
- confidence。
- verification_status。

# 7. Perception：视觉理解与定位

这是第一阶段的最高优先级。

## 7.1 Component Locator

统一接口：

```
result = component_locator.locate(
    image=image,
    target="未开启的CH2通道",
    context=knowledge_context
)
```

输入：

- 当前图像。
- 自然语言目标。
- 可选设备知识。
- 可选参考图片。

输出：

```
{
  "found": true,
  "target": "CH2",
  "bbox": [x_min, y_min, x_max, y_max],
  "image_size": [1704, 1279],
  "confidence": 0.95,
  "evidence": [
    "识别到CH2标签",
    "位置符合底部通道控制区域"
  ]
}
```

要求：

1. 统一使用 `[x_min, y_min, x_max, y_max]`。
2. 输出原始图片坐标。
3. 保留图像尺寸。
4. 支持目标不存在。
5. 支持多个候选框。
6. 支持低置信度和不确定结果。
7. 不允许将模型未经验证的坐标直接传给机械臂。

如果模型使用缩放图片或 ROI 图片，必须进行坐标映射。

## 7.2 视觉定位的三种模式

必须支持以下实验模式。

### Mode A：纯视觉定位

输入：

```
当前图片 + 自然语言目标
```

目的：

测试 VLM 自身是否能够理解示波器界面并定位组件。

### Mode B：说明书辅助定位

输入：

```
当前图片 + 自然语言目标 + 相关说明书知识
```

目的：

测试设备知识是否提高定位准确率。

### Mode C：参考图片辅助定位

输入：

```
当前图片 + 目标描述 + 说明书相关图片
```

目的：

测试说明书中的视觉参考能否帮助定位。

三组实验使用相同测试图片和目标描述。

比较定位成功率、IoU 和推理时间。

## 7.3 OCR 辅助定位

OCR 主要用于识别：

- CH1～CH4。
- 中文菜单。
- 延迟(r-f)。
- 测量选项。
- 当前选中标签。

OCR 返回文字及其 Bounding Box。

对于存在文字的组件，优先结合 OCR 结果校验 VLM 定位。

对于图标、无文字组件，则使用 VLM 视觉理解。

## 7.4 图像畸变

机械臂相机拍摄的屏幕可能存在：

- 角度倾斜。
- 透视畸变。
- 镜头畸变。
- 屏幕反光。
- 图像模糊。

第一版先通过真实图像评估影响。

如果需要，再加入 OpenCV 预处理。

不能默认模型输入坐标与机械臂执行坐标一致，必须明确原图、处理图和机械臂系统之间的坐标转换。

# 8. Planning：任务规划

## 8.1 Task Planner

负责理解用户最终目标。

例如：

用户：

测量 CH1 和 CH2 之间的上升沿到下降沿延迟。

输出：

```
{
  "goal": "measure_delay_r_f",
  "parameters": {
    "source_a": "CH1",
    "source_b": "CH2"
  },
  "success_condition": "获取有效的延迟测量结果"
}
```

不生成点击坐标。

## 8.2 Operation Planner

负责根据设备知识理解高级设备操作需要完成哪些功能步骤。

例如：

```
测量 CH1 和 CH2 之间的延迟
          |
          v
打开测量面板
          |
          v
进入对应测量分类
          |
          v
选择延迟测量
          |
          v
配置测量源
          |
          v
读取测量结果
```

具体步骤必须根据说明书和设备实际操作验证。

## 8.3 Interaction Planner

负责根据当前界面状态决定下一步交互动作。

输入：

```
{
  "goal": "measure_delay_r_f",
  "current_state": "measurement_panel"
}
```

输出：

```
{
  "action": "click",
  "target": "vertical_tab",
  "expected_state": "measurement_vertical"
}
```

每次只决定当前动作。

执行后重新获取图像，再次规划。

## 8.4 Workflow Matcher

固定 Workflow 继续保留。

如果已有验证过的操作流程，优先匹配。

但 Workflow 不应保存固定坐标。

每一步仍然需要：

- 当前状态检查。
- 动态目标定位。
- 操作后验证。

如果没有匹配的 Workflow，则结合说明书知识动态规划。

## 8.5 Replanner

操作失败或实际界面与预期不一致时：

1. 重新观察。
2. 识别当前状态。
3. 分析失败原因。
4. 重新检索知识。
5. 决定下一步。

设置最大重试次数和安全停止条件。

# 9. Execution：执行与反馈

保留原有视觉机械臂系统。

Agent 不重新开发机械臂运动学和 ROS2 控制。

建议采用 Adapter：

```
Agent Action
     |
     v
Action Dispatcher
     |
     v
Robot Adapter
     |
     v
Existing Robot System
     |
     v
ROS2 / Traditional Vision
```

统一接口：

```
executor.execute(
    action="click",
    target_bbox=bbox
)
```

但必须先检查现有系统的真实接口，再决定具体参数。

需要确认：

- 相机图像尺寸。
- Bounding Box 坐标格式。
- 原有 JSON 格式。
- click 的输入格式。
- slide 的输入格式。
- 执行结果返回方式。
- ROS2 通信接口。
- 安全停止机制。

不能虚构这些接口。

如果暂时无法连接真实机械臂，先通过 Mock Adapter 测试。

# 10. State Recognition 与 Validation

Agent 必须能够识别当前界面状态。

例如：

```
S1：主界面
S2：测量面板
S3：测量面板-垂直分类
S4：测量面板-水平分类
S5：测量配置界面
```

状态识别结合：

- VLM。
- OCR。
- 关键组件。
- 当前选中状态。
- 图像变化。

状态识别需要允许返回 unknown。

不能强制把未知界面映射到已有状态。

## 10.1 状态验证

点击垂直选项之后：

```
执行点击
    |
    v
获取新图片
    |
    v
识别当前选中分类
    |
    v
是否为垂直？
    |
 +--+--+
 |     |
是     否
 |     |
 v     v
下一步 重新分析
```

验证不应只依赖界面名称。

还需要检查实际可见组件、选中状态和必要的文字证据。

无法确认时应返回 uncertain。

# 11. Agent 完整闭环

最终执行逻辑：

```
用户输入
   |
   v
Task Planner
   |
   v
Knowledge Retrieval
   |
   v
获取当前图像
   |
   v
State Recognizer
   |
   v
Interaction Planner
   |
   v
Component Locator
   |
   v
Action Executor
   |
   v
等待设备响应
   |
   v
获取新图像
   |
   v
State Validator
   |
   +----------+
   |          |
   v          v
  成功       失败
   |          |
   v          v
下一步      Replanner
   |          |
   +----------+
       |
       v
    任务完成
```

不允许在没有重新观察的情况下连续执行依赖界面状态的点击。

# 12. 第一批测试数据

当前已经有真实 DHO804 相机图片，可作为第一批测试数据。

目标组件包括：

1. CH1。
2. CH2。
3. CH3。
4. CH4。
5. 测量面板。
6. 垂直选项。
7. 水平选项。
8. 其它选项。
9. 延迟(r-f)。

其中部分组件已经通过之前的视觉定位实验确认可以直接框选。

但不能将之前人工确定的 Bounding Box 写死在模型中。

必须使用实际模型独立完成定位。

测试数据应包含：

- 不同界面状态。
- 不同拍摄角度。
- 反光。
- 模糊。
- 透视畸变。
- 相似组件。

第一阶段建议先准备 20～30 张图片。

不需要人工标注训练数据，但需要人工核对测试结果，建立 Ground Truth 评价数据。

# 13. 开发计划：16 周

## Phase 0：代码审查（第 1 周）

首先检查当前仓库。

重点检查：

- llm.py。
- models.py。
- agent.py。
- conversation.py。
- cli.py。
- repository.py。
- 当前 knowledge。
- 当前 tools。
- 依赖和运行方式。

输出：

1. 当前项目结构。
2. 模块调用关系。
3. 已实现功能。
4. 可以复用的代码。
5. 与目标架构的差异。
6. 迁移方案。

不要直接大规模重构。

## Phase 1：视觉定位（第 2～3 周）

实现：

- Qwen3-VL API Adapter。
- Component Locator。
- Bounding Box Schema。
- OCR Adapter。
- 图片处理。
- 定位测试脚本。

完成纯视觉、说明书辅助、参考图片辅助三组对比实验。

验收：

给定真实相机图片和自然语言目标，能够输出准确的 Bounding Box。

## Phase 2：说明书解析（第 4～6 周）

实现：

- PDF 解析。
- 图片提取。
- 表格提取。
- 章节提取。
- 知识提取。
- 来源追踪。
- 知识检索。

验收：

Agent 能够根据自然语言需求检索相关设备功能和操作知识。


## Phase 3：状态识别（第 7～8 周）

实现：

- State Schema。
- State Recognizer。
- State Repository。
- 状态转换关系。
- 前后画面对比。
- 操作结果验证。

验收：

能够识别常见界面状态，并判断预期状态是否达成。

## Phase 4：动态规划（第 9～10 周）

实现：

- Task Planner。
- Operation Planner。
- Interaction Planner。
- Workflow Matcher。
- Replanner。

验收：

Agent 能够根据当前状态决定下一步动作，而不是依赖完整固定点击序列。

## Phase 5：机械臂闭环执行（第 11～13 周）

实现：

- Robot Adapter。
- Action Dispatcher。
- Executor。
- Feedback。
- State Validator。
- 安全停止。

验收：

至少完成一个完整多步骤示波器操作。

## Phase 6：综合测试（第 14～16 周）

实现：

- 多任务测试。
- 动态规划测试。
- 异常恢复测试。
- 运行日志。
- 性能统计。
- 项目文档。
- 演示视频。

# 14. 预算和部署原则

第一版以 API 调用为主。

需要配置：

- DeepSeek API Key。
- Qwen3-VL API Key。

两者分别管理，不共享 API Key。

API 余额和 ChatGPT 订阅无关。

开源工具不需要额外购买商业授权：

- Docling。
- PyMuPDF。
- PaddleOCR。
- OpenCV。
- Grounding DINO。

Grounding DINO 暂时不部署。

不要求购买额外 GPU 服务器。

模型调用必须支持：

- 环境变量配置。
- 超时。
- 重试。
- 异常处理。
- 日志记录。
- 离线 Mock 测试。

API Key 不允许写入仓库。

建议 `.env.example`：

```
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=
DEEPSEEK_MODEL=

QWEN_API_KEY=
QWEN_BASE_URL=
QWEN_MODEL=
```

具体 API 地址和模型名称以实际开通的服务为准。

# 15. 工程规范

1. 使用 Python。
2. 使用 Pydantic 定义核心数据结构。
3. 使用 YAML/JSON 保存设备知识。
4. LLM 通过独立 Provider Adapter 调用。
5. VLM 通过独立视觉 Adapter 调用。
6. 模型必须可替换。
7. 不允许将模型调用写入业务核心逻辑。
8. 不允许将未经验证的坐标直接传给机械臂。
9. 不允许把固定 Bounding Box 写入 Workflow。
10. 所有图像坐标统一使用原始图像坐标系。
11. 所有动作必须有执行反馈。
12. 必须支持最大重试次数。
13. 必须支持未知状态。
14. 必须支持视觉定位失败。
15. 必须保留知识来源。
16. 必须支持独立模块测试。
17. 必须保留原有项目可以复用的代码。
18. 不要为了使用 LangGraph、LlamaIndex 等框架而增加不必要的依赖。

# 16. 最终验收标准

以下是建议的项目目标，不代表当前模型已经达到这些指标。

| 指标                   | 目标 |
| ---------------------- | ---- |
| 常见组件定位成功率     | ≥90% |
| 常见界面状态识别准确率 | ≥90% |
| 操作后状态验证准确率   | ≥90% |
| 典型多步骤任务完成率   | ≥80% |
| 异常操作安全停止能力   | 100% |

测试必须覆盖不同拍摄角度、反光、模糊和不同界面状态。

不能只使用调试时的图片评价。

# 17. 最终演示任务

项目最终以以下任务作为主要演示：

用户：

测量 CH1 和 CH2 之间的上升沿到下降沿延迟。

Agent 应该：

1. 理解用户需求。
2. 从说明书知识库检索相关操作。
3. 获取当前示波器画面。
4. 判断当前界面状态。
5. 决定下一步操作。
6. 定位目标组件。
7. 调用原有机械臂系统。
8. 获取新画面。
9. 验证操作结果。
10. 根据实际界面继续规划。
11. 完成测量。
12. 返回测量结果。

如果某一步无法确认，应暂停并报告原因，而不是盲目继续。

# 18. 当前立即执行的任务

请不要一次性实现全部系统。

首先完成以下工作。

## 第一项：检查当前仓库

读取全部关键代码。

理解：

- 当前 LLMClient 如何调用 DeepSeek。
- Proposal 如何定义。
- Agent 当前如何工作。
- Knowledge 当前如何存储。
- 当前 CLI 如何启动。
- 当前配置如何管理。

输出代码审查报告。

## 第二项：确定模型调用方案

明确：

- DeepSeek 文本模型的实际 API 配置。
- Qwen3-VL 的实际 API 配置。
- 两种模型各自的输入输出结构。
- 图片如何传递给 VLM。
- 如何保证 Bounding Box 输出符合统一 Schema。

不要在没有核实服务商 API 文档的情况下编造模型名称或请求参数。

## 第三项：实现视觉定位 MVP

先实现：

```
python scripts/locate_component.py \
    --image test.jpg \
    --target "未开启的CH2"
```

要求：

1. 读取真实图片。
2. 调用 Qwen3-VL。
3. 输出 JSON。
4. 输出 Bounding Box。
5. 将框绘制到原图。
6. 保存结果。
7. 显示推理耗时。
8. 处理模型无法识别的情况。

再测试：

```
python scripts/locate_component.py \
    --image test.jpg \
    --target "测量面板中的垂直选项"
```

以及：

```
python scripts/locate_component.py \
    --image test.jpg \
    --target "延迟(r-f)"
```

## 第四项：建立视觉定位评估

支持三种模式：

- 纯视觉定位。
- 说明书辅助定位。
- 参考图片辅助定位。

比较三者效果。

## 第五项：逐步扩展

视觉定位稳定后，再进入说明书解析、状态识别、动态规划和机械臂闭环执行。

# 19. 特别注意

本项目最重要的目标不是让 LLM 生成更多 JSON，也不是增加大量固定 Workflow。

而是让 Agent 真正具备：

**理解目标、观察环境、决定行动、执行操作、验证结果、调整计划的能力。**

请始终遵循：

- DeepSeek 负责推理和规划。
- Qwen3-VL 负责视觉理解和定位。
- OCR 负责文字识别。
- Docling 负责说明书解析。
- Knowledge Base 负责长期设备知识。
- 原有机械臂系统负责物理执行。
- Agent 负责组织整个闭环。

第一阶段优先验证语义视觉定位，不要急于接入 ROS2。

整个项目以现有代码为基础逐步演进，不允许无依据地大规模重构。

**请从 Phase 0 开始，先理解现有代码，再制定具体实施方案。**
