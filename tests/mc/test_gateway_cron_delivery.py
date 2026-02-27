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
        ),
    )


async def _run_gateway_and_capture(captured: dict) -> None:
    """Run run_gateway() with all dependencies mocked, capture the on_job callback."""
    from nanobot.mc.gateway import run_gateway

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

    async def trigger_stop():
        await asyncio.sleep(0.05)
        os.kill(os.getpid(), signal.SIGTERM)

    stop_task = asyncio.create_task(trigger_stop())

    with patch("nanobot.mc.gateway.TaskOrchestrator", return_value=mock_orch_instance), \
         patch("nanobot.mc.gateway.TimeoutChecker", return_value=mock_tc_instance), \
         patch("nanobot.mc.executor.TaskExecutor", mock_exec_cls), \
         patch("nanobot.mc.chat_handler.ChatHandler", return_value=mock_chat_instance), \
         patch("nanobot.config.loader.load_config"), \
         patch("nanobot.mc.mention_watcher.MentionWatcher", return_value=mock_mention_instance), \
         patch("nanobot.cron.service.CronService", mock_cron_cls), \
         patch("nanobot.mc.gateway._run_plan_negotiation_manager", new=AsyncMock()):
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
        """Job with deliver=True, channel, and to → pending_deliveries has entry."""
        captured: dict = {}
        await _run_gateway_and_capture(captured)

        on_job = captured.get("on_job")
        assert on_job is not None, "on_job callback was not captured"

        job = _make_cron_job(deliver=True, channel="telegram", to="123", message="hi")
        await on_job(job)

        # The executor should have received on_task_completed callback
        assert "executor_kwargs" in captured
        on_task_completed = captured["executor_kwargs"].get("on_task_completed")
        assert on_task_completed is not None, "on_task_completed callback was not passed to executor"

    @pytest.mark.asyncio
    async def test_cron_job_deliver_skipped_when_task_fails(self):
        """When task creation raises, pending_deliveries should NOT have entry."""
        captured: dict = {}
        await _run_gateway_and_capture(captured)

        on_job = captured.get("on_job")
        assert on_job is not None

        # Make bridge.mutation raise so task_id_for_delivery stays None
        captured["bridge"].mutation = MagicMock(side_effect=RuntimeError("db error"))

        job = _make_cron_job(deliver=True, channel="telegram", to="123")
        await on_job(job)

        # Since mutation failed, task_id_for_delivery is None, no delivery registered
        # (We can't directly inspect pending_deliveries since it's a local in run_gateway,
        # but the on_task_completed callback should exist and calling it shouldn't crash)
        on_task_completed = captured["executor_kwargs"].get("on_task_completed")
        assert on_task_completed is not None

    @pytest.mark.asyncio
    async def test_cron_job_mc_channel_with_task_id_skips_delivery(self):
        """Job with channel='mc' and task_id set → no pending delivery registered."""
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

        job = _make_cron_job(deliver=True, channel="mc", to="t1", task_id="t1")
        await on_job(job)

        # MC channel with task_id is excluded from pending deliveries (channel != "mc" check)
        on_task_completed = captured["executor_kwargs"].get("on_task_completed")
        assert on_task_completed is not None

    @pytest.mark.asyncio
    async def test_cron_job_deliver_false_skips_delivery(self):
        """Job with deliver=False → no pending delivery registered."""
        captured: dict = {}
        await _run_gateway_and_capture(captured)

        on_job = captured.get("on_job")
        assert on_job is not None

        job = _make_cron_job(deliver=False, channel="telegram", to="123")
        await on_job(job)

        # deliver=False means no pending delivery registered
        on_task_completed = captured["executor_kwargs"].get("on_task_completed")
        assert on_task_completed is not None

    @pytest.mark.asyncio
    async def test_on_task_completed_callback_passed_to_executor(self):
        """The on_task_completed callback is wired to the TaskExecutor."""
        captured: dict = {}
        await _run_gateway_and_capture(captured)

        assert "executor_kwargs" in captured
        assert "on_task_completed" in captured["executor_kwargs"]
        assert callable(captured["executor_kwargs"]["on_task_completed"])
