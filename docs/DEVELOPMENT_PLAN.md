# Rigol Agent 开发进度与后续计划说明

## 1. 项目目标

本项目计划在原有示波器视觉识别、Qt 客户端和机械臂控制系统基础上，增加一个面向 Rigol 示波器操作的自然语言 Agent。

预期完整流程为：

```text
用户自然语言指令
  → Agent 理解测量目标
  → 生成结构化任务步骤
  → 转换为原 Qt/视觉系统可用的 taskList JSON
  → 视觉系统定位界面组件
  → 机械臂执行点击
  → 视觉系统确认点击后的界面状态
  → 返回任务成功或失败信息
```

当前优先目标是先完成一个可稳定演示的测量闭环，而不是一次覆盖示波器全部功能。

## 2. 现有系统组成

### 2.1 Agent 项目

路径：

```text
/home/cjailab/Desktop/rigol_agent
```

主要职责：

- 将自然语言转换为结构化测量任务；
- 根据知识配置展开通道、菜单、分类和测量项步骤；
- 校验组件、动作、步骤顺序和任务 Schema；
- 保存内部 Task JSON；
- 通过 Legacy Adapter 转换为旧系统的 `taskList` JSON。

### 2.2 视觉系统

路径：

```text
/home/cjailab/Desktop/RIGOL/ws_siasun-1.3/ws_siasun-1.3
```

主要职责：

- MindVision 和 RealSense 图像采集；
- 示波器屏幕分割和透视变换；
- NanoDet 组件检测；
- 将类别 ID 转换为目标位置；
- 结合深度、标定和屏幕平面计算三维点击目标；
- 动作完成后检测预期界面状态。

### 2.3 Qt 客户端

路径：

```text
/home/cjailab/Desktop/RIGOL/RIGOL_AITestClient-deploy
```

主要职责：

- 显示视觉系统图像；
- 编辑、保存和加载 `taskList` JSON；
- 通过 rosbridge 发布点击等任务；
- 顺序执行子任务；
- 接收视觉与机械臂状态；
- 提供屏幕图像采集页面。

### 2.4 机械臂控制系统

路径：

```text
/home/cjailab/grasp_demo
```

主要职责：

- 接收视觉系统计算的三维目标；
- 通过 Piper/MoveIt 执行触屏动作；
- 返回动作完成状态。

## 3. 当前已完成内容

### 3.1 Agent M1 任务规划框架

已经实现：

- Pydantic Task、Subtask、Step 等数据模型；
- YAML 配置化组件、动作、工作流和约束；
- 已知工作流的确定性解析；
- 无法确定时调用 DeepSeek 生成结构化 Proposal；
- 测量任务参数化规划：`channel + category + item`；
- 连续测量时减少重复步骤；
- 任务 Schema 和知识版本校验；
- 内部 JSON 保存与读取；
- 内部 Task 到旧 `taskList` 格式的 Adapter；
- 基础自动化测试。

当前规划示例：

```text
测量 CH2 的峰峰值
  → 点击 CH2
  → 点击 Measure
  → 选择 Vertical
  → 点击 Peak-to-Peak
  → 关闭测量窗口
```

### 3.2 原系统接口调查

已经确认：

- `category_id=1` 表示 `SCREEN_CTRL`；
- `name_id` 与 NanoDet 类别 ID 相同，采用零基索引；
- Qt 将 `taskList.name_id` 原样作为点击消息的 `class_id`；
- 视觉端通过 `boxes_info[i].label == class_id` 查找目标；
- 点击完成后通过 `feedback_config.xml` 查找期望反馈类别；
- 找不到反馈映射时，现有代码会直接跳过反馈检查并视为完成；
- 找到反馈映射但未检测到目标时，会重试检测，并在连续失败后尝试重做动作。

### 3.3 新型号示波器数据采集

由于真机型号和原训练型号存在界面差异，决定重新采集和标注 ScreenCtrl 数据。

当前已经准备：

```text
155 张有效图像
分辨率全部为 1290×810
编号为 000001.jpg～000155.jpg
```

数据内容包括：

- CH1、CH2、CH3、CH4 各自选中状态，每组约 15 张；
- Vertical、Horizontal、Other 三个面板，每组约 15 张；
- Maximum、Minimum、Peak-to-Peak 选中状态，每组约 10 张；
- Period、Frequency 选中状态，每组约 10 张。

旧数据已备份至：

```text
/home/cjailab/Desktop/RIGOL/datasets/images_backup_20261113_old91
/home/cjailab/Desktop/RIGOL/datasets/labels_backup_20261113_old91
```

新图片已经放入：

```text
/home/cjailab/Desktop/RIGOL/datasets/images
```

### 3.4 新 ScreenCtrl 类别方案

当前为第一版 Demo 规划了 26 个类别：

```text
CH1 / CH1_select
CH2 / CH2_select
CH3 / CH3_select
CH4 / CH4_select
measure
Measure_close
Vertical / Vertical_select
Horizontal / Horizontal_select
Other / Other_select
Vmax_off / Vmax_on
Vmin_off / Vmin_on
Vpp_off / Vpp_on
Period_off / Period_on
Frequency_off / Frequency_on
```

区分普通、选中、关闭和开启状态的原因是现有视觉反馈流程需要比较点击前后的状态变化，例如：

```text
CH2 → CH2_select
Horizontal → Horizontal_select
Vpp_off → Vpp_on
```

## 4. 当前尚未完成或存在的问题

### 4.1 新数据尚未标注和训练

当前155张图片已经整理完成，但新标签尚未开始生成。因此：

- 新 NanoDet 模型尚未训练；
- 训练配置仍是原7分类配置；
- 当前视觉服务仍使用旧的7分类 `screenctrl.onnx`；
- 新26类 ID 尚不能用于实际点击。

### 4.2 反馈配置与当前模型不一致

当前 `feedback_config.xml` 保留的是旧百分类模型映射，存在：

- 类别 ID 与当前模型不一致；
- 配置内容重复；
- 部分当前点击类别会误命中旧映射；
- 当前7分类模型的点击后确认实际上没有按预期工作。

新模型部署后必须重新生成一份精简、可审查的反馈映射。

### 4.3 Window 模型是否继续使用尚未确定

原系统通过独立的 `window.onnx` 检测整个 Measure 弹窗，例如：

```text
measure_vertical
measure_horizontal
```

但该模型针对旧型号英文界面。新型号是中文界面，布局也有差异，不能保证继续可靠识别。

当前建议的 Demo 方案是：

```text
点击定位和点击后确认均使用新的 screenctrl.onnx
```

例如：

```text
点击 measure → 确认 Vertical_select 出现
```

这样第一阶段不需要单独重训 Window 模型。后续如果导师要求保留原架构，再单独采集整窗标签并训练新的 `window.onnx`。

### 4.4 Agent 尚未接入真实执行

当前 Agent 仍未实现：

- 自动导出旧格式 JSON 的 CLI 流程；
- 将任务下发给 Qt 或 ROS2；
- 用户执行确认；
- 执行状态机；
- 单步结果回传；
- 失败重试和恢复规划；
- 任务取消；
- 真实设备状态读取。

### 4.5 Agent 保存流程存在待修复问题

当前 CLI 在“先规划、再输入保存”时，待保存对象类型处理不一致，需要在下一阶段修复并补充测试。

### 4.6 组件已经处于目标状态时的处理

如果 CH1 已经是 `CH1_select`，但任务仍要求定位并点击 `CH1`，视觉端可能找不到普通状态的 CH1。

短期 Demo 可以固定初始界面状态。正式版本需要选择一种方案：

1. Agent 根据当前视觉状态跳过已经完成的步骤；
2. 视觉端允许一个逻辑组件对应多个可定位状态；
3. 在执行前增加界面状态归一化步骤。

## 5. 建议的 Demo 范围

第一阶段建议只演示以下能力：

### 通道

```text
CH1
CH2
CH3
CH4
```

### 测量分类

```text
Vertical
Horizontal
Other（只演示面板切换，不执行内部测量项）
```

### 测量项目

```text
Maximum
Minimum
Peak-to-Peak
Period
Frequency
```

### 推荐演示指令

```text
测量 CH2 的最大值
测量 CH4 的峰峰值
测量 CH1 的周期
测量 CH3 的频率
```

第一阶段暂不纳入：

- Delay 和 Phase 的多种边沿组合；
- 亮度设置；
- 关机和重启；
- 滑动和旋转操作；
- 波形 OCR；
- 通用界面自主探索；
- ESP32 压力传感器功能。

## 6. 后续实施计划

### 阶段 A：完成新视觉模型

1. 使用 LabelImg 标注155张图片；
2. 每张图片完整标注所有可见且已列入类别表的组件；
3. 检查图片与标签一一对应；
4. 统计每个类别的标注框数量；
5. 对数量不足或变化不足的状态定向补采；
6. 将 NanoDet 配置由7类更新为26类；
7. 按采集场景划分训练集与验证集，避免连续近重复帧同时进入训练和验证；
8. 训练并导出 ONNX；
9. 验证输入、输出维度与类别数量匹配；
10. 备份旧模型后部署新模型；
11. 在不启动机械臂的情况下验证实时检测。

### 阶段 B：重建点击反馈

1. 清理旧 `feedback_config.xml`；
2. 按新类别 ID 建立点击前后映射；
3. 验证通道切换反馈；
4. 验证面板切换反馈；
5. 验证测量项 `_off → _on` 反馈；
6. 验证反馈失败重试；
7. 决定关闭 Measure 后使用何种状态确认；
8. 决定是否保留或重训 Window 模型。

建议映射示例：

```text
CH1              → CH1_select
CH2              → CH2_select
CH3              → CH3_select
CH4              → CH4_select
measure           → Vertical_select
Vertical          → Vertical_select
Horizontal        → Horizontal_select
Other             → Other_select
Vmax_off          → Vmax_on
Vmin_off          → Vmin_on
Vpp_off           → Vpp_on
Period_off        → Period_on
Frequency_off     → Frequency_on
```

### 阶段 C：完成 Agent 到旧系统 JSON 的闭环

1. 修复 Agent 的待保存任务逻辑；
2. 建立正式 `rigol_real` 知识 profile；
3. 将26类真实 ID 写入映射表；
4. 只允许导出已验证的组件；
5. 在 CLI 中增加显式的旧格式导出命令；
6. 为每个 Demo 测量流程增加 JSON 转换测试；
7. 使用 Qt 加载导出的 JSON，确认字段完全兼容；
8. 在不执行机械臂的情况下检查任务列表和视觉目标。

### 阶段 D：单步真机验证

1. 先验证单个通道点击；
2. 再验证打开 Measure；
3. 再验证面板切换；
4. 再验证单个测量项；
5. 每一步检查三维目标、深度和平面拟合结果；
6. 使用低速、单步、人工确认方式执行；
7. 记录定位失败、点击失败和反馈失败原因。

### 阶段 E：完整任务执行与反馈

1. Agent 生成任务；
2. 用户确认；
3. 导出并下发旧格式任务；
4. Qt 顺序执行；
5. 每一步等待视觉反馈；
6. 将成功或失败结果返回 Agent；
7. 增加任务取消、超时和安全停止；
8. 最后再考虑失败后的自动恢复规划。

## 7. 预期第一阶段交付物

- 新型号示波器的26类 ScreenCtrl 数据集；
- 对应 NanoDet 训练配置、权重和 ONNX；
- 新类别文件与类别 ID 清单；
- 精简后的反馈映射配置；
- `rigol_real` Agent 知识配置；
- Agent 内部 Task JSON；
- Qt 可加载的旧 `taskList` JSON；
- 至少四条可重复演示的测量任务；
- 单步和完整流程测试记录；
- 部署、启动、停止和故障排查说明。

## 8. 需要导师确认的问题

### 8.1 Agent 的定位

希望确认 Agent 应当做到哪一层：

1. 只负责自然语言理解和任务 JSON 生成；
2. 负责生成并下发任务，但执行仍由 Qt 管理；
3. 同时负责执行状态机、重试和失败恢复。

当前建议先实现第2层，第3层作为后续扩展。

### 8.2 第一阶段 Demo 范围

希望确认以下范围是否足够：

```text
CH1～CH4
Maximum / Minimum / Peak-to-Peak
Period / Frequency
Vertical / Horizontal / Other 面板切换
```

### 8.3 Window 模型处理方式

希望确认：

1. 第一阶段完全使用 ScreenCtrl 做定位和反馈；
2. 仍要求重新训练 Window 模型并保留整窗确认。

当前建议第一阶段选择方案1。

### 8.4 反馈标准

希望确认任务成功标准是：

1. 机械臂动作完成即视为成功；
2. 必须检测到点击后的界面状态才视为成功；
3. 还需要读取示波器最终测量数值并返回用户。

当前建议第一阶段采用方案2，数值读取作为下一阶段。

### 8.5 最终交互入口

希望确认最终演示使用：

1. 独立 Agent 终端；
2. 在 Qt 客户端中嵌入自然语言输入框；
3. Web 页面或其他上层界面。

当前实现是独立终端，后续可以通过统一工具接口接入 Qt。

### 8.6 是否要求通用化

希望确认第一阶段目标是：

1. 固定型号、固定机位、固定初始界面的可靠 Demo；
2. 支持多型号、不同机位和任意初始界面。

当前数据和计划面向方案1。方案2需要显著增加数据、状态识别、校准和恢复规划工作。

## 9. 当前建议结论

建议采用“先闭环、后扩展”的实施方式：

```text
新型号小范围视觉模型
  → 点击前后状态确认
  → Agent 真实 ID 映射
  → Qt JSON 兼容
  → 单步低速真机验证
  → 完整测量任务
  → 执行结果回传 Agent
```

先把五种测量项目做成稳定、可重复演示的闭环，再扩展 Other 面板、多状态恢复、测量数值读取和更多示波器功能。
