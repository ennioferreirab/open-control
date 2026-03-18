"""Overflow protection for Convex string fields.

Convex has a hard 1MB limit per string value. This module provides a
safety cap that truncates oversized content and persists the full
version to the filesystem so no data is lost.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# 900 KB — safely under the 1 MB Convex limit, leaving room for UTF-8
# multi-byte overhead and document metadata.
CONVEX_STRING_SAFE_LIMIT = 900_000


def safe_string_for_convex(
    value: str,
    *,
    field_name: str = "content",
    task_id: str | None = None,
    overflow_dir: Path | None = None,
) -> str:
    """Return *value* capped to the Convex safe limit.

    If the string exceeds ``CONVEX_STRING_SAFE_LIMIT``:
    1. The full content is written to ``overflow_dir`` (when provided).
    2. The string is truncated and a footer is appended pointing to the
       saved file (or just noting the original size when no dir is given).

    Returns the (possibly truncated) string that is safe to store in Convex.
    """
    if len(value.encode("utf-8")) <= CONVEX_STRING_SAFE_LIMIT:
        return value

    original_size = len(value.encode("utf-8"))
    overflow_path: str | None = None

    if overflow_dir is not None:
        try:
            overflow_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
            filename = f"{field_name}_{ts}.txt"
            file_path = overflow_dir / filename
            file_path.write_text(value, encoding="utf-8")
            overflow_path = str(file_path)
            logger.info(
                "[overflow] Saved %d bytes to %s (field=%s, task=%s)",
                original_size,
                overflow_path,
                field_name,
                task_id,
            )
        except Exception:
            logger.warning(
                "[overflow] Failed to save overflow file for field=%s task=%s",
                field_name,
                task_id,
                exc_info=True,
            )

    # Truncate to safe limit (in chars, slightly conservative vs bytes)
    safe_char_limit = CONVEX_STRING_SAFE_LIMIT
    truncated = value[:safe_char_limit]

    if overflow_path:
        truncated += (
            f"\n\n--- [TRUNCATED: {original_size:,} bytes total. "
            f"Full content saved to: {overflow_path}] ---"
        )
    else:
        truncated += f"\n\n--- [TRUNCATED: {original_size:,} bytes total] ---"

    return truncated
