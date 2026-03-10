"""Tests for the ChatHandler (Story 10.2, Story 20.1)."""

from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.application.execution.request import (
    ExecutionRequest,
    ExecutionResult,
    RunnerType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bridge() -> MagicMock:
    """Create a mock ConvexBridge with chat helper methods."""
    bridge = MagicMock()
    bridge.get_pending_chat_messages = MagicMock(return_value=[])
    bridge.send_chat_response = MagicMock()
    bridge.mark_chat_processing = MagicMock()
    bridge.mark_chat_done = MagicMock()
    bridge.query = MagicMock(return_value=None)
    bridge.mutation = MagicMock()
    return bridge


def _make_pending_msg(
    chat_id: str = "chat123",
    agent_name: str = "test-agent",
    content: str = "Hello!",
) -> dict:
    """Create a mock pending chat message dict (snake_case keys)."""
    return {
        "id": chat_id,
        "agent_name": agent_name,
        "author_name": "User",
        "author_type": "user",
        "content": content,
        "status": "pending",
        "timestamp": "2026-02-26T00:00:00Z",
    }


# ---------------------------------------------------------------------------
# Test: ChatHandler._process_chat_message — happy path
# ---------------------------------------------------------------------------


class TestProcessChatMessage:
    """Test the core message processing logic."""

    @pytest.mark.asyncio
    async def test_happy_path_sends_response_and_marks_done(self, tmp_path):
        """Process a pending message: mark processing, run engine, send response, mark done."""
        from mc.contexts.conversation.chat_handler import ChatHandler

        bridge = _make_bridge()
        handler = ChatHandler(bridge)
        msg = _make_pending_msg()

        # Set up agents dir
        agents_dir = tmp_path / "agents"
        config_dir = agents_dir / "test-agent"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text("name: test-agent")

        engine_result = ExecutionResult(
            success=True,
            output="Agent response here",
            session_id="sess-1",
        )

        mock_engine = MagicMock()
        mock_engine.run = AsyncMock(return_value=engine_result)

        with (
            patch(
                "mc.infrastructure.agents.yaml_validator.validate_agent_file",
                return_value=MagicMock(
                    prompt="Test prompt", model=None, skills=[],
                    display_name=None,
                ),
            ),
            patch(
                "mc.infrastructure.config.AGENTS_DIR",
                agents_dir,
            ),
            patch(
                "mc.contexts.conversation.chat_handler.ExecutionEngine",
                return_value=mock_engine,
            ),
        ):
            await handler._process_chat_message(msg)

        # Assertions: mark_chat_processing called with chat_id
        bridge.mark_chat_processing.assert_called_once_with("chat123")
        # mark_chat_done called
        bridge.mark_chat_done.assert_called_once_with("chat123")
        # send_chat_response called with agent name, result, and display name
        bridge.send_chat_response.assert_called_once()
        call_args = bridge.send_chat_response.call_args[0]
        assert call_args[0] == "test-agent"
        assert call_args[1] == "Agent response here"

    @pytest.mark.asyncio
    async def test_skips_message_without_id(self):
        """Messages without an id are skipped silently."""
        from mc.contexts.conversation.chat_handler import ChatHandler

        bridge = _make_bridge()
        handler = ChatHandler(bridge)
        msg = {"agent_name": "test-agent", "content": "Hello"}

        await handler._process_chat_message(msg)

        bridge.mark_chat_processing.assert_not_called()
        bridge.send_chat_response.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_message_without_agent_name(self):
        """Messages without an agent_name are skipped."""
        from mc.contexts.conversation.chat_handler import ChatHandler

        bridge = _make_bridge()
        handler = ChatHandler(bridge)
        msg = {"id": "chat123", "content": "Hello", "agent_name": ""}

        await handler._process_chat_message(msg)

        bridge.mark_chat_processing.assert_not_called()


# ---------------------------------------------------------------------------
# Test: Error handling
# ---------------------------------------------------------------------------


class TestProcessChatMessageErrors:
    """Test error handling during message processing."""

    @pytest.mark.asyncio
    async def test_error_marks_done_and_sends_error_response(self, tmp_path):
        """On processing error, mark original done and send error response."""
        from mc.contexts.conversation.chat_handler import ChatHandler

        bridge = _make_bridge()
        handler = ChatHandler(bridge)
        msg = _make_pending_msg()

        agents_dir = tmp_path / "agents"
        config_dir = agents_dir / "test-agent"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text("name: test-agent")

        engine_result = ExecutionResult(
            success=False,
            error_message="Engine execution failed",
        )

        mock_engine = MagicMock()
        mock_engine.run = AsyncMock(return_value=engine_result)

        with (
            patch(
                "mc.infrastructure.agents.yaml_validator.validate_agent_file",
                return_value=MagicMock(
                    prompt="Test prompt", model=None, skills=[],
                    display_name=None,
                ),
            ),
            patch(
                "mc.infrastructure.config.AGENTS_DIR",
                agents_dir,
            ),
            patch(
                "mc.contexts.conversation.chat_handler.ExecutionEngine",
                return_value=mock_engine,
            ),
        ):
            await handler._process_chat_message(msg)

        # Original should still be marked done (error recovery)
        bridge.mark_chat_done.assert_called_once_with("chat123")
        # Error response should be sent
        bridge.send_chat_response.assert_called_once()
        call_args = bridge.send_chat_response.call_args
        assert call_args[0][0] == "test-agent"
        assert "RuntimeError" in call_args[0][1]


# ---------------------------------------------------------------------------
# Test: Polling loop
# ---------------------------------------------------------------------------


class TestChatHandlerPollingLoop:
    """Test the polling loop behavior."""

    @pytest.mark.asyncio
    async def test_run_waits_for_sleep_controller_before_first_poll(self):
        """When the shared controller is sleeping, polling pauses until wake."""
        from mc.contexts.conversation.chat_handler import ChatHandler

        bridge = _make_bridge()

        gate = asyncio.Event()

        class SleepController:
            mode = "sleep"

            async def wait_for_next_cycle(self, _delay):
                await gate.wait()

            async def record_work_found(self):
                return None

            async def record_idle(self):
                return None

            def current_poll_interval(self, active_interval):
                return active_interval

        controller = SleepController()
        handler = ChatHandler(bridge, sleep_controller=controller)

        task = asyncio.create_task(handler.run())
        await asyncio.sleep(0.05)
        assert bridge.get_pending_chat_messages.call_count == 0

        controller.mode = "active"
        gate.set()

        for _ in range(20):
            if bridge.get_pending_chat_messages.call_count > 0:
                break
            await asyncio.sleep(0.01)

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert bridge.get_pending_chat_messages.call_count > 0

    @pytest.mark.asyncio
    async def test_run_polls_and_dispatches(self):
        """The run() loop polls for pending messages and processes them."""
        from mc.contexts.conversation.chat_handler import ChatHandler

        bridge = _make_bridge()
        handler = ChatHandler(bridge)

        msg = _make_pending_msg()
        call_count = 0
        processed = asyncio.Event()

        def fake_get_pending():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [msg]
            return []

        bridge.get_pending_chat_messages = fake_get_pending

        # Mock _process_chat_message to avoid the full agent processing
        original_process = handler._process_chat_message

        async def mock_process(m):
            processed.set()

        handler._process_chat_message = mock_process

        # Patch both polling intervals to 0 so the loop iterates fast
        with (
            patch("mc.contexts.conversation.chat_handler.ACTIVE_POLL_INTERVAL_SECONDS", 0),
            patch("mc.contexts.conversation.chat_handler.SLEEP_POLL_INTERVAL_SECONDS", 0),
        ):
            task = asyncio.create_task(handler.run())
            # Wait for processing to happen (with timeout)
            try:
                await asyncio.wait_for(processed.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                pass
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        assert processed.is_set()

    @pytest.mark.asyncio
    async def test_run_handles_poll_error_gracefully(self):
        """Errors during polling don't crash the loop."""
        from mc.contexts.conversation.chat_handler import ChatHandler

        bridge = _make_bridge()
        handler = ChatHandler(bridge)

        call_count = 0
        second_poll_done = asyncio.Event()

        def failing_get_pending():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Convex down")
            # Second call succeeds -- proves loop survived the error
            second_poll_done.set()
            return []

        bridge.get_pending_chat_messages = failing_get_pending

        with (
            patch("mc.contexts.conversation.chat_handler.ACTIVE_POLL_INTERVAL_SECONDS", 0),
            patch("mc.contexts.conversation.chat_handler.SLEEP_POLL_INTERVAL_SECONDS", 0),
        ):
            task = asyncio.create_task(handler.run())
            try:
                await asyncio.wait_for(second_poll_done.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                pass
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # The loop survived the error and polled again
        assert call_count >= 2

    @pytest.mark.asyncio
    async def test_run_publishes_sleep_runtime_on_start(self):
        """The handler publishes sleeping runtime metadata before polling."""
        from mc.contexts.conversation.chat_handler import ChatHandler

        bridge = _make_bridge()
        handler = ChatHandler(bridge)

        sleep_mock = AsyncMock(side_effect=asyncio.CancelledError)
        with patch("mc.contexts.conversation.chat_handler.asyncio.sleep", sleep_mock):
            with pytest.raises(asyncio.CancelledError):
                await handler.run()

        runtime_calls = [
            call.args
            for call in bridge.mutation.call_args_list
            if call.args and call.args[0] == "settings:set"
        ]
        assert runtime_calls, "Expected chat runtime to be persisted on startup"

        payload = json.loads(runtime_calls[0][1]["value"])
        assert runtime_calls[0][1]["key"] == "chat_handler_runtime"
        assert payload["mode"] == "sleep"
        assert payload["pollIntervalSeconds"] == 60
        assert payload["inFlight"] == 0

    @pytest.mark.asyncio
    async def test_run_ignores_remote_terminal_pending_messages(self):
        """Remote terminal chat messages do not wake or dispatch the chat poller."""
        from mc.contexts.conversation.chat_handler import ChatHandler

        bridge = _make_bridge()
        bridge.get_pending_chat_messages = MagicMock(
            return_value=[_make_pending_msg(agent_name="remote-agent")]
        )
        bridge.get_agent_by_name = MagicMock(
            return_value={"name": "remote-agent", "role": "remote-terminal"}
        )
        handler = ChatHandler(bridge)
        handler._process_chat_message = AsyncMock()

        sleep_mock = AsyncMock(side_effect=asyncio.CancelledError)
        with patch("mc.contexts.conversation.chat_handler.asyncio.sleep", sleep_mock):
            with pytest.raises(asyncio.CancelledError):
                await handler.run()

        handler._process_chat_message.assert_not_called()
        runtime_calls = [
            call.args
            for call in bridge.mutation.call_args_list
            if call.args and call.args[0] == "settings:set"
        ]
        payload = json.loads(runtime_calls[-1][1]["value"])
        assert payload["mode"] == "sleep"

    @pytest.mark.asyncio
    async def test_run_switches_to_active_for_non_remote_work_and_back_to_sleep(self):
        """Useful work wakes the handler and it sleeps again when the queue drains."""
        from mc.contexts.conversation.chat_handler import ChatHandler

        bridge = _make_bridge()
        msg = _make_pending_msg(agent_name="worker-agent")
        polls = [[msg], [], []]

        def get_pending():
            if polls:
                return polls.pop(0)
            return []

        bridge.get_pending_chat_messages = get_pending
        bridge.get_agent_by_name = MagicMock(
            return_value={"name": "worker-agent", "role": "developer"}
        )

        handler = ChatHandler(bridge)
        processed = asyncio.Event()

        async def mock_process(_msg):
            processed.set()

        handler._process_chat_message = mock_process

        real_sleep = asyncio.sleep
        sleep_calls = 0

        async def fake_sleep(_delay):
            nonlocal sleep_calls
            sleep_calls += 1
            await real_sleep(0)
            if sleep_calls >= 3:
                raise asyncio.CancelledError

        with patch(
            "mc.contexts.conversation.chat_handler.asyncio.sleep",
            new=AsyncMock(side_effect=fake_sleep),
        ):
            with pytest.raises(asyncio.CancelledError):
                await handler.run()

        assert processed.is_set()

        runtime_payloads = [
            json.loads(call.args[1]["value"])
            for call in bridge.mutation.call_args_list
            if call.args and call.args[0] == "settings:set"
        ]
        modes = [payload["mode"] for payload in runtime_payloads]
        assert modes[:3] == ["sleep", "active", "sleep"]


# ---------------------------------------------------------------------------
# Test: Bridge chat helpers
# ---------------------------------------------------------------------------


class TestBridgeChatHelpers:
    """Test that the bridge chat methods call the right Convex functions.

    After the bridge split (Story 15.3), methods delegate to ChatRepository
    via the adapter, which calls bridge.mutation() (not _mutation_with_retry).
    """

    @patch("mc.bridge.ConvexClient")
    def test_get_pending_chat_messages_calls_query(self, MockClient):
        """get_pending_chat_messages calls chats:listPending query."""
        from mc.bridge import ConvexBridge

        mock_client = MockClient.return_value
        mock_client.query.return_value = []

        bridge = ConvexBridge("https://test.convex.cloud")
        result = bridge.get_pending_chat_messages()

        mock_client.query.assert_called_with("chats:listPending", {})
        assert result == []

    @patch("mc.bridge.ConvexClient")
    def test_get_pending_returns_list_or_empty(self, MockClient):
        """get_pending_chat_messages returns empty list for None."""
        from mc.bridge import ConvexBridge

        mock_client = MockClient.return_value
        mock_client.query.return_value = None

        bridge = ConvexBridge("https://test.convex.cloud")
        result = bridge.get_pending_chat_messages()
        assert result == []

    @patch("mc.bridge.ConvexClient")
    def test_send_chat_response_calls_mutation(self, MockClient):
        """send_chat_response calls chats:send mutation."""
        from mc.bridge import ConvexBridge

        mock_client = MockClient.return_value
        mock_client.mutation.return_value = None

        bridge = ConvexBridge("https://test.convex.cloud")
        bridge.send_chat_response("my-agent", "Hello back!")

        mock_client.mutation.assert_called_once()
        call_args = mock_client.mutation.call_args[0]
        assert call_args[0] == "chats:send"
        payload = call_args[1]
        assert payload["agentName"] == "my-agent"
        assert payload["authorName"] == "my-agent"
        assert payload["authorType"] == "agent"
        assert payload["content"] == "Hello back!"
        assert payload["status"] == "done"

    @patch("mc.bridge.ConvexClient")
    def test_mark_chat_processing_calls_mutation(self, MockClient):
        """mark_chat_processing calls chats:updateStatus with processing."""
        from mc.bridge import ConvexBridge

        mock_client = MockClient.return_value
        mock_client.mutation.return_value = None

        bridge = ConvexBridge("https://test.convex.cloud")
        bridge.mark_chat_processing("chat456")

        mock_client.mutation.assert_called_once()
        call_args = mock_client.mutation.call_args[0]
        assert call_args[0] == "chats:updateStatus"
        assert call_args[1]["chatId"] == "chat456"
        assert call_args[1]["status"] == "processing"

    @patch("mc.bridge.ConvexClient")
    def test_mark_chat_done_calls_mutation(self, MockClient):
        """mark_chat_done calls chats:updateStatus with done."""
        from mc.bridge import ConvexBridge

        mock_client = MockClient.return_value
        mock_client.mutation.return_value = None

        bridge = ConvexBridge("https://test.convex.cloud")
        bridge.mark_chat_done("chat789")

        mock_client.mutation.assert_called_once()
        call_args = mock_client.mutation.call_args[0]
        assert call_args[0] == "chats:updateStatus"
        assert call_args[1]["chatId"] == "chat789"
        assert call_args[1]["status"] == "done"


# ---------------------------------------------------------------------------
# Test: CC model routing
# ---------------------------------------------------------------------------


class TestCCModelRouting:
    """Test that cc/ model prefix routes messages via CC runner through engine."""

    def _make_cc_bridge(self) -> MagicMock:
        bridge = _make_bridge()
        bridge.get_agent_by_name = MagicMock(return_value=None)
        return bridge

    def _make_validate_result(self, model: str) -> MagicMock:
        return MagicMock(
            prompt="Be helpful.",
            model=model,
            skills=[],
            display_name="CC Test Agent",
        )

    @pytest.mark.asyncio
    async def test_cc_model_routes_through_engine(self, tmp_path):
        """When model resolves to cc/*, route through ExecutionEngine."""
        from mc.contexts.conversation.chat_handler import ChatHandler

        bridge = self._make_cc_bridge()
        handler = ChatHandler(bridge)
        msg = _make_pending_msg(agent_name="cc-agent", content="Hello CC!")

        agents_dir = tmp_path / "agents"
        config_dir = agents_dir / "cc-agent"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(
            "name: cc-agent\nmodel: cc/claude-sonnet-4-6"
        )

        engine_result = ExecutionResult(
            success=True,
            output="CC response",
            session_id="sess-1",
            memory_workspace=tmp_path,
        )

        mock_engine = MagicMock()
        mock_engine.run = AsyncMock(return_value=engine_result)

        with (
            patch(
                "mc.infrastructure.agents.yaml_validator.validate_agent_file",
                return_value=self._make_validate_result("cc/claude-sonnet-4-6"),
            ),
            patch("mc.infrastructure.config.AGENTS_DIR", agents_dir),
            patch(
                "mc.contexts.conversation.chat_handler.ExecutionEngine",
                return_value=mock_engine,
            ),
        ):
            await handler._process_chat_message(msg)

        # ExecutionEngine.run() was called
        mock_engine.run.assert_called_once()

        # send_chat_response called with the CC response
        bridge.send_chat_response.assert_called_once()
        call_args = bridge.send_chat_response.call_args[0]
        assert call_args[0] == "cc-agent"
        assert call_args[1] == "CC response"

        # mark_chat_done called
        bridge.mark_chat_done.assert_called_once_with("chat123")

    @pytest.mark.asyncio
    async def test_cc_request_has_claude_code_runner_type(self, tmp_path):
        """CC chat request should have RunnerType.CLAUDE_CODE."""
        from mc.contexts.conversation.chat_handler import ChatHandler

        bridge = self._make_cc_bridge()
        handler = ChatHandler(bridge)
        msg = _make_pending_msg(agent_name="cc-agent", content="Check runner type")

        agents_dir = tmp_path / "agents"
        config_dir = agents_dir / "cc-agent"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(
            "name: cc-agent\nmodel: cc/claude-sonnet-4-6"
        )

        captured_requests: list[ExecutionRequest] = []

        async def capture_run(req):
            captured_requests.append(req)
            return ExecutionResult(
                success=True, output="done", memory_workspace=tmp_path
            )

        mock_engine = MagicMock()
        mock_engine.run = AsyncMock(side_effect=capture_run)

        with (
            patch(
                "mc.infrastructure.agents.yaml_validator.validate_agent_file",
                return_value=self._make_validate_result("cc/claude-sonnet-4-6"),
            ),
            patch("mc.infrastructure.config.AGENTS_DIR", agents_dir),
            patch(
                "mc.contexts.conversation.chat_handler.ExecutionEngine",
                return_value=mock_engine,
            ),
        ):
            await handler._process_chat_message(msg)

        assert len(captured_requests) == 1
        assert captured_requests[0].runner_type == RunnerType.CLAUDE_CODE

    @pytest.mark.asyncio
    async def test_non_cc_model_routes_through_nanobot_engine(self, tmp_path):
        """Non cc/ model goes through ExecutionEngine with NANOBOT runner."""
        from mc.contexts.conversation.chat_handler import ChatHandler

        bridge = self._make_cc_bridge()
        handler = ChatHandler(bridge)
        msg = _make_pending_msg(agent_name="gpt-agent", content="Hello GPT!")

        agents_dir = tmp_path / "agents"
        config_dir = agents_dir / "gpt-agent"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(
            "name: gpt-agent\nmodel: gpt-4"
        )

        engine_result = ExecutionResult(
            success=True,
            output="GPT response",
            session_id="nb-sess-1",
        )

        mock_engine = MagicMock()
        mock_engine.run = AsyncMock(return_value=engine_result)

        with (
            patch(
                "mc.infrastructure.agents.yaml_validator.validate_agent_file",
                return_value=self._make_validate_result("gpt-4"),
            ),
            patch("mc.infrastructure.config.AGENTS_DIR", agents_dir),
            patch(
                "mc.contexts.conversation.chat_handler.ExecutionEngine",
                return_value=mock_engine,
            ),
        ):
            await handler._process_chat_message(msg)

        # Engine was called
        mock_engine.run.assert_called_once()

        # Request has nanobot runner type
        req = mock_engine.run.call_args[0][0]
        assert req.runner_type == RunnerType.NANOBOT

        # Response sent
        bridge.send_chat_response.assert_called_once()
        call_args = bridge.send_chat_response.call_args[0]
        assert call_args[0] == "gpt-agent"
        assert call_args[1] == "GPT response"


MC_ROOT = Path(__file__).resolve().parent.parent.parent / "mc"


# ---------------------------------------------------------------------------
# Test: Architecture — chat_handler must not import mc.contexts.execution.executor (Story 20.1)
# ---------------------------------------------------------------------------


class TestChatHandlerArchitecture:
    """Verify chat_handler does not import mc.contexts.execution.executor directly."""

    def test_no_executor_imports(self) -> None:
        """chat_handler.py must not import from mc.contexts.execution.executor (AC4)."""
        filepath = MC_ROOT / "contexts" / "conversation" / "chat_handler.py"
        assert filepath.exists(), "chat_handler.py must exist"

        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
        executor_imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "mc.contexts.execution.executor" or alias.name.startswith(
                        "mc.contexts.execution.executor."
                    ):
                        executor_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and (
                    node.module == "mc.contexts.execution.executor"
                    or node.module.startswith("mc.contexts.execution.executor.")
                ):
                    executor_imports.append(node.module)
        assert executor_imports == [], (
            f"chat_handler.py imports from mc.contexts.execution.executor: {executor_imports}"
        )


# ---------------------------------------------------------------------------
# Test: Chat handler ExecutionEngine integration (Story 20.1, Task 4)
# ---------------------------------------------------------------------------


class TestChatHandlerEngineIntegration:
    """Verify chat_handler routes CC and nanobot execution through ExecutionEngine."""

    @pytest.mark.asyncio
    async def test_cc_chat_routes_through_engine(self, tmp_path):
        """CC-model chat messages should route through ExecutionEngine.run()."""
        from mc.contexts.conversation.chat_handler import ChatHandler

        bridge = _make_bridge()
        bridge.get_agent_by_name = MagicMock(return_value=None)
        handler = ChatHandler(bridge)
        msg = _make_pending_msg(agent_name="cc-agent", content="Hello via engine!")

        agents_dir = tmp_path / "agents"
        config_dir = agents_dir / "cc-agent"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(
            "name: cc-agent\nmodel: cc/claude-sonnet-4-6"
        )

        engine_result = ExecutionResult(
            success=True,
            output="Engine CC response",
            session_id="sess-engine-1",
            memory_workspace=tmp_path,
        )

        mock_engine = MagicMock()
        mock_engine.run = AsyncMock(return_value=engine_result)

        with (
            patch(
                "mc.infrastructure.agents.yaml_validator.validate_agent_file",
                return_value=MagicMock(
                    prompt="Be helpful.",
                    model="cc/claude-sonnet-4-6",
                    skills=[],
                    display_name="CC Test Agent",
                ),
            ),
            patch("mc.infrastructure.config.AGENTS_DIR", agents_dir),
            patch(
                "mc.contexts.conversation.chat_handler.ExecutionEngine",
                return_value=mock_engine,
            ),
        ):
            await handler._process_chat_message(msg)

        # ExecutionEngine.run() was called
        mock_engine.run.assert_called_once()

        # The request is correctly typed
        req = mock_engine.run.call_args[0][0]
        assert isinstance(req, ExecutionRequest)
        assert req.runner_type == RunnerType.CLAUDE_CODE
        assert req.agent_name == "cc-agent"

        # Response was sent
        bridge.send_chat_response.assert_called_once()
        call_args = bridge.send_chat_response.call_args[0]
        assert call_args[0] == "cc-agent"
        assert call_args[1] == "Engine CC response"

        # Message marked done
        bridge.mark_chat_done.assert_called_once_with("chat123")

    @pytest.mark.asyncio
    async def test_cc_chat_persists_session(self, tmp_path):
        """CC chat should persist session_id from engine result."""
        from mc.contexts.conversation.chat_handler import ChatHandler

        bridge = _make_bridge()
        bridge.get_agent_by_name = MagicMock(return_value=None)
        handler = ChatHandler(bridge)
        msg = _make_pending_msg(agent_name="cc-agent", content="Persist session")

        agents_dir = tmp_path / "agents"
        config_dir = agents_dir / "cc-agent"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(
            "name: cc-agent\nmodel: cc/claude-sonnet-4-6"
        )

        engine_result = ExecutionResult(
            success=True,
            output="Session response",
            session_id="new-session-id",
            memory_workspace=tmp_path,
        )

        mock_engine = MagicMock()
        mock_engine.run = AsyncMock(return_value=engine_result)

        with (
            patch(
                "mc.infrastructure.agents.yaml_validator.validate_agent_file",
                return_value=MagicMock(
                    prompt="Be helpful.",
                    model="cc/claude-sonnet-4-6",
                    skills=[],
                    display_name="CC Test Agent",
                ),
            ),
            patch("mc.infrastructure.config.AGENTS_DIR", agents_dir),
            patch(
                "mc.contexts.conversation.chat_handler.ExecutionEngine",
                return_value=mock_engine,
            ),
        ):
            await handler._process_chat_message(msg)

        # Session was persisted via bridge.mutation
        bridge.mutation.assert_called()
        mutation_call = bridge.mutation.call_args
        assert mutation_call[0][0] == "settings:set"
        assert mutation_call[0][1]["value"] == "new-session-id"

    @pytest.mark.asyncio
    async def test_nanobot_chat_routes_through_engine(self, tmp_path):
        """Non-CC model chat should route through ExecutionEngine with NANOBOT runner."""
        from mc.contexts.conversation.chat_handler import ChatHandler

        bridge = _make_bridge()
        bridge.get_agent_by_name = MagicMock(return_value=None)
        handler = ChatHandler(bridge)
        msg = _make_pending_msg(agent_name="nb-agent", content="Hello nanobot!")

        agents_dir = tmp_path / "agents"
        config_dir = agents_dir / "nb-agent"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(
            "name: nb-agent\nmodel: gpt-4"
        )

        engine_result = ExecutionResult(
            success=True,
            output="Nanobot response",
            session_id="nb-sess-1",
        )

        mock_engine = MagicMock()
        mock_engine.run = AsyncMock(return_value=engine_result)

        with (
            patch(
                "mc.infrastructure.agents.yaml_validator.validate_agent_file",
                return_value=MagicMock(
                    prompt="Be helpful.",
                    model="gpt-4",
                    skills=[],
                    display_name="NB Test Agent",
                ),
            ),
            patch("mc.infrastructure.config.AGENTS_DIR", agents_dir),
            patch(
                "mc.contexts.conversation.chat_handler.ExecutionEngine",
                return_value=mock_engine,
            ),
        ):
            await handler._process_chat_message(msg)

        # ExecutionEngine.run() was called
        mock_engine.run.assert_called_once()

        # The request has NANOBOT runner type
        req = mock_engine.run.call_args[0][0]
        assert isinstance(req, ExecutionRequest)
        assert req.runner_type == RunnerType.NANOBOT
        assert req.agent_name == "nb-agent"

        # Response was sent
        bridge.send_chat_response.assert_called_once()
        call_args = bridge.send_chat_response.call_args[0]
        assert call_args[0] == "nb-agent"
        assert call_args[1] == "Nanobot response"
