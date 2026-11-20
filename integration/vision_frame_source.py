"""Read-only ROS2 bridge for the external vision workspace.

The vision process already publishes a perspective-corrected oscilloscope
screen on ``/vision_srv/camera/rgb_screen``.  This bridge captures one frame
to a local image file so the existing Phase 3 VLM pipeline can consume it.
It deliberately does not publish click or robot commands.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
import time


@dataclass(frozen=True)
class VisionFrame:
    path: Path
    topic: str
    width: int
    height: int
    encoding: str
    captured_at: str


class Ros2VisionFrameSource:
    """Capture one cropped screen image from the existing ROS2 vision node."""

    def __init__(self, *, topic: str = "/vision_srv/camera/rgb_screen", output_dir: str | Path = "data/vision_frames", node_name: str = "rigol_agent_frame_source"):
        self.topic = topic
        self.output_dir = Path(output_dir)
        self.node_name = node_name

    def capture(self, *, timeout: float = 15.0) -> VisionFrame:
        try:
            import rclpy
            from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
            from sensor_msgs.msg import Image
        except ImportError as exc:
            raise RuntimeError("ROS2 sensor_msgs 未加载，请先 source 视觉工作空间") from exc
        try:
            from PIL import Image as PILImage
        except ImportError as exc:
            raise RuntimeError("缺少 Pillow，无法保存视觉帧") from exc

        initialized_here = not rclpy.ok()
        if initialized_here:
            rclpy.init(args=None)
        node = rclpy.create_node(self.node_name)
        done = Event()
        result: dict[str, VisionFrame] = {}
        qos = QoSProfile(depth=1, history=HistoryPolicy.KEEP_LAST, reliability=ReliabilityPolicy.BEST_EFFORT)

        def callback(message: Image) -> None:
            try:
                pixels = self._message_pixels(message)
                image = PILImage.frombytes("RGB", (message.width, message.height), pixels)
                self.output_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now(timezone.utc)
                path = self.output_dir / f"screen_{timestamp.strftime('%Y%m%dT%H%M%S_%fZ')}.jpg"
                image.save(path, quality=95)
                result["frame"] = VisionFrame(path, self.topic, message.width, message.height, message.encoding, timestamp.isoformat())
                done.set()
            except Exception as exc:
                result["error"] = exc
                done.set()

        node.create_subscription(Image, self.topic, callback, qos)
        deadline = time.monotonic() + float(timeout)
        try:
            while not done.is_set() and time.monotonic() < deadline:
                rclpy.spin_once(node, timeout_sec=0.1)
            if "error" in result:
                raise RuntimeError(f"视觉帧保存失败：{result['error']}")
            if "frame" not in result:
                raise TimeoutError(f"等待视觉话题超时：{self.topic}")
            return result["frame"]
        finally:
            node.destroy_node()
            if initialized_here and rclpy.ok():
                rclpy.shutdown()

    @staticmethod
    def _message_pixels(message) -> bytes:
        """Convert ROS Image bytes to packed RGB bytes without cv_bridge."""
        encoding = str(message.encoding).lower()
        channels = {"rgb8": 3, "bgr8": 3, "mono8": 1}.get(encoding)
        if channels is None:
            raise ValueError(f"暂不支持 ROS 图像编码：{message.encoding}")
        row_bytes = message.width * channels
        raw = bytes(message.data)
        rows = []
        for row in range(message.height):
            start = row * message.step
            rows.append(raw[start:start + row_bytes])
        packed = b"".join(rows)
        if encoding == "rgb8":
            return packed
        if encoding == "mono8":
            return b"".join(bytes((value, value, value)) for value in packed)
        # bgr8 → rgb8
        return b"".join(bytes((packed[i + 2], packed[i + 1], packed[i])) for i in range(0, len(packed), 3))

