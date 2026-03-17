"""Unit tests for mc.bridge.client module."""

from unittest.mock import patch

from mc.bridge.client import BridgeClient


class TestBridgeClientInit:
    @patch("mc.bridge.client.ConvexClient")
    def test_creates_client(self, MockClient):
        BridgeClient("https://test.convex.cloud")
        MockClient.assert_called_once_with("https://test.convex.cloud")

    @patch("mc.bridge.client.ConvexClient")
    def test_sets_admin_auth(self, MockClient):
        mock_client = MockClient.return_value
        BridgeClient("https://test.convex.cloud", admin_key="secret123")
        mock_client.set_admin_auth.assert_called_once_with("secret123")

    @patch("mc.bridge.client.ConvexClient")
    def test_no_admin_key(self, MockClient):
        mock_client = MockClient.return_value
        BridgeClient("https://test.convex.cloud")
        mock_client.set_admin_auth.assert_not_called()


class TestBridgeClientQuery:
    @patch("mc.bridge.client.ConvexClient")
    def test_query_converts_keys(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.query.return_value = [{"_id": "abc", "assignedAgent": "bob"}]

        client = BridgeClient("https://test.convex.cloud")
        result = client.query("tasks:list")

        assert result[0]["id"] == "abc"
        assert result[0]["assigned_agent"] == "bob"
        mock_client.query.assert_called_once_with("tasks:list", {})

    @patch("mc.bridge.client.ConvexClient")
    def test_query_converts_args(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.query.return_value = []

        client = BridgeClient("https://test.convex.cloud")
        client.query("messages:listByTask", {"task_id": "abc"})

        mock_client.query.assert_called_once_with("messages:listByTask", {"taskId": "abc"})


class TestBridgeClientMutation:
    @patch("mc.bridge.client.ConvexClient")
    def test_mutation_delegates_to_retry(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.mutation.return_value = "new_id"

        client = BridgeClient("https://test.convex.cloud")
        result = client.mutation("tasks:create", {"title": "Test"})

        assert result == "new_id"
        mock_client.mutation.assert_called_once()


class TestBridgeClientSubscribe:
    @patch("mc.bridge.client.ConvexClient")
    def test_subscribe_yields_converted_results(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.subscribe.return_value = iter(
            [
                [{"_id": "1", "assignedAgent": "bob"}],
            ]
        )

        client = BridgeClient("https://test.convex.cloud")
        results = list(client.subscribe("tasks:list"))

        assert len(results) == 1
        assert results[0][0]["id"] == "1"
        assert results[0][0]["assigned_agent"] == "bob"


class TestBridgeClientClose:
    @patch("mc.bridge.client.ConvexClient")
    def test_close(self, MockClient):
        mock_client = MockClient.return_value
        client = BridgeClient("https://test.convex.cloud")
        client.close()
        mock_client.close.assert_called_once()

    @patch("mc.bridge.client.ConvexClient")
    def test_raw_client_property(self, MockClient):
        mock_client = MockClient.return_value
        client = BridgeClient("https://test.convex.cloud")
        assert client.raw_client is mock_client
