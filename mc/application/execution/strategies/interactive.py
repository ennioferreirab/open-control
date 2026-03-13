"""Interactive TUI runner strategy for backend-owned step execution."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from mc.application.execution.request import (
    ErrorCategory,
    ExecutionRequest,
    ExecutionResult,
)
from mc.contexts.interactive.identity import InteractiveSessionIdentity
from mc.contexts.interactive.metrics import increment_interactive_metric
from mc.types import AgentData


class InteractiveTuiRunnerStrategy:
    """Run interactive-capable work through the shared TUI runtime."""

    def __init__(
        self,
        *,
        bridge: Any,
        session_coordinator: Any | None,
        poll_interval_seconds: float = 0.25,
    ) -> None:
        self._bridge = bridge
        self._session_coordinator = session_coordinator
        self._poll_interval_seconds = poll_interval_seconds

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        if self._session_coordinator is None:
            increment_interactive_metric("interactive_startup_failure_total")
            return ExecutionResult(
                success=False,
                error_category=ErrorCategory.RUNNER,
                error_message="Interactive session coordinator is not available.",
            )

        try:
            provider = self._resolve_provider(request)
        except ValueError as exc:
            increment_interactive_metric("interactive_startup_failure_total")
            return ExecutionResult(
                success=False,
                error_category=ErrorCategory.RUNNER,
                error_message=str(exc),
            )

        agent = self._resolve_agent(request, provider=provider)
        identity = InteractiveSessionIdentity(
            provider=provider,
            agent_name=request.agent_name,
            scope_kind="task",
            scope_id=request.task_id,
            surface="step",
        )
        timestamp = datetime.now(timezone.utc).isoformat()

        try:
            session = await self._session_coordinator.create_or_attach(
                identity=identity,
                agent=agent,
                task_id=request.task_id,
                step_id=request.step_id,
                timestamp=timestamp,
                orientation=request.agent_prompt,
                task_prompt=_build_interactive_task_prompt(request),
                board_name=request.board_name,
                memory_mode=request.memory_mode or "clean",
                memory_workspace=request.memory_workspace,
            )
        except Exception as exc:
            increment_interactive_metric("interactive_startup_failure_total")
            return ExecutionResult(
                success=False,
                error_category=ErrorCategory.RUNNER,
                error_message=f"{type(exc).__name__}: {exc}",
                error_exception=exc,
            )

        session_id = str(session["session_id"])
        increment_interactive_metric("interactive_startup_success_total")
        request.session_key = session_id

        return await self._wait_for_outcome(
            session_id=session_id,
            memory_workspace=request.memory_workspace,
        )

    def _resolve_provider(self, request: ExecutionRequest) -> str:
        agent = request.agent
        provider = getattr(agent, "interactive_provider", None) if agent is not None else None
        if provider:
            return str(provider)
        backend = getattr(agent, "backend", None) if agent is not None else None
        if backend == "claude-code" or request.is_cc:
            return "claude-code"
        raise ValueError(
            f"Interactive execution requires an interactive provider for agent '{request.agent_name}'."
        )

    def _resolve_agent(self, request: ExecutionRequest, *, provider: str) -> AgentData:
        if request.agent is not None:
            return request.agent
        return AgentData(
            name=request.agent_name,
            display_name=request.agent_name,
            role="agent",
            model=request.model or request.agent_model,
            backend="claude-code" if provider == "claude-code" else "nanobot",
            interactive_provider=provider,
        )

    async def _wait_for_outcome(
        self,
        *,
        session_id: str,
        memory_workspace: Any | None = None,
    ) -> ExecutionResult:
        while True:
            metadata = self._bridge.query(
                "interactiveSessions:getForRuntime",
                {"session_id": session_id},
            )
            if not isinstance(metadata, dict):
                return ExecutionResult(
                    success=False,
                    error_category=ErrorCategory.RUNNER,
                    error_message=f"Interactive session metadata not found for {session_id}.",
                    session_id=session_id,
                )

            manual_completion_requested_at = str(
                metadata.get("manual_completion_requested_at") or ""
            ).strip()
            control_mode = str(metadata.get("control_mode") or "").strip()
            final_result = str(metadata.get("final_result") or "").strip()
            if manual_completion_requested_at:
                if not final_result:
                    return ExecutionResult(
                        success=False,
                        error_category=ErrorCategory.RUNNER,
                        error_message=(
                            "Manual Live completion is missing a canonical final result."
                        ),
                        session_id=session_id,
                    )
                return ExecutionResult(
                    success=True,
                    output=final_result,
                    session_id=session_id,
                    memory_workspace=memory_workspace,
                )

            last_event_kind = str(metadata.get("last_event_kind") or "")
            if last_event_kind == "turn_completed":
                if control_mode == "human":
                    await asyncio.sleep(self._poll_interval_seconds)
                    continue
                if not final_result:
                    return ExecutionResult(
                        success=False,
                        error_category=ErrorCategory.RUNNER,
                        error_message=(
                            "Interactive session completed but is missing a canonical final result."
                        ),
                        session_id=session_id,
                    )
                return ExecutionResult(
                    success=True,
                    output=final_result,
                    session_id=session_id,
                    memory_workspace=memory_workspace,
                )
            if last_event_kind == "session_failed" or metadata.get("supervision_state") == "failed":
                return ExecutionResult(
                    success=False,
                    error_category=ErrorCategory.RUNNER,
                    error_message=str(
                        metadata.get("last_error")
                        or metadata.get("summary")
                        or "Interactive session failed."
                    ),
                    session_id=session_id,
                    memory_workspace=memory_workspace,
                )

            await asyncio.sleep(self._poll_interval_seconds)


def _build_interactive_task_prompt(request: ExecutionRequest) -> str:
    parts: list[str] = []
    if request.is_step and request.step_title:
        parts.append(f"Step: {request.step_title}")
    elif request.title:
        parts.append(request.title)

    description = (request.description or request.step_description or "").strip()
    if description:
        parts.append(description)

    return "\n\n".join(part for part in parts if part).strip()
