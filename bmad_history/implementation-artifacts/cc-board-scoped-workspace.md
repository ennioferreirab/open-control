# Story: CC Board-Scoped Workspace — memory isolation per board for CC agents

## Goal

CC agents currently always use `~/.nanobot/agents/{agent}/` regardless of which board
the task belongs to. Nanobot agents already have board isolation via `board_utils`.
This story brings CC to parity: when a task has a `board_id`, the CC workspace uses
`~/.nanobot/boards/{board}/agents/{agent}/` as root, with memory isolated or shared
per the board's agent memory mode ("clean" or "with_history").

## Architecture

```
mode: clean (default, "not share")
  ~/.nanobot/boards/{board}/agents/{agent}/   ← CC workspace root
    memory/MEMORY.md   ← isolated, board-specific
    memory/HISTORY.md  ← isolated, board-specific

mode: with_history ("share")
  ~/.nanobot/boards/{board}/agents/{agent}/
    memory/MEMORY.md → symlink → ~/.nanobot/agents/{agent}/memory/MEMORY.md
    memory/HISTORY.md → symlink → ~/.nanobot/agents/{agent}/memory/HISTORY.md
```

The symlink setup is already handled by `mc.board_utils.resolve_board_workspace()`.
`CCWorkspaceManager` just needs to call it when `board_name` is provided.

No board_id on task → workspace stays at `~/.nanobot/agents/{agent}/` (unchanged).

---

## File 1 (PATCH): `vendor/claude-code/claude_code/workspace.py`

Add `board_name: str | None = None` and `memory_mode: str = "clean"` params to
`CCWorkspaceManager.prepare()`.

Change the workspace root selection from:
```python
workspace = self._root / "agents" / agent_name
workspace.mkdir(parents=True, exist_ok=True)
(workspace / "memory").mkdir(exist_ok=True)
(workspace / "sessions").mkdir(exist_ok=True)
```

To:
```python
if board_name:
    from mc.board_utils import resolve_board_workspace
    workspace = resolve_board_workspace(board_name, agent_name, mode=memory_mode)
    # resolve_board_workspace already created memory/ and sessions/
    # Still ensure they exist (idempotent):
    (workspace / "memory").mkdir(parents=True, exist_ok=True)
    (workspace / "sessions").mkdir(exist_ok=True)
else:
    workspace = self._root / "agents" / agent_name
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "memory").mkdir(exist_ok=True)
    (workspace / "sessions").mkdir(exist_ok=True)
```

Also update the docstring for `prepare()` to document `board_name` and `memory_mode` params.

---

## File 2 (PATCH): `mc/executor.py`

In `_execute_cc_task()`, add board resolution before step 1 (workspace preparation).

The nanobot path already has this block at around line 1116-1142. Add an identical block
inside `_execute_cc_task()` right before the "1. Prepare workspace" comment (around line 1519):

```python
        # Resolve board-scoped workspace for CC (mirrors nanobot board resolution)
        _cc_board_name: str | None = None
        _cc_memory_mode: str = "clean"
        _board_id = (task_data or {}).get("board_id")
        if _board_id:
            try:
                _board = await asyncio.to_thread(
                    self._bridge.get_board_by_id, _board_id
                )
                if _board:
                    _cc_board_name = _board.get("name")
                    if _cc_board_name:
                        from mc.board_utils import get_agent_memory_mode
                        _cc_memory_mode = get_agent_memory_mode(_board, agent_name)
                        logger.info(
                            "[executor] CC: board-scoped workspace for agent '%s' on board '%s' (mode=%s)",
                            agent_name, _cc_board_name, _cc_memory_mode,
                        )
            except Exception:
                logger.warning(
                    "[executor] CC: failed to resolve board workspace for task '%s', using global workspace",
                    title,
                    exc_info=True,
                )

        # 1. Prepare workspace
        try:
            ws_mgr = CCWorkspaceManager()
            from mc.orientation import load_orientation
            orientation = load_orientation(agent_name)
            ws_ctx = ws_mgr.prepare(
                agent_name, agent_data, task_id,
                orientation=orientation,
                task_prompt=title,
                board_name=_cc_board_name,
                memory_mode=_cc_memory_mode,
            )
        except Exception as exc:
            await self._crash_task(task_id, title, f"Workspace preparation failed: {exc}", agent_name)
            return
```

---

## File 3 (PATCH): `tests/cc/test_workspace.py`

Add a new test class `TestBoardScopedWorkspace` at the end of the file:

```python
class TestBoardScopedWorkspace:
    """Tests for board-scoped workspace isolation."""

    def test_board_scoped_workspace_uses_board_path(self, tmp_path: Path) -> None:
        """When board_name is provided, workspace root is under boards/{board}/agents/{agent}/."""
        from unittest.mock import patch

        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()

        board_workspace = tmp_path / "boards" / "myboard" / "agents" / "test-agent"
        board_workspace.mkdir(parents=True, exist_ok=True)
        (board_workspace / "memory").mkdir()
        (board_workspace / "sessions").mkdir()

        with patch("mc.board_utils.resolve_board_workspace", return_value=board_workspace) as mock_resolve:
            ctx = manager.prepare("test-agent", agent, "task123", board_name="myboard", memory_mode="clean")

        mock_resolve.assert_called_once_with("myboard", "test-agent", mode="clean")
        assert ctx.cwd == board_workspace

    def test_no_board_uses_global_path(self, tmp_path: Path) -> None:
        """Without board_name, workspace stays at agents/{agent}/."""
        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()
        ctx = manager.prepare("test-agent", agent, "task123")
        assert ctx.cwd == tmp_path / "agents" / "test-agent"

    def test_with_history_mode_passed_to_board_utils(self, tmp_path: Path) -> None:
        """memory_mode='with_history' is forwarded to resolve_board_workspace."""
        from unittest.mock import patch

        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent()

        board_workspace = tmp_path / "boards" / "projboard" / "agents" / "test-agent"
        board_workspace.mkdir(parents=True, exist_ok=True)
        (board_workspace / "memory").mkdir()
        (board_workspace / "sessions").mkdir()

        with patch("mc.board_utils.resolve_board_workspace", return_value=board_workspace) as mock_resolve:
            manager.prepare("test-agent", agent, "task123", board_name="projboard", memory_mode="with_history")

        mock_resolve.assert_called_once_with("projboard", "test-agent", mode="with_history")

    def test_board_workspace_generates_claude_md(self, tmp_path: Path) -> None:
        """Board-scoped workspace still generates CLAUDE.md correctly."""
        from unittest.mock import patch

        manager = CCWorkspaceManager(workspace_root=tmp_path)
        agent = _make_agent(prompt="Board agent prompt.")

        board_workspace = tmp_path / "boards" / "b1" / "agents" / "test-agent"
        board_workspace.mkdir(parents=True, exist_ok=True)
        (board_workspace / "memory").mkdir()
        (board_workspace / "sessions").mkdir()

        with patch("mc.board_utils.resolve_board_workspace", return_value=board_workspace):
            ctx = manager.prepare("test-agent", agent, "task999", board_name="b1")

        claude_md = board_workspace / "CLAUDE.md"
        assert claude_md.exists()
        assert "Board agent prompt." in claude_md.read_text()
```

---

## Verification

```bash
# New board workspace tests
uv run pytest tests/cc/test_workspace.py -v -k "TestBoardScopedWorkspace"

# Full workspace test suite
uv run pytest tests/cc/test_workspace.py -v

# Regression
uv run pytest tests/cc/ tests/mc/test_executor_cc.py -v --timeout=30
```

All new tests must pass. No regressions.

Commit message: `feat(cc): board-scoped workspace for CC agents — memory isolation mirrors nanobot`
