"""Tests for InteractiveSessionRegistry in-memory cache."""

from __future__ import annotations

from unittest.mock import MagicMock

from mc.contexts.interactive.registry import InteractiveSessionRegistry


def _make_registry() -> tuple[InteractiveSessionRegistry, MagicMock]:
    """Create a registry with a mock bridge."""
    bridge = MagicMock()
    bridge.create_activity = MagicMock()
    registry = InteractiveSessionRegistry(bridge)
    return registry, bridge


class TestSessionCache:
    """Verify that the registry caches session data to avoid redundant queries."""

    def test_get_caches_after_first_fetch(self) -> None:
        """Second get() for the same session_id returns cached data, no Convex query."""
        registry, bridge = _make_registry()
        bridge.query.return_value = {"session_id": "s1", "status": "attached", "agent_name": "a"}

        first = registry.get("s1")
        second = registry.get("s1")

        assert first == second
        assert bridge.query.call_count == 1

    def test_get_returns_none_without_caching(self) -> None:
        """get() for a non-existent session returns None and does not cache None."""
        registry, bridge = _make_registry()
        bridge.query.return_value = None

        result = registry.get("missing")

        assert result is None
        # Second call should query again since None is not cached
        registry.get("missing")
        assert bridge.query.call_count == 2

    def test_upsert_updates_cache(self) -> None:
        """After _upsert, cached data reflects the new metadata."""
        registry, bridge = _make_registry()
        bridge.query.return_value = {
            "session_id": "s1",
            "status": "attached",
            "agent_name": "a",
            "provider": "p",
            "scope_kind": "task",
            "surface": "tmux",
            "tmux_session": "s1",
            "capabilities": [],
        }

        # Prime the cache
        registry.get("s1")

        # record_supervision calls _require_session -> get() (cached), then _upsert
        registry.record_supervision(
            "s1",
            event={"kind": "turn_started"},
            timestamp="2026-03-26T00:00:00Z",
        )

        # get() should return updated data from cache, not query Convex again
        result = registry.get("s1")
        assert result is not None
        assert result["supervision_state"] == "running"
        # Only 1 query total (the initial get)
        assert bridge.query.call_count == 1

    def test_end_session_removes_from_cache(self) -> None:
        """After end_session, cached entry is removed; next get() queries Convex."""
        registry, bridge = _make_registry()
        bridge.query.return_value = {
            "session_id": "s1",
            "status": "attached",
            "agent_name": "a",
            "provider": "p",
            "scope_kind": "task",
            "surface": "tmux",
            "tmux_session": "s1",
            "capabilities": [],
        }

        # Prime cache
        registry.get("s1")
        assert bridge.query.call_count == 1

        # End session
        registry.end_session("s1", timestamp="2026-03-26T00:00:00Z", outcome="completed")

        # Next get() should query Convex since cache was cleared
        registry.get("s1")
        assert bridge.query.call_count == 2

    def test_record_supervision_uses_cache(self) -> None:
        """record_supervision calls _require_session which uses cached data."""
        registry, bridge = _make_registry()
        bridge.query.return_value = {
            "session_id": "s1",
            "status": "attached",
            "agent_name": "a",
            "provider": "p",
            "scope_kind": "task",
            "surface": "tmux",
            "tmux_session": "s1",
            "capabilities": [],
        }

        # First supervision event triggers a Convex query
        registry.record_supervision("s1", event={"kind": "turn_started"}, timestamp="t1")
        # Second supervision event uses cache
        registry.record_supervision("s1", event={"kind": "item_started"}, timestamp="t2")
        # Third supervision event uses cache
        registry.record_supervision("s1", event={"kind": "item_completed"}, timestamp="t3")

        # Only 1 Convex query despite 3 supervision events
        assert bridge.query.call_count == 1
