"""Shared post-execution hooks for the ExecutionEngine."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from mc.application.execution.background_tasks import create_background_task
from mc.application.execution.engine import ExecutionEngine
from mc.application.execution.request import (
    ExecutionRequest,
    ExecutionResult,
    RunnerType,
)
from mc.application.execution.runtime import relocate_invalid_memory_files
from mc.application.execution.strategies.claude_code import (
    ClaudeCodeRunnerStrategy,
)
from mc.application.execution.strategies.human import HumanRunnerStrategy
from mc.application.execution.strategies.interactive import InteractiveTuiRunnerStrategy
from mc.application.execution.strategies.nanobot import NanobotRunnerStrategy
from mc.memory.service import consolidate_task_output, resolve_consolidation_model

logger = logging.getLogger(__name__)


def _memory_files_touched(workspace: Path | None) -> list[str]:
    if workspace is None:
        return []
    return [
        str(workspace / "memory" / "MEMORY.md"),
        str(workspace / "memory" / "HISTORY.md"),
    ]


def _log_consolidation_event(
    *,
    agent_name: str,
    backend: str,
    channel: str,
    trigger_type: str,
    boundary_reason: str | None,
    memory_workspace: Path | None,
    artifacts_workspace: Path | None,
    action: str,
    skip_reason: str | None = None,
    files_touched: list[str] | None = None,
) -> None:
    payload = {
        "agent_name": agent_name,
        "backend": backend,
        "channel": channel,
        "trigger_type": trigger_type,
        "boundary_reason": boundary_reason,
        "memory_workspace": str(memory_workspace) if memory_workspace is not None else None,
        "artifacts_workspace": str(artifacts_workspace)
        if artifacts_workspace is not None
        else None,
        "action": action,
        "skip_reason": skip_reason,
        "files_touched": files_touched or [],
    }
    logger.info("[memory] consolidation %s", json.dumps(payload, sort_keys=True))


async def relocate_invalid_memory_hook(
    request: ExecutionRequest,
    result: ExecutionResult,
) -> None:
    """Relocate invalid memory files after a runner touched the workspace."""
    if result.memory_workspace is None:
        return

    await asyncio.to_thread(
        relocate_invalid_memory_files,
        request.task_id,
        result.memory_workspace,
    )


async def nanobot_memory_consolidation_hook(
    request: ExecutionRequest,
    result: ExecutionResult,
) -> None:
    """End the nanobot task session in the background after execution."""
    if request.session_boundary_reason is None:
        _log_consolidation_event(
            agent_name=request.agent_name,
            backend=RunnerType.NANOBOT.value,
            channel="mc",
            trigger_type="session_boundary",
            boundary_reason=None,
            memory_workspace=result.memory_workspace,
            artifacts_workspace=result.memory_workspace,
            action="skipped",
            skip_reason="no_session_boundary",
        )
        return

    if result.session_loop is None or not result.session_id:
        _log_consolidation_event(
            agent_name=request.agent_name,
            backend=RunnerType.NANOBOT.value,
            channel="mc",
            trigger_type="session_boundary",
            boundary_reason=request.session_boundary_reason,
            memory_workspace=result.memory_workspace,
            artifacts_workspace=result.memory_workspace,
            action="skipped",
            skip_reason="missing_session_state",
        )
        return

    async def _consolidate() -> None:
        try:
            await result.session_loop.end_task_session(result.session_id)
            _log_consolidation_event(
                agent_name=request.agent_name,
                backend=RunnerType.NANOBOT.value,
                channel="mc",
                trigger_type="session_boundary",
                boundary_reason=request.session_boundary_reason,
                memory_workspace=result.memory_workspace,
                artifacts_workspace=result.memory_workspace,
                action="consolidated",
                files_touched=_memory_files_touched(result.memory_workspace),
            )
        except Exception:
            _log_consolidation_event(
                agent_name=request.agent_name,
                backend=RunnerType.NANOBOT.value,
                channel="mc",
                trigger_type="session_boundary",
                boundary_reason=request.session_boundary_reason,
                memory_workspace=result.memory_workspace,
                artifacts_workspace=result.memory_workspace,
                action="failed",
                skip_reason="exception",
            )
            logger.warning(
                "[execution] Memory consolidation failed for task '%s' session '%s'",
                request.task_id,
                result.session_id,
                exc_info=True,
            )

    create_background_task(_consolidate())


def build_cc_task_memory_consolidation_hook(
    *,
    bridge: Any | None = None,
):
    """Return the canonical Claude Code task-boundary consolidation hook."""

    async def cc_task_memory_consolidation_hook(
        request: ExecutionRequest,
        result: ExecutionResult,
    ) -> None:
        if request.runner_type != RunnerType.CLAUDE_CODE:
            return

        if request.session_boundary_reason is None:
            _log_consolidation_event(
                agent_name=request.agent_name,
                backend=RunnerType.CLAUDE_CODE.value,
                channel="mc",
                trigger_type="session_boundary",
                boundary_reason=None,
                memory_workspace=result.memory_workspace,
                artifacts_workspace=result.memory_workspace,
                action="skipped",
                skip_reason="no_session_boundary",
            )
            return

        if result.memory_workspace is None:
            _log_consolidation_event(
                agent_name=request.agent_name,
                backend=RunnerType.CLAUDE_CODE.value,
                channel="mc",
                trigger_type="session_boundary",
                boundary_reason=request.session_boundary_reason,
                memory_workspace=None,
                artifacts_workspace=None,
                action="skipped",
                skip_reason="missing_memory_workspace",
            )
            return

        async def _consolidate() -> None:
            try:
                model = resolve_consolidation_model(bridge)
                if model is None:
                    _log_consolidation_event(
                        agent_name=request.agent_name,
                        backend=RunnerType.CLAUDE_CODE.value,
                        channel="mc",
                        trigger_type="session_boundary",
                        boundary_reason=request.session_boundary_reason,
                        memory_workspace=result.memory_workspace,
                        artifacts_workspace=result.memory_workspace,
                        action="skipped",
                        skip_reason="missing_consolidation_model",
                    )
                    return

                ok = await consolidate_task_output(
                    result.memory_workspace,
                    task_title=request.title,
                    task_output=result.output,
                    task_status="completed" if result.success else "error",
                    task_id=request.task_id,
                    model=model,
                )
                _log_consolidation_event(
                    agent_name=request.agent_name,
                    backend=RunnerType.CLAUDE_CODE.value,
                    channel="mc",
                    trigger_type="session_boundary",
                    boundary_reason=request.session_boundary_reason,
                    memory_workspace=result.memory_workspace,
                    artifacts_workspace=result.memory_workspace,
                    action="consolidated" if ok else "skipped",
                    skip_reason=None if ok else "consolidate_returned_false",
                    files_touched=_memory_files_touched(result.memory_workspace) if ok else [],
                )
            except Exception:
                _log_consolidation_event(
                    agent_name=request.agent_name,
                    backend=RunnerType.CLAUDE_CODE.value,
                    channel="mc",
                    trigger_type="session_boundary",
                    boundary_reason=request.session_boundary_reason,
                    memory_workspace=result.memory_workspace,
                    artifacts_workspace=result.memory_workspace,
                    action="failed",
                    skip_reason="exception",
                )
                logger.warning(
                    "[execution] CC memory consolidation failed for task '%s'",
                    request.task_id,
                    exc_info=True,
                )

        create_background_task(_consolidate())

    return cc_task_memory_consolidation_hook


def build_interactive_memory_consolidation_hook(
    *,
    bridge: Any | None = None,
):
    """Return the canonical memory hook for interactive TUI step execution."""

    async def interactive_memory_consolidation_hook(
        request: ExecutionRequest,
        result: ExecutionResult,
    ) -> None:
        if request.runner_type != RunnerType.INTERACTIVE_TUI:
            return

        if request.session_boundary_reason is None:
            _log_consolidation_event(
                agent_name=request.agent_name,
                backend=RunnerType.INTERACTIVE_TUI.value,
                channel="mc",
                trigger_type="session_boundary",
                boundary_reason=None,
                memory_workspace=result.memory_workspace,
                artifacts_workspace=result.memory_workspace,
                action="skipped",
                skip_reason="no_session_boundary",
            )
            return

        if result.memory_workspace is None:
            _log_consolidation_event(
                agent_name=request.agent_name,
                backend=RunnerType.INTERACTIVE_TUI.value,
                channel="mc",
                trigger_type="session_boundary",
                boundary_reason=request.session_boundary_reason,
                memory_workspace=None,
                artifacts_workspace=None,
                action="skipped",
                skip_reason="missing_memory_workspace",
            )
            return

        task_output = (result.output or result.error_message or "").strip()
        if not task_output:
            _log_consolidation_event(
                agent_name=request.agent_name,
                backend=RunnerType.INTERACTIVE_TUI.value,
                channel="mc",
                trigger_type="session_boundary",
                boundary_reason=request.session_boundary_reason,
                memory_workspace=result.memory_workspace,
                artifacts_workspace=result.memory_workspace,
                action="skipped",
                skip_reason="missing_task_output",
            )
            return

        async def _consolidate() -> None:
            try:
                model = resolve_consolidation_model(bridge)
                if model is None:
                    _log_consolidation_event(
                        agent_name=request.agent_name,
                        backend=RunnerType.INTERACTIVE_TUI.value,
                        channel="mc",
                        trigger_type="session_boundary",
                        boundary_reason=request.session_boundary_reason,
                        memory_workspace=result.memory_workspace,
                        artifacts_workspace=result.memory_workspace,
                        action="skipped",
                        skip_reason="missing_consolidation_model",
                    )
                    return

                ok = await consolidate_task_output(
                    result.memory_workspace,
                    task_title=request.title,
                    task_output=task_output,
                    task_status="completed" if result.success else "error",
                    task_id=request.task_id,
                    model=model,
                )
                _log_consolidation_event(
                    agent_name=request.agent_name,
                    backend=RunnerType.INTERACTIVE_TUI.value,
                    channel="mc",
                    trigger_type="session_boundary",
                    boundary_reason=request.session_boundary_reason,
                    memory_workspace=result.memory_workspace,
                    artifacts_workspace=result.memory_workspace,
                    action="consolidated" if ok else "skipped",
                    skip_reason=None if ok else "consolidate_returned_false",
                    files_touched=_memory_files_touched(result.memory_workspace) if ok else [],
                )
            except Exception:
                _log_consolidation_event(
                    agent_name=request.agent_name,
                    backend=RunnerType.INTERACTIVE_TUI.value,
                    channel="mc",
                    trigger_type="session_boundary",
                    boundary_reason=request.session_boundary_reason,
                    memory_workspace=result.memory_workspace,
                    artifacts_workspace=result.memory_workspace,
                    action="failed",
                    skip_reason="exception",
                )
                logger.warning(
                    "[execution] Interactive memory consolidation failed for task '%s'",
                    request.task_id,
                    exc_info=True,
                )

        create_background_task(_consolidate())

    return interactive_memory_consolidation_hook


def build_execution_engine(
    *,
    bridge: Any | None = None,
    cron_service: Any | None = None,
    ask_user_registry: Any | None = None,
    interactive_session_coordinator: Any | None = None,
) -> ExecutionEngine:
    """Create the canonical execution engine used by production runtime paths."""
    # Both PROVIDER_CLI (production default) and INTERACTIVE_TUI (escape hatch)
    # use the same strategy implementation — the coordinator drives the session
    # regardless of the PTY/tmux layer. (Story 28.7)
    _interactive_strategy = InteractiveTuiRunnerStrategy(
        bridge=bridge,
        session_coordinator=interactive_session_coordinator,
    )
    return ExecutionEngine(
        strategies={
            RunnerType.NANOBOT: NanobotRunnerStrategy(),
            RunnerType.CLAUDE_CODE: ClaudeCodeRunnerStrategy(
                bridge=bridge,
                cron_service=cron_service,
                ask_user_registry=ask_user_registry,
            ),
            RunnerType.HUMAN: HumanRunnerStrategy(),
            RunnerType.PROVIDER_CLI: _interactive_strategy,
            RunnerType.INTERACTIVE_TUI: _interactive_strategy,
        },
        post_execution_hooks=[
            relocate_invalid_memory_hook,
            nanobot_memory_consolidation_hook,
            build_cc_task_memory_consolidation_hook(bridge=bridge),
            build_interactive_memory_consolidation_hook(bridge=bridge),
        ],
    )
