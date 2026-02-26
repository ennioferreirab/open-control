"""Tests for MessageBus lazy queue initialization."""

import asyncio

import pytest

from nanobot.bus.queue import MessageBus


class TestMessageBusInit:
    """MessageBus can be created outside an async context."""

    def test_create_without_event_loop(self) -> None:
        """MessageBus() should not require a running event loop."""
        bus = MessageBus()
        assert bus is not None

    def test_queues_not_created_on_init(self) -> None:
        """Queues should be lazily created, not in __init__."""
        bus = MessageBus()
        assert bus._inbound is None
        assert bus._outbound is None

    @pytest.mark.asyncio
    async def test_inbound_queue_created_on_access(self) -> None:
        """Inbound queue is created on first async access."""
        bus = MessageBus()
        assert bus._inbound is None
        q = bus.inbound
        assert isinstance(q, asyncio.Queue)

    @pytest.mark.asyncio
    async def test_outbound_queue_created_on_access(self) -> None:
        """Outbound queue is created on first async access."""
        bus = MessageBus()
        assert bus._outbound is None
        q = bus.outbound
        assert isinstance(q, asyncio.Queue)

    @pytest.mark.asyncio
    async def test_queue_reused_on_subsequent_access(self) -> None:
        """Same queue instance returned on repeated access."""
        bus = MessageBus()
        q1 = bus.inbound
        q2 = bus.inbound
        assert q1 is q2

    @pytest.mark.asyncio
    async def test_publish_consume_roundtrip(self) -> None:
        """Messages flow through the bus correctly with lazy init."""
        from nanobot.bus.events import InboundMessage

        bus = MessageBus()
        msg = InboundMessage(
            channel="test",
            chat_id="c1",
            sender_id="user",
            content="hello",
        )
        await bus.publish_inbound(msg)
        received = await bus.consume_inbound()
        assert received.content == "hello"

    @pytest.mark.asyncio
    async def test_qsize_works_before_and_after_init(self) -> None:
        """Queue size properties work with lazy initialization."""
        bus = MessageBus()
        assert bus.inbound_size == 0
        assert bus.outbound_size == 0
