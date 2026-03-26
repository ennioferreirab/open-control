"""Nanobot runner strategy — executes tasks via the nanobot AgentLoop."""

from __future__ import annotations

import logging
from typing import Any

from mc.application.execution.request import (
    ErrorCategory,
    ExecutionRequest,
    ExecutionResult,
)
from mc.application.execution.runtime import (
    provider_error_types,
    run_nanobot_task,
)
from mc.contexts.interactive.activity_service import SessionActivityService

logger = logging.getLogger(__name__)


_PROVIDER_ERRORS = provider_error_types()


def _parse_tool_name(text: str) -> str:
    """Extract tool name from a tool hint string like 'web_search("q")'."""
    idx = text.find("(")
    name = text[:idx].strip() if idx >= 0 else text.strip()
    return name[:200] if name else "tool_use"


class NanobotRunnerStrategy:
    """Runs agent work through the nanobot AgentLoop.

    This strategy is the runtime-facing adapter for nanobot execution.
    """

    def __init__(self, *, bridge: Any | None = None) -> None:
        self._bridge = bridge
        self._activity = SessionActivityService(bridge)

    def _build_on_progress(
        self,
        mc_session_id: str,
        *,
        agent_name: str,
        step_id: str | None = None,
    ) -> Any | None:
        """Build an on_progress callback that streams events to sessionActivityLog."""
        if not self._activity.has_bridge:
            return None

        activity = self._activity

        async def _on_progress(text: str, *, tool_hint: bool = False) -> None:
            if tool_hint:
                activity.append_event(
                    mc_session_id,
                    kind="tool_use",
                    agent_name=agent_name,
                    provider="nanobot",
                    step_id=step_id,
                    source_type="tool_use",
                    tool_name=_parse_tool_name(text),
                    summary=text[:1000],
                )
            else:
                activity.append_event(
                    mc_session_id,
                    kind="text",
                    agent_name=agent_name,
                    provider="nanobot",
                    step_id=step_id,
                    source_type="assistant",
                    summary=text[:1000],
                    raw_text=text,
                )

        return _on_progress

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute a task via the nanobot agent loop.

        Returns an ExecutionResult with the agent output on success, or
        an error result with categorized error on failure.
        """
        from mc.contexts.execution.agent_runner import _coerce_agent_run_result

        mc_session_id = f"{request.task_id}-{request.entity_id}"

        self._activity.upsert_session(
            mc_session_id,
            agent_name=request.agent_name,
            provider="nanobot",
            surface="nanobot",
            task_id=request.task_id,
            status="ready",
        )

        try:
            raw_result, session_key, loop = await self._run_agent_loop(request, mc_session_id)
        except _PROVIDER_ERRORS as exc:
            logger.error(
                "[nanobot-strategy] Provider error for task '%s': %s",
                request.title,
                exc,
            )
            self._activity.upsert_session(
                mc_session_id,
                agent_name=request.agent_name,
                provider="nanobot",
                surface="nanobot",
                task_id=request.task_id,
                status="error",
                last_error=str(exc),
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
            self._activity.upsert_session(
                mc_session_id,
                agent_name=request.agent_name,
                provider="nanobot",
                surface="nanobot",
                task_id=request.task_id,
                status="error",
                last_error=f"{type(exc).__name__}: {exc}",
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
            self._activity.append_result(
                mc_session_id,
                agent_name=request.agent_name,
                provider="nanobot",
                success=False,
                content=run_result.error_message or run_result.content,
            )
            self._activity.upsert_session(
                mc_session_id,
                agent_name=request.agent_name,
                provider="nanobot",
                surface="nanobot",
                task_id=request.task_id,
                status="error",
                last_error=run_result.error_message or run_result.content,
            )
            return ExecutionResult(
                success=False,
                error_category=ErrorCategory.RUNNER,
                error_message=run_result.error_message or run_result.content,
            )

        self._activity.append_result(
            mc_session_id,
            agent_name=request.agent_name,
            provider="nanobot",
            success=True,
            content=run_result.content or "",
        )
        self._activity.upsert_session(
            mc_session_id,
            agent_name=request.agent_name,
            provider="nanobot",
            surface="nanobot",
            task_id=request.task_id,
            status="ended",
            final_result=(run_result.content or "")[:500],
        )

        return ExecutionResult(
            success=True,
            output=run_result.content,
            session_id=session_key,
            memory_workspace=getattr(loop, "memory_workspace", None),
            session_loop=loop,
        )

    async def _run_agent_loop(
        self, request: ExecutionRequest, mc_session_id: str
    ) -> tuple[str, str, object]:
        """Set up and run the nanobot AgentLoop.

        Returns (result_text, session_key, loop) on success.
        Raises on failure — caller handles exception categorization.
        """
        on_progress = self._build_on_progress(
            mc_session_id,
            agent_name=request.agent_name,
        )

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
            step_id=request.step_id,
            bridge=self._bridge,
            on_progress=on_progress,
        )
        return result, session_key, loop
