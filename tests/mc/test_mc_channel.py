"""Tests for MissionControlChannel."""

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.mission_control import MissionControlChannel


class TestMissionControlChannel:
    """MissionControlChannel unit tests."""

    def test_channel_name_is_mc(self) -> None:
        bus = MessageBus()
        ch = MissionControlChannel(config=MagicMock(), bus=bus)
        assert ch.name == "mc"

    def test_init_without_bridge(self) -> None:
        bus = MessageBus()
        ch = MissionControlChannel(config=MagicMock(), bus=bus)
        assert ch._bridge is None

    def test_init_with_bridge(self) -> None:
        bus = MessageBus()
        bridge = MagicMock()
        ch = MissionControlChannel(config=MagicMock(), bus=bus, bridge=bridge)
        assert ch._bridge is bridge

    @pytest.mark.asyncio
    async def test_send_without_bridge_logs_warning(self) -> None:
        bus = MessageBus()
        ch = MissionControlChannel(config=MagicMock(), bus=bus)
        msg = OutboundMessage(channel="mc", chat_id="task123", content="hello")
        # Should not raise, just log warning
        await ch.send(msg)

    @pytest.mark.asyncio
    async def test_send_with_task_id_posts_to_thread(self) -> None:
        bus = MessageBus()
        bridge = MagicMock()
        bridge.query = MagicMock(return_value={"_id": "task123", "status": "done"})
        bridge.send_message = MagicMock()
        ch = MissionControlChannel(config=MagicMock(), bus=bus, bridge=bridge)

        msg = OutboundMessage(channel="mc", chat_id="task123", content="cron result")
        await ch.send(msg)

        bridge.send_message.assert_called_once()
        call_args = bridge.send_message.call_args
        assert call_args[0][0] == "task123"  # task_id
        assert "cron result" in call_args[0][3]  # content

    @pytest.mark.asyncio
    async def test_send_creates_task_when_no_existing_task(self) -> None:
        bus = MessageBus()
        bridge = MagicMock()
        bridge.query = MagicMock(return_value=None)
        bridge.mutation = MagicMock()
        ch = MissionControlChannel(config=MagicMock(), bus=bus, bridge=bridge)

        msg = OutboundMessage(channel="mc", chat_id="nonexistent", content="hello")
        await ch.send(msg)

        bridge.mutation.assert_called_once()
        call_args = bridge.mutation.call_args
        assert call_args[0][0] == "tasks:create"

    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self) -> None:
        bus = MessageBus()
        ch = MissionControlChannel(config=MagicMock(), bus=bus)
        ch._running = True
        await ch.stop()
        assert ch._running is False
        assert ch._stop_event.is_set()

    @pytest.mark.asyncio
    async def test_send_uses_to_thread(self) -> None:
        """Verify bridge calls are wrapped in asyncio.to_thread."""
        bus = MessageBus()
        bridge = MagicMock()
        bridge.query = MagicMock(return_value={"_id": "t1", "status": "done"})
        bridge.send_message = MagicMock()
        ch = MissionControlChannel(config=MagicMock(), bus=bus, bridge=bridge)

        msg = OutboundMessage(channel="mc", chat_id="t1", content="test")
        with patch("nanobot.channels.mission_control.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.side_effect = [
                {"_id": "t1", "status": "done"},  # query result
                None,  # send_message result
            ]
            await ch.send(msg)
            assert mock_to_thread.call_count == 2
