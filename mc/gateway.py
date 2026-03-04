"""
Agent Gateway — connects nanobot agents to Convex via the bridge.

Contains the sync_agent_registry function that loads agent YAML files,
validates them, and syncs them to the Convex agents table via the bridge.

Also contains the AgentGateway class that monitors agent processes for
crashes and implements auto-retry logic (FR37, FR38, NFR10).
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import os
import shutil
import signal
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from mc.orchestrator import TaskOrchestrator
from mc.timeout_checker import TimeoutChecker
from mc.yaml_validator import validate_agent_file

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge
    from mc.types import AgentData

logger = logging.getLogger(__name__)

AGENTS_DIR = Path.home() / ".nanobot" / "agents"
NANOBOT_AGENT_NAME = "nanobot"  # Re-exported for backward compat; canonical in types.py
_NANOBOT_AGENT_CONFIG = """\
name: nanobot
role: "{role}"
display_name: "{display_name}"
is_system: true
prompt: |
  You are the fallback agent for Mission Control task delegation.
  When the Lead Agent cannot find a specialist agent for a task,
  it is routed to you.

  Your identity, personality, and memory come from your SOUL.md and
  workspace files — do NOT invent a new persona.

  Focus on completing the delegated task using your tools and knowledge.
skills: []
"""


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
            Path(__file__).resolve().parents[2] / "dashboard",
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
    """
    if dashboard_dir is None:
        candidates = [
            Path.cwd() / "dashboard",
            Path(__file__).resolve().parents[2] / "dashboard",
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

    return None


def filter_agent_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Filter a dict to only known AgentData fields.

    Convex returns extra system fields (e.g. creation_time from _creationTime)
    that are not part of the AgentData dataclass. This function strips them.
    """
    from mc.types import AgentData

    valid_fields = {f.name for f in dataclasses.fields(AgentData)}
    return {k: v for k, v in data.items() if k in valid_fields}


def _parse_utc_timestamp(value: str) -> "datetime | None":
    """Parse an ISO 8601 timestamp string into a UTC-aware datetime.

    Handles the common variants produced by different systems:
    - ``Z`` suffix  (``2026-01-01T00:00:00Z``)
    - ``+00:00`` suffix (``2026-01-01T00:00:00+00:00``)
    - Naive (no timezone info) — assumed UTC

    Returns None if parsing fails so the caller can skip gracefully.
    """
    from datetime import datetime, timezone

    if not isinstance(value, str) or not value:
        return None
    try:
        # Normalise "Z" to "+00:00" for fromisoformat (Python < 3.11 compat)
        normalised = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalised)
        # If parsed as naive (no tz), treat as UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
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


def _restore_archived_files(agent_dir: Path, archive: dict) -> None:
    """Write archived memory/history/session files back to disk.

    Args:
        agent_dir: Path to the agent's local directory (e.g. ~/.nanobot/agents/{name}/).
        archive: Dict with optional keys memory_content, history_content, session_data.
    """
    memory_dir = agent_dir / "memory"
    sessions_dir = agent_dir / "sessions"

    memory_content = archive.get("memory_content")
    if memory_content:
        memory_dir.mkdir(parents=True, exist_ok=True)
        (memory_dir / "MEMORY.md").write_text(memory_content, encoding="utf-8")

    history_content = archive.get("history_content")
    if history_content:
        memory_dir.mkdir(parents=True, exist_ok=True)
        (memory_dir / "HISTORY.md").write_text(history_content, encoding="utf-8")

    session_data = archive.get("session_data")
    if session_data:
        sessions_dir.mkdir(parents=True, exist_ok=True)
        name = agent_dir.name
        (sessions_dir / f"mc_task_{name}.jsonl").write_text(session_data, encoding="utf-8")


def _cleanup_deleted_agents(bridge: "ConvexBridge", agents_dir: Path) -> None:
    """Archive local data for soft-deleted agents, then remove their folders.

    For each deleted agent that still has a local folder:
    1. Read MEMORY.md, HISTORY.md, and session JSONL files.
    2. Archive them to Convex (must succeed before deletion).
    3. Delete the local folder.

    Idempotent: if the local folder is already gone, no action is taken.
    Fail-safe: if archiving fails for an agent, its local folder is NOT deleted.
    """
    try:
        deleted_agents = bridge.list_deleted_agents()
    except Exception:
        logger.exception("Failed to list deleted agents for cleanup")
        return

    for agent_data in deleted_agents:
        name = agent_data.get("name")
        if not name:
            continue
        agent_dir = agents_dir / name
        if not agent_dir.is_dir():
            continue  # Already cleaned up — idempotent

        memory = _read_file_or_none(agent_dir / "memory" / "MEMORY.md")
        history = _read_file_or_none(agent_dir / "memory" / "HISTORY.md")
        session = _read_session_data(agent_dir / "sessions")

        if memory is None and history is None and session is None:
            logger.info("No archive data for agent '%s' — skipping archive call, proceeding to cleanup", name)
        else:
            try:
                bridge.archive_agent_data(name, memory, history, session)
                logger.info("Archived agent data for '%s'", name)
            except Exception:
                logger.exception("Failed to archive agent '%s' — skipping cleanup", name)
                continue  # Don't delete if archive failed

        try:
            shutil.rmtree(agent_dir)
            logger.info("Removed local folder for deleted agent '%s'", name)
        except OSError:
            logger.exception("Failed to remove local folder for agent '%s' — will retry on next sync", name)

        # TODO (CC-6 H1): Clean up cc_session:{name}:* keys from Convex settings
        # when an agent is deleted. The bridge does not currently expose a
        # settings:listByPrefix query, so we cannot enumerate and delete all
        # session keys for this agent. This is a known gap — when
        # settings:listByPrefix (or an equivalent bulk-delete mutation) is
        # available, iterate over cc_session:{name}:* keys and call
        # settings:set with value="" for each, or add a dedicated
        # settings:deleteByPrefix mutation.


def _write_back_convex_agents(bridge: ConvexBridge, agents_dir: Path) -> None:
    """Write-back Convex -> local for agents where Convex is newer.

    Both timestamps are compared as UTC-aware datetime objects.
    """
    from datetime import datetime, timezone

    try:
        convex_agents = bridge.list_agents()
    except Exception:
        logger.exception("Failed to list agents from Convex for write-back")
        return

    for agent_data in convex_agents:
        name = agent_data.get("name")
        if not name:
            continue

        # System agents (e.g. low-agent) are Convex-only — skip local write-back
        if agent_data.get("is_system"):
            continue

        config_path = agents_dir / name / "config.yaml"
        last_active = agent_data.get("last_active_at")
        if not last_active:
            continue

        convex_ts = _parse_utc_timestamp(last_active)
        if convex_ts is None:
            logger.warning(
                "Write-back: skipping agent '%s' — unparseable timestamp '%s'",
                name, last_active,
            )
            continue

        if config_path.is_file():
            local_mtime = datetime.fromtimestamp(
                config_path.stat().st_mtime, tz=timezone.utc
            )
            if convex_ts > local_mtime:
                try:
                    bridge.write_agent_config(agent_data, agents_dir)
                    logger.info("Write-back: updated local config for agent '%s'", name)
                except Exception:
                    logger.exception("Write-back failed for agent '%s'", name)
        else:
            # Agent exists in Convex but has no local YAML — create it
            try:
                bridge.write_agent_config(agent_data, agents_dir)
                logger.info("Write-back: created local config for agent '%s'", name)
            except Exception:
                logger.exception("Write-back failed for new agent '%s'", name)
                continue

            # Restore archived memory/history/session data if present (restore flow).
            # Clear the archive fields from Convex after a successful restore to free
            # storage and prevent stale data from being re-archived on a second delete.
            try:
                archive = bridge.get_agent_archive(name)
                if archive:
                    _restore_archived_files(agents_dir / name, archive)
                    logger.info("Restored archived data for agent '%s'", name)
                    try:
                        bridge.clear_agent_archive(name)
                    except Exception:
                        logger.exception("Failed to clear archive for agent '%s' — archive data remains in Convex", name)
            except Exception:
                logger.exception("Failed to restore archive for agent '%s'", name)


def _fetch_bot_identity() -> dict[str, str]:
    """Fetch the Telegram bot identity (name + role).

    Raises RuntimeError if Telegram is not configured or the API call fails.
    The nanobot agent MUST mirror the Telegram bot — no silent fallback.
    """
    from nanobot.config.loader import load_config
    import httpx

    config = load_config()
    if not config.channels.telegram.enabled or not config.channels.telegram.token:
        raise RuntimeError(
            "Telegram channel is not enabled or token is missing in ~/.nanobot/config.json. "
            "The nanobot agent requires a configured Telegram bot to mirror its identity."
        )

    token = config.channels.telegram.token
    proxy = config.channels.telegram.proxy

    kwargs: dict[str, Any] = {"timeout": 5.0}
    if proxy:
        kwargs["proxy"] = proxy

    try:
        with httpx.Client(**kwargs) as client:
            resp = client.get(f"https://api.telegram.org/bot{token}/getMe")
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok") or "result" not in data:
                raise RuntimeError(f"Telegram getMe returned unexpected response: {data}")
            first_name = data["result"].get("first_name")
            if not first_name:
                raise RuntimeError("Telegram bot has no first_name set")
            return {
                "name": first_name,
                "role": "Personal Assistant and Task Delegation Fallback",
            }
    except httpx.HTTPError as e:
        raise RuntimeError(f"Failed to fetch Telegram bot identity: {e}") from e

def ensure_nanobot_agent(agents_dir: Path) -> None:
    """Ensure the nanobot agent YAML definition exists on disk and links to the global workspace.

    Creates the directory and config.yaml if missing. Links SOUL.md, memory, and skills
    to the global workspace so the Mission Control agent shares the same persona and context
    as the Telegram bot.

    Raises RuntimeError if the Telegram bot identity cannot be fetched.
    """
    agent_dir = agents_dir / NANOBOT_AGENT_NAME
    config_path = agent_dir / "config.yaml"

    workspace = Path.home() / ".nanobot" / "workspace"

    # Fetch identity from Telegram — raises RuntimeError on failure (no fallback)
    identity = _fetch_bot_identity()
    bot_name = identity["name"]
    bot_role = identity["role"]

    if not config_path.is_file():
        agent_dir.mkdir(parents=True, exist_ok=True)
        config_content = _NANOBOT_AGENT_CONFIG.format(
            role=bot_role,
            display_name=bot_name,
        )
        config_path.write_text(config_content, encoding="utf-8")
        logger.info("Created nanobot agent definition at %s (Identity: %s)", config_path, bot_name)

    # Always try to fix up symlinks (for upgrades/retrofits)
    for item in ["memory", "skills", "SOUL.md"]:
        agent_path = agent_dir / item
        global_path = workspace / item

        # Global paths MUST already exist — they are created by 'nanobot onboard'.
        # memory/ and skills/ dirs are safe to create if missing, but SOUL.md must exist.
        if not global_path.exists():
            if item == "SOUL.md":
                raise RuntimeError(
                    f"Global workspace SOUL.md not found at {global_path}. "
                    "Run 'nanobot onboard' first to initialize the workspace."
                )
            else:
                global_path.mkdir(parents=True, exist_ok=True)

        # If the local item is an empty directory (from older versions), remove it
        if agent_path.is_dir() and not agent_path.is_symlink() and not any(agent_path.iterdir()):
            shutil.rmtree(agent_path)

        # Create symlink if missing
        if not agent_path.exists():
            try:
                os.symlink(global_path, agent_path)
                logger.info("Symlinked %s to global workspace for %s", item, bot_name)
            except Exception as e:
                logger.warning("Failed to symlink %s for nanobot agent: %s", item, e)


def ensure_low_agent(bridge: "ConvexBridge") -> None:
    """Upsert the low-agent system agent to Convex.

    low-agent is a pure system agent (no YAML file on disk). It is always
    configured with the standard-low model tier and is used internally for
    lightweight tasks such as auto-title generation.

    isSystem=True protects it from being deactivated by deactivateExcept.
    """
    from mc.types import LOW_AGENT_NAME, AgentData

    agent = AgentData(
        name=LOW_AGENT_NAME,
        display_name="Low Agent",
        role="Lightweight system utility agent",
        prompt="You are a lightweight system utility agent for internal tasks.",
        model="tier:standard-low",
        is_system=True,
    )
    bridge.sync_agent(agent)
    logger.info("[gateway] Ensured low-agent system agent")


def _sync_model_tiers(bridge: ConvexBridge) -> None:
    """Sync connected models list and seed default tiers on startup.

    - Writes available model identifiers to ``connected_models`` setting.
    - Seeds ``model_tiers`` with defaults if the setting does not yet exist.
    - Idempotent: existing tier mappings are never overwritten.

    Story 11.1 — AC #4.
    """
    import json

    # Collect available models from provider config
    from mc.provider_factory import list_available_models

    models_list = list_available_models()

    bridge.mutation(
        "settings:set",
        {"key": "connected_models", "value": json.dumps(models_list)},
    )

    # Derive default tier assignments from the models list.
    # Assumes list is ordered: high-capability first, low-capability last.
    def _pick_tier(keyword: str) -> str | None:
        for m in models_list:
            base = m.split("/", 1)[1] if "/" in m else m
            if keyword in base:
                return m
        return models_list[0] if models_list else None

    default_tiers = {
        "standard-low": _pick_tier("haiku"),
        "standard-medium": _pick_tier("sonnet"),
        "standard-high": _pick_tier("opus"),
        "reasoning-low": None,
        "reasoning-medium": None,
        "reasoning-high": None,
    }

    existing_raw = bridge.query("settings:get", {"key": "model_tiers"})
    if existing_raw is None:
        bridge.mutation(
            "settings:set",
            {"key": "model_tiers", "value": json.dumps(default_tiers)},
        )
        logger.info("[gateway] Seeded default model tiers: %s", default_tiers)
    else:
        # Migrate any tier values that are no longer in the connected_models list
        # (e.g. wrong provider prefix or outdated model ID from a previous seed).
        existing = json.loads(existing_raw)
        models_set = set(models_list)
        updated = dict(existing)
        changed = False
        for tier_key, default_val in default_tiers.items():
            current_val = existing.get(tier_key)
            if current_val and current_val not in models_set:
                updated[tier_key] = default_val
                logger.info(
                    "[gateway] Migrated model tier %s: %s → %s",
                    tier_key, current_val, default_val,
                )
                changed = True
        if changed:
            bridge.mutation(
                "settings:set",
                {"key": "model_tiers", "value": json.dumps(updated)},
            )
        else:
            logger.info("[gateway] Model tiers up to date — no migration needed")


def sync_agent_registry(
    bridge: ConvexBridge,
    agents_dir: Path,
    default_model: str | None = None,
) -> tuple[list[AgentData], dict[str, list[str]]]:
    """Sync agent YAML files to Convex agents table.

    Write-back first (Convex -> local), then validate, resolve models,
    upsert, and deactivate removed agents.

    Returns (synced_agents, errors_by_filename).
    """
    resolved_default = default_model or _config_default_model()

    # Step 0: Ensure system agents exist on disk
    ensure_nanobot_agent(agents_dir)

    # Ensure low-agent system agent exists in Convex
    try:
        ensure_low_agent(bridge)
    except Exception:
        logger.warning("[gateway] Failed to ensure low-agent", exc_info=True)

    # Step 0a: Cleanup — archive and remove local folders for soft-deleted agents
    _cleanup_deleted_agents(bridge, agents_dir)

    # Step 0b: Write-back — Convex → local for dashboard-edited agents
    _write_back_convex_agents(bridge, agents_dir)

    # Step 1: Validate agent YAML in each subdirectory
    valid_agents: list[AgentData] = []
    errors: dict[str, list[str]] = {}

    # Roles that represent non-delegatable sessions (e.g. tmux terminals)
    _NON_AGENT_ROLES = {"remote-terminal"}

    if agents_dir.is_dir():
        for child in sorted(agents_dir.iterdir()):
            config_file = child / "config.yaml"
            if child.is_dir() and config_file.is_file():
                # Quick-check: skip non-agent roles (tmux sessions, etc.)
                try:
                    raw = yaml.safe_load(config_file.read_text(encoding="utf-8"))
                    if isinstance(raw, dict) and raw.get("role") in _NON_AGENT_ROLES:
                        logger.debug(
                            "Skipping non-agent directory %s (role=%s)",
                            child.name, raw.get("role"),
                        )
                        continue
                except Exception:
                    pass  # Fall through to normal validation which reports errors

                result = validate_agent_file(config_file)
                if isinstance(result, list):
                    errors[child.name] = result
                    for msg in result:
                        logger.error("Skipping invalid agent %s: %s", child.name, msg)
                else:
                    valid_agents.append(result)

    # Step 2-3: Resolve model (with provider prefix) and sync each valid agent
    for agent in valid_agents:
        if not agent.model:
            agent.model = resolved_default
        elif "/" not in agent.model and resolved_default.endswith("/" + agent.model):
            # Bare model name matches config default — use full name with prefix
            agent.model = resolved_default

        try:
            bridge.sync_agent(agent)
            logger.info("Synced agent '%s' (%s)", agent.name, agent.role)
        except Exception:
            logger.exception("Failed to sync agent '%s'", agent.name)

    # Step 4: Deactivate agents whose YAML files were removed
    active_names = [agent.name for agent in valid_agents]
    try:
        bridge.deactivate_agents_except(active_names)
    except Exception:
        logger.exception("Failed to deactivate removed agents")

    return valid_agents, errors


def sync_skills(
    bridge: ConvexBridge,
    builtin_skills_dir: Path | None = None,
) -> list[str]:
    """Sync nanobot skills to Convex via SkillsLoader public API.

    Returns list of synced skill names.
    """
    # Lazy import to avoid heavy dependency chain through nanobot.agent.__init__
    import importlib.util
    _skills_path = Path(__file__).parent.parent / "vendor" / "nanobot" / "nanobot" / "agent" / "skills.py"
    spec = importlib.util.spec_from_file_location("_nanobot_skills", str(_skills_path))
    skills_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(skills_mod)
    SkillsLoader = skills_mod.SkillsLoader
    default_dir = skills_mod.BUILTIN_SKILLS_DIR

    resolved_dir = builtin_skills_dir or default_dir
    # Use configured workspace path (e.g. ~/.nanobot/workspace) for skill discovery
    from nanobot.config.loader import load_config
    workspace = load_config().workspace_path
    loader = SkillsLoader(workspace, builtin_skills_dir=resolved_dir)

    all_skills = loader.list_skills(filter_unavailable=False)
    synced_names: list[str] = []

    for skill_info in all_skills:
        name = skill_info["name"]
        source = skill_info["source"]  # "builtin" or "workspace"

        try:
            # Load body content (frontmatter stripped) via public API
            content_body = loader.get_skill_body(name)
            if not content_body:
                continue

            # Parse frontmatter metadata
            meta = loader.get_skill_metadata(name) or {}
            description = meta.get("description", name)
            metadata_str = meta.get("metadata")  # raw JSON string
            always = meta.get("always", "").lower() == "true" if meta.get("always") else False

            # Check requirements via public API
            available = loader.is_skill_available(name)
            requires_str = loader.get_missing_requirements(name) if not available else None

            # Upsert to Convex
            args: dict[str, Any] = {
                "name": name,
                "description": description,
                "content": content_body,
                "source": source,
                "available": available,
            }
            if metadata_str:
                args["metadata"] = metadata_str
            if always:
                args["always"] = True
            if requires_str:
                args["requires"] = requires_str

            bridge.mutation("skills:upsertByName", args)
            synced_names.append(name)
            logger.info("Synced skill '%s' (%s)", name, source)

        except Exception:
            logger.exception("Failed to sync skill '%s'", name)

    # Deactivate skills no longer on disk
    try:
        bridge.mutation("skills:deactivateExcept", {"active_names": synced_names})
    except Exception:
        logger.exception("Failed to deactivate removed skills")

    return synced_names


# Max auto-retries per task (FR37: single retry)
MAX_AUTO_RETRIES = 1


class AgentGateway:
    """Monitors agent processes and handles crash recovery with auto-retry.

    Implements FR37 (auto-retry once on crash), FR38 (crashed status with error
    log), and NFR10 (crash recovery within 30 seconds).
    """

    def __init__(self, bridge: ConvexBridge) -> None:
        self._bridge = bridge
        self._retry_counts: dict[str, int] = {}

    async def handle_agent_crash(
        self, agent_name: str, task_id: str, error: Exception
    ) -> None:
        """Handle an agent crash during task execution.

        On first crash: transitions task to "retrying", logs error to thread,
        and re-dispatches. On second crash (or if retry count already >= 1):
        transitions to "crashed" and stops.

        Args:
            agent_name: Name of the crashed agent.
            task_id: Convex task _id the agent was working on.
            error: The exception that caused the crash.
        """
        error_msg = f"{type(error).__name__}: {error}"
        current_retries = self._retry_counts.get(task_id, 0)

        if current_retries < MAX_AUTO_RETRIES:
            await self._retry_task(task_id, agent_name, error_msg, current_retries)
        else:
            await self._crash_task(task_id, agent_name, error_msg)

    async def _retry_task(
        self,
        task_id: str,
        agent_name: str,
        error_msg: str,
        current_retries: int,
    ) -> None:
        """Auto-retry: transition to retrying, log error, re-dispatch."""
        self._retry_counts[task_id] = current_retries + 1
        attempt = current_retries + 1

        logger.info(
            "[gateway] Agent '%s' crashed on task %s. "
            "Auto-retrying (attempt %d/%d)",
            agent_name, task_id, attempt, MAX_AUTO_RETRIES,
        )

        # Transition task to "retrying"
        await asyncio.to_thread(
            self._bridge.update_task_status,
            task_id,
            "retrying",
            agent_name,
            f"Agent {agent_name} crashed. Auto-retrying (attempt {attempt}/{MAX_AUTO_RETRIES})",
        )

        # Write error details to task thread
        await asyncio.to_thread(
            self._bridge.send_message,
            task_id,
            "System",
            "system",
            f"Agent crash detected:\n```\n{error_msg}\n```\nAuto-retrying...",
            "system_event",
        )

        # Re-dispatch: transition retrying -> in_progress
        await asyncio.to_thread(
            self._bridge.update_task_status,
            task_id,
            "in_progress",
            agent_name,
            f"Re-dispatching task to {agent_name}",
        )

    async def _crash_task(
        self, task_id: str, agent_name: str, error_msg: str
    ) -> None:
        """Retry exhausted: transition to crashed, log full error."""
        self._retry_counts.pop(task_id, None)

        logger.error(
            "[gateway] Agent '%s' crashed on task %s. "
            "Retry exhausted — marking as crashed.",
            agent_name, task_id,
        )

        # Transition task to "crashed"
        await asyncio.to_thread(
            self._bridge.update_task_status,
            task_id,
            "crashed",
            agent_name,
            f"Agent {agent_name} crashed. Retry failed. Task marked as crashed.",
        )

        # Write error details to task thread
        await asyncio.to_thread(
            self._bridge.send_message,
            task_id,
            "System",
            "system",
            (
                f"Retry failed. Agent crash:\n```\n{error_msg}\n```\n"
                "Task marked as crashed. Use 'Retry from Beginning' to try again."
            ),
            "system_event",
        )

    def clear_retry_count(self, task_id: str) -> None:
        """Clear the retry count for a task.

        Called when a task completes successfully or is manually retried
        (transitions to "inbox" via Story 6.4).
        """
        self._retry_counts.pop(task_id, None)

    def get_retry_count(self, task_id: str) -> int:
        """Return current retry count for a task."""
        return self._retry_counts.get(task_id, 0)


# Task IDs requeued by cron — plan negotiation manager skips these.
# Must be module-level so _process_batch (nested in _run_plan_negotiation_manager)
# and run_gateway() can both access it without a NameError.
_cron_requeued_ids: set[str] = set()


async def _run_plan_negotiation_manager(bridge: "ConvexBridge") -> None:
    """Manage per-task plan negotiation loops.

    Subscribes to tasks in both "review" (awaitingKickoff) and "in_progress"
    statuses. For each task that enters a negotiable state, spawns a
    start_plan_negotiation_loop coroutine. Prevents duplicate loops for the
    same task_id.

    The per-task loops are self-terminating — they exit when the task leaves
    a negotiable status. This manager only needs to spawn new ones.

    Story 7.3 — Task 4.3 / 4.4.
    """
    from mc.plan_negotiator import start_plan_negotiation_loop

    logger.info("[gateway] Plan negotiation manager started")

    # Track active negotiation loops to prevent duplicates
    active_negotiation_ids: set[str] = set()

    async def _spawn_loop_if_needed(task_id: str) -> None:
        """Spawn a plan negotiation loop for task_id if not already active."""
        if task_id in active_negotiation_ids:
            return
        active_negotiation_ids.add(task_id)
        logger.info("[gateway] Spawning plan negotiation loop for task %s", task_id)

        async def _run_and_cleanup() -> None:
            try:
                await start_plan_negotiation_loop(bridge, task_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "[gateway] Plan negotiation loop for task %s crashed", task_id
                )
            finally:
                active_negotiation_ids.discard(task_id)
                logger.info(
                    "[gateway] Plan negotiation loop for task %s ended", task_id
                )

        asyncio.create_task(_run_and_cleanup())

    # Subscribe to both review and in_progress task lists
    review_queue = bridge.async_subscribe(
        "tasks:listByStatus", {"status": "review"}
    )
    in_progress_queue = bridge.async_subscribe(
        "tasks:listByStatus", {"status": "in_progress"}
    )

    async def _process_batch(tasks_batch: object) -> None:
        """Process a batch of tasks from either subscription queue."""
        if not tasks_batch or isinstance(tasks_batch, dict):
            return
        for task_data in tasks_batch:  # type: ignore[union-attr]
            task_id = task_data.get("id")
            if not task_id:
                continue

            task_status = task_data.get("status", "")
            awaiting_kickoff = task_data.get("awaiting_kickoff", False)

            # Only spawn for supervised tasks in review (awaitingKickoff) or in_progress
            if task_status == "in_progress" or (
                task_status == "review" and awaiting_kickoff
            ):
                # Skip plan negotiation for cron-requeued tasks (they
                # re-enter in_progress but don't need lead-agent interaction).
                # Manual reassignments are NOT in this set and proceed normally.
                if task_id in _cron_requeued_ids:
                    _cron_requeued_ids.discard(task_id)
                    logger.info(
                        "[gateway] Skipping plan negotiation for task %s "
                        "(cron requeue)",
                        task_id,
                    )
                    continue
                await _spawn_loop_if_needed(task_id)

    # Drain both queues by creating persistent reader tasks so no queue.get()
    # coroutine is ever abandoned (avoids leaked asyncio tasks from asyncio.wait).
    async def _drain_queue(queue: asyncio.Queue) -> None:  # type: ignore[type-arg]
        while True:
            try:
                batch = await queue.get()
                await _process_batch(batch)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "[gateway] Plan negotiation manager: error reading queue: %s",
                    exc,
                )

    reader_tasks = [
        asyncio.create_task(_drain_queue(review_queue)),
        asyncio.create_task(_drain_queue(in_progress_queue)),
    ]
    try:
        # Wait until cancelled (gateway shutdown)
        await asyncio.gather(*reader_tasks)
    finally:
        for t in reader_tasks:
            t.cancel()


async def run_gateway(bridge: ConvexBridge) -> None:
    """Gateway main loop — starts orchestrator, executor, timeout checker, and cron service.

    Args:
        bridge: ConvexBridge instance used by all components.
    """
    from mc.executor import TaskExecutor
    from nanobot.cron.service import CronService
    from nanobot.cron.types import CronJob
    from nanobot.config.loader import load_config

    logger.info("[gateway] Agent Gateway started")

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    config = load_config()

    # Lightweight delivery: dict tracks pending cron deliveries, callback sends after completion
    pending_deliveries: dict[str, tuple[str, str]] = {}  # task_id → (channel, to)

    async def _send_telegram_direct(chat_id: str, content: str) -> None:
        """Send message to Telegram without polling — direct Bot API call."""
        from telegram import Bot
        from nanobot.channels.telegram import _markdown_to_telegram_html, _split_message

        if not chat_id.lstrip("-").isdigit():
            logger.error(
                "[gateway] Telegram delivery aborted — chat_id %r is not a numeric ID. "
                "The cron job was likely created with deliver_to set to an MC agent name "
                "instead of a Telegram chat ID. Update or recreate the cron job with the "
                "correct numeric chat_id (e.g. '986097959').",
                chat_id,
            )
            return
        token = config.channels.telegram.token
        if not token:
            logger.warning("[gateway] No Telegram token — skipping delivery")
            return
        bot = Bot(token=token)
        html = _markdown_to_telegram_html(content)
        for chunk in _split_message(html):
            await bot.send_message(chat_id=int(chat_id), text=chunk, parse_mode="HTML")

    async def on_task_completed(task_id: str, result: str) -> None:
        """Callback invoked by executor after agent completes — delivers result if pending."""
        delivery = pending_deliveries.pop(task_id, None)
        if not delivery:
            return
        if not result.strip():
            logger.info("[gateway] Skipping delivery for task %s — empty result (task may have failed)", task_id)
            return
        channel, to = delivery
        try:
            if channel == "telegram":
                await _send_telegram_direct(to, result)
                logger.info("[gateway] Delivered cron result for task %s → telegram:%s", task_id, to)
            else:
                logger.warning("[gateway] Delivery to '%s' not supported", channel)
        except Exception:
            logger.exception("[gateway] Failed to deliver result for task %s", task_id)

    # Cron service — when a job fires, create a task in Convex (enters normal MC flow)
    cron_store_path = Path.home() / ".nanobot" / "cron" / "jobs.json"
    cron = CronService(cron_store_path)

    async def _requeue_cron_task(b: "ConvexBridge", task_id: str, message: str, agent: str | None = None) -> bool:
        """Re-queue an existing task for cron execution.

        Injects the cron trigger message into the task's thread so the agent
        sees it as a new user turn, then resets status to 'assigned' so the
        executor picks it up again. Skips if the task is already active.

        Returns True if the task was actually re-queued, False otherwise.
        """
        from mc.types import (
            AuthorType,
            MessageType,
            is_lead_agent,
        )

        try:
            task = await asyncio.to_thread(b.query, "tasks:getById", {"task_id": task_id})
        except Exception:
            logger.warning("[gateway] Could not fetch cron origin task %s — creating new task instead", task_id)
            create_args: dict = {"title": message}
            if agent:
                create_args["assigned_agent"] = agent
            await asyncio.to_thread(b.mutation, "tasks:create", create_args)
            return False

        if not task:
            logger.warning("[gateway] Cron origin task %s not found — creating new task", task_id)
            create_args = {"title": message}
            if agent:
                create_args["assigned_agent"] = agent
            await asyncio.to_thread(b.mutation, "tasks:create", create_args)
            return False

        current_status = task.get("status", "")
        if current_status in ("in_progress", "assigned", "deleted"):
            logger.info(
                "[gateway] Cron origin task %s is '%s' — skipping re-queue",
                task_id, current_status,
            )
            return False

        agent_name = agent or task.get("assigned_agent") or NANOBOT_AGENT_NAME
        if is_lead_agent(agent_name):
            logger.warning(
                "[gateway] Cron task %s had lead-agent assignment; using %s "
                "(pure orchestrator invariant)",
                task_id,
                NANOBOT_AGENT_NAME,
            )
            agent_name = NANOBOT_AGENT_NAME

        # Inject cron trigger as a new user message so it appears in the thread
        await asyncio.to_thread(
            b.send_message,
            task_id,
            "Cron",
            AuthorType.USER,
            f"🔔 Cron triggered: {message}",
            MessageType.USER_MESSAGE,
        )

        # Reset task to 'assigned' — the executor will pick it up and run the agent
        await asyncio.to_thread(
            b.update_task_status,
            task_id,
            "assigned",
            agent_name,
            f"Cron re-queued task to {agent_name}",
        )
        _cron_requeued_ids.add(task_id)
        logger.info("[gateway] Cron re-queued task %s → assigned to %s", task_id, agent_name)
        return True

    async def on_cron_job(job: CronJob) -> str | None:
        """Re-queue the originating task (if linked) or create a new task when a cron job fires."""
        logger.info("[gateway] Cron job '%s' fired", job.name)
        task_id_for_delivery: str | None = None
        try:
            if job.payload.task_id:
                requeued = await _requeue_cron_task(bridge, job.payload.task_id, job.payload.message, agent=job.payload.agent)
                if requeued:
                    task_id_for_delivery = job.payload.task_id
            else:
                # No linked task — create a new task (classic cron behavior)
                create_args: dict = {"title": job.payload.message}
                if job.payload.agent:
                    create_args["assigned_agent"] = job.payload.agent
                new_id = await asyncio.to_thread(
                    bridge.mutation,
                    "tasks:create",
                    create_args,
                )
                task_id_for_delivery = new_id
        except Exception:
            logger.exception("[gateway] Failed to handle cron job '%s'", job.name)

        # Register pending delivery (executor will call on_task_completed after agent finishes)
        if (
            task_id_for_delivery
            and job.payload.deliver
            and job.payload.channel
            and job.payload.to
            and job.payload.channel != "mc"
        ):
            pending_deliveries[task_id_for_delivery] = (job.payload.channel, job.payload.to)

        return None

    cron.on_job = on_cron_job
    await cron.start()
    cron_status = cron.status()
    if cron_status["jobs"] > 0:
        logger.info("[gateway] Cron service started with %d job(s)", cron_status["jobs"])

    orchestrator = TaskOrchestrator(bridge, cron_service=cron)

    async def _inbox_loop_with_crash_log() -> None:
        try:
            await orchestrator.start_inbox_routing_loop()
        except Exception as exc:
            logger.critical(
                "[gateway] Inbox routing loop CRASHED — auto-title will not work: %s",
                exc,
            )

    inbox_task = asyncio.create_task(_inbox_loop_with_crash_log())
    routing_task = asyncio.create_task(orchestrator.start_routing_loop())
    review_task = asyncio.create_task(orchestrator.start_review_routing_loop())
    kickoff_task = asyncio.create_task(orchestrator.start_kickoff_watch_loop())

    executor = TaskExecutor(bridge, cron_service=cron, on_task_completed=on_task_completed)
    execution_task = asyncio.create_task(executor.start_execution_loop())

    timeout_checker = TimeoutChecker(bridge)
    timeout_task = asyncio.create_task(timeout_checker.start())

    # Plan negotiation manager — spawns per-task loops for review/in_progress tasks
    plan_negotiation_task = asyncio.create_task(
        _run_plan_negotiation_manager(bridge)
    )

    # Chat handler — polls for pending direct-chat messages (Story 10.2)
    from mc.chat_handler import ChatHandler

    chat_handler = ChatHandler(bridge)
    chat_task = asyncio.create_task(chat_handler.run())

    # Mention watcher — detects @agent-name mentions in all task threads
    # (covers tasks not handled by plan_negotiator: done, crashed, inbox, etc.)
    from mc.mention_watcher import MentionWatcher

    mention_watcher = MentionWatcher(bridge)
    mention_task = asyncio.create_task(mention_watcher.run())

    # Wait for shutdown signal
    await stop_event.wait()
    logger.info("[gateway] Agent Gateway stopping...")

    cron.stop()

    # Cancel all loops gracefully
    inbox_task.cancel()
    routing_task.cancel()
    review_task.cancel()
    kickoff_task.cancel()
    execution_task.cancel()
    timeout_task.cancel()
    plan_negotiation_task.cancel()
    chat_task.cancel()
    mention_task.cancel()
    for task in (
        inbox_task,
        routing_task,
        review_task,
        kickoff_task,
        execution_task,
        timeout_task,
        plan_negotiation_task,
        chat_task,
        mention_task,
    ):
        try:
            await task
        except asyncio.CancelledError:
            pass


async def main() -> None:
    """Gateway entry point — resolves Convex URL, creates bridge, syncs agents, runs gateway."""
    from mc.bridge import ConvexBridge

    convex_url = _resolve_convex_url()
    if not convex_url:
        logger.error(
            "[gateway] Cannot start: Convex URL not found. "
            "Set CONVEX_URL env var or ensure dashboard/.env.local exists."
        )
        return

    admin_key = os.environ.get("CONVEX_ADMIN_KEY") or _resolve_admin_key()
    if not admin_key:
        logger.error(
            "[gateway] Cannot start: CONVEX_ADMIN_KEY not set. "
            "Set CONVEX_ADMIN_KEY env var or add it to dashboard/.env.local."
        )
        return

    bridge = ConvexBridge(convex_url, admin_key)

    try:
        agents_dir = AGENTS_DIR
        if agents_dir.is_dir():
            synced, errors = sync_agent_registry(bridge, agents_dir)
            logger.info("[gateway] Synced %d agent(s)", len(synced))
            for filename, errs in errors.items():
                for err in errs:
                    logger.warning("[gateway] Agent sync error (%s): %s", filename, err)

        # Sync skills alongside agents (Story 8.2)
        try:
            skill_names = sync_skills(bridge)
            logger.info("[gateway] Synced %d skill(s)", len(skill_names))
        except Exception:
            logger.exception("[gateway] Skills sync failed")

        # Sync connected models and seed default tiers (Story 11.1, AC4)
        try:
            _sync_model_tiers(bridge)
            logger.info("[gateway] Model tiers synced")
        except Exception:
            logger.exception("[gateway] Model tiers sync failed")

        # Ensure default board exists (AC2)
        try:
            bridge.ensure_default_board()
            logger.info("[gateway] Default board ensured")
        except Exception:
            logger.exception("[gateway] Failed to ensure default board")

        await run_gateway(bridge)
    finally:
        bridge.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
