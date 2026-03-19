"""
Agent bootstrap — low-agent bootstrap, agent sync, and related config logic.

Extracted from mc.gateway so that internal modules can access agent bootstrap
helpers without depending on the gateway composition root.

Contains:
- ensure_nanobot_agent / ensure_low_agent
- sync_agent_registry / sync_skills / sync_nanobot_default_model
- _sync_model_tiers / _sync_embedding_model
- _distribute_builtin_skills
- _cleanup_deleted_agents / _write_back_convex_agents / _restore_archived_files
- _fetch_bot_identity
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from mc.infrastructure.config import (
    _config_default_model,
    _parse_utc_timestamp,
    _read_file_or_none,
)

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge
    from mc.types import AgentData

logger = logging.getLogger(__name__)

NANOBOT_AGENT_NAME = "nanobot"  # Re-exported for backward compat; canonical in types.py
_SKILL_PROVIDER_ORDER = ("claude-code", "codex", "nanobot")
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


def _parse_skill_metadata_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _detect_supported_providers(skill_info: dict[str, Any], metadata_str: str | None) -> list[str]:
    providers: set[str] = {"claude-code", "nanobot"}
    skill_md_path = Path(str(skill_info["path"]))
    skill_dir = skill_md_path.parent

    if (skill_dir / "agents" / "openai.yaml").exists():
        providers.add("codex")

    metadata = _parse_skill_metadata_json(metadata_str)
    adapters = metadata.get("adapters")
    if isinstance(adapters, dict):
        configured = adapters.get("providers")
        if isinstance(configured, list):
            providers = {str(value) for value in configured if str(value) in _SKILL_PROVIDER_ORDER}
            providers.update({"claude-code", "nanobot"})
            if (skill_dir / "agents" / "openai.yaml").exists():
                providers.add("codex")

    return [provider for provider in _SKILL_PROVIDER_ORDER if provider in providers]


def _fetch_bot_identity() -> dict[str, str]:
    """Fetch the Telegram bot identity (name + role).

    Raises RuntimeError if Telegram is not configured or the API call fails.
    The nanobot agent MUST mirror the Telegram bot — no silent fallback.
    """
    import httpx
    from nanobot.config.loader import load_config

    config = load_config()
    if not config.channels.telegram.enabled or not config.channels.telegram.token:
        raise RuntimeError(
            "Telegram channel is not enabled or token is missing in "
            "~/.nanobot/config.json. "
            "The nanobot agent requires a configured Telegram bot to "
            "mirror its identity."
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
        logger.info(
            "Created nanobot agent definition at %s (Identity: %s)",
            config_path,
            bot_name,
        )

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


def ensure_low_agent(bridge: ConvexBridge) -> None:
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


def _restore_archived_files(agent_dir: Path, archive: dict) -> None:
    """Write archived memory/history/session files back to disk (legacy compat).

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


def _restore_memory_from_backup(bridge: ConvexBridge, agent_name: str, agent_dir: Path) -> None:
    """Restore board-scoped memory from Convex backup when files are missing on disk.

    Checks each board in the backup — if the board workspace memory directory
    is missing locally, recreates it and writes MEMORY.md + HISTORY.md.
    Also restores global workspace memory for nanobot.

    Archive data is never cleared — it persists as a permanent backup.
    """
    try:
        backup = bridge.get_agent_memory_backup(agent_name)
    except Exception:
        logger.warning("Failed to fetch memory backup for agent '%s'", agent_name, exc_info=True)
        return

    if not backup:
        return

    boards_root = Path.home() / ".nanobot" / "boards"
    restored_count = 0

    # Restore per-board memory
    boards = backup.get("boards") or []
    for board_entry in boards:
        board_name = board_entry.get("board_name")
        if not board_name:
            continue
        board_memory_dir = boards_root / board_name / "agents" / agent_name / "memory"
        memory_file = board_memory_dir / "MEMORY.md"
        history_file = board_memory_dir / "HISTORY.md"

        # Only restore if memory directory or files are missing
        if memory_file.exists() and history_file.exists():
            continue

        board_memory_dir.mkdir(parents=True, exist_ok=True)
        # Also ensure sessions dir exists
        (boards_root / board_name / "agents" / agent_name / "sessions").mkdir(
            parents=True, exist_ok=True
        )

        mem = board_entry.get("memory_content")
        if mem and not memory_file.exists():
            memory_file.write_text(mem, encoding="utf-8")
        hist = board_entry.get("history_content")
        if hist and not history_file.exists():
            history_file.write_text(hist, encoding="utf-8")

        restored_count += 1
        logger.info(
            "Restored board memory for agent '%s' on board '%s'",
            agent_name,
            board_name,
        )

    # Restore global workspace memory (nanobot)
    global_mem = backup.get("global_memory_content")
    global_hist = backup.get("global_history_content")
    if global_mem or global_hist:
        global_memory_dir = agent_dir / "memory"
        global_memory_dir.mkdir(parents=True, exist_ok=True)
        if global_mem and not (global_memory_dir / "MEMORY.md").exists():
            (global_memory_dir / "MEMORY.md").write_text(global_mem, encoding="utf-8")
            restored_count += 1
        if global_hist and not (global_memory_dir / "HISTORY.md").exists():
            (global_memory_dir / "HISTORY.md").write_text(global_hist, encoding="utf-8")

    if restored_count:
        logger.info(
            "Restored memory for agent '%s' from backup (%d items)", agent_name, restored_count
        )


def _backup_agent_memory(bridge: ConvexBridge, agents_dir: Path) -> int:
    """Back up all agent memory to Convex.

    Regular agents: scans board workspaces for MEMORY.md and HISTORY.md.
    Nanobot: reads from global workspace.

    Returns count of agents backed up.
    """
    from mc.infrastructure.boards import list_agent_board_workspaces

    backed_up = 0

    try:
        convex_agents = bridge.list_agents()
    except Exception:
        logger.exception("Failed to list agents for memory backup")
        return 0

    for agent_data in convex_agents:
        name = agent_data.get("name")
        if not name:
            continue
        # Skip agents with no local directory (e.g. low-agent is Convex-only).
        agent_dir = agents_dir / name
        if not agent_dir.is_dir():
            continue

        try:
            if name == NANOBOT_AGENT_NAME:
                # Nanobot uses global workspace
                workspace = Path.home() / ".nanobot" / "workspace"
                global_mem = _read_file_or_none(workspace / "memory" / "MEMORY.md")
                global_hist = _read_file_or_none(workspace / "memory" / "HISTORY.md")
                if global_mem is not None or global_hist is not None:
                    bridge.backup_agent_memory(
                        name,
                        boards_data=[],
                        global_data={
                            "memory_content": global_mem,
                            "history_content": global_hist,
                        },
                    )
                    backed_up += 1
                    logger.info("Backed up nanobot global memory")
            else:
                # Regular agents — collect per-board memory
                boards_data: list[dict[str, Any]] = []
                board_workspaces = list_agent_board_workspaces(name)
                for board_name, board_ws in board_workspaces:
                    memory_dir = board_ws / "memory"
                    mem = _read_file_or_none(memory_dir / "MEMORY.md")
                    hist = _read_file_or_none(memory_dir / "HISTORY.md")
                    if mem is not None or hist is not None:
                        entry: dict[str, Any] = {"board_name": board_name}
                        if mem is not None:
                            entry["memory_content"] = mem
                        if hist is not None:
                            entry["history_content"] = hist
                        boards_data.append(entry)

                if boards_data:
                    bridge.backup_agent_memory(name, boards_data)
                    backed_up += 1
                    logger.info(
                        "Backed up memory for agent '%s' (%d boards)", name, len(boards_data)
                    )
        except Exception:
            logger.exception("Failed to backup memory for agent '%s'", name)

    return backed_up


def _cleanup_deleted_agents(bridge: ConvexBridge, agents_dir: Path) -> None:
    """Archive local data for soft-deleted agents (board-scoped + global), then remove their folders.

    For each deleted agent that still has a local folder:
    1. Scan board workspaces for per-board MEMORY.md and HISTORY.md.
    2. Read global agent memory (for fallback/nanobot).
    3. Back up to Convex via upsertMemoryBackup (must succeed before deletion).
    4. Delete local agent folder and board workspace directories.

    Idempotent: if the local folder is already gone, no action is taken.
    Fail-safe: if backup fails for an agent, its local folder is NOT deleted.
    """
    from mc.infrastructure.boards import list_agent_board_workspaces

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

        # Collect board-scoped memory
        boards_data: list[dict[str, Any]] = []
        board_workspaces = list_agent_board_workspaces(name)
        for board_name, board_ws in board_workspaces:
            memory_dir = board_ws / "memory"
            mem = _read_file_or_none(memory_dir / "MEMORY.md")
            hist = _read_file_or_none(memory_dir / "HISTORY.md")
            if mem is not None or hist is not None:
                entry: dict[str, Any] = {"board_name": board_name}
                if mem is not None:
                    entry["memory_content"] = mem
                if hist is not None:
                    entry["history_content"] = hist
                boards_data.append(entry)

        # Collect global agent memory (fallback)
        global_mem = _read_file_or_none(agent_dir / "memory" / "MEMORY.md")
        global_hist = _read_file_or_none(agent_dir / "memory" / "HISTORY.md")
        global_data: dict[str, str | None] | None = None
        if global_mem is not None or global_hist is not None:
            global_data = {
                "memory_content": global_mem,
                "history_content": global_hist,
            }

        if not boards_data and global_data is None:
            logger.info(
                "No archive data for agent '%s' — skipping backup call, proceeding to cleanup",
                name,
            )
        else:
            try:
                bridge.backup_agent_memory(name, boards_data, global_data)
                logger.info("Backed up agent memory for '%s' (%d boards)", name, len(boards_data))
            except Exception:
                logger.exception("Failed to backup agent '%s' — skipping cleanup", name)
                continue  # Don't delete if backup failed

        # Delete board workspace directories
        for _board_name, board_ws in board_workspaces:
            try:
                shutil.rmtree(board_ws)
            except OSError:
                logger.warning("Failed to remove board workspace %s for agent '%s'", board_ws, name)

        # Delete global agent directory
        try:
            shutil.rmtree(agent_dir)
            logger.info("Removed local folder for deleted agent '%s'", name)
        except OSError:
            logger.exception(
                "Failed to remove local folder for agent '%s' — will retry on next sync",
                name,
            )


def _write_back_convex_agents(bridge: ConvexBridge, agents_dir: Path) -> None:
    """Write-back Convex -> local for agents where Convex is newer.

    Both timestamps are compared as UTC-aware datetime objects.
    After writing config.yaml, checks if board memory directories are missing
    and restores from Convex backup if available. Archive is never cleared.
    """
    from datetime import datetime

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
                name,
                last_active,
            )
            continue

        if config_path.is_file():
            local_mtime = datetime.fromtimestamp(config_path.stat().st_mtime, tz=UTC)
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

        # Restore memory from backup if board workspaces are missing on disk.
        # Archive data is kept persistent — never cleared after restore.
        _restore_memory_from_backup(bridge, name, agents_dir / name)


def _sync_model_tiers(bridge: ConvexBridge) -> None:
    """Sync connected models list and seed default tiers on startup.

    - Writes available model identifiers to ``connected_models`` setting.
    - Seeds ``model_tiers`` with defaults if the setting does not yet exist.
    - Idempotent: existing tier mappings are never overwritten.

    Story 11.1 — AC #4.
    """
    # Collect available models from provider config
    from mc.infrastructure.providers.factory import list_available_models

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
                    tier_key,
                    current_val,
                    default_val,
                )
                changed = True
        if changed:
            bridge.mutation(
                "settings:set",
                {"key": "model_tiers", "value": json.dumps(updated)},
            )
        else:
            logger.info("[gateway] Model tiers up to date — no migration needed")


def _sync_embedding_model(bridge: ConvexBridge) -> None:
    """Sync the memory embedding model setting from Convex to env/disk."""
    try:
        model = bridge.query("settings:get", {"key": "memory_embedding_model"})
    except Exception:
        logger.warning("[gateway] Failed to read memory_embedding_model setting")
        return
    if model:
        os.environ["NANOBOT_MEMORY_EMBEDDING_MODEL"] = model
        logger.info("[gateway] Memory embedding model set: %s", model)
    else:
        os.environ.pop("NANOBOT_MEMORY_EMBEDDING_MODEL", None)
        logger.info("[gateway] Memory embedding model cleared (FTS-only)")

    # Persist to memory_settings.json so standalone nanobot (Telegram) can read it
    try:
        settings_path = Path.home() / ".nanobot" / "memory_settings.json"
        existing: dict = {}
        if settings_path.exists():
            existing = json.loads(settings_path.read_text(encoding="utf-8"))
        existing["embedding_model"] = model or ""
        settings_path.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        logger.debug("[gateway] Failed to persist embedding model to memory_settings.json")


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
    from mc.infrastructure.agents.yaml_validator import validate_agent_file

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
    non_agent_roles = {"remote-terminal"}

    if agents_dir.is_dir():
        for child in sorted(agents_dir.iterdir()):
            config_file = child / "config.yaml"
            if child.is_dir() and config_file.is_file():
                # Quick-check: skip non-agent roles (tmux sessions, etc.)
                try:
                    raw = yaml.safe_load(config_file.read_text(encoding="utf-8"))
                    if isinstance(raw, dict) and raw.get("role") in non_agent_roles:
                        logger.debug(
                            "Skipping non-agent directory %s (role=%s)",
                            child.name,
                            raw.get("role"),
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


def _distribute_builtin_skills(workspace_skills_dir: Path, *source_dirs: Path) -> None:
    """Copy builtin skill directories to the workspace if not already present.

    For each *source_dir*, iterates its subdirectories looking for those that
    contain a ``SKILL.md`` file. If the corresponding directory does not yet
    exist under *workspace_skills_dir*, it is copied via ``shutil.copytree()``.

    Existing workspace skills are **never** overwritten so that user
    customizations are preserved.
    """
    workspace_skills_dir.mkdir(parents=True, exist_ok=True)

    for source_dir in source_dirs:
        if not source_dir.is_dir():
            logger.debug("Skipping missing builtin skills source: %s", source_dir)
            continue

        for entry in sorted(source_dir.iterdir()):
            if not entry.is_dir():
                continue
            if not (entry / "SKILL.md").exists():
                continue

            target = workspace_skills_dir / entry.name
            if target.exists():
                logger.debug(
                    "Skill '%s' already exists in workspace, skipping",
                    entry.name,
                )
                continue

            shutil.copytree(entry, target)
            logger.info("Distributed builtin skill '%s' to workspace", entry.name)


def sync_skills(
    bridge: ConvexBridge,
    builtin_skills_dir: Path | None = None,
) -> list[str]:
    """Sync nanobot skills to Convex via SkillsLoader public API.

    Returns list of synced skill names.
    """
    # Lazy import to avoid heavy dependency chain through nanobot.agent.__init__
    import importlib.util

    _skills_path = (
        Path(__file__).parent.parent.parent
        / "vendor"
        / "nanobot"
        / "nanobot"
        / "agent"
        / "skills.py"
    )
    spec = importlib.util.spec_from_file_location("_nanobot_skills", str(_skills_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load skill module from {_skills_path}")
    skills_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(skills_mod)
    skills_loader_cls = skills_mod.SkillsLoader
    default_dir = skills_mod.BUILTIN_SKILLS_DIR

    resolved_dir = builtin_skills_dir or default_dir
    # Use configured workspace path (e.g. ~/.nanobot/workspace) for skill discovery
    from nanobot.config.loader import load_config

    workspace = load_config().workspace_path
    loader = skills_loader_cls(workspace, builtin_skills_dir=resolved_dir)

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
                "supportedProviders": _detect_supported_providers(skill_info, metadata_str),
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


def sync_nanobot_default_model(bridge: ConvexBridge) -> bool:
    """Sync config.json default model from the canonical Convex system agent."""
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

    # Resolve tier references (e.g. "tier:standard-low" → "anthropic/claude-haiku-4-5")
    if convex_model.startswith("tier:"):
        from mc.infrastructure.providers.tier_resolver import TierResolver

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
        "[gateway] Updated %s default model: %s → %s",
        NANOBOT_AGENT_NAME,
        old_model,
        convex_model,
    )
    return True


def cleanup_orphaned_tasks(bridge: ConvexBridge) -> int:
    """Delete tasks that lack a boardId (pre-production cleanup).

    boardId is now a required field on tasks. Any existing tasks without it
    are orphaned records from before the schema change and can be safely
    deleted in a pre-production environment.

    Returns the number of tasks deleted.
    """
    try:
        result = bridge.mutation("tasks:deleteOrphanedTasks", {})
        deleted = result if isinstance(result, int) else 0
        if deleted:
            logger.info("[cleanup] Deleted %d orphaned tasks without boardId", deleted)
        return deleted
    except Exception:
        logger.warning("[cleanup] Failed to delete orphaned tasks", exc_info=True)
        return 0
