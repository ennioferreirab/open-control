"""Unit tests for TaskOrchestrator behavior.

After the planning phase removal, the orchestrator only manages inbox and review
routing loops. These tests verify the wiring and delegation.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from mc.infrastructure.runtime_context import RuntimeContext
from mc.runtime.orchestrator import TaskOrchestrator


def _make_bridge() -> MagicMock:
    bridge = MagicMock()
    bridge.query.return_value = None
    return bridge


def _make_ctx(bridge: MagicMock | None = None) -> RuntimeContext:
    if bridge is None:
        bridge = _make_bridge()
    return RuntimeContext(bridge=bridge, agents_dir=Path("/tmp/test-agents"))


class TestOrchestratorInit:
    """Tests for orchestrator initialization."""

    def test_creates_inbox_and_review_workers(self) -> None:
        bridge = _make_bridge()
        ctx = _make_ctx(bridge)
        orchestrator = TaskOrchestrator(ctx)

        assert orchestrator._inbox_worker is not None
        assert orchestrator._review_worker is not None

    def test_does_not_have_planning_or_kickoff_workers(self) -> None:
        bridge = _make_bridge()
        ctx = _make_ctx(bridge)
        orchestrator = TaskOrchestrator(ctx)

        assert not hasattr(orchestrator, "_planning_worker")
        assert not hasattr(orchestrator, "_kickoff_worker")

    def test_does_not_have_routing_or_kickoff_loops(self) -> None:
        bridge = _make_bridge()
        ctx = _make_ctx(bridge)
        orchestrator = TaskOrchestrator(ctx)

        assert not hasattr(orchestrator, "start_routing_loop")
        assert not hasattr(orchestrator, "start_kickoff_watch_loop")

    def test_accepts_bare_bridge_backward_compat(self) -> None:
        bridge = _make_bridge()
        orchestrator = TaskOrchestrator(bridge)

        assert orchestrator._bridge is bridge
        assert orchestrator._inbox_worker is not None
