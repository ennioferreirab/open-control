"""ProviderCliRunnerStrategy — executes tasks via the generic provider CLI session core.

This strategy is provider-agnostic: it delegates to any ProviderCLIParser
implementation (e.g. ClaudeCodeCLIParser, CodexCLIParser).  The parser
encapsulates all provider-specific logic; the strategy only orchestrates the
execution lifecycle.

Story 28.2 wires Claude Code as the first provider.
Story 28.18 adds LiveStreamProjector and supervision_sink wiring.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from mc.application.execution.request import (
    ErrorCategory,
    ExecutionRequest,
    ExecutionResult,
)
from mc.contexts.provider_cli.registry import ProviderSessionRegistry
from mc.contexts.provider_cli.types import ParsedCliEvent, SessionStatus

if TYPE_CHECKING:
    from mc.runtime.provider_cli.live_stream import LiveStreamProjector

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

    Optional wiring (Story 28-18):
      - projector: LiveStreamProjector — projects each ParsedCliEvent into an
        ordered, timestamped stream so downstream subscribers can observe activity.
      - supervision_sink: callable — receives a normalized dict payload for each
        projected event, enabling the gateway to route events into the supervision
        pipeline (e.g. InteractiveExecutionSupervisor.handle_event).
    """

    def __init__(
        self,
        *,
        parser: Any,
        registry: ProviderSessionRegistry,
        supervisor: Any,
        command: list[str],
        cwd: str,
        projector: "LiveStreamProjector | None" = None,
        supervision_sink: Callable[[dict[str, Any]], None] | None = None,
        control_plane: Any | None = None,
    ) -> None:
        self._parser = parser
        self._registry = registry
        self._supervisor = supervisor
        self._command = command
        self._cwd = cwd
        self._projector = projector
        self._control_plane = control_plane
        self._supervision_sink = supervision_sink

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

    def _cleanup(self, mc_session_id: str) -> None:
        """Remove the session record from the registry after execution completes."""
        if self._control_plane is not None:
            self._control_plane.unregister_parser(mc_session_id)
        self._registry.remove(mc_session_id)

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

        # 3. Register the session
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

        # 4. Transition to RUNNING
        self._registry.update_status(handle.mc_session_id, SessionStatus.RUNNING)

        # 4b. Register parser/handle in control plane for intervention routing
        if self._control_plane is not None:
            self._control_plane.register_parser(
                handle.mc_session_id, parser=self._parser, handle=handle
            )

        # 5. Stream and parse output
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
                    # Project the event through the live stream projector (Story 28-18)
                    if self._projector is not None:
                        projected = self._projector.project(event, session_id=mc_session_id)
                        # Deliver normalized payload to supervision sink if wired
                        if self._supervision_sink is not None:
                            self._supervision_sink(
                                {
                                    "session_id": mc_session_id,
                                    "kind": event.kind,
                                    "text": event.text,
                                    "provider_session_id": event.provider_session_id,
                                    "metadata": event.metadata,
                                    "sequence": projected.sequence,
                                    "timestamp": projected.timestamp,
                                }
                            )
        except Exception as exc:
            logger.warning(
                "[provider-cli-strategy] Stream error for session '%s': %s",
                mc_session_id,
                exc,
            )

        # 6. Wait for exit
        exit_code = await self._supervisor.wait_for_exit(handle)

        # 7. Evaluate result
        error_events = [e for e in collected_events if e.kind == "error"]
        result_events = [e for e in collected_events if e.kind == "result"]
        text_events = [e for e in collected_events if e.kind == "text"]

        # Discover session ID
        session_id = record.provider_session_id
        if session_id is None:
            sid_events = [e for e in collected_events if e.kind == "session_id"]
            session_id = sid_events[0].provider_session_id if sid_events else None

        # Determine output text:
        #   1. canonical: last result event text
        #   2. fallback: concatenation of all text events (when no result event)
        output_text = ""
        if result_events:
            output_text = result_events[-1].text or ""
        elif text_events:
            output_text = "".join(e.text or "" for e in text_events)
        elif error_events:
            output_text = error_events[0].text or ""

        # Determine success
        has_error = bool(error_events) or (exit_code is not None and exit_code != 0)

        if has_error:
            error_msg = (
                error_events[0].text if error_events else f"Process exited with code {exit_code}"
            )
            self._registry.update_status(handle.mc_session_id, SessionStatus.CRASHED)
            self._cleanup(handle.mc_session_id)
            return ExecutionResult(
                success=False,
                error_category=ErrorCategory.RUNNER,
                error_message=error_msg,
                session_id=session_id,
            )

        self._registry.update_status(handle.mc_session_id, SessionStatus.COMPLETED)
        self._cleanup(handle.mc_session_id)
        return ExecutionResult(
            success=True,
            output=output_text,
            session_id=session_id,
        )
