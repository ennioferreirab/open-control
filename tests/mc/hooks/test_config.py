"""Tests for mc.hooks.config — HookConfig dataclass and helpers."""
from __future__ import annotations

from pathlib import Path

from mc.hooks.config import HookConfig, get_config, get_project_root


class TestHookConfig:
    """Test HookConfig dataclass defaults and immutability."""

    def test_defaults(self):
        config = HookConfig()
        assert config.plan_pattern == "docs/plans/*.md"
        assert config.tracker_dir == ".claude/plan-tracker"
        assert config.state_dir == ".claude/hook-state"

    def test_custom_values(self):
        config = HookConfig(
            plan_pattern="plans/*.md",
            tracker_dir="custom/tracker",
            state_dir="custom/state",
        )
        assert config.plan_pattern == "plans/*.md"
        assert config.tracker_dir == "custom/tracker"
        assert config.state_dir == "custom/state"

    def test_frozen(self):
        """HookConfig is frozen — attribute assignment should raise."""
        config = HookConfig()
        import dataclasses
        with __import__("pytest").raises(dataclasses.FrozenInstanceError):
            config.plan_pattern = "other"  # type: ignore[misc]

    def test_equality(self):
        a = HookConfig()
        b = HookConfig()
        assert a == b

    def test_inequality(self):
        a = HookConfig()
        b = HookConfig(plan_pattern="different/*.md")
        assert a != b


class TestGetConfig:
    """Test the get_config() factory function."""

    def test_returns_hookconfig(self):
        config = get_config()
        assert isinstance(config, HookConfig)

    def test_returns_defaults(self):
        config = get_config()
        assert config == HookConfig()


class TestGetProjectRoot:
    """Test get_project_root() path resolution."""

    def test_returns_path(self):
        root = get_project_root()
        assert isinstance(root, Path)

    def test_is_directory(self):
        root = get_project_root()
        assert root.is_dir()

    def test_contains_mc_hooks(self):
        root = get_project_root()
        assert (root / "mc" / "hooks").is_dir()

    def test_resolves_to_absolute(self):
        root = get_project_root()
        assert root.is_absolute()
