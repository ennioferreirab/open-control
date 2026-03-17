"""Tests for sync_nanobot_default_model startup config sync."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch


def _write_config(path: Path, model: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"agents": {"defaults": {"model": model}}}, indent=2) + "\n",
        encoding="utf-8",
    )


def test_updates_config_when_convex_model_differs(tmp_path, monkeypatch):
    from mc.runtime.gateway import NANOBOT_AGENT_NAME, sync_nanobot_default_model

    config_path = tmp_path / ".nanobot" / "config.json"
    _write_config(config_path, model="anthropic/old-model")
    monkeypatch.setattr(
        "nanobot.config.loader.get_config_path",
        lambda: config_path,
    )

    bridge = MagicMock()
    bridge.get_agent_by_name.return_value = {
        "name": NANOBOT_AGENT_NAME,
        "model": "anthropic/new-model",
    }

    updated = sync_nanobot_default_model(bridge)

    assert updated is True
    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert data["agents"]["defaults"]["model"] == "anthropic/new-model"
    bridge.get_agent_by_name.assert_called_once_with(NANOBOT_AGENT_NAME)


def test_no_write_when_models_match(tmp_path, monkeypatch):
    from mc.runtime.gateway import NANOBOT_AGENT_NAME, sync_nanobot_default_model

    config_path = tmp_path / ".nanobot" / "config.json"
    _write_config(config_path, model="anthropic/match-model")
    monkeypatch.setattr(
        "nanobot.config.loader.get_config_path",
        lambda: config_path,
    )

    bridge = MagicMock()
    bridge.get_agent_by_name.return_value = {
        "name": NANOBOT_AGENT_NAME,
        "model": "anthropic/match-model",
    }

    with patch("mc.infrastructure.agent_bootstrap.os.replace") as mock_replace:
        updated = sync_nanobot_default_model(bridge)

    assert updated is False
    mock_replace.assert_not_called()


def test_skips_when_agent_absent(tmp_path, monkeypatch):
    from mc.runtime.gateway import sync_nanobot_default_model

    config_path = tmp_path / ".nanobot" / "config.json"
    _write_config(config_path, model="anthropic/current-model")
    monkeypatch.setattr(
        "nanobot.config.loader.get_config_path",
        lambda: config_path,
    )

    bridge = MagicMock()
    bridge.get_agent_by_name.return_value = None

    updated = sync_nanobot_default_model(bridge)

    assert updated is False


def test_skips_when_agent_model_empty_or_none(tmp_path, monkeypatch):
    from mc.runtime.gateway import sync_nanobot_default_model

    config_path = tmp_path / ".nanobot" / "config.json"
    _write_config(config_path, model="anthropic/current-model")
    monkeypatch.setattr(
        "nanobot.config.loader.get_config_path",
        lambda: config_path,
    )

    bridge = MagicMock()
    bridge.get_agent_by_name.return_value = {"model": None}
    assert sync_nanobot_default_model(bridge) is False

    bridge.get_agent_by_name.return_value = {"model": ""}
    assert sync_nanobot_default_model(bridge) is False


def test_resolves_tier_reference_before_writing(tmp_path, monkeypatch):
    from mc.runtime.gateway import NANOBOT_AGENT_NAME, sync_nanobot_default_model

    config_path = tmp_path / ".nanobot" / "config.json"
    _write_config(config_path, model="anthropic/old-model")
    monkeypatch.setattr(
        "nanobot.config.loader.get_config_path",
        lambda: config_path,
    )

    bridge = MagicMock()
    bridge.get_agent_by_name.return_value = {
        "name": NANOBOT_AGENT_NAME,
        "model": "tier:standard-low",
    }
    # TierResolver queries model_tiers setting via bridge.query
    bridge.query.return_value = json.dumps(
        {
            "standard-low": "anthropic/claude-haiku-4-5",
            "standard-medium": "anthropic/claude-sonnet-4-6",
            "standard-high": "anthropic/claude-opus-4-6",
        }
    )

    updated = sync_nanobot_default_model(bridge)

    assert updated is True
    data = json.loads(config_path.read_text(encoding="utf-8"))
    # Must write the resolved model, NOT the tier reference
    assert data["agents"]["defaults"]["model"] == "anthropic/claude-haiku-4-5"
    assert "tier:" not in data["agents"]["defaults"]["model"]


def test_skips_when_tier_resolution_fails(tmp_path, monkeypatch):
    from mc.runtime.gateway import NANOBOT_AGENT_NAME, sync_nanobot_default_model

    config_path = tmp_path / ".nanobot" / "config.json"
    _write_config(config_path, model="anthropic/old-model")
    monkeypatch.setattr(
        "nanobot.config.loader.get_config_path",
        lambda: config_path,
    )

    bridge = MagicMock()
    bridge.get_agent_by_name.return_value = {
        "name": NANOBOT_AGENT_NAME,
        "model": "tier:nonexistent-tier",
    }
    # Return empty tiers so resolution fails
    bridge.query.return_value = json.dumps({})

    updated = sync_nanobot_default_model(bridge)

    assert updated is False
    # config.json must NOT be modified
    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert data["agents"]["defaults"]["model"] == "anthropic/old-model"


def test_skips_when_config_missing(tmp_path, monkeypatch):
    from mc.runtime.gateway import NANOBOT_AGENT_NAME, sync_nanobot_default_model

    missing_config = tmp_path / ".nanobot" / "config.json"
    monkeypatch.setattr(
        "nanobot.config.loader.get_config_path",
        lambda: missing_config,
    )

    bridge = MagicMock()
    bridge.get_agent_by_name.return_value = {
        "name": NANOBOT_AGENT_NAME,
        "model": "anthropic/new-model",
    }

    updated = sync_nanobot_default_model(bridge)

    assert updated is False
