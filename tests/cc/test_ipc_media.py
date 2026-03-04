"""Unit tests for media support in send_message IPC handler."""
from __future__ import annotations
import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
from claude_code.ipc_server import MCSocketServer

pytestmark = pytest.mark.asyncio

class TestSendMessageMedia:
    async def test_media_passed_to_outbound_message(self):
        """send_message handler passes media paths to OutboundMessage."""
        bus = MagicMock()
        bus.publish_outbound = AsyncMock()
        server = MCSocketServer(None, bus)
        result = await server._handle_send_message(
            content="check this image",
            channel="telegram",
            chat_id="123",
            media=["/tmp/image.png"],
        )
        assert result["status"] == "Message sent"
        bus.publish_outbound.assert_called_once()
        msg = bus.publish_outbound.call_args[0][0]
        assert msg.media == ["/tmp/image.png"]

    async def test_media_defaults_to_empty_list(self):
        """send_message handler defaults media to empty list when not provided."""
        bus = MagicMock()
        bus.publish_outbound = AsyncMock()
        server = MCSocketServer(None, bus)
        result = await server._handle_send_message(
            content="no attachments",
            channel="telegram",
            chat_id="123",
        )
        msg = bus.publish_outbound.call_args[0][0]
        assert msg.media == []

    async def test_media_multiple_files(self):
        """send_message handler handles multiple media files."""
        bus = MagicMock()
        bus.publish_outbound = AsyncMock()
        server = MCSocketServer(None, bus)
        media_list = ["/tmp/a.png", "/tmp/b.pdf", "/tmp/c.mp3"]
        result = await server._handle_send_message(
            content="multiple files",
            channel="telegram",
            chat_id="123",
            media=media_list,
        )
        msg = bus.publish_outbound.call_args[0][0]
        assert msg.media == media_list
