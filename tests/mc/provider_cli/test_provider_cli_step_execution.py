"""Integration-style backend tests for provider CLI step execution path.

Story 28-15 — Prove that the full provider-CLI step execution path works
end-to-end without PTY/tmux dependencies or InteractiveSessionCoordinator.

Tests:
    1. Full path integration — context builder → runner type resolution →
       strategy execution → registry cleanup.
    2. No tmux dependency — importing the provider-CLI execution modules
       does NOT import tmux modules.
    3. No InteractiveSessionCoordinator dependency — ProviderCliRunnerStrategy
       works without the coordinator.
    4. Prompt presence — ContextBuilder populates request.prompt and
       _build_command produces a command using `-p <prompt>`.
    5. Completion and crash projection — exit 0 → COMPLETED, exit 1 → CRASHED.
"""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.application.execution.interactive_mode import resolve_step_runner_type
from mc.application.execution.request import EntityType, ExecutionRequest, RunnerType
from mc.application.execution.strategies.provider_cli import ProviderCliRunnerStrategy
from mc.contexts.provider_cli.registry import ProviderSessionRegistry
from mc.contexts.provider_cli.types import ParsedCliEvent, ProviderProcessHandle, SessionStatus
from mc.types import AgentData

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_interactive_request(
    *,
    task_id: str = "task-001",
    step_id: str = "step-001",
    agent_name: str = "agent-cc",
    provider: str = "claude-code",
    prompt: str = "Implement the feature",
) -> ExecutionRequest:
    """Build a minimal ExecutionRequest for an interactive agent step."""
    return ExecutionRequest(
        entity_type=EntityType.STEP,
        entity_id=step_id,
        task_id=task_id,
        step_id=step_id,
        title="Test Task",
        step_title="Implement feature",
        step_description="Do the thing",
        agent_name=agent_name,
        agent=AgentData(
            name=agent_name,
            display_name="CC Agent",
            role="Engineer",
            backend="claude-code",
            interactive_provider=provider,
        ),
        is_cc=True,
        prompt=prompt,
    )


def _make_mock_bridge(
    *,
    task_data: dict[str, Any] | None = None,
    agent_data: dict[str, Any] | None = None,
) -> MagicMock:
    """Create a mock ConvexBridge with configurable return values."""
    bridge = MagicMock()

    default_task: dict[str, Any] = task_data or {
        "id": "task-001",
        "title": "Test Task",
        "description": "A step task",
        "board_id": "board_001",
        "files": [],
        "tags": [],
    }

    def mock_query(fn_name: str, args: dict[str, Any]) -> Any:
        if fn_name == "tasks:getById":
            return default_task
        if fn_name == "tagAttributeValues:getByTask":
            return []
        if fn_name == "tagAttributes:list":
            return []
        return None

    bridge.query = mock_query
    bridge.get_agent_by_name = MagicMock(return_value=agent_data)
    bridge.get_task_messages = MagicMock(return_value=[])
    bridge.get_board_by_id = MagicMock(return_value=None)
    bridge.get_steps_by_task = MagicMock(return_value=[])
    return bridge


def _make_mock_handle(mc_session_id: str = "task-001-step-001") -> ProviderProcessHandle:
    """Create a mock ProviderProcessHandle."""
    return ProviderProcessHandle(
        mc_session_id=mc_session_id,
        provider="claude-code",
        pid=12345,
        pgid=12345,
        cwd=".",
        command=["claude", "--print"],
        started_at="2026-01-01T00:00:00+00:00",
    )


# ---------------------------------------------------------------------------
# Test 1: Full path integration test
# ---------------------------------------------------------------------------


class TestFullPathIntegration:
    """Integration test: ContextBuilder → runner type → strategy → registry."""

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.context_builder.load_agent_config",
        return_value=(None, None, None),
    )
    @patch(
        "mc.application.execution.context_builder.inject_orientation",
        side_effect=lambda n, p, **kw: p,
    )
    @patch("mc.application.execution.context_builder.resolve_tier", return_value=(None, None))
    async def test_full_path_integration(
        self,
        mock_tier: MagicMock,
        mock_orientation: MagicMock,
        mock_config: MagicMock,
    ) -> None:
        """Context builder → runner type → strategy returns a result.

        Verifies the full path:
        1. ContextBuilder builds a step request.
        2. resolve_step_runner_type returns PROVIDER_CLI.
        3. ProviderCliRunnerStrategy executes and returns a result.
        4. Session registry is cleaned up after execution.
        """
        from mc.application.execution.context_builder import ContextBuilder

        bridge = _make_mock_bridge()
        builder = ContextBuilder(bridge)

        step = {
            "id": "step-001",
            "title": "Implement feature",
            "description": "Do the thing",
            "assigned_agent": "agent-cc",
            "blocked_by": [],
        }

        # 1. Build step context
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("MC_INTERACTIVE_EXECUTION_MODE", None)
            # Override agent to have interactive_provider so resolution works
            req = await builder.build_step_context(task_id="task-001", step=step)

        # Manually set fields that require a live CC agent
        req.is_cc = True
        req.agent = AgentData(
            name="agent-cc",
            display_name="CC Agent",
            role="Engineer",
            backend="claude-code",
            interactive_provider="claude-code",
        )
        req.prompt = req.description or req.step_description or req.step_title

        # 2. Resolve runner type → should be PROVIDER_CLI
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("MC_INTERACTIVE_EXECUTION_MODE", None)
            runner_type = resolve_step_runner_type(req)

        assert runner_type == RunnerType.PROVIDER_CLI

        # 3. Execute through strategy (with mocked supervisor and parser)
        registry = ProviderSessionRegistry()
        mock_supervisor = MagicMock()
        mock_parser = MagicMock()

        handle = _make_mock_handle("task-001-step-001")
        mock_parser.start_session = AsyncMock(return_value=handle)
        mock_parser.provider_name = "claude-code"
        mock_parser.parse_output = MagicMock(
            return_value=[ParsedCliEvent(kind="result", text="Done!")]
        )

        async def _fake_stream(h: ProviderProcessHandle):
            yield b'{"type": "result", "subtype": "success", "result": "Done!"}'

        mock_supervisor.stream_output = _fake_stream
        mock_supervisor.wait_for_exit = AsyncMock(return_value=0)

        strategy = ProviderCliRunnerStrategy(
            parser=mock_parser,
            registry=registry,
            supervisor=mock_supervisor,
            command=["claude", "--output-format", "stream-json", "--print"],
            cwd=".",
        )

        result = await strategy.execute(req)

        # 4. Verify result and registry cleanup
        assert result.success is True
        assert registry.get("task-001-step-001") is None  # cleaned up


# ---------------------------------------------------------------------------
# Test 2: No tmux dependency
# ---------------------------------------------------------------------------


class TestNoTmuxDependency:
    """Verify that importing the provider-CLI execution path avoids tmux modules."""

    def test_provider_cli_imports_do_not_load_tmux_modules(self) -> None:
        """Importing provider-CLI strategy, supervisor, and parser must NOT import tmux.

        mc.infrastructure.interactive.tmux must not appear in sys.modules after
        importing the provider-CLI stack.
        """
        # Remove any prior tmux import to start clean
        tmux_key = "mc.infrastructure.interactive.tmux"
        previously_loaded = tmux_key in sys.modules
        sys.modules.pop(tmux_key, None)

        # Import the full provider-CLI stack
        import importlib

        importlib.import_module("mc.application.execution.strategies.provider_cli")
        importlib.import_module("mc.runtime.provider_cli.process_supervisor")
        importlib.import_module("mc.contexts.provider_cli.providers.claude_code")

        # Check that tmux was NOT imported as a side effect
        assert tmux_key not in sys.modules, (
            "Importing the provider-CLI execution path caused mc.infrastructure.interactive.tmux "
            "to be loaded. The provider-CLI backend must not depend on tmux infrastructure."
        )

        # Restore prior state if it was loaded before
        if previously_loaded:
            importlib.import_module(tmux_key)


# ---------------------------------------------------------------------------
# Test 3: No InteractiveSessionCoordinator dependency
# ---------------------------------------------------------------------------


class TestNoInteractiveSessionCoordinatorDependency:
    """ProviderCliRunnerStrategy must not depend on InteractiveSessionCoordinator."""

    def test_strategy_source_has_no_coordinator_reference(self) -> None:
        """The provider_cli.py strategy source must not reference InteractiveSessionCoordinator."""
        import pathlib

        strategy_path = (
            pathlib.Path(__file__).parents[3]
            / "mc"
            / "application"
            / "execution"
            / "strategies"
            / "provider_cli.py"
        )
        source = strategy_path.read_text(encoding="utf-8")
        assert "InteractiveSessionCoordinator" not in source, (
            "ProviderCliRunnerStrategy must not import or reference InteractiveSessionCoordinator. "
            "It is a fully independent backend."
        )

    def test_strategy_instantiation_requires_no_coordinator(self) -> None:
        """ProviderCliRunnerStrategy can be built without a coordinator argument."""
        registry = ProviderSessionRegistry()
        mock_supervisor = MagicMock()
        mock_parser = MagicMock()
        mock_parser.provider_name = "claude-code"

        # Must not raise — no session_coordinator parameter
        strategy = ProviderCliRunnerStrategy(
            parser=mock_parser,
            registry=registry,
            supervisor=mock_supervisor,
            command=["claude", "--print"],
            cwd=".",
        )
        assert strategy is not None

    def test_build_execution_engine_provider_cli_strategy_has_no_coordinator(self) -> None:
        """build_execution_engine() creates a ProviderCliRunnerStrategy with no coordinator."""
        from mc.application.execution.post_processing import build_execution_engine

        engine = build_execution_engine()
        strategy = engine.get_strategy(RunnerType.PROVIDER_CLI)
        assert isinstance(strategy, ProviderCliRunnerStrategy)
        # The strategy must not have a session_coordinator attribute
        assert not hasattr(strategy, "_session_coordinator"), (
            "ProviderCliRunnerStrategy must not carry a session_coordinator dependency."
        )


# ---------------------------------------------------------------------------
# Test 4: Prompt presence from canonical path
# ---------------------------------------------------------------------------


class TestPromptPresenceFromCanonicalPath:
    """ContextBuilder.build_step_context populates request.prompt; _build_command uses it."""

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.context_builder.load_agent_config",
        return_value=(None, None, None),
    )
    @patch(
        "mc.application.execution.context_builder.inject_orientation",
        side_effect=lambda n, p, **kw: p,
    )
    @patch("mc.application.execution.context_builder.resolve_tier", return_value=(None, None))
    async def test_build_step_context_populates_prompt(
        self,
        mock_tier: MagicMock,
        mock_orientation: MagicMock,
        mock_config: MagicMock,
    ) -> None:
        """After build_step_context, request.prompt must be non-empty."""
        from mc.application.execution.context_builder import ContextBuilder

        bridge = _make_mock_bridge(
            task_data={
                "id": "task-001",
                "title": "Build feature",
                "description": "A serious task",
                "board_id": "board_001",
                "files": [],
                "tags": [],
            }
        )
        builder = ContextBuilder(bridge)
        step = {
            "id": "step-99",
            "title": "Write tests",
            "description": "Write comprehensive tests for the feature",
            "assigned_agent": "dev-agent",
            "blocked_by": [],
        }
        req = await builder.build_step_context(task_id="task-001", step=step)
        assert req.prompt, (
            "request.prompt must be non-empty after build_step_context; "
            "story 28-13 requires ContextBuilder to populate the canonical prompt."
        )

    def test_build_command_appends_prompt_as_print_argument(self) -> None:
        """ProviderCliRunnerStrategy._build_command places prompt after the binary with `-p`.

        The Claude CLI does not have a ``--prompt`` flag.  The correct invocation is:
            claude -p "prompt text" [flags...]
        where ``-p`` is equivalent to ``--print`` and the prompt is a positional argument.
        """
        registry = ProviderSessionRegistry()
        mock_supervisor = MagicMock()
        mock_parser = MagicMock()
        mock_parser.provider_name = "claude-code"

        base_command = ["claude", "--output-format", "stream-json", "--print"]
        strategy = ProviderCliRunnerStrategy(
            parser=mock_parser,
            registry=registry,
            supervisor=mock_supervisor,
            command=base_command,
            cwd=".",
        )

        req = _make_interactive_request(prompt="Implement the feature end-to-end")
        command = strategy._build_command(req)

        assert "--prompt" not in command
        assert command[1:3] == ["-p", "Implement the feature end-to-end"]

    def test_build_command_without_prompt_does_not_append_argument(self) -> None:
        """When request.prompt is empty, no `-p` prompt is added to the command."""
        registry = ProviderSessionRegistry()
        mock_supervisor = MagicMock()
        mock_parser = MagicMock()
        mock_parser.provider_name = "claude-code"

        base_command = ["claude", "--output-format", "stream-json", "--print"]
        strategy = ProviderCliRunnerStrategy(
            parser=mock_parser,
            registry=registry,
            supervisor=mock_supervisor,
            command=base_command,
            cwd=".",
        )

        req = _make_interactive_request(prompt="")
        command = strategy._build_command(req)

        assert "--prompt" not in command
        assert "-p" not in command


# ---------------------------------------------------------------------------
# Test 5: Completion and crash projection
# ---------------------------------------------------------------------------


class TestCompletionAndCrashProjection:
    """Success (exit 0) → COMPLETED; crash (exit 1) → CRASHED."""

    def _make_strategy(
        self, registry: ProviderSessionRegistry
    ) -> tuple[ProviderCliRunnerStrategy, MagicMock, MagicMock]:
        """Return (strategy, mock_parser, mock_supervisor)."""
        mock_supervisor = MagicMock()
        mock_parser = MagicMock()
        mock_parser.provider_name = "claude-code"

        strategy = ProviderCliRunnerStrategy(
            parser=mock_parser,
            registry=registry,
            supervisor=mock_supervisor,
            command=["claude", "--output-format", "stream-json", "--print"],
            cwd=".",
        )
        return strategy, mock_parser, mock_supervisor

    @pytest.mark.asyncio
    async def test_success_path_returns_completed(self) -> None:
        """exit 0 + result event → success=True, registry entry removed."""
        registry = ProviderSessionRegistry()
        strategy, mock_parser, mock_supervisor = self._make_strategy(registry)

        handle = _make_mock_handle("task-001-step-001")
        mock_parser.start_session = AsyncMock(return_value=handle)
        mock_parser.parse_output = MagicMock(
            return_value=[ParsedCliEvent(kind="result", text="Task complete")]
        )

        async def _stream(h: ProviderProcessHandle):
            yield b'{"type": "result", "subtype": "success", "result": "Task complete"}'

        mock_supervisor.stream_output = _stream
        mock_supervisor.wait_for_exit = AsyncMock(return_value=0)

        req = _make_interactive_request()
        result = await strategy.execute(req)

        assert result.success is True
        assert result.output == "Task complete"
        assert result.error_message is None
        # Registry entry should be cleaned up
        assert registry.get("task-001-step-001") is None

    @pytest.mark.asyncio
    async def test_crash_path_exit_one_returns_crashed(self) -> None:
        """exit 1 with no result event → success=False, error message populated."""
        registry = ProviderSessionRegistry()
        strategy, mock_parser, mock_supervisor = self._make_strategy(registry)

        handle = _make_mock_handle("task-001-step-001")
        mock_parser.start_session = AsyncMock(return_value=handle)
        mock_parser.parse_output = MagicMock(return_value=[])

        async def _stream(h: ProviderProcessHandle):
            yield b""

        mock_supervisor.stream_output = _stream
        mock_supervisor.wait_for_exit = AsyncMock(return_value=1)

        req = _make_interactive_request()
        result = await strategy.execute(req)

        assert result.success is False
        assert result.error_message is not None
        assert "1" in result.error_message or "exit" in result.error_message.lower()
        # Registry entry should be cleaned up after crash
        assert registry.get("task-001-step-001") is None

    @pytest.mark.asyncio
    async def test_crash_path_error_event_populates_error_message(self) -> None:
        """Error event in output → success=False, error_message from event text."""
        registry = ProviderSessionRegistry()
        strategy, mock_parser, mock_supervisor = self._make_strategy(registry)

        handle = _make_mock_handle("task-001-step-001")
        mock_parser.start_session = AsyncMock(return_value=handle)
        error_event = ParsedCliEvent(kind="error", text="Tool execution failed: timeout")
        mock_parser.parse_output = MagicMock(return_value=[error_event])

        async def _stream(h: ProviderProcessHandle):
            yield b'{"type": "result", "subtype": "error", "result": "Tool execution failed: timeout"}'

        mock_supervisor.stream_output = _stream
        mock_supervisor.wait_for_exit = AsyncMock(return_value=0)

        req = _make_interactive_request()
        result = await strategy.execute(req)

        assert result.success is False
        assert "timeout" in (result.error_message or "")
        assert registry.get("task-001-step-001") is None

    @pytest.mark.asyncio
    async def test_session_registry_transitions_to_running_then_terminal(self) -> None:
        """Registry transitions: STARTING → RUNNING → (COMPLETED or CRASHED)."""
        registry = ProviderSessionRegistry()
        strategy, mock_parser, mock_supervisor = self._make_strategy(registry)

        handle = _make_mock_handle("task-001-step-001")
        mock_parser.start_session = AsyncMock(return_value=handle)
        mock_parser.parse_output = MagicMock(
            return_value=[ParsedCliEvent(kind="result", text="Done")]
        )

        statuses_seen: list[SessionStatus] = []

        original_update = registry.update_status

        def _tracking_update(mc_sid: str, new_status: SessionStatus) -> Any:
            statuses_seen.append(new_status)
            return original_update(mc_sid, new_status)

        registry.update_status = _tracking_update  # type: ignore[method-assign]

        async def _stream(h: ProviderProcessHandle):
            yield b"result"

        mock_supervisor.stream_output = _stream
        mock_supervisor.wait_for_exit = AsyncMock(return_value=0)

        req = _make_interactive_request()
        await strategy.execute(req)

        assert SessionStatus.RUNNING in statuses_seen
        assert SessionStatus.COMPLETED in statuses_seen


# ---------------------------------------------------------------------------
# Test 6: Strategy calls the projector for each event (Story 28-18)
# ---------------------------------------------------------------------------


class TestStrategyProjectorIntegration:
    """Strategy execution calls the LiveStreamProjector for each parsed event."""

    @pytest.mark.asyncio
    async def test_strategy_calls_projector_for_each_event(self) -> None:
        """Every ParsedCliEvent yielded during stream processing is projected."""
        from mc.runtime.provider_cli.live_stream import LiveStreamProjector, ProjectedEvent

        registry = ProviderSessionRegistry()
        mock_supervisor = MagicMock()
        mock_parser = MagicMock()
        mock_parser.provider_name = "claude-code"

        handle = _make_mock_handle("task-proj-001-step-001")
        mock_parser.start_session = AsyncMock(return_value=handle)

        events = [
            ParsedCliEvent(kind="text", text="Hello"),
            ParsedCliEvent(kind="text", text="World"),
            ParsedCliEvent(kind="result", text="Done"),
        ]
        mock_parser.parse_output = MagicMock(side_effect=[[e] for e in events])

        async def _stream(h: ProviderProcessHandle):
            for _ in events:
                yield b"chunk"

        mock_supervisor.stream_output = _stream
        mock_supervisor.wait_for_exit = AsyncMock(return_value=0)

        projector = LiveStreamProjector()
        projected_events: list[ProjectedEvent] = []
        projector.subscribe(projected_events.append)

        strategy = ProviderCliRunnerStrategy(
            parser=mock_parser,
            registry=registry,
            supervisor=mock_supervisor,
            command=["claude", "--output-format", "stream-json", "--print"],
            cwd=".",
            projector=projector,
        )

        req = _make_interactive_request()
        result = await strategy.execute(req)

        assert result.success is True
        # Each of the 3 events must have been projected
        assert len(projected_events) == 3
        assert projected_events[0].event.kind == "text"
        assert projected_events[0].event.text == "Hello"
        assert projected_events[1].event.text == "World"
        assert projected_events[2].event.kind == "result"
        # Sequences must be monotonically increasing
        sequences = [p.sequence for p in projected_events]
        assert sequences == sorted(sequences)
        assert sequences[0] >= 1

    @pytest.mark.asyncio
    async def test_strategy_without_projector_still_works(self) -> None:
        """When projector is None, the strategy executes normally without projecting events."""
        registry = ProviderSessionRegistry()
        mock_supervisor = MagicMock()
        mock_parser = MagicMock()
        mock_parser.provider_name = "claude-code"

        handle = _make_mock_handle("task-noproj-001-step-001")
        mock_parser.start_session = AsyncMock(return_value=handle)
        mock_parser.parse_output = MagicMock(
            return_value=[ParsedCliEvent(kind="result", text="Done")]
        )

        async def _stream(h: ProviderProcessHandle):
            yield b"chunk"

        mock_supervisor.stream_output = _stream
        mock_supervisor.wait_for_exit = AsyncMock(return_value=0)

        # No projector passed (defaults to None)
        strategy = ProviderCliRunnerStrategy(
            parser=mock_parser,
            registry=registry,
            supervisor=mock_supervisor,
            command=["claude", "--output-format", "stream-json", "--print"],
            cwd=".",
        )

        req = _make_interactive_request()
        result = await strategy.execute(req)
        assert result.success is True


# ---------------------------------------------------------------------------
# Test 7: Supervision sink receives normalized payloads (Story 28-18)
# ---------------------------------------------------------------------------


class TestStrategySupervisionSinkIntegration:
    """Strategy calls supervision_sink with normalized event payload for each event."""

    @pytest.mark.asyncio
    async def test_supervision_sink_receives_normalized_payload(self) -> None:
        """Each projected event must trigger a supervision_sink call with correct fields."""
        from mc.runtime.provider_cli.live_stream import LiveStreamProjector

        registry = ProviderSessionRegistry()
        mock_supervisor = MagicMock()
        mock_parser = MagicMock()
        mock_parser.provider_name = "claude-code"

        handle = _make_mock_handle("task-sink-001-step-001")
        mock_parser.start_session = AsyncMock(return_value=handle)

        events = [
            ParsedCliEvent(kind="text", text="stream text"),
            ParsedCliEvent(kind="result", text="final result"),
        ]
        mock_parser.parse_output = MagicMock(side_effect=[[e] for e in events])

        async def _stream(h: ProviderProcessHandle):
            for _ in events:
                yield b"chunk"

        mock_supervisor.stream_output = _stream
        mock_supervisor.wait_for_exit = AsyncMock(return_value=0)

        projector = LiveStreamProjector()
        sink_payloads: list[dict[str, Any]] = []

        strategy = ProviderCliRunnerStrategy(
            parser=mock_parser,
            registry=registry,
            supervisor=mock_supervisor,
            command=["claude", "--output-format", "stream-json", "--print"],
            cwd=".",
            projector=projector,
            supervision_sink=sink_payloads.append,
        )

        req = _make_interactive_request(task_id="task-sink-001", step_id="step-001")
        result = await strategy.execute(req)

        assert result.success is True
        # Sink must have been called once per event
        assert len(sink_payloads) == 2

        # Verify first payload shape
        first = sink_payloads[0]
        assert "session_id" in first
        assert "kind" in first
        assert "sequence" in first
        assert "timestamp" in first
        assert first["kind"] == "text"
        assert first["text"] == "stream text"
        assert first["session_id"] == "task-sink-001-step-001"
        assert isinstance(first["sequence"], int)
        assert first["sequence"] >= 1

        # Verify second payload
        second = sink_payloads[1]
        assert second["kind"] == "result"
        assert second["text"] == "final result"
        assert second["sequence"] == first["sequence"] + 1

    @pytest.mark.asyncio
    async def test_supervision_sink_payload_includes_all_required_fields(self) -> None:
        """The normalized payload must include all fields documented in Story 28-18."""
        from mc.runtime.provider_cli.live_stream import LiveStreamProjector

        registry = ProviderSessionRegistry()
        mock_supervisor = MagicMock()
        mock_parser = MagicMock()
        mock_parser.provider_name = "claude-code"

        handle = _make_mock_handle("task-fields-001-step-001")
        mock_parser.start_session = AsyncMock(return_value=handle)

        event = ParsedCliEvent(
            kind="session_id",
            text=None,
            provider_session_id="prov-sess-abc",
            metadata={"extra": "data"},
        )
        mock_parser.parse_output = MagicMock(return_value=[event])

        async def _stream(h: ProviderProcessHandle):
            yield b"chunk"

        mock_supervisor.stream_output = _stream
        mock_supervisor.wait_for_exit = AsyncMock(return_value=0)

        projector = LiveStreamProjector()
        sink_payloads: list[dict[str, Any]] = []

        strategy = ProviderCliRunnerStrategy(
            parser=mock_parser,
            registry=registry,
            supervisor=mock_supervisor,
            command=["claude", "--output-format", "stream-json", "--print"],
            cwd=".",
            projector=projector,
            supervision_sink=sink_payloads.append,
        )

        req = _make_interactive_request(task_id="task-fields-001", step_id="step-001")
        await strategy.execute(req)

        assert len(sink_payloads) == 1
        payload = sink_payloads[0]

        # All Story 28-18 required fields must be present
        required_fields = {
            "session_id",
            "kind",
            "text",
            "provider_session_id",
            "metadata",
            "sequence",
            "timestamp",
        }
        assert required_fields <= payload.keys(), (
            f"Missing required payload fields: {required_fields - payload.keys()}"
        )
        assert payload["session_id"] == "task-fields-001-step-001"
        assert payload["kind"] == "session_id"
        assert payload["provider_session_id"] == "prov-sess-abc"
        assert payload["metadata"] == {"extra": "data"}

    @pytest.mark.asyncio
    async def test_supervision_sink_not_called_when_none(self) -> None:
        """When supervision_sink is None, no error occurs and strategy succeeds."""
        from mc.runtime.provider_cli.live_stream import LiveStreamProjector

        registry = ProviderSessionRegistry()
        mock_supervisor = MagicMock()
        mock_parser = MagicMock()
        mock_parser.provider_name = "claude-code"

        handle = _make_mock_handle("task-nosink-001-step-001")
        mock_parser.start_session = AsyncMock(return_value=handle)
        mock_parser.parse_output = MagicMock(
            return_value=[ParsedCliEvent(kind="result", text="Done")]
        )

        async def _stream(h: ProviderProcessHandle):
            yield b"chunk"

        mock_supervisor.stream_output = _stream
        mock_supervisor.wait_for_exit = AsyncMock(return_value=0)

        projector = LiveStreamProjector()
        strategy = ProviderCliRunnerStrategy(
            parser=mock_parser,
            registry=registry,
            supervisor=mock_supervisor,
            command=["claude", "--output-format", "stream-json", "--print"],
            cwd=".",
            projector=projector,
            supervision_sink=None,
        )

        req = _make_interactive_request()
        result = await strategy.execute(req)
        assert result.success is True


# ---------------------------------------------------------------------------
# Test 8: Story 28-29 — provider_session_id and bootstrap_prompt reach Convex
# ---------------------------------------------------------------------------


class TestProviderCliMetadataPersistenceToConvex:
    """Prove that provider_session_id and bootstrap_prompt reach Convex from the real runtime path.

    Story 28-29 — The ProviderCliRunnerStrategy must persist provider-cli metadata to
    interactiveSessions via the bridge when bridge is injected.
    """

    @pytest.mark.asyncio
    async def test_provider_session_id_persisted_to_convex_on_discovery(self) -> None:
        """When a session_id event is parsed, provider_session_id must be persisted to Convex."""
        registry = ProviderSessionRegistry()
        mock_supervisor = MagicMock()
        mock_parser = MagicMock()
        mock_parser.provider_name = "claude-code"

        handle = _make_mock_handle("task-persist-001-step-001")
        mock_parser.start_session = AsyncMock(return_value=handle)

        session_id_event = ParsedCliEvent(
            kind="session_id",
            text="claude-sess-29-abc",
            provider_session_id="claude-sess-29-abc",
        )
        result_event = ParsedCliEvent(kind="result", text="Done")
        mock_parser.parse_output = MagicMock(side_effect=[[session_id_event], [result_event]])

        async def _stream(h: ProviderProcessHandle):
            yield b"chunk1"
            yield b"chunk2"

        mock_supervisor.stream_output = _stream
        mock_supervisor.wait_for_exit = AsyncMock(return_value=0)

        bridge = MagicMock()

        strategy = ProviderCliRunnerStrategy(
            parser=mock_parser,
            registry=registry,
            supervisor=mock_supervisor,
            command=["claude", "--output-format", "stream-json", "--print"],
            cwd=".",
            bridge=bridge,
        )

        req = _make_interactive_request(task_id="task-persist-001", step_id="step-001")
        result = await strategy.execute(req)

        assert result.success is True
        assert result.session_id == "claude-sess-29-abc"

        # Verify bridge was called to persist provider_session_id to Convex
        patch_calls = [
            call
            for call in bridge.mutation.call_args_list
            if call[0][0] == "interactiveSessions:patchProviderCliMetadata"
        ]
        assert len(patch_calls) >= 1, (
            "interactiveSessions:patchProviderCliMetadata must be called when provider_session_id "
            "is discovered"
        )
        # At least one call must include provider_session_id
        sid_calls = [c for c in patch_calls if c[0][1].get("provider_session_id")]
        assert len(sid_calls) >= 1, "provider_session_id must be persisted"
        assert sid_calls[0][0][1]["provider_session_id"] == "claude-sess-29-abc"

    @pytest.mark.asyncio
    async def test_bootstrap_prompt_persisted_to_convex_on_session_create(self) -> None:
        """On session startup, bootstrap_prompt must be persisted to Convex via bridge."""
        registry = ProviderSessionRegistry()
        mock_supervisor = MagicMock()
        mock_parser = MagicMock()
        mock_parser.provider_name = "claude-code"

        handle = _make_mock_handle("task-bp-001-step-001")
        mock_parser.start_session = AsyncMock(return_value=handle)
        mock_parser.parse_output = MagicMock(
            return_value=[ParsedCliEvent(kind="result", text="Done")]
        )

        async def _stream(h: ProviderProcessHandle):
            yield b"result"

        mock_supervisor.stream_output = _stream
        mock_supervisor.wait_for_exit = AsyncMock(return_value=0)

        bridge = MagicMock()

        strategy = ProviderCliRunnerStrategy(
            parser=mock_parser,
            registry=registry,
            supervisor=mock_supervisor,
            command=["claude", "--output-format", "stream-json", "--print"],
            cwd=".",
            bridge=bridge,
        )

        req = _make_interactive_request(
            task_id="task-bp-001",
            step_id="step-001",
            prompt="Write comprehensive tests for the authentication module.",
        )
        result = await strategy.execute(req)

        assert result.success is True

        # Verify bridge was called with bootstrap_prompt via interactiveSessions:upsert
        upsert_calls = [
            call
            for call in bridge.mutation.call_args_list
            if call[0][0] == "interactiveSessions:upsert"
        ]
        assert len(upsert_calls) >= 1, (
            "interactiveSessions:upsert must be called on session startup"
        )
        bp_calls = [c for c in upsert_calls if c[0][1].get("bootstrap_prompt")]
        assert len(bp_calls) >= 1, "bootstrap_prompt must be persisted to Convex"
        assert (
            bp_calls[0][0][1]["bootstrap_prompt"]
            == "Write comprehensive tests for the authentication module."
        )
