import time
from datetime import datetime, timezone

from mc.memory.index import MemoryIndex, SearchResult


def test_sync_indexes_file(tmp_path):
    (tmp_path / "MEMORY.md").write_text(
        "Project memory includes keyword: banana.", encoding="utf-8"
    )
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


def test_sync_ignores_non_contract_markdown_files(tmp_path):
    (tmp_path / "MEMORY.md").write_text("Canonical memory entry about alpha.", encoding="utf-8")
    (tmp_path / "rogue_summary.md").write_text("Rogue artifact about zebra.", encoding="utf-8")
    idx = MemoryIndex(tmp_path)

    idx.sync()

    files = idx._conn.execute("SELECT path FROM files ORDER BY path").fetchall()
    assert files == [(str(tmp_path / "MEMORY.md"),)]
    assert idx.search("zebra") == []


def test_sync_prunes_previously_indexed_non_contract_markdown(tmp_path):
    (tmp_path / "MEMORY.md").write_text("Canonical memory entry about alpha.", encoding="utf-8")
    rogue = tmp_path / "rogue_summary.md"
    rogue.write_text("Rogue artifact about zebra.", encoding="utf-8")
    idx = MemoryIndex(tmp_path)

    with idx._conn:
        idx._conn.execute(
            "INSERT INTO files(path, hash, mtime) VALUES (?, ?, ?)",
            (str(rogue), "legacy", rogue.stat().st_mtime),
        )
        cur = idx._conn.execute(
            """
            INSERT INTO chunks(file_path, content, offset_start, offset_end, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (str(rogue), "Rogue artifact about zebra.", 0, 26, 0.0),
        )
        idx._conn.execute(
            "INSERT INTO chunks_fts(rowid, content) VALUES (?, ?)",
            (int(cur.lastrowid), "Rogue artifact about zebra."),
        )

    assert idx.search("zebra")

    idx.sync()

    assert idx.search("zebra") == []
    files = idx._conn.execute("SELECT path FROM files ORDER BY path").fetchall()
    assert files == [(str(tmp_path / "MEMORY.md"),)]


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


def test_search_with_url_characters_does_not_raise(tmp_path):
    (tmp_path / "MEMORY.md").write_text(
        "YouTube summaries for Kelvin Cleto channel and recent videos.",
        encoding="utf-8",
    )
    idx = MemoryIndex(tmp_path)

    idx.sync()
    results = idx.search(
        "Transcreva e resuma os videos do canal https://www.youtube.com/@eusoukelvincleto"
    )

    assert isinstance(results, list)


def test_history_archive_is_indexed_with_snapshot_timestamps(tmp_path):
    archive = tmp_path / "HISTORY_ARCHIVE.md"
    archive.write_text(
        "## Archived Snapshot [2026-03-01T10:00:00Z]\n"
        "Source: HISTORY.md\n"
        "Chars: 20\n\n"
        "Old deployment note.\n\n"
        "---\n"
        "## Archived Snapshot [2026-03-05T10:00:00Z]\n"
        "Source: HISTORY.md\n"
        "Chars: 22\n\n"
        "Recent deployment note.\n\n"
        "---\n",
        encoding="utf-8",
    )
    idx = MemoryIndex(tmp_path)

    idx.sync()

    rows = idx._conn.execute(
        "SELECT content, created_at FROM chunks WHERE file_path = ? ORDER BY created_at ASC",
        (str(archive),),
    ).fetchall()
    assert rows
    assert any("Old deployment note" in row[0] for row in rows)
    assert any("Recent deployment note" in row[0] for row in rows)
    assert (
        min(row[1] for row in rows) == datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc).timestamp()
    )
    assert (
        max(row[1] for row in rows) == datetime(2026, 3, 5, 10, 0, tzinfo=timezone.utc).timestamp()
    )


def test_history_archive_search_prefers_recent_snapshot(tmp_path):
    archive = tmp_path / "HISTORY_ARCHIVE.md"
    archive.write_text(
        "## Archived Snapshot [2026-02-01T10:00:00Z]\n"
        "Source: HISTORY.md\n"
        "Chars: 35\n\n"
        "Deployment runbook marker oldrelease.\n\n"
        "---\n"
        "## Archived Snapshot [2026-03-05T10:00:00Z]\n"
        "Source: HISTORY.md\n"
        "Chars: 38\n\n"
        "Deployment runbook marker newrelease.\n\n"
        "---\n",
        encoding="utf-8",
    )
    idx = MemoryIndex(tmp_path)

    idx.sync()
    results = idx.search("deployment runbook marker", top_k=2)

    assert results
    assert "newrelease" in results[0].content


def test_legacy_history_snapshot_files_are_excluded_from_index(tmp_path):
    legacy = tmp_path / "HISTORY_2026-03-05_2214.md"
    legacy.write_text("Legacy history snapshot with asteroid.", encoding="utf-8")
    idx = MemoryIndex(tmp_path)

    idx.sync()

    results = idx.search("asteroid")
    assert not results

    rows = idx._conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE file_path = ?",
        (str(legacy),),
    ).fetchone()
    assert rows is not None
    assert rows[0] == 0


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


def test_sync_canonicalizes_shared_symlink_paths(tmp_path):
    global_memory = tmp_path / "agents" / "nanobot" / "memory"
    global_memory.mkdir(parents=True)
    (global_memory / "MEMORY.md").write_text("Shared banana memory.", encoding="utf-8")

    board_memory = tmp_path / "boards" / "default" / "agents" / "nanobot" / "memory"
    board_memory.mkdir(parents=True)
    (board_memory / "MEMORY.md").symlink_to(global_memory / "MEMORY.md")
    (board_memory / "memory-index.sqlite").symlink_to(global_memory / "memory-index.sqlite")

    global_idx = MemoryIndex(global_memory)
    global_idx.sync()

    board_idx = MemoryIndex(board_memory)
    board_idx.sync()

    tracked_paths = [
        row[0] for row in board_idx._conn.execute("SELECT path FROM files ORDER BY path").fetchall()
    ]
    assert tracked_paths == [str(global_memory / "MEMORY.md")]

    sources = [
        row[0]
        for row in board_idx._conn.execute(
            "SELECT DISTINCT file_path FROM chunks ORDER BY file_path"
        ).fetchall()
    ]
    assert sources == [str(global_memory / "MEMORY.md")]

    results = board_idx.search("banana", top_k=10)
    assert len(results) == 1
    assert results[0].source == str(global_memory / "MEMORY.md")


def test_sync_prunes_legacy_duplicates_for_equivalent_shared_paths(tmp_path):
    global_memory = tmp_path / "agents" / "nanobot" / "memory"
    global_memory.mkdir(parents=True)
    shared_file = global_memory / "MEMORY.md"
    shared_file.write_text("Shared banana memory.", encoding="utf-8")

    board_memory = tmp_path / "boards" / "default" / "agents" / "nanobot" / "memory"
    board_memory.mkdir(parents=True)
    board_file = board_memory / "MEMORY.md"
    board_file.symlink_to(shared_file)
    (board_memory / "memory-index.sqlite").symlink_to(global_memory / "memory-index.sqlite")

    idx = MemoryIndex(board_memory)
    idx.sync_file(shared_file)

    with idx._conn:
        idx._conn.execute(
            "INSERT INTO files(path, hash, mtime) VALUES (?, ?, ?)",
            (str(board_file), "legacy-board-hash", board_file.stat().st_mtime),
        )
        cur = idx._conn.execute(
            """
            INSERT INTO chunks(file_path, content, offset_start, offset_end, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (str(board_file), "Shared banana memory.", 0, 21, 0.0),
        )
        idx._conn.execute(
            "INSERT INTO chunks_fts(rowid, content) VALUES (?, ?)",
            (int(cur.lastrowid), "Shared banana memory."),
        )

    legacy_sources = {
        row[0] for row in idx._conn.execute("SELECT DISTINCT file_path FROM chunks").fetchall()
    }
    assert legacy_sources == {str(shared_file), str(board_file)}

    idx.sync()

    tracked_paths = {
        row[0] for row in idx._conn.execute("SELECT path FROM files ORDER BY path").fetchall()
    }
    assert tracked_paths == {str(shared_file)}

    sources = {
        row[0] for row in idx._conn.execute("SELECT DISTINCT file_path FROM chunks").fetchall()
    }
    assert sources == {str(shared_file)}

    results = idx.search("banana", top_k=10)
    assert len(results) == 1
    assert results[0].source == str(shared_file)


def test_sync_preserves_clean_board_isolation_for_same_content(tmp_path):
    global_memory = tmp_path / "agents" / "nanobot" / "memory"
    global_memory.mkdir(parents=True)
    global_file = global_memory / "MEMORY.md"
    global_file.write_text("Shared banana memory.", encoding="utf-8")

    board_memory = tmp_path / "boards" / "clean-board" / "agents" / "nanobot" / "memory"
    board_memory.mkdir(parents=True)
    board_file = board_memory / "MEMORY.md"
    board_file.write_text("Shared banana memory.", encoding="utf-8")

    global_idx = MemoryIndex(global_memory)
    global_idx.sync()

    board_idx = MemoryIndex(board_memory)
    board_idx.sync()

    global_sources = {
        row[0]
        for row in global_idx._conn.execute("SELECT DISTINCT file_path FROM chunks").fetchall()
    }
    board_sources = {
        row[0]
        for row in board_idx._conn.execute("SELECT DISTINCT file_path FROM chunks").fetchall()
    }

    assert global_sources == {str(global_file)}
    assert board_sources == {str(board_file)}
    assert global_sources != board_sources
