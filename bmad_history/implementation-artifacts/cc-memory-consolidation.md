# Story: CCMemoryConsolidator — Post-task memory consolidation for CC agents

## Goal

After a Claude Code (CC) task or chat completes, extract key facts from the task output
and persist them to the agent's MEMORY.md + HISTORY.md. Same pattern as nanobot's
`end_task_session()` / `MemoryStore.consolidate()`, but adapted for CC (which runs as a
subprocess — no in-process session messages).

## Architecture

- ALL logic lives in `vendor/claude-code/claude_code/memory_consolidator.py` (CC backend scope)
- `mc/executor.py` and `mc/chat_handler.py` each add ~10 lines to call it (fire-and-forget)
- Model is resolved from `tier:standard-low` by the caller (MC layer), not hardcoded in the consolidator

---

## File 1 (NEW): `vendor/claude-code/claude_code/memory_consolidator.py`

```python
"""Post-task memory consolidation for Claude Code agents.

After a CC task completes, calls an LLM with the same save_memory tool
as nanobot's MemoryStore.consolidate() to extract facts into MEMORY.md
and HISTORY.md.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import litellm
from filelock import FileLock

logger = logging.getLogger(__name__)

_SAVE_MEMORY_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save the memory consolidation result to persistent storage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "history_entry": {
                        "type": "string",
                        "description": (
                            "A paragraph (2-5 sentences) summarizing key events/decisions/topics. "
                            "Start with [YYYY-MM-DD HH:MM]. Include detail useful for grep search."
                        ),
                    },
                    "memory_update": {
                        "type": "string",
                        "description": (
                            "Full updated long-term memory as markdown. Include all existing "
                            "facts plus new ones. Return unchanged if nothing new."
                        ),
                    },
                },
                "required": ["history_entry", "memory_update"],
            },
        },
    }
]

_SYSTEM_PROMPT = (
    "You are a memory consolidation agent for a Claude Code agent. "
    "Extract key facts from this task execution and call save_memory. "
    "Focus on: decisions made, patterns learned, errors and how they were resolved, "
    "project-specific facts, user preferences revealed. "
    "Be concise. history_entry: 2-5 sentences with [YYYY-MM-DD HH:MM] prefix. "
    "memory_update: full MEMORY.md content; unchanged if nothing new."
)


class CCMemoryConsolidator:
    """Post-task memory consolidation for CC agents.

    Calls an LLM to extract key facts from a completed task and persist them
    to the agent's MEMORY.md and HISTORY.md files, then syncs the SQLite index.
    """

    def __init__(self, workspace: Path) -> None:
        self._memory_dir = workspace / "memory"

    async def consolidate(
        self,
        task_title: str,
        task_output: str,
        task_status: str,
        task_id: str,
        model: str,
    ) -> bool:
        """Extract facts from CC task output and persist to MEMORY.md + HISTORY.md.

        Args:
            task_title: The task title or description.
            task_output: Final output text from the CC subprocess.
            task_status: "completed" or "error".
            task_id: Task identifier for logging.
            model: Resolved LLM model string (e.g. "claude-haiku-4-5-20251001").

        Returns:
            True on success (or no-op), False on failure.
        """
        self._memory_dir.mkdir(parents=True, exist_ok=True)
        current_memory = self._read_memory()

        # Truncate output to avoid huge prompts
        truncated_output = task_output[:3000]
        if len(task_output) > 3000:
            truncated_output += f"\n... [truncated, full output: {len(task_output)} chars]"

        prompt = (
            f"## Current Long-term Memory\n{current_memory or '(empty)'}\n\n"
            f"## Task to Consolidate\n"
            f"Title: {task_title}\n"
            f"Status: {task_status}\n"
            f"Task ID: {task_id}\n"
            f"Output:\n{truncated_output}"
        )

        try:
            response = await litellm.acompletion(
                model=model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                tools=_SAVE_MEMORY_TOOL,
                tool_choice={"type": "function", "function": {"name": "save_memory"}},
            )
        except Exception:
            logger.exception("CCMemoryConsolidator: LLM call failed for task %s", task_id)
            return False

        # Extract tool call arguments
        try:
            tool_calls = response.choices[0].message.tool_calls
            if not tool_calls:
                logger.warning("CCMemoryConsolidator: no tool call returned for task %s", task_id)
                return False
            args = tool_calls[0].function.arguments
            if isinstance(args, str):
                args = json.loads(args)
        except Exception:
            logger.exception("CCMemoryConsolidator: failed to parse tool call for task %s", task_id)
            return False

        if not isinstance(args, dict):
            logger.warning("CCMemoryConsolidator: unexpected args type %s", type(args).__name__)
            return False

        # Persist to files
        if entry := args.get("history_entry"):
            if not isinstance(entry, str):
                entry = json.dumps(entry, ensure_ascii=False)
            self._append_history(entry)
            self._sync_index(self._memory_dir / "HISTORY.md")

        if update := args.get("memory_update"):
            if not isinstance(update, str):
                update = json.dumps(update, ensure_ascii=False)
            if update != current_memory:
                self._write_memory(update)
                self._sync_index(self._memory_dir / "MEMORY.md")

        logger.info("CCMemoryConsolidator: consolidated task %s (%s)", task_id, task_status)
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_memory(self) -> str:
        """Read current MEMORY.md content."""
        path = self._memory_dir / "MEMORY.md"
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8").strip()

    def _write_memory(self, content: str) -> None:
        """Overwrite MEMORY.md with file lock for concurrent safety."""
        path = self._memory_dir / "MEMORY.md"
        lock = FileLock(str(path) + ".lock")
        with lock:
            path.write_text(content, encoding="utf-8")

    def _append_history(self, entry: str) -> None:
        """Append an entry to HISTORY.md with file lock."""
        path = self._memory_dir / "HISTORY.md"
        lock = FileLock(str(path) + ".lock")
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        # Only prepend timestamp if not already present in entry
        if not entry.startswith("["):
            entry = f"[{now}] {entry}"
        with lock:
            existing = path.read_text(encoding="utf-8") if path.exists() else ""
            path.write_text(existing + entry + "\n\n", encoding="utf-8")

    def _sync_index(self, path: Path) -> None:
        """Sync the MemoryIndex SQLite for the given file (best-effort)."""
        try:
            from mc.memory.index import MemoryIndex
            index = MemoryIndex(self._memory_dir)
            index.sync_file(path)
        except Exception:
            logger.debug("CCMemoryConsolidator: SQLite sync skipped for %s", path.name)
```

---

## File 2 (NEW): `tests/cc/test_memory_consolidator.py`

Write tests covering:

1. `test_consolidate_writes_history` — after consolidate(), HISTORY.md contains the history_entry returned by mocked LLM
2. `test_consolidate_updates_memory` — MEMORY.md is overwritten when memory_update differs from current
3. `test_consolidate_skips_memory_if_unchanged` — MEMORY.md not written when memory_update equals current content
4. `test_consolidate_returns_false_on_llm_failure` — when litellm raises, returns False without raising
5. `test_consolidate_returns_false_on_no_tool_call` — when LLM returns no tool calls, returns False
6. `test_consolidate_error_status_task` — tasks with status="error" consolidate normally
7. `test_consolidate_creates_memory_dir` — memory/ dir created if missing

Use `unittest.mock.patch("litellm.acompletion")` to mock the LLM call.
Build a mock response like:
```python
from unittest.mock import MagicMock, AsyncMock, patch
import json

def _make_llm_response(history_entry, memory_update):
    tool_call = MagicMock()
    tool_call.function.arguments = json.dumps({
        "history_entry": history_entry,
        "memory_update": memory_update,
    })
    msg = MagicMock()
    msg.tool_calls = [tool_call]
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    return response
```

All tests use `tmp_path` fixture and `pytest.mark.asyncio`.

---

## File 3 (PATCH): `mc/executor.py`

**Location**: after the `if result.is_error: ... else: _complete_cc_task(...)` block at around line 1600.
The current block ends at line ~1631 (after `on_task_completed` callback).

Add a fire-and-forget consolidation AFTER the if/else block (runs for both success and error):

```python
        # Fire-and-forget post-CC memory consolidation (best-effort, non-blocking).
        # Mirrors nanobot's end_task_session() — runs for both success and error tasks.
        _cc_task_status = "error" if result.is_error else "completed"
        _cc_ws_cwd = ws_ctx.cwd  # capture before ws_ctx goes out of scope

        async def _post_cc_consolidate():
            try:
                from claude_code.memory_consolidator import CCMemoryConsolidator
                from mc.types import is_tier_reference
                from mc.tier_resolver import TierResolver
                _model = "tier:standard-low"
                if is_tier_reference(_model):
                    _model = TierResolver(self._bridge).resolve_model(_model) or _model
                consolidator = CCMemoryConsolidator(_cc_ws_cwd)
                await consolidator.consolidate(
                    task_title=title,
                    task_output=result.output or "",
                    task_status=_cc_task_status,
                    task_id=task_id,
                    model=_model,
                )
                logger.info("[executor] CC memory consolidation done for '%s'", title)
            except Exception:
                logger.warning(
                    "[executor] CC memory consolidation failed for '%s'", title, exc_info=True
                )

        _t = asyncio.create_task(_post_cc_consolidate())
        _background_tasks.add(_t)
        _t.add_done_callback(_background_tasks.discard)
```

**Where exactly to insert**: right after the closing of the `else:` block for `_complete_cc_task`, i.e., after:
```python
            if self._on_task_completed:
                try:
                    await self._on_task_completed(task_id, result.output or "")
                except Exception:
                    logger.exception("[executor] on_task_completed failed for CC task '%s'", title)
```

---

## File 4 (PATCH): `mc/chat_handler.py`

**Location**: after `mark_chat_done` (line ~265) and before the `return` (line ~268) in the CC branch.

Add fire-and-forget after:
```python
                logger.info("[chat] CC response sent for @%s", agent_name)
                return
```

Change to:
```python
                logger.info("[chat] CC response sent for @%s", agent_name)

                # Fire-and-forget memory consolidation for CC chat
                _cc_ws_cwd_chat = ws_ctx.cwd

                async def _post_chat_consolidate():
                    try:
                        from claude_code.memory_consolidator import CCMemoryConsolidator
                        from mc.types import is_tier_reference
                        from mc.tier_resolver import TierResolver
                        _model = "tier:standard-low"
                        if is_tier_reference(_model):
                            _model = TierResolver(self._bridge).resolve_model(_model) or _model
                        consolidator = CCMemoryConsolidator(_cc_ws_cwd_chat)
                        await consolidator.consolidate(
                            task_title=f"chat with @{agent_name}",
                            task_output=result,
                            task_status="completed",
                            task_id=task_id,
                            model=_model,
                        )
                        logger.info("[chat] CC memory consolidation done for @%s", agent_name)
                    except Exception:
                        logger.warning(
                            "[chat] CC memory consolidation failed for @%s", agent_name, exc_info=True
                        )

                asyncio.create_task(_post_chat_consolidate())
                return
```

---

## File 5 (PATCH): `PATCHES.md`

Add an entry to the **"vendor/claude-code/ patches"** section (create section if missing, at the end of file):

```markdown
## vendor/claude-code/ (CC Backend)

### New Files

| File | Description |
|------|-------------|
| `claude_code/memory_consolidator.py` | `CCMemoryConsolidator`: post-task LLM consolidation into MEMORY.md + HISTORY.md + SQLite index; mirrors nanobot `end_task_session()` |
```

---

## Verification

```bash
# Run new tests
uv run pytest tests/cc/test_memory_consolidator.py -v

# Run full CC test suite
uv run pytest tests/cc/ -v

# Regression (skip known-broken tests)
uv run pytest tests/ -v --timeout=30 -k "not (test_auto_title or test_manual_tasks or test_mention or test_process_manager or test_state_machine or test_subscriptions)"
```

All new tests must pass. No regressions in existing tests.

Commit message: `feat(cc): CCMemoryConsolidator — post-task memory consolidation for CC agents`
