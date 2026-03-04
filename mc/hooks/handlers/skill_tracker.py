"""Skill tracker — captures which skill was invoked."""
from __future__ import annotations

from ..handler import BaseHandler


class SkillTrackerHandler(BaseHandler):
    events = [("PostToolUse", "Skill")]

    def handle(self) -> str | None:
        tool_input = self.payload.get("tool_input", {})
        skill_name = tool_input.get("skill", "")
        if not skill_name:
            return None

        self.ctx.active_skill = skill_name
        return f"Active skill: {skill_name}"
