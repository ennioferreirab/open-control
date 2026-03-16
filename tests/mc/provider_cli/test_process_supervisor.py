"""Tests for ProviderProcessSupervisor."""

from __future__ import annotations

import asyncio
import signal
import sys

from mc.contexts.provider_cli.types import ProviderProcessHandle
from mc.runtime.provider_cli.process_supervisor import ProviderProcessSupervisor


class TestProviderProcessSupervisor:
    async def test_launch_returns_handle_with_valid_pid(self) -> None:
        supervisor = ProviderProcessSupervisor()
        handle = await supervisor.launch(
            mc_session_id="s1",
            provider="test",
            command=["echo", "hello"],
            cwd="/tmp",
        )
        assert isinstance(handle, ProviderProcessHandle)
        assert handle.pid > 0
        assert handle.mc_session_id == "s1"
        assert handle.provider == "test"
        assert handle.cwd == "/tmp"
        assert handle.command == ["echo", "hello"]

    async def test_launch_captures_pgid(self) -> None:
        supervisor = ProviderProcessSupervisor()
        handle = await supervisor.launch(
            mc_session_id="s2",
            provider="test",
            command=["echo", "pgid-test"],
            cwd="/tmp",
        )
        # pgid should be set (on Unix systems)
        assert handle.pgid is not None
        assert handle.pgid > 0

    async def test_launch_started_at_is_iso_string(self) -> None:
        supervisor = ProviderProcessSupervisor()
        handle = await supervisor.launch(
            mc_session_id="s3",
            provider="test",
            command=["echo", "time"],
            cwd="/tmp",
        )
        # started_at should be a non-empty ISO format string
        assert isinstance(handle.started_at, str)
        assert len(handle.started_at) > 0
        assert "T" in handle.started_at or "-" in handle.started_at

    async def test_stream_output_captures_stdout(self) -> None:
        supervisor = ProviderProcessSupervisor()
        handle = await supervisor.launch(
            mc_session_id="s4",
            provider="test",
            command=["echo", "hello provider"],
            cwd="/tmp",
        )
        chunks: list[bytes] = []
        async for chunk in supervisor.stream_output(handle):
            chunks.append(chunk)
        combined = b"".join(chunks)
        assert b"hello provider" in combined

    async def test_stream_output_captures_stderr(self) -> None:
        supervisor = ProviderProcessSupervisor()
        # Use a command that writes to stderr
        handle = await supervisor.launch(
            mc_session_id="s5",
            provider="test",
            command=["bash", "-c", "echo error-output >&2"],
            cwd="/tmp",
        )
        chunks: list[bytes] = []
        async for chunk in supervisor.stream_output(handle):
            chunks.append(chunk)
        combined = b"".join(chunks)
        assert b"error-output" in combined

    async def test_wait_for_exit_returns_exit_code(self) -> None:
        supervisor = ProviderProcessSupervisor()
        handle = await supervisor.launch(
            mc_session_id="s6",
            provider="test",
            command=["bash", "-c", "exit 0"],
            cwd="/tmp",
        )
        # Consume output first
        async for _ in supervisor.stream_output(handle):
            pass
        exit_code = await supervisor.wait_for_exit(handle)
        assert exit_code == 0

    async def test_wait_for_exit_nonzero(self) -> None:
        supervisor = ProviderProcessSupervisor()
        handle = await supervisor.launch(
            mc_session_id="s7",
            provider="test",
            command=["bash", "-c", "exit 42"],
            cwd="/tmp",
        )
        async for _ in supervisor.stream_output(handle):
            pass
        exit_code = await supervisor.wait_for_exit(handle)
        assert exit_code == 42

    async def test_send_signal_interrupt(self) -> None:
        """Interrupt a long-running process."""
        supervisor = ProviderProcessSupervisor()
        handle = await supervisor.launch(
            mc_session_id="s8",
            provider="test",
            command=["bash", "-c", "sleep 60"],
            cwd="/tmp",
        )
        # Give process a moment to start
        await asyncio.sleep(0.1)
        await supervisor.send_signal(handle, signal.SIGTERM)
        exit_code = await supervisor.wait_for_exit(handle)
        assert exit_code is not None  # process ended

    async def test_terminate_kills_process(self) -> None:
        """terminate() sends SIGTERM and the process exits."""
        supervisor = ProviderProcessSupervisor()
        handle = await supervisor.launch(
            mc_session_id="s9",
            provider="test",
            command=["bash", "-c", "sleep 60"],
            cwd="/tmp",
        )
        await asyncio.sleep(0.1)
        await supervisor.terminate(handle)
        exit_code = await supervisor.wait_for_exit(handle)
        assert exit_code is not None

    async def test_kill_kills_process(self) -> None:
        """kill() sends SIGKILL and the process exits."""
        supervisor = ProviderProcessSupervisor()
        handle = await supervisor.launch(
            mc_session_id="s10",
            provider="test",
            command=["bash", "-c", "sleep 60"],
            cwd="/tmp",
        )
        await asyncio.sleep(0.1)
        await supervisor.kill(handle)
        exit_code = await supervisor.wait_for_exit(handle)
        assert exit_code is not None

    async def test_inspect_process_tree_returns_dict_with_pid(self) -> None:
        supervisor = ProviderProcessSupervisor()
        handle = await supervisor.launch(
            mc_session_id="s11",
            provider="test",
            command=["bash", "-c", "sleep 60"],
            cwd="/tmp",
        )
        await asyncio.sleep(0.1)
        tree = await supervisor.inspect_process_tree(handle)
        assert isinstance(tree, dict)
        assert "pid" in tree
        assert tree["pid"] == handle.pid
        # Cleanup
        await supervisor.kill(handle)
        await supervisor.wait_for_exit(handle)

    async def test_launch_with_custom_env(self) -> None:
        """Launch with extra env vars and verify they're passed."""
        supervisor = ProviderProcessSupervisor()
        handle = await supervisor.launch(
            mc_session_id="s12",
            provider="test",
            command=["bash", "-c", "echo $MY_TEST_VAR"],
            cwd="/tmp",
            env={"MY_TEST_VAR": "custom-value"},
        )
        chunks: list[bytes] = []
        async for chunk in supervisor.stream_output(handle):
            chunks.append(chunk)
        combined = b"".join(chunks)
        assert b"custom-value" in combined

    async def test_launch_with_devnull_stdin_allows_process_waiting_for_eof_to_run(self) -> None:
        """A headless provider launch must be able to close stdin at startup."""
        supervisor = ProviderProcessSupervisor()
        handle = await supervisor.launch(
            mc_session_id="s12-devnull",
            provider="test",
            command=[
                sys.executable,
                "-c",
                "import sys; sys.stdin.read(); print('stdin-closed')",
            ],
            cwd="/tmp",
            stdin_mode="devnull",
        )
        chunks: list[bytes] = []
        async for chunk in supervisor.stream_output(handle):
            chunks.append(chunk)
        combined = b"".join(chunks)
        assert b"stdin-closed" in combined

    async def test_launch_inherits_env_when_none(self) -> None:
        """When env=None, inherit the current process environment."""

        supervisor = ProviderProcessSupervisor()
        # HOME is always set in normal environments
        handle = await supervisor.launch(
            mc_session_id="s13",
            provider="test",
            command=["bash", "-c", "echo $HOME"],
            cwd="/tmp",
            env=None,
        )
        chunks: list[bytes] = []
        async for chunk in supervisor.stream_output(handle):
            chunks.append(chunk)
        combined = b"".join(chunks)
        # HOME should be present (non-empty output)
        assert len(combined.strip()) > 0

    # ---------------------------------------------------------------------------
    # Process lifecycle (Story 28-9 coverage)
    # ---------------------------------------------------------------------------

    async def test_launch_creates_subprocess_handle(self) -> None:
        """launch() must return a real ProviderProcessHandle with a live process."""
        supervisor = ProviderProcessSupervisor()
        handle = await supervisor.launch(
            mc_session_id="s14-lifecycle",
            provider="claude-code",
            command=["echo", "process-lifecycle"],
            cwd="/tmp",
        )
        # Handle must carry a valid PID (real process was started)
        assert handle.pid > 0
        # The handle must reference the correct session and provider
        assert handle.mc_session_id == "s14-lifecycle"
        assert handle.provider == "claude-code"
        # Drain output and confirm the process exits cleanly
        async for _ in supervisor.stream_output(handle):
            pass
        exit_code = await supervisor.wait_for_exit(handle)
        assert exit_code == 0

    async def test_stream_output_yields_bytes(self) -> None:
        """stream_output must yield raw bytes from the subprocess stdout."""
        supervisor = ProviderProcessSupervisor()
        handle = await supervisor.launch(
            mc_session_id="s15-bytes",
            provider="test",
            command=["echo", "raw-bytes-check"],
            cwd="/tmp",
        )
        first_chunk: bytes | None = None
        async for chunk in supervisor.stream_output(handle):
            first_chunk = chunk
            break  # only need the first chunk

        # At least one chunk must be bytes
        assert isinstance(first_chunk, bytes)

        # Drain remaining output
        async for _ in supervisor.stream_output(handle):
            pass
        await supervisor.wait_for_exit(handle)

    # ---------------------------------------------------------------------------
    # is_alive() — crash detection (Story 28-10)
    # ---------------------------------------------------------------------------

    async def test_is_alive_returns_true_for_running_process(self) -> None:
        """is_alive must return True when the process is still running."""
        supervisor = ProviderProcessSupervisor()
        handle = await supervisor.launch(
            mc_session_id="s16-alive",
            provider="test",
            command=["bash", "-c", "sleep 60"],
            cwd="/tmp",
        )
        await asyncio.sleep(0.05)
        assert supervisor.is_alive(handle) is True
        # Cleanup
        await supervisor.kill(handle)
        await supervisor.wait_for_exit(handle)

    async def test_is_alive_returns_false_for_finished_process(self) -> None:
        """is_alive must return False once the process has exited."""
        supervisor = ProviderProcessSupervisor()
        handle = await supervisor.launch(
            mc_session_id="s17-dead",
            provider="test",
            command=["echo", "done"],
            cwd="/tmp",
        )
        # Drain output and wait for exit
        async for _ in supervisor.stream_output(handle):
            pass
        await supervisor.wait_for_exit(handle)
        assert supervisor.is_alive(handle) is False

    async def test_is_alive_returns_false_for_unknown_session(self) -> None:
        """is_alive must return False for a session ID that was never launched."""
        supervisor = ProviderProcessSupervisor()
        from mc.contexts.provider_cli.types import ProviderProcessHandle

        fake_handle = ProviderProcessHandle(
            mc_session_id="never-launched",
            provider="test",
            pid=99999,
            pgid=99999,
            cwd="/tmp",
            command=["echo"],
            started_at="2026-01-01T00:00:00Z",
        )
        assert supervisor.is_alive(fake_handle) is False
