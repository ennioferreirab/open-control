from __future__ import annotations

from mc.contexts.interactive.identity import (
    InteractiveSessionIdentity,
    build_interactive_session_key,
    build_tmux_session_name,
)


def test_interactive_session_key_uses_its_own_namespace() -> None:
    session_key = build_interactive_session_key(
        provider="claude-code",
        agent_name="claude-pair",
        scope_kind="chat",
        scope_id="chat/claude-pair",
        surface="chat",
    )

    assert session_key.startswith("interactive_session:")
    assert not session_key.startswith("cc_session:")
    assert "claude-code" in session_key
    assert "claude-pair" in session_key


def test_tmux_session_name_is_deterministic_and_filesystem_safe() -> None:
    session_key = build_interactive_session_key(
        provider="claude-code",
        agent_name="claude-pair",
        scope_kind="chat",
        scope_id="chat/claude-pair",
        surface="chat",
    )

    session_name = build_tmux_session_name(session_key)

    assert session_name.startswith("mc-int-")
    assert session_name == build_tmux_session_name(session_key)
    assert "/" not in session_name
    assert ":" not in session_name
    assert len(session_name) <= 24


def test_identity_builds_metadata_payload_without_terminal_buffer_fields() -> None:
    identity = InteractiveSessionIdentity(
        provider="claude-code",
        agent_name="claude-pair",
        scope_kind="chat",
        scope_id="chat/claude-pair",
        surface="chat",
    )

    metadata = identity.to_metadata(
        status="ready",
        capabilities=["tui", "autocomplete"],
        timestamp="2026-03-12T22:15:00.000Z",
    )

    assert metadata["session_id"] == identity.session_key
    assert metadata["tmux_session"] == identity.tmux_session_name
    assert metadata["provider"] == "claude-code"
    assert metadata["surface"] == "chat"
    assert metadata["status"] == "ready"
    assert metadata["capabilities"] == ["tui", "autocomplete"]
    assert "output" not in metadata
    assert "pendingInput" not in metadata
