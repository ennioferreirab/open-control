"""Unit tests for ConvexBridge: case conversion, query/mutation/subscribe, retry logic."""

from unittest.mock import MagicMock, call, patch

import pytest

from nanobot.mc.bridge import (
    ConvexBridge,
    _convert_keys_to_camel,
    _convert_keys_to_snake,
    _to_camel_case,
    _to_snake_case,
)


# ── _to_camel_case tests ──────────────────────────────────────────────

class TestToCamelCase:
    def test_single_word(self):
        assert _to_camel_case("name") == "name"

    def test_two_words(self):
        assert _to_camel_case("assigned_agent") == "assignedAgent"

    def test_three_words(self):
        assert _to_camel_case("inter_agent_timeout") == "interAgentTimeout"

    def test_already_camel(self):
        # Single word that's already fine
        assert _to_camel_case("status") == "status"

    def test_task_id(self):
        assert _to_camel_case("task_id") == "taskId"

    def test_created_at(self):
        assert _to_camel_case("created_at") == "createdAt"

    def test_trust_level(self):
        assert _to_camel_case("trust_level") == "trustLevel"

    def test_display_name(self):
        assert _to_camel_case("display_name") == "displayName"

    def test_last_active_at(self):
        assert _to_camel_case("last_active_at") == "lastActiveAt"

    def test_empty_string(self):
        assert _to_camel_case("") == ""

    def test_preserves_convex_id(self):
        assert _to_camel_case("_id") == "_id"

    def test_preserves_convex_creation_time(self):
        assert _to_camel_case("_creationTime") == "_creationTime"


# ── _to_snake_case tests ──────────────────────────────────────────────

class TestToSnakeCase:
    def test_single_word(self):
        assert _to_snake_case("name") == "name"

    def test_two_words(self):
        assert _to_snake_case("assignedAgent") == "assigned_agent"

    def test_three_words(self):
        assert _to_snake_case("interAgentTimeout") == "inter_agent_timeout"

    def test_already_snake(self):
        assert _to_snake_case("status") == "status"

    def test_task_id(self):
        assert _to_snake_case("taskId") == "task_id"

    def test_created_at(self):
        assert _to_snake_case("createdAt") == "created_at"

    def test_trust_level(self):
        assert _to_snake_case("trustLevel") == "trust_level"

    def test_display_name(self):
        assert _to_snake_case("displayName") == "display_name"

    def test_last_active_at(self):
        assert _to_snake_case("lastActiveAt") == "last_active_at"

    def test_convex_id(self):
        assert _to_snake_case("_id") == "id"

    def test_convex_creation_time(self):
        assert _to_snake_case("_creationTime") == "creation_time"

    def test_empty_string(self):
        assert _to_snake_case("") == ""


# ── _convert_keys_to_camel tests ──────────────────────────────────────

class TestConvertKeysToCamel:
    def test_flat_dict(self):
        result = _convert_keys_to_camel({"assigned_agent": "bob", "trust_level": "autonomous"})
        assert result == {"assignedAgent": "bob", "trustLevel": "autonomous"}

    def test_nested_dict(self):
        data = {"task_data": {"assigned_agent": "bob", "created_at": "2026-01-01"}}
        result = _convert_keys_to_camel(data)
        assert result == {"taskData": {"assignedAgent": "bob", "createdAt": "2026-01-01"}}

    def test_list_of_dicts(self):
        data = [{"task_id": "1"}, {"task_id": "2"}]
        result = _convert_keys_to_camel(data)
        assert result == [{"taskId": "1"}, {"taskId": "2"}]

    def test_dict_with_list_of_dicts(self):
        data = {"items": [{"assigned_agent": "a"}, {"assigned_agent": "b"}]}
        result = _convert_keys_to_camel(data)
        assert result == {"items": [{"assignedAgent": "a"}, {"assignedAgent": "b"}]}

    def test_empty_dict(self):
        assert _convert_keys_to_camel({}) == {}

    def test_primitive_passthrough(self):
        assert _convert_keys_to_camel("hello") == "hello"
        assert _convert_keys_to_camel(42) == 42
        assert _convert_keys_to_camel(None) is None

    def test_values_not_converted(self):
        # String values like "in_progress" must NOT be converted
        result = _convert_keys_to_camel({"status": "in_progress"})
        assert result == {"status": "in_progress"}

    def test_list_of_strings_not_converted(self):
        result = _convert_keys_to_camel({"tags": ["my_tag", "another_tag"]})
        assert result == {"tags": ["my_tag", "another_tag"]}

    def test_preserves_underscore_prefixed_keys(self):
        """Convex system fields like _id and _creationTime are preserved outgoing."""
        result = _convert_keys_to_camel({"_id": "abc", "task_id": "xyz", "_creationTime": 12345})
        assert result == {"_id": "abc", "taskId": "xyz", "_creationTime": 12345}


# ── _convert_keys_to_snake tests ──────────────────────────────────────

class TestConvertKeysToSnake:
    def test_flat_dict(self):
        result = _convert_keys_to_snake({"assignedAgent": "bob", "trustLevel": "autonomous"})
        assert result == {"assigned_agent": "bob", "trust_level": "autonomous"}

    def test_nested_dict(self):
        data = {"taskData": {"assignedAgent": "bob", "createdAt": "2026-01-01"}}
        result = _convert_keys_to_snake(data)
        assert result == {"task_data": {"assigned_agent": "bob", "created_at": "2026-01-01"}}

    def test_list_of_dicts(self):
        data = [{"taskId": "1"}, {"taskId": "2"}]
        result = _convert_keys_to_snake(data)
        assert result == [{"task_id": "1"}, {"task_id": "2"}]

    def test_dict_with_list_of_dicts(self):
        data = {"items": [{"assignedAgent": "a"}, {"assignedAgent": "b"}]}
        result = _convert_keys_to_snake(data)
        assert result == {"items": [{"assigned_agent": "a"}, {"assigned_agent": "b"}]}

    def test_empty_dict(self):
        assert _convert_keys_to_snake({}) == {}

    def test_primitive_passthrough(self):
        assert _convert_keys_to_snake("hello") == "hello"
        assert _convert_keys_to_snake(42) == 42
        assert _convert_keys_to_snake(None) is None

    def test_convex_id_field(self):
        result = _convert_keys_to_snake({"_id": "abc123", "taskId": "xyz"})
        assert result == {"id": "abc123", "task_id": "xyz"}

    def test_convex_creation_time_field(self):
        result = _convert_keys_to_snake({"_creationTime": 1234567890, "_id": "abc"})
        assert result == {"creation_time": 1234567890, "id": "abc"}

    def test_values_not_converted(self):
        # camelCase string values must NOT be converted
        result = _convert_keys_to_snake({"authorName": "agentSmith"})
        assert result == {"author_name": "agentSmith"}


# ── ConvexBridge.query tests ──────────────────────────────────────────

class TestBridgeQuery:
    @patch("nanobot.mc.bridge.ConvexClient")
    def test_query_converts_result_keys(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.query.return_value = [
            {
                "_id": "abc",
                "taskId": "xyz",
                "assignedAgent": "financeiro",
                "createdAt": "2026-02-22T10:00:00Z",
            }
        ]

        bridge = ConvexBridge("https://test.convex.cloud")
        result = bridge.query("tasks:list")

        assert result[0]["id"] == "abc"
        assert result[0]["task_id"] == "xyz"
        assert result[0]["assigned_agent"] == "financeiro"
        assert result[0]["created_at"] == "2026-02-22T10:00:00Z"
        mock_client.query.assert_called_once_with("tasks:list", {})

    @patch("nanobot.mc.bridge.ConvexClient")
    def test_query_converts_arg_keys(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.query.return_value = []

        bridge = ConvexBridge("https://test.convex.cloud")
        bridge.query("messages:listByTask", {"task_id": "abc123"})

        mock_client.query.assert_called_once_with(
            "messages:listByTask", {"taskId": "abc123"}
        )

    @patch("nanobot.mc.bridge.ConvexClient")
    def test_query_with_no_args(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.query.return_value = []

        bridge = ConvexBridge("https://test.convex.cloud")
        result = bridge.query("tasks:list")

        assert result == []
        mock_client.query.assert_called_once_with("tasks:list", {})

    @patch("nanobot.mc.bridge.ConvexClient")
    def test_query_returns_none(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.query.return_value = None

        bridge = ConvexBridge("https://test.convex.cloud")
        result = bridge.query("settings:get", {"key": "taskTimeout"})

        assert result is None


# ── ConvexBridge.mutation tests ───────────────────────────────────────

class TestBridgeMutation:
    @patch("nanobot.mc.bridge.ConvexClient")
    def test_mutation_converts_arg_keys(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.mutation.return_value = "new_id_123"

        bridge = ConvexBridge("https://test.convex.cloud")
        result = bridge.mutation(
            "tasks:create",
            {
                "title": "Research AI",
                "status": "inbox",
                "trust_level": "autonomous",
                "created_at": "2026-02-22T10:00:00Z",
                "updated_at": "2026-02-22T10:00:00Z",
            },
        )

        call_args = mock_client.mutation.call_args[0]
        assert call_args[0] == "tasks:create"
        assert call_args[1]["trustLevel"] == "autonomous"
        assert call_args[1]["createdAt"] == "2026-02-22T10:00:00Z"
        # Status value "inbox" should NOT be key-converted
        assert call_args[1]["status"] == "inbox"

    @patch("nanobot.mc.bridge.ConvexClient")
    def test_mutation_with_no_args(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.mutation.return_value = None

        bridge = ConvexBridge("https://test.convex.cloud")
        result = bridge.mutation("system:reset")

        assert result is None
        mock_client.mutation.assert_called_once_with("system:reset", {})

    @patch("nanobot.mc.bridge.ConvexClient")
    def test_mutation_returns_dict_converted(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.mutation.return_value = {"_id": "abc", "createdAt": "2026-01-01"}

        bridge = ConvexBridge("https://test.convex.cloud")
        result = bridge.mutation("tasks:create", {"title": "Test"})

        assert result == {"id": "abc", "created_at": "2026-01-01"}


# ── ConvexBridge.subscribe tests ──────────────────────────────────────

class TestBridgeSubscribe:
    @patch("nanobot.mc.bridge.ConvexClient")
    def test_subscribe_converts_results(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.subscribe.return_value = iter([
            [{"_id": "1", "assignedAgent": "bob"}],
            [{"_id": "1", "assignedAgent": "alice"}],
        ])

        bridge = ConvexBridge("https://test.convex.cloud")
        results = list(bridge.subscribe("tasks:list"))

        assert len(results) == 2
        assert results[0][0]["id"] == "1"
        assert results[0][0]["assigned_agent"] == "bob"
        assert results[1][0]["assigned_agent"] == "alice"

    @patch("nanobot.mc.bridge.ConvexClient")
    def test_subscribe_converts_args(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.subscribe.return_value = iter([])

        bridge = ConvexBridge("https://test.convex.cloud")
        list(bridge.subscribe("messages:listByTask", {"task_id": "abc"}))

        mock_client.subscribe.assert_called_once_with(
            "messages:listByTask", {"taskId": "abc"}
        )


# ── ConvexBridge initialization tests ─────────────────────────────────

class TestBridgeInit:
    @patch("nanobot.mc.bridge.ConvexClient")
    def test_init_creates_client(self, MockClient):
        bridge = ConvexBridge("https://test.convex.cloud")
        MockClient.assert_called_once_with("https://test.convex.cloud")

    @patch("nanobot.mc.bridge.ConvexClient")
    def test_init_with_admin_key(self, MockClient):
        mock_client = MockClient.return_value
        bridge = ConvexBridge("https://test.convex.cloud", admin_key="secret123")
        mock_client.set_admin_auth.assert_called_once_with("secret123")

    @patch("nanobot.mc.bridge.ConvexClient")
    def test_init_without_admin_key(self, MockClient):
        mock_client = MockClient.return_value
        bridge = ConvexBridge("https://test.convex.cloud")
        mock_client.set_admin_auth.assert_not_called()

    @patch("nanobot.mc.bridge.ConvexClient")
    def test_close(self, MockClient):
        mock_client = MockClient.return_value
        bridge = ConvexBridge("https://test.convex.cloud")
        bridge.close()
        mock_client.close.assert_called_once()


# ── Edge case tests ───────────────────────────────────────────────────

class TestEdgeCases:
    @patch("nanobot.mc.bridge.ConvexClient")
    def test_query_with_empty_dict_args(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.query.return_value = []

        bridge = ConvexBridge("https://test.convex.cloud")
        bridge.query("tasks:list", {})

        mock_client.query.assert_called_once_with("tasks:list", {})

    @patch("nanobot.mc.bridge.time.sleep")
    @patch("nanobot.mc.bridge.ConvexClient")
    def test_error_propagation(self, MockClient, mock_sleep):
        from convex import ConvexError

        mock_client = MockClient.return_value
        mock_client.mutation.side_effect = ConvexError("test error", data="bad input")

        bridge = ConvexBridge("https://test.convex.cloud")
        with pytest.raises(ConvexError):
            bridge.mutation("tasks:create", {"title": "fail"})


# ── Retry logic tests (Story 1.4) ───────────────────────────────────

class TestMutationRetry:
    @patch("nanobot.mc.bridge.time.sleep")
    @patch("nanobot.mc.bridge.ConvexClient")
    def test_retry_succeeds_on_attempt_2(self, MockClient, mock_sleep):
        """Mutation fails once, succeeds on retry."""
        mock_client = MockClient.return_value
        mock_client.mutation.side_effect = [
            Exception("Connection timeout"),
            {"_id": "abc123"},
        ]

        bridge = ConvexBridge("https://test.convex.cloud")
        result = bridge.mutation("tasks:create", {"title": "Test"})

        assert mock_client.mutation.call_count == 2
        mock_sleep.assert_called_once_with(1)
        assert result == {"id": "abc123"}

    @patch("nanobot.mc.bridge.time.sleep")
    @patch("nanobot.mc.bridge.ConvexClient")
    def test_retry_succeeds_on_attempt_3(self, MockClient, mock_sleep):
        """Mutation fails twice, succeeds on third attempt."""
        mock_client = MockClient.return_value
        mock_client.mutation.side_effect = [
            Exception("Timeout"),
            Exception("Timeout again"),
            {"_id": "xyz"},
        ]

        bridge = ConvexBridge("https://test.convex.cloud")
        result = bridge.mutation("tasks:create", {"title": "Test"})

        assert mock_client.mutation.call_count == 3
        assert mock_sleep.call_args_list == [call(1), call(2)]
        assert result == {"id": "xyz"}

    @patch("nanobot.mc.bridge.time.sleep")
    @patch("nanobot.mc.bridge.ConvexClient")
    def test_retry_succeeds_on_attempt_4(self, MockClient, mock_sleep):
        """Mutation fails three times, succeeds on fourth (last) attempt."""
        mock_client = MockClient.return_value
        mock_client.mutation.side_effect = [
            Exception("Timeout 1"),
            Exception("Timeout 2"),
            Exception("Timeout 3"),
            {"_id": "recovered"},
        ]

        bridge = ConvexBridge("https://test.convex.cloud")
        result = bridge.mutation("tasks:create", {"title": "Test"})

        assert mock_client.mutation.call_count == 4
        assert mock_sleep.call_args_list == [call(1), call(2), call(4)]
        assert result == {"id": "recovered"}

    @patch("nanobot.mc.bridge.time.sleep")
    @patch("nanobot.mc.bridge.ConvexClient")
    def test_retry_exhaustion_raises(self, MockClient, mock_sleep):
        """All 4 attempts fail -- exception is re-raised."""
        mock_client = MockClient.return_value
        mock_client.mutation.side_effect = Exception("Convex unavailable")

        bridge = ConvexBridge("https://test.convex.cloud")
        with pytest.raises(Exception, match="Convex unavailable"):
            bridge.mutation("tasks:create", {"title": "Test"})

        # 4 mutation attempts + 1 best-effort error activity
        assert mock_client.mutation.call_count == 5

    @patch("nanobot.mc.bridge.time.sleep")
    @patch("nanobot.mc.bridge.ConvexClient")
    def test_retry_exhaustion_best_effort_activity(self, MockClient, mock_sleep):
        """On exhaustion, best-effort error activity is written to Convex."""
        mock_client = MockClient.return_value
        # First 4 calls fail (the mutation), 5th call succeeds (best-effort activity)
        mock_client.mutation.side_effect = [
            Exception("fail 1"),
            Exception("fail 2"),
            Exception("fail 3"),
            Exception("fail 4"),
            None,  # best-effort activity write succeeds
        ]

        bridge = ConvexBridge("https://test.convex.cloud")
        with pytest.raises(Exception, match="fail 4"):
            bridge.mutation("tasks:create", {"title": "Test"})

        # Check the best-effort activity call
        activity_call = mock_client.mutation.call_args_list[4]
        assert activity_call[0][0] == "activities:create"
        assert activity_call[0][1]["eventType"] == "system_error"
        assert "tasks:create" in activity_call[0][1]["description"]

    @patch("nanobot.mc.bridge.time.sleep")
    @patch("nanobot.mc.bridge.ConvexClient")
    def test_best_effort_activity_failure_silent(self, MockClient, mock_sleep):
        """Best-effort error activity write also fails -- no cascading exception."""
        mock_client = MockClient.return_value
        # All calls fail including the best-effort activity
        mock_client.mutation.side_effect = Exception("Total failure")

        bridge = ConvexBridge("https://test.convex.cloud")
        with pytest.raises(Exception, match="Total failure"):
            bridge.mutation("tasks:create", {"title": "Test"})

        # 4 retry attempts + 1 best-effort (also fails, silently caught)
        assert mock_client.mutation.call_count == 5

    @patch("nanobot.mc.bridge.time.sleep")
    @patch("nanobot.mc.bridge.ConvexClient")
    def test_exponential_backoff_timing(self, MockClient, mock_sleep):
        """Verify backoff delays: 1s, 2s, 4s per AC #1."""
        mock_client = MockClient.return_value
        mock_client.mutation.side_effect = Exception("fail")

        bridge = ConvexBridge("https://test.convex.cloud")
        with pytest.raises(Exception):
            bridge.mutation("tasks:create", {"title": "Test"})

        # Sleep called after attempt 1 (1s), attempt 2 (2s), attempt 3 (4s)
        # No sleep after attempt 4 (exhaustion)
        assert mock_sleep.call_args_list == [call(1), call(2), call(4)]

    @patch("nanobot.mc.bridge.time.sleep")
    @patch("nanobot.mc.bridge.ConvexClient")
    def test_successful_retry_no_error_activity(self, MockClient, mock_sleep):
        """When retry succeeds, no error activity event is written."""
        mock_client = MockClient.return_value
        mock_client.mutation.side_effect = [
            Exception("Temporary failure"),
            {"_id": "success"},
        ]

        bridge = ConvexBridge("https://test.convex.cloud")
        bridge.mutation("tasks:create", {"title": "Test"})

        # Only 2 calls: the failed attempt and the success -- no best-effort activity
        assert mock_client.mutation.call_count == 2

    @patch("nanobot.mc.bridge.ConvexClient")
    def test_query_not_retried(self, MockClient):
        """Query failures are NOT retried."""
        mock_client = MockClient.return_value
        mock_client.query.side_effect = Exception("Query failed")

        bridge = ConvexBridge("https://test.convex.cloud")
        with pytest.raises(Exception, match="Query failed"):
            bridge.query("tasks:list")

        assert mock_client.query.call_count == 1


# ── Dual logging tests (Story 1.4) ──────────────────────────────────

class TestDualLogging:
    @patch("nanobot.mc.bridge.time.sleep")
    @patch("nanobot.mc.bridge.ConvexClient")
    def test_retry_success_logs_attempt(self, MockClient, mock_sleep, caplog):
        """Successful retry logs which attempt succeeded."""
        mock_client = MockClient.return_value
        mock_client.mutation.side_effect = [
            Exception("Timeout"),
            {"_id": "ok"},
        ]

        import logging
        with caplog.at_level(logging.INFO, logger="nanobot.mc.bridge"):
            bridge = ConvexBridge("https://test.convex.cloud")
            bridge.mutation("tasks:create", {"title": "Test"})

        assert any("succeeded on attempt 2/4" in r.message for r in caplog.records)

    @patch("nanobot.mc.bridge.time.sleep")
    @patch("nanobot.mc.bridge.ConvexClient")
    def test_retry_failure_logs_error(self, MockClient, mock_sleep, caplog):
        """Retry exhaustion logs error with context."""
        mock_client = MockClient.return_value
        mock_client.mutation.side_effect = Exception("Network error")

        import logging
        with caplog.at_level(logging.ERROR, logger="nanobot.mc.bridge"):
            bridge = ConvexBridge("https://test.convex.cloud")
            with pytest.raises(Exception):
                bridge.mutation("tasks:create", {"title": "Test"})

        assert any("failed after 4 attempts" in r.message for r in caplog.records)

    @patch("nanobot.mc.bridge.time.sleep")
    @patch("nanobot.mc.bridge.ConvexClient")
    def test_state_transition_logging(self, MockClient, mock_sleep, caplog):
        """Convenience methods log state transitions with [MC] prefix."""
        mock_client = MockClient.return_value
        mock_client.mutation.return_value = None

        import logging
        with caplog.at_level(logging.INFO, logger="nanobot.mc.bridge"):
            bridge = ConvexBridge("https://test.convex.cloud")
            bridge.update_task_status("task123", "in_progress", agent_name="dev")

        assert any("[MC]" in r.message and "task" in r.message for r in caplog.records)


# ── Convenience method tests (Story 1.4) ─────────────────────────────

class TestConvenienceMethods:
    @patch("nanobot.mc.bridge.ConvexClient")
    def test_update_task_status(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.mutation.return_value = None

        bridge = ConvexBridge("https://test.convex.cloud")
        bridge.update_task_status("task123", "in_progress", agent_name="dev")

        call_args = mock_client.mutation.call_args[0]
        assert call_args[0] == "tasks:updateStatus"
        assert call_args[1]["taskId"] == "task123"
        assert call_args[1]["status"] == "in_progress"
        assert call_args[1]["agentName"] == "dev"

    @patch("nanobot.mc.bridge.ConvexClient")
    def test_update_agent_status(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.mutation.return_value = None

        bridge = ConvexBridge("https://test.convex.cloud")
        bridge.update_agent_status("financeiro", "active")

        call_args = mock_client.mutation.call_args[0]
        assert call_args[0] == "agents:updateStatus"
        assert call_args[1]["agentName"] == "financeiro"
        assert call_args[1]["status"] == "active"

    @patch("nanobot.mc.bridge.ConvexClient")
    def test_create_activity(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.mutation.return_value = None

        bridge = ConvexBridge("https://test.convex.cloud")
        bridge.create_activity(
            "task_created", "Task created", task_id="t1", agent_name="lead"
        )

        call_args = mock_client.mutation.call_args[0]
        assert call_args[0] == "activities:create"
        assert call_args[1]["eventType"] == "task_created"
        assert call_args[1]["description"] == "Task created"
        assert call_args[1]["taskId"] == "t1"
        assert call_args[1]["agentName"] == "lead"
        assert "timestamp" in call_args[1]

    @patch("nanobot.mc.bridge.ConvexClient")
    def test_send_message(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.mutation.return_value = None

        bridge = ConvexBridge("https://test.convex.cloud")
        bridge.send_message("t1", "dev", "agent", "Done!", "work")

        call_args = mock_client.mutation.call_args[0]
        assert call_args[0] == "messages:create"
        assert call_args[1]["taskId"] == "t1"
        assert call_args[1]["authorName"] == "dev"
        assert call_args[1]["authorType"] == "agent"
        assert call_args[1]["content"] == "Done!"
        assert call_args[1]["messageType"] == "work"
        assert "timestamp" in call_args[1]

    @patch("nanobot.mc.bridge.ConvexClient")
    def test_create_step(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.mutation.return_value = "step-123"

        bridge = ConvexBridge("https://test.convex.cloud")
        step_id = bridge.create_step({
            "task_id": "task-123",
            "title": "Run checks",
            "description": "Run validation checks",
            "assigned_agent": "general-agent",
            "blocked_by": [],
            "parallel_group": 1,
            "order": 1,
        })

        assert step_id == "step-123"
        call_args = mock_client.mutation.call_args[0]
        assert call_args[0] == "steps:create"
        assert call_args[1]["taskId"] == "task-123"
        assert call_args[1]["assignedAgent"] == "general-agent"
        assert call_args[1]["parallelGroup"] == 1

    @patch("nanobot.mc.bridge.ConvexClient")
    def test_batch_create_steps(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.mutation.return_value = ["step-1", "step-2"]

        bridge = ConvexBridge("https://test.convex.cloud")
        step_ids = bridge.batch_create_steps(
            "task-123",
            [
                {
                    "temp_id": "step_1",
                    "title": "First step",
                    "description": "Do first step",
                    "assigned_agent": "general-agent",
                    "blocked_by_temp_ids": [],
                    "parallel_group": 1,
                    "order": 1,
                },
                {
                    "temp_id": "step_2",
                    "title": "Second step",
                    "description": "Do second step",
                    "assigned_agent": "general-agent",
                    "blocked_by_temp_ids": ["step_1"],
                    "parallel_group": 2,
                    "order": 2,
                },
            ],
        )

        assert step_ids == ["step-1", "step-2"]
        call_args = mock_client.mutation.call_args[0]
        assert call_args[0] == "steps:batchCreate"
        assert call_args[1]["taskId"] == "task-123"
        assert call_args[1]["steps"][0]["tempId"] == "step_1"
        assert call_args[1]["steps"][1]["blockedByTempIds"] == ["step_1"]

    @patch("nanobot.mc.bridge.ConvexClient")
    def test_kick_off_task(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.mutation.return_value = None

        bridge = ConvexBridge("https://test.convex.cloud")
        bridge.kick_off_task("task-123", 3)

        call_args = mock_client.mutation.call_args[0]
        assert call_args[0] == "tasks:kickOff"
        assert call_args[1]["taskId"] == "task-123"
        assert call_args[1]["stepCount"] == 3

    @patch("nanobot.mc.bridge.ConvexClient")
    def test_update_step_status(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.mutation.return_value = None

        bridge = ConvexBridge("https://test.convex.cloud")
        bridge.update_step_status("step-123", "running")

        call_args = mock_client.mutation.call_args[0]
        assert call_args[0] == "steps:updateStatus"
        assert call_args[1]["stepId"] == "step-123"
        assert call_args[1]["status"] == "running"
        assert "errorMessage" not in call_args[1]

    @patch("nanobot.mc.bridge.ConvexClient")
    def test_get_steps_by_task(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.query.return_value = [{"_id": "step-123", "taskId": "task-123"}]

        bridge = ConvexBridge("https://test.convex.cloud")
        result = bridge.get_steps_by_task("task-123")

        assert result == [{"id": "step-123", "task_id": "task-123"}]
        mock_client.query.assert_called_once_with(
            "steps:getByTask", {"taskId": "task-123"}
        )

    @patch("nanobot.mc.bridge.ConvexClient")
    def test_check_and_unblock_dependents(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.mutation.return_value = ["step-2", "step-3"]

        bridge = ConvexBridge("https://test.convex.cloud")
        result = bridge.check_and_unblock_dependents("step-1")

        assert result == ["step-2", "step-3"]
        call_args = mock_client.mutation.call_args[0]
        assert call_args[0] == "steps:checkAndUnblockDependents"
        assert call_args[1]["stepId"] == "step-1"

    @patch("nanobot.mc.bridge.ConvexClient")
    def test_create_activity_optional_fields(self, MockClient):
        """Activity without task_id and agent_name omits those fields."""
        mock_client = MockClient.return_value
        mock_client.mutation.return_value = None

        bridge = ConvexBridge("https://test.convex.cloud")
        bridge.create_activity("system_error", "Something broke")

        call_args = mock_client.mutation.call_args[0]
        assert "taskId" not in call_args[1]
        assert "agentName" not in call_args[1]

    @patch("nanobot.mc.bridge.time.sleep")
    @patch("nanobot.mc.bridge.ConvexClient")
    def test_convenience_methods_use_retry(self, MockClient, mock_sleep):
        """Convenience methods retry on failure."""
        mock_client = MockClient.return_value
        mock_client.mutation.side_effect = [
            Exception("Temporary"),
            None,  # success on attempt 2
        ]

        bridge = ConvexBridge("https://test.convex.cloud")
        bridge.update_task_status("t1", "done")

        assert mock_client.mutation.call_count == 2
        mock_sleep.assert_called_once_with(1)
