"""Canonical helpers shared by nanobot and Claude Code memory backends."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from mc.memory.policy import find_invalid_memory_files
from mc.memory.store import HybridMemoryStore
from mc.provider_factory import create_provider

logger = logging.getLogger(__name__)
MEMORY_CONSOLIDATION_MODEL = "tier:standard-medium"

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

DEFAULT_TASK_CONSOLIDATION_SYSTEM_PROMPT = (
    "You are a memory consolidation agent. "
    "Extract key facts from this task execution and call save_memory. "
    "Focus on: decisions made, patterns learned, errors and how they were resolved, "
    "project-specific facts, user preferences revealed. "
    "Be concise. history_entry: 2-5 sentences with [YYYY-MM-DD HH:MM] prefix. "
    "memory_update: full MEMORY.md content; unchanged if nothing new."
)


def create_memory_store(workspace: Path, embedding_model: str | None = None) -> HybridMemoryStore:
    """Return the canonical memory store implementation for a workspace."""
    quarantine_invalid_memory_files(workspace)
    return HybridMemoryStore(workspace, embedding_model=embedding_model)


def quarantine_invalid_memory_files(
    workspace: Path,
    quarantine_root: Path | None = None,
) -> list[Path]:
    """Move legacy memory contract violations out of memory/ into quarantine."""
    from mc.memory.index import MemoryIndex

    memory_dir = workspace / "memory"
    invalid_paths = find_invalid_memory_files(memory_dir)
    if not invalid_paths:
        return []

    quarantine_root = quarantine_root or (workspace / ".memory-quarantine")
    quarantine_root.mkdir(parents=True, exist_ok=True)
    moved: list[Path] = []

    def _unique_target(name: str) -> Path:
        candidate = quarantine_root / name
        if not candidate.exists():
            return candidate
        stem = candidate.stem
        suffix = candidate.suffix
        idx = 2
        while True:
            candidate = quarantine_root / f"{stem}-{idx}{suffix}"
            if not candidate.exists():
                return candidate
            idx += 1

    for path in invalid_paths:
        target = _unique_target(path.name)
        shutil.move(str(path), str(target))
        moved.append(target)
        logger.warning(
            "Quarantined invalid memory artifact '%s' to '%s'",
            path,
            target,
        )

    if memory_dir.exists():
        MemoryIndex(memory_dir).sync()

    return moved


async def consolidate_task_output(
    workspace: Path,
    *,
    task_title: str,
    task_output: str,
    task_status: str,
    task_id: str,
    model: str | None = None,
    system_prompt: str | None = None,
    max_output_chars: int = 3000,
) -> bool:
    """Consolidate task output into MEMORY.md and HISTORY.md using the canonical store."""
    store = create_memory_store(workspace)
    current_memory = store.read_long_term().strip()

    truncated_output = task_output[:max_output_chars]
    if len(task_output) > max_output_chars:
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
        provider, resolved_model = create_provider(model or MEMORY_CONSOLIDATION_MODEL)
        response = await provider.chat(
            messages=[
                {"role": "system", "content": system_prompt or DEFAULT_TASK_CONSOLIDATION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            tools=_SAVE_MEMORY_TOOL,
            model=resolved_model,
        )
    except Exception:
        logger.exception("Task memory consolidation LLM call failed for task %s", task_id)
        return False

    try:
        if not response.tool_calls:
            logger.warning("Task memory consolidation returned no tool call for task %s", task_id)
            return False
        args = response.tool_calls[0].arguments
        if isinstance(args, str):
            args = json.loads(args)
    except Exception:
        logger.exception("Task memory consolidation failed to parse tool call for task %s", task_id)
        return False

    if not isinstance(args, dict):
        logger.warning(
            "Task memory consolidation returned unexpected args type %s for task %s",
            type(args).__name__,
            task_id,
        )
        return False

    if entry := args.get("history_entry"):
        if not isinstance(entry, str):
            entry = json.dumps(entry, ensure_ascii=False)
        store.append_history(entry)

    if update := args.get("memory_update"):
        if not isinstance(update, str):
            update = json.dumps(update, ensure_ascii=False)
        if update.strip() != current_memory:
            store.write_long_term(update)

    logger.info("Task memory consolidation done for task %s (%s)", task_id, task_status)
    return True
