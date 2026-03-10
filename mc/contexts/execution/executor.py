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
import shutil
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from mc.contexts.execution.cc_executor import CCExecutorMixin
from mc.contexts.execution.crash_recovery import AgentGateway
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


@dataclass(slots=True)
class AgentRunResult:
    content: str
    is_error: bool = False
    error_message: str | None = None


def _coerce_agent_run_result(value: Any) -> AgentRunResult:
    """Normalize old string results and structured loop results to one shape."""
    if isinstance(value, AgentRunResult):
        return value
    if isinstance(value, str):
        return AgentRunResult(content=value)
    content = getattr(value, "content", "") or ""
    is_error = bool(getattr(value, "is_error", False))
    error_message = getattr(value, "error_message", None)
    return AgentRunResult(
        content=content,
        is_error=is_error,
        error_message=error_message,
    )


def _collect_provider_error_types() -> tuple[type[Exception], ...]:
    """Collect provider-specific exception types for targeted catching.

    Returns a tuple of exception classes that represent provider/OAuth
    errors (as opposed to agent runtime errors). These are caught
    separately in _execute_task so they get surfaced with actionable
    instructions instead of being buried in generic crash handling.
    """
    from mc.infrastructure.providers.factory import ProviderError

    types: list[type[Exception]] = [ProviderError]
    try:
        from nanobot.providers.anthropic_oauth import AnthropicOAuthExpired

        types.append(AnthropicOAuthExpired)
    except ImportError:
        pass
    return tuple(types)


_PROVIDER_ERRORS = _collect_provider_error_types()


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
    """Extract a user-facing action string from a provider error.

    For ProviderError the action is explicit. For AnthropicOAuthExpired
    the message itself contains the command. Falls back to a generic hint.
    """
    from mc.infrastructure.providers.factory import ProviderError

    if isinstance(exc, ProviderError) and exc.action:
        return exc.action
    # AnthropicOAuthExpired messages include "Run: nanobot provider login ..."
    msg = str(exc)
    if "Run:" in msg:
        return msg[msg.index("Run:") :]
    return "Check provider configuration in ~/.nanobot/config.json"


def _make_provider(model: str | None = None):
    """Create the LLM provider from the user's nanobot config.

    Delegates to the shared provider_factory.create_provider() to avoid
    duplication with nanobot/cli/commands.py.
    """
    from mc.infrastructure.providers.factory import create_provider

    return create_provider(model)


def build_task_message(title: str, description: str | None) -> str:
    """Build the task message sent to the agent.

    When a description exists, uses structured XML tags so the agent
    can distinguish title from description. Otherwise, plain title
    for backward compatibility.
    """
    if description and description.strip():
        return f"<title>{title}</title>\n<description>{description}</description>"
    return title


async def _run_agent_on_task(
    agent_name: str,
    agent_prompt: str | None,
    agent_model: str | None,
    reasoning_level: str | None = None,
    task_title: str = "",
    task_description: str | None = None,
    agent_skills: list[str] | None = None,
    board_name: str | None = None,
    memory_workspace: Path | None = None,
    cron_service: Any | None = None,
    task_id: str | None = None,
    bridge: "ConvexBridge | None" = None,
    ask_user_registry: Any | None = None,
) -> tuple[str, str, "AgentLoop"]:
    """Run the nanobot agent loop on a task and return the result.

    Uses AgentLoop.process_direct() with the agent's system prompt and model.
    The task title + description become the message input.
    When board_name is provided, uses board-scoped session key and memory_workspace.
    """
    if is_lead_agent(agent_name):
        raise LeadAgentExecutionError(
            "INVARIANT VIOLATION: Lead Agent must never be passed to "
            "_run_agent_on_task(). Execution structurally blocked."
        )

    from nanobot.agent.loop import AgentLoop
    from nanobot.bus.queue import MessageBus

    workspace = Path.home() / ".nanobot" / "agents" / agent_name
    workspace.mkdir(parents=True, exist_ok=True)

    # Global workspace skills (installed via ClawHub or manually)
    global_skills_dir = Path.home() / ".nanobot" / "workspace" / "skills"

    # Build the message from task title + description (structured format)
    message = build_task_message(task_title, task_description)

    # Prefix with agent system prompt if available (ContextBuilder reads
    # bootstrap files from workspace, but the YAML prompt isn't a bootstrap
    # file — so we include it in the message content).
    if agent_prompt:
        message = f"[System instructions]\n{agent_prompt}\n\n[Task]\n{message}"

    logger.info(
        "[_run_agent_on_task] Agent '%s': workspace=%s, memory_workspace=%s",
        agent_name, workspace, memory_workspace,
    )
    logger.info(
        "[_run_agent_on_task] Agent '%s': final message len=%d, first 500 chars:\n%s",
        agent_name, len(message), repr(message[:500]),
    )

    # Board-scoped session key format (AC6); include task_id for per-task isolation
    if board_name:
        session_key = f"mc:board:{board_name}:task:{agent_name}:{task_id}" if task_id else f"mc:board:{board_name}:task:{agent_name}"
    else:
        session_key = f"mc:task:{agent_name}:{task_id}" if task_id else f"mc:task:{agent_name}"
    logger.info(
        "[_run_agent_on_task] Agent '%s': session_key='%s', board_name=%s",
        agent_name, session_key, board_name,
    )

    # Create provider from user config (respects OAuth, API keys, etc.)
    provider, resolved_model = _make_provider(agent_model)

    bus = MessageBus()
    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=workspace,
        model=resolved_model,
        reasoning_level=reasoning_level,
        allowed_skills=agent_skills,
        global_skills_dir=global_skills_dir,
        memory_workspace=memory_workspace,
        cron_service=cron_service,
        agent_name=agent_name,
        mc_consolidation_system_prompt=(
            "You are a memory consolidation agent processing MC task history. "
            "User messages may contain <title>...</title> and <description>...</description> XML tags identifying the task. "
            "Descriptions may include: file manifests (input files attached to the task), "
            "[Task Tag Attributes] (tags and their attribute key=value pairs), "
            "and ## Thread Context (prior human messages in the task thread). "
            "When writing history_entry, use this format for each task: "
            "'[YYYY-MM-DD HH:MM] Task \"<title>\": <summary>. "
            "Tags: <tag>(<attr=val>, ...). "
            "Files read: <paths>. Files written: <paths>.' "
            "Omit any field that has no data. "
            "Call the save_memory tool with your consolidation."
        ),
    )

    # Agents running MC steps should execute tasks directly, not re-delegate.
    # Remove delegate_task to prevent circular delegation loops.
    loop.tools.unregister("delegate_task")

    # Inject Telegram default chat_id into CronTool so agents running in MC
    # context can schedule cron jobs that deliver to Telegram without needing
    # to know the numeric chat_id explicitly.
    if cron_tool := loop.tools.get("cron"):
        from nanobot.agent.tools.cron import CronTool as _CronTool
        if isinstance(cron_tool, _CronTool):
            from nanobot.config.loader import load_config as _load_config
            _cfg = _load_config()
            _tg_ids = [x for x in _cfg.channels.telegram.allow_from if x.lstrip("-").isdigit()]
            if _tg_ids:
                cron_tool.set_telegram_default(_tg_ids[0])

    # Set MC context on ask_agent tool for inter-agent conversations (Story 10.3)
    if ask_tool := loop.tools.get("ask_agent"):
        from nanobot.agent.tools.ask_agent import AskAgentTool
        if isinstance(ask_tool, AskAgentTool):
            ask_tool.set_context(
                caller_agent=agent_name,
                task_id=task_id,
                depth=0,
                bridge=bridge,
            )

    # Set MC context on ask_user tool for interactive user questions
    _ask_user_cleanup: tuple[Any | None, str | None] | None = None
    if ask_user_tool := loop.tools.get("ask_user"):
        from nanobot.agent.tools.ask_user import AskUserTool
        if isinstance(ask_user_tool, AskUserTool):
            from mc.ask_user.handler import AskUserHandler

            handler = AskUserHandler()
            if ask_user_registry and task_id:
                ask_user_registry.register(task_id, handler)
            ask_user_tool.set_context(
                agent_name=agent_name,
                task_id=task_id,
                bridge=bridge,
                handler=handler,
            )
            _ask_user_cleanup = (ask_user_registry, task_id)

    try:
        result = await loop.process_direct(
            content=message,
            session_key=session_key,
            channel="mc",
            chat_id=agent_name,
            task_id=task_id,
        )
    finally:
        if _ask_user_cleanup is not None:
            reg, tid = _ask_user_cleanup
            if reg and tid:
                reg.unregister(tid)

    return result, session_key, loop


def _human_size(b: int) -> str:
    """Convert a byte count to a human-readable size string."""
    if b < 1024 * 1024:
        return f"{b // 1024} KB"
    return f"{b / (1024 * 1024):.1f} MB"


def _snapshot_output_dir(task_id: str) -> dict[str, float]:
    """Capture {relative_path: mtime} for all files in the task's output dir.

    The relative path is relative to the task base directory (two levels above
    the file), e.g. ``"output/report.pdf"`` for a file stored in
    ``~/.nanobot/tasks/{safe_id}/output/report.pdf``.
    """
    safe_id = task_safe_id(task_id)
    output_dir = Path.home() / ".nanobot" / "tasks" / safe_id / "output"
    snapshot: dict[str, float] = {}
    if output_dir.exists():
        for entry in output_dir.rglob("*"):
            if entry.is_file():
                # relative to task base dir (one level above output/)
                rel = str(entry.relative_to(output_dir.parent))
                snapshot[rel] = entry.stat().st_mtime
    return snapshot


def _collect_output_artifacts(
    task_id: str,
    pre_snapshot: dict[str, float] | None,
) -> list[dict[str, Any]]:
    """Compare post-execution output dir against pre-snapshot to detect artifacts.

    Returns a list of artifact dicts (Convex-compatible) describing files
    that were created or modified during agent execution.

    Each dict has keys: ``path``, ``action``, and optionally ``description``
    (for created files) or ``diff`` (for modified files).

    The ``path`` is relative to the task base directory (e.g., ``"output/report.pdf"``).
    """
    safe_id = task_safe_id(task_id)
    output_dir = Path.home() / ".nanobot" / "tasks" / safe_id / "output"
    artifacts: list[dict[str, Any]] = []
    pre = pre_snapshot or {}

    if not output_dir.exists():
        return artifacts

    for entry in output_dir.rglob("*"):
        if not entry.is_file():
            continue
        # relative to task base dir (parent of output/)
        rel = str(entry.relative_to(output_dir.parent))
        size = entry.stat().st_size

        if rel not in pre:
            # New file — created
            ext = entry.suffix.lstrip(".").upper() or "file"
            artifacts.append({
                "path": rel,
                "action": "created",
                "description": f"{ext}, {_human_size(size)}",
            })
        elif entry.stat().st_mtime > pre[rel]:
            # Existing file with newer mtime — modified
            artifacts.append({
                "path": rel,
                "action": "modified",
                "diff": f"File updated ({_human_size(size)})",
            })

    return artifacts


def _relocate_invalid_memory_files(task_id: str, workspace: Path) -> list[Path]:
    """Move memory contract violations into the task output directory.

    Files are relocated to `output/` with a `memory-relocated-` prefix so they
    show up in the normal artifact pipeline. Directories are archived as zip
    files for the same reason.
    """
    from mc.memory import find_invalid_memory_files
    from mc.memory.index import MemoryIndex

    memory_dir = workspace / "memory"
    invalid_paths = find_invalid_memory_files(memory_dir)
    if not invalid_paths:
        return []

    safe_id = task_safe_id(task_id)
    output_dir = Path.home() / ".nanobot" / "tasks" / safe_id / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    moved: list[Path] = []

    def _unique_path(base_name: str) -> Path:
        candidate = output_dir / base_name
        if not candidate.exists():
            return candidate
        stem = candidate.stem
        suffix = candidate.suffix
        idx = 2
        while True:
            candidate = output_dir / f"{stem}-{idx}{suffix}"
            if not candidate.exists():
                return candidate
            idx += 1

    for path in invalid_paths:
        if path.is_dir() and not path.is_symlink():
            archive_base = _unique_path(f"memory-relocated-{path.name}").with_suffix("")
            archive_file = Path(
                shutil.make_archive(
                    str(archive_base),
                    "zip",
                    root_dir=path.parent,
                    base_dir=path.name,
                )
            )
            shutil.rmtree(path)
            moved.append(archive_file)
            logger.warning(
                "[executor] Archived invalid memory directory '%s' to '%s'",
                path,
                archive_file,
            )
            continue

        target = _unique_path(f"memory-relocated-{path.name}")
        shutil.move(str(path), str(target))
        moved.append(target)
        logger.warning(
            "[executor] Relocated invalid memory file '%s' to '%s'",
            path,
            target,
        )

    if memory_dir.exists():
        MemoryIndex(memory_dir).sync()

    return moved


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

            # Determine final status based on trust level
            if trust_level == TrustLevel.AUTONOMOUS:
                final_status = TaskStatus.DONE
            else:
                final_status = TaskStatus.REVIEW

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
