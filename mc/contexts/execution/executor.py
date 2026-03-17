"""
Task Executor — picks up assigned tasks and runs agent work.

Extracted from orchestrator.py per NFR21 (500-line module limit).
Subscribes to assigned tasks, transitions them to in_progress,
runs the nanobot agent loop, and handles completion/crash.

Implements AC #3 (assigned → in_progress), AC #4 (task execution and
completion), and AC #8 (dual logging via activity events).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from mc.application.execution.completion_status import (
    resolve_completion_review_phase,
    resolve_completion_status,
)
from mc.application.execution.interactive_mode import resolve_task_runner_type
from mc.bridge.runtime_claims import acquire_runtime_claim, task_snapshot_claim_kind
from mc.contexts.execution.agent_runner import (  # noqa: F401
    AgentRunResult,
    _coerce_agent_run_result,
    _make_provider,
    _run_agent_on_task,
)
from mc.contexts.execution.cc_executor import CCExecutorMixin
from mc.contexts.execution.completion_reporting import append_task_completion_heartbeat
from mc.contexts.execution.crash_recovery import AgentGateway
from mc.contexts.execution.executor_agent_config import (
    build_executor_agent_roster as _build_executor_agent_roster_impl,
)
from mc.contexts.execution.executor_agent_config import (
    get_iana_timezone as _get_iana_timezone_impl,
)
from mc.contexts.execution.executor_agent_config import (
    load_agent_config as _load_agent_config_impl,
)
from mc.contexts.execution.executor_agent_config import (
    load_agent_data as _load_agent_data_impl,
)
from mc.contexts.execution.executor_agent_config import (
    maybe_inject_orientation as _maybe_inject_orientation_impl,
)
from mc.contexts.execution.executor_agent_config import (
    render_agent_roster as _render_agent_roster_impl,
)
from mc.contexts.execution.executor_routing import (
    pickup_task as _pickup_task_impl,
)
from mc.contexts.execution.executor_routing import (
    reroute_lead_agent_task as _reroute_lead_agent_task_impl,
)
from mc.contexts.execution.message_builder import build_task_message  # noqa: F401
from mc.contexts.execution.output_artifacts import (  # noqa: F401
    _collect_output_artifacts,
    _human_size,
    _relocate_invalid_memory_files,
    _snapshot_output_dir,
)
from mc.contexts.execution.provider_errors import (
    PROVIDER_ERRORS,
)
from mc.contexts.execution.provider_errors import (
    _provider_error_action as _provider_error_action_impl,
)
from mc.contexts.planning.planner import TaskPlanner
from mc.types import (
    LEAD_AGENT_NAME,
    ActivityEventType,
    AgentData,
    AuthorType,
    CCTaskResult,
    LeadAgentExecutionError,
    MessageType,
    TaskStatus,
    is_lead_agent,
)

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)


async def _transition_completion(
    bridge: Any,
    *,
    task_id: str,
    task_data: dict[str, Any] | None,
    title: str,
    agent_name: str,
) -> tuple[Any, str, dict[str, Any] | None]:
    snapshot: dict[str, Any] | None = await asyncio.to_thread(bridge.get_task, task_id)
    if not isinstance(snapshot, dict):
        snapshot = task_data or None
    snapshot_for_status = {
        "id": task_id,
        "status": TaskStatus.IN_PROGRESS,
        "state_version": 0,
        **(task_data or {}),
        **(snapshot or {}),
    }
    final_status = resolve_completion_status(snapshot_for_status)
    result = await asyncio.to_thread(
        bridge.transition_task_from_snapshot,
        snapshot_for_status,
        final_status,
        reason=f"Agent {agent_name} completed task '{title}'",
        agent_name=agent_name,
        review_phase=resolve_completion_review_phase(snapshot_for_status),
    )
    return result, final_status, snapshot


# Strong references to fire-and-forget background tasks to prevent GC cancellation.
# See: https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
_background_tasks: set[asyncio.Task[None]] = set()
_PROVIDER_ERRORS = PROVIDER_ERRORS


def _get_iana_timezone() -> str | None:
    """Resolve IANA timezone name from system (e.g. 'America/Vancouver')."""
    return _get_iana_timezone_impl()


def build_executor_agent_roster() -> str:
    """Build a roster of available agents for injection into executor orientation.

    Reads ~/.nanobot/agents/*/config.yaml, excludes system agents and lead-agent.
    Returns formatted list for agent orientation interpolation.
    """
    return _build_executor_agent_roster_impl()


def _provider_error_action(exc: Exception) -> str:
    """Extract a user-facing action string from a provider error."""
    return _provider_error_action_impl(exc)


def _build_thread_context(messages: list[dict[str, Any]], max_messages: int = 20) -> str:
    """Format thread messages as conversation context for the agent.

    Thin shim that delegates to ThreadContextBuilder for backward compatibility.
    Preserves legacy behavior: returns empty string if no user messages exist.

    For step-aware context with predecessor injection, use ThreadContextBuilder
    directly with predecessor_step_ids parameter.
    """
    from mc.application.execution.thread_context import ThreadContextBuilder

    return ThreadContextBuilder().build(messages, max_messages=max_messages)


def _build_tag_attributes_context(
    tags: list[str],
    attr_values: list[dict[str, Any]],
    attr_catalog: list[dict[str, Any]],
) -> str:
    """Build a context section describing tag attribute values for the agent.

    Delegates to the canonical implementation in the unified execution pipeline.
    This wrapper preserves backward compatibility for callers within executor.py.
    """
    from mc.application.execution.context_builder import build_tag_attributes_context

    return build_tag_attributes_context(tags, attr_values, attr_catalog)


class TaskExecutor(CCExecutorMixin):
    """Picks up assigned tasks and runs agent execution."""

    def __init__(
        self,
        bridge: ConvexBridge,
        cron_service: Any | None = None,
        on_task_completed: Any | None = None,
        ask_user_registry: Any | None = None,
        sleep_controller: Any | None = None,
        provider_cli_registry: Any | None = None,
        provider_cli_supervisor: Any | None = None,
        provider_cli_projector: Any | None = None,
        provider_cli_supervision_sink: Any | None = None,
        provider_cli_control_plane: Any | None = None,
    ) -> None:
        self._bridge = bridge
        self._agent_gateway = AgentGateway(bridge)
        self._known_assigned_ids: set[str] = set()
        self._cron_service = cron_service
        self._on_task_completed = on_task_completed
        self._tier_resolver: Any | None = None
        self._ask_user_registry = ask_user_registry
        self._sleep_controller = sleep_controller
        self._provider_cli_registry = provider_cli_registry
        self._provider_cli_supervisor = provider_cli_supervisor
        self._provider_cli_projector = provider_cli_projector
        self._provider_cli_supervision_sink = provider_cli_supervision_sink
        self._provider_cli_control_plane = provider_cli_control_plane

    def _get_tier_resolver(self) -> Any:
        """Lazily create and return a TierResolver instance."""
        if self._tier_resolver is None:
            from mc.infrastructure.providers.tier_resolver import TierResolver

            self._tier_resolver = TierResolver(self._bridge)
        return self._tier_resolver

    def _build_execution_engine(self) -> Any:
        """Build the canonical execution engine for production task execution."""
        from mc.application.execution.post_processing import build_execution_engine

        return build_execution_engine(
            bridge=self._bridge,
            cron_service=self._cron_service,
            ask_user_registry=self._ask_user_registry,
            provider_cli_registry=self._provider_cli_registry,
            provider_cli_supervisor=self._provider_cli_supervisor,
            provider_cli_projector=self._provider_cli_projector,
            provider_cli_supervision_sink=self._provider_cli_supervision_sink,
            provider_cli_control_plane=self._provider_cli_control_plane,
        )

    async def _handle_tier_error(
        self,
        task_id: str,
        title: str,
        agent_name: str,
        exc: Exception,
    ) -> None:
        """Surface tier resolution errors in the task thread and crash the task."""
        error_msg = f"Model tier resolution failed: {exc}"
        logger.error("[executor] %s (task '%s', agent '%s')", error_msg, title, agent_name)

        try:
            await asyncio.to_thread(
                self._bridge.send_message,
                task_id,
                "System",
                AuthorType.SYSTEM,
                error_msg,
                MessageType.SYSTEM_EVENT,
            )
        except Exception:
            logger.exception("[executor] Failed to write tier error message")

        try:
            await asyncio.to_thread(
                self._bridge.create_activity,
                ActivityEventType.SYSTEM_ERROR,
                f"Tier resolution failed for '{title}': {exc}",
                task_id,
                agent_name,
            )
        except Exception:
            logger.exception("[executor] Failed to create tier error activity")

        try:
            await asyncio.to_thread(
                self._bridge.update_task_status,
                task_id,
                TaskStatus.CRASHED,
                agent_name,
                f"Tier resolution failed: {exc}",
            )
        except Exception:
            logger.exception("[executor] Failed to crash task after tier error")

    async def start_execution_loop(self) -> None:
        """Subscribe to assigned tasks and execute them as they arrive.

        Uses bridge.async_subscribe() which runs the blocking Convex
        subscription in a dedicated thread and feeds updates into an
        asyncio.Queue — no event-loop blocking.
        Tasks are dispatched concurrently via asyncio.create_task() to
        satisfy NFR2 (< 5s pickup latency).
        """
        logger.info("[executor] Starting execution loop")

        queue = self._bridge.async_subscribe(
            "tasks:listByStatus",
            {"status": "assigned"},
            sleep_controller=self._sleep_controller,
        )

        while True:
            tasks = await queue.get()
            if tasks is None:
                continue
            for task_data in tasks:
                task_id = task_data.get("id")
                if not task_id or task_id in self._known_assigned_ids:
                    continue
                # Skip manual tasks — user-managed, no agent execution
                if task_data.get("is_manual"):
                    logger.info(
                        "[executor] Skipping manual task '%s' (%s)",
                        task_data.get("title", ""),
                        task_id,
                    )
                    continue
                claimed = await asyncio.to_thread(
                    acquire_runtime_claim,
                    self._bridge,
                    claim_kind=task_snapshot_claim_kind("executor", task_data),
                    entity_type="task",
                    entity_id=task_id,
                    metadata={"status": task_data.get("status", "assigned")},
                )
                if not claimed:
                    logger.debug("[executor] Claim denied for task %s", task_id)
                    continue
                self._known_assigned_ids.add(task_id)
                asyncio.create_task(self._pickup_task(task_data))  # noqa: RUF006

    async def _pickup_task(self, task_data: dict[str, Any]) -> None:
        """Transition assigned task to in_progress and start execution."""
        await _pickup_task_impl(self, task_data, planner_cls=TaskPlanner)

    async def _handle_lead_agent_task(self, task_data: dict[str, Any]) -> None:
        """Re-route lead-agent tasks through the planner."""
        await _reroute_lead_agent_task_impl(self._bridge, task_data, planner_cls=TaskPlanner)

    def _load_agent_config(
        self, agent_name: str
    ) -> tuple[str | None, str | None, list[str] | None]:
        """Load prompt, model, and skills from the agent's YAML config file.

        Returns:
            Tuple of (prompt, model, skills). prompt/model may be None if not
            configured; skills is None when no config exists (meaning "no
            filtering"), or the actual list from config (possibly empty,
            meaning "only always-on skills").
        """
        return _load_agent_config_impl(agent_name)

    def _load_agent_data(self, agent_name: str) -> AgentData | None:
        """Load full AgentData from an agent's YAML config file.

        Returns the validated AgentData (including backend field) or None when
        the config file does not exist or fails validation.
        """
        return _load_agent_data_impl(agent_name)

    async def _handle_provider_error(
        self,
        task_id: str,
        title: str,
        agent_name: str,
        exc: Exception,
    ) -> None:
        """Surface provider/OAuth errors prominently.

        Instead of burying the error through generic crash handling, this
        writes a clear system message with the actionable command the user
        needs to run, AND creates a system_error activity event so it
        shows up in the dashboard activity feed.
        """
        action = _provider_error_action(exc)
        error_class = type(exc).__name__
        user_message = f"Provider error: {error_class}: {exc}\n\nAction: {action}"

        logger.error(
            "[executor] Provider error on task '%s': %s. Action: %s",
            title,
            exc,
            action,
        )

        # Write system message to task thread with clear instructions
        try:
            await asyncio.to_thread(
                self._bridge.send_message,
                task_id,
                "System",
                AuthorType.SYSTEM,
                user_message,
                MessageType.SYSTEM_EVENT,
            )
        except Exception:
            logger.exception("[executor] Failed to write provider error message")

        # Create system_error activity event for the dashboard feed
        try:
            await asyncio.to_thread(
                self._bridge.create_activity,
                ActivityEventType.SYSTEM_ERROR,
                f"Provider error on '{title}': {error_class}. {action}",
                task_id,
                agent_name,
            )
        except Exception:
            logger.exception("[executor] Failed to create provider error activity")

        # Transition task to crashed (provider errors should not auto-retry)
        try:
            await asyncio.to_thread(
                self._bridge.update_task_status,
                task_id,
                TaskStatus.CRASHED,
                agent_name,
                f"Provider error: {error_class}",
            )
        except Exception:
            logger.exception("[executor] Failed to crash task after provider error")

    def _build_agent_roster(self) -> str:
        """Build a markdown roster of all available agents from AGENTS_DIR.

        Reads ~/.nanobot/agents/ and for each agent reads config.yaml to
        extract name, display_name, role, and skills. Returns a formatted
        string suitable for injection into the lead-agent context.
        """
        return _render_agent_roster_impl()

    def _maybe_inject_orientation(self, agent_name: str, agent_prompt: str | None) -> str | None:
        """Prepend global orientation for non-lead-agent MC agents."""
        return _maybe_inject_orientation_impl(agent_name, agent_prompt)

    async def _execute_task(
        self,
        task_id: str,
        title: str,
        description: str | None,
        agent_name: str,
        trust_level: str,
        task_data: dict[str, Any] | None = None,
        step_id: str | None = None,
    ) -> None:
        """Run the agent on the task and handle completion or crash."""
        if is_lead_agent(agent_name):
            raise LeadAgentExecutionError(
                "INVARIANT VIOLATION: Lead Agent "
                f"'{LEAD_AGENT_NAME}' must never enter the execution pipeline. "
                "This is a bug - the _pickup_task guard should have intercepted "
                "this dispatch."
            )

        # ── Unified context pipeline (Story 16.1) ─────────────────────────
        # Delegate all context building to the shared ContextBuilder.
        from mc.application.execution.context_builder import ContextBuilder

        try:
            ctx_builder = ContextBuilder(self._bridge)
            ctx_builder._tier_resolver = self._tier_resolver  # share resolver
            req = await ctx_builder.build_task_context(
                task_id=task_id,
                title=title,
                description=description,
                agent_name=agent_name,
                trust_level=trust_level,
                task_data=task_data,
            )
        except ValueError as exc:
            # Tier resolution error
            await self._handle_tier_error(task_id, title, agent_name, exc)
            return

        # Unpack unified request into local variables
        description = req.description
        agent_model = req.agent_model
        agent_skills = req.agent_skills

        # Route to Claude Code backend:
        # - If agent is configured with backend: claude-code (YAML config)
        # - Or if unified pipeline detected a cc/ model prefix
        agent_data = self._load_agent_data(agent_name)
        is_cc_backend = agent_data and agent_data.backend == "claude-code"

        if agent_skills is not None:
            logger.info(
                "[executor] Agent '%s' allowed_skills=%s (only these + always-on skills visible)",
                agent_name,
                agent_skills,
            )
        else:
            logger.info(
                "[executor] Agent '%s' has no skills filter (all skills visible)",
                agent_name,
            )

        # Snapshot the output directory before agent execution so we can detect
        # created/modified files afterwards (Story 2.5).
        pre_snapshot = await asyncio.to_thread(_snapshot_output_dir, task_id)

        # Log the full task description being sent to the agent for debugging
        if description:
            logger.info(
                "[executor] Task description for '%s' (len=%d, first 300 chars): %s",
                agent_name,
                len(description),
                repr(description[:300]),
            )

        try:
            from mc.application.execution.request import (
                ErrorCategory,
                RunnerType,
            )

            if req.is_cc or is_cc_backend:
                req.runner_type = RunnerType.CLAUDE_CODE
                if agent_data is None:
                    cc_model_name = req.model if req.is_cc else agent_model
                    agent_data = AgentData(
                        name=agent_name,
                        display_name=agent_name,
                        role="agent",
                        model=cc_model_name,
                        backend="claude-code",
                    )
                else:
                    agent_data.backend = "claude-code"
                    if req.is_cc and req.model:
                        agent_data.model = req.model
                req.agent = agent_data
                req.is_cc = True
                req.runner_type = resolve_task_runner_type(req)
            else:
                req.runner_type = RunnerType.NANOBOT

            req.session_boundary_reason = "task_completion"
            engine = self._build_execution_engine()
            execution_result = await engine.run(req)

            if not execution_result.success:
                if execution_result.error_category == ErrorCategory.PROVIDER:
                    provider_exc = execution_result.error_exception or RuntimeError(
                        execution_result.error_message or "Provider error"
                    )
                    await self._handle_provider_error(task_id, title, agent_name, provider_exc)
                elif req.runner_type == RunnerType.CLAUDE_CODE:
                    try:
                        await asyncio.to_thread(
                            self._bridge.sync_task_output_files,
                            task_id,
                            task_data or {},
                            agent_name,
                        )
                    except Exception:
                        logger.warning(
                            "[executor] CC: output sync failed for errored task '%s'",
                            title,
                            exc_info=True,
                        )
                    await self._crash_task(
                        task_id,
                        title,
                        execution_result.error_message or "Claude Code execution failed",
                        agent_name,
                    )
                else:
                    crash_exc = execution_result.error_exception or RuntimeError(
                        execution_result.error_message or "Execution failed"
                    )
                    logger.error(
                        "[executor] Agent '%s' crashed on task '%s': %s",
                        agent_name,
                        title,
                        crash_exc,
                    )
                    await self._agent_gateway.handle_agent_crash(
                        agent_name,
                        task_id,
                        crash_exc,
                    )
                if self._on_task_completed:
                    try:
                        await self._on_task_completed(task_id, "")
                    except Exception:
                        pass
                return

            result = execution_result.output

            # Collect file artifacts produced during agent execution.
            artifacts = await asyncio.to_thread(_collect_output_artifacts, task_id, pre_snapshot)

            if req.runner_type == RunnerType.CLAUDE_CODE:
                cc_result = CCTaskResult(
                    output=result,
                    cost_usd=execution_result.cost_usd,
                    session_id=execution_result.session_id or "",
                    usage={},
                    is_error=False,
                )
                await self._complete_cc_task(
                    task_id,
                    title,
                    agent_name,
                    cc_result,
                    trust_level=trust_level,
                )
                try:
                    if artifacts:
                        logger.info(
                            "[executor] CC: %d artifact(s) detected for task '%s'",
                            len(artifacts),
                            title,
                        )
                    await asyncio.to_thread(
                        self._bridge.sync_task_output_files,
                        task_id,
                        task_data or {},
                        agent_name,
                    )
                except Exception:
                    logger.warning(
                        "[executor] CC: artifact sync failed for '%s'",
                        title,
                        exc_info=True,
                    )
                if self._on_task_completed:
                    try:
                        await self._on_task_completed(task_id, result or "")
                    except Exception:
                        logger.exception(
                            "[executor] on_task_completed failed for CC task '%s'",
                            title,
                        )
                return

            if step_id:
                # Post structured completion message with step context (Story 2.5).
                await asyncio.to_thread(
                    self._bridge.post_step_completion,
                    task_id,
                    step_id,
                    agent_name,
                    result,
                    artifacts or None,
                )
            else:
                # Legacy path: no step context available — post plain work message.
                await asyncio.to_thread(
                    self._bridge.send_message,
                    task_id,
                    agent_name,
                    AuthorType.AGENT,
                    result,
                    MessageType.WORK,
                )

            # Sync output file manifest to Convex (best-effort, non-blocking)
            try:
                await asyncio.to_thread(
                    self._bridge.sync_task_output_files,
                    task_id,
                    task_data or {},
                    agent_name,
                )
            except Exception:
                logger.exception("[executor] Failed to sync output files for task '%s'", title)

            # Sync output files to cron parent task if applicable (best-effort)
            cron_parent_task_id = (task_data or {}).get("cron_parent_task_id")
            if cron_parent_task_id:
                try:
                    await asyncio.to_thread(
                        self._bridge.sync_output_files_to_parent,
                        task_id,
                        cron_parent_task_id,
                        agent_name,
                    )
                except Exception:
                    logger.exception(
                        "[executor] Failed to sync output files to parent task '%s'",
                        cron_parent_task_id,
                    )

            # Activity event (task_completed) is written by the Convex
            # tasks:transition mutation — no duplicate create_activity here.
            transition_result, final_status, _fresh_task = await _transition_completion(
                self._bridge,
                task_id=task_id,
                task_data=task_data,
                title=title,
                agent_name=agent_name,
            )
            if not isinstance(transition_result, dict) or transition_result.get("kind") not in {
                "applied",
                "noop",
            }:
                logger.warning(
                    "[executor] Task '%s' completion transition did not apply: %s",
                    title,
                    transition_result,
                )
                return

            # Clear retry count on success
            self._agent_gateway.clear_retry_count(task_id)

            logger.info(
                "[executor] Task '%s' completed by '%s' → %s",
                title,
                agent_name,
                final_status,
            )

            try:
                append_task_completion_heartbeat(
                    title=title,
                    task_id=task_id,
                    agent_name=agent_name,
                    final_status=final_status,
                    result=result,
                )
                logger.info("[executor] Written task '%s' completion to global HEARTBEAT.md", title)
            except Exception as hb_exc:
                logger.warning(
                    "[executor] Failed to write to HEARTBEAT.md for task '%s': %s", title, hb_exc
                )

            # Deliver cron result to external channel if pending
            if self._on_task_completed:
                try:
                    await self._on_task_completed(task_id, result or "")
                except Exception:
                    logger.exception("[executor] on_task_completed failed for task '%s'", title)

        except Exception as exc:
            logger.error(
                "[executor] Agent '%s' crashed on task '%s': %s",
                agent_name,
                title,
                exc,
            )
            await self._agent_gateway.handle_agent_crash(agent_name, task_id, exc)
            # Pop pending delivery entry to prevent dict leak (empty → skips actual send)
            if self._on_task_completed:
                try:
                    await self._on_task_completed(task_id, "")
                except Exception:
                    pass
        finally:
            # Allow re-pickup if task returns to assigned (e.g. after retry)
            self._known_assigned_ids.discard(task_id)
