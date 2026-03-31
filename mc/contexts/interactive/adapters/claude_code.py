"""Claude Code adapter for the interactive session runtime."""

from __future__ import annotations

import logging
import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar

from claude_code.ipc_server import MCSocketServer
from claude_code.tool_policy import merge_mc_disallowed_tools
from claude_code.workspace import CCWorkspaceManager

from mc.contexts.interactive.errors import (
    InteractiveSessionBinaryMissingError,
    InteractiveSessionBootstrapError,
)
from mc.contexts.interactive.identity import InteractiveSessionIdentity
from mc.contexts.interactive.types import InteractiveLaunchSpec, InteractiveSupervisionSink
from mc.types import AgentData

logger = logging.getLogger(__name__)


class ClaudeCodeInteractiveAdapter:
    """Prepare and clean up Claude Code interactive sessions."""

    provider_name = "claude-code"
    capabilities: ClassVar[list[str]] = [
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
        supervision_sink: InteractiveSupervisionSink | None = None,
    ) -> None:
        self._bridge = bridge
        self._workspace_manager = workspace_manager or CCWorkspaceManager()
        self._socket_server_factory = socket_server_factory
        self._cli_path = cli_path
        self._which = which
        self._bus = bus
        self._cron_service = cron_service
        self._supervision_sink = supervision_sink
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
        task_id: str | None = None,
        orientation: str | None = None,
        task_prompt: str | None = None,
        board_name: str | None = None,
        memory_mode: str = "clean",
        memory_workspace: Path | None = None,
        resume_session_id: str | None = None,
    ) -> InteractiveLaunchSpec:
        if not board_name:
            raise InteractiveSessionBootstrapError(
                f"Agent '{agent.name}' requires a board-scoped workspace — "
                "no board_name provided for interactive session."
            )
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
                memory_workspace=memory_workspace,
                interactive_session_id=identity.session_key,
            )
        except Exception as exc:
            raise InteractiveSessionBootstrapError(
                f"Claude Code workspace bootstrap failed: {exc}"
            ) from exc

        socket_server = self._socket_server_factory(
            self._bridge,
            self._bus,
            cron_service=self._cron_service,
            interactive_supervisor=self._supervision_sink,
        )
        await socket_server.start(workspace_ctx.socket_path)
        self._socket_servers[identity.session_key] = socket_server

        bootstrap = _normalize_bootstrap_input(task_prompt)
        return InteractiveLaunchSpec(
            cwd=workspace_ctx.cwd,
            command=self._build_command(
                agent,
                workspace_ctx,
                resume_session_id=resume_session_id,
            ),
            capabilities=list(self.capabilities),
            bootstrap_input=bootstrap,
            bootstrap_delay=2.0 if bootstrap else 0.0,
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
        cmd = [self._cli_path]

        # Isolate agent sessions from host user settings (plugins, hooks, MCPs)
        # unless CLAUDE_CODE_SETTING_SOURCES is explicitly set (e.g. to empty
        # string to inherit user auth/settings inside Docker).
        setting_sources = os.environ.get("CLAUDE_CODE_SETTING_SOURCES", "project")
        if setting_sources:
            cmd.extend(["--setting-sources", setting_sources])
        cmd.extend(["--strict-mcp-config"])
        cmd.extend(["--mcp-config", str(workspace_ctx.mcp_config)])

        cc = agent.claude_code_opts
        permission_mode = (cc and cc.permission_mode) or "bypassPermissions"
        cmd.extend(["--permission-mode", permission_mode])

        allowed_tools = list((cc and cc.allowed_tools) or [])
        # When no explicit allowed_tools are configured, default to "*" so
        # that all built-in and MCP tools are auto-approved in MC sessions.
        # See also: provider_cli.py, vendor/claude-code/provider.py
        if not allowed_tools:
            logger.info("No allowed_tools configured — defaulting to '*'")
            allowed_tools.append("*")
        allowed_tools.append("mcp__mc__*")
        for tool in allowed_tools:
            cmd.extend(["--allowedTools", tool])

        for tool in merge_mc_disallowed_tools((cc and cc.disallowed_tools) or None):
            cmd.extend(["--disallowedTools", tool])

        if cc and cc.effort_level:
            cmd.extend(["--effort", cc.effort_level])

        if resume_session_id:
            cmd.extend(["--resume", resume_session_id])

        return cmd


def _normalize_bootstrap_input(task_prompt: str | None) -> str | None:
    if not task_prompt:
        return None
    text = task_prompt.strip()
    return text or None
