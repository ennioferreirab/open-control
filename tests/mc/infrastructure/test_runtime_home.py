"""Tests for mc.infrastructure.runtime_home — env var resolution and path helpers."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def reset_runtime_home_cache() -> None:
    """Reset the runtime_home module cache before each test.

    runtime_home.py caches the resolved path in module-level globals.
    Tests must clear this cache so env var changes take effect.
    """
    import mc.infrastructure.runtime_home as runtime_home

    runtime_home._resolved = None
    runtime_home._resolved_from_env = None
    yield
    runtime_home._resolved = None
    runtime_home._resolved_from_env = None


class TestDefaultResolution:
    """Default path when no env vars are set."""

    def test_default_resolves_to_nanobot(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without any env var, runtime home resolves to ~/.nanobot."""
        from mc.infrastructure.runtime_home import get_runtime_home

        monkeypatch.delenv("OPEN_CONTROL_HOME", raising=False)
        monkeypatch.delenv("NANOBOT_HOME", raising=False)

        assert get_runtime_home() == Path.home() / ".nanobot"


class TestOpenControlHomeOverride:
    """OPEN_CONTROL_HOME env var override."""

    def test_open_control_home_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OPEN_CONTROL_HOME env var sets the runtime home."""
        from mc.infrastructure.runtime_home import get_runtime_home

        custom = str(tmp_path / "my-control")
        monkeypatch.setenv("OPEN_CONTROL_HOME", custom)
        monkeypatch.delenv("NANOBOT_HOME", raising=False)

        assert get_runtime_home() == Path(custom)


class TestNanobotHomeOverride:
    """NANOBOT_HOME legacy env var override."""

    def test_nanobot_home_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """NANOBOT_HOME env var sets the runtime home when OPEN_CONTROL_HOME is absent."""
        from mc.infrastructure.runtime_home import get_runtime_home

        legacy = str(tmp_path / "legacy-home")
        monkeypatch.delenv("OPEN_CONTROL_HOME", raising=False)
        monkeypatch.setenv("NANOBOT_HOME", legacy)

        assert get_runtime_home() == Path(legacy)


class TestPrecedence:
    """OPEN_CONTROL_HOME takes precedence over NANOBOT_HOME."""

    def test_open_control_home_takes_precedence(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When both env vars are set, OPEN_CONTROL_HOME wins."""
        from mc.infrastructure.runtime_home import get_runtime_home

        open_control = str(tmp_path / "open-control")
        nanobot = str(tmp_path / "nanobot")
        monkeypatch.setenv("OPEN_CONTROL_HOME", open_control)
        monkeypatch.setenv("NANOBOT_HOME", nanobot)

        result = get_runtime_home()

        assert result == Path(open_control)
        assert result != Path(nanobot)


class TestHelperFunctions:
    """Helper functions return correct subpaths under the runtime home."""

    def test_get_agents_dir_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_agents_dir returns <runtime_home>/agents."""
        from mc.infrastructure.runtime_home import get_agents_dir, get_runtime_home

        monkeypatch.delenv("OPEN_CONTROL_HOME", raising=False)
        monkeypatch.delenv("NANOBOT_HOME", raising=False)

        assert get_agents_dir() == get_runtime_home() / "agents"

    def test_get_tasks_dir_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_tasks_dir returns <runtime_home>/tasks."""
        from mc.infrastructure.runtime_home import get_runtime_home, get_tasks_dir

        monkeypatch.delenv("OPEN_CONTROL_HOME", raising=False)
        monkeypatch.delenv("NANOBOT_HOME", raising=False)

        assert get_tasks_dir() == get_runtime_home() / "tasks"

    def test_get_boards_dir_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_boards_dir returns <runtime_home>/boards."""
        from mc.infrastructure.runtime_home import get_boards_dir, get_runtime_home

        monkeypatch.delenv("OPEN_CONTROL_HOME", raising=False)
        monkeypatch.delenv("NANOBOT_HOME", raising=False)

        assert get_boards_dir() == get_runtime_home() / "boards"

    def test_get_workspace_dir_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_workspace_dir returns <runtime_home>/workspace."""
        from mc.infrastructure.runtime_home import get_runtime_home, get_workspace_dir

        monkeypatch.delenv("OPEN_CONTROL_HOME", raising=False)
        monkeypatch.delenv("NANOBOT_HOME", raising=False)

        assert get_workspace_dir() == get_runtime_home() / "workspace"

    def test_helper_functions_respect_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Helper functions resolve subpaths under the overridden runtime home."""
        from mc.infrastructure.runtime_home import (
            get_agents_dir,
            get_boards_dir,
            get_config_path,
            get_secrets_path,
            get_tasks_dir,
            get_workspace_dir,
        )

        root = str(tmp_path / "custom-root")
        monkeypatch.setenv("OPEN_CONTROL_HOME", root)
        monkeypatch.delenv("NANOBOT_HOME", raising=False)

        root_path = Path(root)
        assert get_agents_dir() == root_path / "agents"
        assert get_tasks_dir() == root_path / "tasks"
        assert get_boards_dir() == root_path / "boards"
        assert get_workspace_dir() == root_path / "workspace"
        assert get_config_path() == root_path / "config.json"
        assert get_secrets_path() == root_path / "secrets.json"
