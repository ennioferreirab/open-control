"""Tests for MC plan sync: SyncIPCClient + MCPlanSyncHandler."""
from __future__ import annotations

import json
import os
import socket
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

import pytest


def _short_sock_path(name: str) -> str:
    """Return a short Unix socket path under /tmp to stay within the 104-char macOS limit."""
    return str(Path(tempfile.gettempdir()) / name)


# ---------------------------------------------------------------------------
# SyncIPCClient tests
# ---------------------------------------------------------------------------

class TestSyncIPCClient:
    """Tests for the synchronous IPC client."""

    def test_request_sends_json_rpc_and_returns_response(self):
        """Client sends JSON-RPC request and parses response."""
        sock_path = _short_sock_path("mc_ipc_test.sock")
        # Clean up any leftover socket file
        Path(sock_path).unlink(missing_ok=True)

        # Start a mock IPC server
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(sock_path)
        server.listen(1)

        def handle():
            conn, _ = server.accept()
            data = b""
            while b"\n" not in data:
                data += conn.recv(4096)
            request = json.loads(data.decode())
            assert request["method"] == "report_progress"
            assert request["params"]["message"] == "hello"
            response = json.dumps({"status": "Progress reported"}) + "\n"
            conn.sendall(response.encode())
            conn.close()
            server.close()

        t = threading.Thread(target=handle)
        t.start()

        from mc.hooks.ipc_sync import SyncIPCClient
        client = SyncIPCClient(sock_path)
        result = client.request("report_progress", {"message": "hello"})
        assert result == {"status": "Progress reported"}
        t.join(timeout=5)
        Path(sock_path).unlink(missing_ok=True)

    def test_request_raises_connection_error_when_no_socket(self):
        """Client raises ConnectionError when socket doesn't exist."""
        from mc.hooks.ipc_sync import SyncIPCClient
        client = SyncIPCClient(_short_sock_path("mc_ipc_nonexistent.sock"))
        with pytest.raises(ConnectionError):
            client.request("report_progress", {"message": "hello"})

    def test_request_raises_connection_error_on_timeout(self):
        """Client raises ConnectionError when server doesn't respond."""
        sock_path = _short_sock_path("mc_ipc_timeout.sock")
        Path(sock_path).unlink(missing_ok=True)

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(sock_path)
        server.listen(1)

        def handle():
            conn, _ = server.accept()
            import time
            time.sleep(10)  # Don't respond
            conn.close()
            server.close()

        t = threading.Thread(target=handle, daemon=True)
        t.start()

        from mc.hooks.ipc_sync import SyncIPCClient
        client = SyncIPCClient(sock_path, timeout=0.5)
        with pytest.raises(ConnectionError):
            client.request("report_progress", {"message": "hello"})
        Path(sock_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# MC context discovery tests
# ---------------------------------------------------------------------------

class TestMCContextDiscovery:
    """Tests for _discover_mc_context in MCPlanSyncHandler."""

    def _make_handler(self, payload):
        from mc.hooks.handlers.mc_plan_sync import MCPlanSyncHandler
        from mc.hooks.context import HookContext
        ctx = HookContext("test-session")
        return MCPlanSyncHandler(ctx, payload)

    def test_returns_none_when_no_mcp_json_and_no_env(self, tmp_path):
        """No MC context available — should return None."""
        handler = self._make_handler({"cwd": str(tmp_path)})
        assert handler._discover_mc_context() is None

    def test_reads_mcp_json_from_cwd(self, tmp_path):
        """Discovers MC context from .mcp.json in cwd."""
        sock_path = str(tmp_path / "mc.sock")
        Path(sock_path).touch()

        mcp_config = {
            "mcpServers": {
                "nanobot": {
                    "command": "uv",
                    "args": ["run", "python", "-m", "claude_code.mcp_bridge"],
                    "env": {
                        "MC_SOCKET_PATH": sock_path,
                        "AGENT_NAME": "test-agent",
                        "TASK_ID": "task-123",
                    },
                }
            }
        }
        (tmp_path / ".mcp.json").write_text(json.dumps(mcp_config))

        handler = self._make_handler({"cwd": str(tmp_path)})
        mc_ctx = handler._discover_mc_context()
        assert mc_ctx is not None
        assert mc_ctx["socket_path"] == sock_path
        assert mc_ctx["agent_name"] == "test-agent"
        assert mc_ctx["task_id"] == "task-123"

    def test_env_var_takes_precedence(self, tmp_path):
        """MC_SOCKET_PATH env var is preferred over .mcp.json."""
        sock_path = str(tmp_path / "env.sock")
        Path(sock_path).touch()

        with patch.dict(os.environ, {
            "MC_SOCKET_PATH": sock_path,
            "AGENT_NAME": "env-agent",
            "TASK_ID": "env-task",
        }):
            handler = self._make_handler({"cwd": str(tmp_path)})
            mc_ctx = handler._discover_mc_context()
            assert mc_ctx is not None
            assert mc_ctx["socket_path"] == sock_path
            assert mc_ctx["agent_name"] == "env-agent"

    def test_returns_none_when_socket_file_missing(self, tmp_path):
        """Socket path in .mcp.json but file doesn't exist — no MC."""
        mcp_config = {
            "mcpServers": {
                "nanobot": {
                    "env": {
                        "MC_SOCKET_PATH": "/tmp/nonexistent-mc-test.sock",
                        "AGENT_NAME": "agent",
                        "TASK_ID": "task",
                    },
                }
            }
        }
        (tmp_path / ".mcp.json").write_text(json.dumps(mcp_config))

        handler = self._make_handler({"cwd": str(tmp_path)})
        assert handler._discover_mc_context() is None


# ---------------------------------------------------------------------------
# Plan write sync tests
# ---------------------------------------------------------------------------

class TestPlanWriteSync:
    """Tests for _handle_plan_write in MCPlanSyncHandler."""

    def _make_handler(self, payload):
        from mc.hooks.handlers.mc_plan_sync import MCPlanSyncHandler
        from mc.hooks.context import HookContext
        ctx = HookContext("test-session")
        return MCPlanSyncHandler(ctx, payload)

    def test_reports_plan_to_mc_via_ipc(self, tmp_path):
        """When a plan file is written, report_progress is called."""
        plan_content = (
            "# Plan\n\n"
            "### Task 1: Setup\n\nDo stuff\n\n"
            "### Task 2: Build\n\n**Blocked by:** Task 1\n"
        )
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Write",
            "cwd": str(tmp_path),
            "session_id": "test-session",
            "tool_input": {
                "file_path": str(tmp_path / "docs" / "plans" / "my-plan.md"),
                "content": plan_content,
            },
        }
        handler = self._make_handler(payload)
        mc_ctx = {
            "socket_path": "/tmp/fake.sock",
            "agent_name": "test-agent",
            "task_id": "task-123",
        }

        ipc_calls = []

        def mock_request(method, params):
            ipc_calls.append((method, params))
            return {"status": "Progress reported"}

        with (
            patch("mc.hooks.handlers.mc_plan_sync.SyncIPCClient") as MockClient,
            patch("mc.hooks.handlers.mc_plan_sync.is_plan_file", return_value=True),
        ):
            MockClient.return_value.request = mock_request
            result = handler._handle_plan_write(mc_ctx)

        assert result is not None
        assert "2 task" in result
        assert len(ipc_calls) == 1
        assert ipc_calls[0][0] == "report_progress"
        assert ipc_calls[0][1].get("task_id") == "task-123"

    def test_skips_non_plan_files(self, tmp_path):
        """Non-plan files are silently ignored."""
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Write",
            "cwd": str(tmp_path),
            "session_id": "test-session",
            "tool_input": {
                "file_path": str(tmp_path / "src" / "main.py"),
                "content": "print('hello')",
            },
        }
        handler = self._make_handler(payload)
        mc_ctx = {"socket_path": "/tmp/fake.sock", "agent_name": "a", "task_id": "t"}

        with patch("mc.hooks.handlers.mc_plan_sync.is_plan_file", return_value=False):
            result = handler._handle_plan_write(mc_ctx)
        assert result is None

    def test_survives_ipc_failure(self, tmp_path):
        """IPC failure is non-fatal — still returns summary."""
        plan_content = "### Task 1: Setup\n\nDo stuff\n"
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Write",
            "cwd": str(tmp_path),
            "session_id": "test-session",
            "tool_input": {
                "file_path": str(tmp_path / "docs" / "plans" / "plan.md"),
                "content": plan_content,
            },
        }
        handler = self._make_handler(payload)
        mc_ctx = {"socket_path": "/tmp/fake.sock", "agent_name": "a", "task_id": "t"}

        with (
            patch("mc.hooks.handlers.mc_plan_sync.SyncIPCClient") as MockClient,
            patch("mc.hooks.handlers.mc_plan_sync.is_plan_file", return_value=True),
        ):
            MockClient.return_value.request.side_effect = ConnectionError("nope")
            result = handler._handle_plan_write(mc_ctx)

        assert result is not None
        assert "1 task" in result


# ---------------------------------------------------------------------------
# Task completed sync tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def tracker_setup(tmp_path):
    """Create a tracker JSON for task completion tests."""
    tracker_dir = tmp_path / ".claude" / "plan-tracker"
    tracker_dir.mkdir(parents=True)
    tracker = {
        "plan_file": "docs/plans/my-plan.md",
        "created_at": "2026-03-04T12:00:00Z",
        "steps": [
            {"id": 1, "name": "Setup", "order": 1, "status": "completed",
             "blocked_by": [], "parallel_group": 1},
            {"id": 2, "name": "Build API", "order": 2, "status": "pending",
             "blocked_by": [1], "parallel_group": 2},
            {"id": 3, "name": "Frontend", "order": 3, "status": "pending",
             "blocked_by": [1, 2], "parallel_group": 3},
        ],
    }
    tracker_path = tracker_dir / "my-plan.json"
    tracker_path.write_text(json.dumps(tracker, indent=2))
    return tmp_path, tracker_dir, tracker_path


class TestTaskCompletedSync:
    """Tests for _handle_task_completed in MCPlanSyncHandler."""

    def _make_handler(self, payload):
        from mc.hooks.handlers.mc_plan_sync import MCPlanSyncHandler
        from mc.hooks.context import HookContext
        ctx = HookContext("test-session")
        return MCPlanSyncHandler(ctx, payload)

    def test_reports_step_completion_to_mc(self, tracker_setup):
        """Completing a task reports progress via IPC."""
        tmp_path, tracker_dir, tracker_path = tracker_setup
        payload = {
            "hook_event_name": "TaskCompleted",
            "session_id": "test-session",
            "cwd": str(tmp_path),
            "task": {"subject": "Task 2: Build API"},
        }
        handler = self._make_handler(payload)
        mc_ctx = {"socket_path": "/tmp/fake.sock", "agent_name": "a", "task_id": "t"}

        ipc_calls = []

        def mock_request(method, params):
            ipc_calls.append((method, params))
            return {"status": "Progress reported"}

        from mc.hooks.config import HookConfig
        config = HookConfig(tracker_dir=".claude/plan-tracker")

        with (
            patch("mc.hooks.handlers.mc_plan_sync.SyncIPCClient") as MockClient,
            patch("mc.hooks.handlers.mc_plan_sync.get_project_root", return_value=tmp_path),
            patch("mc.hooks.handlers.mc_plan_sync.get_config", return_value=config),
        ):
            MockClient.return_value.request = mock_request
            result = handler._handle_task_completed(mc_ctx)

        assert result is not None
        assert "Build API" in result
        assert "2/3" in result
        assert len(ipc_calls) == 1
        assert ipc_calls[0][0] == "report_progress"

    def test_no_match_returns_none(self, tracker_setup):
        """Task that doesn't match any step is ignored."""
        tmp_path, _, _ = tracker_setup
        payload = {
            "hook_event_name": "TaskCompleted",
            "session_id": "test-session",
            "cwd": str(tmp_path),
            "task": {"subject": "Unrelated task"},
        }
        handler = self._make_handler(payload)
        mc_ctx = {"socket_path": "/tmp/fake.sock", "agent_name": "a", "task_id": "t"}

        from mc.hooks.config import HookConfig
        config = HookConfig(tracker_dir=".claude/plan-tracker")

        with (
            patch("mc.hooks.handlers.mc_plan_sync.get_project_root", return_value=tmp_path),
            patch("mc.hooks.handlers.mc_plan_sync.get_config", return_value=config),
        ):
            result = handler._handle_task_completed(mc_ctx)
        assert result is None

    def test_survives_ipc_failure_on_completion(self, tracker_setup):
        """IPC failure during step completion is non-fatal."""
        tmp_path, _, _ = tracker_setup
        payload = {
            "hook_event_name": "TaskCompleted",
            "session_id": "test-session",
            "cwd": str(tmp_path),
            "task": {"subject": "Task 2: Build API"},
        }
        handler = self._make_handler(payload)
        mc_ctx = {"socket_path": "/tmp/fake.sock", "agent_name": "a", "task_id": "t"}

        from mc.hooks.config import HookConfig
        config = HookConfig(tracker_dir=".claude/plan-tracker")

        with (
            patch("mc.hooks.handlers.mc_plan_sync.SyncIPCClient") as MockClient,
            patch("mc.hooks.handlers.mc_plan_sync.get_project_root", return_value=tmp_path),
            patch("mc.hooks.handlers.mc_plan_sync.get_config", return_value=config),
        ):
            MockClient.return_value.request.side_effect = ConnectionError("nope")
            result = handler._handle_task_completed(mc_ctx)

        assert result is not None
        assert "Build API" in result


# ---------------------------------------------------------------------------
# Integration: full dispatch test
# ---------------------------------------------------------------------------

class TestMCPlanSyncIntegration:
    """End-to-end test through the dispatcher."""

    def test_plan_write_dispatches_to_both_handlers(self, tmp_path):
        """PostToolUse/Write dispatches to both PlanTracker AND MCPlanSync."""
        from mc.hooks.dispatcher import _dispatch
        from mc.hooks.config import HookConfig
        from mc.hooks.discovery import reset_cache

        plan_content = "### Task 1: Setup\n\n### Task 2: Build\n\n**Blocked by:** Task 1\n"
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        tracker_dir = tmp_path / ".claude" / "plan-tracker"
        tracker_dir.mkdir(parents=True)
        state_dir = tmp_path / ".claude" / "hook-state"
        state_dir.mkdir(parents=True)

        config = HookConfig(
            plan_pattern="docs/plans/*.md",
            tracker_dir=".claude/plan-tracker",
            state_dir=".claude/hook-state",
        )

        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Write",
            "session_id": "integration-test",
            "cwd": str(tmp_path),
            "tool_input": {
                "file_path": str(tmp_path / "docs" / "plans" / "test-plan.md"),
                "content": plan_content,
            },
        }

        reset_cache()

        with (
            patch("mc.hooks.config.get_project_root", return_value=tmp_path),
            patch("mc.hooks.config.get_config", return_value=config),
            patch("mc.hooks.context.get_project_root", return_value=tmp_path),
            patch("mc.hooks.context.get_config", return_value=config),
            patch("mc.hooks.handlers.plan_tracker.get_project_root", return_value=tmp_path),
            patch("mc.hooks.handlers.plan_tracker.get_config", return_value=config),
            patch("mc.hooks.handlers.plan_capture.get_project_root", return_value=tmp_path),
            patch("mc.hooks.handlers.plan_capture.get_config", return_value=config),
        ):
            result = _dispatch(payload)

        # PlanTracker should have created a tracker file
        assert (tracker_dir / "test-plan.json").exists()
        # Result should contain PlanTracker output (MCPlanSync skips — no MC context)
        assert result is not None
        parsed = json.loads(result)
        assert "Plan tracker created" in parsed["hookSpecificOutput"]["additionalContext"]

        reset_cache()
