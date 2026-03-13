"""Codex adapter for the interactive session runtime."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

from mc.contexts.interactive.errors import (
    InteractiveSessionBinaryMissingError,
    InteractiveSessionBootstrapError,
)
from mc.contexts.interactive.identity import InteractiveSessionIdentity
from mc.contexts.interactive.types import InteractiveLaunchSpec
from mc.infrastructure.config import AGENTS_DIR
from mc.types import AgentData


def _strip_codex_model_prefix(model: str | None) -> str | None:
    if not model:
        return None
    for prefix in (
        "codex/",
        "openai-codex/",
        "openai_codex/",
        "github-copilot/",
        "github_copilot/",
    ):
        if model.startswith(prefix):
            return model[len(prefix) :]
    return model


class CodexInteractiveAdapter:
    """Prepare and clean up Codex interactive sessions."""

    provider_name = "codex"
    capabilities = [
        "tui",
        "autocomplete",
        "interactive-prompts",
        "commands",
    ]

    def __init__(
        self,
        *,
        cli_path: str = "codex",
        which: Callable[[str], str | None] = shutil.which,
        agents_dir: Path = AGENTS_DIR,
    ) -> None:
        self._cli_path = cli_path
        self._which = which
        self._agents_dir = agents_dir

    async def healthcheck(self, *, agent: AgentData) -> None:
        del agent
        if self._which(self._cli_path) is None:
            raise InteractiveSessionBinaryMissingError(
                f"Codex binary '{self._cli_path}' is not available on PATH."
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
        del identity, task_id, orientation, task_prompt, board_name, memory_mode, resume_session_id
        await self.healthcheck(agent=agent)

        try:
            cwd = self._agents_dir / agent.name
            cwd.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise InteractiveSessionBootstrapError(
                f"Codex workspace bootstrap failed: {exc}"
            ) from exc

        return InteractiveLaunchSpec(
            cwd=cwd,
            command=self._build_command(agent),
            capabilities=list(self.capabilities),
        )

    async def stop_session(self, session_key: str) -> None:
        del session_key

    def _build_command(self, agent: AgentData) -> list[str]:
        command = [
            self._cli_path,
            "--sandbox",
            "workspace-write",
            "--ask-for-approval",
            "on-request",
        ]
        model = _strip_codex_model_prefix(agent.model)
        if model:
            command.extend(["--model", model])
        return command
