from __future__ import annotations

from unittest.mock import MagicMock

from mc.contexts.interactive.supervision_types import InteractiveSupervisionEvent
from mc.contexts.interactive.supervisor import InteractiveExecutionSupervisor
from mc.types import ActivityEventType


def test_supervisor_marks_task_and_step_running_on_turn_started() -> None:
    bridge = MagicMock()
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "agent_name": "claude-pair",
        "task_id": "task-1",
        "step_id": "step-1",
    }
    supervisor = InteractiveExecutionSupervisor(bridge=bridge, registry=registry)

    supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="turn_started",
            provider="claude-code",
            session_id="interactive_session:claude",
        )
    )

    registry.record_supervision.assert_called_once()
    bridge.update_task_status.assert_called_once_with(
        "task-1",
        "in_progress",
        agent_name="claude-pair",
        description="Interactive turn started for step step-1",
    )
    bridge.update_step_status.assert_called_once_with("step-1", "running")
    bridge.create_activity.assert_called_once_with(
        ActivityEventType.STEP_STARTED,
        "Interactive step started for @claude-pair.",
        task_id="task-1",
        agent_name="claude-pair",
    )


def test_supervisor_marks_task_review_and_step_review_when_paused() -> None:
    bridge = MagicMock()
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "agent_name": "claude-pair",
        "task_id": "task-1",
        "step_id": "step-1",
    }
    supervisor = InteractiveExecutionSupervisor(bridge=bridge, registry=registry)

    supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="paused_for_review",
            provider="claude-code",
            session_id="interactive_session:claude",
            summary="Need user confirmation before continuing.",
        )
    )

    bridge.update_task_status.assert_called_once_with(
        "task-1",
        "review",
        agent_name="claude-pair",
        description="Need user confirmation before continuing.",
    )
    bridge.update_step_status.assert_called_once_with("step-1", "review")
    bridge.create_activity.assert_called_once_with(
        ActivityEventType.REVIEW_REQUESTED,
        "Interactive session paused for review for @claude-pair.",
        task_id="task-1",
        agent_name="claude-pair",
    )


def test_supervisor_marks_task_and_step_crashed_on_session_failure() -> None:
    bridge = MagicMock()
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "agent_name": "claude-pair",
        "task_id": "task-1",
        "step_id": "step-1",
    }
    supervisor = InteractiveExecutionSupervisor(bridge=bridge, registry=registry)

    supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="session_failed",
            provider="claude-code",
            session_id="interactive_session:claude",
            error="Provider process exited unexpectedly",
        )
    )

    bridge.update_task_status.assert_called_once_with(
        "task-1",
        "crashed",
        agent_name="claude-pair",
        description="Provider process exited unexpectedly",
    )
    bridge.update_step_status.assert_called_once_with(
        "step-1",
        "crashed",
        "Provider process exited unexpectedly",
    )
    bridge.create_activity.assert_called_once_with(
        ActivityEventType.AGENT_CRASHED,
        "Interactive session failed for @claude-pair.",
        task_id="task-1",
        agent_name="claude-pair",
    )


def test_supervisor_emits_activity_when_supervision_becomes_ready() -> None:
    bridge = MagicMock()
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "agent_name": "claude-pair",
        "task_id": "task-1",
        "step_id": "step-1",
    }
    supervisor = InteractiveExecutionSupervisor(bridge=bridge, registry=registry)

    supervisor.handle_event(
        InteractiveSupervisionEvent(
            kind="session_ready",
            provider="claude-code",
            session_id="interactive_session:claude",
        )
    )

    bridge.create_activity.assert_called_once_with(
        ActivityEventType.AGENT_CONNECTED,
        "Interactive supervision ready for @claude-pair.",
        task_id="task-1",
        agent_name="claude-pair",
    )
