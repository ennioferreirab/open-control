"""Unit tests for mc.bridge.subscriptions module."""

import asyncio
from unittest.mock import MagicMock

import pytest

from mc.bridge.subscriptions import SubscriptionManager


class TestSubscriptionManager:
    def test_subscribe_yields_converted_results(self):
        """subscribe() converts camelCase keys to snake_case."""
        client = MagicMock()
        client.raw_client.subscribe.return_value = iter(
            [
                [{"_id": "1", "assignedAgent": "bob"}],
                [{"_id": "1", "assignedAgent": "alice"}],
            ]
        )

        manager = SubscriptionManager(client)
        results = list(manager.subscribe("tasks:list"))

        assert len(results) == 2
        assert results[0][0]["id"] == "1"
        assert results[0][0]["assigned_agent"] == "bob"
        assert results[1][0]["assigned_agent"] == "alice"

    def test_subscribe_converts_args(self):
        """subscribe() converts snake_case args to camelCase."""
        client = MagicMock()
        client.raw_client.subscribe.return_value = iter([])

        manager = SubscriptionManager(client)
        list(manager.subscribe("messages:listByTask", {"task_id": "abc"}))

        client.raw_client.subscribe.assert_called_once_with(
            "messages:listByTask", {"taskId": "abc"}
        )

    def test_subscribe_empty(self):
        """subscribe() handles empty result."""
        client = MagicMock()
        client.raw_client.subscribe.return_value = iter([])

        manager = SubscriptionManager(client)
        results = list(manager.subscribe("tasks:list"))
        assert results == []

    @pytest.mark.asyncio
    async def test_async_subscribe_waits_while_controller_is_sleeping(self):
        """Polling should stay paused during sleep and resume immediately on wake."""
        from mc.runtime.sleep_controller import RuntimeSleepController

        client = MagicMock()
        client.query = MagicMock(return_value=[{"id": "task_1"}])

        controller = RuntimeSleepController(client)
        await controller.initialize()
        await controller.apply_manual_mode("sleep")

        manager = SubscriptionManager(client)
        queue = manager.async_subscribe(
            "tasks:list",
            poll_interval=0.01,
            sleep_controller=controller,
        )

        await asyncio.sleep(0.05)
        assert client.query.call_count == 0
        assert queue.empty()

        await controller.apply_manual_mode("active")
        result = await asyncio.wait_for(queue.get(), timeout=1.0)

        assert result == [{"id": "task_1"}]
        assert client.query.call_count >= 1

    @pytest.mark.asyncio
    async def test_non_empty_sleep_sync_wakes_controller(self):
        """A non-empty poll result during sleep should wake the shared controller."""
        from mc.runtime.sleep_controller import RuntimeSleepController

        client = MagicMock()
        client.query = MagicMock(return_value=[{"id": "task_1"}])

        controller = RuntimeSleepController(
            client,
            sleep_poll_interval_seconds=0.01,
        )
        await controller.initialize()
        await controller.apply_manual_mode("sleep")

        manager = SubscriptionManager(client)
        queue = manager.async_subscribe(
            "tasks:list",
            poll_interval=0.01,
            sleep_controller=controller,
        )

        result = await asyncio.wait_for(queue.get(), timeout=1.0)

        assert result == [{"id": "task_1"}]
        assert controller.mode == "active"
