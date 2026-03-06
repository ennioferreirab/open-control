import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from mc.memory import create_memory_store
from mc.memory.store import HybridMemoryStore
from nanobot.agent.memory import MemoryStore


def test_hybrid_store_is_memory_store(tmp_path):
    assert isinstance(HybridMemoryStore(tmp_path), MemoryStore)


def test_create_memory_store_quarantines_invalid_files(tmp_path):
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    rogue = memory_dir / "rogue.md"
    rogue.write_text("artifact", encoding="utf-8")

    store = create_memory_store(tmp_path)

    assert isinstance(store, HybridMemoryStore)
    assert not rogue.exists()
    quarantined = tmp_path / ".memory-quarantine" / "rogue.md"
    assert quarantined.read_text(encoding="utf-8") == "artifact"


def test_create_memory_store_keeps_archive_and_legacy_files(tmp_path):
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    archive = memory_dir / "HISTORY_ARCHIVE.md"
    legacy = memory_dir / "HISTORY_2026-03-05_2214.md"
    archive.write_text("archive", encoding="utf-8")
    legacy.write_text("legacy", encoding="utf-8")

    create_memory_store(tmp_path)

    assert archive.exists()
    assert legacy.exists()
    assert not (tmp_path / ".memory-quarantine" / "HISTORY_ARCHIVE.md").exists()


def test_write_triggers_sync(tmp_path):
    store = HybridMemoryStore(tmp_path)

    store.write_long_term("test content")

    assert store.search("test")


def test_append_history_triggers_sync(tmp_path):
    store = HybridMemoryStore(tmp_path)

    store.append_history("[2026-01-01] Built feature")

    assert store.search("feature")


def test_search_returns_empty_for_no_match(tmp_path):
    store = HybridMemoryStore(tmp_path)

    assert store.search("xyznonexistent") == ""


def test_get_memory_context_unchanged(tmp_path):
    store = HybridMemoryStore(tmp_path)

    store.write_long_term("facts")

    assert "facts" in store.get_memory_context()


# ── Recent history in context ───────────────────────────────────────────────


def test_get_memory_context_includes_recent_history(tmp_path):
    store = HybridMemoryStore(tmp_path)
    store._history_context_days = 5

    today = datetime.now().strftime("%Y-%m-%d")
    store.write_long_term("I like Python")
    store.append_history(f"[{today}] Discussed memory architecture")

    ctx = store.get_memory_context()
    assert "Long-term Memory" in ctx
    assert "I like Python" in ctx
    assert "Recent History" in ctx
    assert "Discussed memory architecture" in ctx


def test_get_memory_context_excludes_old_history(tmp_path):
    store = HybridMemoryStore(tmp_path)
    store._history_context_days = 3

    old = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    recent = datetime.now().strftime("%Y-%m-%d")
    store.append_history(f"[{old}] Ancient event")
    store.append_history(f"[{recent}] Fresh event")

    ctx = store.get_memory_context()
    assert "Ancient event" not in ctx
    assert "Fresh event" in ctx


def test_get_memory_context_respects_max_chars(tmp_path):
    store = HybridMemoryStore(tmp_path)
    store._memory_context_max_chars = 100

    store.write_long_term("x" * 200)

    ctx = store.get_memory_context()
    assert len(ctx) <= 120  # 100 + truncation marker
    assert "truncated" in ctx


def test_get_memory_context_zero_days_skips_history(tmp_path):
    store = HybridMemoryStore(tmp_path)
    store._history_context_days = 0

    today = datetime.now().strftime("%Y-%m-%d")
    store.append_history(f"[{today}] Should not appear")
    store.write_long_term("only memory")

    ctx = store.get_memory_context()
    assert "Recent History" not in ctx
    assert "only memory" in ctx


def test_get_memory_context_date_range_entries(tmp_path):
    """Entries with date ranges like [2026-02-26 to 2026-03-04] use end date."""
    store = HybridMemoryStore(tmp_path)
    store._history_context_days = 3

    today = datetime.now()
    old_start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    recent_end = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    store.append_history(f"[{old_start} to {recent_end}] Spanning event")

    ctx = store.get_memory_context()
    assert "Spanning event" in ctx


def test_get_memory_context_empty_history(tmp_path):
    store = HybridMemoryStore(tmp_path)
    store._history_context_days = 5

    store.write_long_term("just memory")

    ctx = store.get_memory_context()
    assert "Long-term Memory" in ctx
    assert "Recent History" not in ctx


def test_undated_entries_skipped_in_recent_history(tmp_path):
    """Legacy undated entries in HISTORY.md are skipped entirely."""
    store = HybridMemoryStore(tmp_path)
    store._history_context_days = 3

    recent = datetime.now().strftime("%Y-%m-%d")

    # Simulate legacy file with an undated entry
    history = (
        f"Undated legacy entry\n\n"
        f"[{recent}] Recent dated entry\n"
    )
    (tmp_path / "memory" / "HISTORY.md").write_text(history, encoding="utf-8")

    ctx = store.get_memory_context()
    assert "Undated legacy" not in ctx
    assert "Recent dated entry" in ctx


def test_append_history_adds_date_prefix(tmp_path):
    """MemoryStore.append_history() prepends date if entry lacks one."""
    from nanobot.agent.memory import MemoryStore

    store = MemoryStore(tmp_path / "ws")
    (tmp_path / "ws" / "memory").mkdir(parents=True, exist_ok=True)
    store.append_history("Entry without date")

    content = store.history_file.read_text(encoding="utf-8")
    assert content.startswith("[")
    assert "Entry without date" in content


def test_append_history_preserves_existing_date(tmp_path):
    """MemoryStore.append_history() does not double-prefix dated entries."""
    from nanobot.agent.memory import MemoryStore

    store = MemoryStore(tmp_path / "ws")
    (tmp_path / "ws" / "memory").mkdir(parents=True, exist_ok=True)
    store.append_history("[2026-03-05 10:00] Already dated")

    content = store.history_file.read_text(encoding="utf-8")
    assert content.startswith("[2026-03-05 10:00]")
    assert content.count("[2026-03-05") == 1


@pytest.mark.asyncio
async def test_consolidation_worker_loops_until_history_below_threshold(
    tmp_path,
):
    with patch.object(HybridMemoryStore, "_resolve_consolidation_model", return_value="test-model"), \
         patch("mc.memory.consolidation.is_history_above_threshold") as threshold_mock, \
         patch("mc.memory.consolidation.consolidate_history_and_memory", new_callable=AsyncMock) as consolidate_mock:
        store = HybridMemoryStore(tmp_path)
        threshold_mock.side_effect = [True, True, True, False]
        consolidate_mock.return_value = True

        store._maybe_trigger_consolidation()

        for _ in range(100):
            if not store._consolidation_in_progress:
                break
            await asyncio.sleep(0)

    assert store._consolidation_in_progress is False
    assert consolidate_mock.await_count == 2
