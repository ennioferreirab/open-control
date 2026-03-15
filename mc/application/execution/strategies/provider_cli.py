"""ProviderCliRunnerStrategy — executes tasks via the generic provider CLI session core.

This strategy is provider-agnostic: it delegates to any ProviderCLIParser
implementation (e.g. ClaudeCodeCLIParser, CodexCLIParser).  The parser
encapsulates all provider-specific logic; the strategy only orchestrates the
execution lifecycle.

Story 28.2 wires Claude Code as the first provider.
"""

from __future__ import annotations

import logging
from typing import Any

from mc.application.execution.request import (
    ErrorCategory,
    ExecutionRequest,
    ExecutionResult,
)
from mc.contexts.provider_cli.registry import ProviderSessionRegistry
from mc.contexts.provider_cli.types import ParsedCliEvent, SessionStatus

logger = logging.getLogger(__name__)


class ProviderCliRunnerStrategy:
    """Run agent work through the provider CLI session core.

    Provider-agnostic: any ProviderCLIParser implementation can be injected.
    The strategy owns the execution lifecycle:
      1. Launch the provider CLI process via the parser's start_session.
      2. Register the session in ProviderSessionRegistry.
      3. Stream and parse output via the parser.
      4. Wait for process exit and return ExecutionResult.

    Provider-specific concerns (JSON format, session ID discovery, resume
    semantics) are entirely inside the parser.
    """

    def __init__(
        self,
        *,
        parser: Any,
        registry: ProviderSessionRegistry,
        supervisor: Any,
        command: list[str],
        cwd: str,
    ) -> None:
        self._parser = parser
        self._registry = registry
        self._supervisor = supervisor
        self._command = command
        self._cwd = cwd

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute a task via the provider CLI backend.

        Returns ExecutionResult.  Never raises for expected failures.
        """
        try:
            return await self._run(request)
        except Exception as exc:
            logger.error(
                "[provider-cli-strategy] Runner error for task '%s': %s",
                request.title,
                exc,
            )
            return ExecutionResult(
                success=False,
                error_category=ErrorCategory.RUNNER,
                error_message=f"{type(exc).__name__}: {exc}",
                error_exception=exc,
            )

    def _build_command(self, request: ExecutionRequest) -> list[str]:
        """Build the full command for the provider CLI process.

        Appends ``--prompt <request.prompt>`` to the base command when the
        request carries a non-empty prompt.  The base command list stored in
        ``self._command`` is never mutated — a new list is always returned.
        """
        command = list(self._command)
        if request.prompt:
            command.extend(["--prompt", request.prompt])
        return command

    async def _run(self, request: ExecutionRequest) -> ExecutionResult:
        """Core execution — raises on failure for the outer handler."""
        mc_session_id = f"{request.task_id}-{request.entity_id}"

        # 1. Build the full command, injecting the bootstrap prompt
        command = self._build_command(request)

        # 2. Launch the provider CLI process
        handle = await self._parser.start_session(
            mc_session_id=mc_session_id,
            command=command,
            cwd=self._cwd,
        )

        # 2. Register the session
        record = self._registry.create(
            mc_session_id=handle.mc_session_id,
            provider=self._parser.provider_name,
            pid=handle.pid,
            pgid=handle.pgid,
            mode="provider-native",
            supports_resume=True,
            supports_interrupt=True,
            supports_stop=True,
        )

        # 3. Transition to RUNNING
        self._registry.update_status(handle.mc_session_id, SessionStatus.RUNNING)

        # 4. Stream and parse output
        collected_events: list[ParsedCliEvent] = []
        try:
            async for chunk in self._supervisor.stream_output(handle):
                if not chunk:
                    continue
                events = self._parser.parse_output(chunk)
                for event in events:
                    collected_events.append(event)
                    # Update registry with discovered session ID
                    if event.kind == "session_id" and event.provider_session_id:
                        self._registry.update_provider_session_id(
                            handle.mc_session_id, event.provider_session_id
                        )
                        record.provider_session_id = event.provider_session_id
        except Exception as exc:
            logger.warning(
                "[provider-cli-strategy] Stream error for session '%s': %s",
                mc_session_id,
                exc,
            )

        # 5. Wait for exit
        exit_code = await self._supervisor.wait_for_exit(handle)

        # 6. Evaluate result
        error_events = [e for e in collected_events if e.kind == "error"]
        result_events = [e for e in collected_events if e.kind == "result"]

        # Discover session ID
        session_id = record.provider_session_id
        if session_id is None:
            sid_events = [e for e in collected_events if e.kind == "session_id"]
            session_id = sid_events[0].provider_session_id if sid_events else None

        # Determine output text
        output_text = ""
        if result_events:
            output_text = result_events[-1].text or ""
        elif error_events:
            output_text = error_events[0].text or ""

        # Determine success
        has_error = bool(error_events) or (exit_code is not None and exit_code != 0)

        if has_error:
            error_msg = (
                error_events[0].text if error_events else f"Process exited with code {exit_code}"
            )
            self._registry.update_status(handle.mc_session_id, SessionStatus.CRASHED)
            return ExecutionResult(
                success=False,
                error_category=ErrorCategory.RUNNER,
                error_message=error_msg,
                session_id=session_id,
            )

        self._registry.update_status(handle.mc_session_id, SessionStatus.COMPLETED)
        return ExecutionResult(
            success=True,
            output=output_text,
            session_id=session_id,
        )
