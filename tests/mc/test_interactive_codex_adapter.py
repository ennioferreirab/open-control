from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mc.contexts.interactive.adapters.codex import CodexInteractiveAdapter
from mc.contexts.interactive.errors import (
    InteractiveSessionBinaryMissingError,
    InteractiveSessionBootstrapError,
)
from mc.contexts.interactive.identity import InteractiveSessionIdentity
from mc.types import AgentData


def _identity() -> InteractiveSessionIdentity:
    return InteractiveSessionIdentity(
        provider="codex",
        agent_name="codex-pair",
        scope_kind="chat",
        scope_id="chat-123",
        surface="chat",
    )


def _agent(model: str = "openai-codex/gpt-5.4") -> AgentData:
    return AgentData(
        name="codex-pair",
        display_name="Codex Pair",
        role="Engineer",
        model=model,
        interactive_provider="codex",
    )


@pytest.mark.asyncio
async def test_prepare_launch_builds_codex_command_in_agent_workspace(tmp_path: Path) -> None:
    adapter = CodexInteractiveAdapter(
        cli_path="codex",
        which=MagicMock(return_value="/opt/homebrew/bin/codex"),
        agents_dir=tmp_path,
    )

    launch = await adapter.prepare_launch(
        identity=_identity(),
        agent=_agent(),
        task_id="task-123",
    )

    assert launch.cwd == tmp_path / "codex-pair"
    assert launch.command == [
        "codex",
        "--sandbox",
        "workspace-write",
        "--ask-for-approval",
        "on-request",
        "--model",
        "gpt-5.4",
    ]
    assert "autocomplete" in launch.capabilities
    assert launch.environment == {"MEMORY_WORKSPACE": str(tmp_path / "codex-pair")}
    assert launch.bootstrap_input is None


@pytest.mark.asyncio
async def test_prepare_launch_accepts_plain_codex_models_without_rewriting(tmp_path: Path) -> None:
    adapter = CodexInteractiveAdapter(
        cli_path="codex",
        which=MagicMock(return_value="/opt/homebrew/bin/codex"),
        agents_dir=tmp_path,
    )

    launch = await adapter.prepare_launch(
        identity=_identity(),
        agent=_agent(model="gpt-5.4"),
        task_id="task-123",
    )

    assert launch.command[-1] == "gpt-5.4"


@pytest.mark.asyncio
async def test_prepare_launch_bootstraps_codex_with_orientation_task_prompt_and_memory_workspace(
    tmp_path: Path,
) -> None:
    adapter = CodexInteractiveAdapter(
        cli_path="codex",
        which=MagicMock(return_value="/opt/homebrew/bin/codex"),
        agents_dir=tmp_path,
    )

    launch = await adapter.prepare_launch(
        identity=_identity(),
        agent=_agent(),
        task_id="task-123",
        orientation="Global orientation",
        task_prompt="Investigate failing test",
        memory_workspace=tmp_path / "board-memory",
    )

    assert launch.environment == {"MEMORY_WORKSPACE": str(tmp_path / "board-memory")}
    assert launch.bootstrap_input == "Global orientation\n\nInvestigate failing test"


@pytest.mark.asyncio
async def test_prepare_launch_fails_with_actionable_error_when_codex_missing(
    tmp_path: Path,
) -> None:
    adapter = CodexInteractiveAdapter(
        cli_path="codex",
        which=MagicMock(return_value=None),
        agents_dir=tmp_path,
    )

    with pytest.raises(InteractiveSessionBinaryMissingError, match="codex"):
        await adapter.prepare_launch(
            identity=_identity(),
            agent=_agent(),
            task_id="task-123",
        )


@pytest.mark.asyncio
async def test_prepare_launch_wraps_workspace_bootstrap_failures(tmp_path: Path) -> None:
    blocked_path = tmp_path / "blocked"
    blocked_path.write_text("not-a-directory", encoding="utf-8")
    adapter = CodexInteractiveAdapter(
        cli_path="codex",
        which=MagicMock(return_value="/opt/homebrew/bin/codex"),
        agents_dir=blocked_path,
    )

    with pytest.raises(InteractiveSessionBootstrapError, match="Codex workspace bootstrap failed"):
        await adapter.prepare_launch(
            identity=_identity(),
            agent=_agent(),
            task_id="task-123",
        )
