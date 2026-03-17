"""Plan capture — captures plan approval via ExitPlanMode."""

from __future__ import annotations

from typing import ClassVar

from ..config import get_config, get_project_root
from ..handler import BaseHandler


class PlanCaptureHandler(BaseHandler):
    events: ClassVar[list[tuple[str, str | None]]] = [("PostToolUse", "ExitPlanMode")]

    def handle(self) -> str | None:
        if self.ctx.active_plan:
            return f"Plan approved: {self.ctx.active_plan}"

        # Fallback: find most recently modified tracker
        config = get_config()
        tracker_dir = get_project_root() / config.tracker_dir
        if not tracker_dir.is_dir():
            return None

        trackers = sorted(tracker_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if trackers:
            self.ctx.active_plan = trackers[0].stem
            return f"Plan approved: {self.ctx.active_plan}"

        return None
