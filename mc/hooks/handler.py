"""Base handler class for hook factory."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .context import HookContext


class BaseHandler:
    """Base class for hook handlers.

    Subclasses declare which events they handle via the `events` class attribute.
    Each entry is a tuple of (event_name, matcher_value_or_None).
    """

    events: list[tuple[str, str | None]] = []

    def __init__(self, ctx: HookContext, payload: dict) -> None:
        self.ctx = ctx
        self.payload = payload

    @classmethod
    def matches(cls, event_name: str, matcher_value: str) -> bool:
        for ev, m in cls.events:
            if ev == event_name and (m is None or m == matcher_value):
                return True
        return False

    def handle(self) -> str | None:
        """Execute handler logic. Return additionalContext string or None."""
        raise NotImplementedError
