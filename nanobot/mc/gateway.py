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

from nanobot.mc.orchestrator import TaskOrchestrator
from nanobot.mc.timeout_checker import TimeoutChecker
from nanobot.mc.yaml_validator import validate_agent_file

if TYPE_CHECKING:
    from nanobot.mc.bridge import ConvexBridge
    from nanobot.mc.types import AgentData

logger = logging.getLogger(__name__)

AGENTS_DIR = Path.home() / ".nanobot" / "agents"
GENERAL_AGENT_NAME = "general-agent"
_GENERAL_AGENT_CONFIG = """\
name: general-agent
role: General-Purpose Assistant
is_system: true
prompt: |
  You are the General Agent, a versatile assistant capable of handling any task
  that doesn't require a specialist agent.

  You serve as the system fallback — when no specialist agent matches a task's
  requirements, you step in to provide a capable, thoughtful response.

  **Your strengths:**
  - Broad knowledge across many domains
  - Clear, structured communication
  - Ability to break down complex problems
  - Research, analysis, and synthesis
  - Writing, editing, and summarization
  - General problem-solving and reasoning

  **How you work:**
  - Approach each task methodically
  - Ask clarifying questions when the task is ambiguous
  - Provide structured, actionable responses
  - Be transparent about the limits of your knowledge
  - When a task would benefit from a specialist, note that in your response
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


def ensure_general_agent(agents_dir: Path) -> None:
    """Ensure the General Agent YAML definition exists on disk.

    Creates the directory and config.yaml if missing. Idempotent:
    does nothing if the file already exists (preserves user edits).
    """
    agent_dir = agents_dir / GENERAL_AGENT_NAME
    config_path = agent_dir / "config.yaml"

    if config_path.is_file():
        return

    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "memory").mkdir(exist_ok=True)
    (agent_dir / "skills").mkdir(exist_ok=True)
    config_path.write_text(_GENERAL_AGENT_CONFIG, encoding="utf-8")
    logger.info("Created General Agent definition at %s", config_path)


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
    ensure_general_agent(agents_dir)

    # Step 0a: Cleanup — archive and remove local folders for soft-deleted agents
    _cleanup_deleted_agents(bridge, agents_dir)

    # Step 0b: Write-back — Convex → local for dashboard-edited agents
    _write_back_convex_agents(bridge, agents_dir)

    # Step 1: Validate agent YAML in each subdirectory
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
    """Gateway main loop — starts orchestrator, executor, timeout checker, and cron service.

    Args:
        bridge: ConvexBridge instance used by all components.
    """
    from nanobot.mc.executor import TaskExecutor
    from nanobot.cron.service import CronService
    from nanobot.cron.types import CronJob

    logger.info("[gateway] Agent Gateway started")

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    # Cron service — when a job fires, create a task in Convex (enters normal MC flow)
    cron_store_path = Path.home() / ".nanobot" / "cron" / "jobs.json"
    cron = CronService(cron_store_path)

    async def _requeue_cron_task(b: "ConvexBridge", task_id: str, message: str) -> None:
        """Re-queue an existing task for cron execution.

        Injects the cron trigger message into the task's thread so the agent
        sees it as a new user turn, then resets status to 'assigned' so the
        executor picks it up again. Skips if the task is already active.
        """
        from nanobot.mc.types import (
            AuthorType,
            MessageType,
            is_lead_agent,
        )

        try:
            task = await asyncio.to_thread(b.query, "tasks:getById", {"task_id": task_id})
        except Exception:
            logger.warning("[gateway] Could not fetch cron origin task %s — creating new task instead", task_id)
            await asyncio.to_thread(b.mutation, "tasks:create", {"title": message})
            return

        if not task:
            logger.warning("[gateway] Cron origin task %s not found — creating new task", task_id)
            await asyncio.to_thread(b.mutation, "tasks:create", {"title": message})
            return

        current_status = task.get("status", "")
        if current_status in ("in_progress", "assigned", "deleted"):
            logger.info(
                "[gateway] Cron origin task %s is '%s' — skipping re-queue",
                task_id, current_status,
            )
            return

        agent_name = task.get("assigned_agent") or GENERAL_AGENT_NAME
        if is_lead_agent(agent_name):
            logger.warning(
                "[gateway] Cron task %s had lead-agent assignment; using %s "
                "(pure orchestrator invariant)",
                task_id,
                GENERAL_AGENT_NAME,
            )
            agent_name = GENERAL_AGENT_NAME

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
        logger.info("[gateway] Cron re-queued task %s → assigned to %s", task_id, agent_name)

    async def on_cron_job(job: CronJob) -> str | None:
        """Re-queue the originating task (if linked) or create a new task when a cron job fires."""
        logger.info("[gateway] Cron job '%s' fired", job.name)
        try:
            if job.payload.task_id:
                # Re-queue the original task so history accumulates in one place
                await _requeue_cron_task(bridge, job.payload.task_id, job.payload.message)
            else:
                # No linked task — create a new task (classic cron behavior)
                await asyncio.to_thread(
                    bridge.mutation,
                    "tasks:create",
                    {"title": job.payload.message},
                )
        except Exception:
            logger.exception("[gateway] Failed to handle cron job '%s'", job.name)
        return None

    cron.on_job = on_cron_job
    await cron.start()
    cron_status = cron.status()
    if cron_status["jobs"] > 0:
        logger.info("[gateway] Cron service started with %d job(s)", cron_status["jobs"])

    orchestrator = TaskOrchestrator(bridge)
    routing_task = asyncio.create_task(orchestrator.start_routing_loop())
    review_task = asyncio.create_task(orchestrator.start_review_routing_loop())
    kickoff_task = asyncio.create_task(orchestrator.start_kickoff_watch_loop())

    executor = TaskExecutor(bridge, cron_service=cron)
    execution_task = asyncio.create_task(executor.start_execution_loop())

    timeout_checker = TimeoutChecker(bridge)
    timeout_task = asyncio.create_task(timeout_checker.start())

    # Wait for shutdown signal
    await stop_event.wait()
    logger.info("[gateway] Agent Gateway stopping...")

    cron.stop()

    # Cancel all loops gracefully
    routing_task.cancel()
    review_task.cancel()
    kickoff_task.cancel()
    execution_task.cancel()
    timeout_task.cancel()
    for task in (routing_task, review_task, kickoff_task, execution_task, timeout_task):
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
