---
name: memory
description: Two-layer memory system with hybrid search recall.
always: true
---

# Memory

## Structure

- `memory/MEMORY.md` — Long-term facts (preferences, project context, relationships). Always loaded into your context.
- `memory/HISTORY.md` — Append-only event log. NOT loaded into context. Each entry starts with [YYYY-MM-DD HH:MM].

## Search Past Events

**Preferred: use the `search_memory` tool** for hybrid BM25 + optional vector search:

```
search_memory(query="keyword or question", top_k=5)
```

This searches both MEMORY.md and HISTORY.md using full-text search with temporal decay (recent events rank higher) and diversity reranking.

**Fallback:** You can also use grep for simple keyword matching:
```bash
grep -i "keyword" memory/HISTORY.md
```

## Hybrid Search Configuration

The search engine is powered by SQLite FTS5 (always available) with optional vector embeddings.

**Environment variable:** `NANOBOT_MEMORY_EMBEDDING_MODEL`
- Not set (default): FTS5/BM25 keyword search only
- `ollama/nomic-embed-text`: Local embeddings via Ollama
- `mistral/mistral-embed`: Mistral cloud embeddings
- Any model supported by [litellm](https://docs.litellm.ai/docs/embedding/supported_embedding)

**Search parameters** (advanced, passed via kwargs):
- `vector_weight` (0.0-1.0, default 0.5): Balance BM25 vs vector. 0=pure keyword, 1=pure semantic.
- `decay_lambda` (0.0-0.1, default 0.01): Temporal decay rate. Higher = more aggressive recency bias.
- `mmr_diversity` (0.0-1.0, default 0.7): Result diversity. Lower = more diverse, less relevant.

## When to Update MEMORY.md

Write important facts immediately using `edit_file` or `write_file`:
- User preferences ("I prefer dark mode")
- Project context ("The API uses OAuth2")
- Relationships ("Alice is the project lead")

## Auto-consolidation

Old conversations are automatically summarized and appended to HISTORY.md when the session grows large. Long-term facts are extracted to MEMORY.md. You don't need to manage this.
