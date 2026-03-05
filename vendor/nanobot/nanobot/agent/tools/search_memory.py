"""Search memory tool — hybrid BM25+vector search over agent memory."""

from __future__ import annotations

from typing import Any

from nanobot.agent.tools.base import Tool


class SearchMemoryTool(Tool):
    """Search agent memory (MEMORY.md + HISTORY.md) using hybrid BM25+vector search."""

    def __init__(self, memory_store: Any = None):
        self._memory_store = memory_store

    @property
    def name(self) -> str:
        return "search_memory"

    @property
    def description(self) -> str:
        return (
            "Search agent memory and history for relevant past events, decisions, "
            "and facts. Uses hybrid BM25 keyword + optional vector search."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query — keywords or natural language question.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5).",
                    "minimum": 1,
                    "maximum": 50,
                },
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> str:
        query = kwargs.get("query", "")
        top_k = kwargs.get("top_k", 5)

        if not self._memory_store or not hasattr(self._memory_store, "search"):
            return "Memory search is not available."

        result = self._memory_store.search(query, top_k=top_k)
        return result if result else "No matching memories found."
