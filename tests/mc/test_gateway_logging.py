"""Tests for gateway logging configuration helpers."""

from __future__ import annotations

import logging


def test_resolve_log_level_defaults_to_info(monkeypatch) -> None:
    """Gateway logging defaults to INFO when no env override exists."""
    from mc.runtime.gateway import _resolve_log_level

    monkeypatch.delenv("MC_LOG_LEVEL", raising=False)
    assert _resolve_log_level() == logging.INFO


def test_resolve_log_level_uses_debug_env_override(monkeypatch) -> None:
    """Gateway logging honors MC_LOG_LEVEL=DEBUG."""
    from mc.runtime.gateway import _resolve_log_level

    monkeypatch.setenv("MC_LOG_LEVEL", "DEBUG")
    assert _resolve_log_level() == logging.DEBUG


def test_resolve_log_level_falls_back_to_info_for_invalid_value(monkeypatch) -> None:
    """Invalid log levels do not break startup and fall back to INFO."""
    from mc.runtime.gateway import _resolve_log_level

    monkeypatch.setenv("MC_LOG_LEVEL", "LOUD")
    assert _resolve_log_level() == logging.INFO
