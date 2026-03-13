"""Claude Code adapter for the interactive session runtime."""

from __future__ import annotations

import shutil
from typing import Any, Callable

from claude_code.ipc_server import MCSocketServer
from claude_code.workspace import CCWorkspaceManager

from mc.contexts.interactive.errors import (
    InteractiveSessionBinaryMissingError,
    InteractiveSessionBootstrapError,
)
from mc.contexts.interactive.identity import InteractiveSessionIdentity
from mc.contexts.interactive.types import InteractiveLaunchSpec
from mc.types import AgentData


class ClaudeCodeInteractiveAdapter:
    """Prepare and clean up Claude Code interactive sessions."""

    provider_name = "claude-code"
    capabilities = [
        "tui",
        "autocomplete",
        "interactive-prompts",
        "commands",
        "mcp-tools",
    ]

    def __init__(
        self,
        *,
        bridge: Any,
        workspace_manager: CCWorkspaceManager | None = None,
        socket_server_factory: Callable[..., MCSocketServer] = MCSocketServer,
        cli_path: str = "claude",
        which: Callable[[str], str | None] = shutil.which,
        bus: Any | None = None,
        cron_service: Any | None = None,
    ) -> None:
        self._bridge = bridge
        self._workspace_manager = workspace_manager or CCWorkspaceManager()
        self._socket_server_factory = socket_server_factory
        self._cli_path = cli_path
        self._which = which
        self._bus = bus
        self._cron_service = cron_service
        self._socket_servers: dict[str, MCSocketServer] = {}

    async def healthcheck(self, *, agent: AgentData) -> None:
        del agent
        if self._which(self._cli_path) is None:
            raise InteractiveSessionBinaryMissingError(
                f"Claude Code binary '{self._cli_path}' is not available on PATH."
            )

    async def prepare_launch(
        self,
        *,
        identity: InteractiveSessionIdentity,
        agent: AgentData,
        task_id: str,
        orientation: str | None = None,
        task_prompt: str | None = None,
        board_name: str | None = None,
        memory_mode: str = "clean",
        resume_session_id: str | None = None,
    ) -> InteractiveLaunchSpec:
        await self.healthcheck(agent=agent)

        try:
            workspace_ctx = self._workspace_manager.prepare(
                agent.name,
                agent,
                task_id,
                orientation=orientation,
                task_prompt=task_prompt,
                board_name=board_name,
                memory_mode=memory_mode,
            )
        except Exception as exc:
            raise InteractiveSessionBootstrapError(
                f"Claude Code workspace bootstrap failed: {exc}"
            ) from exc

        socket_server = self._socket_server_factory(
            self._bridge,
            self._bus,
            cron_service=self._cron_service,
        )
        await socket_server.start(workspace_ctx.socket_path)
        self._socket_servers[identity.session_key] = socket_server

        return InteractiveLaunchSpec(
            cwd=workspace_ctx.cwd,
            command=self._build_command(agent, workspace_ctx, resume_session_id=resume_session_id),
            capabilities=list(self.capabilities),
        )

    async def stop_session(self, session_key: str) -> None:
        socket_server = self._socket_servers.pop(session_key, None)
        if socket_server is not None:
            await socket_server.stop()

    def _build_command(
        self,
        agent: AgentData,
        workspace_ctx: Any,
        *,
        resume_session_id: str | None,
    ) -> list[str]:
        cmd = [self._cli_path, "--mcp-config", str(workspace_ctx.mcp_config)]

        model = agent.model
        if model and model.startswith("cc/"):
            model = model[3:]
        if model:
            cmd.extend(["--model", model])

        cc = agent.claude_code_opts
        permission_mode = (cc and cc.permission_mode) or "acceptEdits"
        cmd.extend(["--permission-mode", permission_mode])

        allowed_tools = list((cc and cc.allowed_tools) or [])
        allowed_tools.append("mcp__nanobot__*")
        for tool in allowed_tools:
            cmd.extend(["--allowedTools", tool])

        for tool in (cc and cc.disallowed_tools) or []:
            cmd.extend(["--disallowedTools", tool])

        if cc and cc.effort_level:
            cmd.extend(["--effort", cc.effort_level])

        if resume_session_id:
            cmd.extend(["--resume", resume_session_id])

        return cmd
