"""Memory store adapter that adds hybrid search indexing."""

from __future__ import annotations

import os
from pathlib import Path

from mc.memory.index import MemoryIndex
from nanobot.agent.memory import MemoryStore


class HybridMemoryStore(MemoryStore):
    def __init__(self, workspace: Path, embedding_model: str | None = None):
        super().__init__(workspace)
        model = embedding_model or os.environ.get("NANOBOT_MEMORY_EMBEDDING_MODEL")
        self._index = MemoryIndex(self.memory_dir, model)

    def write_long_term(self, content: str) -> None:
        super().write_long_term(content)
        self._index.sync_file(self.memory_file)

    def append_history(self, entry: str) -> None:
        super().append_history(entry)
        self._index.sync_file(self.history_file)

    def search(self, query: str, top_k: int = 5, **kwargs) -> str:
        results = self._index.search(query, top_k, **kwargs)
        return chr(10).join(f"- {result.content.strip()}" for result in results) if results else ""
