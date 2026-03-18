"""Polling configuration helpers for Mission Control runtime."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)

POLLING_DEFAULTS: dict[str, int] = {
    "gateway_active_poll_seconds": 5,
    "gateway_sleep_poll_seconds": 300,
    "gateway_auto_sleep_seconds": 300,
    "chat_active_poll_seconds": 5,
    "chat_sleep_poll_seconds": 60,
    "mention_poll_seconds": 10,
    "timeout_check_seconds": 60,
}

POLLING_BOUNDS: dict[str, tuple[int, int]] = {
    "gateway_active_poll_seconds": (1, 60),
    "gateway_sleep_poll_seconds": (10, 3600),
    "gateway_auto_sleep_seconds": (30, 3600),
    "chat_active_poll_seconds": (1, 60),
    "chat_sleep_poll_seconds": (5, 600),
    "mention_poll_seconds": (1, 120),
    "timeout_check_seconds": (10, 600),
}


def _read_polling_settings(bridge: ConvexBridge) -> dict[str, int]:
    """Read polling/sleep settings from Convex, falling back to defaults."""
    store: dict[str, str] = {}
    try:
        all_settings = bridge.query("settings:list") or []
        for setting in all_settings:
            store[setting["key"]] = setting["value"]
    except Exception:
        logger.warning("[gateway] Could not fetch settings — using polling defaults")
        return dict(POLLING_DEFAULTS)

    result: dict[str, int] = {}
    for key, default in POLLING_DEFAULTS.items():
        lo, hi = POLLING_BOUNDS[key]
        try:
            raw = store.get(key)
            val = int(raw) if raw else default
        except (TypeError, ValueError):
            val = default
        result[key] = max(lo, min(hi, val))
    return result
