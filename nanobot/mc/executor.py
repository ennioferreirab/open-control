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
from typing import TYPE_CHECKING, Any

from nanobot.mc.gateway import AgentGateway
from nanobot.mc.planner import TaskPlanner
from nanobot.mc.types import (
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
)

if TYPE_CHECKING:
    from nanobot.mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)


def _collect_provider_error_types() -> tuple[type[Exception], ...]:
    """Collect provider-specific exception types for targeted catching.

    Returns a tuple of exception classes that represent provider/OAuth
    errors (as opposed to agent runtime errors). These are caught
    separately in _execute_task so they get surfaced with actionable
    instructions instead of being buried in generic crash handling.
    """
    from nanobot.mc.provider_factory import ProviderError

    types: list[type[Exception]] = [ProviderError]
    try:
        from nanobot.providers.anthropic_oauth import AnthropicOAuthExpired

        types.append(AnthropicOAuthExpired)
    except ImportError:
        pass
    return tuple(types)


_PROVIDER_ERRORS = _collect_provider_error_types()


def _provider_error_action(exc: Exception) -> str:
    """Extract a user-facing action string from a provider error.

    For ProviderError the action is explicit. For AnthropicOAuthExpired
    the message itself contains the command. Falls back to a generic hint.
    """
    from nanobot.mc.provider_factory import ProviderError

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
    from nanobot.mc.provider_factory import create_provider

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
) -> str:
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

    # Board-scoped session key format (AC6)
    if board_name:
        session_key = f"mc:board:{board_name}:task:{agent_name}"
    else:
        session_key = f"mc:task:{agent_name}"

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

    result = await loop.process_direct(
        content=message,
        session_key=session_key,
        channel="mc",
        chat_id=agent_name,
        task_id=task_id,
    )
    # TODO: revisit task-based consolidation — may be better than message-count
    # Consolidate memory and clear session (mirrors /new behavior)
    # await loop.end_task_session(session_key)
    return result


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
    import re

    safe_id = re.sub(r"[^\w\-]", "_", task_id)
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
    import re

    safe_id = re.sub(r"[^\w\-]", "_", task_id)
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


def _build_thread_context(messages: list[dict[str, Any]], max_messages: int = 20) -> str:
    """Format thread messages as conversation context for the agent.

    Thin shim that delegates to ThreadContextBuilder for backward compatibility.
    Preserves legacy behavior: returns empty string if no user messages exist.

    For step-aware context with predecessor injection, use ThreadContextBuilder
    directly with predecessor_step_ids parameter.
    """
    from nanobot.mc.thread_context import ThreadContextBuilder

    return ThreadContextBuilder().build(messages, max_messages=max_messages)


def _build_tag_attributes_context(
    tags: list[str],
    attr_values: list[dict[str, Any]],
    attr_catalog: list[dict[str, Any]],
) -> str:
    """Build a context section describing tag attribute values for the agent.

    Args:
        tags: List of tag name strings assigned to the task.
        attr_values: List of tagAttributeValue records (snake_case keys from bridge).
        attr_catalog: List of tagAttribute records (snake_case keys from bridge).

    Returns:
        A formatted string section like:
        [Task Tag Attributes]
        client-tag: priority=high, deadline=2026-03-01
        ...
        Returns empty string if no tags have non-empty attribute values.
    """
    if not tags or not attr_values or not attr_catalog:
        return ""

    # Build attribute id -> name lookup
    attr_name_map: dict[str, str] = {}
    for attr in attr_catalog:
        attr_id = attr.get("id") or attr.get("_id") or ""
        attr_name = attr.get("name", "")
        if attr_id and attr_name:
            attr_name_map[attr_id] = attr_name

    # Group values by tag name
    tag_attrs: dict[str, list[str]] = {}
    for val in attr_values:
        tag_name = val.get("tag_name", "")
        value = val.get("value", "")
        attr_id = val.get("attribute_id") or val.get("_attribute_id") or ""

        # Skip empty values
        if not tag_name or not value or tag_name not in tags:
            continue

        attr_name = attr_name_map.get(attr_id, "")
        if not attr_name:
            continue

        if tag_name not in tag_attrs:
            tag_attrs[tag_name] = []
        tag_attrs[tag_name].append(f"{attr_name}={value}")

    if not tag_attrs:
        return ""

    lines = ["[Task Tag Attributes]"]
    for tag_name in tags:
        if tag_name in tag_attrs:
            pairs = ", ".join(tag_attrs[tag_name])
            lines.append(f"{tag_name}: {pairs}")

    return "\n".join(lines)


class TaskExecutor:
    """Picks up assigned tasks and runs agent execution."""

    def __init__(self, bridge: ConvexBridge, cron_service: Any | None = None) -> None:
        self._bridge = bridge
        self._agent_gateway = AgentGateway(bridge)
        self._known_assigned_ids: set[str] = set()
        self._cron_service = cron_service
        self._tier_resolver: Any | None = None

    def _get_tier_resolver(self) -> Any:
        """Lazily create and return a TierResolver instance."""
        if self._tier_resolver is None:
            from nanobot.mc.tier_resolver import TierResolver
            self._tier_resolver = TierResolver(self._bridge)
        return self._tier_resolver

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
        from nanobot.mc.gateway import filter_agent_fields

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

        planner = TaskPlanner()
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
        from nanobot.mc.gateway import AGENTS_DIR
        from nanobot.mc.yaml_validator import validate_agent_file

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
        from nanobot.mc.gateway import AGENTS_DIR
        from nanobot.mc.yaml_validator import validate_agent_file

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
        """Prepend global orientation for non-lead-agent MC agents.

        Reads ~/.nanobot/mc/agent-orientation.md and prepends its content
        before the agent's own prompt. Returns prompt unchanged if:
        - agent is 'lead-agent'
        - orientation file does not exist
        - orientation file is empty
        """
        if is_lead_agent(agent_name):
            return agent_prompt

        orientation_path = Path.home() / ".nanobot" / "mc" / "agent-orientation.md"
        if not orientation_path.exists():
            return agent_prompt

        orientation = orientation_path.read_text(encoding="utf-8").strip()
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

        import re

        # Fetch fresh task data for up-to-date file manifest (NFR8)
        safe_id = re.sub(r"[^\w\-]", "_", task_id)
        files_dir = str(Path.home() / ".nanobot" / "tasks" / safe_id)
        try:
            fresh_task = await asyncio.to_thread(
                self._bridge.query, "tasks:getById", {"task_id": task_id}
            )
            raw_files = (fresh_task or {}).get("files") or []
        except Exception:
            logger.warning(
                "[executor] Failed to fetch fresh task data for '%s', using subscription snapshot",
                title,
            )
            raw_files = (task_data or {}).get("files") or []
        file_manifest = [
            {
                "name": f.get("name", "unknown"),
                "type": f.get("type", "application/octet-stream"),
                "size": f.get("size", 0),
                "subfolder": f.get("subfolder", "attachments"),
            }
            for f in raw_files
        ]

        output_dir = str(Path.home() / ".nanobot" / "tasks" / safe_id / "output")
        task_instruction = (
            f"Task workspace: {files_dir}\n"
            f"Save ALL output files (reports, summaries, generated content) to: {output_dir}\n"
            f"Do NOT save output files outside this directory."
        )
        if file_manifest:
            manifest_summary = ", ".join(
                f"{f['name']} ({f['subfolder']}, {_human_size(f['size'])})"
                for f in file_manifest
            )
            task_instruction += (
                f"\nTask has {len(file_manifest)} attached file(s) at {files_dir}/attachments. "
                f"File manifest: {manifest_summary}"
            )
        description = (description or "") + f"\n\n{task_instruction}"

        # Inject thread context for multi-turn agent interaction
        try:
            thread_messages = await asyncio.to_thread(
                self._bridge.get_task_messages, task_id
            )
            thread_context = _build_thread_context(thread_messages)
            if thread_context:
                description = (description or "") + f"\n{thread_context}"
                injected_count = min(len(thread_messages), 20)
                logger.info(
                    "[executor] Injected thread context (%d of %d messages) for task '%s'",
                    injected_count, len(thread_messages), title,
                )
        except Exception:
            logger.warning(
                "[executor] Failed to fetch thread messages for '%s', continuing without thread context",
                title,
                exc_info=True,
            )

        # Inject tag attribute values context (Story 12.2)
        try:
            task_tags = (task_data or {}).get("tags") or []
            if task_tags:
                tag_attr_values = await asyncio.to_thread(
                    self._bridge.query,
                    "tagAttributeValues:getByTask",
                    {"task_id": task_id},
                )
                tag_attr_catalog = await asyncio.to_thread(
                    self._bridge.query,
                    "tagAttributes:list",
                    {},
                )
                tag_attrs_context = _build_tag_attributes_context(
                    task_tags,
                    tag_attr_values if isinstance(tag_attr_values, list) else [],
                    tag_attr_catalog if isinstance(tag_attr_catalog, list) else [],
                )
                if tag_attrs_context:
                    description = (description or "") + f"\n\n{tag_attrs_context}"
                    logger.info(
                        "[executor] Injected tag attributes context for task '%s'",
                        title,
                    )
        except Exception:
            logger.warning(
                "[executor] Failed to fetch tag attributes for '%s', continuing without tag attributes context",
                title,
                exc_info=True,
            )

        # Load agent prompt, model, and skills from YAML config
        agent_prompt, agent_model, agent_skills = self._load_agent_config(agent_name)

        # Convex is the source of truth for model, prompt, and variables — override YAML
        try:
            from nanobot.mc.gateway import AGENTS_DIR
            convex_agent = await asyncio.to_thread(self._bridge.get_agent_by_name, agent_name)
            if convex_agent:
                # Sync model
                if convex_agent.get("model"):
                    convex_model = convex_agent["model"]
                    if convex_model != agent_model:
                        logger.info(
                            "[executor] Model synced from Convex for '%s': %s → %s",
                            agent_name, agent_model, convex_model,
                        )
                        agent_model = convex_model
                        # Write back to YAML so local host stays in sync
                        try:
                            await asyncio.to_thread(
                                self._bridge.write_agent_config, convex_agent, AGENTS_DIR
                            )
                        except Exception:
                            logger.warning(
                                "[executor] YAML write-back failed for '%s'", agent_name, exc_info=True
                            )

                # Sync prompt (Convex is source of truth for dashboard edits)
                convex_prompt = convex_agent.get("prompt")
                if convex_prompt:
                    agent_prompt = convex_prompt

                # Interpolate variables into prompt ({{var_name}} → value)
                variables = convex_agent.get("variables") or []
                if variables and agent_prompt:
                    for var in variables:
                        placeholder = "{{" + var["name"] + "}}"
                        agent_prompt = agent_prompt.replace(placeholder, var["value"])
                    logger.info(
                        "[executor] Interpolated %d variable(s) into prompt for '%s'",
                        len(variables), agent_name,
                    )
        except Exception:
            logger.warning(
                "[executor] Could not fetch Convex agent data for '%s', using YAML", agent_name, exc_info=True
            )

        # Resolve tier references (Story 11.1, AC5)
        reasoning_level: str | None = None
        if agent_model and is_tier_reference(agent_model):
            tier_ref = agent_model  # save before overwriting
            try:
                agent_model = self._get_tier_resolver().resolve_model(agent_model)
                logger.info("[executor] Resolved tier for agent '%s': %s", agent_name, agent_model)
            except ValueError as exc:
                await self._handle_tier_error(task_id, title, agent_name, exc)
                return
            # Resolve reasoning level — never raises, missing config = off
            reasoning_level = self._get_tier_resolver().resolve_reasoning_level(tier_ref)
            if reasoning_level:
                logger.info(
                    "[executor] Reasoning level for agent '%s': %s", agent_name, reasoning_level
                )

        # Inject global orientation for non-lead agents
        agent_prompt = self._maybe_inject_orientation(agent_name, agent_prompt)

        # System agents (nanobot) use identity from SOUL.md + ContextBuilder —
        # skip prompt/orientation injection so MC uses the exact same prompt as Telegram.
        if agent_name == NANOBOT_AGENT_NAME:
            agent_prompt = None

        # Inject agent roster into lead-agent context so it can discover all
        # available agents without relying on list_dir (which only shows agents
        # that have already run and have a board-scoped workspace).
        if is_lead_agent(agent_name):
            roster = self._build_agent_roster()
            if roster:
                description = (description or "") + f"\n\n{roster}"
                logger.info("[executor] Injected agent roster into lead-agent context")

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

        # Resolve board-scoped workspace (AC6, AC7)
        board_name: str | None = None
        memory_workspace: Path | None = None
        board_id = (task_data or {}).get("board_id")
        if board_id:
            try:
                board = await asyncio.to_thread(
                    self._bridge.get_board_by_id, board_id
                )
                if board:
                    board_name = board.get("name")
                    if board_name:
                        from nanobot.mc.board_utils import resolve_board_workspace, get_agent_memory_mode
                        mode = get_agent_memory_mode(board, agent_name)
                        memory_workspace = resolve_board_workspace(
                            board_name, agent_name, mode=mode
                        )
                        logger.info(
                            "[executor] Using board-scoped workspace for agent '%s' on board '%s' (mode=%s)",
                            agent_name, board_name, mode,
                        )
            except Exception:
                logger.warning(
                    "[executor] Failed to resolve board workspace for task '%s', using global workspace",
                    title,
                    exc_info=True,
                )

        # Snapshot the output directory before agent execution so we can detect
        # created/modified files afterwards (Story 2.5).
        pre_snapshot = await asyncio.to_thread(_snapshot_output_dir, task_id)

        try:
            result = await _run_agent_on_task(
                agent_name=agent_name,
                agent_prompt=agent_prompt,
                agent_model=agent_model,
                reasoning_level=reasoning_level,
                task_title=title,
                task_description=description,
                agent_skills=agent_skills,
                board_name=board_name,
                memory_workspace=memory_workspace,
                cron_service=self._cron_service,
                task_id=task_id,
                bridge=self._bridge,
            )

            # Collect file artifacts produced during agent execution.
            artifacts = await asyncio.to_thread(
                _collect_output_artifacts, task_id, pre_snapshot
            )

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

        except _PROVIDER_ERRORS as exc:
            # Provider/OAuth errors get surfaced with clear actionable message
            await self._handle_provider_error(task_id, title, agent_name, exc)

        except Exception as exc:
            logger.error(
                "[executor] Agent '%s' crashed on task '%s': %s",
                agent_name, title, exc,
            )
            await self._agent_gateway.handle_agent_crash(agent_name, task_id, exc)
        finally:
            # Allow re-pickup if task returns to assigned (e.g. after retry)
            self._known_assigned_ids.discard(task_id)
