from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from mc.contexts.interactive.coordinator import InteractiveSessionCoordinator
from mc.contexts.interactive.errors import (
    InteractiveSessionAttachError,
    InteractiveSessionStartupError,
)
from mc.contexts.interactive.identity import InteractiveSessionIdentity
from mc.contexts.interactive.types import InteractiveLaunchSpec
from mc.infrastructure.interactive import TerminalSize
from mc.types import AgentData


def _identity() -> InteractiveSessionIdentity:
    return InteractiveSessionIdentity(
        provider="claude-code",
        agent_name="claude-pair",
        scope_kind="chat",
        scope_id="chat-123",
        surface="chat",
    )


def _agent() -> AgentData:
    return AgentData(
        name="claude-pair",
        display_name="Claude Pair",
        role="Engineer",
        backend="claude-code",
    )


def _launch_spec() -> InteractiveLaunchSpec:
    return InteractiveLaunchSpec(
        cwd=Path("/tmp/workspace"),
        command=["claude", "--mcp-config", "/tmp/workspace/.mcp.json"],
        capabilities=["tui", "autocomplete"],
        environment={"FOO": "bar"},
    )


@pytest.mark.asyncio
async def test_create_or_attach_prepares_launch_and_registers_new_session() -> None:
    registry = MagicMock()
    registry.get.return_value = None
    registry.register.return_value = {"session_id": "interactive_session:claude"}
    tmux = MagicMock()
    tmux.ensure_session.return_value = True
    adapter = MagicMock()
    adapter.healthcheck = AsyncMock()
    adapter.prepare_launch = AsyncMock(return_value=_launch_spec())
    coordinator = InteractiveSessionCoordinator(
        registry=registry,
        tmux=tmux,
        adapters={"claude-code": adapter},
    )
    identity = _identity()

    result = await coordinator.create_or_attach(
        identity=identity,
        agent=_agent(),
        task_id="task-123",
        timestamp="2026-03-12T23:00:00.000Z",
    )

    adapter.prepare_launch.assert_awaited_once()
    adapter.healthcheck.assert_awaited_once_with(agent=_agent())
    tmux.ensure_session.assert_called_once_with(
        identity.tmux_session_name,
        cwd="/tmp/workspace",
        command=["claude", "--mcp-config", "/tmp/workspace/.mcp.json"],
        env={"FOO": "bar"},
    )
    registry.register.assert_called_once_with(
        identity,
        status="ready",
        capabilities=["tui", "autocomplete"],
        timestamp="2026-03-12T23:00:00.000Z",
        task_id="task-123",
        step_id=None,
        rotate_attach_token=True,
    )
    assert result == {"session_id": "interactive_session:claude"}


@pytest.mark.asyncio
async def test_create_or_attach_reuses_existing_live_session_without_relaunch() -> None:
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "tmux_session": "mc-int-123",
        "status": "ready",
    }
    tmux = MagicMock()
    tmux.has_session.return_value = True
    adapter = MagicMock()
    adapter.healthcheck = AsyncMock()
    coordinator = InteractiveSessionCoordinator(
        registry=registry,
        tmux=tmux,
        adapters={"claude-code": adapter},
    )

    result = await coordinator.create_or_attach(
        identity=_identity(),
        agent=_agent(),
        task_id="task-123",
        timestamp="2026-03-12T23:00:00.000Z",
    )

    assert result["session_id"] == "interactive_session:claude"
    adapter.prepare_launch.assert_not_called()
    tmux.ensure_session.assert_not_called()


@pytest.mark.asyncio
async def test_create_or_attach_reclaims_stale_detached_session_before_relaunch() -> None:
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "tmux_session": "mc-int-123",
        "provider": "claude-code",
        "status": "detached",
        "last_active_at": "2026-03-12T20:00:00+00:00",
    }
    registry.register.return_value = {"session_id": "interactive_session:claude"}
    tmux = MagicMock()
    tmux.has_session.return_value = True
    adapter = MagicMock()
    adapter.healthcheck = AsyncMock()
    adapter.prepare_launch = AsyncMock(return_value=_launch_spec())
    adapter.stop_session = AsyncMock()
    coordinator = InteractiveSessionCoordinator(
        registry=registry,
        tmux=tmux,
        adapters={"claude-code": adapter},
        idle_timeout_seconds=900,
    )

    result = await coordinator.create_or_attach(
        identity=_identity(),
        agent=_agent(),
        task_id="task-123",
        timestamp="2026-03-12T23:00:00+00:00",
    )

    adapter.stop_session.assert_awaited_once_with("interactive_session:claude")
    tmux.terminate_session.assert_called_once_with("mc-int-123")
    registry.end_session.assert_called_once_with(
        "interactive_session:claude",
        timestamp="2026-03-12T23:00:00+00:00",
        outcome="terminated",
    )
    adapter.prepare_launch.assert_awaited_once()
    assert result == {"session_id": "interactive_session:claude"}


@pytest.mark.asyncio
async def test_create_or_attach_recovers_from_orphaned_metadata_before_relaunch() -> None:
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "tmux_session": "mc-int-123",
        "provider": "claude-code",
        "status": "attached",
    }
    registry.register.return_value = {"session_id": "interactive_session:claude"}
    tmux = MagicMock()
    tmux.has_session.return_value = False
    adapter = MagicMock()
    adapter.healthcheck = AsyncMock()
    adapter.prepare_launch = AsyncMock(return_value=_launch_spec())
    adapter.stop_session = AsyncMock()
    coordinator = InteractiveSessionCoordinator(
        registry=registry,
        tmux=tmux,
        adapters={"claude-code": adapter},
    )

    await coordinator.create_or_attach(
        identity=_identity(),
        agent=_agent(),
        task_id="task-123",
        timestamp="2026-03-12T23:00:00+00:00",
    )

    adapter.stop_session.assert_awaited_once_with("interactive_session:claude")
    registry.end_session.assert_called_once_with(
        "interactive_session:claude",
        timestamp="2026-03-12T23:00:00+00:00",
        outcome="crashed",
    )


@pytest.mark.asyncio
async def test_create_or_attach_raises_explicit_startup_error_when_tmux_fails() -> None:
    registry = MagicMock()
    registry.get.return_value = None
    tmux = MagicMock()
    tmux.ensure_session.side_effect = RuntimeError("tmux new-session failed")
    adapter = MagicMock()
    adapter.healthcheck = AsyncMock()
    adapter.prepare_launch = AsyncMock(return_value=_launch_spec())
    adapter.stop_session = AsyncMock()
    coordinator = InteractiveSessionCoordinator(
        registry=registry,
        tmux=tmux,
        adapters={"claude-code": adapter},
    )

    with pytest.raises(InteractiveSessionStartupError, match="tmux new-session failed"):
        await coordinator.create_or_attach(
            identity=_identity(),
            agent=_agent(),
            task_id="task-123",
            timestamp="2026-03-12T23:00:00.000Z",
        )

    adapter.stop_session.assert_awaited_once()


def test_attach_raises_explicit_error_when_pty_attach_fails() -> None:
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "tmux_session": "mc-int-123",
        "attach_token": "attach-token-123",
        "status": "ready",
    }
    attach_factory = MagicMock(side_effect=RuntimeError("attach-session failed"))
    tmux = MagicMock()
    tmux.has_session.return_value = True
    coordinator = InteractiveSessionCoordinator(
        registry=registry,
        tmux=tmux,
        adapters={},
        attach_factory=attach_factory,
    )

    with pytest.raises(InteractiveSessionAttachError, match="attach-session failed"):
        coordinator.attach_session(
            "interactive_session:claude",
            size=TerminalSize(columns=120, rows=40),
            attach_token="attach-token-123",
            timestamp="2026-03-12T23:02:00+00:00",
        )


def test_attach_rejects_unknown_attach_token() -> None:
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "tmux_session": "mc-int-123",
        "attach_token": "attach-token-123",
        "status": "ready",
    }
    tmux = MagicMock()
    tmux.has_session.return_value = True
    coordinator = InteractiveSessionCoordinator(
        registry=registry,
        tmux=tmux,
        adapters={},
        attach_factory=MagicMock(),
    )

    with pytest.raises(InteractiveSessionAttachError, match="authorized"):
        coordinator.attach_session(
            "interactive_session:claude",
            size=TerminalSize(columns=120, rows=40),
            attach_token="wrong-token",
            timestamp="2026-03-12T23:02:00+00:00",
        )


def test_attach_marks_session_attached_and_returns_metadata() -> None:
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "tmux_session": "mc-int-123",
        "attach_token": "attach-token-123",
        "status": "detached",
    }
    registry.mark_attached.return_value = {
        "session_id": "interactive_session:claude",
        "tmux_session": "mc-int-123",
        "attach_token": "attach-token-123",
        "status": "attached",
    }
    attached_terminal = MagicMock()
    attach_factory = MagicMock(return_value=attached_terminal)
    tmux = MagicMock()
    tmux.has_session.return_value = True
    coordinator = InteractiveSessionCoordinator(
        registry=registry,
        tmux=tmux,
        adapters={},
        attach_factory=attach_factory,
    )

    result = coordinator.attach_session(
        "interactive_session:claude",
        size=TerminalSize(columns=120, rows=40),
        attach_token="attach-token-123",
        timestamp="2026-03-12T23:02:00+00:00",
    )

    registry.mark_attached.assert_called_once_with(
        "interactive_session:claude",
        timestamp="2026-03-12T23:02:00+00:00",
    )
    assert result.terminal is attached_terminal
    assert result.metadata["attach_token"] == "attach-token-123"


@pytest.mark.asyncio
async def test_terminate_session_stops_adapter_and_tmux() -> None:
    registry = MagicMock()
    registry.terminate.return_value = {"status": "ended"}
    tmux = MagicMock()
    adapter = MagicMock()
    adapter.stop_session = AsyncMock()
    coordinator = InteractiveSessionCoordinator(
        registry=registry,
        tmux=tmux,
        adapters={"claude-code": adapter},
    )
    identity = _identity()

    result = await coordinator.terminate_session(
        identity,
        timestamp="2026-03-12T23:05:00.000Z",
    )

    adapter.stop_session.assert_awaited_once_with(identity.session_key)
    tmux.terminate_session.assert_called_once_with(identity.tmux_session_name)
    registry.terminate.assert_called_once_with(
        identity,
        timestamp="2026-03-12T23:05:00.000Z",
    )
    assert result == {"status": "ended"}
