from mc.memory.store import HybridMemoryStore
from nanobot.agent.memory import MemoryStore


def test_hybrid_store_is_memory_store(tmp_path):
    assert isinstance(HybridMemoryStore(tmp_path), MemoryStore)


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
