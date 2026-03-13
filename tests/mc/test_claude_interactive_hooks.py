from __future__ import annotations

from unittest.mock import MagicMock

from mc.contexts.interactive.adapters.claude_hooks import ClaudeHookRelay
from mc.contexts.interactive.supervision_types import InteractiveSupervisionEvent


def test_claude_hook_relay_maps_stop_event_into_turn_completed() -> None:
    sink = MagicMock()
    sink.handle_event.return_value = {"session_id": "interactive_session:claude"}
    relay = ClaudeHookRelay(sink=sink)

    result = relay.handle(
        {
            "hook_event_name": "Stop",
            "stop_hook_active": True,
        },
        session_id="interactive_session:claude",
        task_id="task-1",
        step_id="step-1",
        agent_name="claude-pair",
    )

    sink.handle_event.assert_called_once()
    event = sink.handle_event.call_args.args[0]
    assert event == InteractiveSupervisionEvent(
        kind="turn_completed",
        session_id="interactive_session:claude",
        provider="claude-code",
        task_id="task-1",
        step_id="step-1",
        agent_name="claude-pair",
        metadata={"stop_hook_active": True},
    )
    assert result == {"session_id": "interactive_session:claude"}


def test_claude_hook_relay_maps_permission_request_into_approval_requested() -> None:
    sink = MagicMock()
    sink.handle_event.return_value = {"session_id": "interactive_session:claude"}
    relay = ClaudeHookRelay(sink=sink)

    relay.handle(
        {
            "hook_event_name": "PermissionRequest",
            "tool_name": "Bash",
            "input": {"command": "rm -rf tmp"},
        },
        session_id="interactive_session:claude",
        task_id="task-1",
        step_id="step-1",
        agent_name="claude-pair",
    )

    event = sink.handle_event.call_args.args[0]
    assert event.kind == "approval_requested"
    assert event.metadata == {"tool_name": "Bash", "input": {"command": "rm -rf tmp"}}
