"""In-memory metrics for interactive execution rollout."""

from __future__ import annotations

from collections import Counter
from threading import Lock

_COUNTS: Counter[str] = Counter()
_LOCK = Lock()


def increment_interactive_metric(name: str, amount: int = 1) -> None:
    """Increment a named interactive rollout metric."""

    with _LOCK:
        _COUNTS[name] += amount


def snapshot_interactive_metrics() -> dict[str, int]:
    """Return a copy of the current interactive metric counters."""

    with _LOCK:
        return dict(_COUNTS)


def reset_interactive_metrics() -> None:
    """Clear interactive metric counters. Intended for tests."""

    with _LOCK:
        _COUNTS.clear()
