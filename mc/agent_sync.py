"""Agent registry synchronization — disk <-> Convex agent sync.

Syncs agent YAML definitions from ~/.nanobot/agents/ to Convex, handles
write-back from Convex to local, ensures system agents (nanobot, low-agent)
exist, and syncs the nanobot default model to config.json.

Extracted from mc.gateway to separate sync logic from runtime lifecycle.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from mc.yaml_validator import validate_agent_file

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge
    from mc.types import AgentData

logger = logging.getLogger(__name__)

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

    # Step 0b: Write-back — Convex -> local for dashboard-edited agents
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


def sync_nanobot_default_model(bridge: "ConvexBridge") -> bool:
    """Sync config.json default model from the canonical Convex system agent."""
    import json

    agent = bridge.get_agent_by_name(NANOBOT_AGENT_NAME)
    if not agent:
        logger.warning(
            "[gateway] Skipping %s model sync: agent not found in Convex",
            NANOBOT_AGENT_NAME,
        )
        return False

    convex_model: str | None = None
    if isinstance(agent, dict):
        model_val = agent.get("model")
        if isinstance(model_val, str):
            convex_model = model_val.strip()
    else:
        model_val = getattr(agent, "model", None)
        if isinstance(model_val, str):
            convex_model = model_val.strip()

    if not convex_model:
        logger.warning(
            "[gateway] Skipping %s model sync: missing model in Convex",
            NANOBOT_AGENT_NAME,
        )
        return False

    # Resolve tier references (e.g. "tier:standard-low" -> "anthropic/claude-haiku-4-5")
    if convex_model.startswith("tier:"):
        from mc.tier_resolver import TierResolver

        try:
            resolver = TierResolver(bridge)
            resolved = resolver.resolve_model(convex_model)
            if not resolved:
                logger.warning(
                    "[gateway] Skipping %s model sync: tier '%s' resolved to None",
                    NANOBOT_AGENT_NAME,
                    convex_model,
                )
                return False
            logger.info(
                "[gateway] Resolved %s model tier: %s -> %s",
                NANOBOT_AGENT_NAME,
                convex_model,
                resolved,
            )
            convex_model = resolved
        except Exception:
            logger.warning(
                "[gateway] Skipping %s model sync: failed to resolve tier '%s'",
                NANOBOT_AGENT_NAME,
                convex_model,
                exc_info=True,
            )
            return False

    from nanobot.config.loader import get_config_path

    config_path = get_config_path()
    if not config_path.exists():
        logger.warning(
            "[gateway] Skipping %s model sync: config not found at %s",
            NANOBOT_AGENT_NAME,
            config_path,
        )
        return False

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        logger.warning(
            "[gateway] Skipping %s model sync: could not read %s",
            NANOBOT_AGENT_NAME,
            config_path,
            exc_info=True,
        )
        return False

    if not isinstance(config, dict):
        logger.warning(
            "[gateway] Skipping %s model sync: invalid config format",
            NANOBOT_AGENT_NAME,
        )
        return False

    agents_cfg = config.setdefault("agents", {})
    if not isinstance(agents_cfg, dict):
        logger.warning(
            "[gateway] Skipping %s model sync: invalid agents config",
            NANOBOT_AGENT_NAME,
        )
        return False

    defaults_cfg = agents_cfg.setdefault("defaults", {})
    if not isinstance(defaults_cfg, dict):
        logger.warning(
            "[gateway] Skipping %s model sync: invalid agents.defaults config",
            NANOBOT_AGENT_NAME,
        )
        return False

    old_model = defaults_cfg.get("model")
    if old_model == convex_model:
        logger.debug(
            "[gateway] %s default model already in sync: %s",
            NANOBOT_AGENT_NAME,
            convex_model,
        )
        return False

    defaults_cfg["model"] = convex_model

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=config_path.parent,
            prefix=f"{config_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp_file:
            tmp_path = tmp_file.name
            json.dump(config, tmp_file, indent=2, ensure_ascii=False)
            tmp_file.write("\n")
        os.replace(tmp_path, config_path)
    except Exception:
        logger.error(
            "[gateway] Failed to sync %s default model to %s",
            NANOBOT_AGENT_NAME,
            config_path,
            exc_info=True,
        )
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                pass
        return False

    logger.info(
        "[gateway] Updated %s default model: %s -> %s",
        NANOBOT_AGENT_NAME,
        old_model,
        convex_model,
    )
    return True
