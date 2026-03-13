"""Nanobot adapter for the interactive session runtime."""

from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path

from mc.contexts.interactive.identity import InteractiveSessionIdentity
from mc.contexts.interactive.types import InteractiveLaunchSpec
from mc.infrastructure.config import AGENTS_DIR, _resolve_admin_key, _resolve_convex_url
from mc.types import AgentData


class NanobotInteractiveAdapter:
    """Prepare and clean up Nanobot-backed interactive sessions."""

    provider_name = "mc"
    capabilities = [
        "tui",
        "commands",
        "interactive-prompts",
    ]

    def __init__(
        self,
        *,
        python_executable: str | None = None,
        agents_dir: Path = AGENTS_DIR,
        project_root: Path | None = None,
    ) -> None:
        self._python_executable = python_executable or sys.executable
        self._agents_dir = agents_dir
        self._project_root = project_root or Path(__file__).resolve().parents[4]

    async def healthcheck(self, *, agent: AgentData) -> None:
        del agent
        return None

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
        memory_workspace: Path | None = None,
        resume_session_id: str | None = None,
    ) -> InteractiveLaunchSpec:
        del memory_mode, resume_session_id
        cwd = self._agents_dir / agent.name
        cwd.mkdir(parents=True, exist_ok=True)
        effective_memory_workspace = memory_workspace or cwd

        environment = {
            "MC_INTERACTIVE_SESSION_ID": identity.session_key,
            "MC_INTERACTIVE_TASK_ID": task_id,
            "MC_INTERACTIVE_AGENT_NAME": agent.name,
            "MC_INTERACTIVE_MEMORY_WORKSPACE": str(effective_memory_workspace),
        }
        existing_pythonpath = os.environ.get("PYTHONPATH")
        pythonpath_parts = [str(self._project_root)]
        if existing_pythonpath:
            pythonpath_parts.append(existing_pythonpath)
        environment["PYTHONPATH"] = ":".join(part for part in pythonpath_parts if part)
        convex_url = _resolve_convex_url()
        if convex_url:
            environment["CONVEX_URL"] = convex_url
        admin_key = _resolve_admin_key()
        if admin_key:
            environment["CONVEX_ADMIN_KEY"] = admin_key
        if agent.model:
            environment["MC_INTERACTIVE_AGENT_MODEL"] = agent.model
        if orientation:
            environment["MC_INTERACTIVE_AGENT_PROMPT"] = orientation
        if task_prompt:
            environment["MC_INTERACTIVE_TASK_PROMPT"] = task_prompt
        if board_name:
            environment["MC_INTERACTIVE_BOARD_NAME"] = board_name

        return InteractiveLaunchSpec(
            cwd=cwd,
            command=[
                "/bin/bash",
                "-lc",
                shlex.join(
                    [
                        self._python_executable,
                        "-m",
                        "mc.runtime.nanobot_interactive_session",
                    ]
                ),
            ],
            capabilities=list(self.capabilities),
            environment=environment,
            bootstrap_input=None,
        )

    async def stop_session(self, session_key: str) -> None:
        del session_key
        return None
