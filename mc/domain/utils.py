"""Shared utility functions for the mc package."""


def as_positive_int(value: object, *, default: int) -> int:
    """Convert a value to a positive integer, falling back to *default*."""
    try:
        n = int(value)  # type: ignore[arg-type]
        return n if n > 0 else default
    except (TypeError, ValueError):
        return default
