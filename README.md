# rigol_agent

Rigol 示波器领域 Agent，支持自然语言任务理解、配置化工作流规划、规则验证、内部 JSON 保存、旧 `taskList` JSON 导出，以及经显式确认后的 ROS2 点击任务执行。

## 架构

终端 → `Agent`/`Conversation` → `Planner` → `Knowledge` 工作流展开 → `TaskValidator` → `TaskRepository`。`ToolRegistry` 提供 `create_task`、`validate_task`、`save_task` 三个统一工具契约，工具返回值仍必须经过程序验证；未来可注册 Qt/WebSocket/ROS2 adapter。对话历史和任务状态分开，Task 状态已预留 `CREATED/VALIDATED/CONFIRMED/RUNNING/SUCCESS/FAILED/CANCELLED`。

`knowledge/rigol_real` 是当前真机26类模型对应的正式配置；`demo` 仅用于开发示例，`verified` 保留为空配置占位。

## 安装与使用

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
cp .env.example .env
```

编辑 `.env`，配置 DeepSeek：

```env
RIGOL_API_KEY=你的_DeepSeek_API_Key
RIGOL_MODEL=deepseek-flash
RIGOL_BASE_URL=https://api.deepseek.com
```

仅规划和导出时启动：

```bash
python3 -m rigol_agent
```

真实执行前必须加载 ROS2、视觉和机械臂工作空间：

```bash
source /opt/ros/humble/setup.bash
source /home/cjailab/Desktop/RIGOL/ws_siasun-1.3/ws_siasun-1.3/install/setup.bash
source /home/cjailab/grasp_demo/install/setup.bash
python3 -m rigol_agent
```

在 zsh 中将 `setup.bash` 改为 `setup.zsh`。

`deepseek-flash` 是 DeepSeek V4.1 Flash 当前使用的 API 模型名。项目通过 OpenAI 兼容的 Chat Completions 接口调用 DeepSeek。

在线模式需要在 `.env` 设置 `RIGOL_API_KEY`、`RIGOL_MODEL` 和可选 `RIGOL_BASE_URL`。LLM 只输出结构化工作流提案；程序根据 YAML 展开和验证最终 JSON。OpenAI 兼容接口使用 Chat Completions 的 `response_format`，并保留 `json_schema` 配置入口；官方文档说明函数调用适合连接外部工具，结构化输出适合约束模型响应。[Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) / [Function calling](https://developers.openai.com/api/docs/guides/function-calling)

```text
You: 测量 CH2 的电压峰峰值
You: 观察
You: 保存
You: 导出
You: 执行
```

文件保存到 `data/tasks/<task_name>_<task_id前8位>.json`。Schema 为 Pydantic `Task`，包含 `schema_version: "1.0"`、任务 ID、知识配置摘要、状态、子任务、步骤和组件/动作。

## 测试

```bash
pytest -q
```

测试覆盖简单点击、组合测量、多任务、中文别名、缺参、非法组件、多轮对话和 JSON 往返/篡改校验。

## 当前限制

`观察` 命令只读当前 ScreenCtrl 检测结果，返回类别、置信度、屏幕框、屏幕中心、RealSense 像素和相机坐标系三维点，不触发运动。真实执行当前只支持 `SCREEN_CTRL` 点击任务。执行命令要求再次输入 `EXECUTE`，并检查视觉节点、机械臂目标订阅、子任务反馈、关节反馈和关节速度。Qt 可作为监控界面，但不是 Agent 执行链的必要组件。尚未实现执行中主动取消、进程自动启动、测量数值读取和失败后的自动重新规划。
