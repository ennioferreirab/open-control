"""
Agent Gateway — composition root and bootstrap/lifecycle for Mission Control.

ARCHITECTURAL RULE: gateway can import services; services cannot import gateway.

This module is the composition root — it wires everything together at startup
and manages the lifecycle (start/stop) of all runtime loops.  All config
resolution, env resolution, path utilities, agent bootstrap helpers, and sync
logic live in ``mc.infrastructure``.

Internal modules should import from ``mc.infrastructure`` (config, agent_bootstrap)
or accept dependencies via constructor injection / function parameters.
Only the entry point (boot.py or __main__) and integration tests should import
from this module.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Re-export AgentGateway from crash_handler for backward compatibility
from mc.contexts.execution.crash_recovery import MAX_AUTO_RETRIES, AgentGateway  # noqa: F401
from mc.infrastructure.agent_bootstrap import (  # noqa: F401
    _NANOBOT_AGENT_CONFIG,
    NANOBOT_AGENT_NAME,
    _cleanup_deleted_agents,
    _distribute_builtin_skills,
    _fetch_bot_identity,
    _restore_archived_files,
    _sync_embedding_model,
    _sync_model_tiers,
    _write_back_convex_agents,
    ensure_low_agent,
    ensure_nanobot_agent,
    sync_agent_registry,
    sync_nanobot_default_model,
    sync_skills,
)

# Re-export from infrastructure so the runtime gateway remains the canonical
# process entrypoint and composition root for bootstrap helpers.
from mc.infrastructure.config import (  # noqa: F401
    AGENTS_DIR,
    _config_default_model,
    _parse_utc_timestamp,
    _read_file_or_none,
    _read_session_data,
    _resolve_admin_key,
    _resolve_convex_url,
    filter_agent_fields,
)
from mc.runtime.cron_delivery import build_on_task_completed_callback
from mc.runtime.interactive import build_interactive_runtime
from mc.runtime.orchestrator import TaskOrchestrator
from mc.runtime.polling_settings import _read_polling_settings
from mc.runtime.task_requeue import on_cron_job
from mc.runtime.timeout_checker import TimeoutChecker

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge
    from mc.contexts.planning.supervisor import PlanNegotiationSupervisor

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Plan negotiation manager
# ---------------------------------------------------------------------------

# Plan negotiation supervisor instance — created at gateway level for cron integration.
# The _cron_requeued_ids set is now managed by PlanNegotiationSupervisor.
_plan_negotiation_supervisor: "PlanNegotiationSupervisor | None" = None


async def _run_plan_negotiation_manager(
    bridge: "ConvexBridge",
    ask_user_registry: "Any | None" = None,
    sleep_controller: "Any | None" = None,
) -> None:
    """Manage per-task plan negotiation loops.

    Thin wrapper that delegates to PlanNegotiationSupervisor (Story 17.2).
    """
    from mc.contexts.planning.supervisor import PlanNegotiationSupervisor

    global _plan_negotiation_supervisor
    _plan_negotiation_supervisor = PlanNegotiationSupervisor(
        bridge=bridge,
        ask_user_registry=ask_user_registry,
        sleep_controller=sleep_controller,
    )
    await _plan_negotiation_supervisor.run()


# ---------------------------------------------------------------------------
# run_gateway — main runtime loop
# ---------------------------------------------------------------------------


async def run_gateway(bridge: "ConvexBridge") -> None:
    """Gateway main loop — starts orchestrator, executor, timeout checker, and cron service.

    Args:
        bridge: ConvexBridge instance used by all components.
    """
    from nanobot.config.loader import load_config
    from nanobot.cron.service import CronService

    from mc.contexts.execution.executor import TaskExecutor

    logger.info("[gateway] Agent Gateway started")

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    config = load_config()

    # Lightweight delivery: dict tracks pending cron deliveries, callback sends after completion
    pending_deliveries: dict[str, tuple[str, str]] = {}  # task_id → (channel, to)
    on_task_completed = build_on_task_completed_callback(config, pending_deliveries)

    # Cron service — when a job fires, create a task in Convex (enters normal MC flow)
    cron_store_path = Path.home() / ".nanobot" / "cron" / "jobs.json"
    cron = CronService(cron_store_path)

    async def _handle_cron_job(job: Any) -> str | None:
        return await on_cron_job(
            bridge,
            job,
            pending_deliveries=pending_deliveries,
            plan_negotiation_supervisor=_plan_negotiation_supervisor,
        )

    cron.on_job = _handle_cron_job
    await cron.start()
    cron_status = cron.status()
    if cron_status["jobs"] > 0:
        logger.info("[gateway] Cron service started with %d job(s)", cron_status["jobs"])

    # Ask-user reply routing — registry + watcher (CC agents only)
    from mc.contexts.conversation.ask_user.registry import AskUserRegistry
    from mc.contexts.conversation.ask_user.watcher import AskUserReplyWatcher
    from mc.runtime.sleep_controller import RuntimeSleepController

    # Read configurable polling/sleep intervals from Convex settings
    polling_cfg = _read_polling_settings(bridge)
    logger.info("[gateway] Polling config: %s", polling_cfg)

    ask_user_registry = AskUserRegistry()
    sleep_controller = RuntimeSleepController(
        bridge,
        active_poll_interval_seconds=polling_cfg["gateway_active_poll_seconds"],
        sleep_poll_interval_seconds=polling_cfg["gateway_sleep_poll_seconds"],
        auto_sleep_after_seconds=polling_cfg["gateway_auto_sleep_seconds"],
    )
    await sleep_controller.initialize()

    # Create RuntimeContext — single source of runtime dependencies (Story 20.3)
    from mc.infrastructure.runtime_context import RuntimeContext

    runtime_ctx = RuntimeContext(
        bridge=bridge,
        agents_dir=AGENTS_DIR,
        admin_key=os.environ.get("CONVEX_ADMIN_KEY", ""),
        admin_url=os.environ.get("CONVEX_URL", ""),
    )
    interactive_runtime = build_interactive_runtime(
        bridge,
        cron_service=cron,
    )
    runtime_ctx.services["interactive_runtime"] = interactive_runtime
    runtime_ctx.services["interactive_session_service"] = interactive_runtime.service
    runtime_ctx.services["interactive_session_coordinator"] = interactive_runtime.service
    runtime_ctx.services["interactive_socket_transport"] = interactive_runtime.transport
    runtime_ctx.services["interactive_execution_supervisor"] = interactive_runtime.supervisor
    await interactive_runtime.server.start()

    orchestrator = TaskOrchestrator(
        runtime_ctx,
        cron_service=cron,
        ask_user_registry=ask_user_registry,
        sleep_controller=sleep_controller,
    )

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

    executor = TaskExecutor(
        bridge,
        cron_service=cron,
        on_task_completed=on_task_completed,
        ask_user_registry=ask_user_registry,
        sleep_controller=sleep_controller,
    )
    execution_task = asyncio.create_task(executor.start_execution_loop())

    timeout_checker = TimeoutChecker(
        bridge,
        sleep_controller=sleep_controller,
        check_interval_seconds=polling_cfg["timeout_check_seconds"],
    )
    timeout_task = asyncio.create_task(timeout_checker.start())

    # Plan negotiation manager — spawns per-task loops for review/in_progress tasks
    plan_negotiation_task = asyncio.create_task(
        _run_plan_negotiation_manager(
            bridge,
            ask_user_registry=ask_user_registry,
            sleep_controller=sleep_controller,
        )
    )

    # Unified ConversationService — routes all thread messages through a
    # single pipeline (intent classification → dispatch).  Story 20.2.
    from mc.contexts.conversation.service import ConversationService

    conversation_service = ConversationService(bridge=bridge, ask_user_registry=ask_user_registry)

    # Chat handler — polls for pending direct-chat messages (Story 10.2)
    from mc.contexts.conversation.chat_handler import ChatHandler

    chat_handler = ChatHandler(
        bridge,
        ask_user_registry=ask_user_registry,
        sleep_controller=sleep_controller,
        active_poll_interval_seconds=polling_cfg["chat_active_poll_seconds"],
        sleep_poll_interval_seconds=polling_cfg["chat_sleep_poll_seconds"],
    )
    chat_task = asyncio.create_task(chat_handler.run())

    # Mention watcher — detects @agent-name mentions in all task threads
    # (covers tasks not handled by plan_negotiator: done, crashed, inbox, etc.)
    # Routes through ConversationService for unified intent classification.
    from mc.contexts.conversation.mentions.watcher import MentionWatcher

    mention_watcher = MentionWatcher(
        bridge,
        conversation_service=conversation_service,
        sleep_controller=sleep_controller,
        poll_interval_seconds=polling_cfg["mention_poll_seconds"],
    )
    mention_task = asyncio.create_task(mention_watcher.run())

    # Ask-user reply watcher — delivers user replies to pending ask_user calls
    # Routes through ConversationService for unified intent classification.
    ask_user_watcher = AskUserReplyWatcher(
        bridge,
        ask_user_registry,
        conversation_service=conversation_service,
        sleep_controller=sleep_controller,
    )
    ask_user_watcher_task = asyncio.create_task(ask_user_watcher.run())
    sleep_control_task = asyncio.create_task(sleep_controller.watch_control())

    # Wait for shutdown signal
    await stop_event.wait()
    logger.info("[gateway] Agent Gateway stopping...")

    cron.stop()
    await interactive_runtime.server.stop()

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
    sleep_control_task.cancel()
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
        sleep_control_task,
    ):
        try:
            await task
        except asyncio.CancelledError:
            pass


# ---------------------------------------------------------------------------
# main — entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    """Gateway entry point — resolves Convex URL, creates bridge, syncs agents, runs gateway.

    Uses AgentSyncService (Story 17.2) for all sync operations.
    """
    from mc.bridge import ConvexBridge
    from mc.contexts.agents.sync import AgentSyncService

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
        sync_service = AgentSyncService(bridge=bridge, agents_dir=agents_dir)

        if agents_dir.is_dir():
            synced, errors = sync_service.sync_agent_registry()
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
            _builtin_dir = (
                Path(__file__).parent.parent / "vendor" / "nanobot" / "nanobot" / "skills"
            )
            _distribute_builtin_skills(_ws / "skills", _builtin_dir, MC_SKILLS_DIR)
        except Exception:
            logger.exception("[gateway] Builtin skill distribution failed")

        # Sync skills alongside agents (Story 8.2)
        try:
            skill_names = sync_service.sync_skills()
            logger.info("[gateway] Synced %d skill(s)", len(skill_names))
        except Exception:
            logger.exception("[gateway] Skills sync failed")

        # Sync connected models and seed default tiers (Story 11.1, AC4)
        try:
            sync_service.sync_model_tiers()
            logger.info("[gateway] Model tiers synced")
        except Exception:
            logger.exception("[gateway] Model tiers sync failed")
        try:
            sync_service.sync_embedding_model()
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
