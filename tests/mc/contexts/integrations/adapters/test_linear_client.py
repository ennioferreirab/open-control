"""Tests for the Linear GraphQL client."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from mc.contexts.integrations.adapters.linear_client import (
    LINEAR_API_ENDPOINT,
    LinearAPIError,
    LinearGraphQLClient,
)


def _make_transport(responses: list[httpx.Response]) -> httpx.MockTransport:
    """Return a MockTransport that serves responses in order."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        response = responses[min(call_count, len(responses) - 1)]
        call_count += 1
        return response

    return httpx.MockTransport(handler)


def _json_response(data: dict[str, Any], status_code: int = 200) -> httpx.Response:
    """Build an httpx.Response with JSON body."""
    return httpx.Response(
        status_code=status_code,
        headers={"Content-Type": "application/json"},
        content=json.dumps(data).encode(),
    )


def _make_client(transport: httpx.MockTransport) -> LinearGraphQLClient:
    """Construct a LinearGraphQLClient using the given mock transport."""
    client = LinearGraphQLClient(api_key="lin_api_test_key")
    # Replace the internal http client with one using the mock transport
    client._http = httpx.AsyncClient(
        base_url=LINEAR_API_ENDPOINT,
        headers={
            "Authorization": "lin_api_test_key",
            "Content-Type": "application/json",
        },
        transport=transport,
    )
    return client


class TestExecuteSuccess:
    """Successful GraphQL execution returns parsed data."""

    async def test_execute_success(self) -> None:
        response_body = {"data": {"viewer": {"id": "user-1", "name": "Alice"}}}
        transport = _make_transport([_json_response(response_body)])
        client = _make_client(transport)

        with patch("asyncio.sleep"):
            result = await client.execute("query { viewer { id name } }")

        assert result == {"viewer": {"id": "user-1", "name": "Alice"}}
        await client.close()

    async def test_execute_with_variables(self) -> None:
        response_body = {"data": {"issue": {"id": "issue-1", "title": "Test"}}}
        transport = _make_transport([_json_response(response_body)])
        client = _make_client(transport)

        with patch("asyncio.sleep"):
            result = await client.execute(
                "query GetIssue($id: String!) { issue(id: $id) { id } }", {"id": "issue-1"}
            )

        assert result == {"issue": {"id": "issue-1", "title": "Test"}}
        await client.close()

    async def test_execute_empty_data(self) -> None:
        response_body = {"data": {}}
        transport = _make_transport([_json_response(response_body)])
        client = _make_client(transport)

        with patch("asyncio.sleep"):
            result = await client.execute("query { viewer { id } }")

        assert result == {}
        await client.close()


class TestExecuteGraphQLErrors:
    """GraphQL error responses raise LinearAPIError."""

    async def test_single_error_raises(self) -> None:
        response_body = {
            "errors": [{"message": "Entity not found: Issue"}],
        }
        transport = _make_transport([_json_response(response_body)])
        client = _make_client(transport)

        with patch("asyncio.sleep"), pytest.raises(LinearAPIError) as exc_info:
            await client.execute('query { issue(id: "bad") { id } }')

        assert "Entity not found: Issue" in exc_info.value.message
        assert len(exc_info.value.errors) == 1
        await client.close()

    async def test_multiple_errors_joined(self) -> None:
        response_body = {
            "errors": [
                {"message": "First error"},
                {"message": "Second error"},
            ],
        }
        transport = _make_transport([_json_response(response_body)])
        client = _make_client(transport)

        with patch("asyncio.sleep"), pytest.raises(LinearAPIError) as exc_info:
            await client.execute("query { viewer { id } }")

        assert "First error" in exc_info.value.message
        assert "Second error" in exc_info.value.message
        assert len(exc_info.value.errors) == 2
        await client.close()

    async def test_error_without_message_field(self) -> None:
        response_body = {"errors": [{}]}
        transport = _make_transport([_json_response(response_body)])
        client = _make_client(transport)

        with patch("asyncio.sleep"), pytest.raises(LinearAPIError) as exc_info:
            await client.execute("query { viewer { id } }")

        assert "Unknown error" in exc_info.value.message
        await client.close()


class TestExecuteRateLimitRetry:
    """429 responses trigger retry with Retry-After header."""

    async def test_rate_limit_then_success(self) -> None:
        rate_limit_response = httpx.Response(
            status_code=429,
            headers={"Retry-After": "0.01"},
            content=b"",
        )
        success_response = _json_response({"data": {"viewer": {"id": "u1"}}})
        transport = _make_transport([rate_limit_response, success_response])
        client = _make_client(transport)

        sleep_calls: list[float] = []

        async def capture_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with patch(
            "mc.contexts.integrations.adapters.linear_client.asyncio.sleep",
            side_effect=capture_sleep,
        ):
            result = await client.execute("query { viewer { id } }")

        assert result == {"viewer": {"id": "u1"}}
        assert len(sleep_calls) == 1
        assert sleep_calls[0] == pytest.approx(0.01)
        await client.close()

    async def test_rate_limit_uses_backoff_when_no_retry_after_header(self) -> None:
        rate_limit_response = httpx.Response(
            status_code=429,
            content=b"",
        )
        success_response = _json_response({"data": {"viewer": {"id": "u1"}}})
        transport = _make_transport([rate_limit_response, success_response])
        client = _make_client(transport)

        sleep_calls: list[float] = []

        async def capture_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with patch(
            "mc.contexts.integrations.adapters.linear_client.asyncio.sleep",
            side_effect=capture_sleep,
        ):
            result = await client.execute("query { viewer { id } }")

        assert result == {"viewer": {"id": "u1"}}
        assert len(sleep_calls) == 1
        # First attempt backoff = 1.0 * 2^0 = 1.0
        assert sleep_calls[0] == pytest.approx(1.0)
        await client.close()


class TestExecuteServerErrorRetry:
    """5xx responses trigger exponential backoff retry."""

    async def test_server_error_then_success(self) -> None:
        server_error = _json_response({}, status_code=500)
        success_response = _json_response({"data": {"viewer": {"id": "u1"}}})
        transport = _make_transport([server_error, success_response])
        client = _make_client(transport)

        sleep_calls: list[float] = []

        async def capture_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with patch(
            "mc.contexts.integrations.adapters.linear_client.asyncio.sleep",
            side_effect=capture_sleep,
        ):
            result = await client.execute("query { viewer { id } }")

        assert result == {"viewer": {"id": "u1"}}
        assert len(sleep_calls) == 1
        assert sleep_calls[0] == pytest.approx(1.0)
        await client.close()

    async def test_backoff_doubles_on_second_retry(self) -> None:
        server_error_1 = _json_response({}, status_code=503)
        server_error_2 = _json_response({}, status_code=503)
        success = _json_response({"data": {"ok": True}})
        transport = _make_transport([server_error_1, server_error_2, success])
        client = _make_client(transport)

        sleep_calls: list[float] = []

        async def capture_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with patch(
            "mc.contexts.integrations.adapters.linear_client.asyncio.sleep",
            side_effect=capture_sleep,
        ):
            result = await client.execute("query { viewer { id } }")

        assert result == {"ok": True}
        assert len(sleep_calls) == 2
        assert sleep_calls[0] == pytest.approx(1.0)
        assert sleep_calls[1] == pytest.approx(2.0)
        await client.close()


class TestExecuteAllRetriesExhausted:
    """All retries exhausted raises the final error."""

    async def test_three_server_errors_raises(self) -> None:
        server_errors = [_json_response({}, status_code=500)] * 3
        transport = _make_transport(server_errors)
        client = _make_client(transport)

        with patch("mc.contexts.integrations.adapters.linear_client.asyncio.sleep"):
            with pytest.raises(RuntimeError, match="Linear API request failed after retries"):
                await client.execute("query { viewer { id } }")

        await client.close()

    async def test_three_rate_limits_raises(self) -> None:
        rate_limit = httpx.Response(status_code=429, content=b"")
        transport = _make_transport([rate_limit] * 3)
        client = _make_client(transport)

        with patch("mc.contexts.integrations.adapters.linear_client.asyncio.sleep"):
            with pytest.raises(RuntimeError, match="Linear API request failed after retries"):
                await client.execute("query { viewer { id } }")

        await client.close()


class TestExecuteConnectionErrorRetry:
    """Network connection errors trigger retry."""

    async def test_connection_error_then_success(self) -> None:
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.ConnectError("Connection refused")
            return _json_response({"data": {"viewer": {"id": "u1"}}})

        transport = httpx.MockTransport(handler)
        client = _make_client(transport)

        sleep_calls: list[float] = []

        async def capture_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with patch(
            "mc.contexts.integrations.adapters.linear_client.asyncio.sleep",
            side_effect=capture_sleep,
        ):
            result = await client.execute("query { viewer { id } }")

        assert result == {"viewer": {"id": "u1"}}
        assert len(sleep_calls) == 1
        await client.close()

    async def test_all_connection_errors_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        transport = httpx.MockTransport(handler)
        client = _make_client(transport)

        with patch("mc.contexts.integrations.adapters.linear_client.asyncio.sleep"):
            with pytest.raises(httpx.ConnectError):
                await client.execute("query { viewer { id } }")

        await client.close()

    async def test_timeout_then_success(self) -> None:
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.TimeoutException("Request timed out")
            return _json_response({"data": {"viewer": {"id": "u1"}}})

        transport = httpx.MockTransport(handler)
        client = _make_client(transport)

        with patch("mc.contexts.integrations.adapters.linear_client.asyncio.sleep"):
            result = await client.execute("query { viewer { id } }")

        assert result == {"viewer": {"id": "u1"}}
        await client.close()


class TestGetIssue:
    """get_issue fetches and parses issue details."""

    async def test_get_issue_returns_parsed_fields(self) -> None:
        issue_data = {
            "id": "issue-abc",
            "identifier": "ENG-123",
            "title": "Fix the bug",
            "description": "Details here",
            "url": "https://linear.app/team/issue/ENG-123",
            "state": {"id": "state-1", "name": "In Progress", "type": "started"},
            "team": {"id": "team-1", "name": "Engineering", "key": "ENG"},
            "assignee": {"id": "user-1", "name": "Alice", "email": "alice@example.com"},
            "labels": {"nodes": [{"id": "label-1", "name": "bug", "color": "#ff0000"}]},
            "comments": {"nodes": []},
            "createdAt": "2024-01-01T00:00:00.000Z",
            "updatedAt": "2024-01-02T00:00:00.000Z",
        }
        response_body = {"data": {"issue": issue_data}}
        transport = _make_transport([_json_response(response_body)])
        client = _make_client(transport)

        with patch("asyncio.sleep"):
            result = await client.get_issue("issue-abc")

        assert result["id"] == "issue-abc"
        assert result["identifier"] == "ENG-123"
        assert result["title"] == "Fix the bug"
        assert result["state"]["name"] == "In Progress"
        assert result["team"]["key"] == "ENG"
        assert result["labels"]["nodes"][0]["name"] == "bug"
        await client.close()

    async def test_get_issue_not_found_returns_empty(self) -> None:
        response_body = {"data": {}}
        transport = _make_transport([_json_response(response_body)])
        client = _make_client(transport)

        with patch("asyncio.sleep"):
            result = await client.get_issue("nonexistent")

        assert result == {}
        await client.close()


class TestCreateComment:
    """create_comment posts a comment and returns the result."""

    async def test_create_comment_success(self) -> None:
        comment_data = {
            "success": True,
            "comment": {
                "id": "comment-1",
                "body": "This is a comment",
                "createdAt": "2024-01-01T00:00:00.000Z",
            },
        }
        response_body = {"data": {"commentCreate": comment_data}}
        transport = _make_transport([_json_response(response_body)])
        client = _make_client(transport)

        with patch("asyncio.sleep"):
            result = await client.create_comment("issue-1", "This is a comment")

        assert result["success"] is True
        assert result["comment"]["id"] == "comment-1"
        assert result["comment"]["body"] == "This is a comment"
        await client.close()

    async def test_create_comment_failure(self) -> None:
        response_body = {"data": {"commentCreate": {"success": False, "comment": None}}}
        transport = _make_transport([_json_response(response_body)])
        client = _make_client(transport)

        with patch("asyncio.sleep"):
            result = await client.create_comment("issue-1", "failing comment")

        assert result["success"] is False
        await client.close()


class TestUpdateIssue:
    """update_issue applies field changes and returns the result."""

    async def test_update_issue_state(self) -> None:
        update_data = {
            "success": True,
            "issue": {
                "id": "issue-1",
                "title": "Updated Title",
                "state": {"id": "state-done", "name": "Done", "type": "completed"},
            },
        }
        response_body = {"data": {"issueUpdate": update_data}}
        transport = _make_transport([_json_response(response_body)])
        client = _make_client(transport)

        with patch("asyncio.sleep"):
            result = await client.update_issue("issue-1", stateId="state-done")

        assert result["success"] is True
        assert result["issue"]["state"]["name"] == "Done"
        await client.close()

    async def test_update_issue_multiple_fields(self) -> None:
        update_data = {
            "success": True,
            "issue": {
                "id": "issue-1",
                "title": "New Title",
                "state": {"id": "state-1", "name": "In Progress", "type": "started"},
            },
        }
        response_body = {"data": {"issueUpdate": update_data}}
        transport = _make_transport([_json_response(response_body)])
        client = _make_client(transport)

        with patch("asyncio.sleep"):
            result = await client.update_issue("issue-1", title="New Title", stateId="state-1")

        assert result["success"] is True
        assert result["issue"]["title"] == "New Title"
        await client.close()


class TestGetTeamWorkflowStates:
    """get_team_workflow_states returns all state nodes for the team."""

    async def test_returns_states_list(self) -> None:
        states = [
            {"id": "state-1", "name": "Backlog", "type": "backlog", "position": 0.0},
            {"id": "state-2", "name": "In Progress", "type": "started", "position": 1.0},
            {"id": "state-3", "name": "Done", "type": "completed", "position": 2.0},
        ]
        response_body = {"data": {"team": {"states": {"nodes": states}}}}
        transport = _make_transport([_json_response(response_body)])
        client = _make_client(transport)

        with patch("asyncio.sleep"):
            result = await client.get_team_workflow_states("team-1")

        assert len(result) == 3
        assert result[0]["name"] == "Backlog"
        assert result[1]["type"] == "started"
        assert result[2]["id"] == "state-3"
        await client.close()

    async def test_returns_empty_list_when_no_states(self) -> None:
        response_body = {"data": {"team": {"states": {"nodes": []}}}}
        transport = _make_transport([_json_response(response_body)])
        client = _make_client(transport)

        with patch("asyncio.sleep"):
            result = await client.get_team_workflow_states("team-empty")

        assert result == []
        await client.close()

    async def test_returns_empty_list_when_team_missing(self) -> None:
        response_body = {"data": {}}
        transport = _make_transport([_json_response(response_body)])
        client = _make_client(transport)

        with patch("asyncio.sleep"):
            result = await client.get_team_workflow_states("nonexistent")

        assert result == []
        await client.close()
