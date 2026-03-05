"""File-based memory consolidation — compacts HISTORY.md + MEMORY.md into a fresh MEMORY.md."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import litellm
from filelock import FileLock

logger = logging.getLogger(__name__)

# --- Configurable constants ---
HISTORY_CONSOLIDATION_THRESHOLD_CHARS = 160_000  # ~40K tokens
MEMORY_TARGET_MAX_CHARS = 12_000  # ~3K tokens — target size for consolidated MEMORY.md

_CONSOLIDATION_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "save_consolidated_memory",
            "description": "Save the consolidated long-term memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory": {
                        "type": "string",
                        "description": "Full consolidated long-term memory as markdown.",
                    },
                },
                "required": ["memory"],
            },
        },
    }
]


def is_history_above_threshold(
    memory_dir: Path,
    threshold_chars: int = HISTORY_CONSOLIDATION_THRESHOLD_CHARS,
) -> bool:
    """Check if HISTORY.md exceeds the consolidation threshold."""
    history_file = memory_dir / "HISTORY.md"
    if not history_file.exists():
        return False
    return history_file.stat().st_size > threshold_chars


async def consolidate_history_and_memory(
    memory_dir: Path,
    model: str,
    *,
    memory_target_max_chars: int = MEMORY_TARGET_MAX_CHARS,
) -> bool:
    """Consolidate HISTORY.md + MEMORY.md into a fresh MEMORY.md, archive old files.

    Returns True on success, False on failure.
    """
    history_file = memory_dir / "HISTORY.md"
    memory_file = memory_dir / "MEMORY.md"

    if not history_file.exists() or history_file.stat().st_size == 0:
        return True  # Nothing to consolidate

    lock = FileLock(str(memory_dir / ".consolidation.lock"), timeout=30)
    with lock:
        history_text = history_file.read_text(encoding="utf-8")
        memory_text = memory_file.read_text(encoding="utf-8") if memory_file.exists() else ""

        system_prompt = (
            "You are a memory consolidation agent. "
            "Read the history log and current long-term memory, then call save_consolidated_memory "
            "with a fresh, comprehensive long-term memory that preserves ALL important facts, decisions, "
            "preferences, and patterns. "
            f"Keep the output under {memory_target_max_chars} characters (~{memory_target_max_chars // 4} tokens). "
            "Use concise markdown. Prioritize: user preferences > project facts > recent decisions > older context."
        )

        user_prompt = (
            f"## Current Long-term Memory\n{memory_text or '(empty)'}\n\n"
            f"## History Log to Consolidate\n{history_text}"
        )

        try:
            response = await litellm.acompletion(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                tools=_CONSOLIDATION_TOOL,
                tool_choice={"type": "function", "function": {"name": "save_consolidated_memory"}},
            )
        except Exception:
            logger.exception("consolidate_history_and_memory: LLM call failed")
            return False

        # Parse tool call
        try:
            tool_calls = response.choices[0].message.tool_calls
            if not tool_calls:
                logger.warning("consolidate_history_and_memory: no tool call returned")
                return False
            args = tool_calls[0].function.arguments
            if isinstance(args, str):
                args = json.loads(args)
        except Exception:
            logger.exception("consolidate_history_and_memory: failed to parse tool call")
            return False

        new_memory = args.get("memory", "")
        if not isinstance(new_memory, str) or not new_memory.strip():
            logger.warning("consolidate_history_and_memory: empty memory returned")
            return False

        # Archive old files with timestamp
        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y-%m-%d_%H%M")

        if history_file.exists():
            archive_history = memory_dir / f"HISTORY_{timestamp}.md"
            history_file.rename(archive_history)

        if memory_text.strip():
            archive_memory = memory_dir / f"MEMORY_{timestamp}.md"
            archive_memory.write_text(memory_text, encoding="utf-8")

        # Write new MEMORY.md
        memory_file.write_text(new_memory, encoding="utf-8")

        # Clear HISTORY.md (fresh start)
        history_file.write_text("", encoding="utf-8")

        # Sync SQLite index for all .md files (including archives)
        try:
            from mc.memory.index import MemoryIndex
            index = MemoryIndex(memory_dir)
            index.sync()
        except Exception:
            logger.debug("consolidate_history_and_memory: SQLite sync skipped")

        logger.info(
            "consolidate_history_and_memory: archived to %s, new memory %d chars",
            timestamp, len(new_memory),
        )
        return True
