"""Unit tests for mc.bridge.retry module."""

from unittest.mock import MagicMock, call, patch

import pytest

from mc.bridge import ConvexBridge
from mc.bridge.retry import (
    BACKOFF_BASE_SECONDS,
    MAX_RETRIES,
    _write_error_activity,
    mutation_with_retry,
)


class TestMutationWithRetry:
    @patch("mc.bridge.retry.time.sleep")
    def test_succeeds_first_attempt(self, mock_sleep):
        """Mutation succeeds on first attempt -- no sleep."""
        client = MagicMock()
        client.mutation.return_value = {"_id": "abc"}

        result = mutation_with_retry(client, "tasks:create", {"title": "Test"})

        assert result == {"id": "abc"}
        assert client.mutation.call_count == 1
        mock_sleep.assert_not_called()

    @patch("mc.bridge.retry.time.sleep")
    def test_succeeds_on_retry(self, mock_sleep):
        """Mutation fails once, succeeds on second attempt."""
        client = MagicMock()
        client.mutation.side_effect = [Exception("Timeout"), {"_id": "ok"}]

        result = mutation_with_retry(client, "tasks:create", {"title": "Test"})

        assert result == {"id": "ok"}
        assert client.mutation.call_count == 2
        mock_sleep.assert_called_once_with(BACKOFF_BASE_SECONDS)

    @patch("mc.bridge.retry.time.sleep")
    def test_exhaustion_raises(self, mock_sleep):
        """All attempts fail -- raises last exception."""
        client = MagicMock()
        client.mutation.side_effect = Exception("Unavailable")

        with pytest.raises(Exception, match="Unavailable"):
            mutation_with_retry(client, "tasks:create", {"title": "Test"})

        # 4 mutation attempts + 1 best-effort error activity
        assert client.mutation.call_count == MAX_RETRIES + 1 + 1

    @patch("mc.bridge.retry.time.sleep")
    def test_exponential_backoff(self, mock_sleep):
        """Verify backoff delays: 1s, 2s, 4s."""
        client = MagicMock()
        client.mutation.side_effect = Exception("fail")

        with pytest.raises(Exception):
            mutation_with_retry(client, "tasks:create", {"title": "Test"})

        assert mock_sleep.call_args_list == [call(1), call(2), call(4)]

    @patch("mc.bridge.retry.time.sleep")
    def test_converts_snake_to_camel_args(self, mock_sleep):
        """Arguments are converted from snake_case to camelCase."""
        client = MagicMock()
        client.mutation.return_value = None

        mutation_with_retry(client, "tasks:create", {"task_id": "abc", "trust_level": "auto"})

        call_args = client.mutation.call_args[0]
        assert call_args[1]["taskId"] == "abc"
        assert call_args[1]["trustLevel"] == "auto"

    @patch("mc.bridge.retry.time.sleep")
    def test_none_result_not_converted(self, mock_sleep):
        """When mutation returns None, no conversion is attempted."""
        client = MagicMock()
        client.mutation.return_value = None

        result = mutation_with_retry(client, "system:reset")

        assert result is None

    @patch("mc.bridge.retry.time.sleep")
    def test_generates_and_reuses_idempotency_key_for_message_retries(self, mock_sleep):
        """Supported write mutations should get one stable key across retry attempts."""
        client = MagicMock()
        client.mutation.side_effect = [Exception("Timeout"), {"_id": "ok"}]

        mutation_with_retry(
            client,
            "messages:create",
            {
                "task_id": "task-1",
                "author_name": "bot",
                "author_type": "agent",
                "content": "hello",
                "message_type": "work",
                "timestamp": "2026-03-16T12:00:00.000Z",
            },
        )

        first_args = client.mutation.call_args_list[0].args[1]
        second_args = client.mutation.call_args_list[1].args[1]
        assert first_args["idempotencyKey"] == second_args["idempotencyKey"]
        assert first_args["idempotencyKey"].startswith("messages:create:")


class TestBridgeMutationWithRetry:
    @patch("mc.bridge.time.sleep")
    def test_reuses_existing_idempotency_key_across_bridge_retries(self, mock_sleep):
        """Bridge retry should keep a caller-supplied key stable on every attempt."""
        bridge = object.__new__(ConvexBridge)
        bridge._client = MagicMock()
        bridge._client.mutation.side_effect = [Exception("Timeout"), {"_id": "ok"}]
        bridge._write_error_activity = MagicMock()

        result = bridge._mutation_with_retry(
            "tasks:transition",
            {
                "task_id": "task-1",
                "from_status": "in_progress",
                "expected_state_version": 3,
                "to_status": "review",
                "reason": "done",
                "idempotency_key": "py:task-1:v3:in_progress:review:none:none:none",
            },
        )

        assert result == {"id": "ok"}
        first_args = bridge._client.mutation.call_args_list[0].args[1]
        second_args = bridge._client.mutation.call_args_list[1].args[1]
        assert first_args["idempotencyKey"] == second_args["idempotencyKey"]
        assert first_args["idempotencyKey"] == "py:task-1:v3:in_progress:review:none:none:none"


class TestWriteErrorActivity:
    def test_writes_activity_on_exhaustion(self):
        """Best-effort activity is written to Convex."""
        client = MagicMock()
        client.mutation.return_value = None

        _write_error_activity(client, "tasks:create", "Network error")

        call_args = client.mutation.call_args[0]
        assert call_args[0] == "activities:create"
        assert call_args[1]["eventType"] == "system_error"
        assert "tasks:create" in call_args[1]["description"]
        assert "Network error" in call_args[1]["description"]

    def test_silent_on_failure(self):
        """If writing activity fails, no exception propagates."""
        client = MagicMock()
        client.mutation.side_effect = Exception("Also broken")

        # Should not raise
        _write_error_activity(client, "tasks:create", "Original error")


class TestConstants:
    def test_max_retries_value(self):
        assert MAX_RETRIES == 3

    def test_backoff_base_value(self):
        assert BACKOFF_BASE_SECONDS == 1
