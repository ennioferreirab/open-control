"""Memory store adapter that adds hybrid search indexing."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from mc.memory.index import MemoryIndex
from nanobot.agent.memory import MemoryStore

logger = logging.getLogger(__name__)


class HybridMemoryStore(MemoryStore):
    def __init__(self, workspace: Path, embedding_model: str | None = None):
        super().__init__(workspace)
        model = embedding_model or os.environ.get("NANOBOT_MEMORY_EMBEDDING_MODEL")
        self._index = MemoryIndex(self.memory_dir, model)
        self._consolidation_in_progress = False

    def write_long_term(self, content: str) -> None:
        super().write_long_term(content)
        self._index.sync_file(self.memory_file)

    def append_history(self, entry: str) -> None:
        super().append_history(entry)
        self._index.sync_file(self.history_file)
        self._maybe_trigger_consolidation()

    def _maybe_trigger_consolidation(self) -> None:
        """Check if HISTORY.md exceeds threshold and schedule consolidation if needed."""
        if self._consolidation_in_progress:
            return

        from mc.memory.consolidation import is_history_above_threshold
        if not is_history_above_threshold(self.memory_dir):
            return

        # Resolve model for consolidation
        model = self._resolve_consolidation_model()
        if not model:
            logger.warning("History above threshold but no consolidation model available")
            return

        self._consolidation_in_progress = True

        async def _run():
            try:
                from mc.memory.consolidation import consolidate_history_and_memory
                ok = await consolidate_history_and_memory(self.memory_dir, model)
                if ok:
                    self._index.sync()
                    logger.info("File-based memory consolidation completed")
                else:
                    logger.warning("File-based memory consolidation returned False")
            except Exception:
                logger.exception("File-based memory consolidation failed")
            finally:
                self._consolidation_in_progress = False

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_run())
        except RuntimeError:
            # No running event loop — skip async consolidation
            logger.debug("No event loop available for consolidation, skipping")
            self._consolidation_in_progress = False

    def _resolve_consolidation_model(self) -> str | None:
        """Resolve the model to use for file-based consolidation."""
        return os.environ.get("NANOBOT_CONSOLIDATION_MODEL", "openrouter/anthropic/claude-haiku")

    def search(self, query: str, top_k: int = 5, **kwargs) -> str:
        results = self._index.search(query, top_k, **kwargs)
        return chr(10).join(f"- {result.content.strip()}" for result in results) if results else ""
