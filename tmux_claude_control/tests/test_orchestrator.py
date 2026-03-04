"""
Tests for the Orchestrator class that do NOT require live Claude sessions.

Extracted from orchestrator.py's original _run_skip_claude_tests() function.
These are pure Python unit tests — no tmux or Claude needed.
"""

import pytest

from tmux_claude_control import (
    ClaudeController,
    Response,
    ClaudeError,
    ScreenMode,
    ScreenState,
)
from tmux_claude_control.orchestrator import Orchestrator, WorkerResult


class TestOrchestratorInstantiation:
    """Tests for Orchestrator.__init__."""

    def test_default_prefix(self):
        """Orchestrator uses 'orch' as the default prefix."""
        orch = Orchestrator()
        assert orch.prefix == "orch", f"Expected prefix='orch', got {orch.prefix!r}"

    def test_empty_workers_on_init(self):
        """Orchestrator starts with an empty workers dict."""
        orch = Orchestrator()
        assert orch.workers == {}, f"Expected empty workers dict, got {orch.workers!r}"

    def test_custom_prefix(self):
        """Orchestrator accepts a custom prefix."""
        orch = Orchestrator(prefix="mytest")
        assert orch.prefix == "mytest"


class TestListWorkers:
    """Tests for Orchestrator.list_workers()."""

    def test_list_workers_empty(self):
        """list_workers() returns an empty list on a fresh orchestrator."""
        orch = Orchestrator()
        assert orch.list_workers() == []


class TestWorkerResult:
    """Tests for the WorkerResult dataclass."""

    def test_success_case(self):
        """WorkerResult can be constructed with a successful response."""
        state = ScreenState(mode=ScreenMode.IDLE, raw_text="test")
        resp = Response(
            text="Paris",
            screen_text="raw screen",
            duration=1.5,
            state=state,
            tool_calls=[],
        )
        wr = WorkerResult(worker_name="alpha", response=resp, duration=1.5)
        assert wr.worker_name == "alpha"
        assert wr.response is resp
        assert wr.error == ""
        assert wr.duration == 1.5

    def test_error_case(self):
        """WorkerResult can be constructed with an error (no response)."""
        wr_err = WorkerResult(
            worker_name="beta",
            response=None,
            error="Tmux session does not exist",
            duration=0.1,
        )
        assert wr_err.response is None
        assert wr_err.error == "Tmux session does not exist"


class TestGetWorker:
    """Tests for Orchestrator.get_worker()."""

    def test_get_worker_raises_key_error_for_unknown(self):
        """get_worker() raises KeyError for a worker name that was never registered."""
        orch = Orchestrator()
        with pytest.raises(KeyError):
            orch.get_worker("nonexistent")


class TestShutdownOperations:
    """Tests for shutdown_worker, kill_all, and shutdown_all on empty orchestrators."""

    def test_shutdown_worker_noop_on_unknown(self):
        """shutdown_worker() on an unknown name does not raise."""
        orch = Orchestrator()
        orch.shutdown_worker("nonexistent")  # should not raise

    def test_kill_all_noop_on_empty(self):
        """kill_all() on an empty orchestrator leaves workers dict empty."""
        orch = Orchestrator()
        orch.kill_all()
        assert orch.workers == {}

    def test_shutdown_all_noop_on_empty(self):
        """shutdown_all() on an empty orchestrator leaves workers dict empty."""
        orch = Orchestrator()
        orch.shutdown_all()
        assert orch.workers == {}


class TestDispatchParallel:
    """Tests for Orchestrator.dispatch_parallel() with missing workers."""

    def test_dispatch_parallel_captures_key_error(self):
        """dispatch_parallel() captures KeyError for non-existent workers in WorkerResult.error."""
        orch_empty = Orchestrator(prefix="empty")
        empty_results = orch_empty.dispatch_parallel(
            tasks={"ghost": "hello"},
            timeout=5.0,
        )
        assert "ghost" in empty_results
        assert empty_results["ghost"].response is None
        assert empty_results["ghost"].error != ""
