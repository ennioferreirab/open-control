"""Unit tests for mc.bridge.subscriptions module."""

from unittest.mock import MagicMock

from mc.bridge.subscriptions import SubscriptionManager


class TestSubscriptionManager:
    def test_subscribe_yields_converted_results(self):
        """subscribe() converts camelCase keys to snake_case."""
        client = MagicMock()
        client.raw_client.subscribe.return_value = iter([
            [{"_id": "1", "assignedAgent": "bob"}],
            [{"_id": "1", "assignedAgent": "alice"}],
        ])

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
