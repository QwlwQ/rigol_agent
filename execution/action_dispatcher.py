"""Action dispatch boundary; ROS2 dispatch remains in executor.py."""
class ActionDispatcher:
    def dispatch(self, action, target):
        raise NotImplementedError("Action dispatch is not part of the Qwen3-VL perception MVP.")
