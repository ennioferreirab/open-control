"""Unit tests for ProcessManager."""

import asyncio
import signal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.cli.process_manager import (
    SHUTDOWN_TIMEOUT_SECONDS,
    STARTUP_TIMEOUT_SECONDS,
    ManagedProcess,
    ProcessConfig,
    ProcessManager,
)


def _make_mock_process(pid: int = 12345, returncode=None):
    """Create a mock asyncio subprocess."""
    proc = AsyncMock(spec=asyncio.subprocess.Process)
    proc.pid = pid
    proc.returncode = returncode
    proc.stdout = AsyncMock()
    proc.stdout.readline = AsyncMock(return_value=b"")
    proc.terminate = MagicMock()
    proc.kill = MagicMock()

    async def _wait():
        proc.returncode = 0
        return 0

    proc.wait = AsyncMock(side_effect=_wait)
    return proc


@pytest.fixture
def dashboard_dir(tmp_path):
    """Create a temporary dashboard directory."""
    d = tmp_path / "dashboard"
    d.mkdir()
    return str(d)


@pytest.fixture
def project_root(tmp_path):
    """Return project root (parent of dashboard)."""
    return str(tmp_path)


@pytest.mark.asyncio
async def test_startup_order(dashboard_dir, project_root):
    """Processes start in correct order: dashboard (npm), gateway (python mc.gateway), nanobot."""
    spawn_order = []

    async def mock_create_subprocess(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("program", "")
        spawn_order.append(cmd)
        return _make_mock_process()

    with patch(
        "mc.cli.process_manager.asyncio.create_subprocess_exec",
        side_effect=mock_create_subprocess,
    ):
        pm = ProcessManager(dashboard_dir, project_root)
        await pm.start()

        assert len(spawn_order) == 3
        assert spawn_order[0] == "npm"        # Dashboard first
        assert "python" in spawn_order[1]     # Gateway (mc.gateway) second
        assert "python" in spawn_order[2]     # Nanobot gateway third

        await pm.stop()


@pytest.mark.asyncio
async def test_process_configs(dashboard_dir, project_root):
    """Process configs have correct labels, commands, and working dirs."""
    pm = ProcessManager(dashboard_dir, project_root)
    configs = pm._get_process_configs()

    assert len(configs) == 3

    assert configs[0].label == "dashboard"
    assert configs[0].command == "npm"
    assert configs[0].args == ["run", "dev"]
    assert configs[0].cwd == dashboard_dir

    assert configs[1].label == "gateway"
    assert configs[1].args == ["-m", "mc.gateway"]
    assert configs[1].cwd == project_root

    assert configs[2].label == "nanobot"
    assert configs[2].args == ["-m", "nanobot", "gateway"]
    assert configs[2].cwd == project_root


@pytest.mark.asyncio
async def test_shutdown_reverse_order(dashboard_dir, project_root):
    """Processes are terminated in reverse startup order."""
    terminate_order = []
    pids = iter([100, 200, 300])

    async def mock_create_subprocess(*args, **kwargs):
        pid = next(pids)
        proc = _make_mock_process(pid=pid)

        original_terminate = proc.terminate

        def tracked_terminate():
            terminate_order.append(pid)
            proc.returncode = 0

        proc.terminate = MagicMock(side_effect=tracked_terminate)
        return proc

    with patch(
        "mc.cli.process_manager.asyncio.create_subprocess_exec",
        side_effect=mock_create_subprocess,
    ):
        pm = ProcessManager(dashboard_dir, project_root)
        await pm.start()
        await pm.stop()

    # Reverse of startup: nanobot (300), gateway (200), dashboard (100)
    assert terminate_order == [300, 200, 100]


@pytest.mark.asyncio
async def test_force_kill_after_timeout(dashboard_dir, project_root):
    """Process that doesn't exit within timeout is force-killed."""
    killed = []

    async def mock_create_subprocess(*args, **kwargs):
        proc = _make_mock_process()
        proc._was_killed = False

        async def stubborn_wait():
            if not proc._was_killed:
                # Simulate a process that never exits on SIGTERM
                await asyncio.sleep(999)
            return proc.returncode

        proc.wait = AsyncMock(side_effect=stubborn_wait)

        def track_terminate():
            pass  # Process doesn't actually terminate

        proc.terminate = MagicMock(side_effect=track_terminate)

        def track_kill():
            killed.append(True)
            proc.returncode = -9
            proc._was_killed = True

        proc.kill = MagicMock(side_effect=track_kill)
        return proc

    with patch(
        "mc.cli.process_manager.asyncio.create_subprocess_exec",
        side_effect=mock_create_subprocess,
    ), patch(
        "mc.cli.process_manager.SHUTDOWN_TIMEOUT_SECONDS", 0.3
    ):
        pm = ProcessManager(dashboard_dir, project_root)
        await pm.start()
        results = await pm.stop()

    # All 3 processes should have been force-killed
    assert len(killed) == 3
    assert all(v == "killed" for v in results.values())


@pytest.mark.asyncio
async def test_crash_callback(dashboard_dir, project_root):
    """on_crash callback is invoked when process exits unexpectedly."""
    crash_reports = []

    async def on_crash(label: str, exit_code: int):
        crash_reports.append((label, exit_code))

    procs = []

    async def mock_create_subprocess(*args, **kwargs):
        proc = _make_mock_process()
        procs.append(proc)
        return proc

    with patch(
        "mc.cli.process_manager.asyncio.create_subprocess_exec",
        side_effect=mock_create_subprocess,
    ):
        pm = ProcessManager(dashboard_dir, project_root, on_crash=on_crash)
        await pm.start()

        # Simulate the second process (gateway) crashing — it is critical
        procs[1].returncode = 1

        # Give the monitor loop time to detect the crash
        await asyncio.sleep(1.5)

        assert len(crash_reports) == 1
        assert crash_reports[0] == ("gateway", 1)

        await pm.stop()


@pytest.mark.asyncio
async def test_startup_timeout(dashboard_dir, project_root):
    """Startup times out if a process takes too long."""

    async def slow_create_subprocess(*args, **kwargs):
        # Simulate very slow startup
        await asyncio.sleep(999)
        return _make_mock_process()

    with patch(
        "mc.cli.process_manager.asyncio.create_subprocess_exec",
        side_effect=slow_create_subprocess,
    ), patch(
        "mc.cli.process_manager.STARTUP_TIMEOUT_SECONDS", 0.2
    ):
        pm = ProcessManager(dashboard_dir, project_root)
        with pytest.raises(RuntimeError, match="Startup failed"):
            await pm.start()


@pytest.mark.asyncio
async def test_output_forwarding(dashboard_dir, project_root, capsys):
    """Child stdout is forwarded with process label prefix."""
    call_count = 0

    async def mock_create_subprocess(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        proc = _make_mock_process()
        if call_count == 1:
            # First process (dashboard) gets custom output
            lines = iter([b"hello world\n", b"second line\n", b""])
            proc.stdout.readline = AsyncMock(
                side_effect=lambda: next(lines, b"")
            )
        # Other processes use default (returns b"" immediately)
        return proc

    with patch(
        "mc.cli.process_manager.asyncio.create_subprocess_exec",
        side_effect=mock_create_subprocess,
    ):
        pm = ProcessManager(dashboard_dir, project_root)
        await pm.start()

        # Give time for output forwarding tasks to process
        await asyncio.sleep(0.2)

        # Check that stderr output includes process label prefix
        # _forward_output uses print(..., file=sys.stderr) to pipe child output
        captured = capsys.readouterr()
        assert "[dashboard] hello world" in captured.err
        assert "[dashboard] second line" in captured.err

        await pm.stop()


@pytest.mark.asyncio
async def test_is_running_property(dashboard_dir, project_root):
    """is_running reflects whether all processes are alive."""
    async def mock_create_subprocess(*args, **kwargs):
        return _make_mock_process()

    with patch(
        "mc.cli.process_manager.asyncio.create_subprocess_exec",
        side_effect=mock_create_subprocess,
    ):
        pm = ProcessManager(dashboard_dir, project_root)
        assert pm.is_running is False

        await pm.start()
        assert pm.is_running is True

        await pm.stop()
        assert pm.is_running is False


@pytest.mark.asyncio
async def test_double_start_raises(dashboard_dir, project_root):
    """Starting an already-running ProcessManager raises RuntimeError."""
    async def mock_create_subprocess(*args, **kwargs):
        return _make_mock_process()

    with patch(
        "mc.cli.process_manager.asyncio.create_subprocess_exec",
        side_effect=mock_create_subprocess,
    ):
        pm = ProcessManager(dashboard_dir, project_root)
        await pm.start()

        with pytest.raises(RuntimeError, match="already running"):
            await pm.start()

        await pm.stop()


@pytest.mark.asyncio
async def test_immediate_exit_aborts_startup(dashboard_dir, project_root):
    """If a process exits immediately, startup is aborted."""
    async def mock_create_subprocess(*args, **kwargs):
        proc = _make_mock_process()
        proc.returncode = 1  # Already exited
        return proc

    with patch(
        "mc.cli.process_manager.asyncio.create_subprocess_exec",
        side_effect=mock_create_subprocess,
    ):
        pm = ProcessManager(dashboard_dir, project_root)
        with pytest.raises(RuntimeError, match="Startup failed"):
            await pm.start()


@pytest.mark.asyncio
async def test_default_project_root(tmp_path):
    """project_root defaults to parent of dashboard_dir."""
    dashboard = tmp_path / "project" / "dashboard"
    dashboard.mkdir(parents=True)

    pm = ProcessManager(str(dashboard))
    assert pm._project_root == str(tmp_path / "project")
