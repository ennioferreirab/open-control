"""Integration tests for the Linear pipeline — inbound, outbound, registry, sync."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from mc.contexts.integrations.adapters.linear import LinearAdapter, create_linear_adapter
from mc.contexts.integrations.config import IntegrationConfig
from mc.contexts.integrations.events import IntegrationEventType
from mc.contexts.integrations.pipeline.inbound import InboundPipeline
from mc.contexts.integrations.pipeline.outbound import OutboundPipeline
from mc.contexts.integrations.registry import AdapterRegistry
from mc.runtime.integrations.sync_service import IntegrationSyncService
from tests.mc.contexts.integrations.fixtures import linear_webhooks as wh

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_config(
    *,
    config_id: str = "cfg-1",
    api_key: str | None = "lin_api_test",
    status_mapping: dict[str, Any] | None = None,
) -> IntegrationConfig:
    return IntegrationConfig(
        id=config_id,
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
    client.create_comment = AsyncMock(return_value={"comment": {"id": "c-new"}})
    client.update_issue = AsyncMock(return_value={"success": True})
    client.get_team_workflow_states = AsyncMock(return_value=[])
    client.execute = AsyncMock()
    return client


def _make_adapter(
    *,
    config_id: str = "cfg-1",
    api_key: str | None = "lin_api_test",
    status_mapping: dict[str, Any] | None = None,
    client: MagicMock | None = None,
) -> tuple[LinearAdapter, MagicMock]:
    config = _make_config(config_id=config_id, api_key=api_key, status_mapping=status_mapping)
    mock_client = client if client is not None else _make_client()
    adapter = LinearAdapter(config, mock_client)
    return adapter, mock_client


def _make_registry_with_adapter(
    config_id: str = "cfg-1",
) -> tuple[AdapterRegistry, LinearAdapter, MagicMock]:
    """Create a registry pre-populated with one Linear adapter."""
    registry = AdapterRegistry()
    adapter, mock_client = _make_adapter(config_id=config_id)
    registry._adapters[config_id] = adapter
    return registry, adapter, mock_client


def _make_mock_bridge() -> MagicMock:
    bridge = MagicMock()
    bridge.get_enabled_integration_configs = MagicMock(return_value=[])
    bridge.get_outbound_pending = MagicMock(return_value={"messages": [], "activities": []})
    return bridge


# ---------------------------------------------------------------------------
# InboundPipeline
# ---------------------------------------------------------------------------


class TestInboundPipeline:
    async def test_issue_create_normalized(self) -> None:
        """Webhook create → pipeline yields ITEM_CREATED event with correct fields."""
        registry, _, _ = _make_registry_with_adapter()
        pipeline = InboundPipeline(
            bridge=_make_mock_bridge(),
            adapter_registry=registry,
            mapping_service=MagicMock(),
        )

        payload = wh.issue_created_webhook(
            issue_id="issue-abc",
            title="Fix login bug",
            state_type="unstarted",
        )
        events = await pipeline.process_webhook("cfg-1", payload, {})

        assert len(events) == 1
        ev = events[0]
        assert ev.event_type == IntegrationEventType.ITEM_CREATED
        assert ev.external_id == "issue-abc"
        assert ev.title == "Fix login bug"
        assert ev.status == "unstarted"
        assert ev.mc_status == "inbox"

    async def test_status_change_normalized(self) -> None:
        """Status change webhook → STATUS_CHANGED event with mapped mc_status."""
        registry, _, _ = _make_registry_with_adapter()
        pipeline = InboundPipeline(
            bridge=_make_mock_bridge(),
            adapter_registry=registry,
            mapping_service=MagicMock(),
        )

        payload = wh.issue_status_changed_webhook(issue_id="issue-xyz", new_state_type="started")
        events = await pipeline.process_webhook("cfg-1", payload, {})

        assert len(events) == 1
        ev = events[0]
        assert ev.event_type == IntegrationEventType.STATUS_CHANGED
        assert ev.external_id == "issue-xyz"
        assert ev.status == "started"
        assert ev.mc_status == "in_progress"

    async def test_comment_create_normalized(self) -> None:
        """Comment create webhook → COMMENT_ADDED event with body and author."""
        registry, _, _ = _make_registry_with_adapter()
        pipeline = InboundPipeline(
            bridge=_make_mock_bridge(),
            adapter_registry=registry,
            mapping_service=MagicMock(),
        )

        payload = wh.comment_created_webhook(
            issue_id="issue-123",
            body="I'll look into this today",
            user_name="Bob",
        )
        events = await pipeline.process_webhook("cfg-1", payload, {})

        assert len(events) == 1
        ev = events[0]
        assert ev.event_type == IntegrationEventType.COMMENT_ADDED
        assert ev.external_id == "issue-123"
        assert ev.comment_body == "I'll look into this today"
        assert ev.author == "Bob"

    async def test_duplicate_event_deduplicated(self) -> None:
        """Sending the same webhook twice produces only one event (idempotency)."""
        registry, _, _ = _make_registry_with_adapter()
        pipeline = InboundPipeline(
            bridge=_make_mock_bridge(),
            adapter_registry=registry,
            mapping_service=MagicMock(),
        )

        payload = wh.issue_created_webhook(issue_id="issue-dup")

        first = await pipeline.process_webhook("cfg-1", payload, {})
        second = await pipeline.process_webhook("cfg-1", payload, {})

        assert len(first) == 1
        assert len(second) == 0, "Duplicate event should be filtered by idempotency key"

    async def test_application_actor_skipped(self) -> None:
        """Webhooks from application actors are suppressed (loop prevention)."""
        registry, _, _ = _make_registry_with_adapter()
        pipeline = InboundPipeline(
            bridge=_make_mock_bridge(),
            adapter_registry=registry,
            mapping_service=MagicMock(),
        )

        payload = wh.application_actor_webhook()
        events = await pipeline.process_webhook("cfg-1", payload, {})

        assert events == []


# ---------------------------------------------------------------------------
# OutboundPipeline
# ---------------------------------------------------------------------------


class TestOutboundPipeline:
    def _make_pipeline(
        self,
        config_id: str = "cfg-1",
    ) -> tuple[OutboundPipeline, LinearAdapter, MagicMock, MagicMock]:
        registry, adapter, mock_client = _make_registry_with_adapter(config_id)
        bridge = _make_mock_bridge()
        pipeline = OutboundPipeline(
            bridge=bridge,
            adapter_registry=registry,
            mapping_service=MagicMock(),
        )
        return pipeline, adapter, mock_client, bridge

    async def test_message_published_as_comment(self) -> None:
        """A regular MC message is published as a comment on the Linear issue."""
        pipeline, _, mock_client, bridge = self._make_pipeline()
        bridge.get_outbound_pending.return_value = {
            "messages": [
                {
                    "message": {
                        "content": "Step done",
                        "author_name": "agent",
                        "type": "agent_message",
                    },
                    "mapping": {"external_id": "issue-123"},
                }
            ],
            "activities": [],
        }

        count = await pipeline.process_outbound_batch("cfg-1", "2026-01-01T00:00:00Z")

        assert count == 1
        mock_client.create_comment.assert_called_once()
        call_body: str = mock_client.create_comment.call_args[0][1]
        assert "Step done" in call_body

    async def test_mc_comment_not_echoed(self) -> None:
        """Messages with [MC] prefix are not republished (echo suppression)."""
        pipeline, _, mock_client, bridge = self._make_pipeline()
        bridge.get_outbound_pending.return_value = {
            "messages": [
                {
                    "message": {
                        "content": "[MC] **agent** Step completed: Fixed the login bug",
                        "author_name": "MC Bot",
                        "type": "agent_message",
                    },
                    "mapping": {"external_id": "issue-123"},
                }
            ],
            "activities": [],
        }

        count = await pipeline.process_outbound_batch("cfg-1", "2026-01-01T00:00:00Z")

        assert count == 0
        mock_client.create_comment.assert_not_called()

    async def test_status_change_published(self) -> None:
        """task_completed activity triggers a status change on the Linear issue."""
        pipeline, _, mock_client, bridge = self._make_pipeline()
        mock_client.get_issue.return_value = {"team": {"id": "team-1"}}
        mock_client.get_team_workflow_states.return_value = [
            {"id": "state-done", "type": "completed", "name": "Done"},
        ]
        bridge.get_outbound_pending.return_value = {
            "messages": [],
            "activities": [
                {
                    "activity": {"event_type": "task_completed"},
                    "mapping": {"external_id": "issue-123"},
                }
            ],
        }

        count = await pipeline.process_outbound_batch("cfg-1", "2026-01-01T00:00:00Z")

        assert count == 1
        mock_client.update_issue.assert_called_once_with("issue-123", stateId="state-done")

    async def test_irrelevant_activity_skipped(self) -> None:
        """Non-task activities (e.g. board_created) are not published to Linear."""
        pipeline, _, mock_client, bridge = self._make_pipeline()
        bridge.get_outbound_pending.return_value = {
            "messages": [],
            "activities": [
                {
                    "activity": {"event_type": "board_created"},
                    "mapping": {"external_id": "issue-123"},
                }
            ],
        }

        count = await pipeline.process_outbound_batch("cfg-1", "2026-01-01T00:00:00Z")

        assert count == 0
        mock_client.update_issue.assert_not_called()


# ---------------------------------------------------------------------------
# AdapterRegistry
# ---------------------------------------------------------------------------


class TestAdapterRegistry:
    def test_register_and_create(self) -> None:
        """A registered factory creates an adapter retrievable by config ID."""
        registry = AdapterRegistry()
        config = _make_config(config_id="cfg-reg")

        registry.register_factory("linear", create_linear_adapter)
        adapter = registry.create_adapter(config)

        assert isinstance(adapter, LinearAdapter)
        assert registry.get_adapter("cfg-reg") is adapter

    def test_create_unknown_platform_raises(self) -> None:
        """Creating an adapter for an unregistered platform raises ValueError."""
        registry = AdapterRegistry()
        config_with_unknown = IntegrationConfig(
            id="cfg-unknown",
            platform="github",  # not registered
            name="GitHub",
            enabled=True,
            board_id="board-1",
            api_key="tok",
        )

        with pytest.raises(ValueError, match="No factory registered for platform"):
            registry.create_adapter(config_with_unknown)

    def test_list_adapters(self) -> None:
        """list_adapters returns all adapters created through the registry."""
        registry = AdapterRegistry()
        config_a = _make_config(config_id="cfg-a")
        config_b = _make_config(config_id="cfg-b")

        registry.register_factory("linear", create_linear_adapter)
        registry.create_adapter(config_a)
        registry.create_adapter(config_b)

        adapters = registry.list_adapters()
        assert len(adapters) == 2
        assert all(isinstance(a, LinearAdapter) for a in adapters)


# ---------------------------------------------------------------------------
# IntegrationSyncService
# ---------------------------------------------------------------------------


class TestSyncService:
    def test_initialize_creates_adapters(self) -> None:
        """initialize() reads enabled configs from bridge and creates one adapter per entry."""
        registry = AdapterRegistry()
        registry.register_factory("linear", create_linear_adapter)

        bridge = _make_mock_bridge()
        bridge.get_enabled_integration_configs.return_value = [
            {
                "id": "cfg-sync-1",
                "platform": "linear",
                "name": "My Linear",
                "enabled": True,
                "board_id": "board-1",
                "api_key": "lin_api_key",
                "sync_direction": "bidirectional",
                "thread_mirroring": True,
                "sync_attachments": False,
                "sync_labels": False,
            }
        ]

        service = IntegrationSyncService(bridge=bridge, adapter_registry=registry)
        count = service.initialize()

        assert count == 1
        adapter = registry.get_adapter("cfg-sync-1")
        assert isinstance(adapter, LinearAdapter)

    def test_initialize_handles_errors(self) -> None:
        """A bad config (missing api_key) logs an error but does not stop other configs."""
        registry = AdapterRegistry()
        registry.register_factory("linear", create_linear_adapter)

        bridge = _make_mock_bridge()
        bridge.get_enabled_integration_configs.return_value = [
            # Bad config — no api_key, will raise IntegrationError
            {
                "id": "cfg-bad",
                "platform": "linear",
                "name": "Bad Linear",
                "enabled": True,
                "board_id": "board-1",
                # api_key intentionally absent → create_linear_adapter raises
                "sync_direction": "bidirectional",
                "thread_mirroring": True,
                "sync_attachments": False,
                "sync_labels": False,
            },
            # Good config
            {
                "id": "cfg-good",
                "platform": "linear",
                "name": "Good Linear",
                "enabled": True,
                "board_id": "board-1",
                "api_key": "lin_api_good",
                "sync_direction": "bidirectional",
                "thread_mirroring": True,
                "sync_attachments": False,
                "sync_labels": False,
            },
        ]

        service = IntegrationSyncService(bridge=bridge, adapter_registry=registry)
        count = service.initialize()

        # Only the good config succeeded
        assert count == 1
        assert registry.get_adapter("cfg-bad") is None
        assert isinstance(registry.get_adapter("cfg-good"), LinearAdapter)
