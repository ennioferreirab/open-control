"""Lifecycle CLI tests for Mission Control startup flags."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

from typer.testing import CliRunner

from mc.cli import mc_app

runner = CliRunner()


class _FakeProcessManager:
    instances: ClassVar[list[_FakeProcessManager]] = []

    def __init__(
        self,
        dashboard_dir: str | Path,
        project_root: str | Path | None = None,
        convex_mode: str = "local",
        on_crash=None,
    ):
        self.dashboard_dir = str(dashboard_dir)
        self.project_root = None if project_root is None else str(project_root)
        self.convex_mode = convex_mode
        self.on_crash = on_crash
        self.started = False
        self.stopped = False
        self.waited = False
        self.__class__.instances.append(self)

    async def start(self) -> None:
        self.started = True

    async def wait(self) -> None:
        self.waited = True

    async def stop(self) -> None:
        self.stopped = True


def test_start_defaults_to_local_convex(tmp_path) -> None:
    dashboard = tmp_path / "dashboard"
    dashboard.mkdir()
    (dashboard / "package.json").write_text("{}")
    fake_pid = tmp_path / "mc.pid"

    _FakeProcessManager.instances.clear()

    with (
        patch("mc.cli.PID_FILE", fake_pid),
        patch("mc.cli._find_dashboard_dir", return_value=dashboard),
        patch("mc.cli.lifecycle._kill_stale_processes"),
        patch("mc.cli.process_manager.ProcessManager", _FakeProcessManager),
    ):
        result = runner.invoke(mc_app, ["start"])

    assert result.exit_code == 0
    assert len(_FakeProcessManager.instances) == 1
    assert _FakeProcessManager.instances[0].convex_mode == "local"


def test_start_local_mode_skips_cloud_bootstrap_bridge(tmp_path) -> None:
    dashboard = tmp_path / "dashboard"
    dashboard.mkdir()
    (dashboard / "package.json").write_text("{}")
    fake_pid = tmp_path / "mc.pid"

    _FakeProcessManager.instances.clear()

    with (
        patch("mc.cli.PID_FILE", fake_pid),
        patch("mc.cli._find_dashboard_dir", return_value=dashboard),
        patch("mc.cli.lifecycle._kill_stale_processes"),
        patch("mc.cli.process_manager.ProcessManager", _FakeProcessManager),
        patch("mc.cli._get_bridge") as get_bridge,
    ):
        result = runner.invoke(mc_app, ["start"])

    assert result.exit_code == 0
    get_bridge.assert_not_called()


def test_start_accepts_cloud_override(tmp_path) -> None:
    dashboard = tmp_path / "dashboard"
    dashboard.mkdir()
    (dashboard / "package.json").write_text("{}")
    fake_pid = tmp_path / "mc.pid"

    _FakeProcessManager.instances.clear()

    with (
        patch("mc.cli.PID_FILE", fake_pid),
        patch("mc.cli._find_dashboard_dir", return_value=dashboard),
        patch("mc.cli.lifecycle._kill_stale_processes"),
        patch("mc.cli.process_manager.ProcessManager", _FakeProcessManager),
    ):
        result = runner.invoke(mc_app, ["start", "--cloud"])

    assert result.exit_code == 0
    assert len(_FakeProcessManager.instances) == 1
    assert _FakeProcessManager.instances[0].convex_mode == "cloud"


def test_start_cloud_mode_runs_bootstrap_bridge(tmp_path) -> None:
    dashboard = tmp_path / "dashboard"
    dashboard.mkdir()
    (dashboard / "package.json").write_text("{}")
    fake_pid = tmp_path / "mc.pid"

    class _FakeBridge:
        def close(self) -> None:
            return None

    _FakeProcessManager.instances.clear()

    with (
        patch("mc.cli.PID_FILE", fake_pid),
        patch("mc.cli._find_dashboard_dir", return_value=dashboard),
        patch("mc.cli.lifecycle._kill_stale_processes"),
        patch("mc.cli.process_manager.ProcessManager", _FakeProcessManager),
        patch("mc.cli._get_bridge", return_value=_FakeBridge()) as get_bridge,
        patch("mc.infrastructure.agent_bootstrap.sync_nanobot_default_model", return_value=False),
    ):
        result = runner.invoke(mc_app, ["start", "--cloud"])

    assert result.exit_code == 0
    get_bridge.assert_called_once()


def test_start_rejects_conflicting_convex_mode_flags(tmp_path) -> None:
    dashboard = tmp_path / "dashboard"
    dashboard.mkdir()
    (dashboard / "package.json").write_text("{}")
    fake_pid = tmp_path / "mc.pid"

    with (
        patch("mc.cli.PID_FILE", fake_pid),
        patch("mc.cli._find_dashboard_dir", return_value=dashboard),
        patch("mc.cli.lifecycle._kill_stale_processes"),
    ):
        result = runner.invoke(mc_app, ["start", "--local", "--cloud"])

    assert result.exit_code == 1
    assert "Choose only one of --local or --cloud" in result.output
