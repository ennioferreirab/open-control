from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mc.contexts.interactive.identity import InteractiveSessionIdentity
from mc.contexts.interactive.service import InteractiveSessionService
from mc.infrastructure.interactive import AttachedTerminal, TerminalSize


def _identity() -> InteractiveSessionIdentity:
    return InteractiveSessionIdentity(
        provider="claude-code",
        agent_name="claude-pair",
        scope_kind="chat",
        scope_id="chat/claude-pair",
        surface="chat",
    )


def test_create_session_ensures_tmux_and_registers_attachable_metadata() -> None:
    registry = MagicMock()
    tmux = MagicMock()
    tmux.ensure_session.return_value = True
    attach_factory = MagicMock()
    service = InteractiveSessionService(registry=registry, tmux=tmux, attach_factory=attach_factory)
    identity = _identity()

    metadata = service.create_session(
        identity,
        cwd="/tmp/workspace",
        command=["claude"],
        capabilities=["tui", "autocomplete"],
        timestamp="2026-03-12T22:30:00.000Z",
    )

    tmux.ensure_session.assert_called_once_with(
        identity.tmux_session_name,
        cwd="/tmp/workspace",
        command=["claude"],
    )
    registry.register.assert_called_once_with(
        identity,
        status="ready",
        capabilities=["tui", "autocomplete"],
        timestamp="2026-03-12T22:30:00.000Z",
        rotate_attach_token=True,
    )
    assert metadata == registry.register.return_value


def test_attach_session_reattaches_using_tmux_session_from_metadata() -> None:
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "tmux_session": "mc-int-123",
        "attach_token": "attach-token-123",
        "status": "ready",
    }
    registry.mark_attached.return_value = {
        "session_id": "interactive_session:claude",
        "tmux_session": "mc-int-123",
        "attach_token": "attach-token-123",
        "status": "attached",
    }
    tmux = MagicMock()
    tmux.has_session.return_value = True
    attached = AttachedTerminal(master_fd=10, process=MagicMock())
    attach_factory = MagicMock(return_value=attached)
    service = InteractiveSessionService(registry=registry, tmux=tmux, attach_factory=attach_factory)

    result = service.attach_session(
        "interactive_session:claude",
        size=TerminalSize(columns=120, rows=40),
        attach_token="attach-token-123",
        timestamp="2026-03-12T22:32:00.000Z",
    )

    registry.get.assert_called_once_with("interactive_session:claude")
    attach_factory.assert_called_once_with(
        "mc-int-123",
        size=TerminalSize(columns=120, rows=40),
    )
    registry.mark_attached.assert_called_once_with(
        "interactive_session:claude",
        timestamp="2026-03-12T22:32:00.000Z",
    )
    assert result.terminal is attached
    assert result.metadata["status"] == "attached"


def test_attach_session_requires_existing_metadata() -> None:
    registry = MagicMock()
    registry.get.return_value = None
    service = InteractiveSessionService(
        registry=registry,
        tmux=MagicMock(),
        attach_factory=MagicMock(),
    )

    with pytest.raises(ValueError, match="interactive_session:claude"):
        service.attach_session(
            "interactive_session:claude",
            size=TerminalSize(columns=120, rows=40),
            attach_token="attach-token-123",
            timestamp="2026-03-12T22:32:00.000Z",
        )


def test_attach_session_rejects_unknown_attach_token() -> None:
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": "interactive_session:claude",
        "tmux_session": "mc-int-123",
        "attach_token": "attach-token-123",
        "status": "ready",
    }
    tmux = MagicMock()
    tmux.has_session.return_value = True
    service = InteractiveSessionService(
        registry=registry,
        tmux=tmux,
        attach_factory=MagicMock(),
    )

    with pytest.raises(ValueError, match="authorized"):
        service.attach_session(
            "interactive_session:claude",
            size=TerminalSize(columns=120, rows=40),
            attach_token="wrong-token",
            timestamp="2026-03-12T22:32:00.000Z",
        )


def test_list_sessions_delegates_to_registry() -> None:
    registry = MagicMock()
    registry.list_sessions.return_value = [{"session_id": "interactive_session:claude"}]
    service = InteractiveSessionService(
        registry=registry,
        tmux=MagicMock(),
        attach_factory=MagicMock(),
    )

    result = service.list_sessions(agent_name="claude-pair")

    assert result == [{"session_id": "interactive_session:claude"}]
    registry.list_sessions.assert_called_once_with(agent_name="claude-pair")


def test_terminate_session_marks_registry_and_kills_tmux() -> None:
    registry = MagicMock()
    tmux = MagicMock()
    service = InteractiveSessionService(
        registry=registry,
        tmux=tmux,
        attach_factory=MagicMock(),
    )
    identity = _identity()

    metadata = service.terminate_session(
        identity,
        timestamp="2026-03-12T22:35:00.000Z",
    )

    registry.terminate.assert_called_once_with(
        identity,
        timestamp="2026-03-12T22:35:00.000Z",
    )
    tmux.terminate_session.assert_called_once_with(identity.tmux_session_name)
    assert metadata == registry.terminate.return_value
