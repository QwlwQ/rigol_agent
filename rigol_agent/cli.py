import argparse
import json
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(): pass

from .agent import Agent
from .knowledge import Knowledge
from .llm import LLMClient
from .models import AgentError
from .planner import Planner, TaskValidator
from .repository import TaskRepository
from .ros2_executor import Ros2TaskExecutor
from .screen_observer import ScreenObserver
from task.legacy_adapter import LegacyTaskAdapter


HELP = """\
当前真机能力：
  通道：CH1 / CH2 / CH3 / CH4
  垂直测量：最大值 / 最小值 / 峰峰值
  水平测量：周期 / 频率

自然语言示例：
  测量 CH2 的峰峰值
  测量 CH1 的频率
  先测量 CH1 的最大值，再测量 CH3 的周期
  点击 CH4

命令：
  帮助 / help            显示本说明
  状态 / status          显示当前待处理任务
  观察 / observe         读取当前画面识别组件和相机三维坐标（不运动）
  保存 / save            保存内部 Task JSON
  导出 / export          导出 Qt 兼容 taskList JSON
  执行 / execute         执行当前待处理任务（真实机械臂动作）
  执行文件 <路径>         执行指定 taskList JSON（真实机械臂动作）
  退出 / quit            退出程序

执行要求：视觉与机械臂服务已启动、关节反馈有效且机械臂静止。
真实执行必须再次输入大写 EXECUTE；Qt仅用于可选监控。
"""


def _confirm():
    return input("该操作将真实驱动机械臂，输入 EXECUTE 确认：").strip() == "EXECUTE"


def _progress(index,total,item):
    print(f"\n[执行] {index}/{total}：{item.get('taskName') or item.get('targetName')}")
    print(f"       目标：{item.get('targetName')}，类别ID：{item.get('name_id')}")


def _status(message):
    print(f"[状态] {message}")


def _execute_payload(executor,payload):
    if not _confirm(): return "已取消执行。"
    try:
        result=executor.execute(payload,progress=_progress,status=_status)
        return f"任务执行完成：{result.completed_steps}/{result.total_steps} 步"
    except AgentError as exc:
        return f"无法执行任务：{exc}"


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--profile",choices=["demo","verified","rigol_real"],default="rigol_real")
    args=parser.parse_args()
    load_dotenv()

    root=Path(__file__).parent.parent
    knowledge=Knowledge(root/"knowledge"/args.profile)
    llm=LLMClient()
    agent=Agent(Planner(knowledge,llm),TaskValidator(knowledge),TaskRepository())
    adapter=LegacyTaskAdapter(root/"knowledge"/"legacy_mapping.yaml")
    executor=Ros2TaskExecutor()
    observer=ScreenObserver()

    print("Rigol Agent 已启动（规划、保存、导出、真实执行）")
    print("输入“帮助”查看当前能力；输入“执行”前请确认机械臂周围安全。")
    try:
        while True:
            try:
                text=input("\nYou: ").strip()
            except (EOFError,KeyboardInterrupt):
                print("\n已退出 Rigol Agent。")
                break
            if not text: continue
            if text.lower() in {"exit","quit","退出"}: break
            if text.lower() in {"帮助","help","?"}: print(HELP); continue
            if text.lower() in {"状态","status"}:
                print("当前有待处理任务，可继续保存、导出或执行。" if agent.pending else
                      "当前没有待处理任务，请先输入自然语言任务。")
                continue
            if text.lower() in {"保存","save"}: print(agent.save_pending()); continue
            if text.lower() in {"导出","export"}: print(agent.export_pending(adapter)); continue
            if text.lower() in {"观察","observe"}:
                try:
                    observed=observer.observe()
                    print(f"画面：{observed['screen']['width']}×{observed['screen']['height']}，相机坐标系：{observed['frame_id']}")
                    if not observed['components']:
                        print("当前帧未识别到组件。")
                    for c in observed['components']:
                        center=c['screen_center']; point=c['camera_point_m']
                        depth=(f"相机点=({point['x']:.4f}, {point['y']:.4f}, {point['z']:.4f})m"
                               if c['depth_valid'] else "深度无效")
                        print(f"- {c['name']}({c['class_id']}) 置信度={c['confidence']:.3f} "
                              f"屏幕中心=({center['x']},{center['y']}) {depth}")
                except AgentError as exc:
                    print(f"无法观察画面：{exc}")
                continue
            if text.lower() in {"执行","execute"}:
                if not agent.pending: print("当前没有待执行任务。"); continue
                if not _confirm(): print("已取消执行。"); continue
                print(agent.execute_pending(adapter,executor,_progress,_status)); continue
            if text.startswith("执行文件 ") or text.lower().startswith("execute-file "):
                raw=text.split(maxsplit=1)[1]
                try:
                    payload=json.loads(Path(raw).expanduser().read_text(encoding="utf-8"))
                    print(_execute_payload(executor,payload))
                except (OSError,json.JSONDecodeError) as exc:
                    print(f"无法读取任务文件：{exc}")
                continue
            print(agent.handle(text))
    finally:
        llm.close()
