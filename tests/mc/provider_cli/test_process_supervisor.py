"""Tests for ProviderProcessSupervisor."""

from __future__ import annotations

import asyncio
import signal

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
