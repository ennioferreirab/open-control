"""Chat channels module with plugin architecture."""

from nanobot.channels.base import BaseChannel
from nanobot.channels.manager import ChannelManager
from nanobot.channels.mission_control import MissionControlChannel

__all__ = ["BaseChannel", "ChannelManager", "MissionControlChannel"]
