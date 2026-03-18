"""Tests for ChannelManager.register_channel and MC channel init."""

from unittest.mock import MagicMock

from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.channels.manager import ChannelManager


class FakeChannel(BaseChannel):
    name = "fake"

    async def start(self):
        self._running = True

    async def stop(self):
        self._running = False

    async def send(self, msg):
        pass


class TestRegisterChannel:
    def test_register_channel_adds_to_dict(self) -> None:
        config = MagicMock()
        # Disable all channels in config so _init_channels is a no-op
        for ch_name in (
            "telegram",
            "whatsapp",
            "discord",
            "feishu",
            "mochat",
            "dingtalk",
            "email",
            "slack",
            "qq",
        ):
            getattr(config.channels, ch_name).enabled = False

        bus = MessageBus()
        mgr = ChannelManager(config, bus)

        fake = FakeChannel(config=MagicMock(), bus=bus)
        mgr.register_channel("fake", fake)

        assert "fake" in mgr.channels
        assert mgr.get_channel("fake") is fake

    def test_register_channel_appears_in_enabled_list(self) -> None:
        config = MagicMock()
        for ch_name in (
            "telegram",
            "whatsapp",
            "discord",
            "feishu",
            "mochat",
            "dingtalk",
            "email",
            "slack",
            "qq",
        ):
            getattr(config.channels, ch_name).enabled = False

        bus = MessageBus()
        mgr = ChannelManager(config, bus)
        fake = FakeChannel(config=MagicMock(), bus=bus)
        mgr.register_channel("fake", fake)

        assert "fake" in mgr.enabled_channels
