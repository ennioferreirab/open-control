"""
Tests for mc.vault.subscriptions.SubscriptionManager.

Story 2.2, Task 5.7: Test SubscriptionManager — mock ConvexClient.subscribe,
verify ConvexChangedEvent is pushed to the queue.
"""
from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mc.vault.subscriptions import (
    SubscriptionManager,
    _compute_changes,
    _subscription_thread,
)
from mc.vault.sync_service import ConvexChangedEvent


# ---------------------------------------------------------------------------
# _compute_changes unit tests
# ---------------------------------------------------------------------------


class TestComputeChanges:
    """Unit tests for the diff computation helper."""

    def test_new_document_is_created(self) -> None:
        """A doc in current but not in prev is marked created."""
        prev: dict = {}
        current = [{"_id": "doc-001", "name": "alpha"}]

        changes, new_snap = _compute_changes(prev, current)

        assert len(changes) == 1
        doc_id, change_type, doc = changes[0]
        assert doc_id == "doc-001"
        assert change_type == "created"
        assert doc["name"] == "alpha"

    def test_changed_document_is_updated(self) -> None:
        """A doc in both prev and current with different data is marked updated."""
        prev = {"doc-002": {"_id": "doc-002", "status": "idle"}}
        current = [{"_id": "doc-002", "status": "active"}]

        changes, _ = _compute_changes(prev, current)

        assert len(changes) == 1
        _, change_type, doc = changes[0]
        assert change_type == "updated"
        assert doc["status"] == "active"

    def test_unchanged_document_not_emitted(self) -> None:
        """A doc in both prev and current with identical data emits no change."""
        doc = {"_id": "doc-003", "status": "idle"}
        prev = {"doc-003": doc}
        current = [dict(doc)]

        changes, _ = _compute_changes(prev, current)

        assert len(changes) == 0

    def test_removed_document_is_deleted(self) -> None:
        """A doc in prev but not in current is marked deleted."""
        prev = {"doc-004": {"_id": "doc-004", "name": "gone"}}
        current: list = []

        changes, _ = _compute_changes(prev, current)

        assert len(changes) == 1
        doc_id, change_type, doc = changes[0]
        assert doc_id == "doc-004"
        assert change_type == "deleted"

    def test_returns_updated_snapshot(self) -> None:
        """New snapshot dict replaces prev correctly."""
        prev: dict = {}
        current = [{"_id": "snap-001", "v": 1}]

        _, new_snap = _compute_changes(prev, current)

        assert "snap-001" in new_snap
        assert new_snap["snap-001"]["v"] == 1

    def test_handles_id_field_alias(self) -> None:
        """Docs using 'id' (not '_id') are also handled."""
        prev: dict = {}
        current = [{"id": "doc-alias", "name": "alias-doc"}]

        changes, new_snap = _compute_changes(prev, current)

        assert len(changes) == 1
        doc_id, change_type, _ = changes[0]
        assert doc_id == "doc-alias"
        assert change_type == "created"
        assert "doc-alias" in new_snap

    def test_multiple_changes_at_once(self) -> None:
        """Multiple creates, updates, and deletes in one diff."""
        prev = {
            "keep": {"_id": "keep", "v": 1},
            "update": {"_id": "update", "v": 1},
            "delete": {"_id": "delete", "v": 1},
        }
        current = [
            {"_id": "keep", "v": 1},   # unchanged
            {"_id": "update", "v": 2}, # updated
            {"_id": "new", "v": 1},    # created
            # "delete" is absent -> deleted
        ]

        changes, _ = _compute_changes(prev, current)

        change_types = {c[0]: c[1] for c in changes}
        assert change_types.get("update") == "updated"
        assert change_types.get("new") == "created"
        assert change_types.get("delete") == "deleted"
        assert "keep" not in change_types


# ---------------------------------------------------------------------------
# SubscriptionManager integration tests
# ---------------------------------------------------------------------------


class TestSubscriptionManager:
    """Task 5.7: SubscriptionManager pushes ConvexChangedEvents to queue."""

    def test_start_creates_threads(self) -> None:
        """start() launches one daemon thread per configured table."""
        mock_bridge = MagicMock()
        # subscribe() returns an infinite iterator -- use a stop_event to end
        stop_holder: list[threading.Event] = []

        def fake_subscribe(query_name, args=None):
            """Yields nothing immediately, then blocks until stop event."""
            stop = threading.Event()
            stop_holder.append(stop)
            stop.wait(timeout=5.0)
            return
            yield  # make it a generator

        mock_bridge.subscribe.side_effect = fake_subscribe

        loop = asyncio.new_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        manager = SubscriptionManager(mock_bridge)
        manager.start(loop, queue)

        try:
            assert len(manager._threads) > 0
            for thread in manager._threads:
                assert thread.is_alive()
                assert thread.daemon is True
        finally:
            manager.stop()
            loop.close()

    def test_stop_signals_threads(self) -> None:
        """stop() signals all threads and waits for them to exit."""
        mock_bridge = MagicMock()

        def fake_subscribe(query_name, args=None):
            # Empty generator -- thread will exit immediately
            return
            yield

        mock_bridge.subscribe.side_effect = fake_subscribe

        loop = asyncio.new_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        manager = SubscriptionManager(mock_bridge)
        manager.start(loop, queue)
        manager.stop()

        # After stop, no threads should remain
        assert len(manager._threads) == 0

    def test_subscription_thread_pushes_created_event(self) -> None:
        """_subscription_thread pushes ConvexChangedEvent for new docs."""
        mock_bridge = MagicMock()

        # subscribe() yields one result (new doc), then stop event is set
        def fake_subscribe(query_name, args=None):
            yield [{"_id": "doc-new", "name": "test", "status": "active"}]

        mock_bridge.subscribe.side_effect = fake_subscribe

        loop = asyncio.new_event_loop()
        # Use a plain list as a thread-safe collector instead of asyncio.Queue
        # because loop.call_soon_threadsafe requires the loop to be running.
        # We directly patch put_nowait to capture events.
        collected: list = []
        queue: asyncio.Queue = asyncio.Queue()
        queue.put_nowait = collected.append  # type: ignore[method-assign]
        stop_event = threading.Event()

        thread = threading.Thread(
            target=_subscription_thread,
            args=(mock_bridge, "tasks:list", "tasks", loop, queue, stop_event),
            daemon=True,
        )
        thread.start()
        thread.join(timeout=3.0)
        # Drain loop callbacks
        loop.run_until_complete(asyncio.sleep(0))

        assert len(collected) > 0, "Expected ConvexChangedEvent in collected"
        event = collected[0]
        assert isinstance(event, ConvexChangedEvent)
        assert event.table == "tasks"
        assert event.document_id == "doc-new"
        assert event.change_type == "created"
        loop.close()

    def test_subscription_thread_pushes_updated_event(self) -> None:
        """_subscription_thread detects updates across multiple snapshots."""
        mock_bridge = MagicMock()

        # First result: initial snapshot
        # Second result: doc-001 updated
        call_count = [0]

        def fake_subscribe(query_name, args=None):
            call_count[0] += 1
            yield [{"_id": "doc-001", "status": "idle"}]
            yield [{"_id": "doc-001", "status": "active"}]

        mock_bridge.subscribe.side_effect = fake_subscribe

        loop = asyncio.new_event_loop()
        # Capture events directly instead of using asyncio.Queue with loop
        collected: list = []
        queue: asyncio.Queue = asyncio.Queue()
        queue.put_nowait = collected.append  # type: ignore[method-assign]
        stop_event = threading.Event()

        thread = threading.Thread(
            target=_subscription_thread,
            args=(mock_bridge, "agents:list", "agents", loop, queue, stop_event),
            daemon=True,
        )
        thread.start()
        thread.join(timeout=3.0)
        # Drain loop callbacks
        loop.run_until_complete(asyncio.sleep(0))

        # Should have two events: first "created", then "updated"
        assert len(collected) == 2, f"Expected 2 events, got {len(collected)}: {collected}"
        assert collected[0].change_type == "created"
        assert collected[1].change_type == "updated"
        loop.close()

    def test_subscription_thread_stops_on_stop_event(self) -> None:
        """_subscription_thread exits when stop_event is set."""
        mock_bridge = MagicMock()

        stop_event = threading.Event()

        def fake_subscribe(query_name, args=None):
            while not stop_event.is_set():
                yield []
                time.sleep(0.01)

        mock_bridge.subscribe.side_effect = fake_subscribe

        loop = asyncio.new_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        thread = threading.Thread(
            target=_subscription_thread,
            args=(mock_bridge, "tasks:list", "tasks", loop, queue, stop_event),
            daemon=True,
        )
        thread.start()

        # Signal stop after a short delay
        time.sleep(0.05)
        stop_event.set()
        thread.join(timeout=3.0)

        assert not thread.is_alive(), "Thread should have exited after stop_event was set"

    def test_subscription_thread_handles_exception_gracefully(self) -> None:
        """_subscription_thread handles subscribe() exceptions without crashing."""
        mock_bridge = MagicMock()

        def bad_subscribe(query_name, args=None):
            raise RuntimeError("Connection error")
            yield  # make it a generator

        mock_bridge.subscribe.side_effect = bad_subscribe

        loop = asyncio.new_event_loop()
        queue: asyncio.Queue = asyncio.Queue()
        stop_event = threading.Event()

        thread = threading.Thread(
            target=_subscription_thread,
            args=(mock_bridge, "tasks:list", "tasks", loop, queue, stop_event),
            daemon=True,
        )
        thread.start()
        thread.join(timeout=3.0)

        # Thread should exit cleanly (not crash the process)
        assert not thread.is_alive()
        # Queue should be empty (no events pushed before exception)
        assert queue.empty()
