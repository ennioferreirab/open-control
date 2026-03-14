"""Tests for ProviderSessionRegistry."""

from __future__ import annotations

import pytest

from mc.contexts.provider_cli.registry import ProviderSessionRecord, ProviderSessionRegistry
from mc.contexts.provider_cli.types import SessionStatus


def _make_registry() -> ProviderSessionRegistry:
    return ProviderSessionRegistry()


def _create_session(registry: ProviderSessionRegistry, mc_session_id: str = "s1") -> ProviderSessionRecord:
    return registry.create(
        mc_session_id=mc_session_id,
        provider="test-provider",
        pid=12345,
        pgid=12345,
        mode="runtime-owned",
        supports_resume=True,
        supports_interrupt=True,
        supports_stop=True,
    )


class TestProviderSessionRegistryCRUD:
    def test_create_returns_record(self) -> None:
        registry = _make_registry()
        record = _create_session(registry)
        assert isinstance(record, ProviderSessionRecord)
        assert record.mc_session_id == "s1"
        assert record.provider == "test-provider"
        assert record.pid == 12345
        assert record.status == SessionStatus.STARTING

    def test_create_sets_initial_status_to_starting(self) -> None:
        registry = _make_registry()
        record = _create_session(registry)
        assert record.status == SessionStatus.STARTING

    def test_create_with_optional_fields(self) -> None:
        registry = _make_registry()
        record = registry.create(
            mc_session_id="s2",
            provider="codex",
            pid=99999,
            pgid=99999,
            mode="provider-native",
            supports_resume=False,
            supports_interrupt=False,
            supports_stop=True,
            provider_session_id="prov-abc",
            child_pids=[100, 200],
            extra={"note": "test"},
        )
        assert record.provider_session_id == "prov-abc"
        assert record.child_pids == [100, 200]
        assert record.extra == {"note": "test"}
        assert record.supports_resume is False
        assert record.supports_interrupt is False
        assert record.supports_stop is True

    def test_create_duplicate_raises(self) -> None:
        registry = _make_registry()
        _create_session(registry, "s1")
        with pytest.raises(ValueError, match="already registered"):
            _create_session(registry, "s1")

    def test_get_returns_record(self) -> None:
        registry = _make_registry()
        _create_session(registry, "s1")
        record = registry.get("s1")
        assert record is not None
        assert record.mc_session_id == "s1"

    def test_get_missing_returns_none(self) -> None:
        registry = _make_registry()
        assert registry.get("nonexistent") is None

    def test_require_returns_record(self) -> None:
        registry = _make_registry()
        _create_session(registry, "s1")
        record = registry.require("s1")
        assert record.mc_session_id == "s1"

    def test_require_missing_raises(self) -> None:
        registry = _make_registry()
        with pytest.raises(ValueError, match="not found"):
            registry.require("nonexistent")

    def test_list_sessions_empty(self) -> None:
        registry = _make_registry()
        assert registry.list_sessions() == []

    def test_list_sessions_returns_all(self) -> None:
        registry = _make_registry()
        _create_session(registry, "s1")
        _create_session(registry, "s2")
        sessions = registry.list_sessions()
        assert len(sessions) == 2
        ids = {s.mc_session_id for s in sessions}
        assert ids == {"s1", "s2"}

    def test_remove_deletes_record(self) -> None:
        registry = _make_registry()
        _create_session(registry, "s1")
        registry.remove("s1")
        assert registry.get("s1") is None

    def test_remove_nonexistent_is_noop(self) -> None:
        registry = _make_registry()
        registry.remove("nonexistent")  # should not raise


class TestProviderSessionRegistryUpdates:
    def test_update_status_valid_transition(self) -> None:
        registry = _make_registry()
        _create_session(registry, "s1")
        record = registry.update_status("s1", SessionStatus.RUNNING)
        assert record.status == SessionStatus.RUNNING

    def test_update_status_invalid_transition_raises(self) -> None:
        registry = _make_registry()
        _create_session(registry, "s1")
        # STARTING -> COMPLETED is not a valid transition
        with pytest.raises(ValueError, match="Invalid status transition"):
            registry.update_status("s1", SessionStatus.COMPLETED)

    def test_update_status_terminal_state_raises(self) -> None:
        registry = _make_registry()
        _create_session(registry, "s1")
        registry.update_status("s1", SessionStatus.RUNNING)
        registry.update_status("s1", SessionStatus.COMPLETED)
        # From COMPLETED, no transitions are valid
        with pytest.raises(ValueError, match="Invalid status transition"):
            registry.update_status("s1", SessionStatus.RUNNING)

    def test_update_status_chain_running_to_waiting(self) -> None:
        registry = _make_registry()
        _create_session(registry, "s1")
        registry.update_status("s1", SessionStatus.RUNNING)
        record = registry.update_status("s1", SessionStatus.WAITING_FOR_INPUT)
        assert record.status == SessionStatus.WAITING_FOR_INPUT

    def test_update_status_running_to_crashed(self) -> None:
        registry = _make_registry()
        _create_session(registry, "s1")
        registry.update_status("s1", SessionStatus.RUNNING)
        record = registry.update_status("s1", SessionStatus.CRASHED)
        assert record.status == SessionStatus.CRASHED

    def test_update_provider_session_id(self) -> None:
        registry = _make_registry()
        _create_session(registry, "s1")
        record = registry.update_provider_session_id("s1", "prov-xyz")
        assert record.provider_session_id == "prov-xyz"
        # Confirm persisted
        assert registry.get("s1").provider_session_id == "prov-xyz"

    def test_update_child_pids(self) -> None:
        registry = _make_registry()
        _create_session(registry, "s1")
        record = registry.update_child_pids("s1", [111, 222, 333])
        assert record.child_pids == [111, 222, 333]
        assert registry.get("s1").child_pids == [111, 222, 333]

    def test_update_child_pids_replace(self) -> None:
        registry = _make_registry()
        registry.create(
            mc_session_id="s1",
            provider="test",
            pid=1,
            pgid=1,
            mode="runtime-owned",
            supports_resume=True,
            supports_interrupt=True,
            supports_stop=True,
            child_pids=[10, 20],
        )
        registry.update_child_pids("s1", [30, 40])
        assert registry.get("s1").child_pids == [30, 40]

    def test_starting_to_running_is_valid(self) -> None:
        registry = _make_registry()
        _create_session(registry, "s1")
        record = registry.update_status("s1", SessionStatus.RUNNING)
        assert record.status == SessionStatus.RUNNING

    def test_starting_to_crashed_is_valid(self) -> None:
        registry = _make_registry()
        _create_session(registry, "s1")
        record = registry.update_status("s1", SessionStatus.CRASHED)
        assert record.status == SessionStatus.CRASHED

    def test_full_lifecycle_running_to_completed(self) -> None:
        registry = _make_registry()
        _create_session(registry, "s1")
        registry.update_status("s1", SessionStatus.RUNNING)
        record = registry.update_status("s1", SessionStatus.COMPLETED)
        assert record.status == SessionStatus.COMPLETED

    def test_registry_importable_from_package(self) -> None:
        from mc.contexts.provider_cli import ProviderSessionRegistry as PackageExport

        assert PackageExport is ProviderSessionRegistry
