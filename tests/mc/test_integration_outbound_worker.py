"""Tests for the subscription-driven integration outbound worker."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from mc.runtime.integrations.outbound_worker import IntegrationOutboundWorker


@pytest.mark.asyncio
async def test_run_subscribes_to_enabled_configs_and_processes_outbound_snapshot() -> None:
    bridge = MagicMock()
    config_queue: asyncio.Queue[object] = asyncio.Queue()
    config_queue.put_nowait([{"id": "cfg-1", "enabled": True}])

    outbound_queue: asyncio.Queue[object] = asyncio.Queue()
    outbound_queue.put_nowait(
        {
            "messages": [
                {
                    "message": {
                        "id": "msg-1",
                        "content": "Hello from MC",
                        "author_name": "User",
                        "type": "user_message",
                        "timestamp": "2026-03-23T12:00:01Z",
                    },
                    "mapping": {"external_id": "EXT-1"},
                }
            ],
            "activities": [],
            "message_window_full": False,
            "activity_window_full": False,
        }
    )
    bridge.async_subscribe.side_effect = [config_queue, outbound_queue]
    bridge.get_outbound_pending = MagicMock(return_value={"messages": [], "activities": []})

    pipeline = MagicMock()
    pipeline.publish_message_item = AsyncMock(return_value="published")
    pipeline.publish_activity_item = AsyncMock(return_value="published")

    worker = IntegrationOutboundWorker(bridge, pipeline)
    task = asyncio.create_task(worker.run())
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert bridge.async_subscribe.call_args_list[0].args == ("integrations:getEnabledConfigs", {})
    assert bridge.async_subscribe.call_args_list[1].args == (
        "integrations:listRecentOutboundPendingByConfig",
        {"config_id": "cfg-1", "limit": worker._feed_limit},
    )
    pipeline.publish_message_item.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_config_snapshot_retries_items_that_failed_to_publish() -> None:
    bridge = MagicMock()
    bridge.get_outbound_pending = MagicMock(return_value={"messages": [], "activities": []})

    pipeline = MagicMock()
    pipeline.publish_message_item = AsyncMock(side_effect=["failed", "published"])
    pipeline.publish_activity_item = AsyncMock(return_value="published")

    worker = IntegrationOutboundWorker(bridge, pipeline)
    snapshot = {
        "messages": [
            {
                "message": {
                    "id": "msg-1",
                    "content": "Hello from MC",
                    "author_name": "User",
                    "type": "user_message",
                    "timestamp": "2026-03-23T12:00:01Z",
                },
                "mapping": {"external_id": "EXT-1"},
            }
        ],
        "activities": [],
        "message_window_full": False,
        "activity_window_full": False,
    }

    first = await worker._process_config_snapshot("cfg-1", snapshot)
    second = await worker._process_config_snapshot("cfg-1", snapshot)

    assert first is False
    assert second is True
    assert pipeline.publish_message_item.await_count == 2
