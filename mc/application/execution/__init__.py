"""Unified execution context pipeline.

Provides shared context building for tasks, steps, and CC execution
so that all execution paths receive context the same way.
"""

from mc.application.execution.request import EntityType, ExecutionRequest
from mc.application.execution.result import ExecutionResult

__all__ = ["EntityType", "ExecutionRequest", "ExecutionResult"]
