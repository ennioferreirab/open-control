"""
Configuration, environment resolution, and path utilities.

Extracted from mc.gateway so that internal modules can import config/path
helpers without depending on the gateway composition root.

Contains:
- AGENTS_DIR constant
- Convex URL / admin key resolution
- Config default model lookup
- Agent data field filtering
- Timestamp parsing
- File read helpers
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

logger = logging.getLogger(__name__)

AGENTS_DIR = Path.home() / ".nanobot" / "agents"


def _config_default_model() -> str:
    """Return the user's configured default model (with provider prefix).

    Reads ``agents.defaults.model`` from ``~/.nanobot/config.json``.
    This is the single source of truth for the active model/provider.
    """
    from nanobot.config.loader import load_config

    return load_config().agents.defaults.model


def _resolve_convex_url(dashboard_dir: Path | None = None) -> str | None:
    """Resolve the Convex deployment URL.

    Checks CONVEX_URL env var first, then falls back to parsing
    NEXT_PUBLIC_CONVEX_URL from dashboard/.env.local.

    Args:
        dashboard_dir: Path to the dashboard directory. Auto-detected if None.

    Returns:
        The Convex URL string, or None if not found.
    """
    url = os.environ.get("CONVEX_URL")
    if url:
        return url

    if dashboard_dir is None:
        candidates = [
            Path.cwd() / "dashboard",
            Path(__file__).resolve().parents[3] / "dashboard",
        ]
        for candidate in candidates:
            if candidate.is_dir() and (candidate / ".env.local").exists():
                dashboard_dir = candidate
                break

    if dashboard_dir is not None:
        env_local = dashboard_dir / ".env.local"
        if env_local.exists():
            for line in env_local.read_text().splitlines():
                if line.startswith("NEXT_PUBLIC_CONVEX_URL="):
                    return line.split("=", 1)[1].strip().strip('"')

    return None


def _resolve_admin_key(dashboard_dir: Path | None = None) -> str | None:
    """Resolve the Convex admin key from dashboard/.env.local.

    Only used as fallback when CONVEX_ADMIN_KEY env var is not set.
    For local Convex deployments, falls back to dashboard/.convex/local/default/config.json.
    """
    if dashboard_dir is None:
        candidates = [
            Path.cwd() / "dashboard",
            Path(__file__).resolve().parents[3] / "dashboard",
        ]
        for candidate in candidates:
            if candidate.is_dir() and (candidate / ".env.local").exists():
                dashboard_dir = candidate
                break

    if dashboard_dir is not None:
        env_local = dashboard_dir / ".env.local"
        if env_local.exists():
            for line in env_local.read_text().splitlines():
                if line.startswith("CONVEX_ADMIN_KEY="):
                    return line.split("=", 1)[1].strip().strip('"')

        local_config = dashboard_dir / ".convex" / "local" / "default" / "config.json"
        if local_config.exists():
            try:
                payload = json.loads(local_config.read_text())
            except (json.JSONDecodeError, OSError):
                logger.warning("Could not parse local Convex config %s", local_config)
            else:
                admin_key = payload.get("adminKey")
                if isinstance(admin_key, str) and admin_key:
                    return admin_key

    return None


def filter_agent_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Filter a dict to only known AgentData fields.

    Convex returns extra system fields (e.g. creation_time from _creationTime)
    that are not part of the AgentData dataclass. This function strips them.
    """
    from mc.types import AgentData

    valid_fields = {f.name for f in dataclasses.fields(AgentData)}
    return {k: v for k, v in data.items() if k in valid_fields}


def _parse_utc_timestamp(value: str) -> datetime | None:
    """Parse an ISO 8601 timestamp string into a UTC-aware datetime.

    Handles the common variants produced by different systems:
    - ``Z`` suffix  (``2026-01-01T00:00:00Z``)
    - ``+00:00`` suffix (``2026-01-01T00:00:00+00:00``)
    - Naive (no timezone info) -- assumed UTC

    Returns None if parsing fails so the caller can skip gracefully.
    """
    from datetime import datetime

    if not isinstance(value, str) or not value:
        return None
    try:
        # Normalise "Z" to "+00:00" for fromisoformat (Python < 3.11 compat)
        normalised = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalised)
        # If parsed as naive (no tz), treat as UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, AttributeError):
        return None


def _read_file_or_none(path: Path) -> str | None:
    """Return file content as a string, or None if the file does not exist."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError:
        logger.warning("Could not read file %s", path)
        return None


def _read_session_data(sessions_dir: Path) -> str | None:
    """Read all .jsonl files in sessions_dir and concatenate their content.

    Multiple session files are concatenated into a single JSONL blob (one JSON
    object per line). On restore, this blob is written to a single predictable
    file ``mc_task_{name}.jsonl``.  This is a best-effort approach: the agent
    runtime reads JSONL line-by-line, so all session entries are preserved;
    however distinct filenames are not.

    Returns None if the directory does not exist or contains no JSONL files.
    """
    if not sessions_dir.is_dir():
        return None
    parts: list[str] = []
    try:
        for entry in sorted(sessions_dir.iterdir()):
            if entry.is_file() and entry.suffix == ".jsonl":
                content = _read_file_or_none(entry)
                if content:
                    parts.append(content)
    except OSError:
        logger.warning("Could not read sessions directory %s", sessions_dir)
        return None
    return "\n".join(parts) if parts else None
