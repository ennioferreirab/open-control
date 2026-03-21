"""Tests for Session Management for Claude Code agents.

Covers:
- AC1: session_id stored on task completion (both task-scoped and latest keys)
- AC2: session looked up for resume on task execution
- AC3: handle_cc_thread_reply routes follow-up with correct session
- AC4: session PERSISTS after task done (no soft-delete on completion — C1 fix)
- Fresh session when no stored session exists
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from claude_code.types import CCTaskResult, ClaudeCodeOpts, WorkspaceContext

from mc.contexts.execution.executor import TaskExecutor
from mc.types import AgentData


def _cc_execute_patches():
    """Return a combined context manager that mocks all dependencies
    that ``_execute_cc_task`` now requires beyond the three original
    mocks (CCWorkspaceManager, MCSocketServer, ClaudeCodeProvider).

    These cover board resolution, Convex agent sync, description enrichment,
    output-dir snapshot, orientation loading, nanobot config loading, and
    the ask-user handler.
    """
    from contextlib import contextmanager

    @contextmanager
    def _patches():
        with (
            patch.object(TaskExecutor, "_resolve_cc_board", new_callable=AsyncMock, return_value=(None, "clean")),
            patch.object(TaskExecutor, "_sync_cc_convex_agent", new_callable=AsyncMock, return_value=None),
            patch.object(TaskExecutor, "_enrich_cc_description", new_callable=AsyncMock, side_effect=lambda tid, desc, td: desc or ""),
            patch("mc.contexts.execution.cc_executor.snapshot_output_dir", return_value=set()),
            patch("mc.contexts.execution.cc_executor.relocate_invalid_memory_files"),
            patch("mc.contexts.execution.cc_executor.collect_output_artifacts", return_value=[]),
            patch("mc.infrastructure.orientation.load_orientation", return_value=None),
            patch("mc.contexts.conversation.ask_user.handler.AskUserHandler"),
            patch("nanobot.config.loader.load_config") as mock_cfg,
        ):
            mock_cfg.return_value.claude_code.cli_path = "/usr/bin/claude"
            mock_cfg.return_value.claude_code = MagicMock()
            yield
    return _patches()

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_bridge() -> MagicMock:
    """Return a minimal ConvexBridge mock."""
    bridge = MagicMock()
    bridge.send_message = MagicMock(return_value=None)
    bridge.create_activity = MagicMock(return_value=None)
    bridge.update_task_status = MagicMock(return_value=None)
    bridge.mutation = MagicMock(return_value=None)
    bridge.query = MagicMock(return_value=None)
    return bridge


def _make_executor(bridge: MagicMock | None = None) -> TaskExecutor:
    bridge = bridge or _make_bridge()
    return TaskExecutor(bridge)


def _cc_agent(backend: str = "claude-code") -> AgentData:
    return AgentData(
        name="my-cc-agent",
        display_name="CC Agent",
        role="developer",
        backend=backend,
        claude_code_opts=ClaudeCodeOpts(max_budget_usd=1.0, max_turns=10),
    )


def _ws_ctx() -> WorkspaceContext:
    return WorkspaceContext(
        cwd=Path("/tmp/test-ws"),
        mcp_config=Path("/tmp/test-ws/.mcp.json"),
        claude_md=Path("/tmp/test-ws/CLAUDE.md"),
        socket_path="/tmp/mc-test.sock",
    )


def _cc_result(
    output: str = "All done",
    session_id: str = "sess-abc123",
    cost_usd: float = 0.0123,
    is_error: bool = False,
) -> CCTaskResult:
    return CCTaskResult(
        output=output,
        session_id=session_id,
        cost_usd=cost_usd,
        usage={"input_tokens": 100, "output_tokens": 50},
        is_error=is_error,
    )


# ---------------------------------------------------------------------------
# AC1: Session stored on task completion
# ---------------------------------------------------------------------------


class TestSessionStorageOnCompletion:
    """AC1: _complete_cc_task stores session_id in settings."""

    @pytest.mark.asyncio
    async def test_session_stored_with_task_scoped_key(self):
        """When result has a session_id, it is stored under cc_session:{agent}:{task}."""
        bridge = _make_bridge()
        executor = _make_executor(bridge)
        result = _cc_result(session_id="sess-xyz")

        await executor._complete_cc_task(
            task_id="task-001",
            title="My Task",
            agent_name="my-cc-agent",
            result=result,
        )

        # Find the call that stored the task-scoped key
        mutation_calls = bridge.mutation.call_args_list
        task_scoped_calls = [
            c for c in mutation_calls
            if c[0][0] == "settings:set"
            and c[0][1].get("key") == "cc_session:my-cc-agent:task-001"
        ]
        assert task_scoped_calls, "Expected settings:set for task-scoped key"
        assert task_scoped_calls[0][0][1]["value"] == "sess-xyz"

    @pytest.mark.asyncio
    async def test_session_stored_with_latest_key(self):
        """When result has a session_id, it is also stored under cc_session:{agent}:latest."""
        bridge = _make_bridge()
        executor = _make_executor(bridge)
        result = _cc_result(session_id="sess-xyz")

        await executor._complete_cc_task(
            task_id="task-001",
            title="My Task",
            agent_name="my-cc-agent",
            result=result,
        )

        mutation_calls = bridge.mutation.call_args_list
        latest_calls = [
            c for c in mutation_calls
            if c[0][0] == "settings:set"
            and c[0][1].get("key") == "cc_session:my-cc-agent:latest"
        ]
        assert latest_calls, "Expected settings:set for latest key"
        assert latest_calls[0][0][1]["value"] == "sess-xyz"

    @pytest.mark.asyncio
    async def test_no_session_stored_when_empty_session_id(self):
        """When result.session_id is empty, no session is stored."""
        bridge = _make_bridge()
        executor = _make_executor(bridge)
        result = _cc_result(session_id="")

        await executor._complete_cc_task(
            task_id="task-001",
            title="My Task",
            agent_name="my-cc-agent",
            result=result,
        )

        # No session should be stored when session_id is empty
        mutation_calls = bridge.mutation.call_args_list
        store_calls = [
            c for c in mutation_calls
            if c[0][0] == "settings:set"
            and c[0][1].get("key") in (
                "cc_session:my-cc-agent:task-001",
                "cc_session:my-cc-agent:latest",
            )
            and c[0][1].get("value") != ""
        ]
        assert not store_calls, f"Should not store session when session_id is empty, got: {store_calls}"

    @pytest.mark.asyncio
    async def test_session_storage_failure_does_not_prevent_completion(self):
        """If session storage fails, the task still transitions to DONE."""
        bridge = _make_bridge()
        bridge.mutation.side_effect = Exception("Convex unavailable")
        executor = _make_executor(bridge)
        result = _cc_result(session_id="sess-xyz")

        # Should not raise
        await executor._complete_cc_task(
            task_id="task-001",
            title="My Task",
            agent_name="my-cc-agent",
            result=result,
        )

        # update_task_status should still be called
        bridge.update_task_status.assert_called_once()


# ---------------------------------------------------------------------------
# AC2: Session looked up on task execution
# ---------------------------------------------------------------------------


class TestSessionLookupOnExecution:
    """AC2: _execute_cc_task looks up and passes session_id to provider."""

    @pytest.mark.asyncio
    async def test_stored_session_passed_to_provider(self):
        """When a session exists in settings, it is passed as session_id to execute_task."""
        bridge = _make_bridge()
        # settings:get returns the stored session_id string directly
        bridge.query.return_value = "sess-stored-123"
        executor = _make_executor(bridge)
        agent_data = _cc_agent()
        ws_ctx = _ws_ctx()
        result = _cc_result(session_id="sess-stored-123")

        with (
            _cc_execute_patches(),
            patch("claude_code.workspace.CCWorkspaceManager") as MockWsMgr,
            patch("claude_code.ipc_server.MCSocketServer") as MockIpc,
            patch("claude_code.provider.ClaudeCodeProvider") as MockProvider,
        ):
            MockWsMgr.return_value.prepare.return_value = ws_ctx
            mock_ipc = MockIpc.return_value
            mock_ipc.start = AsyncMock()
            mock_ipc.stop = AsyncMock()
            mock_provider = MockProvider.return_value
            mock_provider.execute_task = AsyncMock(return_value=result)

            await executor._execute_cc_task(
                task_id="task-999",
                title="Resume Task",
                description="Continue from before",
                agent_name="my-cc-agent",
                agent_data=agent_data,
            )

            # Provider should receive the stored session_id
            mock_provider.execute_task.assert_awaited_once()
            call_kwargs = mock_provider.execute_task.call_args
            assert call_kwargs.kwargs.get("session_id") == "sess-stored-123" or \
                   (call_kwargs.args and "sess-stored-123" in call_kwargs.args), \
                   f"session_id not passed correctly: {call_kwargs}"

    @pytest.mark.asyncio
    async def test_no_session_when_settings_returns_none(self):
        """When settings:get returns None, session_id is None (fresh start)."""
        bridge = _make_bridge()
        bridge.query.return_value = None
        executor = _make_executor(bridge)
        agent_data = _cc_agent()
        ws_ctx = _ws_ctx()
        result = _cc_result(session_id="sess-new-456")

        with (
            _cc_execute_patches(),
            patch("claude_code.workspace.CCWorkspaceManager") as MockWsMgr,
            patch("claude_code.ipc_server.MCSocketServer") as MockIpc,
            patch("claude_code.provider.ClaudeCodeProvider") as MockProvider,
        ):
            MockWsMgr.return_value.prepare.return_value = ws_ctx
            mock_ipc = MockIpc.return_value
            mock_ipc.start = AsyncMock()
            mock_ipc.stop = AsyncMock()
            mock_provider = MockProvider.return_value
            mock_provider.execute_task = AsyncMock(return_value=result)

            await executor._execute_cc_task(
                task_id="task-000",
                title="Fresh Task",
                description=None,
                agent_name="my-cc-agent",
                agent_data=agent_data,
            )

            mock_provider.execute_task.assert_awaited_once()
            call_kwargs = mock_provider.execute_task.call_args
            # session_id should be None for fresh start
            passed_session = call_kwargs.kwargs.get("session_id")
            assert passed_session is None, f"Expected None session_id, got: {passed_session}"

    @pytest.mark.asyncio
    async def test_session_lookup_failure_starts_fresh(self):
        """If the settings query fails, execution starts with no session."""
        bridge = _make_bridge()
        bridge.query.side_effect = Exception("Query failed")
        executor = _make_executor(bridge)
        agent_data = _cc_agent()
        ws_ctx = _ws_ctx()
        result = _cc_result()

        with (
            _cc_execute_patches(),
            patch("claude_code.workspace.CCWorkspaceManager") as MockWsMgr,
            patch("claude_code.ipc_server.MCSocketServer") as MockIpc,
            patch("claude_code.provider.ClaudeCodeProvider") as MockProvider,
        ):
            MockWsMgr.return_value.prepare.return_value = ws_ctx
            mock_ipc = MockIpc.return_value
            mock_ipc.start = AsyncMock()
            mock_ipc.stop = AsyncMock()
            mock_provider = MockProvider.return_value
            mock_provider.execute_task = AsyncMock(return_value=result)

            # Should not raise
            await executor._execute_cc_task(
                task_id="task-111",
                title="Task With Query Failure",
                description=None,
                agent_name="my-cc-agent",
                agent_data=agent_data,
            )

            mock_provider.execute_task.assert_awaited_once()
            call_kwargs = mock_provider.execute_task.call_args
            passed_session = call_kwargs.kwargs.get("session_id")
            assert passed_session is None, "Should start fresh when query fails"


# ---------------------------------------------------------------------------
# AC3: Thread follow-up routing via handle_cc_thread_reply
# ---------------------------------------------------------------------------


class TestThreadFollowUp:
    """AC3: handle_cc_thread_reply resumes the CC session with user's message."""

    @pytest.mark.asyncio
    async def test_reply_resumes_stored_session(self):
        """handle_cc_thread_reply passes the stored session_id to the provider."""
        bridge = _make_bridge()
        bridge.query.return_value = "sess-thread-abc"
        executor = _make_executor(bridge)
        agent_data = _cc_agent()
        ws_ctx = _ws_ctx()
        result = _cc_result(session_id="sess-thread-abc", output="Here is my response")

        with (
            patch("claude_code.workspace.CCWorkspaceManager") as MockWsMgr,
            patch("claude_code.ipc_server.MCSocketServer") as MockIpc,
            patch("claude_code.provider.ClaudeCodeProvider") as MockProvider,
        ):
            MockWsMgr.return_value.prepare.return_value = ws_ctx
            mock_ipc = MockIpc.return_value
            mock_ipc.start = AsyncMock()
            mock_ipc.stop = AsyncMock()
            mock_provider = MockProvider.return_value
            mock_provider.execute_task = AsyncMock(return_value=result)

            output = await executor.handle_cc_thread_reply(
                task_id="task-222",
                agent_name="my-cc-agent",
                user_message="Can you elaborate on step 3?",
                agent_data=agent_data,
            )

        assert output == "Here is my response"
        # Provider should receive the stored session_id
        mock_provider.execute_task.assert_awaited_once()
        call_kwargs = mock_provider.execute_task.call_args
        assert call_kwargs.kwargs.get("session_id") == "sess-thread-abc", \
            f"Expected session_id='sess-thread-abc', got: {call_kwargs}"

    @pytest.mark.asyncio
    async def test_reply_updates_session_after_response(self):
        """After a thread reply, the session_id is updated in settings."""
        bridge = _make_bridge()
        bridge.query.return_value = "sess-old"
        executor = _make_executor(bridge)
        agent_data = _cc_agent()
        ws_ctx = _ws_ctx()
        result = _cc_result(session_id="sess-new-after-reply")

        with (
            patch("claude_code.workspace.CCWorkspaceManager") as MockWsMgr,
            patch("claude_code.ipc_server.MCSocketServer") as MockIpc,
            patch("claude_code.provider.ClaudeCodeProvider") as MockProvider,
        ):
            MockWsMgr.return_value.prepare.return_value = ws_ctx
            mock_ipc = MockIpc.return_value
            mock_ipc.start = AsyncMock()
            mock_ipc.stop = AsyncMock()
            mock_provider = MockProvider.return_value
            mock_provider.execute_task = AsyncMock(return_value=result)

            await executor.handle_cc_thread_reply(
                task_id="task-333",
                agent_name="my-cc-agent",
                user_message="Follow-up question",
                agent_data=agent_data,
            )

        # Task-scoped session key should be updated with the new session_id
        mutation_calls = bridge.mutation.call_args_list
        task_update_calls = [
            c for c in mutation_calls
            if c[0][0] == "settings:set"
            and c[0][1].get("key") == "cc_session:my-cc-agent:task-333"
            and c[0][1].get("value") == "sess-new-after-reply"
        ]
        assert task_update_calls, (
            f"Expected task-scoped session update call, got: {mutation_calls}"
        )
        # The :latest key should also be updated (L1 fix)
        latest_update_calls = [
            c for c in mutation_calls
            if c[0][0] == "settings:set"
            and c[0][1].get("key") == "cc_session:my-cc-agent:latest"
            and c[0][1].get("value") == "sess-new-after-reply"
        ]
        assert latest_update_calls, (
            f"Expected :latest key update after thread reply, got: {mutation_calls}"
        )

    @pytest.mark.asyncio
    async def test_reply_returns_none_on_error_result(self):
        """If CC execution returns is_error=True, handle_cc_thread_reply returns None."""
        bridge = _make_bridge()
        bridge.query.return_value = None
        executor = _make_executor(bridge)
        agent_data = _cc_agent()
        ws_ctx = _ws_ctx()
        error_result = _cc_result(output="Error occurred", is_error=True)

        with (
            patch("claude_code.workspace.CCWorkspaceManager") as MockWsMgr,
            patch("claude_code.ipc_server.MCSocketServer") as MockIpc,
            patch("claude_code.provider.ClaudeCodeProvider") as MockProvider,
        ):
            MockWsMgr.return_value.prepare.return_value = ws_ctx
            mock_ipc = MockIpc.return_value
            mock_ipc.start = AsyncMock()
            mock_ipc.stop = AsyncMock()
            mock_provider = MockProvider.return_value
            mock_provider.execute_task = AsyncMock(return_value=error_result)

            output = await executor.handle_cc_thread_reply(
                task_id="task-444",
                agent_name="my-cc-agent",
                user_message="What went wrong?",
                agent_data=agent_data,
            )

        assert output is None

    @pytest.mark.asyncio
    async def test_reply_returns_none_on_workspace_failure(self):
        """If workspace preparation fails, handle_cc_thread_reply returns None."""
        bridge = _make_bridge()
        executor = _make_executor(bridge)
        agent_data = _cc_agent()

        with patch("claude_code.workspace.CCWorkspaceManager") as MockWsMgr:
            MockWsMgr.return_value.prepare.side_effect = RuntimeError("disk full")

            output = await executor.handle_cc_thread_reply(
                task_id="task-555",
                agent_name="my-cc-agent",
                user_message="Hello",
                agent_data=agent_data,
            )

        assert output is None


# ---------------------------------------------------------------------------
# AC4: Session persists after task done (C1 fix — no soft-delete on completion)
# ---------------------------------------------------------------------------


class TestSessionCleanupOnDone:
    """AC4: Session PERSISTS after task completion for follow-up resume.

    The original implementation incorrectly soft-deleted the task-scoped
    session key immediately after storing it (store-then-delete in the same
    function). That bug was fixed: _complete_cc_task no longer clears the
    session. Session cleanup is deferred until agent deletion.
    """

    @pytest.mark.asyncio
    async def test_task_scoped_session_persists_after_done(self):
        """After transitioning to DONE, the task-scoped session key is NOT cleared."""
        bridge = _make_bridge()
        executor = _make_executor(bridge)
        result = _cc_result(session_id="sess-to-persist")

        await executor._complete_cc_task(
            task_id="task-999",
            title="Done Task",
            agent_name="my-cc-agent",
            result=result,
        )

        mutation_calls = bridge.mutation.call_args_list
        # Verify no soft-delete (empty value) was written for the task-scoped key
        soft_delete_calls = [
            c for c in mutation_calls
            if c[0][0] == "settings:set"
            and c[0][1].get("key") == "cc_session:my-cc-agent:task-999"
            and c[0][1].get("value") == ""
        ]
        assert not soft_delete_calls, (
            f"Session must NOT be cleared on task done (C1 fix); got: {mutation_calls}"
        )
        # Verify the session was stored with the correct value
        store_calls = [
            c for c in mutation_calls
            if c[0][0] == "settings:set"
            and c[0][1].get("key") == "cc_session:my-cc-agent:task-999"
            and c[0][1].get("value") == "sess-to-persist"
        ]
        assert store_calls, (
            f"Session must be stored with session_id after done; got: {mutation_calls}"
        )

    @pytest.mark.asyncio
    async def test_latest_key_not_cleared_on_done(self):
        """The cc_session:{agent}:latest key is NOT cleared when task is done."""
        bridge = _make_bridge()
        executor = _make_executor(bridge)
        result = _cc_result(session_id="sess-keep-latest")

        await executor._complete_cc_task(
            task_id="task-999",
            title="Done Task",
            agent_name="my-cc-agent",
            result=result,
        )

        mutation_calls = bridge.mutation.call_args_list
        clear_latest_calls = [
            c for c in mutation_calls
            if c[0][0] == "settings:set"
            and c[0][1].get("key") == "cc_session:my-cc-agent:latest"
            and c[0][1].get("value") == ""
        ]
        assert not clear_latest_calls, (
            "The latest session key should not be cleared when task is done"
        )

    @pytest.mark.asyncio
    async def test_session_storage_failure_still_completes_task(self):
        """If session storage fails, the task still transitions to DONE."""
        bridge = _make_bridge()
        bridge.mutation.side_effect = Exception("Storage failed")
        executor = _make_executor(bridge)
        result = _cc_result(session_id="sess-x")

        # Should not raise
        await executor._complete_cc_task(
            task_id="task-store-fail",
            title="Task",
            agent_name="my-cc-agent",
            result=result,
        )

        # update_task_status should still have been called
        bridge.update_task_status.assert_called_once()


# ---------------------------------------------------------------------------
# Fresh session on first execution
# ---------------------------------------------------------------------------


class TestFreshSession:
    """Ensure a fresh task (no stored session) starts with session_id=None."""

    @pytest.mark.asyncio
    async def test_fresh_task_uses_no_session(self):
        """When no session is stored, provider.execute_task gets session_id=None."""
        bridge = _make_bridge()
        bridge.query.return_value = None
        executor = _make_executor(bridge)
        agent_data = _cc_agent()
        ws_ctx = _ws_ctx()
        result = _cc_result(session_id="sess-brand-new")

        with (
            _cc_execute_patches(),
            patch("claude_code.workspace.CCWorkspaceManager") as MockWsMgr,
            patch("claude_code.ipc_server.MCSocketServer") as MockIpc,
            patch("claude_code.provider.ClaudeCodeProvider") as MockProvider,
        ):
            MockWsMgr.return_value.prepare.return_value = ws_ctx
            mock_ipc = MockIpc.return_value
            mock_ipc.start = AsyncMock()
            mock_ipc.stop = AsyncMock()
            mock_provider = MockProvider.return_value
            mock_provider.execute_task = AsyncMock(return_value=result)

            await executor._execute_cc_task(
                task_id="task-fresh",
                title="Fresh Task",
                description=None,
                agent_name="my-cc-agent",
                agent_data=agent_data,
            )

        call_kwargs = mock_provider.execute_task.call_args
        passed_session = call_kwargs.kwargs.get("session_id")
        assert passed_session is None, f"Fresh task should have no session, got: {passed_session}"
