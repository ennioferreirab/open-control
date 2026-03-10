"""Tests for polling settings: _read_polling_settings helper and constructor kwargs."""

from __future__ import annotations

from unittest.mock import MagicMock

from mc.runtime.gateway import POLLING_BOUNDS, POLLING_DEFAULTS, _read_polling_settings


def _make_bridge(overrides: dict[str, str] | None = None) -> MagicMock:
    """Create a mock bridge returning settings:list with optional overrides."""
    store = dict(overrides or {})

    def fake_query(fn: str, args: dict | None = None) -> list[dict[str, str]] | None:
        if fn == "settings:list":
            return [{"key": k, "value": v} for k, v in store.items()]
        return None

    bridge = MagicMock()
    bridge.query.side_effect = fake_query
    return bridge


# ---------------------------------------------------------------------------
# _read_polling_settings
# ---------------------------------------------------------------------------


def test_defaults_when_no_settings() -> None:
    bridge = _make_bridge()
    result = _read_polling_settings(bridge)
    assert result == POLLING_DEFAULTS


def test_valid_overrides() -> None:
    bridge = _make_bridge(
        {
            "gateway_active_poll_seconds": "10",
            "chat_sleep_poll_seconds": "120",
        }
    )
    result = _read_polling_settings(bridge)
    assert result["gateway_active_poll_seconds"] == 10
    assert result["chat_sleep_poll_seconds"] == 120
    # Non-overridden keys keep defaults
    assert result["gateway_sleep_poll_seconds"] == 300
    assert result["mention_poll_seconds"] == 10


def test_invalid_value_falls_back_to_default() -> None:
    bridge = _make_bridge({"gateway_active_poll_seconds": "not-a-number"})
    result = _read_polling_settings(bridge)
    assert result["gateway_active_poll_seconds"] == POLLING_DEFAULTS["gateway_active_poll_seconds"]


def test_query_exception_falls_back_to_all_defaults() -> None:
    bridge = MagicMock()
    bridge.query.side_effect = RuntimeError("connection error")
    result = _read_polling_settings(bridge)
    assert result == POLLING_DEFAULTS


def test_value_clamped_to_min() -> None:
    bridge = _make_bridge({"gateway_active_poll_seconds": "0"})
    result = _read_polling_settings(bridge)
    lo, _ = POLLING_BOUNDS["gateway_active_poll_seconds"]
    assert result["gateway_active_poll_seconds"] == lo


def test_value_clamped_to_max() -> None:
    bridge = _make_bridge({"gateway_active_poll_seconds": "9999"})
    result = _read_polling_settings(bridge)
    _, hi = POLLING_BOUNDS["gateway_active_poll_seconds"]
    assert result["gateway_active_poll_seconds"] == hi


def test_negative_value_clamped_to_min() -> None:
    bridge = _make_bridge({"timeout_check_seconds": "-10"})
    result = _read_polling_settings(bridge)
    lo, _ = POLLING_BOUNDS["timeout_check_seconds"]
    assert result["timeout_check_seconds"] == lo


# ---------------------------------------------------------------------------
# Constructor kwargs — verify new kwargs are accepted and stored
# ---------------------------------------------------------------------------


def test_chat_handler_accepts_poll_kwargs() -> None:
    from mc.contexts.conversation.chat_handler import ChatHandler

    bridge = MagicMock()
    handler = ChatHandler(
        bridge,
        active_poll_interval_seconds=15,
        sleep_poll_interval_seconds=120,
    )
    assert handler._active_poll_interval == 15
    assert handler._sleep_poll_interval == 120


def test_chat_handler_uses_module_defaults() -> None:
    from mc.contexts.conversation.chat_handler import (
        ACTIVE_POLL_INTERVAL_SECONDS,
        SLEEP_POLL_INTERVAL_SECONDS,
        ChatHandler,
    )

    bridge = MagicMock()
    handler = ChatHandler(bridge)
    assert handler._active_poll_interval == ACTIVE_POLL_INTERVAL_SECONDS
    assert handler._sleep_poll_interval == SLEEP_POLL_INTERVAL_SECONDS


def test_mention_watcher_accepts_poll_kwarg() -> None:
    from mc.mentions.watcher import MentionWatcher

    bridge = MagicMock()
    watcher = MentionWatcher(bridge, poll_interval_seconds=30)
    assert watcher._poll_interval == 30


def test_mention_watcher_uses_module_default() -> None:
    from mc.mentions.watcher import POLL_INTERVAL_SECONDS, MentionWatcher

    bridge = MagicMock()
    watcher = MentionWatcher(bridge)
    assert watcher._poll_interval == POLL_INTERVAL_SECONDS


def test_timeout_checker_accepts_interval_kwarg() -> None:
    from mc.runtime.timeout_checker import TimeoutChecker

    bridge = MagicMock()
    checker = TimeoutChecker(bridge, check_interval_seconds=120)
    assert checker._check_interval == 120


def test_timeout_checker_uses_module_default() -> None:
    from mc.runtime.timeout_checker import CHECK_INTERVAL_SECONDS, TimeoutChecker

    bridge = MagicMock()
    checker = TimeoutChecker(bridge)
    assert checker._check_interval == CHECK_INTERVAL_SECONDS
