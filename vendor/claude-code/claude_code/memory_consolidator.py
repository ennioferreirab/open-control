"""Post-task memory consolidation adapter for Claude Code agents."""

from __future__ import annotations

import logging
from pathlib import Path

from mc.memory import consolidate_task_output

logger = logging.getLogger(__name__)


class CCMemoryConsolidator:
    """Thin adapter that routes Claude Code memory writes through mc.memory."""

    def __init__(self, workspace: Path) -> None:
        self._workspace = workspace

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
        ok = await consolidate_task_output(
            self._workspace,
            task_title=task_title,
            task_output=task_output,
            task_status=task_status,
            task_id=task_id,
            model=model,
        )
        if ok:
            logger.info("CCMemoryConsolidator: consolidated task %s (%s)", task_id, task_status)
        return ok
