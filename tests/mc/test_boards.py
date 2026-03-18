"""Tests for Story 10.1 — Mission Control Boards Foundation.

Covers:
- resolve_board_workspace() returns correct path (now in board_utils)
- Board-scoped session key format
- Agent filter respects board enabledAgents
- System agents always pass filter
- Empty enabledAgents means all agents pass
- Memory bootstrap: copies global MEMORY.md when board-scoped doesn't exist
- Memory bootstrap: creates empty MEMORY.md when no global exists
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helper: make a fake task executor with a mock bridge
# ---------------------------------------------------------------------------


def _make_executor(bridge=None):
    """Return a TaskExecutor with an optional mock bridge."""
    from mc.contexts.execution.executor import TaskExecutor

    if bridge is None:
        bridge = MagicMock()
    return TaskExecutor(bridge)


# ---------------------------------------------------------------------------
# 1. resolve_board_workspace returns correct path (now in board_utils)
# ---------------------------------------------------------------------------


class TestResolveBoardWorkspace:
    def test_returns_correct_path(self, tmp_path):
        from mc.infrastructure.boards import resolve_board_workspace

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = resolve_board_workspace("project-alpha", "dev-agent")

        expected = tmp_path / ".nanobot" / "boards" / "project-alpha" / "agents" / "dev-agent"
        assert result == expected

    def test_creates_memory_and_sessions_dirs(self, tmp_path):
        from mc.infrastructure.boards import resolve_board_workspace

        with patch("pathlib.Path.home", return_value=tmp_path):
            board_ws = resolve_board_workspace("my-board", "worker")

        assert (board_ws / "memory").exists()
        assert (board_ws / "sessions").exists()

    def test_creates_empty_memory_md_when_no_global(self, tmp_path):
        from mc.infrastructure.boards import resolve_board_workspace

        with patch("pathlib.Path.home", return_value=tmp_path):
            board_ws = resolve_board_workspace("my-board", "worker")

        memory_md = board_ws / "memory" / "MEMORY.md"
        assert memory_md.exists()
        assert memory_md.read_text() == ""

    def test_creates_empty_history_md(self, tmp_path):
        from mc.infrastructure.boards import resolve_board_workspace

        with patch("pathlib.Path.home", return_value=tmp_path):
            board_ws = resolve_board_workspace("my-board", "worker")

        history_md = board_ws / "memory" / "HISTORY.md"
        assert history_md.exists()

    def test_copies_global_memory_md_when_present(self, tmp_path):
        from mc.infrastructure.boards import resolve_board_workspace

        # Create global MEMORY.md
        global_memory_dir = tmp_path / ".nanobot" / "agents" / "dev-agent" / "memory"
        global_memory_dir.mkdir(parents=True)
        global_memory = global_memory_dir / "MEMORY.md"
        global_memory.write_text("# Global memories", encoding="utf-8")

        with patch("pathlib.Path.home", return_value=tmp_path):
            board_ws = resolve_board_workspace("sprint-1", "dev-agent")

        board_memory = board_ws / "memory" / "MEMORY.md"
        assert board_memory.exists()
        assert board_memory.read_text() == "# Global memories"

    def test_does_not_overwrite_existing_board_memory(self, tmp_path):
        from mc.infrastructure.boards import resolve_board_workspace

        # Create global MEMORY.md
        global_memory_dir = tmp_path / ".nanobot" / "agents" / "dev-agent" / "memory"
        global_memory_dir.mkdir(parents=True)
        (global_memory_dir / "MEMORY.md").write_text("global", encoding="utf-8")

        # Pre-create board-scoped MEMORY.md with different content
        board_memory_dir = (
            tmp_path / ".nanobot" / "boards" / "sprint-1" / "agents" / "dev-agent" / "memory"
        )
        board_memory_dir.mkdir(parents=True)
        (board_memory_dir / "MEMORY.md").write_text("board-specific", encoding="utf-8")

        with patch("pathlib.Path.home", return_value=tmp_path):
            board_ws = resolve_board_workspace("sprint-1", "dev-agent")

        board_memory = board_ws / "memory" / "MEMORY.md"
        assert board_memory.read_text() == "board-specific"

    def test_idempotent_second_call(self, tmp_path):
        from mc.infrastructure.boards import resolve_board_workspace

        with patch("pathlib.Path.home", return_value=tmp_path):
            ws1 = resolve_board_workspace("board-x", "agent-a")
            ws2 = resolve_board_workspace("board-x", "agent-a")

        assert ws1 == ws2
        assert ws1.exists()


# ---------------------------------------------------------------------------
# 2. Board-scoped session key format
# ---------------------------------------------------------------------------


class TestBoardSessionKey:
    async def test_run_agent_uses_board_session_key(self, tmp_path):
        """_run_agent_on_task uses board-scoped session key when board_name provided."""
        from unittest.mock import AsyncMock, patch

        from mc.contexts.execution.executor import _run_agent_on_task

        captured_session_key = {}

        direct_result = MagicMock()
        direct_result.content = "done"
        direct_result.is_error = False
        direct_result.error_message = None

        async def fake_process_direct_result(
            content, session_key, channel, chat_id, task_id=None, on_progress=None
        ):
            captured_session_key["key"] = session_key
            return direct_result

        mock_loop = MagicMock()
        mock_loop.process_direct_result = fake_process_direct_result
        mock_loop.end_task_session = AsyncMock()

        with (
            patch("pathlib.Path.home", return_value=tmp_path),
            patch(
                "mc.contexts.execution.executor._make_provider", return_value=(MagicMock(), "model")
            ),
            patch("nanobot.agent.loop.AgentLoop", return_value=mock_loop),
            patch("nanobot.bus.queue.MessageBus"),
        ):
            (tmp_path / ".nanobot" / "agents" / "worker").mkdir(parents=True)
            await _run_agent_on_task(
                agent_name="worker",
                agent_prompt=None,
                agent_model=None,
                task_title="task",
                task_description=None,
                board_name="sprint-1",
            )

        assert captured_session_key.get("key") == "mc:board:sprint-1:task:worker"


# ---------------------------------------------------------------------------
# 3-5. Agent filter respects board enabledAgents
# ---------------------------------------------------------------------------


class TestBoardAgentFilter:
    """Test the agent filtering logic from the orchestrator."""

    def _make_agent(self, name: str, is_system: bool = False, enabled: bool = True):
        """Create a fake AgentData-like dict."""
        return type(
            "Agent",
            (),
            {
                "name": name,
                "is_system": is_system,
                "enabled": enabled,
            },
        )()

    def _filter_agents(self, agents, board_enabled_agents):
        """Apply the same filtering logic as the orchestrator."""
        if not board_enabled_agents:
            return agents
        return [
            a for a in agents if a.name in board_enabled_agents or getattr(a, "is_system", False)
        ]

    def test_empty_enabled_agents_allows_all(self):
        agents = [
            self._make_agent("dev-agent"),
            self._make_agent("research-agent"),
            self._make_agent("lead-agent", is_system=True),
        ]
        result = self._filter_agents(agents, [])
        assert len(result) == 3

    def test_non_empty_filters_to_listed_plus_system(self):
        agents = [
            self._make_agent("dev-agent"),
            self._make_agent("research-agent"),
            self._make_agent("lead-agent", is_system=True),
            self._make_agent("mc-agent", is_system=True),
        ]
        result = self._filter_agents(agents, ["dev-agent"])
        names = {a.name for a in result}
        assert "dev-agent" in names, "Listed agent must be included"
        assert "lead-agent" in names, "System agent must always be included"
        assert "mc-agent" in names, "System agent must always be included"
        assert "research-agent" not in names, "Non-listed agent must be excluded"

    def test_system_agents_always_pass(self):
        agents = [
            self._make_agent("dev-agent"),
            self._make_agent("lead-agent", is_system=True),
        ]
        result = self._filter_agents(agents, ["research-agent"])  # dev-agent not listed
        names = {a.name for a in result}
        assert "lead-agent" in names
        assert "dev-agent" not in names

    def test_multiple_agents_in_filter(self):
        agents = [
            self._make_agent("dev-agent"),
            self._make_agent("research-agent"),
            self._make_agent("test-agent"),
            self._make_agent("lead-agent", is_system=True),
        ]
        result = self._filter_agents(agents, ["dev-agent", "research-agent"])
        names = {a.name for a in result}
        assert names == {"dev-agent", "research-agent", "lead-agent"}
