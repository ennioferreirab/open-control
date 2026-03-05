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
            if update.strip() != current_memory:
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
