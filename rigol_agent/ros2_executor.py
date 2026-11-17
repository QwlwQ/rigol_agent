"""Minimal ROS 2 executor for confirmed, click-only legacy task lists."""
from __future__ import annotations

from dataclasses import dataclass
from threading import Event
import time

from .models import AgentError


@dataclass(frozen=True)
class ExecutionResult:
    completed_steps: int
    total_steps: int


class Ros2TaskExecutor:
    def __init__(self, step_timeout=45.0, ready_timeout=5.0, velocity_limit=0.01):
        self.step_timeout=float(step_timeout)
        self.ready_timeout=float(ready_timeout)
        self.velocity_limit=float(velocity_limit)

    @staticmethod
    def validate_payload(payload):
        tasks=payload.get("taskList") if isinstance(payload,dict) else None
        if not isinstance(tasks,list) or not tasks:
            raise AgentError("旧任务 JSON 缺少非空 taskList")
        for index,item in enumerate(tasks,start=1):
            if not isinstance(item,dict) or item.get("taskType") != 0:
                raise AgentError(f"执行器第 {index} 步只支持 click/taskType=0")
            if item.get("category_id") != 1:
                raise AgentError(f"执行器第 {index} 步只支持 SCREEN_CTRL/category_id=1")
            if not isinstance(item.get("name_id"),int) or not 0 <= item["name_id"] < 26:
                raise AgentError(f"执行器第 {index} 步 name_id 无效")
            if item.get("useCord",0) != 0:
                raise AgentError(f"执行器第 {index} 步暂不支持坐标点击")
        return tasks

    def execute(self,payload,progress=None,status=None):
        tasks=self.validate_payload(payload)
        try:
            import rclpy
            from sensor_msgs.msg import JointState
            from std_msgs.msg import Int32
            from vision_test_msgs.msg import ClickTask
        except ImportError as exc:
            raise AgentError("ROS2 环境未加载；请先 source ROS2、视觉和机械臂工作空间") from exc

        initialized_here=not rclpy.ok()
        if initialized_here: rclpy.init(args=None)
        node=rclpy.create_node("rigol_agent_executor")
        done=Event(); latest_joint={"msg":None}
        node.create_subscription(Int32,"/vision_srv/subtask_status",
                                 lambda msg: done.set() if msg.data == 1 else None,10)
        node.create_subscription(JointState,"/joint_states_feedback",
                                 lambda msg: latest_joint.__setitem__("msg",msg),10)
        publisher=node.create_publisher(ClickTask,"/vision_srv/click_task",10)
        try:
            if status: status("正在检查视觉、机械臂、反馈话题和关节状态……")
            deadline=time.monotonic()+self.ready_timeout
            while time.monotonic() < deadline:
                rclpy.spin_once(node,timeout_sec=0.1)
                if (node.count_subscribers("/vision_srv/click_task") > 0 and
                    node.count_publishers("/vision_srv/subtask_status") > 0 and
                    node.count_subscribers("/vision_srv/movement_info") > 0 and
                    latest_joint["msg"] is not None):
                    break
            else:
                raise AgentError("执行预检失败：视觉、机械臂目标订阅、子任务反馈或关节反馈未就绪")

            velocities=list(latest_joint["msg"].velocity)
            if not velocities:
                raise AgentError("关节反馈缺少速度，机械臂物理状态未知")
            if max(abs(value) for value in velocities) > self.velocity_limit:
                raise AgentError("机械臂仍在运动，拒绝开始新任务")
            if status: status("执行预检通过，机械臂当前静止。")

            for index,item in enumerate(tasks,start=1):
                done.clear()
                msg=ClickTask()
                msg.category_id=item["category_id"]
                msg.class_id=item["name_id"]
                msg.is_used_cord=False
                msg.pt.x=0; msg.pt.y=0
                if progress: progress(index,len(tasks),item)
                publisher.publish(msg)
                if status: status(f"第 {index}/{len(tasks)} 步已发送，等待视觉与机械臂闭环反馈……")
                deadline=time.monotonic()+self.step_timeout
                while not done.is_set() and time.monotonic() < deadline:
                    rclpy.spin_once(node,timeout_sec=0.1)
                if not done.is_set():
                    raise AgentError(f"第 {index} 步等待视觉/机械臂反馈超时，已停止发送后续步骤")
                if status: status(f"第 {index}/{len(tasks)} 步完成。")
            return ExecutionResult(len(tasks),len(tasks))
        finally:
            node.destroy_node()
            if initialized_here and rclpy.ok(): rclpy.shutdown()
