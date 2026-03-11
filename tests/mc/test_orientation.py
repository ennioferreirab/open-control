"""Tests for mc.infrastructure.orientation — shared orientation loader."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mc.infrastructure.orientation import load_orientation


class TestLoadOrientation:
    def test_returns_none_for_lead_agent(self) -> None:
        """Lead-agent should never receive orientation."""
        result = load_orientation("lead-agent")
        assert result is None

    def test_returns_none_for_nanobot(self) -> None:
        """nanobot should never receive orientation."""
        result = load_orientation("nanobot")
        assert result is None

    def test_returns_none_when_file_missing(self, tmp_path: Path) -> None:
        """No orientation file -> None."""
        with patch("mc.infrastructure.orientation.Path") as mock_path_cls:
            mock_home = tmp_path
            mock_path_cls.home.return_value = mock_home
            result = load_orientation("test-agent")
        assert result is None

    def test_returns_none_when_file_empty(self, tmp_path: Path) -> None:
        """Empty orientation file -> None."""
        mc_dir = tmp_path / ".nanobot" / "mc"
        mc_dir.mkdir(parents=True)
        (mc_dir / "agent-orientation.md").write_text("   \n  ", encoding="utf-8")

        with patch("mc.infrastructure.orientation.Path") as mock_path_cls:
            mock_path_cls.home.return_value = tmp_path
            result = load_orientation("test-agent")
        assert result is None

    def test_returns_orientation_text(self, tmp_path: Path) -> None:
        """Simple orientation text returned as-is."""
        mc_dir = tmp_path / ".nanobot" / "mc"
        mc_dir.mkdir(parents=True)
        (mc_dir / "agent-orientation.md").write_text("You are a helpful agent.", encoding="utf-8")

        with patch("mc.infrastructure.orientation.Path") as mock_path_cls:
            mock_path_cls.home.return_value = tmp_path
            result = load_orientation("test-agent")
        assert result == "You are a helpful agent."

    def test_saved_setting_overrides_file(self, tmp_path: Path) -> None:
        """A saved global_orientation_prompt should take precedence over the file."""
        mc_dir = tmp_path / ".nanobot" / "mc"
        mc_dir.mkdir(parents=True)
        (mc_dir / "agent-orientation.md").write_text("File orientation", encoding="utf-8")
        bridge = MagicMock()
        bridge.query.return_value = "Saved orientation"

        with patch("mc.infrastructure.orientation.Path") as mock_path_cls:
            mock_path_cls.home.return_value = tmp_path
            result = load_orientation("test-agent", bridge=bridge)

        assert result == "Saved orientation"
        bridge.query.assert_called_once_with(
            "settings:get",
            {"key": "global_orientation_prompt"},
        )

    def test_blank_setting_falls_back_to_file(self, tmp_path: Path) -> None:
        """Blank saved setting should still use the local fallback file."""
        mc_dir = tmp_path / ".nanobot" / "mc"
        mc_dir.mkdir(parents=True)
        (mc_dir / "agent-orientation.md").write_text("Fallback file orientation", encoding="utf-8")
        bridge = MagicMock()
        bridge.query.return_value = "   "

        with patch("mc.infrastructure.orientation.Path") as mock_path_cls:
            mock_path_cls.home.return_value = tmp_path
            result = load_orientation("test-agent", bridge=bridge)

        assert result == "Fallback file orientation"

    def test_interpolates_agent_roster(self, tmp_path: Path) -> None:
        """The {agent_roster} placeholder is interpolated."""
        mc_dir = tmp_path / ".nanobot" / "mc"
        mc_dir.mkdir(parents=True)
        (mc_dir / "agent-orientation.md").write_text(
            "Agents:\n{agent_roster}", encoding="utf-8"
        )

        with patch("mc.infrastructure.orientation.Path") as mock_path_cls, \
             patch(
                 "mc.infrastructure.orientation_helpers.build_agent_roster",
                 return_value="- **bot** — helper",
             ):
            mock_path_cls.home.return_value = tmp_path
            result = load_orientation("test-agent")

        assert result is not None
        assert "- **bot** — helper" in result
        assert "{agent_roster}" not in result

    def test_interpolates_host_timezone(self, tmp_path: Path) -> None:
        """The {host_timezone} placeholder is interpolated."""
        mc_dir = tmp_path / ".nanobot" / "mc"
        mc_dir.mkdir(parents=True)
        (mc_dir / "agent-orientation.md").write_text(
            "Timezone: {host_timezone}", encoding="utf-8"
        )

        with patch("mc.infrastructure.orientation.Path") as mock_path_cls, \
             patch(
                 "mc.infrastructure.orientation_helpers.get_iana_timezone",
                 return_value="America/Vancouver",
             ):
            mock_path_cls.home.return_value = tmp_path
            result = load_orientation("test-agent")

        assert result is not None
        assert "America/Vancouver" in result
        assert "{host_timezone}" not in result

    def test_host_timezone_fallback_to_utc(self, tmp_path: Path) -> None:
        """When get_iana_timezone returns None, falls back to UTC."""
        mc_dir = tmp_path / ".nanobot" / "mc"
        mc_dir.mkdir(parents=True)
        (mc_dir / "agent-orientation.md").write_text(
            "TZ: {host_timezone}", encoding="utf-8"
        )

        with patch("mc.infrastructure.orientation.Path") as mock_path_cls, \
             patch(
                 "mc.infrastructure.orientation_helpers.get_iana_timezone",
                 return_value=None,
             ):
            mock_path_cls.home.return_value = tmp_path
            result = load_orientation("test-agent")

        assert result is not None
        assert "UTC" in result
