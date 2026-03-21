"""Tests for the Linear platform adapter."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from mc.contexts.integrations.adapters.linear import LinearAdapter, create_linear_adapter
from mc.contexts.integrations.capabilities import PlatformCapability
from mc.contexts.integrations.config import IntegrationConfig
from mc.contexts.integrations.errors import IntegrationError, IntegrationErrorKind
from mc.contexts.integrations.events import IntegrationEventType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    *,
    api_key: str | None = "lin_api_test",
    status_mapping: dict[str, Any] | None = None,
) -> IntegrationConfig:
    return IntegrationConfig(
        id="cfg-1",
        platform="linear",
        name="Test Linear",
        enabled=True,
        board_id="board-1",
        api_key=api_key,
        status_mapping=status_mapping,
    )


def _make_client() -> MagicMock:
    """Return an async-capable mock of LinearGraphQLClient."""
    client = MagicMock()
    client.get_issue = AsyncMock()
    client.create_comment = AsyncMock()
    client.update_issue = AsyncMock()
    client.get_team_workflow_states = AsyncMock()
    client.execute = AsyncMock()
    return client


def _make_adapter(
    *,
    api_key: str | None = "lin_api_test",
    status_mapping: dict[str, Any] | None = None,
    client: MagicMock | None = None,
) -> tuple[LinearAdapter, MagicMock]:
    config = _make_config(api_key=api_key, status_mapping=status_mapping)
    mock_client = client if client is not None else _make_client()
    adapter = LinearAdapter(config, mock_client)
    return adapter, mock_client


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


class TestCapabilities:
    def test_capabilities_declares_nine_entries(self) -> None:
        adapter, _ = _make_adapter()
        assert len(adapter.capabilities) == 9

    def test_capabilities_includes_all_expected(self) -> None:
        adapter, _ = _make_adapter()
        expected = {
            PlatformCapability.INGEST_ITEM,
            PlatformCapability.PUBLISH_STATUS,
            PlatformCapability.THREAD_MIRRORING,
            PlatformCapability.STATUS_MAPPING,
            PlatformCapability.BIDIRECTIONAL_COMMENTS,
            PlatformCapability.LABELS_SYNC,
            PlatformCapability.ASSIGNMENT_SYNC,
            PlatformCapability.WEBHOOK_INBOUND,
            PlatformCapability.EXECUTION_RESUME_FROM_COMMENT,
        }
        assert expected == adapter.capabilities

    def test_supports_returns_true_for_declared(self) -> None:
        adapter, _ = _make_adapter()
        assert adapter.supports(PlatformCapability.INGEST_ITEM) is True
        assert adapter.supports(PlatformCapability.WEBHOOK_INBOUND) is True

    def test_supports_returns_false_for_undeclared(self) -> None:
        adapter, _ = _make_adapter()
        assert adapter.supports(PlatformCapability.BINARY_ATTACHMENTS) is False
        assert adapter.supports(PlatformCapability.POLLING_INBOUND) is False


# ---------------------------------------------------------------------------
# Webhook signature verification
# ---------------------------------------------------------------------------


class TestVerifyWebhookSignature:
    async def test_valid_signature_returns_true(self) -> None:
        adapter, _ = _make_adapter()
        body = b'{"action":"create"}'
        secret = "my-signing-secret"
        sig = _sign(body, secret)

        result = await adapter.verify_webhook_signature(body, {"linear-signature": sig}, secret)
        assert result is True

    async def test_invalid_signature_returns_false(self) -> None:
        adapter, _ = _make_adapter()
        body = b'{"action":"create"}'
        secret = "my-signing-secret"

        result = await adapter.verify_webhook_signature(
            body, {"linear-signature": "wrong-sig"}, secret
        )
        assert result is False

    async def test_missing_signature_header_returns_false(self) -> None:
        adapter, _ = _make_adapter()
        body = b'{"action":"create"}'

        result = await adapter.verify_webhook_signature(body, {}, "secret")
        assert result is False

    async def test_empty_signing_secret_returns_false(self) -> None:
        adapter, _ = _make_adapter()
        body = b'{"action":"create"}'

        result = await adapter.verify_webhook_signature(body, {"linear-signature": "anything"}, "")
        assert result is False

    async def test_case_insensitive_header_key(self) -> None:
        adapter, _ = _make_adapter()
        body = b'{"action":"create"}'
        secret = "s3cr3t"
        sig = _sign(body, secret)

        # Capitalised variant
        result = await adapter.verify_webhook_signature(body, {"Linear-Signature": sig}, secret)
        assert result is True


# ---------------------------------------------------------------------------
# normalize_webhook — Issue events
# ---------------------------------------------------------------------------


class TestNormalizeWebhookIssueCreate:
    async def test_issue_create_returns_item_created_event(self) -> None:
        adapter, _ = _make_adapter()
        payload = {
            "action": "create",
            "type": "Issue",
            "webhookId": "wh-1",
            "createdAt": "2024-01-01T00:00:00Z",
            "data": {
                "id": "issue-99",
                "title": "New bug",
                "description": "Something broke",
                "state": {"type": "unstarted", "name": "Todo"},
                "labels": [{"name": "bug"}],
                "assignee": {"name": "Alice"},
            },
        }

        events = await adapter.normalize_webhook(payload, {})

        assert len(events) == 1
        ev = events[0]
        assert ev.event_type == IntegrationEventType.ITEM_CREATED
        assert ev.external_id == "issue-99"
        assert ev.title == "New bug"
        assert ev.description == "Something broke"
        assert ev.status == "unstarted"
        assert ev.mc_status == "inbox"
        assert "bug" in ev.labels
        assert ev.assignee == "Alice"
        assert ev.idempotency_key == "linear-issue-create-issue-99"


class TestNormalizeWebhookIssueUpdate:
    async def test_status_change_returns_status_changed_event(self) -> None:
        adapter, _ = _make_adapter()
        payload = {
            "action": "update",
            "type": "Issue",
            "webhookId": "wh-2",
            "createdAt": "2024-01-02T00:00:00Z",
            "updatedFrom": {"state": {"type": "unstarted"}},
            "data": {
                "id": "issue-1",
                "state": {"type": "started", "name": "In Progress"},
            },
        }

        events = await adapter.normalize_webhook(payload, {})

        assert len(events) == 1
        ev = events[0]
        assert ev.event_type == IntegrationEventType.STATUS_CHANGED
        assert ev.status == "started"
        assert ev.mc_status == "in_progress"
        assert ev.external_id == "issue-1"

    async def test_title_change_returns_item_updated_event(self) -> None:
        adapter, _ = _make_adapter()
        payload = {
            "action": "update",
            "type": "Issue",
            "webhookId": "wh-3",
            "createdAt": "2024-01-03T00:00:00Z",
            "updatedFrom": {"title": "Old title"},
            "data": {"id": "issue-2", "title": "New title"},
        }

        events = await adapter.normalize_webhook(payload, {})

        assert len(events) == 1
        ev = events[0]
        assert ev.event_type == IntegrationEventType.ITEM_UPDATED
        assert ev.title == "New title"

    async def test_description_change_returns_item_updated_event(self) -> None:
        adapter, _ = _make_adapter()
        payload = {
            "action": "update",
            "type": "Issue",
            "webhookId": "wh-4",
            "createdAt": "2024-01-04T00:00:00Z",
            "updatedFrom": {"description": "old desc"},
            "data": {"id": "issue-3", "description": "new desc"},
        }

        events = await adapter.normalize_webhook(payload, {})

        assert len(events) == 1
        ev = events[0]
        assert ev.event_type == IntegrationEventType.ITEM_UPDATED
        assert ev.description == "new desc"

    async def test_label_change_returns_label_changed_event(self) -> None:
        adapter, _ = _make_adapter()
        payload = {
            "action": "update",
            "type": "Issue",
            "webhookId": "wh-5",
            "createdAt": "2024-01-05T00:00:00Z",
            "updatedFrom": {"labels": []},
            "data": {
                "id": "issue-4",
                "labels": [{"name": "feature"}, {"name": "urgent"}],
            },
        }

        events = await adapter.normalize_webhook(payload, {})

        assert len(events) == 1
        ev = events[0]
        assert ev.event_type == IntegrationEventType.LABEL_CHANGED
        assert "feature" in ev.labels
        assert "urgent" in ev.labels

    async def test_label_change_via_label_ids_key(self) -> None:
        adapter, _ = _make_adapter()
        payload = {
            "action": "update",
            "type": "Issue",
            "webhookId": "wh-6",
            "createdAt": "2024-01-06T00:00:00Z",
            "updatedFrom": {"labelIds": ["old-label-id"]},
            "data": {"id": "issue-5", "labels": [{"name": "backend"}]},
        }

        events = await adapter.normalize_webhook(payload, {})

        assert len(events) == 1
        assert events[0].event_type == IntegrationEventType.LABEL_CHANGED

    async def test_multiple_fields_changed_returns_multiple_events(self) -> None:
        adapter, _ = _make_adapter()
        payload = {
            "action": "update",
            "type": "Issue",
            "webhookId": "wh-7",
            "createdAt": "2024-01-07T00:00:00Z",
            "updatedFrom": {"state": {"type": "unstarted"}, "title": "old"},
            "data": {
                "id": "issue-6",
                "title": "New title",
                "state": {"type": "completed"},
            },
        }

        events = await adapter.normalize_webhook(payload, {})

        types = {ev.event_type for ev in events}
        assert IntegrationEventType.STATUS_CHANGED in types
        assert IntegrationEventType.ITEM_UPDATED in types


class TestNormalizeWebhookIssueRemove:
    async def test_issue_remove_returns_item_deleted_event(self) -> None:
        adapter, _ = _make_adapter()
        payload = {
            "action": "remove",
            "type": "Issue",
            "webhookId": "wh-8",
            "createdAt": "2024-01-08T00:00:00Z",
            "data": {"id": "issue-7"},
        }

        events = await adapter.normalize_webhook(payload, {})

        assert len(events) == 1
        ev = events[0]
        assert ev.event_type == IntegrationEventType.ITEM_DELETED
        assert ev.external_id == "issue-7"
        assert ev.idempotency_key == "linear-issue-remove-issue-7"


# ---------------------------------------------------------------------------
# normalize_webhook — Comment events
# ---------------------------------------------------------------------------


class TestNormalizeWebhookComment:
    async def test_comment_create_returns_comment_added_event(self) -> None:
        adapter, _ = _make_adapter()
        payload = {
            "action": "create",
            "type": "Comment",
            "webhookId": "wh-9",
            "createdAt": "2024-01-09T00:00:00Z",
            "data": {
                "id": "comment-1",
                "issueId": "issue-10",
                "body": "This needs more context",
                "user": {"name": "Bob"},
            },
        }

        events = await adapter.normalize_webhook(payload, {})

        assert len(events) == 1
        ev = events[0]
        assert ev.event_type == IntegrationEventType.COMMENT_ADDED
        assert ev.external_id == "issue-10"
        assert ev.comment_body == "This needs more context"
        assert ev.author == "Bob"
        assert ev.idempotency_key == "linear-comment-comment-1"

    async def test_comment_with_mc_prefix_is_skipped(self) -> None:
        adapter, _ = _make_adapter()
        payload = {
            "action": "create",
            "type": "Comment",
            "webhookId": "wh-10",
            "createdAt": "2024-01-10T00:00:00Z",
            "data": {
                "id": "comment-mc",
                "issueId": "issue-10",
                "body": "[MC] **MC Summary** Work complete.",
                "user": {"name": "nanobot"},
            },
        }

        events = await adapter.normalize_webhook(payload, {})
        assert events == []

    async def test_comment_non_create_action_is_ignored(self) -> None:
        adapter, _ = _make_adapter()
        for action in ("update", "remove"):
            payload = {
                "action": action,
                "type": "Comment",
                "webhookId": "wh-11",
                "createdAt": "2024-01-11T00:00:00Z",
                "data": {
                    "id": "comment-2",
                    "issueId": "issue-11",
                    "body": "Some comment",
                },
            }

            events = await adapter.normalize_webhook(payload, {})
            assert events == [], f"Expected empty list for action={action}"


# ---------------------------------------------------------------------------
# normalize_webhook — Loop prevention
# ---------------------------------------------------------------------------


class TestNormalizeWebhookLoopPrevention:
    async def test_application_actor_webhook_skipped(self) -> None:
        adapter, _ = _make_adapter()
        payload = {
            "action": "create",
            "type": "Issue",
            "webhookId": "wh-12",
            "createdAt": "2024-01-12T00:00:00Z",
            "actor": {"type": "application", "name": "nanobot"},
            "data": {"id": "issue-12", "title": "Auto-created"},
        }

        events = await adapter.normalize_webhook(payload, {})
        assert events == []

    async def test_unknown_entity_type_returns_empty(self) -> None:
        adapter, _ = _make_adapter()
        payload = {
            "action": "create",
            "type": "Reaction",
            "webhookId": "wh-13",
            "createdAt": "2024-01-13T00:00:00Z",
            "data": {"id": "reaction-1"},
        }

        events = await adapter.normalize_webhook(payload, {})
        assert events == []


# ---------------------------------------------------------------------------
# Outbound: publish_comment
# ---------------------------------------------------------------------------


class TestPublishComment:
    async def test_formats_body_with_mc_prefix(self) -> None:
        adapter, mock_client = _make_adapter()
        mock_client.create_comment.return_value = {
            "comment": {"id": "comment-new"},
            "success": True,
        }

        await adapter.publish_comment("issue-1", "Task complete")

        call_args = mock_client.create_comment.call_args
        issued_body: str = call_args[0][1]
        assert issued_body.startswith("[MC]")
        assert "Task complete" in issued_body

    async def test_formats_body_with_author(self) -> None:
        adapter, mock_client = _make_adapter()
        mock_client.create_comment.return_value = {
            "comment": {"id": "comment-new"},
            "success": True,
        }

        await adapter.publish_comment("issue-1", "Summary here", author="MC Summary")

        issued_body: str = mock_client.create_comment.call_args[0][1]
        assert "[MC]" in issued_body
        assert "**MC Summary**" in issued_body
        assert "Summary here" in issued_body

    async def test_returns_comment_id(self) -> None:
        adapter, mock_client = _make_adapter()
        mock_client.create_comment.return_value = {
            "comment": {"id": "comment-xyz"},
            "success": True,
        }

        result = await adapter.publish_comment("issue-1", "hello")
        assert result == "comment-xyz"

    async def test_returns_none_when_no_comment_in_result(self) -> None:
        adapter, mock_client = _make_adapter()
        mock_client.create_comment.return_value = {"success": False}

        result = await adapter.publish_comment("issue-1", "hello")
        assert result is None


# ---------------------------------------------------------------------------
# Outbound: publish_status_change
# ---------------------------------------------------------------------------


class TestPublishStatusChange:
    async def test_resolves_workflow_state_and_calls_update(self) -> None:
        adapter, mock_client = _make_adapter()
        mock_client.get_issue.return_value = {"team": {"id": "team-1"}}
        mock_client.get_team_workflow_states.return_value = [
            {"id": "state-started", "type": "started", "name": "In Progress"},
            {"id": "state-done", "type": "completed", "name": "Done"},
        ]
        mock_client.update_issue.return_value = {"success": True}

        await adapter.publish_status_change("issue-1", "in_progress", "started")

        mock_client.update_issue.assert_called_once_with("issue-1", stateId="state-started")

    async def test_raises_mapping_not_found_when_no_matching_state(self) -> None:
        adapter, mock_client = _make_adapter()
        mock_client.get_issue.return_value = {"team": {"id": "team-1"}}
        mock_client.get_team_workflow_states.return_value = [
            {"id": "state-started", "type": "started", "name": "In Progress"},
        ]

        with pytest.raises(IntegrationError) as exc_info:
            await adapter.publish_status_change("issue-1", "done", "completed")

        assert exc_info.value.kind == IntegrationErrorKind.MAPPING_NOT_FOUND
        assert exc_info.value.retryable is False

    async def test_caches_team_workflow_states(self) -> None:
        adapter, mock_client = _make_adapter()
        mock_client.get_issue.return_value = {"team": {"id": "team-1"}}
        mock_client.get_team_workflow_states.return_value = [
            {"id": "state-started", "type": "started", "name": "In Progress"},
        ]
        mock_client.update_issue.return_value = {"success": True}

        # Call twice with same team
        await adapter.publish_status_change("issue-1", "in_progress", "started")
        await adapter.publish_status_change("issue-2", "in_progress", "started")

        # Should only fetch states once
        mock_client.get_team_workflow_states.assert_called_once()


# ---------------------------------------------------------------------------
# Outbound: close_item
# ---------------------------------------------------------------------------


class TestCloseItem:
    async def test_close_with_summary_posts_comment_then_status(self) -> None:
        adapter, mock_client = _make_adapter()
        mock_client.create_comment.return_value = {"comment": {"id": "c-1"}, "success": True}
        mock_client.get_issue.return_value = {"team": {"id": "team-1"}}
        mock_client.get_team_workflow_states.return_value = [
            {"id": "state-done", "type": "completed", "name": "Done"},
        ]
        mock_client.update_issue.return_value = {"success": True}

        await adapter.close_item("issue-1", "completed", summary="Work done!")

        # Comment was posted
        mock_client.create_comment.assert_called_once()
        comment_body: str = mock_client.create_comment.call_args[0][1]
        assert "Work done!" in comment_body

        # Status was updated
        mock_client.update_issue.assert_called_once_with("issue-1", stateId="state-done")

    async def test_close_without_summary_skips_comment(self) -> None:
        adapter, mock_client = _make_adapter()
        mock_client.get_issue.return_value = {"team": {"id": "team-1"}}
        mock_client.get_team_workflow_states.return_value = [
            {"id": "state-done", "type": "completed", "name": "Done"},
        ]
        mock_client.update_issue.return_value = {"success": True}

        await adapter.close_item("issue-1", "completed")

        mock_client.create_comment.assert_not_called()
        mock_client.update_issue.assert_called_once()


# ---------------------------------------------------------------------------
# Lifecycle: validate_credentials
# ---------------------------------------------------------------------------


class TestValidateCredentials:
    async def test_success_returns_true(self) -> None:
        adapter, mock_client = _make_adapter()
        mock_client.execute.return_value = {"viewer": {"id": "user-1", "name": "Alice"}}

        result = await adapter.validate_credentials()
        assert result is True

    async def test_missing_viewer_id_returns_false(self) -> None:
        adapter, mock_client = _make_adapter()
        mock_client.execute.return_value = {"viewer": {}}

        result = await adapter.validate_credentials()
        assert result is False

    async def test_exception_returns_false(self) -> None:
        adapter, mock_client = _make_adapter()
        mock_client.execute.side_effect = RuntimeError("connection refused")

        result = await adapter.validate_credentials()
        assert result is False


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class TestCreateLinearAdapter:
    def test_factory_creates_adapter_with_valid_config(self) -> None:
        config = _make_config(api_key="lin_api_valid_key")
        adapter = create_linear_adapter(config)
        assert isinstance(adapter, LinearAdapter)
        assert adapter.platform_name == "linear"

    def test_factory_raises_when_api_key_missing(self) -> None:
        config = _make_config(api_key=None)
        with pytest.raises(IntegrationError) as exc_info:
            create_linear_adapter(config)

        assert exc_info.value.kind == IntegrationErrorKind.AUTH_EXPIRED
        assert "API key" in exc_info.value.message
