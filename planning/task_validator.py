"""Compatibility boundary for the task validator.

The current implementation remains next to the planner until the planning
subsystems are split further; callers should import TaskValidator from here.
"""
from .task_planner import TaskValidator
__all__ = ["TaskValidator"]
