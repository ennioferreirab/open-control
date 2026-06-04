"""
Configuration, environment resolution, and path utilities.

Extracted from mc.gateway so that internal modules can import config/path
helpers without depending on the gateway composition root.

Contains:
- mc-owned Config schema (Pydantic BaseModel, subset of nanobot schema)
- load_config() — raises ValueError on malformed JSON (no silent fallback)
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

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from mc.infrastructure.runtime_home import get_agents_dir

logger = logging.getLogger(__name__)

AGENTS_DIR = get_agents_dir()


# ---------------------------------------------------------------------------
# Shared base model — accepts both camelCase and snake_case keys, ignores extras
# ---------------------------------------------------------------------------


class _Base(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )


# ---------------------------------------------------------------------------
# Config schema — models only the fields mc reads
# ---------------------------------------------------------------------------


class AgentDefaults(_Base):
    model: str = "anthropic/claude-opus-4-5"
    provider: str = "auto"
    workspace: str = ""


class AgentsConfig(_Base):
    defaults: AgentDefaults = Field(default_factory=AgentDefaults)
    models: list[str] = []


class ProviderConfig(_Base):
    api_key: str = ""
    api_base: str | None = None
    extra_headers: dict[str, str] | None = None


class ClaudeCodeConfig(_Base):
    cli_path: str = "claude"
    default_model: str = "claude-sonnet-4-6"
    default_max_budget_usd: float = Field(default=5.0, ge=0)
    default_max_turns: int = Field(default=50, ge=1)
    default_permission_mode: str = "bypassPermissions"
    auth_method: str = "oauth"

    @field_validator("auth_method")
    @classmethod
    def _validate_auth_method(cls, v: str) -> str:
        allowed = {"oauth", "api_key"}
        if v not in allowed:
            raise ValueError(f"auth_method must be one of {sorted(allowed)}")
        return v

    @field_validator("default_permission_mode")
    @classmethod
    def _validate_permission_mode(cls, v: str) -> str:
        allowed = {"default", "acceptEdits", "bypassPermissions", "plan"}
        if v not in allowed:
            raise ValueError(f"default_permission_mode must be one of {sorted(allowed)}")
        return v


class WebSearchConfig(_Base):
    api_key: str = ""


class WebConfig(_Base):
    search: WebSearchConfig = Field(default_factory=WebSearchConfig)


class ToolsConfig(_Base):
    web: WebConfig = Field(default_factory=WebConfig)


class TelegramConfig(_Base):
    token: str = ""


class ChannelsConfig(_Base):
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)


class Config(_Base):
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    providers: dict[str, ProviderConfig] = {}
    claude_code: ClaudeCodeConfig = Field(
        default_factory=ClaudeCodeConfig,
        alias="claudeCode",
    )
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)

    @property
    def workspace_path(self) -> Path:
        ws = self.agents.defaults.workspace
        if ws:
            return Path(ws).expanduser()
        from mc.infrastructure.runtime_home import get_workspace_dir

        return get_workspace_dir()

    def _match_provider(self, model: str | None = None) -> tuple[ProviderConfig | None, str | None]:
        """Match provider config and its registry name. Returns (config, spec_name)."""
        from mc.infrastructure.provider_registry import PROVIDERS

        forced = self.agents.defaults.provider
        if forced != "auto":
            p = self.providers.get(forced)
            return (p, forced) if p else (None, None)

        model_lower = (model or self.agents.defaults.model).lower()
        model_normalized = model_lower.replace("-", "_")
        model_prefix = model_lower.split("/", 1)[0] if "/" in model_lower else ""
        normalized_prefix = model_prefix.replace("-", "_")

        def _kw_matches(kw: str) -> bool:
            kw = kw.lower()
            return kw in model_lower or kw.replace("-", "_") in model_normalized

        # Explicit provider prefix wins — prevents `github-copilot/...codex` matching openai_codex.
        for spec in PROVIDERS:
            p = self.providers.get(spec.name)
            if p and model_prefix and normalized_prefix == spec.name:
                if spec.is_oauth or p.api_key:
                    return p, spec.name

        # Match by keyword (order follows PROVIDERS registry)
        for spec in PROVIDERS:
            p = self.providers.get(spec.name)
            if p and any(_kw_matches(kw) for kw in spec.keywords):
                if spec.is_oauth or p.api_key:
                    return p, spec.name

        # Fallback: gateways first, then others (follows registry order)
        # OAuth providers are NOT valid fallbacks — they require explicit model selection
        for spec in PROVIDERS:
            if spec.is_oauth:
                continue
            p = self.providers.get(spec.name)
            if p and p.api_key:
                return p, spec.name
        return None, None

    def get_provider(self, model: str | None = None) -> ProviderConfig | None:
        """Get matched provider config. Falls back to first available."""
        p, _ = self._match_provider(model)
        return p

    def get_provider_name(self, model: str | None = None) -> str | None:
        """Get the registry name of the matched provider."""
        _, name = self._match_provider(model)
        return name

    def get_api_base(self, model: str | None = None) -> str | None:
        """Get API base URL for the given model. Applies default URLs for known gateways."""
        from mc.infrastructure.provider_registry import find_by_name

        p, name = self._match_provider(model)
        if p and p.api_base:
            return p.api_base
        if name:
            spec = find_by_name(name)
            if spec and spec.is_gateway and spec.default_api_base:
                return spec.default_api_base
        return None


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_config(config_path: Path | None = None) -> Config:
    """Load config from disk, returning defaults for a fresh install.

    Raises ValueError on malformed JSON — no silent fallback.
    """
    from mc.infrastructure.runtime_home import get_config_path

    path = config_path or get_config_path()
    if not path.exists():
        return Config()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid config at {path}: {exc}") from exc
    return Config.model_validate(data)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _config_default_model() -> str:
    """Return the user's configured default model (with provider prefix).

    Reads ``agents.defaults.model`` from the configured runtime home config.
    This is the single source of truth for the active model/provider.
    """
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
