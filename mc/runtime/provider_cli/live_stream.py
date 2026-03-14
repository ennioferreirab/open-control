"""LiveStreamProjector - projects ParsedCliEvent objects into an ordered stream."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from mc.contexts.provider_cli.types import ParsedCliEvent


@dataclass
class ProjectedEvent:
    """A ParsedCliEvent decorated with stream metadata."""

    sequence: int
    timestamp: str
    event: ParsedCliEvent
    session_id: str


class LiveStreamProjector:
    """Projects ParsedCliEvent objects into an ordered, timestamped stream.

    Subscribers receive every projected event via registered callbacks or can
    pull from async queues.  The projector guarantees monotonically increasing
    sequence numbers across the lifetime of a session.
    """

    def __init__(self) -> None:
        self._sequence: int = 0
        self._events: list[ProjectedEvent] = []
        self._callbacks: list[Callable[[ProjectedEvent], None]] = []
        self._queues: list[asyncio.Queue[ProjectedEvent]] = []

    def project(self, event: ParsedCliEvent, *, session_id: str) -> ProjectedEvent:
        """Assign a sequence number and timestamp to *event* and notify subscribers.

        Args:
            event: The normalized CLI event to project.
            session_id: The mc_session_id this event belongs to.

        Returns:
            The projected event with sequence and timestamp attached.
        """
        self._sequence += 1
        projected = ProjectedEvent(
            sequence=self._sequence,
            timestamp=datetime.now(timezone.utc).isoformat(),
            event=event,
            session_id=session_id,
        )
        self._events.append(projected)
        self._notify(projected)
        return projected

    def subscribe(self, callback: Callable[[ProjectedEvent], None]) -> None:
        """Register a synchronous callback that is called for every new event."""
        self._callbacks.append(callback)

    def subscribe_queue(self) -> asyncio.Queue[ProjectedEvent]:
        """Create and return an asyncio Queue that receives every new event."""
        q: asyncio.Queue[ProjectedEvent] = asyncio.Queue()
        self._queues.append(q)
        return q

    def unsubscribe(self, callback: Callable[[ProjectedEvent], None]) -> None:
        """Remove a previously registered callback."""
        try:
            self._callbacks.remove(callback)
        except ValueError:
            pass

    def events_for_session(self, session_id: str) -> list[ProjectedEvent]:
        """Return all projected events for *session_id* in sequence order."""
        return [e for e in self._events if e.session_id == session_id]

    def all_events(self) -> list[ProjectedEvent]:
        """Return all projected events in sequence order."""
        return list(self._events)

    @property
    def sequence(self) -> int:
        """Current sequence counter (total events projected so far)."""
        return self._sequence

    def _notify(self, projected: ProjectedEvent) -> None:
        for cb in list(self._callbacks):
            cb(projected)
        for q in list(self._queues):
            try:
                q.put_nowait(projected)
            except asyncio.QueueFull:
                pass  # drop if queue is bounded and full
