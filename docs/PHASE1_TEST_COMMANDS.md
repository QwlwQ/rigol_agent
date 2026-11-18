# Phase 1 Qwen3-VL 视觉定位测试记录

本文记录当前 Phase 1 的真实图片定位命令和结果。测试不接入 ROS2、Qt 或机械臂，只调用 Qwen3-VL 返回组件位置和可观察状态。

## 环境配置

项目根目录 `.env`：

```env
QWEN_VL_API_KEY=新的百炼API_Key
QWEN_VL_BASE_URL=https://ws-yf6bxq3k6up1o5y5.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
QWEN_VL_MODEL=qwen3-vl-plus
```

启动虚拟环境：

```bash
source .venv/bin/activate
```

图片目录：

```text
/home/ubuntu/RIGOL/datasets/images
```

当前图片尺寸：

```text
1290 × 810
```

## 单图定位命令

### CH2 关闭状态：`000001.jpg`

```bash
python3 scripts/locate_component.py \
  --image /home/ubuntu/RIGOL/datasets/images/000001.jpg \
  --target CH2 \
  --state off
```

目标是底部通道控制区中标记为 `2` 的第二张通道卡片。`off` 状态下卡片仍然存在，但颜色较暗、没有高亮边框，主显示区域没有 CH2 活动波形。

已验证：`found=true`，置信度约为 `0.98`。

### CH2 开启状态：`000016.jpg`

```bash
python3 scripts/locate_component.py \
  --image /home/ubuntu/RIGOL/datasets/images/000016.jpg \
  --target CH2 \
  --state on
```

`on` 状态下卡片有青色高亮边框，主波形区域出现 CH2 波形或左侧通道 2 标记。已验证：`found=true`，置信度约为 `0.95～0.98`。

### Measure 测量入口：`000016.jpg`

```bash
python3 scripts/locate_component.py \
  --image /home/ubuntu/RIGOL/datasets/images/000016.jpg \
  --target Measure
```

目标是右上角 RUN/STOP 附近的“测量”入口按钮。此时测量面板可能尚未展开，仍然定位入口按钮本身。已验证：`found=true`，置信度约为 `0.95`。

### Vertical 当前选中状态：`000075.jpg`

```bash
python3 scripts/locate_component.py \
  --image /home/ubuntu/RIGOL/datasets/images/000075.jpg \
  --target Vertical \
  --state on
```

Vertical 对应测量面板顶部的“垂直”分类标签及其下方横线。有明亮横线表示当前分类已选中。已验证：`found=true`，置信度约为 `0.98`。

### Maximum 当前选中状态：`000075.jpg`

```bash
python3 scripts/locate_component.py \
  --image /home/ubuntu/RIGOL/datasets/images/000075.jpg \
  --target Maximum \
  --state on
```

Maximum 对应 Vertical 测量面板中的“最大值”选项。选中状态通过测量项颜色变淡/高亮边框，以及旁边的测量状态区域综合判断。已验证：`found=true`，置信度约为 `0.98`。

## 状态参数规则

`--target` 表示逻辑组件，`--state` 表示可选的期望视觉状态：

```text
any    不限制状态，默认值
on     开启、选中或激活状态
off    关闭、未选中或未激活状态
```

初始观察不应要求调用者提前知道状态，推荐使用：

```bash
python3 scripts/locate_component.py \\
  --image /home/ubuntu/RIGOL/datasets/images/000001.jpg \\
  --target CH2 \\
  --state any
```

此时模型会返回组件位置，并在候选结果中填写 `observed_state`，例如：

```json
{"target": "CH2", "observed_state": "off"}
```

`on/off` 更适合执行前置条件和点击后验证：

```text
点击 CH2：寻找 CH2 + off
点击后验证：寻找 CH2 + on
```

| 组件类型 | 状态判断依据 |
|---|---|
| CH1～CH4 | 通道卡片颜色、高亮边框、主波形和通道标记 |
| Vertical/Horizontal/Other | 分类标签下方是否存在横线 |
| Maximum 等测量项 | 选项颜色、边框和旁边测量状态区域 |
| Measure | 当前版本主要定位入口按钮，不要求面板已打开 |

## 结果和批量测试

单图结果默认保存到：

```text
data/perception_results/locate_result.json
data/perception_results/locate_result_annotated.jpg
```

批量定性测试：

```bash
python3 scripts/evaluate_perception.py \
  --images /home/ubuntu/RIGOL/datasets/images \
  --targets CH2 Measure Vertical Maximum \
  --limit 20
```

输出目录：

```text
data/perception_eval/results.jsonl
data/perception_eval/summary.json
data/perception_eval/annotated/
```

当前没有人工 Ground Truth，因此批量测试只进行人工核对，不计算正式 IoU、Precision 或 Recall。程序会兼容多种 Bounding Box 格式，并统一转换回原始 `1290×810` 图片坐标。

## 当前限制

- `target` 目前由命令行手动指定，`state=any` 时可由模型返回 observed_state；
- Planner 尚未自动生成带状态的视觉目标请求；
- Maximum 的旁边状态栏尚未作为独立视觉目标返回；
- 尚未实现说明书辅助定位和参考图片辅助定位；
- 尚未接入 OCR、ROS2、Qt 和机械臂；
- 不使用旧 NanoDet 标签作为 Ground Truth。

后续任务可以扩展为：

```json
{
  "component": "CH2",
  "action": "click",
  "precondition": {"state": "off"},
  "expected_state": "on"
}
```
