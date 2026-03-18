"""Tests for Convex string overflow protection."""

from __future__ import annotations

from pathlib import Path

from mc.bridge.overflow import CONVEX_STRING_SAFE_LIMIT, safe_string_for_convex


def test_short_string_passes_through() -> None:
    result = safe_string_for_convex("hello world", field_name="test")
    assert result == "hello world"


def test_long_string_is_truncated() -> None:
    huge = "x" * (CONVEX_STRING_SAFE_LIMIT + 10000)
    result = safe_string_for_convex(huge, field_name="test")
    assert len(result.encode("utf-8")) < CONVEX_STRING_SAFE_LIMIT + 200  # footer overhead
    assert "[TRUNCATED:" in result


def test_overflow_file_is_created(tmp_path: Path) -> None:
    huge = "x" * (CONVEX_STRING_SAFE_LIMIT + 10000)
    overflow_dir = tmp_path / "overflow"

    result = safe_string_for_convex(
        huge,
        field_name="raw_text",
        task_id="task-123",
        overflow_dir=overflow_dir,
    )

    assert "[TRUNCATED:" in result
    assert "Full content saved to:" in result

    # Verify file was created with full content
    files = list(overflow_dir.glob("raw_text_*.txt"))
    assert len(files) == 1
    saved = files[0].read_text(encoding="utf-8")
    assert len(saved) == len(huge)


def test_no_overflow_dir_still_truncates() -> None:
    huge = "x" * (CONVEX_STRING_SAFE_LIMIT + 10000)
    result = safe_string_for_convex(huge, field_name="test", overflow_dir=None)
    assert "[TRUNCATED:" in result
    assert "Full content saved to:" not in result
