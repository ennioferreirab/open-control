"""Task Executor — picks up assigned tasks and runs agent work.

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
from typing import TYPE_CHECKING, Any

from mc.gateway import AgentGateway
from mc.planner import TaskPlanner
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
    is_tier_reference,
    is_cc_model,
    extract_cc_model_name,
    task_safe_id,
)
from mc.output_enricher import (
    _human_size,
    _snapshot_output_dir,
    _collect_output_artifacts,
    _relocate_invalid_memory_files,
    _build_thread_context,
    _build_tag_attributes_context,
    _collect_provider_error_types,
    _PROVIDER_ERRORS,
    _provider_error_action,
    _make_provider,
    build_task_message,
    _get_iana_timezone,
    build_executor_agent_roster,
    _run_agent_on_task,
    _enrich_nanobot_description,
)

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)

# Strong references to fire-and-forget background tasks to prevent GC cancellation.
# See: https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
_background_tasks: set[asyncio.Task[None]] = set()


class TaskExecutor:
    """Picks up assigned tasks and runs agent execution.

    Inherits CC backend methods from CCExecutorMixin (in mc.cc_executor).
    """

    def __init__(self, bridge: ConvexBridge, cron_service: Any | None = None,
                 on_task_completed: Any | None = None,
                 ask_user_registry: Any | None = None) -> None:
        self._bridge = bridge
        self._agent_gateway = AgentGateway(bridge)
        self._known_assigned_ids: set[str] = set()
        self._cron_service = cron_service
        self._on_task_completed = on_task_completed
        self._tier_resolver: Any | None = None
        self._ask_user_registry = ask_user_registry

    def _get_tier_resolver(self) -> Any:
        """Lazily create and return a TierResolver instance."""
        if self._tier_resolver is None:
            from mc.tier_resolver import TierResolver
            self._tier_resolver = TierResolver(self._bridge)
        return self._tier_resolver

    async def _handle_tier_error(
        self, task_id: str, title: str, agent_name: str, exc: Exception,
    ) -> None:
        """Surface tier resolution errors in the task thread and crash the task."""
        error_msg = f"Model tier resolution failed: {exc}"
        logger.error("[executor] %s (task '%s', agent '%s')", error_msg, title, agent_name)
        try:
            await asyncio.to_thread(
                self._bridge.send_message, task_id, "System",
                AuthorType.SYSTEM, error_msg, MessageType.SYSTEM_EVENT,
            )
        except Exception:
            logger.exception("[executor] Failed to write tier error message")
        try:
            await asyncio.to_thread(
                self._bridge.create_activity, ActivityEventType.SYSTEM_ERROR,
                f"Tier resolution failed for '{title}': {exc}", task_id, agent_name,
            )
        except Exception:
            logger.exception("[executor] Failed to create tier error activity")
        try:
            await asyncio.to_thread(
                self._bridge.update_task_status, task_id, TaskStatus.CRASHED,
                agent_name, f"Tier resolution failed: {exc}",
            )
        except Exception:
            logger.exception("[executor] Failed to crash task after tier error")

    async def start_execution_loop(self) -> None:
        """Subscribe to assigned tasks and execute them as they arrive."""
        logger.info("[executor] Starting execution loop")
        queue = self._bridge.async_subscribe(
            "tasks:listByStatus", {"status": "assigned"}
        )
        while True:
            tasks = await queue.get()
            if tasks is None:
                continue
            for task_data in tasks:
                task_id = task_data.get("id")
                if not task_id or task_id in self._known_assigned_ids:
                    continue
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
            await asyncio.to_thread(
                self._bridge.update_task_status, task_id, TaskStatus.IN_PROGRESS,
                agent_name, f"Agent {agent_name} started work on '{title}'",
            )
            await asyncio.to_thread(
                self._bridge.send_message, task_id, "System", AuthorType.SYSTEM,
                f"Agent {agent_name} has started work on this task.",
                MessageType.SYSTEM_EVENT,
            )
            logger.info("[executor] Task '%s' picked up by '%s' — now in_progress", title, agent_name)
            await self._execute_task(task_id, title, description, agent_name, trust_level, task_data)
        finally:
            self._known_assigned_ids.discard(task_id)

    async def _handle_lead_agent_task(self, task_data: dict[str, Any]) -> None:
        """Re-route lead-agent tasks through the planner."""
        from mc.gateway import filter_agent_fields

        task_id = task_data["id"]
        title = task_data.get("title", "Untitled")
        description = task_data.get("description")
        logger.warning(
            "[executor] Lead Agent dispatch intercepted for task '%s'. "
            "Pure orchestrator invariant enforced; rerouting via planner.", title,
        )
        try:
            agents_data = await asyncio.to_thread(self._bridge.list_agents)
            agents = [AgentData(**filter_agent_fields(a)) for a in agents_data]
            agents = [a for a in agents if a.enabled is not False]
        except Exception:
            logger.warning(
                "[executor] Failed to list agents while rerouting lead-agent task '%s'; using planner fallback",
                title, exc_info=True,
            )
            agents = []
        planner = TaskPlanner(self._bridge)
        plan = await planner.plan_task(
            title=title, description=description,
            agents=agents, files=task_data.get("files") or [],
        )
        rerouted_agent = next(
            (step.assigned_agent for step in plan.steps
             if step.assigned_agent and not is_lead_agent(step.assigned_agent)),
            None,
        )
        if not rerouted_agent:
            rerouted_agent = NANOBOT_AGENT_NAME
            logger.warning(
                "[executor] Lead-agent reroute produced no executable assignee; using '%s' for task '%s'",
                rerouted_agent, title,
            )
        await asyncio.to_thread(self._bridge.update_execution_plan, task_id, plan.to_dict())
        await asyncio.to_thread(
            self._bridge.update_task_status, task_id, TaskStatus.ASSIGNED, rerouted_agent,
            f"Lead Agent dispatch intercepted for '{title}'. Pure orchestrator invariant enforced; task re-routed to {rerouted_agent} via planner.",
        )
        await asyncio.to_thread(
            self._bridge.send_message, task_id, "System", AuthorType.SYSTEM,
            f"Lead Agent is a pure orchestrator and cannot execute tasks directly. Task re-routed to {rerouted_agent}.",
            MessageType.SYSTEM_EVENT,
        )

    def _load_agent_config(self, agent_name: str) -> tuple[str | None, str | None, list[str] | None]:
        """Load prompt, model, and skills from the agent's YAML config file."""
        from mc.gateway import AGENTS_DIR
        from mc.yaml_validator import validate_agent_file

        config_file = AGENTS_DIR / agent_name / "config.yaml"
        if not config_file.exists():
            return None, None, None
        result = validate_agent_file(config_file)
        if isinstance(result, list):
            logger.warning("[executor] Agent '%s' config invalid: %s", agent_name, result)
            return None, None, None
        return result.prompt, result.model, result.skills

    def _load_agent_data(self, agent_name: str) -> "AgentData | None":
        """Load full AgentData from an agent's YAML config file."""
        from mc.gateway import AGENTS_DIR
        from mc.yaml_validator import validate_agent_file

        config_path = AGENTS_DIR / agent_name / "config.yaml"
        if not config_path.exists():
            return None
        result = validate_agent_file(config_path)
        return result if isinstance(result, AgentData) else None

    async def _handle_provider_error(
        self, task_id: str, title: str, agent_name: str, exc: Exception,
    ) -> None:
        """Surface provider/OAuth errors prominently."""
        action = _provider_error_action(exc)
        error_class = type(exc).__name__
        user_message = f"Provider error: {error_class}: {exc}\n\nAction: {action}"
        logger.error("[executor] Provider error on task '%s': %s. Action: %s", title, exc, action)
        try:
            await asyncio.to_thread(
                self._bridge.send_message, task_id, "System", AuthorType.SYSTEM,
                user_message, MessageType.SYSTEM_EVENT,
            )
        except Exception:
            logger.exception("[executor] Failed to write provider error message")
        try:
            await asyncio.to_thread(
                self._bridge.create_activity, ActivityEventType.SYSTEM_ERROR,
                f"Provider error on '{title}': {error_class}. {action}", task_id, agent_name,
            )
        except Exception:
            logger.exception("[executor] Failed to create provider error activity")
        try:
            await asyncio.to_thread(
                self._bridge.update_task_status, task_id, TaskStatus.CRASHED,
                agent_name, f"Provider error: {error_class}",
            )
        except Exception:
            logger.exception("[executor] Failed to crash task after provider error")

    def _build_agent_roster(self) -> str:
        """Build a markdown roster of all available agents from AGENTS_DIR."""
        from mc.gateway import AGENTS_DIR
        from mc.yaml_validator import validate_agent_file

        lines: list[str] = ["## Available Agents\n"]
        if not AGENTS_DIR.is_dir():
            return ""
        for agent_dir in sorted(AGENTS_DIR.iterdir()):
            if not agent_dir.is_dir():
                continue
            config_path = agent_dir / "config.yaml"
            if not config_path.exists():
                continue
            result = validate_agent_file(config_path)
            if isinstance(result, list):
                continue
            skill_str = ", ".join(result.skills) if result.skills else "—"
            line = f"- `{result.name}` ({result.display_name}) — {result.role}"
            line += f"\n  Skills: {skill_str}"
            lines.append(line)
        return "\n".join(lines)

    def _maybe_inject_orientation(self, agent_name: str, agent_prompt: str | None) -> str | None:
        """Prepend global orientation for non-lead-agent MC agents."""
        from mc.orientation import load_orientation
        orientation = load_orientation(agent_name)
        if not orientation:
            return agent_prompt
        logger.info("[executor] Global orientation injected for agent '%s'", agent_name)
        if agent_prompt:
            return f"{orientation}\n\n---\n\n{agent_prompt}"
        return orientation

    async def _execute_task(
        self, task_id: str, title: str, description: str | None,
        agent_name: str, trust_level: str,
        task_data: dict[str, Any] | None = None, step_id: str | None = None,
    ) -> None:
        """Run the agent on the task and handle completion or crash."""
        if is_lead_agent(agent_name):
            raise LeadAgentExecutionError(
                f"INVARIANT VIOLATION: Lead Agent '{LEAD_AGENT_NAME}' must never enter the execution pipeline. "
                "This is a bug - the _pickup_task guard should have intercepted this dispatch."
            )

        # Route to Claude Code backend if agent is configured with backend: claude-code
        agent_data = self._load_agent_data(agent_name)
        if agent_data and agent_data.backend == "claude-code":
            await self._execute_cc_task(
                task_id, title, description, agent_name, agent_data,
                trust_level=trust_level, task_data=task_data, needs_enrichment=True,
            )
            return

        # Enrich description with file manifest, thread context, tag attributes
        description = await _enrich_nanobot_description(
            self._bridge, task_id, title, description, task_data,
        )

        # Load agent prompt, model, and skills from YAML config
        agent_prompt, agent_model, agent_skills = self._load_agent_config(agent_name)
        logger.info(
            "[executor] Local YAML config for '%s': prompt_len=%d, model=%s, skills=%s",
            agent_name, len(agent_prompt) if agent_prompt else 0, agent_model, agent_skills,
        )

        # Convex is the source of truth for model, prompt, and variables — override YAML
        agent_prompt, agent_model, agent_skills = await self._sync_convex_agent(
            agent_name, agent_prompt, agent_model, agent_skills,
        )

        # Resolve tier references (Story 11.1, AC5)
        reasoning_level: str | None = None
        if agent_model and is_tier_reference(agent_model):
            tier_ref = agent_model
            try:
                agent_model = self._get_tier_resolver().resolve_model(agent_model)
                logger.info("[executor] Resolved tier for agent '%s': %s", agent_name, agent_model)
            except ValueError as exc:
                await self._handle_tier_error(task_id, title, agent_name, exc)
                return
            reasoning_level = self._get_tier_resolver().resolve_reasoning_level(tier_ref)
            if reasoning_level:
                logger.info("[executor] Reasoning level for agent '%s': %s", agent_name, reasoning_level)

        # Route to Claude Code backend when model starts with cc/
        if agent_model and is_cc_model(agent_model):
            cc_model_name = extract_cc_model_name(agent_model)
            if agent_data is None:
                agent_data = self._load_agent_data(agent_name)
            if agent_data is None:
                agent_data = AgentData(
                    name=agent_name, display_name=agent_name, role="agent",
                    model=cc_model_name, backend="claude-code",
                )
            else:
                agent_data.model = cc_model_name
                agent_data.backend = "claude-code"
            await self._execute_cc_task(
                task_id, title, description, agent_name, agent_data,
                trust_level=trust_level, task_data=task_data,
                reasoning_level=reasoning_level, needs_enrichment=False,
            )
            return

        # Inject global orientation for non-lead agents
        agent_prompt = self._maybe_inject_orientation(agent_name, agent_prompt)
        if agent_prompt:
            logger.info(
                "[executor] Post-orientation prompt for '%s' (len=%d, first 200 chars): %s",
                agent_name, len(agent_prompt), repr(agent_prompt[:200]),
            )

        # System agents (nanobot) use identity from SOUL.md + ContextBuilder
        if agent_name == NANOBOT_AGENT_NAME:
            agent_prompt = None
            logger.info("[executor] Cleared prompt for nanobot (uses SOUL.md + ContextBuilder)")

        if is_lead_agent(agent_name):
            roster = self._build_agent_roster()
            if roster:
                description = (description or "") + f"\n\n{roster}"
                logger.info("[executor] Injected agent roster into lead-agent context")

        if agent_skills is not None:
            logger.info("[executor] Agent '%s' allowed_skills=%s (only these + always-on skills visible)", agent_name, agent_skills)
        else:
            logger.info("[executor] Agent '%s' has no skills filter (all skills visible)", agent_name)

        # Resolve board-scoped workspace (AC6, AC7)
        board_name, memory_workspace = await self._resolve_board_workspace(
            task_data, agent_name, title,
        )

        pre_snapshot = await asyncio.to_thread(_snapshot_output_dir, task_id)

        if description:
            logger.info(
                "[executor] Task description for '%s' (len=%d, first 300 chars): %s",
                agent_name, len(description), repr(description[:300]),
            )

        try:
            result, session_key, loop = await _run_agent_on_task(
                agent_name=agent_name, agent_prompt=agent_prompt, agent_model=agent_model,
                reasoning_level=reasoning_level, task_title=title, task_description=description,
                agent_skills=agent_skills, board_name=board_name, memory_workspace=memory_workspace,
                cron_service=self._cron_service, task_id=task_id, bridge=self._bridge,
                ask_user_registry=self._ask_user_registry,
            )
            await asyncio.to_thread(_relocate_invalid_memory_files, task_id, loop.memory_workspace)
            artifacts = await asyncio.to_thread(_collect_output_artifacts, task_id, pre_snapshot)

            if step_id:
                await asyncio.to_thread(
                    self._bridge.post_step_completion, task_id, step_id, agent_name, result, artifacts or None,
                )
            else:
                await asyncio.to_thread(
                    self._bridge.send_message, task_id, agent_name, AuthorType.AGENT, result, MessageType.WORK,
                )

            try:
                await asyncio.to_thread(self._bridge.sync_task_output_files, task_id, task_data or {}, agent_name)
            except Exception:
                logger.exception("[executor] Failed to sync output files for task '%s'", title)

            cron_parent_task_id = (task_data or {}).get("cron_parent_task_id")
            if cron_parent_task_id:
                try:
                    await asyncio.to_thread(self._bridge.sync_output_files_to_parent, task_id, cron_parent_task_id, agent_name)
                except Exception:
                    logger.exception("[executor] Failed to sync output files to parent task '%s'", cron_parent_task_id)

            final_status = TaskStatus.DONE if trust_level == TrustLevel.AUTONOMOUS else TaskStatus.REVIEW
            await asyncio.to_thread(
                self._bridge.update_task_status, task_id, final_status, agent_name,
                f"Agent {agent_name} completed task '{title}'",
            )
            self._agent_gateway.clear_retry_count(task_id)
            logger.info("[executor] Task '%s' completed by '%s' → %s", title, agent_name, final_status)

            async def _post_task_consolidate():
                try:
                    await loop.end_task_session(session_key)
                    logger.info("[executor] Post-task memory consolidation done for '%s'", title)
                except Exception:
                    logger.warning("[executor] Post-task memory consolidation failed for '%s'", title, exc_info=True)

            _task = asyncio.create_task(_post_task_consolidate())
            _background_tasks.add(_task)
            _task.add_done_callback(_background_tasks.discard)

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

            if self._on_task_completed:
                try:
                    await self._on_task_completed(task_id, result or "")
                except Exception:
                    logger.exception("[executor] on_task_completed failed for task '%s'", title)

        except _PROVIDER_ERRORS as exc:
            await self._handle_provider_error(task_id, title, agent_name, exc)
            if self._on_task_completed:
                try:
                    await self._on_task_completed(task_id, "")
                except Exception:
                    pass

        except Exception as exc:
            logger.error("[executor] Agent '%s' crashed on task '%s': %s", agent_name, title, exc)
            await self._agent_gateway.handle_agent_crash(agent_name, task_id, exc)
            if self._on_task_completed:
                try:
                    await self._on_task_completed(task_id, "")
                except Exception:
                    pass
        finally:
            self._known_assigned_ids.discard(task_id)

    async def _sync_convex_agent(
        self, agent_name: str, agent_prompt: str | None,
        agent_model: str | None, agent_skills: list[str] | None,
    ) -> tuple[str | None, str | None, list[str] | None]:
        """Sync prompt, model, skills from Convex (source of truth)."""
        try:
            from mc.gateway import AGENTS_DIR
            convex_agent = await asyncio.to_thread(self._bridge.get_agent_by_name, agent_name)
            if convex_agent:
                if convex_agent.get("model"):
                    convex_model = convex_agent["model"]
                    if convex_model != agent_model:
                        logger.info("[executor] Model synced from Convex for '%s': %s -> %s", agent_name, agent_model, convex_model)
                        agent_model = convex_model
                        try:
                            await asyncio.to_thread(self._bridge.write_agent_config, convex_agent, AGENTS_DIR)
                        except Exception:
                            logger.warning("[executor] YAML write-back failed for '%s'", agent_name, exc_info=True)
                convex_prompt = convex_agent.get("prompt")
                if convex_prompt:
                    agent_prompt = convex_prompt
                variables = convex_agent.get("variables") or []
                if variables and agent_prompt:
                    for var in variables:
                        agent_prompt = agent_prompt.replace("{{" + var["name"] + "}}", var["value"])
                    logger.info("[executor] Interpolated %d variable(s) into prompt for '%s'", len(variables), agent_name)
                convex_skills = convex_agent.get("skills")
                if convex_skills is not None:
                    if convex_skills != agent_skills:
                        logger.info("[executor] Skills synced from Convex for '%s': %s -> %s", agent_name, agent_skills, convex_skills)
                    agent_skills = convex_skills
        except Exception:
            logger.warning("[executor] Could not fetch Convex agent data for '%s', using YAML", agent_name, exc_info=True)
        return agent_prompt, agent_model, agent_skills

    async def _resolve_board_workspace(
        self, task_data: dict[str, Any] | None, agent_name: str, title: str,
    ) -> tuple[str | None, Path | None]:
        """Resolve board-scoped workspace (AC6, AC7)."""
        board_name: str | None = None
        memory_workspace: Path | None = None
        board_id = (task_data or {}).get("board_id")
        if board_id:
            try:
                board = await asyncio.to_thread(self._bridge.get_board_by_id, board_id)
                if board:
                    board_name = board.get("name")
                    if board_name:
                        from mc.board_utils import resolve_board_workspace, get_agent_memory_mode
                        mode = get_agent_memory_mode(board, agent_name)
                        memory_workspace = resolve_board_workspace(board_name, agent_name, mode=mode)
                        logger.info("[executor] Board-scoped workspace for '%s' on '%s' (mode=%s)", agent_name, board_name, mode)
            except Exception:
                logger.warning("[executor] Failed to resolve board workspace for '%s'", title, exc_info=True)
        return board_name, memory_workspace


# ── Mixin injection ──────────────────────────────────────────────────────
# Dynamically inject CCExecutorMixin methods into TaskExecutor so that all
# CC-specific methods (defined in mc.cc_executor) are available as regular
# methods on TaskExecutor instances.

from mc.cc_executor import CCExecutorMixin as _CCMixin  # noqa: E402

for _name in dir(_CCMixin):
    if not _name.startswith("_CCMixin") and not _name.startswith("__"):
        _attr = getattr(_CCMixin, _name)
        if callable(_attr) or isinstance(_attr, (classmethod, staticmethod, property)):
            if not hasattr(TaskExecutor, _name):
                setattr(TaskExecutor, _name, _attr)
