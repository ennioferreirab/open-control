"""Two-layer memory store: MEMORY.md (long-term facts) + HISTORY.md (searchable log)."""

from __future__ import annotations

import re
from pathlib import Path

from filelock import FileLock


def _ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


_SAVE_MEMORY_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save the memory consolidation result to persistent storage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "history_entry": {
                        "type": "string",
                        "description": "A paragraph (2-5 sentences) summarizing key events/decisions/topics. "
                        "Start with [YYYY-MM-DD HH:MM]. Include detail useful for grep search.",
                    },
                    "memory_update": {
                        "type": "string",
                        "description": "Full updated long-term memory as markdown. Include all existing "
                        "facts plus new ones. Return unchanged if nothing new.",
                    },
                },
                "required": ["history_entry", "memory_update"],
            },
        },
    }
]


class MemoryStore:
    """Two-layer memory: MEMORY.md (long-term facts) + HISTORY.md (grep-searchable log)."""

    def __init__(self, workspace: Path):
        self.memory_dir = _ensure_dir(workspace / "memory")
        self.memory_file = self.memory_dir / "MEMORY.md"
        self.history_file = self.memory_dir / "HISTORY.md"
        self._lock = FileLock(self.memory_dir / ".memory.lock", timeout=10)

    def read_long_term(self) -> str:
        with self._lock:
            if self.memory_file.exists():
                return self.memory_file.read_text(encoding="utf-8")
            return ""

    def write_long_term(self, content: str) -> None:
        with self._lock:
            self.memory_file.write_text(content, encoding="utf-8")

    def append_history(self, entry: str) -> None:
        from datetime import datetime as _dt

        if not re.match(r"^\[\d{4}-\d{2}-\d{2}", entry):
            entry = f"[{_dt.now().strftime('%Y-%m-%d %H:%M')}] {entry}"
        with self._lock:
            with open(self.history_file, "a", encoding="utf-8") as f:
                f.write(entry.rstrip() + "\n\n")

    def get_memory_context(self) -> str:
        long_term = self.read_long_term()
        return f"## Long-term Memory\n{long_term}" if long_term else ""
