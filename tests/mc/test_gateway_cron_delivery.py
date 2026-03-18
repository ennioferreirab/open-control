"""Tests for the on_cron_job delivery path inside run_gateway()."""

from __future__ import annotations

import asyncio
import os
import signal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from nanobot.cron.types import CronJob, CronPayload, CronSchedule


def _make_cron_job(
    *,
    deliver: bool = False,
    channel: str | None = None,
    to: str | None = None,
    task_id: str | None = None,
    message: str = "hello",
    agent: str | None = None,
) -> CronJob:
    """Helper to build a CronJob with the given payload fields."""
    return CronJob(
        id="job1",
        name="test-job",
        enabled=True,
        schedule=CronSchedule(kind="every", every_ms=60_000),
        payload=CronPayload(
            kind="agent_turn",
            message=message,
            deliver=deliver,
            channel=channel,
            to=to,
            task_id=task_id,
            agent=agent,
        ),
    )


async def _run_gateway_and_capture(captured: dict) -> None:
    """Run run_gateway() with all dependencies mocked, capture the on_job callback."""
    from mc.runtime.gateway import run_gateway

    # Build mock cron service that captures the on_job callback assignment
    mock_cron = MagicMock()
    mock_cron.start = AsyncMock()
    mock_cron.stop = MagicMock()
    mock_cron.status = MagicMock(return_value={"jobs": 0})

    def _set_on_job(fn):
        captured["on_job"] = fn

    type(mock_cron).on_job = property(
        fget=lambda self: captured.get("on_job"),
        fset=lambda self, fn: _set_on_job(fn),
    )
    mock_cron_cls = MagicMock(return_value=mock_cron)

    # Build mock bridge
    mock_bridge = MagicMock()
    mock_bridge.mutation = MagicMock(return_value=None)
    mock_bridge.query = MagicMock(return_value=None)
    captured["bridge"] = mock_bridge

    # Orchestrator mock
    mock_orch_instance = MagicMock()
    mock_orch_instance.start_routing_loop = AsyncMock()
    mock_orch_instance.start_review_routing_loop = AsyncMock()
    mock_orch_instance.start_kickoff_watch_loop = AsyncMock()
    mock_orch_instance.start_inbox_routing_loop = AsyncMock()

    # Timeout checker mock
    mock_tc_instance = MagicMock()
    mock_tc_instance.start = AsyncMock()

    # Executor mock — capture the on_task_completed callback
    mock_exec_instance = MagicMock()
    mock_exec_instance.start_execution_loop = AsyncMock()

    def _capture_executor(*args, **kwargs):
        captured["executor_kwargs"] = kwargs
        return mock_exec_instance

    mock_exec_cls = MagicMock(side_effect=_capture_executor)

    # Chat handler mock
    mock_chat_instance = MagicMock()
    mock_chat_instance.run = AsyncMock()

    # MentionWatcher mock
    mock_mention_instance = MagicMock()
    mock_mention_instance.run = AsyncMock()

    # AskUserReplyWatcher mock
    mock_ask_user_watcher = MagicMock()
    mock_ask_user_watcher.run = AsyncMock()

    # Interactive runtime mock — prevents real WebSocket server from binding port 8765
    mock_interactive_runtime = MagicMock()
    mock_interactive_runtime.service = MagicMock()
    mock_interactive_runtime.transport = MagicMock()
    mock_interactive_runtime.supervisor = MagicMock()
    mock_interactive_runtime.server.start = AsyncMock()
    mock_interactive_runtime.server.stop = AsyncMock()

    async def trigger_stop():
        await asyncio.sleep(0.05)
        os.kill(os.getpid(), signal.SIGTERM)

    stop_task = asyncio.create_task(trigger_stop())

    with (
        patch("mc.runtime.gateway.TaskOrchestrator", return_value=mock_orch_instance),
        patch("mc.runtime.gateway.TimeoutChecker", return_value=mock_tc_instance),
        patch("mc.contexts.execution.executor.TaskExecutor", mock_exec_cls),
        patch("mc.contexts.conversation.chat_handler.ChatHandler", return_value=mock_chat_instance),
        patch("nanobot.config.loader.load_config"),
        patch(
            "mc.contexts.conversation.mentions.watcher.MentionWatcher",
            return_value=mock_mention_instance,
        ),
        patch("nanobot.cron.service.CronService", mock_cron_cls),
        patch("mc.runtime.gateway._run_plan_negotiation_manager", new=AsyncMock()),
        patch(
            "mc.runtime.gateway.build_interactive_runtime",
            return_value=mock_interactive_runtime,
        ),
        patch(
            "mc.contexts.conversation.ask_user.watcher.AskUserReplyWatcher",
            return_value=mock_ask_user_watcher,
        ),
    ):
        try:
            await run_gateway(mock_bridge)
        except SystemExit:
            pass
        finally:
            stop_task.cancel()
            try:
                await stop_task
            except asyncio.CancelledError:
                pass


class TestOnCronJobDelivery:
    """Tests for the on_cron_job nested function inside run_gateway()."""

    @pytest.mark.asyncio
    async def test_cron_job_with_deliver_registers_pending_delivery(self):
        """Job with deliver=True, channel, and to → on_task_completed actually delivers."""
        captured: dict = {}
        await _run_gateway_and_capture(captured)

        on_job = captured.get("on_job")
        assert on_job is not None, "on_job callback was not captured"

        job = _make_cron_job(deliver=True, channel="telegram", to="123456", message="hi")
        captured["bridge"].mutation = MagicMock(return_value="task-reg-1")
        returned_task_id = await on_job(job)
        assert returned_task_id == "task-reg-1"

        on_task_completed = captured["executor_kwargs"].get("on_task_completed")
        assert on_task_completed is not None

        # Verify the delivery is actually registered: calling on_task_completed triggers send
        with (
            patch("nanobot.channels.telegram._markdown_to_telegram_html", side_effect=lambda x: x),
            patch("nanobot.channels.telegram._split_message", side_effect=lambda x: [x]),
            patch("telegram.Bot") as MockBot,
            patch("nanobot.config.loader.load_config") as mock_cfg,
        ):
            mock_cfg.return_value.channels.telegram.token = "tok"
            mock_bot = AsyncMock()
            MockBot.return_value = mock_bot
            await on_task_completed("task-reg-1", "result text")
            mock_bot.send_message.assert_called_once()
            assert mock_bot.send_message.call_args[1]["chat_id"] == 123456

    @pytest.mark.asyncio
    async def test_cron_job_deliver_skipped_when_task_fails(self):
        """When task creation raises, on_task_completed does NOT deliver (no pending entry)."""
        captured: dict = {}
        await _run_gateway_and_capture(captured)

        on_job = captured.get("on_job")
        assert on_job is not None

        # bridge.mutation raises → task_id is never returned → no entry in pending_deliveries
        captured["bridge"].mutation = MagicMock(side_effect=RuntimeError("db error"))

        job = _make_cron_job(deliver=True, channel="telegram", to="123456")
        await on_job(job)

        on_task_completed = captured["executor_kwargs"].get("on_task_completed")
        assert on_task_completed is not None

        # Calling on_task_completed with ANY task_id should NOT trigger delivery
        # because the failed mutation means no task_id was registered.
        with (
            patch("telegram.Bot") as MockBot,
            patch("nanobot.config.loader.load_config") as mock_cfg,
        ):
            mock_cfg.return_value.channels.telegram.token = "tok"
            mock_bot = AsyncMock()
            MockBot.return_value = mock_bot
            # Use a plausible task_id — it was never registered, so delivery must not happen
            await on_task_completed("any-task-id", "result text")
            mock_bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_cron_job_mc_channel_with_task_id_skips_delivery(self):
        """Job with channel='mc' and task_id set → on_task_completed does NOT deliver."""
        captured: dict = {}
        await _run_gateway_and_capture(captured)

        on_job = captured.get("on_job")
        assert on_job is not None

        # bridge.query returns a task so _requeue_cron_task can succeed
        captured["bridge"].query = MagicMock(
            return_value={"_id": "t1", "status": "idle", "assigned_agent": "nanobot"}
        )
        captured["bridge"].send_message = MagicMock()
        captured["bridge"].update_task_status = MagicMock()
        captured["bridge"].mutation = MagicMock(return_value="t1")

        job = _make_cron_job(deliver=True, channel="mc", to="t1", task_id="t1")
        await on_job(job)

        on_task_completed = captured["executor_kwargs"].get("on_task_completed")
        assert on_task_completed is not None

        # MC channel requeues tasks directly — no Telegram delivery should happen
        with (
            patch("telegram.Bot") as MockBot,
            patch("nanobot.config.loader.load_config") as mock_cfg,
        ):
            mock_cfg.return_value.channels.telegram.token = "tok"
            mock_bot = AsyncMock()
            MockBot.return_value = mock_bot
            await on_task_completed("t1", "result text")
            mock_bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_cron_job_deliver_false_skips_delivery(self):
        """Job with deliver=False → on_task_completed does NOT deliver."""
        captured: dict = {}
        await _run_gateway_and_capture(captured)

        on_job = captured.get("on_job")
        assert on_job is not None

        captured["bridge"].mutation = MagicMock(return_value="task-nodeliver")
        job = _make_cron_job(deliver=False, channel="telegram", to="123456")
        await on_job(job)

        on_task_completed = captured["executor_kwargs"].get("on_task_completed")
        assert on_task_completed is not None

        # deliver=False means no entry in pending_deliveries — send_message must not be called
        with (
            patch("telegram.Bot") as MockBot,
            patch("nanobot.config.loader.load_config") as mock_cfg,
        ):
            mock_cfg.return_value.channels.telegram.token = "tok"
            mock_bot = AsyncMock()
            MockBot.return_value = mock_bot
            await on_task_completed("task-nodeliver", "result text")
            mock_bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_cron_job_with_agent_passes_assigned_agent_to_task_create(self):
        """Job with agent set → tasks:create includes assigned_agent."""
        captured: dict = {}
        await _run_gateway_and_capture(captured)

        on_job = captured.get("on_job")
        assert on_job is not None

        job = _make_cron_job(agent="youtube-summarizer", message="summarize videos")
        returned_task_id = await on_job(job)
        assert returned_task_id is None

        create_calls = [
            call
            for call in captured["bridge"].mutation.call_args_list
            if call.args[0] == "tasks:create"
        ]
        assert len(create_calls) == 1
        create_args = create_calls[0].args[1]
        assert create_args["title"] == "summarize videos"
        assert create_args["assigned_agent"] == "youtube-summarizer"
        assert create_args["active_cron_job_id"] == "job1"

    @pytest.mark.asyncio
    async def test_cron_job_without_agent_creates_task_without_assigned_agent(self):
        """Job without agent → tasks:create has no assigned_agent key (backward compat)."""
        captured: dict = {}
        await _run_gateway_and_capture(captured)

        on_job = captured.get("on_job")
        assert on_job is not None

        job = _make_cron_job(message="do something")
        await on_job(job)

        create_calls = [
            call
            for call in captured["bridge"].mutation.call_args_list
            if call.args[0] == "tasks:create"
        ]
        assert len(create_calls) == 1
        create_args = create_calls[0].args[1]
        assert "assigned_agent" not in create_args
        assert create_args["active_cron_job_id"] == "job1"

    @pytest.mark.asyncio
    async def test_cron_job_requeue_fallback_with_agent(self):
        """When _requeue_cron_task can't find the task, fallback create includes agent."""
        captured: dict = {}
        await _run_gateway_and_capture(captured)

        on_job = captured.get("on_job")
        assert on_job is not None

        # bridge.query returns None → task not found → fallback to create
        captured["bridge"].query = MagicMock(return_value=None)

        job = _make_cron_job(task_id="old-task", agent="youtube-summarizer", message="summarize")
        await on_job(job)

        # Verify fallback task creation includes assigned_agent
        captured["bridge"].mutation.assert_called()
        call_args = captured["bridge"].mutation.call_args
        assert call_args[0][0] == "tasks:create"
        create_args = call_args[0][1]
        assert create_args.get("assigned_agent") == "youtube-summarizer"
        assert create_args["active_cron_job_id"] == "job1"

    @pytest.mark.asyncio
    async def test_cron_job_requeue_marks_active_cron_job_before_assignment(self):
        captured: dict = {}
        await _run_gateway_and_capture(captured)

        on_job = captured.get("on_job")
        assert on_job is not None

        captured["bridge"].query = MagicMock(
            return_value={"_id": "t1", "status": "done", "assigned_agent": "nanobot"}
        )
        captured["bridge"].mutation = MagicMock(return_value=None)
        captured["bridge"].send_message = MagicMock()
        captured["bridge"].update_task_status = MagicMock()

        job = _make_cron_job(task_id="t1", message="rerun")
        returned_task_id = await on_job(job)

        assert returned_task_id == "t1"
        captured["bridge"].mutation.assert_called_once_with(
            "tasks:markActiveCronJob",
            {"task_id": "t1", "cron_job_id": "job1"},
        )
        captured["bridge"].update_task_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_task_completed_delivers_when_result_non_empty(self):
        """on_task_completed sends to Telegram when result is non-empty."""
        captured: dict = {}
        await _run_gateway_and_capture(captured)

        on_job = captured.get("on_job")
        assert on_job is not None

        # Register a pending delivery
        job = _make_cron_job(deliver=True, channel="telegram", to="123456", message="summary")
        captured["bridge"].mutation = MagicMock(return_value="task-abc")
        await on_job(job)

        on_task_completed = captured["executor_kwargs"]["on_task_completed"]

        sent_messages: list[str] = []

        async def _fake_telegram(chat_id: str, content: str) -> None:
            sent_messages.append(content)

        with (
            patch("nanobot.channels.telegram._markdown_to_telegram_html", side_effect=lambda x: x),
            patch("nanobot.channels.telegram._split_message", side_effect=lambda x: [x]),
        ):
            # Directly test that on_task_completed calls _send_telegram_direct
            # by verifying it pops the pending delivery and sends the result.
            # We patch at the telegram Bot level to avoid real network calls.
            with patch("telegram.Bot") as MockBot:
                mock_bot_instance = AsyncMock()
                MockBot.return_value = mock_bot_instance
                mock_bot_instance.send_message = AsyncMock()

                with patch("nanobot.config.loader.load_config") as mock_cfg:
                    mock_cfg.return_value.channels.telegram.token = "fake-token"
                    await on_task_completed("task-abc", "YouTube summary result")

                mock_bot_instance.send_message.assert_called_once()
                call_kw = mock_bot_instance.send_message.call_args[1]
                assert call_kw["chat_id"] == 123456

    @pytest.mark.asyncio
    async def test_on_task_completed_skips_delivery_when_result_empty(self):
        """on_task_completed skips delivery when result is empty (agent failed)."""
        captured: dict = {}
        await _run_gateway_and_capture(captured)

        on_job = captured.get("on_job")
        assert on_job is not None

        job = _make_cron_job(deliver=True, channel="telegram", to="123456", message="summary")
        captured["bridge"].mutation = MagicMock(return_value="task-xyz")
        await on_job(job)

        on_task_completed = captured["executor_kwargs"]["on_task_completed"]

        with patch("telegram.Bot") as MockBot:
            mock_bot_instance = AsyncMock()
            MockBot.return_value = mock_bot_instance

            with patch("nanobot.config.loader.load_config") as mock_cfg:
                mock_cfg.return_value.channels.telegram.token = "fake-token"
                await on_task_completed("task-xyz", "")  # empty result

            mock_bot_instance.send_message.assert_not_called()


class TestProcessDirectReturnsContentWhenMessageToolUsed:
    """Regression tests for the empty-result bug in process_direct.

    When an MC agent calls the message() tool, _process_message returns None
    to avoid double-sending through the bus. Before the fix, process_direct
    returned "" (empty), causing on_task_completed to skip cron delivery.

    Fix: _process_message stores final_content in _last_turn_content, and
    process_direct falls back to it when response is None.
    """

    @pytest.mark.asyncio
    async def test_process_direct_returns_content_when_message_tool_used(self, tmp_path):
        """process_direct returns final_content even when MessageTool sent in turn."""
        from nanobot.agent.loop import AgentLoop
        from nanobot.agent.tools.message import MessageTool
        from nanobot.bus.queue import MessageBus

        bus = MessageBus()
        sent_messages: list = []

        async def _fake_send(msg):
            sent_messages.append(msg)

        # Minimal provider mock
        mock_provider = AsyncMock()
        mock_provider.chat = AsyncMock(return_value=("Hello from MC agent", []))

        loop = AgentLoop(
            bus=bus,
            provider=mock_provider,
            workspace=tmp_path / "agent",
            model="mock-model",
        )

        # Override MessageTool callback to capture sends
        if msg_tool := loop.tools.get("message"):
            if isinstance(msg_tool, MessageTool):
                msg_tool.set_send_callback(_fake_send)
                msg_tool.set_context(channel="telegram", chat_id="123456")

        # Patch _run_agent_loop to simulate agent using message tool
        async def _fake_agent_loop(messages, on_progress=None):
            # Simulate the agent calling message() tool
            if msg_tool := loop.tools.get("message"):
                if isinstance(msg_tool, MessageTool):
                    await msg_tool.execute("Hello from MC agent")
            return "Hello from MC agent", [], []

        loop._run_agent_loop = _fake_agent_loop

        result = await loop.process_direct(
            content="Send a test message",
            session_key="test:session",
            channel="mc",
            chat_id="test-agent",
            task_id="task-001",
        )

        # Before fix: result would be "" (empty)
        # After fix: result is the agent's final text content
        assert result == "Hello from MC agent", (
            f"process_direct returned empty string — fix broken. Got: {result!r}"
        )
        # MessageTool was indeed called
        assert len(sent_messages) == 1
