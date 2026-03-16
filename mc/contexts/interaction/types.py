from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class BridgeLike(Protocol):
    def query(self, function_name: str, args: dict[str, Any] | None = None) -> Any: ...

    def mutation(self, function_name: str, args: dict[str, Any] | None = None) -> Any: ...


@dataclass(slots=True)
class InteractionContext:
    session_id: str
    task_id: str
    step_id: str | None
    agent_name: str
    provider: str
