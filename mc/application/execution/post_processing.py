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
from mc.application.execution.strategies.provider_cli import ProviderCliRunnerStrategy
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


def _task_output_for_consolidation(result: ExecutionResult) -> str:
    return (result.output or result.error_message or "").strip()


def build_session_boundary_memory_consolidation_hook(
    *,
    bridge: Any | None = None,
    runner_type: RunnerType | None = None,
):
    """Return the canonical memory consolidation hook for session boundaries."""

    async def session_boundary_memory_consolidation_hook(
        request: ExecutionRequest,
        result: ExecutionResult,
    ) -> None:
        if runner_type is not None and request.runner_type != runner_type:
            return
        if runner_type is None and request.runner_type == RunnerType.HUMAN:
            return

        backend = request.runner_type.value

        if request.session_boundary_reason is None:
            _log_consolidation_event(
                agent_name=request.agent_name,
                backend=backend,
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
                backend=backend,
                channel="mc",
                trigger_type="session_boundary",
                boundary_reason=request.session_boundary_reason,
                memory_workspace=None,
                artifacts_workspace=None,
                action="skipped",
                skip_reason="missing_memory_workspace",
            )
            return

        task_output = _task_output_for_consolidation(result)

        async def _consolidate() -> None:
            try:
                if result.memory_workspace is None:
                    return
                model = resolve_consolidation_model(bridge)
                if model is None:
                    _log_consolidation_event(
                        agent_name=request.agent_name,
                        backend=backend,
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
                    backend=backend,
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
                    backend=backend,
                    channel="mc",
                    trigger_type="session_boundary",
                    boundary_reason=request.session_boundary_reason,
                    memory_workspace=result.memory_workspace,
                    artifacts_workspace=result.memory_workspace,
                    action="failed",
                    skip_reason="exception",
                )
                logger.warning(
                    "[execution] %s memory consolidation failed for task '%s'",
                    backend,
                    request.task_id,
                    exc_info=True,
                )

        create_background_task(_consolidate())

    return session_boundary_memory_consolidation_hook


def build_cc_task_memory_consolidation_hook(
    *,
    bridge: Any | None = None,
):
    """Return the canonical Claude Code task-boundary consolidation hook."""
    return build_session_boundary_memory_consolidation_hook(
        bridge=bridge,
        runner_type=RunnerType.CLAUDE_CODE,
    )


def build_interactive_memory_consolidation_hook(
    *,
    bridge: Any | None = None,
):
    """Return the canonical memory hook for interactive TUI step execution."""
    return build_session_boundary_memory_consolidation_hook(
        bridge=bridge,
        runner_type=RunnerType.INTERACTIVE_TUI,
    )


def build_provider_cli_memory_consolidation_hook(
    *,
    bridge: Any | None = None,
):
    """Return the canonical memory hook for provider-cli execution."""
    return build_session_boundary_memory_consolidation_hook(
        bridge=bridge,
        runner_type=RunnerType.PROVIDER_CLI,
    )


def build_execution_engine(
    *,
    bridge: Any | None = None,
    cron_service: Any | None = None,
    ask_user_registry: Any | None = None,
    interactive_session_coordinator: Any | None = None,
    provider_cli_registry: Any | None = None,
    provider_cli_supervisor: Any | None = None,
    provider_cli_command: list[str] | None = None,
    provider_cli_cwd: str = ".",
    provider_cli_projector: Any | None = None,
    provider_cli_supervision_sink: Any | None = None,
    provider_cli_control_plane: Any | None = None,
) -> ExecutionEngine:
    """Create the canonical execution engine used by production runtime paths."""
    from mc.contexts.provider_cli.providers.claude_code import ClaudeCodeCLIParser
    from mc.contexts.provider_cli.registry import ProviderSessionRegistry
    from mc.runtime.provider_cli.process_supervisor import ProviderProcessSupervisor

    # Resolve provider-cli runtime services: use injected instances or create defaults.
    _registry = (
        provider_cli_registry if provider_cli_registry is not None else ProviderSessionRegistry()
    )
    _supervisor = (
        provider_cli_supervisor
        if provider_cli_supervisor is not None
        else ProviderProcessSupervisor()
    )
    _command = provider_cli_command or [
        "claude",
        "--verbose",
        "--output-format",
        "stream-json",
    ]
    _parser = ClaudeCodeCLIParser(supervisor=_supervisor)

    return ExecutionEngine(
        strategies={
            RunnerType.CLAUDE_CODE: ClaudeCodeRunnerStrategy(
                bridge=bridge,
                cron_service=cron_service,
                ask_user_registry=ask_user_registry,
            ),
            RunnerType.HUMAN: HumanRunnerStrategy(),
            # DEPRECATED: INTERACTIVE_TUI is the legacy escape hatch.
            # The supported path for new step execution is PROVIDER_CLI.
            RunnerType.INTERACTIVE_TUI: InteractiveTuiRunnerStrategy(
                bridge=bridge,
                session_coordinator=interactive_session_coordinator,
            ),
            RunnerType.PROVIDER_CLI: ProviderCliRunnerStrategy(
                parser=_parser,
                registry=_registry,
                supervisor=_supervisor,
                command=_command,
                cwd=provider_cli_cwd,
                projector=provider_cli_projector,
                supervision_sink=provider_cli_supervision_sink,
                control_plane=provider_cli_control_plane,
                bridge=bridge,
            ),
        },
        post_execution_hooks=[
            relocate_invalid_memory_hook,
            build_session_boundary_memory_consolidation_hook(bridge=bridge),
        ],
    )
