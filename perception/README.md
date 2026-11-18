# Phase 1 perception MVP

当前入口只读取一张已有的示波器屏幕 ROI 图片，不连接 ROS2 或机械臂：

```bash
python3 scripts/locate_component.py \
  --image /path/to/screen_roi.jpg \
  --target "CH2" \
  --state off
```

配置 `.env`：

```env
QWEN_VL_API_KEY=...
QWEN_VL_BASE_URL=...
QWEN_VL_MODEL=...
```

`QWEN_VL_MODEL` 必须填写百炼控制台实际可调用的 Qwen3-VL 模型 ID；代码不预设版本。输出 JSON 和带框图片默认写入 `data/perception_results/`。

当前已实现：

- Base64 Data URL 图片输入；
- OpenAI 兼容 Chat Completions 调用；
- Pydantic Bounding Box 校验；
- 原图像素坐标范围校验；
- `found=false` 结果；
- 推理耗时；
- 原图框选输出。

尚未实现：OCR Adapter、说明书辅助模式、参考图片模式、实时图像文件桥接和评估 Ground Truth。

## 使用既有示波器图片做批量测试

既有示波器图片只作为 Qwen3-VL 输入，外部标注文件不会被读取，也不会修改原数据：

```bash
python3 scripts/evaluate_perception.py \
  --images /home/ubuntu/RIGOL/datasets/images \
  --targets CH2 Measure Vertical Maximum \
  --limit 20
```

结果保存到：

```text
data/perception_eval/results.jsonl
data/perception_eval/summary.json
data/perception_eval/annotated/
```

这是无 Ground Truth 的定性评估。请人工查看 `annotated/` 中的框，并记录：

- 目标是否确实存在；
- 框是否落在目标组件上；
- 是否定位到相似但错误的组件；
- `found=false` 是否合理；
- 当前图片是否确实为示波器屏幕 ROI。

脚本不会计算 IoU，也不会把外部标注文件当作 Ground Truth。


## 目标状态

`--target` 表示逻辑组件，`--state` 表示可选的期望视觉状态。默认 `any` 时，模型应先定位组件并同时返回 `observed_state`：

```bash
# 找未选中的 CH2
python3 scripts/locate_component.py --image test.jpg --target CH2 --state off

# 找已选中的 CH2
python3 scripts/locate_component.py --image test.jpg --target CH2 --state on

# 不限制状态
python3 scripts/locate_component.py --image test.jpg --target CH2 --state any
```

初始观察推荐使用 `any`，不要求调用者事先知道组件状态。`on/off` 主要用于执行前置条件或验证目标。候选结果可以包含：

```json
{"target": "CH2", "observed_state": "off"}
```

`off/on` 是当前视觉 MVP 的逻辑状态名称，不是 Qwen 自动产生的类别 ID。后续 Planner 应将“点击 CH2”解析为查找 `CH2 + off`，并将点击后的验证目标设为 `CH2 + on`。
