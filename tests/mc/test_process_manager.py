"""Unit tests for ProcessManager."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.cli.process_manager import ProcessConfig, ProcessManager


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
    """Processes start in correct order: convex, dashboard, gateway, nanobot."""
    spawn_order = []

    async def mock_create_subprocess(*args, **kwargs):
        spawn_order.append(tuple(args))
        return _make_mock_process()

    with patch(
        "mc.cli.process_manager.asyncio.create_subprocess_exec",
        side_effect=mock_create_subprocess,
    ):
        pm = ProcessManager(dashboard_dir, project_root)
        pm._kill_port = AsyncMock()
        await pm.start()

        assert len(spawn_order) == 4
        assert spawn_order[0][:3] == ("npm", "run", "dev:backend")
        assert spawn_order[1][:3] == ("npm", "run", "dev:frontend")
        assert "python" in spawn_order[2][0]
        assert spawn_order[2][1:] == ("-m", "mc.runtime.gateway")
        assert "python" in spawn_order[3][0]
        assert spawn_order[3][1:] == ("-m", "nanobot", "gateway")

        await pm.stop()


@pytest.mark.asyncio
async def test_process_configs(dashboard_dir, project_root):
    """Process configs have correct labels, commands, and working dirs."""
    pm = ProcessManager(dashboard_dir, project_root)
    configs = pm._get_process_configs()

    assert len(configs) == 4

    assert configs[0].label == "convex"
    assert configs[0].command == "npm"
    assert configs[0].args == ["run", "dev:backend", "--", "--local", "--local-force-upgrade"]
    assert configs[0].cwd == dashboard_dir

    assert configs[1].label == "dashboard"
    assert configs[1].command == "npm"
    assert configs[1].args == ["run", "dev:frontend"]
    assert configs[1].cwd == dashboard_dir

    assert configs[2].label == "gateway"
    assert configs[2].args == ["-m", "mc.runtime.gateway"]
    assert configs[2].cwd == project_root

    assert configs[3].label == "nanobot"
    assert configs[3].args == ["-m", "nanobot", "gateway"]
    assert configs[3].cwd == project_root


@pytest.mark.asyncio
async def test_process_configs_cloud_mode(dashboard_dir, project_root):
    """Cloud mode keeps the Convex backend on the hosted dev deployment."""
    pm = ProcessManager(dashboard_dir, project_root, convex_mode="cloud")
    configs = pm._get_process_configs()

    assert configs[0].label == "convex"
    assert configs[0].command == "npm"
    assert configs[0].args == ["run", "dev:backend"]


@pytest.mark.asyncio
async def test_startup_cleans_port_before_spawning_port_bound_process(dashboard_dir, project_root):
    """Startup proactively clears configured ports before spawning the process."""
    spawn_order = []
    killed_ports = []

    async def mock_create_subprocess(*args, **kwargs):
        spawn_order.append(tuple(args))
        return _make_mock_process()

    async def mock_kill_port(port: int):
        killed_ports.append(port)

    with patch(
        "mc.cli.process_manager.asyncio.create_subprocess_exec",
        side_effect=mock_create_subprocess,
    ):
        pm = ProcessManager(dashboard_dir, project_root)
        pm._kill_port = mock_kill_port

        await pm.start()
        await pm.stop()

    assert killed_ports == [3210]
    assert spawn_order[0][:3] == ("npm", "run", "dev:backend")


@pytest.mark.asyncio
async def test_local_mode_injects_local_convex_env_for_python_processes(
    dashboard_dir, project_root
):
    """Gateway and nanobot inherit local Convex URL and admin key when available."""
    dashboard_path = Path(dashboard_dir)
    (dashboard_path / ".env.local").write_text('NEXT_PUBLIC_CONVEX_URL="http://127.0.0.1:3210"\n')
    local_config = dashboard_path / ".convex" / "local" / "default"
    local_config.mkdir(parents=True)
    (local_config / "config.json").write_text('{"adminKey":"local-admin-key-123"}')

    spawned: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def mock_create_subprocess(*args, **kwargs):
        spawned.append((args, kwargs))
        return _make_mock_process()

    with patch(
        "mc.cli.process_manager.asyncio.create_subprocess_exec",
        side_effect=mock_create_subprocess,
    ):
        pm = ProcessManager(dashboard_dir, project_root)
        await pm.start()
        await pm.stop()

    gateway_env = spawned[2][1]["env"]
    nanobot_env = spawned[3][1]["env"]

    assert gateway_env["CONVEX_URL"] == "http://127.0.0.1:3210"
    assert gateway_env["CONVEX_ADMIN_KEY"] == "local-admin-key-123"
    assert nanobot_env["CONVEX_URL"] == "http://127.0.0.1:3210"
    assert nanobot_env["CONVEX_ADMIN_KEY"] == "local-admin-key-123"


@pytest.mark.asyncio
async def test_shutdown_reverse_order(dashboard_dir, project_root):
    """Processes are terminated in reverse startup order."""
    terminate_order = []
    pids = iter([100, 200, 300, 400])
    pid_to_proc = {}

    async def mock_create_subprocess(*args, **kwargs):
        pid = next(pids)
        proc = _make_mock_process(pid=pid)
        pid_to_proc[pid] = proc
        return proc

    def mock_killpg(pgid, sig):
        if pgid in pid_to_proc:
            terminate_order.append(pgid)
            pid_to_proc[pgid].returncode = 0

    with (
        patch(
            "mc.cli.process_manager.asyncio.create_subprocess_exec",
            side_effect=mock_create_subprocess,
        ),
        patch("mc.cli.process_manager.os.killpg", side_effect=mock_killpg),
    ):
        pm = ProcessManager(dashboard_dir, project_root)
        pm._kill_port = AsyncMock()
        await pm.start()
        await pm.stop()

    # Reverse of startup: nanobot (400), gateway (300), dashboard (200), convex (100)
    assert terminate_order == [400, 300, 200, 100]


@pytest.mark.asyncio
@pytest.mark.slow
async def test_force_kill_after_timeout(dashboard_dir, project_root):
    """Process that doesn't exit within timeout is force-killed."""
    killed = []
    pid_to_proc = {}

    async def mock_create_subprocess(*args, **kwargs):
        proc = _make_mock_process()
        proc._was_killed = False
        pid_to_proc[proc.pid] = proc

        async def stubborn_wait():
            if not proc._was_killed:
                # Simulate a process that never exits on SIGTERM
                await asyncio.sleep(999)
            return proc.returncode

        proc.wait = AsyncMock(side_effect=stubborn_wait)
        return proc

    import signal

    def mock_killpg(pgid, sig):
        if pgid in pid_to_proc:
            proc = pid_to_proc[pgid]
            if sig == signal.SIGKILL:
                killed.append(True)
                proc.returncode = -9
                proc._was_killed = True
            # SIGTERM: process doesn't actually terminate

    with (
        patch(
            "mc.cli.process_manager.asyncio.create_subprocess_exec",
            side_effect=mock_create_subprocess,
        ),
        patch("mc.cli.process_manager.SHUTDOWN_TIMEOUT_SECONDS", 0.3),
        patch("mc.cli.process_manager.os.killpg", side_effect=mock_killpg),
    ):
        pm = ProcessManager(dashboard_dir, project_root)
        await pm.start()
        results = await pm.stop()

    # All 4 processes should have been force-killed
    assert len(killed) == 4
    assert all(v == "killed" for v in results.values())


@pytest.mark.asyncio
@pytest.mark.slow
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

    with (
        patch(
            "mc.cli.process_manager.asyncio.create_subprocess_exec",
            side_effect=mock_create_subprocess,
        ),
        patch("mc.cli.process_manager.os.killpg", side_effect=lambda *a: None),
    ):
        pm = ProcessManager(dashboard_dir, project_root, on_crash=on_crash)
        pm._kill_port = AsyncMock()
        await pm.start()

        # Simulate the third process (gateway) crashing — it is critical
        procs[2].returncode = 1

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

    with (
        patch(
            "mc.cli.process_manager.asyncio.create_subprocess_exec",
            side_effect=slow_create_subprocess,
        ),
        patch("mc.cli.process_manager.STARTUP_TIMEOUT_SECONDS", 0.2),
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
            # First process (convex) gets custom output
            lines = iter([b"hello world\n", b"second line\n", b""])
            proc.stdout.readline = AsyncMock(side_effect=lambda: next(lines, b""))
        # Other processes use default (returns b"" immediately)
        return proc

    with patch(
        "mc.cli.process_manager.asyncio.create_subprocess_exec",
        side_effect=mock_create_subprocess,
    ):
        pm = ProcessManager(dashboard_dir, project_root)
        pm._kill_port = AsyncMock()
        await pm.start()

        # Give time for output forwarding tasks to process
        await asyncio.sleep(0.2)

        # Check that stderr output includes process label prefix
        # _forward_output uses print(..., file=sys.stderr) to pipe child output
        captured = capsys.readouterr()
        assert "[convex] hello world" in captured.err
        assert "[convex] second line" in captured.err

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


# --- Max restart attempts & port cleanup ---


def test_process_config_has_max_restart_attempts_and_port():
    """ProcessConfig exposes max_restart_attempts and port fields."""
    cfg = ProcessConfig(
        label="test",
        command="echo",
        args=["hi"],
        cwd="/tmp",
        restart_on_crash=True,
        max_restart_attempts=3,
        port=3210,
    )
    assert cfg.max_restart_attempts == 3
    assert cfg.port == 3210


def test_process_config_defaults():
    """max_restart_attempts defaults to 5, port defaults to None."""
    cfg = ProcessConfig(label="x", command="x", args=[], cwd="/tmp")
    assert cfg.max_restart_attempts == 5
    assert cfg.port is None


@pytest.mark.asyncio
@pytest.mark.slow
async def test_monitor_stops_restarting_after_max_attempts(dashboard_dir, project_root):
    """After max_restart_attempts consecutive failures, monitor stops restarting."""
    max_attempts = 2
    crash_reports: list[tuple[str, int]] = []

    async def on_crash(label: str, exit_code: int) -> None:
        crash_reports.append((label, exit_code))

    async def mock_create_subprocess(*args, **kwargs):
        return _make_mock_process()

    async def noop_kill_port(port: int) -> None:
        pass

    with (
        patch(
            "mc.cli.process_manager.asyncio.create_subprocess_exec",
            side_effect=mock_create_subprocess,
        ),
        patch("mc.cli.process_manager.os.killpg", side_effect=lambda *a: None),
    ):
        pm = ProcessManager(dashboard_dir, project_root, on_crash=on_crash)
        pm._kill_port = noop_kill_port

        original_get_configs = pm._get_process_configs

        def patched_configs():
            configs = original_get_configs()
            configs[0] = ProcessConfig(
                label="convex",
                command=configs[0].command,
                args=configs[0].args,
                cwd=configs[0].cwd,
                env=configs[0].env,
                critical=False,
                restart_on_crash=True,
                max_restart_attempts=max_attempts,
                port=3210,
            )
            return configs

        pm._get_process_configs = patched_configs
        await pm.start()

        # Crash convex — each restart also immediately crashes
        # because we set returncode=1 right after the monitor replaces the process.
        # Attempt 1: crash, backoff 2s, restart, counter=0 (success)
        pm._processes[0].process.returncode = 1
        await asyncio.sleep(3)

        # Attempt 2: crash again
        pm._processes[0].process.returncode = 1
        await asyncio.sleep(3)

        # Verify counter resets on success — still restarting
        assert pm._restart_failures.get("convex", 0) == 0

        # Now make restarts also immediately crash (returncode set at spawn time)
        async def mock_create_crashing_subprocess(*args, **kwargs):
            proc = _make_mock_process()
            proc.returncode = 1  # crashes immediately
            return proc

        with patch(
            "mc.cli.process_manager.asyncio.create_subprocess_exec",
            side_effect=mock_create_crashing_subprocess,
        ):
            pm._processes[0].process.returncode = 1
            # Wait for max_attempts worth of backoff: 2 + 4 + extra buffer
            await asyncio.sleep(10)

        # Should have given up and called on_crash
        assert pm._restart_failures.get("convex", 0) > max_attempts
        assert len(crash_reports) >= 1
        assert crash_reports[0][0] == "convex"

        await pm.stop()


@pytest.mark.asyncio
@pytest.mark.slow
async def test_successful_restart_resets_failure_counter(dashboard_dir, project_root):
    """A successful restart (process stays alive) resets the failure counter."""
    max_attempts = 2

    async def mock_create_subprocess(*args, **kwargs):
        return _make_mock_process()

    with (
        patch(
            "mc.cli.process_manager.asyncio.create_subprocess_exec",
            side_effect=mock_create_subprocess,
        ),
        patch("mc.cli.process_manager.os.killpg", side_effect=lambda *a: None),
    ):
        pm = ProcessManager(dashboard_dir, project_root)

        original_get_configs = pm._get_process_configs

        def patched_configs():
            configs = original_get_configs()
            configs[0] = ProcessConfig(
                label="convex",
                command=configs[0].command,
                args=configs[0].args,
                cwd=configs[0].cwd,
                env=configs[0].env,
                critical=False,
                restart_on_crash=True,
                max_restart_attempts=max_attempts,
            )
            return configs

        pm._get_process_configs = patched_configs
        await pm.start()

        # Crash convex — counter goes to 1, then resets to 0 after successful restart
        pm._processes[0].process.returncode = 1
        await asyncio.sleep(3)  # backoff = 2s for first failure

        # Counter should be 0 (reset after successful restart)
        assert pm._restart_failures.get("convex", 0) == 0

        # Crash again — if counter wasn't reset, this would be attempt 2
        pm._processes[0].process.returncode = 1
        await asyncio.sleep(3)

        # Still 0 after successful restart
        assert pm._restart_failures.get("convex", 0) == 0

        # Crash a third time — proves counter was reset, not accumulated
        pm._processes[0].process.returncode = 1
        await asyncio.sleep(3)

        assert pm._restart_failures.get("convex", 0) == 0

        await pm.stop()


@pytest.mark.asyncio
@pytest.mark.slow
async def test_port_cleanup_before_restart(dashboard_dir, project_root):
    """When a process with port configured crashes, port cleanup runs before restart."""
    killed_ports: list[int] = []

    async def mock_create_subprocess(*args, **kwargs):
        return _make_mock_process()

    async def mock_kill_port(port: int) -> None:
        killed_ports.append(port)

    with (
        patch(
            "mc.cli.process_manager.asyncio.create_subprocess_exec",
            side_effect=mock_create_subprocess,
        ),
        patch("mc.cli.process_manager.os.killpg", side_effect=lambda *a: None),
    ):
        pm = ProcessManager(dashboard_dir, project_root)

        original_get_configs = pm._get_process_configs

        def patched_configs():
            configs = original_get_configs()
            configs[0] = ProcessConfig(
                label="convex",
                command=configs[0].command,
                args=configs[0].args,
                cwd=configs[0].cwd,
                env=configs[0].env,
                critical=False,
                restart_on_crash=True,
                port=3210,
            )
            return configs

        pm._get_process_configs = patched_configs

        # Patch _kill_port on the instance
        pm._kill_port = mock_kill_port

        await pm.start()

        # Crash convex
        pm._processes[0].process.returncode = 1
        await asyncio.sleep(3)  # backoff = 2s for first failure

        assert 3210 in killed_ports

        await pm.stop()


@pytest.mark.asyncio
async def test_convex_config_has_port_3210(dashboard_dir, project_root):
    """The default convex ProcessConfig has port=3210."""
    pm = ProcessManager(dashboard_dir, project_root)
    configs = pm._get_process_configs()
    convex = configs[0]
    assert convex.port == 3210
