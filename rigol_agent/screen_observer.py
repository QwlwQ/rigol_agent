"""Read-only ROS 2 adapter for the current ScreenCtrl detections."""
from __future__ import annotations

import time
from .models import AgentError


class ScreenObserver:
    def __init__(self,timeout=12.0): self.timeout=float(timeout)

    def observe(self):
        try:
            import rclpy
            from std_msgs.msg import Bool
            from vision_test_msgs.msg import DetectedComponentList
        except ImportError as exc:
            raise AgentError("ROS2/视觉消息环境未加载，请先 source 对应工作空间") from exc

        initialized_here=not rclpy.ok()
        if initialized_here: rclpy.init(args=None)
        node=rclpy.create_node("rigol_agent_screen_observer")
        result={"msg":None}
        node.create_subscription(DetectedComponentList,"/vision_srv/detected_components",
                                 lambda msg: result.__setitem__("msg",msg),10)
        enable=node.create_publisher(Bool,"/vision_srv/send_image_status",10)
        try:
            deadline=time.monotonic()+self.timeout
            while time.monotonic() < deadline and node.count_subscribers("/vision_srv/send_image_status") == 0:
                rclpy.spin_once(node,timeout_sec=0.1)
            if node.count_subscribers("/vision_srv/send_image_status") == 0:
                raise AgentError("视觉服务未启动或未订阅 send_image_status")
            enable.publish(Bool(data=True))
            while time.monotonic() < deadline and result["msg"] is None:
                rclpy.spin_once(node,timeout_sec=0.1)
            if result["msg"] is None:
                raise AgentError("等待结构化识别结果超时")
            msg=result["msg"]
            return {
                "frame_id":msg.header.frame_id,
                "screen":{"width":msg.screen_width,"height":msg.screen_height},
                "components":[{
                    "class_id":c.class_id,"name":c.class_name,
                    "confidence":round(float(c.confidence),4),
                    "bbox":{"x":c.bbox_x,"y":c.bbox_y,"width":c.bbox_width,"height":c.bbox_height},
                    "screen_center":{"x":c.screen_center.x,"y":c.screen_center.y},
                    "rgbd_pixel":{"x":c.rgbd_pixel.x,"y":c.rgbd_pixel.y},
                    "depth_valid":bool(c.depth_valid),
                    "camera_point_m":{"x":float(c.camera_point.x),"y":float(c.camera_point.y),"z":float(c.camera_point.z)},
                } for c in msg.components]
            }
        finally:
            node.destroy_node()
            if initialized_here and rclpy.ok(): rclpy.shutdown()
