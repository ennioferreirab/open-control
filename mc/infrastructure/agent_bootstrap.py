"""
Agent bootstrap — low-agent bootstrap, agent sync, and related config logic.

Extracted from mc.gateway so that internal modules can access agent bootstrap
helpers without depending on the gateway composition root.

Contains:
- ensure_low_agent
- sync_agent_registry / sync_skills
- _sync_model_tiers / _sync_embedding_model
- _distribute_builtin_skills
- _cleanup_deleted_agents / _restore_archived_files
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from mc.infrastructure.config import (
    _config_default_model,
    _read_file_or_none,
)
from mc.infrastructure.runtime_home import get_boards_dir, get_runtime_path

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge
    from mc.types import AgentData

logger = logging.getLogger(__name__)

_SKILL_PROVIDER_ORDER = ("claude-code", "codex")


def _parse_skill_metadata_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _detect_supported_providers(skill_info: dict[str, Any], metadata_str: str | None) -> list[str]:
    providers: set[str] = {"claude-code"}
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
            providers.add("claude-code")
            if (skill_dir / "agents" / "openai.yaml").exists():
                providers.add("codex")

    return [provider for provider in _SKILL_PROVIDER_ORDER if provider in providers]


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
        agent_dir: Path to the agent's local directory.
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
    Archive data is never cleared — it persists as a permanent backup.
    """
    try:
        backup = bridge.get_agent_memory_backup(agent_name)
    except Exception:
        logger.warning("Failed to fetch memory backup for agent '%s'", agent_name, exc_info=True)
        return

    if not backup:
        return

    boards_root = get_boards_dir()
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

    if restored_count:
        logger.info(
            "Restored memory for agent '%s' from backup (%d items)", agent_name, restored_count
        )


def _backup_agent_memory(bridge: ConvexBridge, agents_dir: Path) -> int:
    """Back up all agent memory to Convex.

    Scans board workspaces for MEMORY.md and HISTORY.md.

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
            # Collect per-board memory
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
                logger.info("Backed up memory for agent '%s' (%d boards)", name, len(boards_data))
        except Exception:
            logger.exception("Failed to backup memory for agent '%s'", name)

    return backed_up


def _cleanup_deleted_agents(bridge: ConvexBridge, agents_dir: Path) -> None:
    """Archive local data for soft-deleted agents (board-scoped + global), then remove their folders.

    For each deleted agent that still has a local folder:
    1. Scan board workspaces for per-board MEMORY.md and HISTORY.md.
    2. Read global agent memory.
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

        # Collect global agent memory
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


def _sync_model_tiers(bridge: ConvexBridge) -> None:
    """Sync connected models list and seed default tiers on startup.

    - Writes available model identifiers to ``connected_models`` setting.
    - Seeds ``model_tiers`` with defaults if the setting does not yet exist.
    - Idempotent: existing tier mappings are never overwritten.

    Story 11.1 — AC #4.
    """
    # Collect available models from provider config
    from mc.infrastructure.providers.model_listing import list_available_models

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
        os.environ["OPEN_CONTROL_MEMORY_EMBEDDING_MODEL"] = model
        logger.info("[gateway] Memory embedding model set: %s", model)
    else:
        os.environ.pop("OPEN_CONTROL_MEMORY_EMBEDDING_MODEL", None)
        logger.info("[gateway] Memory embedding model cleared (FTS-only)")

    # Persist to memory_settings.json for external consumers
    try:
        settings_path = get_runtime_path("memory_settings.json")
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

    # Ensure low-agent system agent exists in Convex
    try:
        ensure_low_agent(bridge)
    except Exception:
        logger.warning("[gateway] Failed to ensure low-agent", exc_info=True)

    # Step 0a: Cleanup — archive and remove local folders for soft-deleted agents
    _cleanup_deleted_agents(bridge, agents_dir)

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
    """Sync skills to Convex via SkillsLoader public API.

    Returns list of synced skill names.
    """
    from mc.infrastructure.skills_loader import BUILTIN_SKILLS_DIR, SkillsLoader

    resolved_dir = builtin_skills_dir or BUILTIN_SKILLS_DIR
    # Use configured workspace path (e.g. ~/.open-control/workspace) for skill discovery
    from mc.infrastructure.config import load_config

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
