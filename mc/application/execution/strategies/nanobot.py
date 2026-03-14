"""Nanobot runner strategy — executes tasks via the nanobot AgentLoop."""

from __future__ import annotations

import logging

from mc.application.execution.request import (
    ErrorCategory,
    ExecutionRequest,
    ExecutionResult,
)
from mc.application.execution.runtime import (
    provider_error_types,
    run_nanobot_task,
)

logger = logging.getLogger(__name__)


_PROVIDER_ERRORS = provider_error_types()


class NanobotRunnerStrategy:
    """Runs agent work through the nanobot AgentLoop.

    This strategy is the runtime-facing adapter for nanobot execution.
    """

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute a task via the nanobot agent loop.

        Returns an ExecutionResult with the agent output on success, or
        an error result with categorized error on failure.
        """
        from mc.contexts.execution.agent_runner import _coerce_agent_run_result

        try:
            raw_result, session_key, loop = await self._run_agent_loop(request)
        except _PROVIDER_ERRORS as exc:
            logger.error(
                "[nanobot-strategy] Provider error for task '%s': %s",
                request.title,
                exc,
            )
            return ExecutionResult(
                success=False,
                error_category=ErrorCategory.PROVIDER,
                error_message=str(exc),
                error_exception=exc,
            )
        except Exception as exc:
            logger.error(
                "[nanobot-strategy] Runner error for task '%s': %s",
                request.title,
                exc,
            )
            return ExecutionResult(
                success=False,
                error_category=ErrorCategory.RUNNER,
                error_message=f"{type(exc).__name__}: {exc}",
                error_exception=exc,
            )

        # Coerce to AgentRunResult so we get structured error info even when
        # the loop returns a plain string (backward-compat path).
        run_result = _coerce_agent_run_result(raw_result)

        if run_result.is_error:
            logger.error(
                "[nanobot-strategy] Agent loop reported error for task '%s': %s",
                request.title,
                run_result.error_message,
            )
            return ExecutionResult(
                success=False,
                error_category=ErrorCategory.RUNNER,
                error_message=run_result.error_message or run_result.content,
            )

        return ExecutionResult(
            success=True,
            output=run_result.content,
            session_id=session_key,
            memory_workspace=getattr(loop, "memory_workspace", None),
            session_loop=loop,
        )

    async def _run_agent_loop(self, request: ExecutionRequest) -> tuple[str, str, object]:
        """Set up and run the nanobot AgentLoop.

        Returns (result_text, session_key, loop) on success.
        Raises on failure — caller handles exception categorization.
        """
        result, session_key, loop = await run_nanobot_task(
            agent_name=request.agent_name,
            agent_prompt=request.agent_prompt,
            agent_model=request.agent_model,
            reasoning_level=request.reasoning_level,
            task_title=request.title,
            task_description=request.description,
            agent_skills=request.agent_skills,
            board_name=request.board_name,
            memory_workspace=request.memory_workspace,
            task_id=request.task_id,
        )
        return result, session_key, loop
