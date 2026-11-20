"""Capability boundary for the current touch-pen robot.

The adapter can click screen controls and physical buttons.  It cannot rotate
knobs or connect/disconnect cables.  Unsupported skills remain explicit so a
future robot can replace this policy without changing planning code.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from models.errors import AgentError


MANUAL_COMPLETION_MESSAGE = "当前机械臂暂不具备该功能，请手动完成后再继续。"


class UnsupportedCapabilityError(AgentError):
    """Raised when a planned action needs hardware that is not connected."""


@dataclass(frozen=True)
class CapabilityNotice:
    supported: bool
    message: str = ""
    capability: str = ""


_ROTATION = re.compile(r"旋钮|转动|旋转|顺时针|逆时针|调节档位|调节时基|调节偏移")
_CONNECT = re.compile(r"插入|插上|拔出|拔掉|接入|接线|连接探头|连接电缆|插头|鳄鱼夹")


def capability_for_request(text: str) -> CapabilityNotice:
    """Return a user-facing notice for unsupported physical operations."""
    text = str(text or "")
    if _ROTATION.search(text) and not re.search(r"点击|按下", text):
        return CapabilityNotice(False, MANUAL_COMPLETION_MESSAGE, "knob_rotation")
    if _CONNECT.search(text):
        return CapabilityNotice(False, MANUAL_COMPLETION_MESSAGE, "cable_connection")
    return CapabilityNotice(True)


def ensure_action_supported(action: str, target: str = "") -> None:
    text = f"{action} {target}"
    notice = capability_for_request(text)
    if not notice.supported:
        raise UnsupportedCapabilityError(notice.message)
    if str(action).casefold() not in {"click", "点击", "press", "按下"}:
        raise UnsupportedCapabilityError(MANUAL_COMPLETION_MESSAGE)


class ManualCompletionSkill:
    """Placeholder skill for future knob/cable robot adapters."""

    name = "manual_completion"

    def run(self, *_, **__) -> str:
        return MANUAL_COMPLETION_MESSAGE

