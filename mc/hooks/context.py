"""Shared session context for hook invocations."""
from __future__ import annotations

import fcntl
import json
import re
import time
from pathlib import Path

from .config import get_config, get_project_root

_PRUNE_AGE_SECONDS = 86400  # 24 hours
_SAFE_ID_RE = re.compile(r"[^a-zA-Z0-9_-]")


def _safe_session_id(session_id: str) -> str:
    """Sanitize session_id to prevent path traversal."""
    safe = _SAFE_ID_RE.sub("_", session_id)
    return safe if safe else "unknown"


class HookContext:
    """Shared state across hook invocations for a session."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.active_skill: str | None = None
        self.active_plan: str | None = None
        self.active_agents: dict[str, dict] = {}

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "active_skill": self.active_skill,
            "active_plan": self.active_plan,
            "active_agents": self.active_agents,
        }

    @classmethod
    def from_dict(cls, data: dict) -> HookContext:
        ctx = cls(data["session_id"])
        ctx.active_skill = data.get("active_skill")
        ctx.active_plan = data.get("active_plan")
        ctx.active_agents = data.get("active_agents", {})
        return ctx

    @classmethod
    def load(cls, session_id: str) -> HookContext:
        """Load from state dir or create new. Auto-prunes old state files."""
        config = get_config()
        state_dir = get_project_root() / config.state_dir
        state_dir.mkdir(parents=True, exist_ok=True)

        # Auto-prune old state files
        now = time.time()
        for f in state_dir.glob("*.json"):
            try:
                if now - f.stat().st_mtime > _PRUNE_AGE_SECONDS:
                    f.unlink()
            except OSError:
                pass

        state_file = state_dir / f"{_safe_session_id(session_id)}.json"
        if state_file.exists():
            try:
                with open(state_file) as fh:
                    fcntl.flock(fh, fcntl.LOCK_SH)
                    data = json.load(fh)
                return cls.from_dict(data)
            except (json.JSONDecodeError, KeyError, OSError):
                pass
        return cls(session_id)

    def save(self) -> None:
        """Persist to disk with file locking."""
        config = get_config()
        state_dir = get_project_root() / config.state_dir
        state_dir.mkdir(parents=True, exist_ok=True)

        state_file = state_dir / f"{_safe_session_id(self.session_id)}.json"
        # Open without truncating, lock, then truncate+write to avoid TOCTOU race
        mode = "r+b" if state_file.exists() else "wb"
        with open(state_file, mode) as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            fh.seek(0)
            fh.truncate()
            fh.write(json.dumps(self.to_dict(), indent=2).encode())
