"""Unit tests for mc.bridge.retry module."""

from unittest.mock import MagicMock, call, patch

import pytest

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

        with pytest.raises(Exception, match="fail"):
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
