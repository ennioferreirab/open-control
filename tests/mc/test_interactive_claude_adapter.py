from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from claude_code.provider import ClaudeCodeProvider

from mc.contexts.interactive.adapters.claude_code import ClaudeCodeInteractiveAdapter
from mc.contexts.interactive.errors import (
    InteractiveSessionBinaryMissingError,
    InteractiveSessionBootstrapError,
)
from mc.contexts.interactive.identity import InteractiveSessionIdentity
from mc.types import AgentData, ClaudeCodeOpts, WorkspaceContext


def _identity() -> InteractiveSessionIdentity:
    return InteractiveSessionIdentity(
        provider="claude-code",
        agent_name="claude-pair",
        scope_kind="chat",
        scope_id="chat-123",
        surface="chat",
    )


def _agent() -> AgentData:
    return AgentData(
        name="claude-pair",
        display_name="Claude Pair",
        role="Engineer",
        model="cc/claude-sonnet-4-6",
        backend="claude-code",
        claude_code_opts=ClaudeCodeOpts(
            permission_mode="acceptEdits",
            allowed_tools=["Read", "Edit"],
            disallowed_tools=["Bash(rm:*)"],
            effort_level="high",
        ),
    )


def _workspace() -> WorkspaceContext:
    return WorkspaceContext(
        cwd=Path("/tmp/claude-workspace"),
        mcp_config=Path("/tmp/claude-workspace/.mcp.json"),
        claude_md=Path("/tmp/claude-workspace/CLAUDE.md"),
        socket_path="/tmp/mc-claude.sock",
    )


@pytest.mark.asyncio
async def test_prepare_launch_reuses_cc_workspace_bootstrap_without_headless_flags() -> None:
    workspace_manager = MagicMock()
    workspace_manager.prepare.return_value = _workspace()
    socket_server = MagicMock()
    socket_server.start = AsyncMock()
    adapter = ClaudeCodeInteractiveAdapter(
        bridge=MagicMock(),
        workspace_manager=workspace_manager,
        socket_server_factory=MagicMock(return_value=socket_server),
        cli_path="claude",
        which=MagicMock(return_value="/usr/local/bin/claude"),
    )

    launch = await adapter.prepare_launch(
        identity=_identity(),
        agent=_agent(),
        task_id="task-123",
        orientation="Global orientation",
        task_prompt="Investigate failing test",
        board_name="product",
        memory_mode="clean",
    )

    workspace_manager.prepare.assert_called_once_with(
        "claude-pair",
        _agent(),
        "task-123",
        orientation="Global orientation",
        task_prompt="Investigate failing test",
        board_name="product",
        memory_mode="clean",
    )
    socket_server.start.assert_awaited_once_with("/tmp/mc-claude.sock")
    assert launch.cwd == Path("/tmp/claude-workspace")
    assert launch.command[0] == "claude"
    assert "--mcp-config" in launch.command
    assert str(_workspace().mcp_config) in launch.command
    assert "--permission-mode" in launch.command
    assert "--allowedTools" in launch.command
    assert "--disallowedTools" in launch.command
    assert "--effort" in launch.command
    assert "-p" not in launch.command
    assert "--output-format" not in launch.command
    assert "--resume" not in launch.command
    assert "autocomplete" in launch.capabilities
    assert "interactive-prompts" in launch.capabilities
    assert launch.environment is None


@pytest.mark.asyncio
async def test_prepare_launch_supports_resume_without_using_print_mode() -> None:
    workspace_manager = MagicMock()
    workspace_manager.prepare.return_value = _workspace()
    socket_server = MagicMock()
    socket_server.start = AsyncMock()
    adapter = ClaudeCodeInteractiveAdapter(
        bridge=MagicMock(),
        workspace_manager=workspace_manager,
        socket_server_factory=MagicMock(return_value=socket_server),
        cli_path="claude",
        which=MagicMock(return_value="/usr/local/bin/claude"),
    )

    launch = await adapter.prepare_launch(
        identity=_identity(),
        agent=_agent(),
        task_id="task-123",
        resume_session_id="2f2dd2f2-1111-4444-8888-111122223333",
    )

    resume_index = launch.command.index("--resume")
    assert launch.command[resume_index + 1] == "2f2dd2f2-1111-4444-8888-111122223333"
    assert "-p" not in launch.command


@pytest.mark.asyncio
async def test_interactive_and_headless_paths_diverge_after_shared_workspace_setup() -> None:
    workspace_manager = MagicMock()
    workspace_manager.prepare.return_value = _workspace()
    socket_server = MagicMock()
    socket_server.start = AsyncMock()
    adapter = ClaudeCodeInteractiveAdapter(
        bridge=MagicMock(),
        workspace_manager=workspace_manager,
        socket_server_factory=MagicMock(return_value=socket_server),
        cli_path="claude",
        which=MagicMock(return_value="/usr/local/bin/claude"),
    )
    provider = ClaudeCodeProvider(cli_path="claude")

    launch = await adapter.prepare_launch(
        identity=_identity(),
        agent=_agent(),
        task_id="task-123",
    )
    headless_command = provider._build_command(
        "Investigate failing test",
        _agent(),
        _workspace(),
        session_id=None,
    )

    assert str(_workspace().mcp_config) in launch.command
    assert str(_workspace().mcp_config) in headless_command
    assert "-p" not in launch.command
    assert "--output-format" not in launch.command
    assert "-p" in headless_command
    assert "--output-format" in headless_command


@pytest.mark.asyncio
async def test_prepare_launch_fails_with_actionable_error_when_claude_missing() -> None:
    adapter = ClaudeCodeInteractiveAdapter(
        bridge=MagicMock(),
        workspace_manager=MagicMock(),
        socket_server_factory=MagicMock(),
        cli_path="claude",
        which=MagicMock(return_value=None),
    )

    with pytest.raises(InteractiveSessionBinaryMissingError, match="claude"):
        await adapter.prepare_launch(
            identity=_identity(),
            agent=_agent(),
            task_id="task-123",
        )


@pytest.mark.asyncio
async def test_prepare_launch_wraps_workspace_bootstrap_failures() -> None:
    workspace_manager = MagicMock()
    workspace_manager.prepare.side_effect = RuntimeError("CLAUDE.md generation failed")
    adapter = ClaudeCodeInteractiveAdapter(
        bridge=MagicMock(),
        workspace_manager=workspace_manager,
        socket_server_factory=MagicMock(),
        cli_path="claude",
        which=MagicMock(return_value="/usr/local/bin/claude"),
    )

    with pytest.raises(InteractiveSessionBootstrapError, match="CLAUDE.md generation failed"):
        await adapter.prepare_launch(
            identity=_identity(),
            agent=_agent(),
            task_id="task-123",
        )


@pytest.mark.asyncio
async def test_stop_session_stops_socket_server_when_present() -> None:
    workspace_manager = MagicMock()
    workspace_manager.prepare.return_value = _workspace()
    socket_server = MagicMock()
    socket_server.start = AsyncMock()
    socket_server.stop = AsyncMock()
    adapter = ClaudeCodeInteractiveAdapter(
        bridge=MagicMock(),
        workspace_manager=workspace_manager,
        socket_server_factory=MagicMock(return_value=socket_server),
        cli_path="claude",
        which=MagicMock(return_value="/usr/local/bin/claude"),
    )
    identity = _identity()

    await adapter.prepare_launch(identity=identity, agent=_agent(), task_id="task-123")
    await adapter.stop_session(identity.session_key)

    socket_server.stop.assert_awaited_once_with()
