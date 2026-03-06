"""
Agent Gateway — connects nanobot agents to Convex via the bridge.

Contains the run_gateway main loop that starts the orchestrator, executor,
timeout checker, and cron service.

Also contains the AgentGateway class that monitors agent processes for
crashes and implements auto-retry logic (FR37, FR38, NFR10).

Agent sync logic (sync_agent_registry, sync_nanobot_default_model, etc.)
has been extracted to mc.agent_sync.
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

from mc.orchestrator import TaskOrchestrator
from mc.timeout_checker import TimeoutChecker

# Re-exports from mc.agent_sync — these symbols were extracted but many
# call-sites and test patches still reference mc.gateway.X
from mc.agent_sync import (  # noqa: F401
    NANOBOT_AGENT_NAME,
    _NANOBOT_AGENT_CONFIG,
    _cleanup_deleted_agents,
    _config_default_model,
    _fetch_bot_identity,
    _parse_utc_timestamp,
    _read_file_or_none,
    _read_session_data,
    _restore_archived_files,
    _write_back_convex_agents,
    ensure_low_agent,
    ensure_nanobot_agent,
    sync_agent_registry,
    sync_nanobot_default_model,
)

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge
    from mc.types import AgentData

logger = logging.getLogger(__name__)

AGENTS_DIR = Path.home() / ".nanobot" / "agents"


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


def _sync_embedding_model(bridge) -> None:
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
        import json
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


def _distribute_builtin_skills(
    workspace_skills_dir: Path, *source_dirs: Path
) -> None:
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
            logger.debug(
                "Skipping missing builtin skills source: %s", source_dir
            )
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
            logger.info(
                "Distributed builtin skill '%s' to workspace", entry.name
            )


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


async def _run_plan_negotiation_manager(bridge: "ConvexBridge", ask_user_registry: "Any | None" = None) -> None:
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
                await start_plan_negotiation_loop(bridge, task_id, ask_user_registry=ask_user_registry)
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

    # Ask-user reply routing — registry + watcher (CC agents only)
    from mc.ask_user_registry import AskUserRegistry
    from mc.ask_user_watcher import AskUserReplyWatcher

    ask_user_registry = AskUserRegistry()

    orchestrator = TaskOrchestrator(bridge, cron_service=cron,
                                     ask_user_registry=ask_user_registry)

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

    executor = TaskExecutor(bridge, cron_service=cron, on_task_completed=on_task_completed,
                            ask_user_registry=ask_user_registry)
    execution_task = asyncio.create_task(executor.start_execution_loop())

    timeout_checker = TimeoutChecker(bridge)
    timeout_task = asyncio.create_task(timeout_checker.start())

    # Plan negotiation manager — spawns per-task loops for review/in_progress tasks
    plan_negotiation_task = asyncio.create_task(
        _run_plan_negotiation_manager(bridge, ask_user_registry=ask_user_registry)
    )

    # Chat handler — polls for pending direct-chat messages (Story 10.2)
    from mc.chat_handler import ChatHandler

    chat_handler = ChatHandler(bridge, ask_user_registry=ask_user_registry)
    chat_task = asyncio.create_task(chat_handler.run())

    # Mention watcher — detects @agent-name mentions in all task threads
    # (covers tasks not handled by plan_negotiator: done, crashed, inbox, etc.)
    from mc.mention_watcher import MentionWatcher

    mention_watcher = MentionWatcher(bridge)
    mention_task = asyncio.create_task(mention_watcher.run())

    # Ask-user reply watcher — delivers user replies to pending ask_user calls
    ask_user_watcher = AskUserReplyWatcher(bridge, ask_user_registry)
    ask_user_watcher_task = asyncio.create_task(ask_user_watcher.run())

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
    ask_user_watcher_task.cancel()
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
        ask_user_watcher_task,
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

    os.environ.setdefault("CONVEX_ADMIN_KEY", admin_key)

    bridge = ConvexBridge(convex_url, admin_key)

    try:
        agents_dir = AGENTS_DIR
        if agents_dir.is_dir():
            synced, errors = sync_agent_registry(bridge, agents_dir)
            logger.info("[gateway] Synced %d agent(s)", len(synced))
            for filename, errs in errors.items():
                for err in errs:
                    logger.warning("[gateway] Agent sync error (%s): %s", filename, err)

        try:
            updated = sync_nanobot_default_model(bridge)
            if updated:
                logger.info("[gateway] Nanobot default model synced from Convex")
        except Exception:
            logger.exception("[gateway] Nanobot model sync failed")

        # Distribute builtin skills to workspace before sync (Story SK.1)
        try:
            from nanobot.config.loader import load_config as _lc
            from mc.skills import MC_SKILLS_DIR
            _ws = _lc().workspace_path
            _builtin_dir = Path(__file__).parent.parent / "vendor" / "nanobot" / "nanobot" / "skills"
            _distribute_builtin_skills(_ws / "skills", _builtin_dir, MC_SKILLS_DIR)
        except Exception:
            logger.exception("[gateway] Builtin skill distribution failed")

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
        try:
            _sync_embedding_model(bridge)
        except Exception:
            logger.exception("[gateway] Embedding model sync failed")

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
