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
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from mc.contexts.execution.agent_runner import (  # noqa: F401
    AgentRunResult,
    _coerce_agent_run_result,
    _make_provider,
    _run_agent_on_task,
)
from mc.contexts.execution.cc_executor import CCExecutorMixin
from mc.contexts.execution.crash_recovery import AgentGateway
from mc.contexts.execution.message_builder import build_task_message  # noqa: F401
from mc.contexts.execution.output_artifacts import (  # noqa: F401
    _collect_output_artifacts,
    _human_size,
    _relocate_invalid_memory_files,
    _snapshot_output_dir,
)
from mc.contexts.execution.provider_errors import (  # noqa: F401
    PROVIDER_ERRORS,
    _provider_error_action as _provider_error_action_impl,
)
from mc.contexts.planning.planner import TaskPlanner
from mc.types import (
    ActivityEventType,
    AuthorType,
    AgentData,
    NANOBOT_AGENT_NAME,
    LEAD_AGENT_NAME,
    LeadAgentExecutionError,
    MessageType,
    TaskStatus,
    TrustLevel,
    is_lead_agent,
    task_safe_id,
)

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)

# Strong references to fire-and-forget background tasks to prevent GC cancellation.
# See: https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
_background_tasks: set[asyncio.Task[None]] = set()
_PROVIDER_ERRORS = PROVIDER_ERRORS


def _get_iana_timezone() -> str | None:
    """Resolve IANA timezone name from system (e.g. 'America/Vancouver')."""
    from mc.infrastructure.orientation_helpers import get_iana_timezone

    return get_iana_timezone()


def build_executor_agent_roster() -> str:
    """Build a roster of available agents for injection into executor orientation.

    Reads ~/.nanobot/agents/*/config.yaml, excludes system agents and lead-agent.
    Returns formatted list for agent orientation interpolation.
    """
    from mc.infrastructure.orientation_helpers import build_agent_roster

    return build_agent_roster()


def _provider_error_action(exc: Exception) -> str:
    """Extract a user-facing action string from a provider error."""
    return _provider_error_action_impl(exc)


def _resolve_completion_status(task_data: dict[str, Any] | None) -> TaskStatus:
    """Cron-triggered runs should finish directly in done."""
    if not isinstance(task_data, dict):
        return TaskStatus.REVIEW
    if task_data.get("active_cron_job_id") or task_data.get("activeCronJobId"):
        return TaskStatus.DONE
    return TaskStatus.REVIEW


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

    def __init__(self, bridge: ConvexBridge, cron_service: Any | None = None,
                 on_task_completed: Any | None = None,
                 ask_user_registry: Any | None = None,
                 sleep_controller: Any | None = None) -> None:
        self._bridge = bridge
        self._agent_gateway = AgentGateway(bridge)
        self._known_assigned_ids: set[str] = set()
        self._cron_service = cron_service
        self._on_task_completed = on_task_completed
        self._tier_resolver: Any | None = None
        self._ask_user_registry = ask_user_registry
        self._sleep_controller = sleep_controller

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
                        task_data.get("title", ""), task_id,
                    )
                    continue
                self._known_assigned_ids.add(task_id)
                asyncio.create_task(self._pickup_task(task_data))

    async def _pickup_task(self, task_data: dict[str, Any]) -> None:
        """Transition assigned task to in_progress and start execution."""
        task_id = task_data["id"]
        title = task_data.get("title", "Untitled")
        description = task_data.get("description")
        agent_name = task_data.get("assigned_agent") or NANOBOT_AGENT_NAME
        trust_level = task_data.get("trust_level", TrustLevel.AUTONOMOUS)
        try:
            if is_lead_agent(agent_name):
                await self._handle_lead_agent_task(task_data)
                return

            # Transition to in_progress.
            # Activity event (task_started) is written by the Convex
            # tasks:updateStatus mutation — no duplicate create_activity here.
            await asyncio.to_thread(
                self._bridge.update_task_status,
                task_id,
                TaskStatus.IN_PROGRESS,
                agent_name,
                f"Agent {agent_name} started work on '{title}'",
            )

            # Write system message to task thread (messages are separate from activities)
            await asyncio.to_thread(
                self._bridge.send_message,
                task_id,
                "System",
                AuthorType.SYSTEM,
                f"Agent {agent_name} has started work on this task.",
                MessageType.SYSTEM_EVENT,
            )

            logger.info(
                "[executor] Task '%s' picked up by '%s' — now in_progress",
                title, agent_name,
            )

            await self._execute_task(
                task_id, title, description, agent_name, trust_level, task_data
            )
        finally:
            self._known_assigned_ids.discard(task_id)

    async def _handle_lead_agent_task(self, task_data: dict[str, Any]) -> None:
        """Re-route lead-agent tasks through the planner."""
        from mc.infrastructure.config import filter_agent_fields

        task_id = task_data["id"]
        title = task_data.get("title", "Untitled")
        description = task_data.get("description")

        logger.warning(
            "[executor] Lead Agent dispatch intercepted for task '%s'. "
            "Pure orchestrator invariant enforced; rerouting via planner.",
            title,
        )

        try:
            agents_data = await asyncio.to_thread(self._bridge.list_agents)
            agents = [AgentData(**filter_agent_fields(a)) for a in agents_data]
            agents = [a for a in agents if a.enabled is not False]
        except Exception:
            logger.warning(
                "[executor] Failed to list agents while rerouting lead-agent "
                "task '%s'; using planner fallback",
                title,
                exc_info=True,
            )
            agents = []

        planner = TaskPlanner(self._bridge)
        plan = await planner.plan_task(
            title=title,
            description=description,
            agents=agents,
            files=task_data.get("files") or [],
        )

        rerouted_agent = next(
            (
                step.assigned_agent
                for step in plan.steps
                if step.assigned_agent and not is_lead_agent(step.assigned_agent)
            ),
            None,
        )
        if not rerouted_agent:
            rerouted_agent = NANOBOT_AGENT_NAME
            logger.warning(
                "[executor] Lead-agent reroute produced no executable assignee; "
                "using '%s' for task '%s'",
                rerouted_agent,
                title,
            )

        await asyncio.to_thread(
            self._bridge.update_execution_plan,
            task_id,
            plan.to_dict(),
        )
        await asyncio.to_thread(
            self._bridge.update_task_status,
            task_id,
            TaskStatus.ASSIGNED,
            rerouted_agent,
            (
                f"Lead Agent dispatch intercepted for '{title}'. "
                f"Pure orchestrator invariant enforced; task re-routed to "
                f"{rerouted_agent} via planner."
            ),
        )
        await asyncio.to_thread(
            self._bridge.send_message,
            task_id,
            "System",
            AuthorType.SYSTEM,
            (
                "Lead Agent is a pure orchestrator and cannot execute tasks "
                f"directly. Task re-routed to {rerouted_agent}."
            ),
            MessageType.SYSTEM_EVENT,
        )

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
        from mc.infrastructure.config import AGENTS_DIR
        from mc.infrastructure.agents.yaml_validator import validate_agent_file

        config_file = AGENTS_DIR / agent_name / "config.yaml"
        if not config_file.exists():
            return None, None, None

        result = validate_agent_file(config_file)
        if isinstance(result, list):
            # Validation errors — use defaults
            logger.warning(
                "[executor] Agent '%s' config invalid: %s", agent_name, result
            )
            return None, None, None

        return result.prompt, result.model, result.skills

    def _load_agent_data(self, agent_name: str) -> "AgentData | None":
        """Load full AgentData from an agent's YAML config file.

        Returns the validated AgentData (including backend field) or None when
        the config file does not exist or fails validation.
        """
        from mc.infrastructure.config import AGENTS_DIR
        from mc.infrastructure.agents.yaml_validator import validate_agent_file

        config_path = AGENTS_DIR / agent_name / "config.yaml"
        if not config_path.exists():
            return None
        result = validate_agent_file(config_path)
        return result if isinstance(result, AgentData) else None

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
        user_message = (
            f"Provider error: {error_class}: {exc}\n\n"
            f"Action: {action}"
        )

        logger.error(
            "[executor] Provider error on task '%s': %s. Action: %s",
            title, exc, action,
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
        from mc.infrastructure.config import AGENTS_DIR
        from mc.infrastructure.agents.yaml_validator import validate_agent_file

        lines: list[str] = ["## Available Agents\n"]
        if not AGENTS_DIR.is_dir():
            return ""
        for agent_dir in sorted(AGENTS_DIR.iterdir()):
            if not agent_dir.is_dir():
                continue
            name = agent_dir.name
            config_path = agent_dir / "config.yaml"
            if not config_path.exists():
                continue
            result = validate_agent_file(config_path)
            if isinstance(result, list):
                # Invalid config — skip
                continue
            skill_str = ", ".join(result.skills) if result.skills else "—"
            line = f"- `{result.name}` ({result.display_name}) — {result.role}"
            line += f"\n  Skills: {skill_str}"
            lines.append(line)
        return "\n".join(lines)

    def _maybe_inject_orientation(
        self, agent_name: str, agent_prompt: str | None
    ) -> str | None:
        """Prepend global orientation for non-lead-agent MC agents."""
        from mc.infrastructure.orientation import load_orientation

        orientation = load_orientation(agent_name)
        if not orientation:
            return agent_prompt

        logger.info(
            "[executor] Global orientation injected for agent '%s'", agent_name
        )
        if agent_prompt:
            return f"{orientation}\n\n---\n\n{agent_prompt}"
        return orientation

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
        agent_prompt = req.agent_prompt
        agent_model = req.agent_model
        agent_skills = req.agent_skills
        reasoning_level = req.reasoning_level
        board_name = req.board_name
        memory_workspace = req.memory_workspace

        # Route to Claude Code backend:
        # - If agent is configured with backend: claude-code (YAML config)
        # - Or if unified pipeline detected a cc/ model prefix
        agent_data = self._load_agent_data(agent_name)
        is_cc_backend = agent_data and agent_data.backend == "claude-code"

        if agent_skills is not None:
            logger.info(
                "[executor] Agent '%s' allowed_skills=%s (only these + always-on skills visible)",
                agent_name, agent_skills,
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
                agent_name, len(description), repr(description[:300]),
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
            else:
                req.runner_type = RunnerType.NANOBOT

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
            artifacts = await asyncio.to_thread(
                _collect_output_artifacts, task_id, pre_snapshot
            )

            if req.runner_type == RunnerType.CLAUDE_CODE:
                cc_result = SimpleNamespace(
                    output=result,
                    cost_usd=execution_result.cost_usd,
                    session_id=execution_result.session_id or "",
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
                if execution_result.memory_workspace is not None:
                    self._schedule_cc_consolidation(
                        _background_tasks,
                        title,
                        task_id,
                        cc_result,
                        execution_result.memory_workspace,
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

            final_status = _resolve_completion_status(task_data)

            # Activity event (task_completed) is written by the Convex
            # tasks:updateStatus mutation — no duplicate create_activity here.
            await asyncio.to_thread(
                self._bridge.update_task_status,
                task_id,
                final_status,
                agent_name,
                f"Agent {agent_name} completed task '{title}'",
            )

            # Clear retry count on success
            self._agent_gateway.clear_retry_count(task_id)

            logger.info(
                "[executor] Task '%s' completed by '%s' → %s",
                title, agent_name, final_status,
            )

            # Write completion to global HEARTBEAT.md for the main agent (Owl) to pick up
            try:
                from filelock import FileLock
                result_snippet = (result or "Task completed.").strip()
                if len(result_snippet) > 1000:
                    result_snippet = result_snippet[:1000] + "\n...(truncated)..."

                heartbeat_content = (
                    f"\n## Mission Control Update\n\n"
                    f"The task **'{title}'** (ID: `{task_id}`) assigned to **{agent_name}** "
                    f"has finished with status: `{final_status}`.\n\n"
                    f"### Agent's Result:\n```\n{result_snippet}\n```\n\n"
                    f"Please summarize this naturally and notify the user that the task is complete.\n"
                )

                heartbeat_file = Path.home() / ".nanobot" / "workspace" / "HEARTBEAT.md"
                lock = FileLock(str(heartbeat_file) + ".lock", timeout=10)
                with lock:
                    with open(heartbeat_file, "a", encoding="utf-8") as f:
                        f.write(heartbeat_content)

                logger.info("[executor] Written task '%s' completion to global HEARTBEAT.md", title)
            except Exception as hb_exc:
                logger.warning("[executor] Failed to write to HEARTBEAT.md for task '%s': %s", title, hb_exc)

            # Deliver cron result to external channel if pending
            if self._on_task_completed:
                try:
                    await self._on_task_completed(task_id, result or "")
                except Exception:
                    logger.exception("[executor] on_task_completed failed for task '%s'", title)

        except Exception as exc:
            logger.error(
                "[executor] Agent '%s' crashed on task '%s': %s",
                agent_name, title, exc,
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
