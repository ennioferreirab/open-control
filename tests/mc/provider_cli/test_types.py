"""Tests for provider CLI shared types."""

from __future__ import annotations

import pytest

from mc.contexts.provider_cli.types import (
    ParsedCliEvent,
    ProviderProcessHandle,
    ProviderSessionSnapshot,
    SessionStatus,
)


class TestProviderProcessHandle:
    def test_construction_with_required_fields(self) -> None:
        handle = ProviderProcessHandle(
            mc_session_id="session-1",
            provider="claude-code",
            pid=12345,
            pgid=12345,
            cwd="/tmp/test",
            command=["claude", "--model", "claude-3"],
            started_at="2024-01-01T00:00:00Z",
        )
        assert handle.mc_session_id == "session-1"
        assert handle.provider == "claude-code"
        assert handle.pid == 12345
        assert handle.pgid == 12345
        assert handle.cwd == "/tmp/test"
        assert handle.command == ["claude", "--model", "claude-3"]
        assert handle.started_at == "2024-01-01T00:00:00Z"

    def test_pgid_can_be_none(self) -> None:
        handle = ProviderProcessHandle(
            mc_session_id="session-2",
            provider="codex",
            pid=99999,
            pgid=None,
            cwd="/home/user",
            command=["codex"],
            started_at="2024-01-01T00:00:00Z",
        )
        assert handle.pgid is None

    def test_is_dataclass(self) -> None:
        import dataclasses

        assert dataclasses.is_dataclass(ProviderProcessHandle)


class TestProviderSessionSnapshot:
    def test_construction_with_all_fields(self) -> None:
        snapshot = ProviderSessionSnapshot(
            mc_session_id="session-1",
            provider_session_id="prov-sess-abc",
            mode="provider-native",
            supports_resume=True,
            supports_interrupt=True,
            supports_stop=True,
        )
        assert snapshot.mc_session_id == "session-1"
        assert snapshot.provider_session_id == "prov-sess-abc"
        assert snapshot.mode == "provider-native"
        assert snapshot.supports_resume is True
        assert snapshot.supports_interrupt is True
        assert snapshot.supports_stop is True

    def test_provider_session_id_can_be_none(self) -> None:
        snapshot = ProviderSessionSnapshot(
            mc_session_id="session-2",
            provider_session_id=None,
            mode="runtime-owned",
            supports_resume=False,
            supports_interrupt=True,
            supports_stop=True,
        )
        assert snapshot.provider_session_id is None

    def test_mode_literal_values(self) -> None:
        # Both valid literal values should be constructable
        snap1 = ProviderSessionSnapshot(
            mc_session_id="s1",
            provider_session_id=None,
            mode="provider-native",
            supports_resume=False,
            supports_interrupt=False,
            supports_stop=False,
        )
        snap2 = ProviderSessionSnapshot(
            mc_session_id="s2",
            provider_session_id=None,
            mode="runtime-owned",
            supports_resume=False,
            supports_interrupt=False,
            supports_stop=False,
        )
        assert snap1.mode == "provider-native"
        assert snap2.mode == "runtime-owned"

    def test_is_dataclass(self) -> None:
        import dataclasses

        assert dataclasses.is_dataclass(ProviderSessionSnapshot)


class TestParsedCliEvent:
    def test_construction_with_kind_only(self) -> None:
        event = ParsedCliEvent(kind="output")
        assert event.kind == "output"
        assert event.text is None
        assert event.provider_session_id is None
        assert event.pid is None
        assert event.metadata is None

    def test_construction_with_all_fields(self) -> None:
        event = ParsedCliEvent(
            kind="session_discovered",
            text="Session started",
            provider_session_id="prov-abc",
            pid=12345,
            metadata={"extra": "data"},
        )
        assert event.kind == "session_discovered"
        assert event.text == "Session started"
        assert event.provider_session_id == "prov-abc"
        assert event.pid == 12345
        assert event.metadata == {"extra": "data"}

    def test_valid_kinds(self) -> None:
        valid_kinds = [
            "output",
            "session_discovered",
            "turn_started",
            "turn_completed",
            "subagent_spawned",
            "approval_requested",
            "error",
        ]
        for kind in valid_kinds:
            event = ParsedCliEvent(kind=kind)
            assert event.kind == kind

    def test_is_dataclass(self) -> None:
        import dataclasses

        assert dataclasses.is_dataclass(ParsedCliEvent)


class TestSessionStatus:
    def test_all_states_defined(self) -> None:
        expected_states = [
            "starting",
            "running",
            "waiting_for_input",
            "interrupting",
            "human_intervening",
            "resuming",
            "completed",
            "stopped",
            "crashed",
        ]
        for state in expected_states:
            # Should be accessible as an enum value
            assert SessionStatus(state).value == state

    def test_is_enum(self) -> None:
        import enum

        assert issubclass(SessionStatus, enum.Enum)

    def test_starting_value(self) -> None:
        assert SessionStatus.STARTING.value == "starting"

    def test_running_value(self) -> None:
        assert SessionStatus.RUNNING.value == "running"

    def test_completed_value(self) -> None:
        assert SessionStatus.COMPLETED.value == "completed"

    def test_crashed_value(self) -> None:
        assert SessionStatus.CRASHED.value == "crashed"
