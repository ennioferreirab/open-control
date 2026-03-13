from __future__ import annotations

from pathlib import Path

import pytest

from mc.contexts.interactive.adapters.nanobot import NanobotInteractiveAdapter
from mc.contexts.interactive.identity import InteractiveSessionIdentity
from mc.types import AgentData


def _identity() -> InteractiveSessionIdentity:
    return InteractiveSessionIdentity(
        provider="mc",
        agent_name="nanobot-pair",
        scope_kind="task",
        scope_id="task-123",
        surface="step",
    )


def _agent(model: str = "openrouter/openai/gpt-5.4") -> AgentData:
    return AgentData(
        name="nanobot-pair",
        display_name="Nanobot Pair",
        role="Engineer",
        model=model,
        backend="nanobot",
        interactive_provider="mc",
    )


@pytest.mark.asyncio
async def test_prepare_launch_builds_nanobot_runtime_wrapper_command(tmp_path: Path) -> None:
    adapter = NanobotInteractiveAdapter(
        python_executable="/tmp/venv/bin/python",
        agents_dir=tmp_path,
    )

    launch = await adapter.prepare_launch(
        identity=_identity(),
        agent=_agent(),
        task_id="task-123",
        orientation="Use the MC runtime contract.",
        task_prompt="Step: Verify the dashboard thread output",
        board_name="default",
        memory_workspace=tmp_path / "board-memory",
    )

    assert launch.cwd == tmp_path / "nanobot-pair"
    assert launch.command == [
        "/bin/bash",
        "-lc",
        "/tmp/venv/bin/python -m mc.runtime.nanobot_interactive_session",
    ]
    assert launch.bootstrap_input is None
    assert launch.capabilities == ["tui", "commands", "interactive-prompts"]
    assert launch.environment is not None
    assert launch.environment["MC_INTERACTIVE_SESSION_ID"] == _identity().session_key
    assert launch.environment["MC_INTERACTIVE_TASK_ID"] == "task-123"
    assert launch.environment["MC_INTERACTIVE_AGENT_NAME"] == "nanobot-pair"
    assert launch.environment["MC_INTERACTIVE_AGENT_MODEL"] == "openrouter/openai/gpt-5.4"
    assert launch.environment["MC_INTERACTIVE_AGENT_PROMPT"] == "Use the MC runtime contract."
    assert (
        launch.environment["MC_INTERACTIVE_TASK_PROMPT"]
        == "Step: Verify the dashboard thread output"
    )
    assert launch.environment["MC_INTERACTIVE_BOARD_NAME"] == "default"
    assert launch.environment["MC_INTERACTIVE_MEMORY_WORKSPACE"] == str(tmp_path / "board-memory")


@pytest.mark.asyncio
async def test_prepare_launch_defaults_memory_workspace_to_agent_workspace(tmp_path: Path) -> None:
    adapter = NanobotInteractiveAdapter(
        python_executable="/tmp/venv/bin/python",
        agents_dir=tmp_path,
    )

    launch = await adapter.prepare_launch(
        identity=_identity(),
        agent=_agent(model=""),
        task_id="task-123",
    )

    assert launch.environment is not None
    assert launch.environment["MC_INTERACTIVE_SESSION_ID"] == _identity().session_key
    assert launch.environment["MC_INTERACTIVE_TASK_ID"] == "task-123"
    assert launch.environment["MC_INTERACTIVE_AGENT_NAME"] == "nanobot-pair"
    assert launch.environment["MC_INTERACTIVE_MEMORY_WORKSPACE"] == str(tmp_path / "nanobot-pair")
