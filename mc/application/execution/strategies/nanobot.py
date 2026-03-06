"""Nanobot runner strategy — executes tasks via the nanobot AgentLoop.

Extracts the core nanobot execution logic from mc.executor._run_agent_on_task
into a strategy that the ExecutionEngine can invoke uniformly.
"""

from __future__ import annotations

import logging
from pathlib import Path

from mc.application.execution.request import (
    ErrorCategory,
    ExecutionRequest,
    ExecutionResult,
)

logger = logging.getLogger(__name__)


def _collect_provider_error_types() -> tuple[type[Exception], ...]:
    """Collect provider-specific exception types for targeted catching."""
    from mc.provider_factory import ProviderError

    types: list[type[Exception]] = [ProviderError]
    try:
        from nanobot.providers.anthropic_oauth import AnthropicOAuthExpired

        types.append(AnthropicOAuthExpired)
    except ImportError:
        pass
    return tuple(types)


_PROVIDER_ERRORS = _collect_provider_error_types()


class NanobotRunnerStrategy:
    """Runs agent work through the nanobot AgentLoop.

    Mirrors the execution path in mc.executor._run_agent_on_task() and
    the post-processing in mc.executor.TaskExecutor._execute_task().
    """

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute a task via the nanobot agent loop.

        Returns an ExecutionResult with the agent output on success, or
        an error result with categorized error on failure.
        """
        try:
            result_text, session_key, loop = await self._run_agent_loop(request)
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
            )

        return ExecutionResult(
            success=True,
            output=result_text,
            session_id=session_key,
        )

    async def _run_agent_loop(
        self, request: ExecutionRequest
    ) -> tuple[str, str, object]:
        """Set up and run the nanobot AgentLoop.

        Returns (result_text, session_key, loop) on success.
        Raises on failure — caller handles exception categorization.
        """
        from mc.executor import _run_agent_on_task

        memory_workspace = (
            Path(request.memory_workspace) if request.memory_workspace else None
        )

        result, session_key, loop = await _run_agent_on_task(
            agent_name=request.agent_name,
            agent_prompt=request.agent_prompt,
            agent_model=request.agent_model,
            reasoning_level=request.reasoning_level,
            task_title=request.title,
            task_description=request.description,
            agent_skills=request.agent_skills,
            board_name=request.board_name,
            memory_workspace=memory_workspace,
            task_id=request.task_id,
        )
        return result, session_key, loop
