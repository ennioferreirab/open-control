"""AgentSyncService — agent, skills, settings, and model-tier sync.

Extracted from mc/gateway.py (Story 17.2, AC #1).
All sync logic is consolidated here so the gateway becomes a thin coordinator.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from mc.infrastructure.agents.yaml_validator import validate_agent_file

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge
    from mc.types import AgentData

logger = logging.getLogger(__name__)


# Re-export gateway helpers that are used by the service but defined externally.
# These are imported lazily or passed as dependencies to keep this module testable.

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
    """Read all .jsonl files in sessions_dir and concatenate their content."""
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


# Lazy imports to avoid circular dependencies at module level.
def ensure_nanobot_agent(agents_dir: Path) -> None:
    """Delegate to gateway.ensure_nanobot_agent."""
    from mc.infrastructure.agent_bootstrap import ensure_nanobot_agent as _impl
    _impl(agents_dir)


def ensure_low_agent(bridge: "ConvexBridge") -> None:
    """Delegate to gateway.ensure_low_agent."""
    from mc.infrastructure.agent_bootstrap import ensure_low_agent as _impl
    _impl(bridge)


def sync_skills_impl(
    bridge: "ConvexBridge",
    builtin_skills_dir: Path | None = None,
) -> list[str]:
    """Delegate to gateway.sync_skills."""
    from mc.infrastructure.agent_bootstrap import sync_skills as _impl
    return _impl(bridge, builtin_skills_dir)


def list_available_models() -> list[str]:
    """Delegate to provider_factory.list_available_models."""
    from mc.infrastructure.providers.factory import list_available_models as _impl
    return _impl()


def _config_default_model() -> str:
    """Delegate to gateway._config_default_model."""
    from mc.infrastructure.config import _config_default_model as _impl
    return _impl()


def _write_back_convex_agents(bridge: "ConvexBridge", agents_dir: Path) -> None:
    """Delegate to gateway._write_back_convex_agents."""
    from mc.infrastructure.agent_bootstrap import _write_back_convex_agents as _impl
    _impl(bridge, agents_dir)


class AgentSyncService:
    """Consolidates agent registry sync, skills sync, settings sync,
    model-tier sync, and embedding-settings sync.

    Constructor dependencies:
        bridge: ConvexBridge instance for Convex communication.
        agents_dir: Path to the local agents directory (~/.nanobot/agents).
    """

    def __init__(self, bridge: "ConvexBridge", agents_dir: Path) -> None:
        self._bridge = bridge
        self._agents_dir = agents_dir

    # ------------------------------------------------------------------
    # Agent Registry Sync
    # ------------------------------------------------------------------

    def sync_agent_registry(
        self,
        default_model: str | None = None,
    ) -> tuple[list["AgentData"], dict[str, list[str]]]:
        """Sync agent YAML files to Convex agents table.

        Write-back first (Convex -> local), then validate, resolve models,
        upsert, and deactivate removed agents.

        Returns (synced_agents, errors_by_filename).
        """
        resolved_default = default_model or _config_default_model()

        # Step 0: Ensure system agents exist
        ensure_nanobot_agent(self._agents_dir)

        try:
            ensure_low_agent(self._bridge)
        except Exception:
            logger.warning("[agent_sync] Failed to ensure low-agent", exc_info=True)

        # Step 0a: Cleanup soft-deleted agents
        self.cleanup_deleted_agents()

        # Step 0b: Write-back Convex -> local (uses module-level delegate)
        _write_back_convex_agents(self._bridge, self._agents_dir)

        # Step 1: Validate agent YAML in each subdirectory
        valid_agents: list["AgentData"] = []
        errors: dict[str, list[str]] = {}

        non_agent_roles = {"remote-terminal"}

        if self._agents_dir.is_dir():
            for child in sorted(self._agents_dir.iterdir()):
                config_file = child / "config.yaml"
                if child.is_dir() and config_file.is_file():
                    try:
                        raw = yaml.safe_load(
                            config_file.read_text(encoding="utf-8")
                        )
                        if isinstance(raw, dict) and raw.get("role") in non_agent_roles:
                            logger.debug(
                                "Skipping non-agent directory %s (role=%s)",
                                child.name,
                                raw.get("role"),
                            )
                            continue
                    except Exception:
                        pass

                    result = validate_agent_file(config_file)
                    if isinstance(result, list):
                        errors[child.name] = result
                        for msg in result:
                            logger.error(
                                "Skipping invalid agent %s: %s", child.name, msg
                            )
                    else:
                        valid_agents.append(result)

        # Step 2-3: Resolve model and sync each valid agent
        for agent in valid_agents:
            if not agent.model:
                agent.model = resolved_default
            elif "/" not in agent.model and resolved_default.endswith(
                "/" + agent.model
            ):
                agent.model = resolved_default

            try:
                self._bridge.sync_agent(agent)
                logger.info("Synced agent '%s' (%s)", agent.name, agent.role)
            except Exception:
                logger.exception("Failed to sync agent '%s'", agent.name)

        # Step 4: Deactivate agents whose YAML files were removed
        active_names = [agent.name for agent in valid_agents]
        try:
            self._bridge.deactivate_agents_except(active_names)
        except Exception:
            logger.exception("Failed to deactivate removed agents")

        return valid_agents, errors

    # ------------------------------------------------------------------
    # Deleted Agent Cleanup
    # ------------------------------------------------------------------

    def cleanup_deleted_agents(self) -> None:
        """Archive local data for soft-deleted agents, then remove their folders.

        Idempotent: if the local folder is already gone, no action is taken.
        Fail-safe: if archiving fails for an agent, its local folder is NOT deleted.
        """
        try:
            deleted_agents = self._bridge.list_deleted_agents()
        except Exception:
            logger.exception("Failed to list deleted agents for cleanup")
            return

        for agent_data in deleted_agents:
            name = agent_data.get("name")
            if not name:
                continue
            agent_dir = self._agents_dir / name
            if not agent_dir.is_dir():
                continue  # Already cleaned up

            memory = _read_file_or_none(agent_dir / "memory" / "MEMORY.md")
            history = _read_file_or_none(agent_dir / "memory" / "HISTORY.md")
            session = _read_session_data(agent_dir / "sessions")

            if memory is None and history is None and session is None:
                logger.info(
                    "No archive data for agent '%s' — skipping archive call, "
                    "proceeding to cleanup",
                    name,
                )
            else:
                try:
                    self._bridge.archive_agent_data(name, memory, history, session)
                    logger.info("Archived agent data for '%s'", name)
                except Exception:
                    logger.exception(
                        "Failed to archive agent '%s' — skipping cleanup", name
                    )
                    continue  # Don't delete if archive failed

            try:
                shutil.rmtree(agent_dir)
                logger.info(
                    "Removed local folder for deleted agent '%s'", name
                )
            except OSError:
                logger.exception(
                    "Failed to remove local folder for agent '%s' — "
                    "will retry on next sync",
                    name,
                )

    # ------------------------------------------------------------------
    # Model Tier Sync
    # ------------------------------------------------------------------

    def sync_model_tiers(self) -> None:
        """Sync connected models list and seed default tiers on startup.

        - Writes available model identifiers to ``connected_models`` setting.
        - Seeds ``model_tiers`` with defaults if the setting does not yet exist.
        - Idempotent: existing tier mappings are never overwritten.

        Story 11.1 — AC #4.
        """
        models_list = list_available_models()

        self._bridge.mutation(
            "settings:set",
            {"key": "connected_models", "value": json.dumps(models_list)},
        )

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

        existing_raw = self._bridge.query("settings:get", {"key": "model_tiers"})
        if existing_raw is None:
            self._bridge.mutation(
                "settings:set",
                {"key": "model_tiers", "value": json.dumps(default_tiers)},
            )
            logger.info("[agent_sync] Seeded default model tiers: %s", default_tiers)
        else:
            existing = json.loads(existing_raw)
            models_set = set(models_list)
            updated = dict(existing)
            changed = False
            for tier_key, default_val in default_tiers.items():
                current_val = existing.get(tier_key)
                if current_val and current_val not in models_set:
                    updated[tier_key] = default_val
                    logger.info(
                        "[agent_sync] Migrated model tier %s: %s -> %s",
                        tier_key,
                        current_val,
                        default_val,
                    )
                    changed = True
            if changed:
                self._bridge.mutation(
                    "settings:set",
                    {"key": "model_tiers", "value": json.dumps(updated)},
                )
            else:
                logger.info(
                    "[agent_sync] Model tiers up to date — no migration needed"
                )

    # ------------------------------------------------------------------
    # Embedding Model Sync
    # ------------------------------------------------------------------

    def sync_embedding_model(self) -> None:
        """Sync the embedding model setting from Convex to environment."""
        try:
            model = self._bridge.query(
                "settings:get", {"key": "memory_embedding_model"}
            )
        except Exception:
            logger.warning("[agent_sync] Failed to read memory_embedding_model setting")
            return

        if model:
            os.environ["NANOBOT_MEMORY_EMBEDDING_MODEL"] = model
            logger.info("[agent_sync] Memory embedding model set: %s", model)
        else:
            os.environ.pop("NANOBOT_MEMORY_EMBEDDING_MODEL", None)
            logger.info("[agent_sync] Memory embedding model cleared (FTS-only)")

        # Persist to memory_settings.json
        try:
            settings_path = Path.home() / ".nanobot" / "memory_settings.json"
            existing: dict = {}
            if settings_path.exists():
                existing = json.loads(
                    settings_path.read_text(encoding="utf-8")
                )
            existing["embedding_model"] = model or ""
            settings_path.write_text(
                json.dumps(existing, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            logger.debug(
                "[agent_sync] Failed to persist embedding model to memory_settings.json"
            )

    # ------------------------------------------------------------------
    # Skills Sync
    # ------------------------------------------------------------------

    def sync_skills(
        self,
        builtin_skills_dir: Path | None = None,
    ) -> list[str]:
        """Sync nanobot skills to Convex.

        Returns list of synced skill names.
        """
        return sync_skills_impl(self._bridge, builtin_skills_dir)
