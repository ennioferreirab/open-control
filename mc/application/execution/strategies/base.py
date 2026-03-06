"""RunnerStrategy protocol — common interface for all execution backends.

Each strategy encapsulates the logic for running agent work through a
specific backend (nanobot, claude-code, human). The ExecutionEngine
delegates to strategies based on the request's runner_type.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mc.application.execution.request import ExecutionRequest, ExecutionResult


@runtime_checkable
class RunnerStrategy(Protocol):
    """Protocol that all runner strategies must satisfy.

    Strategies are stateless — all context flows through the request.
    The engine handles pre/post-execution concerns; strategies handle
    only the actual execution.
    """

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Run agent work and return the result.

        Implementations must:
        - Never raise for expected failures (return ExecutionResult with
          success=False and appropriate error_category instead)
        - May raise for truly unexpected errors (engine catches these)
        - Not perform post-execution steps (memory, artifacts, etc.)
        """
        ...
