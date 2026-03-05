"""Hybrid BM25+vector memory index built on SQLite."""

from __future__ import annotations

import hashlib
import os
import math
import re
import sqlite3
import time
import typing
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SearchResult:
    content: str
    score: float
    source: str
    created_at: float


class MemoryIndex:
    def __init__(self, memory_dir: Path, embedding_model: str | None = None):
        self.memory_dir = memory_dir
        self._db_path = memory_dir / "memory-index.sqlite"

        from mc.memory.providers import get_provider

        model = embedding_model or os.environ.get("NANOBOT_MEMORY_EMBEDDING_MODEL")
        self._provider: typing.Any = get_provider(model)
        self._provider_is_null = self._provider.__class__.__name__ == "NullProvider"

        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_schema(self._conn)

        self._vec_available = False
        try:
            import sqlite_vec  # type: ignore

            self._conn.enable_load_extension(True)
            try:
                sqlite_vec.load(self._conn)
            finally:
                self._conn.enable_load_extension(False)
            self._vec_available = True
        except Exception:
            self._vec_available = False

        self._vec_dim: int | None = None
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = 'vec_dim'"
        ).fetchone()
        if row is not None:
            try:
                self._vec_dim = int(row[0])
            except (TypeError, ValueError):
                self._vec_dim = None

    @staticmethod
    def _create_schema(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                path TEXT PRIMARY KEY,
                hash TEXT,
                mtime REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY,
                file_path TEXT,
                content TEXT,
                offset_start INT,
                offset_end INT,
                created_at REAL,
                FOREIGN KEY (file_path) REFERENCES files(path)
            )
            """
        )
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
            USING fts5(content, content='chunks', content_rowid='id')
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        conn.commit()

    def _ensure_vec_table(self, conn: sqlite3.Connection, dim: int) -> None:
        if not self._vec_available:
            return

        if self._vec_dim is not None and self._vec_dim != dim:
            raise ValueError(
                f"Embedding dim mismatch: existing={self._vec_dim}, incoming={dim}"
            )

        conn.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec
            USING vec0(embedding float[{dim}])
            """
        )
        conn.execute(
            """
            INSERT INTO meta(key, value) VALUES('vec_dim', ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (str(dim),),
        )
        self._vec_dim = dim

    def sync(self) -> None:
        for path in sorted(self.memory_dir.glob("*.md")):
            self.sync_file(path)

    def sync_file(self, path: Path) -> None:
        if not path.exists() or path.suffix.lower() != ".md":
            return

        raw = path.read_bytes()
        digest = hashlib.md5(raw).hexdigest()
        path_str = str(path)

        row = self._conn.execute(
            "SELECT hash FROM files WHERE path = ?",
            (path_str,),
        ).fetchone()
        if row and row[0] == digest:
            return

        text = raw.decode("utf-8", errors="replace")
        chunks = self._chunk_text(text, max_chars=500, overlap=50)
        now = time.time()

        chunk_ids: list[int] = []
        chunk_texts: list[str] = []

        with self._conn:
            old_ids = [
                r[0]
                for r in self._conn.execute(
                    "SELECT id FROM chunks WHERE file_path = ?", (path_str,)
                ).fetchall()
            ]
            self._conn.execute("DELETE FROM chunks WHERE file_path = ?", (path_str,))
            if old_ids:
                self._conn.executemany(
                    "DELETE FROM chunks_fts WHERE rowid = ?",
                    [(chunk_id,) for chunk_id in old_ids],
                )
                if self._vec_available:
                    vec_table = self._conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_vec'"
                    ).fetchone()
                    if vec_table:
                        self._conn.executemany(
                            "DELETE FROM chunks_vec WHERE rowid = ?",
                            [(chunk_id,) for chunk_id in old_ids],
                        )

            for content, start, end in chunks:
                cur = self._conn.execute(
                    """
                    INSERT INTO chunks(file_path, content, offset_start, offset_end, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (path_str, content, start, end, now),
                )
                chunk_id = int(cur.lastrowid)
                self._conn.execute(
                    "INSERT INTO chunks_fts(rowid, content) VALUES (?, ?)",
                    (chunk_id, content),
                )
                chunk_ids.append(chunk_id)
                chunk_texts.append(content)

            if (
                chunk_ids
                and self._vec_available
                and not self._provider_is_null
            ):
                embeddings = self._provider.embed(chunk_texts)
                if embeddings:
                    first_dim = len(embeddings[0])
                    self._ensure_vec_table(self._conn, first_dim)
                    rows = [
                        (chunk_id, self._vector_literal(embedding))
                        for chunk_id, embedding in zip(chunk_ids, embeddings)
                        if len(embedding) == first_dim
                    ]
                    if rows:
                        self._conn.executemany(
                            "INSERT INTO chunks_vec(rowid, embedding) VALUES (?, ?)",
                            rows,
                        )

            self._conn.execute(
                """
                INSERT INTO files(path, hash, mtime) VALUES (?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET hash=excluded.hash, mtime=excluded.mtime
                """,
                (path_str, digest, path.stat().st_mtime),
            )

    @staticmethod
    def _chunk_text(
        text: str, max_chars: int = 500, overlap: int = 50
    ) -> list[tuple[str, int, int]]:
        if not text.strip():
            return []

        chunks: list[tuple[str, int, int]] = []
        para_pattern = re.compile(r"\S[\s\S]*?(?=\n\s*\n|$)")
        sent_pattern = re.compile(r"[^.!?\n]+(?:[.!?]+|$)")

        for para_match in para_pattern.finditer(text):
            p_start, p_end = para_match.span()
            para = para_match.group(0).strip()
            if not para:
                continue

            para_raw = text[p_start:p_end]
            content_start = p_start + para_raw.find(para)
            content_end = content_start + len(para)

            if len(para) <= max_chars:
                chunks.append((para, content_start, content_end))
                continue

            sentences = [
                (m.group(0).strip(), content_start + m.start(), content_start + m.end())
                for m in sent_pattern.finditer(para)
                if m.group(0).strip()
            ]

            if not sentences:
                for i in range(0, len(para), max(1, max_chars - overlap)):
                    piece = para[i : i + max_chars].strip()
                    if piece:
                        s = content_start + i
                        e = min(content_end, s + len(piece))
                        chunks.append((piece, s, e))
                continue

            cur_text = ""
            cur_start: int | None = None
            cur_end: int | None = None

            def flush() -> None:
                nonlocal cur_text, cur_start, cur_end
                if cur_text and cur_start is not None and cur_end is not None:
                    chunks.append((cur_text.strip(), cur_start, cur_end))
                cur_text = ""
                cur_start = None
                cur_end = None

            for sent, s_start, s_end in sentences:
                if len(sent) > max_chars:
                    flush()
                    for i in range(0, len(sent), max(1, max_chars - overlap)):
                        piece = sent[i : i + max_chars].strip()
                        if piece:
                            p_start = s_start + i
                            p_end = min(s_end, p_start + len(piece))
                            chunks.append((piece, p_start, p_end))
                    continue

                candidate = sent if not cur_text else f"{cur_text} {sent}"
                if len(candidate) <= max_chars:
                    if cur_start is None:
                        cur_start = s_start
                    cur_text = candidate
                    cur_end = s_end
                else:
                    flush()
                    cur_text = sent
                    cur_start = s_start
                    cur_end = s_end

            flush()

        if overlap <= 0 or not chunks:
            return chunks

        overlapped: list[tuple[str, int, int]] = []
        for idx, (_, start, end) in enumerate(chunks):
            if idx == 0:
                expanded_start = start
            else:
                expanded_start = max(0, start - overlap)
            content = text[expanded_start:end].strip()
            if content:
                real_start = expanded_start + (text[expanded_start:end].find(content))
                real_end = real_start + len(content)
                overlapped.append((content, real_start, real_end))
        return overlapped

    def search(
        self,
        query: str,
        top_k: int = 5,
        *,
        vector_weight: float = 0.5,
        decay_lambda: float = 0.01,
        mmr_diversity: float = 0.7,
    ) -> list[SearchResult]:
        if not query.strip() or top_k <= 0:
            return []

        normalized_query = self._normalize_fts_query(query)
        if not normalized_query:
            return []

        limit = max(top_k * 5, top_k)
        bm25_results = self._bm25(normalized_query, limit=limit)

        vec_results: list[SearchResult] = []
        if self._vec_available and not self._provider_is_null:
            query_emb = self._provider.embed([query])
            if query_emb and query_emb[0]:
                vec_results = self._vector_search(query_emb[0], limit=limit)

        if bm25_results and vec_results:
            merged = self._merge_hybrid(
                bm25_results, vec_results, vector_weight=vector_weight
            )
        else:
            merged = bm25_results or vec_results

        decayed = self._temporal_decay(merged, decay_lambda)
        reranked = self._mmr_rerank(decayed, top_k=top_k, diversity=mmr_diversity)
        return reranked[:top_k]

    @staticmethod
    def _normalize_fts_query(query: str) -> str:
        """Normalize free-form text into a safe SQLite FTS query.

        Raw task prompts can include URLs and punctuation that break FTS5 MATCH
        parsing. We reduce them to alphanumeric tokens and join with spaces.
        """
        tokens = re.findall(r"\w+", query.lower())
        # De-duplicate while preserving order and drop trivial 1-char tokens.
        seen: set[str] = set()
        filtered: list[str] = []
        for token in tokens:
            if len(token) <= 1 or token in seen:
                continue
            seen.add(token)
            filtered.append(token)
        return " ".join(filtered)

    def _bm25(self, query: str, limit: int) -> list[SearchResult]:
        rows = self._conn.execute(
            """
            SELECT c.content, c.file_path AS source, c.created_at, chunks_fts.rank
            FROM chunks_fts
            JOIN chunks c ON chunks_fts.rowid = c.id
            WHERE chunks_fts MATCH ?
            ORDER BY chunks_fts.rank
            LIMIT ?
            """,
            (query, limit),
        ).fetchall()
        return [
            SearchResult(
                content=str(content),
                score=-float(rank),
                source=str(source),
                created_at=float(created_at),
            )
            for content, source, created_at, rank in rows
        ]

    def _vector_search(self, query_emb: list[float], limit: int) -> list[SearchResult]:
        vec_table = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_vec'"
        ).fetchone()
        if not vec_table:
            return []

        rows = self._conn.execute(
            """
            SELECT chunks_vec.rowid, distance
            FROM chunks_vec
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT ?
            """,
            (self._vector_literal(query_emb), limit),
        ).fetchall()
        if not rows:
            return []

        results: list[SearchResult] = []
        for rowid, distance in rows:
            chunk_row = self._conn.execute(
                """
                SELECT content, file_path, created_at
                FROM chunks
                WHERE id = ?
                """,
                (int(rowid),),
            ).fetchone()
            if not chunk_row:
                continue
            content, source, created_at = chunk_row
            score = 1.0 / (1.0 + float(distance))
            results.append(
                SearchResult(
                    content=str(content),
                    score=score,
                    source=str(source),
                    created_at=float(created_at),
                )
            )
        return results

    @staticmethod
    def _temporal_decay(
        results: list[SearchResult], decay_lambda: float
    ) -> list[SearchResult]:
        now = time.time()
        decayed: list[SearchResult] = []
        for result in results:
            age_days = max(0.0, (now - result.created_at) / 86400.0)
            score = result.score * math.exp(-decay_lambda * age_days)
            decayed.append(
                SearchResult(
                    content=result.content,
                    score=score,
                    source=result.source,
                    created_at=result.created_at,
                )
            )
        return decayed

    @staticmethod
    def _mmr_rerank(
        results: list[SearchResult], top_k: int, diversity: float
    ) -> list[SearchResult]:
        if not results:
            return []
        if len(results) <= 1:
            return results[:top_k]

        remaining = list(results)
        selected: list[SearchResult] = []
        token_cache: dict[int, set[str]] = {}

        def tokens(text: str) -> set[str]:
            key = hash(text)
            if key not in token_cache:
                token_cache[key] = set(re.findall(r"\w+", text.lower()))
            return token_cache[key]

        while remaining and len(selected) < top_k:
            if not selected:
                best = max(remaining, key=lambda r: r.score)
                selected.append(best)
                remaining.remove(best)
                continue

            def mmr_score(candidate: SearchResult) -> float:
                c_tokens = tokens(candidate.content)
                max_sim = 0.0
                for chosen in selected:
                    s_tokens = tokens(chosen.content)
                    union = c_tokens | s_tokens
                    if not union:
                        sim = 0.0
                    else:
                        sim = len(c_tokens & s_tokens) / len(union)
                    max_sim = max(max_sim, sim)
                return diversity * candidate.score - (1.0 - diversity) * max_sim

            best = max(remaining, key=mmr_score)
            selected.append(best)
            remaining.remove(best)

        return selected

    @staticmethod
    def _normalize(scores: list[float]) -> list[float]:
        if not scores:
            return []
        lo = min(scores)
        hi = max(scores)
        if hi == lo:
            return [0.5 for _ in scores]
        return [(score - lo) / (hi - lo) for score in scores]

    def _merge_hybrid(
        self,
        bm25_results: list[SearchResult],
        vec_results: list[SearchResult],
        *,
        vector_weight: float,
    ) -> list[SearchResult]:
        bm25_map = {
            (r.content, r.source, r.created_at): r.score for r in bm25_results
        }
        vec_map = {(r.content, r.source, r.created_at): r.score for r in vec_results}
        all_keys = list(set(bm25_map) | set(vec_map))

        bm25_vals = self._normalize([bm25_map.get(k, 0.0) for k in all_keys])
        vec_vals = self._normalize([vec_map.get(k, 0.0) for k in all_keys])

        weight = min(1.0, max(0.0, vector_weight))
        merged: list[SearchResult] = []
        for idx, key in enumerate(all_keys):
            content, source, created_at = key
            score = (1.0 - weight) * bm25_vals[idx] + weight * vec_vals[idx]
            merged.append(
                SearchResult(
                    content=content,
                    score=score,
                    source=source,
                    created_at=created_at,
                )
            )
        merged.sort(key=lambda r: r.score, reverse=True)
        return merged

    def rebuild(self) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM files")
            self._conn.execute("DELETE FROM chunks")
            self._conn.execute("DELETE FROM chunks_fts")
            vec_table = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_vec'"
            ).fetchone()
            if vec_table:
                self._conn.execute("DELETE FROM chunks_vec")
        self.sync()

    @staticmethod
    def _vector_literal(values: list[float]) -> str:
        return "[" + ",".join(f"{float(v):.10g}" for v in values) + "]"
