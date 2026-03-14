"""Tests for ProviderCLIParser protocol conformance."""

from __future__ import annotations

from typing import Any

from mc.contexts.provider_cli.parser import ProviderCLIParser
from mc.contexts.provider_cli.types import (
    ParsedCliEvent,
    ProviderProcessHandle,
    ProviderSessionSnapshot,
)


class _ConcreteParser:
    """Minimal concrete implementation that satisfies ProviderCLIParser."""

    provider_name: str = "test-provider"

    async def start_session(
        self,
        mc_session_id: str,
        command: list[str],
        cwd: str,
        env: dict[str, str] | None = None,
    ) -> ProviderProcessHandle:
        return ProviderProcessHandle(
            mc_session_id=mc_session_id,
            provider=self.provider_name,
            pid=12345,
            pgid=12345,
            cwd=cwd,
            command=command,
            started_at="2024-01-01T00:00:00Z",
        )

    def parse_output(self, chunk: bytes) -> list[ParsedCliEvent]:
        return [ParsedCliEvent(kind="output", text=chunk.decode("utf-8", errors="replace"))]

    async def discover_session(self, handle: ProviderProcessHandle) -> ProviderSessionSnapshot:
        return ProviderSessionSnapshot(
            mc_session_id=handle.mc_session_id,
            provider_session_id=None,
            mode="runtime-owned",
            supports_resume=False,
            supports_interrupt=True,
            supports_stop=True,
        )

    async def inspect_process_tree(self, handle: ProviderProcessHandle) -> dict[str, Any]:
        return {"pid": handle.pid, "children": []}

    async def interrupt(self, handle: ProviderProcessHandle) -> None:
        pass

    async def resume(self, handle: ProviderProcessHandle, message: str) -> None:
        pass

    async def stop(self, handle: ProviderProcessHandle) -> None:
        pass


class TestProviderCLIParserProtocol:
    def test_concrete_class_is_instance_of_protocol(self) -> None:
        """A class implementing all required methods satisfies ProviderCLIParser."""
        parser = _ConcreteParser()
        # isinstance check works for runtime_checkable Protocol only,
        # but we validate structural conformance by calling all methods below
        assert hasattr(parser, "provider_name")
        assert callable(parser.parse_output)
        assert callable(parser.start_session)
        assert callable(parser.discover_session)
        assert callable(parser.inspect_process_tree)
        assert callable(parser.interrupt)
        assert callable(parser.resume)
        assert callable(parser.stop)

    def test_parse_output_returns_list_of_events(self) -> None:
        parser = _ConcreteParser()
        events = parser.parse_output(b"hello world")
        assert isinstance(events, list)
        assert len(events) == 1
        assert events[0].kind == "output"
        assert events[0].text == "hello world"

    def test_parse_output_empty_chunk(self) -> None:
        parser = _ConcreteParser()
        events = parser.parse_output(b"")
        assert isinstance(events, list)

    async def test_start_session_returns_handle(self) -> None:
        parser = _ConcreteParser()
        handle = await parser.start_session(
            mc_session_id="s1",
            command=["test-cli"],
            cwd="/tmp",
        )
        assert isinstance(handle, ProviderProcessHandle)
        assert handle.mc_session_id == "s1"
        assert handle.provider == "test-provider"

    async def test_discover_session_returns_snapshot(self) -> None:
        parser = _ConcreteParser()
        handle = ProviderProcessHandle(
            mc_session_id="s1",
            provider="test-provider",
            pid=9999,
            pgid=9999,
            cwd="/tmp",
            command=["test-cli"],
            started_at="2024-01-01T00:00:00Z",
        )
        snapshot = await parser.discover_session(handle)
        assert isinstance(snapshot, ProviderSessionSnapshot)
        assert snapshot.mc_session_id == "s1"

    async def test_inspect_process_tree_returns_dict(self) -> None:
        parser = _ConcreteParser()
        handle = ProviderProcessHandle(
            mc_session_id="s1",
            provider="test-provider",
            pid=9999,
            pgid=9999,
            cwd="/tmp",
            command=["test-cli"],
            started_at="2024-01-01T00:00:00Z",
        )
        result = await parser.inspect_process_tree(handle)
        assert isinstance(result, dict)

    async def test_interrupt_resume_stop_are_coroutines(self) -> None:
        parser = _ConcreteParser()
        handle = ProviderProcessHandle(
            mc_session_id="s1",
            provider="test-provider",
            pid=9999,
            pgid=9999,
            cwd="/tmp",
            command=["test-cli"],
            started_at="2024-01-01T00:00:00Z",
        )
        # These should be awaitable (no error means they work)
        await parser.interrupt(handle)
        await parser.resume(handle, "continue")
        await parser.stop(handle)

    def test_protocol_is_importable_from_package(self) -> None:
        from mc.contexts.provider_cli import ProviderCLIParser as PackageExport

        assert PackageExport is ProviderCLIParser
