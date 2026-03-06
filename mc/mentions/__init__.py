"""
mc.mentions — @mention detection and handling for task threads.

Re-exports public API from handler and watcher sub-modules.
"""

from mc.mentions.handler import (
    extract_mentions,
    handle_all_mentions,
    handle_mention,
    is_mention_message,
    MENTION_TIMEOUT_SECONDS,
)
from mc.mentions.watcher import MentionWatcher, POLL_INTERVAL_SECONDS

__all__ = [
    "extract_mentions",
    "handle_all_mentions",
    "handle_mention",
    "is_mention_message",
    "MENTION_TIMEOUT_SECONDS",
    "MentionWatcher",
    "POLL_INTERVAL_SECONDS",
]
