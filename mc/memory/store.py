"""Memory store adapter that adds hybrid search indexing."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

from nanobot.agent.memory import MemoryStore

from mc.infrastructure.runtime_home import get_runtime_path
from mc.memory.index import MemoryIndex

logger = logging.getLogger(__name__)

# Defaults — overridable via memory_settings.json
_DEFAULT_HISTORY_CONTEXT_DAYS = 5
_DEFAULT_MEMORY_CONTEXT_MAX_CHARS = 40_000
_CONSOLIDATION_FAILURE_COOLDOWN_SECONDS = 300


class HybridMemoryStore(MemoryStore):
    def __init__(self, workspace: Path, embedding_model: str | None = None):
        super().__init__(workspace)
        settings = self._read_settings()
        model = (
            embedding_model
            or os.environ.get("NANOBOT_MEMORY_EMBEDDING_MODEL")
            or settings.get("embedding_model")
            or None
        )
        self._history_context_days: int = settings.get(
            "history_context_days", _DEFAULT_HISTORY_CONTEXT_DAYS
        )
        self._memory_context_max_chars: int = settings.get(
            "memory_context_max_chars", _DEFAULT_MEMORY_CONTEXT_MAX_CHARS
        )
        self._index = MemoryIndex(self.memory_dir, model)
        self._consolidation_in_progress = False
        self._consolidation_retry_after = 0.0

    @staticmethod
    def _read_settings() -> dict:
        """Read memory settings from ~/.nanobot/memory_settings.json."""
        try:
            settings_path = get_runtime_path("memory_settings.json")
            if not settings_path.exists():
                return {}
            return json.loads(settings_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def get_memory_context(self) -> str:
        """Build memory context: long-term memory + recent history entries."""
        parts: list[str] = []

        long_term = self.read_long_term().strip()
        if long_term:
            parts.append(f"## Long-term Memory\n{long_term}")

        recent = self._read_recent_history(self._history_context_days)
        if recent:
            parts.append(f"## Recent History (last {self._history_context_days} days)\n{recent}")

        combined = "\n\n".join(parts)
        if len(combined) > self._memory_context_max_chars:
            combined = combined[: self._memory_context_max_chars] + "\n...(truncated)"
        return combined

    def _read_recent_history(self, days: int) -> str:
        """Return HISTORY.md entries from the last N days."""
        if days <= 0:
            return ""
        with self._lock:
            if not self.history_file.exists():
                return ""
            text = self.history_file.read_text(encoding="utf-8")
        if not text.strip():
            return ""

        cutoff = datetime.now() - timedelta(days=days)
        date_re = re.compile(r"^\[(\d{4}-\d{2}-\d{2})")
        kept: list[str] = []
        for entry in text.split("\n\n"):
            entry = entry.strip()
            if not entry:
                continue
            m = date_re.match(entry)
            if not m:
                continue  # skip undated entries (legacy; new writes always have dates)
            try:
                entry_date = datetime.strptime(m.group(1), "%Y-%m-%d")
                # Handle date ranges like [2026-02-26 to 2026-03-04]
                range_match = re.search(r"to\s+(\d{4}-\d{2}-\d{2})", entry[:60])
                if range_match:
                    end_date = datetime.strptime(range_match.group(1), "%Y-%m-%d")
                    entry_date = max(entry_date, end_date)
                if entry_date >= cutoff:
                    kept.append(entry)
            except ValueError:
                continue
        return "\n\n".join(kept)

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

        now = time.monotonic()
        if now < self._consolidation_retry_after:
            logger.info(
                "Skipping file-based memory consolidation during cooldown (%.0fs remaining)",
                self._consolidation_retry_after - now,
            )
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

                ran = False
                while is_history_above_threshold(self.memory_dir):
                    ok = await consolidate_history_and_memory(self.memory_dir, model)
                    if not ok:
                        self._consolidation_retry_after = (
                            time.monotonic() + _CONSOLIDATION_FAILURE_COOLDOWN_SECONDS
                        )
                        logger.warning("File-based memory consolidation returned False")
                        break
                    ran = True
                    self._consolidation_retry_after = 0.0
                if ran:
                    self._index.sync()
                    logger.info("File-based memory consolidation completed")
            except Exception:
                self._consolidation_retry_after = (
                    time.monotonic() + _CONSOLIDATION_FAILURE_COOLDOWN_SECONDS
                )
                logger.exception("File-based memory consolidation failed")
            finally:
                self._consolidation_in_progress = False

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_run())  # noqa: RUF006
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
