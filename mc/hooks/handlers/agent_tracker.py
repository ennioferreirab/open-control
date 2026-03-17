"""Agent tracker — tracks subagent lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

from ..handler import BaseHandler


class AgentTrackerHandler(BaseHandler):
    events: ClassVar[list[tuple[str, str | None]]] = [
        ("SubagentStart", None),
        ("SubagentStop", None),
    ]

    def handle(self) -> str | None:
        event = self.payload.get("hook_event_name", "")

        if event == "SubagentStart":
            return self._handle_start()
        elif event == "SubagentStop":
            return self._handle_stop()
        return None

    def _handle_start(self) -> str | None:
        agent_id = self.payload.get("agent_id", "")
        agent_type = self.payload.get("agent_type", "unknown")
        if not agent_id:
            return None

        self.ctx.active_agents[agent_id] = {
            "type": agent_type,
            "started_at": datetime.now(UTC).isoformat(),
        }
        count = len(self.ctx.active_agents)
        return f"Agent '{agent_type}' started ({count} active)"

    def _handle_stop(self) -> str | None:
        agent_id = self.payload.get("agent_id", "")
        agent_type = self.payload.get("agent_type", "unknown")

        self.ctx.active_agents.pop(agent_id, None)
        count = len(self.ctx.active_agents)
        return f"Agent '{agent_type}' stopped ({count} remaining)"
