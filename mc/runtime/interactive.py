"""Composition helpers for the interactive TUI runtime."""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import websockets
from websockets.exceptions import ConnectionClosed

from mc.contexts.interactive import (
    ClaudeCodeInteractiveAdapter,
    CodexInteractiveAdapter,
    InteractiveExecutionSupervisor,
    InteractiveSessionCoordinator,
    InteractiveSessionIdentity,
    InteractiveSessionRegistry,
    NanobotInteractiveAdapter,
)
from mc.contexts.interactive.agent_loader import load_interactive_agent
from mc.infrastructure.interactive import TerminalSize, TmuxSessionManager
from mc.runtime.interactive_transport import InteractiveSocketTransport


@dataclass
class InteractiveRuntime:
    """Interactive runtime services owned by the gateway lifecycle."""

    service: InteractiveSessionCoordinator
    transport: InteractiveSocketTransport
    supervisor: InteractiveExecutionSupervisor
    server: "InteractiveSocketServer"
    adapters: dict[str, Any]


class InteractiveSocketServer:
    """Dedicated websocket server for PTY-backed interactive sessions."""

    def __init__(
        self,
        *,
        transport: InteractiveSocketTransport,
        coordinator: InteractiveSessionCoordinator,
        load_agent: Any,
        host: str,
        port: int,
    ) -> None:
        self._transport = transport
        self._coordinator = coordinator
        self._load_agent = load_agent
        self.host = host
        self.port = port
        self._server: Any | None = None

    async def start(self) -> None:
        self._server = await websockets.serve(self.handle_connection, self.host, self.port)

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()

    async def _send_error_and_close(self, connection: Any, message: str) -> None:
        with contextlib.suppress(ConnectionClosed):
            await connection.send(json.dumps({"type": "error", "message": message}))
        with contextlib.suppress(ConnectionClosed):
            await connection.close()

    async def handle_connection(self, connection: Any) -> None:
        parsed = urlparse(connection.request.path)
        params = parse_qs(parsed.query)
        columns = int(params.get("columns", ["120"])[0])
        rows = int(params.get("rows", ["40"])[0])
        session_id = params.get("sessionId", [None])[0]
        attach_token = params.get("attachToken", [None])[0]

        if session_id is None:
            try:
                provider = params["provider"][0]
                agent_name = params["agentName"][0]
                scope_kind = params.get("scopeKind", ["chat"])[0]
                scope_id = params.get("scopeId", [f"chat:{agent_name}"])[0]
                surface = params.get("surface", ["chat"])[0]
                task_id = params.get("taskId", [scope_id])[0]

                identity = InteractiveSessionIdentity(
                    provider=provider,
                    agent_name=agent_name,
                    scope_kind=scope_kind,
                    scope_id=scope_id,
                    surface=surface,
                )
                agent = self._load_agent(agent_name, provider=provider)
                if agent is None:
                    raise RuntimeError(
                        f"Interactive agent '{agent_name}' could not be loaded for provider '{provider}'."
                    )
                session = await self._coordinator.create_or_attach(
                    identity=identity,
                    agent=agent,
                    task_id=task_id,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                session_id = session["session_id"]
                attach_token = session.get("attach_token")
            except Exception as exc:
                await self._send_error_and_close(connection, str(exc))
                return

        try:
            await self._transport.handle_connection(
                connection,
                session_id=session_id,
                size=TerminalSize(columns=columns, rows=rows),
                attach_token=attach_token,
            )
        except ConnectionClosed:
            return
        except Exception as exc:
            await self._send_error_and_close(connection, str(exc))


def build_interactive_runtime(
    bridge: Any,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    bus: Any | None = None,
    cron_service: Any | None = None,
) -> InteractiveRuntime:
    """Build the provider-agnostic interactive runtime stack."""

    registry = InteractiveSessionRegistry(bridge)
    supervisor = InteractiveExecutionSupervisor(bridge=bridge, registry=registry)
    adapters = {
        "claude-code": ClaudeCodeInteractiveAdapter(
            bridge=bridge,
            bus=bus,
            cron_service=cron_service,
            supervision_sink=supervisor,
        ),
        "codex": CodexInteractiveAdapter(supervision_sink=supervisor),
        "mc": NanobotInteractiveAdapter(),
    }
    service = InteractiveSessionCoordinator(
        registry=registry,
        tmux=TmuxSessionManager(),
        adapters=adapters,
    )
    transport = InteractiveSocketTransport(session_service=service)
    server = InteractiveSocketServer(
        transport=transport,
        coordinator=service,
        load_agent=lambda agent_name, provider: load_interactive_agent(
            agent_name,
            provider=provider,
            bridge=bridge,
        ),
        host=host,
        port=port,
    )
    return InteractiveRuntime(
        service=service,
        transport=transport,
        supervisor=supervisor,
        server=server,
        adapters=adapters,
    )
