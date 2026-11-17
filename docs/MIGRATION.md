# rigol_agent 实际设备迁移说明

本文用于将当前 `rigol_agent` 从开发环境迁移到实际部署设备，并指导后续接入原视觉识别、机械臂执行系统。

## 1. 当前项目定位

当前版本是 M1：Rigol 示波器领域任务规划 Agent。它负责：

```text
自然语言
  → DeepSeek 任务理解
  → 测量目标解析
  → 无状态步骤规划
  → 组件/动作/测量分类校验
  → 内部 Task JSON
  → 保存任务
```

当前版本不负责：

- Qt 客户端通信；
- WebSocket 通信；
- ROS2 通信；
- 机械臂运动；
- 视觉点击确认；
- 点击失败重试；
- 获取示波器真实界面状态；
- 根据执行反馈重新规划。

实际执行仍由原视觉和机械臂系统负责。

## 2. 当前目录和模块

```text
rigol_agent/
├── rigol_agent/
│   ├── cli.py              # 终端入口
│   ├── agent.py            # 对话和任务编排
│   ├── conversation.py     # 对话历史
│   ├── llm.py              # OpenAI 兼容 API 客户端
│   ├── models.py           # Pydantic 数据结构
│   ├── knowledge.py        # YAML 知识加载和校验
│   ├── planner.py          # 模板和动态步骤规划
│   ├── repository.py       # Task JSON 保存/读取
│   └── tools.py            # Tool Registry
├── knowledge/
│   ├── demo/
│   │   ├── components.yaml
│   │   ├── operations.yaml
│   │   ├── workflows.yaml
│   │   └── constraints.yaml
│   └── legacy_mapping.yaml # 旧视觉机械臂 JSON 映射表
├── task/
│   └── legacy_adapter.py   # 内部 Task → 旧 taskList 格式
├── data/tasks/             # 当前内部任务保存目录
├── config/                 # 模型和 Agent 配置
├── tests/
├── scripts/
├── .env.example
├── requirements.txt
└── pyproject.toml
```

## 3. 当前测量规划逻辑

测量任务使用三个核心参数：

```text
channel + category + item
```

例如：

```text
测量 CH2 的峰峰值
```

会规划为：

```text
点击 CH2
点击 Measure
点击 Peak-to-Peak
关闭测量界面
```

当前测量分类：

```text
Vertical:
  Maximum
  Minimum
  Peak-to-Peak
  Top
  Base
  Amplitude

Horizontal:
  Period
  Frequency
  Positive-Duty
  Negative-Duty

Other:
  Delay
  Phase
```

当前使用无设备状态规划：

- 首次测量默认按 Vertical 处理；
- 同一通道连续测量时省略重复的通道和 Measure；
- 分类未变化时省略重复分类按钮；
- 切换通道前关闭测量界面；
- 关闭后认为界面重置为默认 Vertical；
- 最后一个测量组完成后关闭测量界面。

这些状态只是 Agent 在生成一个 JSON 时使用的规划状态，不代表设备真实状态。

## 4. 部署前必须确认的内容

### 4.1 原系统组件映射

需要根据原视觉识别系统确认以下字段：

```text
组件标准名称
视觉 target 名称
category_id
name_id
taskName
可用动作
```

映射文件：

```text
knowledge/legacy_mapping.yaml
```

当前部署的 `screenctrl_classes.txt` 只有 7 类，ID 是类别文件的零基索引：

```text
CH1 → name_id 0
CH1_select → name_id 1
CH4 → name_id 2
CH4_select → name_id 3
measure → name_id 4
Vmax_off → name_id 5
Vmax_on → name_id 6
```

当前 Agent 可直接点击且已经核实映射的组件是 `CH1`、`CH4`、`Measure`
和 `Maximum`（对应 `Vmax_off`）。选择态/开启态类别用于视觉反馈，当前不作为
Agent 点击目标。CH2、CH3、其它测量项以及关闭测量组件在当前模型中不存在，仍标记为：

```yaml
provisional: true
```

在正式执行前，必须替换所有临时映射。可以使用下面的命令检查：

```bash
rg 'provisional: true' knowledge/legacy_mapping.yaml
```

### 4.2 关闭测量组件

当前使用的临时标准名称是：

```text
Close-Measurement
```

需要确认原视觉模型中的真实组件名称和 ID。若原系统没有独立的关闭测量组件，需要改为实际可识别的按钮名称。

### 4.3 实际动作能力

当前所有测量组件都配置为：

```yaml
actions: [click]
```

这需要和原机械臂执行器确认。当前 M1 不使用坐标、滑动或拖动操作。

### 4.4 旧 JSON 格式

当前确认的旧格式为：

```json
{
  "taskList": [
    {
      "angle": 0,
      "category_id": 1,
      "name_id": 4,
      "points": [],
      "regex": "",
      "targetName": "SCREEN_CTRL(1):measure(4)",
      "taskName": "单击measure",
      "taskType": 0,
      "useCord": 0,
      "x": 0,
      "y": 0
    }
  ]
}
```

目前已经提供：

```text
task/legacy_adapter.py
```

它把内部 Task 转换成旧系统的 `taskList` 格式。正式接入前，应使用完整的旧 JSON 样例逐项验证字段含义。

## 5. 实际设备安装步骤

在部署设备上执行：

```bash
git clone <repository-url> rigol_agent
cd rigol_agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

如果使用可编辑安装：

```bash
pip install -e '.[test]'
```

配置 DeepSeek：

```bash
cp .env.example .env
```

编辑 `.env`：

```env
RIGOL_API_KEY=实际的DeepSeek_API_Key
RIGOL_MODEL=deepseek-flash
RIGOL_BASE_URL=https://api.deepseek.com
```

不要把 `.env` 提交到 Git，也不要把 API Key 写入 YAML、JSON 或代码。

启动：

```bash
source .venv/bin/activate
python3 -m rigol_agent --profile demo
```

当前 `demo` 配置用于开发验证。完成真实组件和动作核实后，应复制为正式 profile，例如：

```text
knowledge/rigol_real/
```

然后启动：

```bash
python3 -m rigol_agent --profile rigol_real
```

CLI 当前只允许 `demo` 和 `verified` profile，需要使用新 profile 时同步修改 `rigol_agent/cli.py` 的参数选择。

## 6. 部署验证清单

### 软件验证

```bash
python3 -m py_compile rigol_agent/*.py task/*.py
pytest -q
```

当前测试应全部通过。

### Agent 验证

至少测试：

```text
测量 CH1 的峰峰值
测量 CH2 的频率
先测量 CH1 的峰峰值，再测量 CH1 的频率
先测量 CH1 的频率，再测量 CH3 的频率
测量 CH3 的峰峰值和幅度值
```

重点检查：

- 是否正确识别通道；
- 是否正确识别 Vertical/Horizontal/Other；
- 同一通道是否省略重复步骤；
- 切换通道前是否关闭测量界面；
- 关闭后重新打开是否重新选择 Horizontal；
- 是否最终生成关闭测量动作。

### 旧格式验证

转换后的 JSON 必须由原视觉机械臂系统在仿真或安全环境中验证：

- `taskList` 字段是否完整；
- `targetName` 是否能被视觉系统识别；
- `name_id` 是否对应正确组件；
- `taskType` 是否符合原执行器定义；
- 关闭测量动作是否能正确执行。

在映射表全部确认前，不应直接让机械臂执行临时映射生成的 JSON。

## 7. 推荐的正式接入顺序

### 阶段 A：完成测量知识和映射

1. 提供完整旧 JSON 样例；
2. 建立所有组件的真实 ID 映射；
3. 确认关闭测量按钮；
4. 确认各测量项的视觉名称；
5. 更新 `legacy_mapping.yaml`；
6. 为每类测量增加转换测试。

### 阶段 B：接入保存和导出

当前内部任务保存到：

```text
data/tasks/*.json
```

下一步应支持两种输出：

```text
内部 Task JSON       # Agent 使用
旧 taskList JSON     # 原视觉机械臂系统使用
```

建议先显式导出旧格式，不要直接覆盖内部格式：

```text
save_internal_task
export_legacy_task
```

### 阶段 C：只读执行接口

在真正控制机械臂前，先接入只读或仿真接口：

- 检查任务格式；
- 查看视觉目标是否存在；
- 查看组件 ID 是否有效；
- 执行单步测试；
- 返回点击成功/失败结果。

### 阶段 D：执行和反馈

之后再增加：

- 任务执行状态；
- 视觉点击确认；
- 单步重试；
- 任务取消；
- 失败原因记录；
- 执行结果回传 Agent；
- 根据失败步骤重新规划。

## 8. 当前明确限制

- 仍未接入 Qt、WebSocket、ROS2；
- 未获取实际示波器状态；
- Agent 不能确认点击是否成功；
- 当前关闭测量组件 ID 是临时值；
- 当前模型已确认 `CH1=0`、`CH4=2`、`measure=4` 和 `Vmax_off=5`；
- CH2、CH3、其它测量项和关闭测量组件不在当前七分类模型中；
- 旧格式 Adapter 当前是独立工具，还没有接入默认保存流程；
- 当前 Planner 只保证测量任务的无状态步骤规划；
- 亮度调节、关机、重启、触摸屏检测暂不纳入当前测量规划。

## 9. 后续开发原则

1. Agent 内部结构与旧执行器格式保持解耦；
2. 所有视觉组件 ID 只放在映射表；
3. 不把临时 ID 用于真实机械臂执行；
4. 测量任务继续使用参数化规划，不穷举所有组合；
5. 真实执行前保留用户确认和安全检查；
6. 先完成测量闭环，再扩展亮度、关机、重启和触摸屏检测；
7. 执行反馈接入后，再引入真实设备状态和恢复规划。
