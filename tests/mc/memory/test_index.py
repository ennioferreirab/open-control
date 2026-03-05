import time

from mc.memory.index import MemoryIndex, SearchResult


def test_sync_indexes_file(tmp_path):
    (tmp_path / "MEMORY.md").write_text("Project memory includes keyword: banana.", encoding="utf-8")
    idx = MemoryIndex(tmp_path)

    idx.sync()

    results = idx.search("banana")
    assert results
    assert any("banana" in result.content.lower() for result in results)


def test_sync_idempotent(tmp_path):
    (tmp_path / "MEMORY.md").write_text("Stable content for indexing.", encoding="utf-8")
    idx = MemoryIndex(tmp_path)

    idx.sync()
    idx.sync()

    files_count = idx._conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    assert files_count == 1


def test_sync_reindexes_on_change(tmp_path):
    memory_file = tmp_path / "MEMORY.md"
    memory_file.write_text("First version with alpha.", encoding="utf-8")
    idx = MemoryIndex(tmp_path)

    idx.sync()
    memory_file.write_text("Second version with omega.", encoding="utf-8")
    idx.sync()

    results = idx.search("omega")
    assert results
    assert any("omega" in result.content.lower() for result in results)


def test_bm25_finds_keyword(tmp_path):
    (tmp_path / "MEMORY.md").write_text("Python is great.", encoding="utf-8")
    idx = MemoryIndex(tmp_path)

    idx.sync()
    results = idx.search("Python")

    assert results
    assert any("python" in result.content.lower() for result in results)


def test_bm25_no_match_returns_empty(tmp_path):
    (tmp_path / "MEMORY.md").write_text("Python is great.", encoding="utf-8")
    idx = MemoryIndex(tmp_path)

    idx.sync()
    results = idx.search("xyznonexistent")

    assert results == []


def test_search_fts_fallback(tmp_path):
    (tmp_path / "MEMORY.md").write_text("Fallback search should find Python.", encoding="utf-8")
    idx = MemoryIndex(tmp_path)

    idx.sync()
    results = idx.search("Python")

    assert idx._provider_is_null is True
    assert results
    assert any("python" in result.content.lower() for result in results)


def test_temporal_decay_penalizes_old(tmp_path):
    idx = MemoryIndex(tmp_path)
    now = time.time()
    results = [
        SearchResult(content="recent", score=1.0, source="a.md", created_at=now),
        SearchResult(
            content="old",
            score=1.0,
            source="b.md",
            created_at=now - (30 * 86400),
        ),
    ]

    decayed = idx._temporal_decay(results, decay_lambda=0.01)

    recent_score = next(result.score for result in decayed if result.content == "recent")
    old_score = next(result.score for result in decayed if result.content == "old")
    assert old_score < recent_score


def test_mmr_picks_diverse(tmp_path):
    idx = MemoryIndex(tmp_path)
    now = time.time()
    results = [
        SearchResult(content="duplicate duplicate text", score=1.0, source="a.md", created_at=now),
        SearchResult(content="duplicate duplicate text", score=0.9, source="b.md", created_at=now),
        SearchResult(content="unique zebra topic", score=0.8, source="c.md", created_at=now),
    ]

    reranked = idx._mmr_rerank(results, top_k=2, diversity=0.4)

    assert len(reranked) == 2
    assert any(result.content == "unique zebra topic" for result in reranked)


def test_rebuild_clears_and_reindexes(tmp_path):
    (tmp_path / "MEMORY.md").write_text("Rebuild keeps this searchable: comet.", encoding="utf-8")
    idx = MemoryIndex(tmp_path)

    idx.sync()
    idx.rebuild()

    results = idx.search("comet")
    assert results
    assert any("comet" in result.content.lower() for result in results)


def test_index_reads_embedding_model_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("NANOBOT_MEMORY_EMBEDDING_MODEL", "some-model")
    from mc.memory.index import MemoryIndex

    idx = MemoryIndex(tmp_path)
    assert idx._provider.__class__.__name__ == "LiteLLMProvider"
    assert idx._provider.model == "some-model"
