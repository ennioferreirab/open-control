from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mc.contexts.interactive.coordinator import InteractiveSessionCoordinator
from mc.contexts.interactive.identity import InteractiveSessionIdentity
from mc.infrastructure.interactive import TerminalSize


def _identity() -> InteractiveSessionIdentity:
    return InteractiveSessionIdentity(
        provider="codex",
        agent_name="codex-pair",
        scope_kind="task",
        scope_id="task-123",
        surface="step",
    )


@pytest.mark.asyncio
async def test_attaching_existing_codex_session_does_not_relaunch_provider_runtime() -> None:
    identity = _identity()
    registry = MagicMock()
    registry.get.return_value = {
        "session_id": identity.session_key,
        "agent_name": "codex-pair",
        "provider": "codex",
        "scope_kind": "task",
        "scope_id": "task-123",
        "surface": "step",
        "tmux_session": identity.tmux_session_name,
        "status": "detached",
        "capabilities": ["tui"],
        "attach_token": "attach-token-123",
    }
    registry.mark_attached.return_value = {
        "session_id": identity.session_key,
        "status": "attached",
        "attach_token": "attach-token-123",
    }
    tmux = MagicMock()
    tmux.has_session.return_value = True
    attach_factory = MagicMock(return_value=MagicMock())
    codex_adapter = MagicMock()
    codex_adapter.prepare_launch = AsyncMock()

    coordinator = InteractiveSessionCoordinator(
        registry=registry,
        tmux=tmux,
        adapters={"codex": codex_adapter},
        attach_factory=attach_factory,
    )

    attached = coordinator.attach_session(
        identity.session_key,
        size=TerminalSize(columns=120, rows=40),
        attach_token="attach-token-123",
        timestamp="2026-03-13T10:00:00Z",
    )

    assert attached.metadata["status"] == "attached"
    codex_adapter.prepare_launch.assert_not_called()
    tmux.ensure_session.assert_not_called()
