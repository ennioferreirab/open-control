# Story 13-1: Hybrid SQLite Memory Search

## Goal
Add hybrid BM25+vector search over agent memory (MEMORY.md + HISTORY.md), usable by both the nanobot agent loop AND the CC Backend. Markdown stays source of truth; SQLite is a derived, rebuildable index.

## Architecture
One core engine (`MemoryIndex`) encapsulates schema, sync, and search in a single class. Two thin consumers: `HybridMemoryStore` for nanobot agents, `search_memory` MCP tool for CC agents.

## Tech Stack
Python 3.11+, SQLite FTS5 (stdlib), `sqlite-vec` (new dep), `litellm` (existing for embeddings).

## Module Design
```
mc/memory/
  __init__.py          # re-exports MemoryIndex, SearchResult
  providers.py         # EmbeddingProvider protocol + NullProvider + LiteLLMProvider
  index.py             # MemoryIndex: schema + sync + search
  store.py             # HybridMemoryStore(MemoryStore) — thin nanobot wrapper
```

## Tasks
- Task 0: Dependencies + Package setup
- Task 1: Embedding Providers
- Task 2: MemoryIndex core engine
- Task 3: HybridMemoryStore nanobot wrapper
- Task 4: Wire nanobot (context.py + loop.py)
- Task 5: Wire CC Backend (workspace.py + mcp_bridge.py)
- Task 6: Docs + SKILL.md

## Acceptance Criteria
- `uv run pytest tests/mc/memory/ -v` passes
- FTS-only smoke test works without embedding model
- No regressions in existing tests
- PATCHES.md updated for vendor changes
