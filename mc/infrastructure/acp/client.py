"""ACP transport-only client wrapping the agent-client-protocol SDK."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import acp
from acp.schema import (
    AgentMessageChunk,
    AllowedOutcome,
    ClientCapabilities,
    CreateTerminalResponse,
    DeniedOutcome,
    EnvVariable,
    Implementation,
    KillTerminalResponse,
    PermissionOption,
    ReadTextFileResponse,
    ReleaseTerminalResponse,
    RequestPermissionResponse,
    TerminalOutputResponse,
    TextContentBlock,
    ToolCallUpdate,
    UsageUpdate,
    WaitForTerminalExitResponse,
    WriteTextFileResponse,
)

from mc.infrastructure.acp.types import AcpTurnResult

logger = logging.getLogger(__name__)

_CLIENT_INFO = Implementation(name="open-control", title="Open Control", version="0.1.0")


@dataclass
class _TurnState:
    """Mutable accumulator for a single prompt turn. Reset before each call."""

    text_chunks: list[str] = field(default_factory=list)
    cost_usd: float | None = None
    on_update: Callable[[Any], None] | None = None

    def assembled_text(self) -> str:
        return "".join(self.text_chunks)


class _AcpAdapter(acp.Client):
    """Internal acp.Client subclass whose methods are captured by the SDK router.

    One instance lives for the entire AcpClient lifetime. Before each prompt()
    call, AcpClient replaces _turn with a fresh _TurnState so chunk accumulation
    and cost tracking never bleeds between turns.

    The router captures bound method references at spawn time, so this instance
    must not be replaced — only its _turn slot is mutated.
    """

    def __init__(self) -> None:
        self._turn = _TurnState()

    async def session_update(
        self,
        session_id: str,
        update: Any,
        **kwargs: Any,
    ) -> None:
        if self._turn.on_update is not None:
            self._turn.on_update(update)

        if isinstance(update, AgentMessageChunk):
            content = update.content
            if isinstance(content, TextContentBlock) and content.text:
                self._turn.text_chunks.append(content.text)
        elif isinstance(update, UsageUpdate):
            if update.cost is not None:
                self._turn.cost_usd = update.cost.amount
        # AvailableCommandsUpdate and other update types reach on_update above
        # but contribute nothing to text assembly.

    async def request_permission(
        self,
        options: list[PermissionOption],
        session_id: str,
        tool_call: ToolCallUpdate,
        **kwargs: Any,
    ) -> RequestPermissionResponse:
        for opt in options:
            if opt.kind in ("allow_once", "allow_always"):
                return RequestPermissionResponse(
                    outcome=AllowedOutcome(outcome="selected", option_id=opt.option_id)
                )
        return RequestPermissionResponse(outcome=DeniedOutcome(outcome="cancelled"))

    async def write_text_file(
        self, content: str, path: str, session_id: str, **kwargs: Any
    ) -> WriteTextFileResponse | None:
        raise acp.RequestError.method_not_found("fs/write_text_file")

    async def read_text_file(
        self,
        path: str,
        session_id: str,
        limit: int | None = None,
        line: int | None = None,
        **kwargs: Any,
    ) -> ReadTextFileResponse:
        raise acp.RequestError.method_not_found("fs/read_text_file")

    async def create_terminal(
        self,
        command: str,
        session_id: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: list[EnvVariable] | None = None,
        output_byte_limit: int | None = None,
        **kwargs: Any,
    ) -> CreateTerminalResponse:
        raise acp.RequestError.method_not_found("terminal/create")

    async def terminal_output(
        self, session_id: str, terminal_id: str, **kwargs: Any
    ) -> TerminalOutputResponse:
        raise acp.RequestError.method_not_found("terminal/output")

    async def release_terminal(
        self, session_id: str, terminal_id: str, **kwargs: Any
    ) -> ReleaseTerminalResponse | None:
        raise acp.RequestError.method_not_found("terminal/release")

    async def wait_for_terminal_exit(
        self, session_id: str, terminal_id: str, **kwargs: Any
    ) -> WaitForTerminalExitResponse:
        raise acp.RequestError.method_not_found("terminal/wait_for_exit")

    async def kill_terminal(
        self, session_id: str, terminal_id: str, **kwargs: Any
    ) -> KillTerminalResponse | None:
        raise acp.RequestError.method_not_found("terminal/kill")

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        raise acp.RequestError.method_not_found(method)

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        pass

    def on_connect(self, conn: Any) -> None:
        pass


def _usage_to_dict(usage: Any) -> dict[str, int]:
    """Convert an acp.schema.Usage object to a plain int-valued dict."""
    if usage is None:
        return {}
    result: dict[str, int] = {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
    }
    if usage.cached_read_tokens is not None:
        result["cached_read_tokens"] = usage.cached_read_tokens
    if usage.cached_write_tokens is not None:
        result["cached_write_tokens"] = usage.cached_write_tokens
    if usage.thought_tokens is not None:
        result["thought_tokens"] = usage.thought_tokens
    return result


class AcpClient:
    """Transport-only wrapper for one ACP adapter subprocess connection.

    Spawns the adapter, runs initialize + new_session on enter, and closes
    cleanly on exit. One instance maps to one subprocess lifetime.

    Usage:
        async with AcpClient(
            command=["npx", "-y", "@agentclientprotocol/claude-agent-acp"],
            cwd="/workspace",
            model="haiku",
        ) as client:
            result = await client.prompt("Hello")
    """

    def __init__(
        self,
        command: list[str],
        cwd: str,
        model: str | None = None,
        mcp_servers: list[Any] | None = None,
        allowed_tools: list[str] | None = None,
    ) -> None:
        self._command = command
        self._cwd = cwd
        self._model = model
        self._mcp_servers = mcp_servers
        self._allowed_tools = allowed_tools
        self._session_id: str | None = None
        self._conn: Any = None
        self._ctx: Any = None
        self._adapter: _AcpAdapter | None = None

    @property
    def session_id(self) -> str | None:
        """The ACP session ID, available after entering the context manager."""
        return self._session_id

    async def __aenter__(self) -> AcpClient:
        child_env: dict[str, str] = dict(os.environ)
        if self._model is not None:
            child_env["ANTHROPIC_MODEL"] = self._model

        self._adapter = _AcpAdapter()
        cmd, *args = self._command
        self._ctx = acp.spawn_agent_process(self._adapter, cmd, *args, env=child_env)
        self._conn, _ = await self._ctx.__aenter__()

        await self._conn.initialize(
            protocol_version=acp.PROTOCOL_VERSION,
            client_capabilities=ClientCapabilities(),
            client_info=_CLIENT_INFO,
        )
        servers = self._mcp_servers or []
        if self._mcp_servers or self._allowed_tools:
            session_resp = await self._conn.new_session(
                cwd=self._cwd,
                mcp_servers=servers,
                claudeCode={
                    "options": {
                        "strictMcpConfig": True,
                        "allowedTools": self._allowed_tools or [],
                    }
                },
            )
        else:
            session_resp = await self._conn.new_session(cwd=self._cwd, mcp_servers=[])
        self._session_id = session_resp.session_id
        logger.debug("[acp] session opened session_id=%s", self._session_id)
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._ctx is not None:
            await self._ctx.__aexit__(*exc)
            self._ctx = None
        self._conn = None
        self._session_id = None
        self._adapter = None

    async def prompt(
        self,
        text: str,
        on_update: Callable[[Any], None] | None = None,
    ) -> AcpTurnResult:
        """Send one prompt turn and return the assembled result.

        Args:
            text: The user prompt text.
            on_update: Optional callback invoked for each raw session/update object
                as it arrives. Called before the turn completes.

        Returns:
            AcpTurnResult with assembled text, stop_reason, session_id, usage, and cost.

        Raises:
            RuntimeError: If called outside the async context manager.
        """
        if self._conn is None or self._session_id is None or self._adapter is None:
            raise RuntimeError("AcpClient must be used as an async context manager")

        self._adapter._turn = _TurnState(on_update=on_update)

        response = await self._conn.prompt(
            prompt=[acp.text_block(text)],
            session_id=self._session_id,
            message_id=str(uuid4()),
        )

        turn = self._adapter._turn
        return AcpTurnResult(
            text=turn.assembled_text(),
            stop_reason=response.stop_reason,
            session_id=self._session_id,
            usage=_usage_to_dict(response.usage),
            cost_usd=turn.cost_usd,
        )
