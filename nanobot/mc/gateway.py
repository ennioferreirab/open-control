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
import signal
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nanobot.mc.orchestrator import TaskOrchestrator
from nanobot.mc.timeout_checker import TimeoutChecker
from nanobot.mc.yaml_validator import validate_agent_file

if TYPE_CHECKING:
    from nanobot.mc.bridge import ConvexBridge
    from nanobot.mc.types import AgentData

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


def filter_agent_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Filter a dict to only known AgentData fields.

    Convex returns extra system fields (e.g. creation_time from _creationTime)
    that are not part of the AgentData dataclass. This function strips them.
    """
    from nanobot.mc.types import AgentData

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

    # Step 0: Write-back — Convex → local for dashboard-edited agents
    _write_back_convex_agents(bridge, agents_dir)

    # Step 1: Validate agent config.yaml in each subdirectory
    valid_agents: list[AgentData] = []
    errors: dict[str, list[str]] = {}

    if agents_dir.is_dir():
        for child in sorted(agents_dir.iterdir()):
            config_file = child / "config.yaml"
            if child.is_dir() and config_file.is_file():
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
    _skills_path = Path(__file__).parent.parent / "agent" / "skills.py"
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


async def run_gateway(bridge: ConvexBridge) -> None:
    """Gateway main loop — starts orchestrator, executor, and timeout checker.

    Args:
        bridge: ConvexBridge instance used by all components.
    """
    from nanobot.mc.executor import TaskExecutor

    logger.info("[gateway] Agent Gateway started")

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    orchestrator = TaskOrchestrator(bridge)
    routing_task = asyncio.create_task(orchestrator.start_routing_loop())
    review_task = asyncio.create_task(orchestrator.start_review_routing_loop())

    executor = TaskExecutor(bridge)
    execution_task = asyncio.create_task(executor.start_execution_loop())

    timeout_checker = TimeoutChecker(bridge)
    timeout_task = asyncio.create_task(timeout_checker.start())

    # Wait for shutdown signal
    await stop_event.wait()
    logger.info("[gateway] Agent Gateway stopping...")

    # Cancel all loops gracefully
    routing_task.cancel()
    review_task.cancel()
    execution_task.cancel()
    timeout_task.cancel()
    for task in (routing_task, review_task, execution_task, timeout_task):
        try:
            await task
        except asyncio.CancelledError:
            pass


async def main() -> None:
    """Gateway entry point — resolves Convex URL, creates bridge, syncs agents, runs gateway."""
    from nanobot.mc.bridge import ConvexBridge

    convex_url = _resolve_convex_url()
    if not convex_url:
        logger.error(
            "[gateway] Cannot start: Convex URL not found. "
            "Set CONVEX_URL env var or ensure dashboard/.env.local exists."
        )
        return

    admin_key = os.environ.get("CONVEX_ADMIN_KEY")
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
