"""File-based memory consolidation — compacts HISTORY.md + MEMORY.md into a fresh MEMORY.md."""

from __future__ import annotations

import json
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock

from mc.infrastructure.providers.factory import create_provider

logger = logging.getLogger(__name__)

# --- Configurable constants ---
HISTORY_CONSOLIDATION_THRESHOLD_CHARS = 160_000  # ~40K tokens
MEMORY_TARGET_MAX_CHARS = 12_000  # ~3K tokens — target size for consolidated MEMORY.md
MEMORY_CONSOLIDATION_MODEL = "tier:standard-medium"

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


def _build_archive_block(snapshot_text: str, snapshot_size: int, archived_at: datetime) -> str:
    timestamp = archived_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    body = snapshot_text
    if body and not body.endswith("\n"):
        body += "\n"
    return (
        f"## Archived Snapshot [{timestamp}]\n"
        "Source: HISTORY.md\n"
        f"Chars: {snapshot_size}\n\n"
        f"{body}\n---\n"
    )


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
    model: str | None = None,
    *,
    memory_target_max_chars: int = MEMORY_TARGET_MAX_CHARS,
) -> bool:
    """Consolidate HISTORY.md + MEMORY.md into a fresh MEMORY.md, archive history safely.

    Returns True on success, False on failure.
    """
    history_file = memory_dir / "HISTORY.md"
    memory_file = memory_dir / "MEMORY.md"
    archive_file = memory_dir / "HISTORY_ARCHIVE.md"

    if not history_file.exists() or history_file.stat().st_size == 0:
        return True  # Nothing to consolidate

    consolidation_lock = FileLock(str(memory_dir / ".consolidation.lock"), timeout=30)
    memory_lock = FileLock(str(memory_dir / ".memory.lock"), timeout=30)
    snapshot_path: Path | None = None

    with consolidation_lock:
        with memory_lock:
            if not history_file.exists():
                return True
            snapshot_history_bytes = history_file.read_bytes()
            if not snapshot_history_bytes:
                return True
            if len(snapshot_history_bytes) <= HISTORY_CONSOLIDATION_THRESHOLD_CHARS:
                return True
            memory_text = memory_file.read_text(encoding="utf-8") if memory_file.exists() else ""
            snapshot_handle = tempfile.NamedTemporaryFile(
                mode="wb",
                delete=False,
                prefix="nanobot-history-snapshot-",
                suffix=".md",
            )
            try:
                snapshot_handle.write(snapshot_history_bytes)
                snapshot_handle.flush()
                snapshot_path = Path(snapshot_handle.name)
            finally:
                snapshot_handle.close()

        history_text = snapshot_history_bytes.decode("utf-8", errors="replace")

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
            provider, resolved_model = create_provider(model or MEMORY_CONSOLIDATION_MODEL)
            response = await provider.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                tools=_CONSOLIDATION_TOOL,
                model=resolved_model,
            )
        except Exception:
            logger.exception("consolidate_history_and_memory: LLM call failed")
            return False

        # Parse tool call
        try:
            if not response.tool_calls:
                logger.warning("consolidate_history_and_memory: no tool call returned")
                return False
            args = response.tool_calls[0].arguments
            if isinstance(args, str):
                args = json.loads(args)
        except Exception:
            logger.exception("consolidate_history_and_memory: failed to parse tool call")
            return False

        new_memory = args.get("memory", "")
        if not isinstance(new_memory, str) or not new_memory.strip():
            logger.warning("consolidate_history_and_memory: empty memory returned")
            return False

        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y-%m-%d_%H%M%S")

        try:
            with memory_lock:
                current_history_bytes = history_file.read_bytes() if history_file.exists() else b""
                if not current_history_bytes.startswith(snapshot_history_bytes):
                    logger.warning(
                        "consolidate_history_and_memory: history changed during consolidation; aborting commit"
                    )
                    return False

                tail_bytes = current_history_bytes[len(snapshot_history_bytes) :]
                archive_block = _build_archive_block(history_text, len(snapshot_history_bytes), now)
                existing_archive = (
                    archive_file.read_text(encoding="utf-8") if archive_file.exists() else ""
                )
                archive_prefix = (
                    "" if not existing_archive or existing_archive.endswith("\n") else "\n"
                )
                archive_file.write_text(
                    existing_archive + archive_prefix + archive_block, encoding="utf-8"
                )

                if memory_text.strip():
                    archive_memory = memory_dir / f"MEMORY_{timestamp}.md"
                    archive_memory.write_text(memory_text, encoding="utf-8")

                memory_file.write_text(new_memory, encoding="utf-8")
                history_file.write_bytes(tail_bytes)

            try:
                from mc.memory.index import MemoryIndex

                index = MemoryIndex(memory_dir)
                index.sync()
            except Exception:
                logger.debug("consolidate_history_and_memory: SQLite sync skipped")

            logger.info(
                "consolidate_history_and_memory: archived snapshot to %s, new memory %d chars, tail %d bytes",
                archive_file.name,
                len(new_memory),
                len(tail_bytes),
            )
            return True
        finally:
            if snapshot_path is not None:
                try:
                    snapshot_path.unlink(missing_ok=True)
                except Exception:
                    logger.debug(
                        "consolidate_history_and_memory: failed to delete snapshot %s",
                        snapshot_path,
                    )
