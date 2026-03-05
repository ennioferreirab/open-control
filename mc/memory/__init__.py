"""Hybrid BM25+vector search over agent memory."""

from mc.memory.consolidation import (
    HISTORY_CONSOLIDATION_THRESHOLD_CHARS,
    MEMORY_TARGET_MAX_CHARS,
    consolidate_history_and_memory,
    is_history_above_threshold,
)
from mc.memory.index import MemoryIndex, SearchResult

__all__ = [
    "HISTORY_CONSOLIDATION_THRESHOLD_CHARS",
    "MEMORY_TARGET_MAX_CHARS",
    "MemoryIndex",
    "SearchResult",
    "consolidate_history_and_memory",
    "is_history_above_threshold",
]
