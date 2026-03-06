"""Human runner strategy — transitions tasks to waiting_human without spawning.

Human-assigned steps NEVER spawn a process. Instead, they immediately
return an ExecutionResult with transition_status="waiting_human" so the
engine can transition the step/task to the correct state.
"""

from __future__ import annotations

import logging

from mc.application.execution.request import (
    ExecutionRequest,
    ExecutionResult,
)

logger = logging.getLogger(__name__)


class HumanRunnerStrategy:
    """Returns a waiting_human transition without spawning any process.

    This strategy satisfies AC2: Human strategy NEVER spawns a process.
    """

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Return immediate transition to waiting_human.

        No process is spawned, no external call is made. The engine
        uses the transition_status to update the step/task state.
        """
        logger.info(
            "[human-strategy] Task '%s' (step=%s) assigned to human '%s' "
            "-- returning waiting_human transition",
            request.title,
            request.step_id,
            request.agent_name,
        )
        return ExecutionResult(
            success=True,
            output="Waiting for human action.",
            transition_status="waiting_human",
        )
