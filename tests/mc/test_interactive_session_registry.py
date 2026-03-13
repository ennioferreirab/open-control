from __future__ import annotations

from unittest.mock import MagicMock

from mc.contexts.interactive.identity import InteractiveSessionIdentity
from mc.contexts.interactive.registry import InteractiveSessionRegistry
from mc.types import ActivityEventType


def _identity() -> InteractiveSessionIdentity:
    return InteractiveSessionIdentity(
        provider="claude-code",
        agent_name="claude-pair",
        scope_kind="chat",
        scope_id="chat/claude-pair",
        surface="chat",
    )


def test_register_upserts_dedicated_interactive_session_metadata() -> None:
    bridge = MagicMock()
    bridge.query.return_value = None
    registry = InteractiveSessionRegistry(bridge, token_factory=lambda: "attach-token-123")
    identity = _identity()

    metadata = registry.register(
        identity,
        status="ready",
        capabilities=["tui", "autocomplete"],
        timestamp="2026-03-12T22:15:00.000Z",
        task_id="task-123",
        step_id="step-456",
    )

    bridge.mutation.assert_called_once_with("interactiveSessions:upsert", metadata)
    assert metadata["session_id"] == identity.session_key
    assert metadata["tmux_session"] == identity.tmux_session_name
    assert metadata["scope_kind"] == "chat"
    assert metadata["scope_id"] == "chat/claude-pair"
    assert metadata["task_id"] == "task-123"
    assert metadata["step_id"] == "step-456"
    assert metadata["attach_token"] == "attach-token-123"
    assert "output" not in metadata
    assert "pending_input" not in metadata
    bridge.create_activity.assert_called_once_with(
        ActivityEventType.AGENT_CONNECTED,
        "Interactive TUI session created for @claude-pair on chat.",
        agent_name="claude-pair",
    )


def test_record_supervision_updates_runtime_owned_session_state() -> None:
    bridge = MagicMock()
    bridge.query.side_effect = [
        {
            "session_id": "interactive_session:claude",
            "agent_name": "claude-pair",
            "provider": "claude-code",
            "scope_kind": "chat",
            "scope_id": "chat/claude-pair",
            "surface": "chat",
            "tmux_session": "mc-int-123",
            "status": "attached",
            "capabilities": ["tui", "autocomplete"],
            "attach_token": "attach-token-123",
            "task_id": "task-123",
            "step_id": "step-456",
        }
    ]
    registry = InteractiveSessionRegistry(bridge)

    metadata = registry.record_supervision(
        "interactive_session:claude",
        event={
            "kind": "turn_started",
            "task_id": "task-123",
            "step_id": "step-456",
            "turn_id": "turn-1",
            "summary": "Claude started the turn.",
        },
        timestamp="2026-03-12T22:21:00.000Z",
    )

    assert metadata["task_id"] == "task-123"
    assert metadata["step_id"] == "step-456"
    assert metadata["active_turn_id"] == "turn-1"
    assert metadata["last_event_kind"] == "turn_started"
    assert metadata["last_event_at"] == "2026-03-12T22:21:00.000Z"
    assert metadata["supervision_state"] == "running"
    assert metadata["summary"] == "Claude started the turn."
    bridge.mutation.assert_called_once_with("interactiveSessions:upsert", metadata)


def test_record_final_result_persists_canonical_step_output() -> None:
    bridge = MagicMock()
    bridge.query.return_value = {
        "session_id": "interactive_session:claude",
        "agent_name": "claude-pair",
        "provider": "claude-code",
        "scope_kind": "chat",
        "scope_id": "chat/claude-pair",
        "surface": "chat",
        "tmux_session": "mc-int-123",
        "status": "attached",
        "capabilities": ["tui", "autocomplete"],
        "attach_token": "attach-token-123",
        "task_id": "task-123",
        "step_id": "step-456",
    }
    registry = InteractiveSessionRegistry(bridge)

    metadata = registry.record_final_result(
        "interactive_session:claude",
        content="Implemented the requested step and updated the failing tests.",
        source="claude-mcp",
        timestamp="2026-03-13T01:10:00.000Z",
    )

    assert (
        metadata["final_result"] == "Implemented the requested step and updated the failing tests."
    )
    assert metadata["final_result_source"] == "claude-mcp"
    assert metadata["final_result_at"] == "2026-03-13T01:10:00.000Z"
    bridge.mutation.assert_called_once_with("interactiveSessions:upsert", metadata)


def test_get_queries_interactive_session_metadata_by_session_id() -> None:
    bridge = MagicMock()
    bridge.query.return_value = {"session_id": "interactive_session:claude"}
    registry = InteractiveSessionRegistry(bridge)

    result = registry.get("interactive_session:claude")

    assert result == {"session_id": "interactive_session:claude"}
    bridge.query.assert_called_once_with(
        "interactiveSessions:getForRuntime",
        {"session_id": "interactive_session:claude"},
    )


def test_list_sessions_filters_by_agent_name_without_using_terminal_sessions() -> None:
    bridge = MagicMock()
    bridge.query.return_value = [{"session_id": "interactive_session:claude"}]
    registry = InteractiveSessionRegistry(bridge)

    result = registry.list_sessions(agent_name="claude-pair")

    assert result == [{"session_id": "interactive_session:claude"}]
    bridge.query.assert_called_once_with(
        "interactiveSessions:listForRuntime",
        {"agent_name": "claude-pair"},
    )


def test_mark_attached_reuses_existing_attach_token_and_emits_reattach_activity() -> None:
    bridge = MagicMock()
    bridge.query.return_value = {
        "session_id": "interactive_session:claude",
        "agent_name": "claude-pair",
        "provider": "claude-code",
        "scope_kind": "chat",
        "scope_id": "chat/claude-pair",
        "surface": "chat",
        "tmux_session": "mc-int-123",
        "status": "detached",
        "capabilities": ["tui", "autocomplete"],
        "attach_token": "attach-token-123",
    }
    registry = InteractiveSessionRegistry(bridge)

    metadata = registry.mark_attached(
        "interactive_session:claude",
        timestamp="2026-03-12T22:18:00.000Z",
    )

    assert metadata["status"] == "attached"
    assert metadata["attach_token"] == "attach-token-123"
    assert metadata["last_active_at"] == "2026-03-12T22:18:00.000Z"
    bridge.create_activity.assert_called_once_with(
        ActivityEventType.AGENT_CONNECTED,
        "Interactive TUI session reattached for @claude-pair on chat.",
        agent_name="claude-pair",
    )


def test_mark_detached_updates_last_active_timestamp_and_activity() -> None:
    bridge = MagicMock()
    bridge.query.return_value = {
        "session_id": "interactive_session:claude",
        "agent_name": "claude-pair",
        "provider": "claude-code",
        "scope_kind": "chat",
        "scope_id": "chat/claude-pair",
        "surface": "chat",
        "tmux_session": "mc-int-123",
        "status": "attached",
        "capabilities": ["tui", "autocomplete"],
        "attach_token": "attach-token-123",
    }
    registry = InteractiveSessionRegistry(bridge)

    metadata = registry.mark_detached(
        "interactive_session:claude",
        timestamp="2026-03-12T22:19:00.000Z",
    )

    assert metadata["status"] == "detached"
    assert metadata["last_active_at"] == "2026-03-12T22:19:00.000Z"
    bridge.create_activity.assert_called_once_with(
        ActivityEventType.AGENT_DISCONNECTED,
        "Interactive TUI session detached for @claude-pair on chat.",
        agent_name="claude-pair",
    )


def test_terminate_marks_session_ended_without_touching_headless_settings() -> None:
    bridge = MagicMock()
    bridge.query.return_value = None
    registry = InteractiveSessionRegistry(bridge, token_factory=lambda: "attach-token-123")
    identity = _identity()

    metadata = registry.terminate(identity, timestamp="2026-03-12T22:20:00.000Z")

    bridge.mutation.assert_called_once_with("interactiveSessions:upsert", metadata)
    assert metadata["status"] == "ended"
    assert metadata["ended_at"] == "2026-03-12T22:20:00.000Z"
    assert metadata["last_active_at"] == "2026-03-12T22:20:00.000Z"
    assert metadata["updated_at"] == "2026-03-12T22:20:00.000Z"
    bridge.create_activity.assert_called_once_with(
        ActivityEventType.AGENT_DISCONNECTED,
        "Interactive TUI session terminated for @claude-pair on chat.",
        agent_name="claude-pair",
    )
