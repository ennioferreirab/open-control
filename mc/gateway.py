"""Agent Gateway — agent registry sync, main gateway loop, and entry point.

Contains sync_agent_registry, run_gateway(), main(), and the functions that
must remain here due to test-patching constraints (ensure_nanobot_agent,
sync_nanobot_default_model, _write_back_convex_agents).

Process monitoring, crash detection, restart logic, and extracted helper
utilities live in mc.process_monitor.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import signal
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from mc.orchestrator import TaskOrchestrator
from mc.timeout_checker import TimeoutChecker
from mc.yaml_validator import validate_agent_file

# ---------------------------------------------------------------------------
# Re-exports from mc.process_monitor — these symbols were extracted but many
# call-sites still import them from mc.gateway.  Keeping them here ensures
# that ``from mc.gateway import X`` and ``patch("mc.gateway.X", ...)`` both
# continue to work without touching existing code or tests.
# ---------------------------------------------------------------------------
from mc.process_monitor import (  # noqa: F401, E402
    AgentGateway,
    MAX_AUTO_RETRIES,
    _cleanup_deleted_agents,
    _config_default_model,
    _cron_requeued_ids,
    _distribute_builtin_skills,
    _fetch_bot_identity,
    _parse_utc_timestamp,
    _read_file_or_none,
    _read_session_data,
    _resolve_admin_key,
    _resolve_convex_url,
    _restore_archived_files,
    _run_plan_negotiation_manager,
    _sync_embedding_model,
    _sync_model_tiers,
    ensure_low_agent,
    filter_agent_fields,
    sync_skills,
)

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


def _write_back_convex_agents(bridge: "ConvexBridge", agents_dir: Path) -> None:
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


def sync_agent_registry(
    bridge: "ConvexBridge",
    agents_dir: Path,
    default_model: str | None = None,
) -> tuple[list["AgentData"], dict[str, list[str]]]:
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


async def run_gateway(bridge: "ConvexBridge") -> None:
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
    pending_deliveries: dict[str, tuple[str, str]] = {}  # task_id -> (channel, to)

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
                logger.info("[gateway] Delivered cron result for task %s -> telegram:%s", task_id, to)
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
            f"\U0001f514 Cron triggered: {message}",
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
        logger.info("[gateway] Cron re-queued task %s -> assigned to %s", task_id, agent_name)
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
    from mc.mentions.watcher import MentionWatcher

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
