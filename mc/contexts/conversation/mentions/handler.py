"""
Conversation-owned mention handler for task-thread @mentions.

When a user writes "@agent-name message" in a task thread, this module:
1. Detects the @mention pattern
2. Loads and runs the mentioned agent
3. Posts the agent's response back to the task thread

Story: "Mencionar agentes via @arroba em qualquer task"
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mc.types import (
    ActivityEventType,
    AuthorType,
    MessageType,
    TrustLevel,
    is_lead_agent,
)

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)

# Regex to detect @mentions at the start of a message or inline.
# Matches @agent-name or @agent_name (alphanumeric, hyphens, underscores).
# Returns (agent_name, message_body) where message_body is the rest of the text.
_MENTION_RE = re.compile(
    r"@([\w][\w\-]*)",
    re.UNICODE,
)

# Timeout for a single mention response (seconds)
MENTION_TIMEOUT_SECONDS = 120


def _known_agent_names() -> set[str]:
    """Return lowercase names of all agents with a config.yaml on disk."""
    agents_dir = Path.home() / ".nanobot" / "agents"
    if not agents_dir.is_dir():
        return set()
    return {
        d.name.lower() for d in agents_dir.iterdir() if d.is_dir() and (d / "config.yaml").exists()
    }


def extract_mentions(content: str) -> list[tuple[str, str]]:
    """Extract @mentions that match known agent names.

    Returns a list of (agent_name, query) tuples.
    The query is the full message with only valid agent @mentions removed (trimmed).
    Non-agent @handles (e.g. YouTube channel handles like @AIJasonZ) are left
    intact in the query text.

    If the message has multiple @mentions (e.g. "@alice @bob help me"),
    each agent receives the same query (message without any agent @mentions).

    Args:
        content: Raw message text from the user.

    Returns:
        List of (agent_name, query) tuples. Empty list if no known-agent @mentions found.
    """
    mentions = _MENTION_RE.findall(content)
    if not mentions:
        return []

    # Only keep mentions that match actual agent names
    known = _known_agent_names()
    valid_mentions = [m for m in mentions if m.lower() in known]
    if not valid_mentions:
        return []

    # Strip only VALID agent mentions from the message to get the clean query
    # (leave non-agent @handles like @AIJasonZ intact in the query)
    query = content
    for agent_name in valid_mentions:
        query = re.sub(rf"@{re.escape(agent_name)}\b", "", query, flags=re.IGNORECASE)
    query = query.strip()

    # Deduplicate while preserving order
    seen: set[str] = set()
    result: list[tuple[str, str]] = []
    for agent_name in valid_mentions:
        lower_name = agent_name.lower()
        if lower_name not in seen:
            seen.add(lower_name)
            result.append((lower_name, query))

    return result


def is_mention_message(content: str) -> bool:
    """Return True if content contains @mentions of known agents."""
    return bool(extract_mentions(content))


async def handle_mention(
    bridge: ConvexBridge,
    task_id: str,
    agent_name: str,
    query: str,
    caller_message_content: str,
    task_title: str = "",
) -> None:
    """Handle a single @mention: run the agent and post response to the thread.

    Args:
        bridge: ConvexBridge instance.
        task_id: Convex task _id.
        agent_name: Name of the mentioned agent.
        query: The message to send to the agent (without @mention prefix).
        caller_message_content: Original full message from the user (for context).
        task_title: Title of the task (for context injection).
    """
    logger.info(
        "[mention_handler] @%s mentioned in task %s: %r",
        agent_name,
        task_id,
        query[:80],
    )

    # Guard: lead-agent cannot be mentioned directly
    if is_lead_agent(agent_name) or agent_name == "lead-agent":
        await asyncio.to_thread(
            bridge.send_message,
            task_id,
            "System",
            AuthorType.SYSTEM,
            (
                f"@{agent_name} cannot be mentioned directly. "
                "The Lead Agent is a pure orchestrator and does not respond to mentions."
            ),
            MessageType.SYSTEM_EVENT,
        )
        return

    # Load agent config — needed for early validation and to get display_name
    from mc.infrastructure.agents.yaml_validator import validate_agent_file
    from mc.infrastructure.config import AGENTS_DIR

    config_file = AGENTS_DIR / agent_name / "config.yaml"
    if not config_file.exists():
        # List available agents for a helpful error message
        available = _list_available_agents(AGENTS_DIR)
        await asyncio.to_thread(
            bridge.send_message,
            task_id,
            "System",
            AuthorType.SYSTEM,
            (f"Agent @{agent_name} not found.\nAvailable agents: {available}"),
            MessageType.SYSTEM_EVENT,
        )
        return

    config_result = validate_agent_file(config_file)
    if isinstance(config_result, list):
        await asyncio.to_thread(
            bridge.send_message,
            task_id,
            "System",
            AuthorType.SYSTEM,
            f"Agent @{agent_name} has an invalid configuration: {'; '.join(config_result)}",
            MessageType.SYSTEM_EVENT,
        )
        return

    display_name = config_result.display_name or agent_name

    # Fetch task data for mention-specific sections
    task_data: dict[str, Any] | None = None
    try:
        task_data = await asyncio.to_thread(bridge.get_task, task_id)
    except Exception:
        logger.warning(
            "[mention_handler] Failed to fetch task data for task %s",
            task_id,
            exc_info=True,
        )

    # Post a "typing" indicator to the thread
    try:
        await asyncio.to_thread(
            bridge.create_activity,
            ActivityEventType.THREAD_MESSAGE_SENT,
            f"@{agent_name} was mentioned in task '{task_title or task_id}'",
            task_id,
            agent_name,
        )
    except Exception:
        pass  # Non-critical

    # Build the mention query
    mention_query = query or caller_message_content
    if not mention_query.strip():
        mention_query = f"You were mentioned in task: {task_title or task_id}"

    # Build execution context via ContextBuilder (handles YAML, Convex sync,
    # tier resolution, orientation, thread context, file enrichment, etc.)
    try:
        from mc.application.execution.context_builder import ContextBuilder
        from mc.application.execution.post_processing import build_execution_engine

        ctx_builder = ContextBuilder(bridge)
        req = await ctx_builder.build_task_context(
            task_id=task_id,
            title=task_title or task_data.get("title", task_id)
            if task_data
            else task_title or task_id,
            description=task_data.get("description") if task_data else None,
            agent_name=agent_name,
            trust_level=task_data.get("trust_level", TrustLevel.AUTONOMOUS)
            if task_data
            else TrustLevel.AUTONOMOUS,
            task_data=task_data or {},
        )

        # Append mention-specific sections to description
        mention_sections: list[str] = []

        # [Mention] — the core reason the agent was invoked
        mention_sections.append(
            f"[Mention]\n"
            f"You were mentioned via @{agent_name} in a task thread.\n"
            f"User message: {mention_query}"
        )

        # [Task Context] — task metadata summary
        task_context = _build_task_context(task_data)
        if task_context:
            mention_sections.append(task_context)

        # [Execution Plan] — step-by-step plan summary
        plan_section = _build_execution_plan_summary(task_data)
        if plan_section:
            mention_sections.append(plan_section)

        # [Task Files] — attached file listing
        files_section = _build_task_files_section(task_data)
        if files_section:
            mention_sections.append(files_section)

        mention_addendum = "\n\n".join(mention_sections)
        req.description = (req.description or "") + f"\n\n{mention_addendum}"

        # Reassemble the canonical prompt after modifying description
        if req.agent_prompt:
            req.prompt = f"{req.agent_prompt}\n\n---\n\n{req.description}"
        else:
            req.prompt = req.description or req.title

        req.session_boundary_reason = "mention"

        engine = build_execution_engine(bridge=bridge)
        execution_result = await asyncio.wait_for(
            engine.run(req),
            timeout=MENTION_TIMEOUT_SECONDS,
        )

        if execution_result.success:
            response = execution_result.output
        else:
            response = f"@{agent_name} encountered an error: {execution_result.error_message or 'Unknown error'}"

    except TimeoutError:
        response = (
            f"@{agent_name} timed out after {MENTION_TIMEOUT_SECONDS} seconds "
            "and could not respond."
        )
        logger.error(
            "[mention_handler] @%s timed out on task %s",
            agent_name,
            task_id,
        )
    except Exception as exc:
        response = f"@{agent_name} encountered an error: {type(exc).__name__}: {exc}"
        logger.exception(
            "[mention_handler] @%s failed on task %s: %s",
            agent_name,
            task_id,
            exc,
        )

    # Post the agent's response to the task thread
    await asyncio.to_thread(
        bridge.send_message,
        task_id,
        display_name,
        AuthorType.AGENT,
        response,
        MessageType.WORK,
    )

    logger.info(
        "[mention_handler] @%s responded to mention in task %s",
        agent_name,
        task_id,
    )


async def handle_all_mentions(
    bridge: ConvexBridge,
    task_id: str,
    content: str,
    task_title: str = "",
) -> bool:
    """Detect and handle all @mentions in a message.

    Returns True if any @mentions were found and handled, False otherwise.

    All mentions in a single message are dispatched concurrently.

    Args:
        bridge: ConvexBridge instance.
        task_id: Convex task _id.
        content: Raw message content from the user.
        task_title: Title of the task (for context).

    Returns:
        True if at least one @mention was found and processed.
    """
    mentions = extract_mentions(content)
    if not mentions:
        return False

    logger.info(
        "[mention_handler] Found %d mention(s) in task %s: %s",
        len(mentions),
        task_id,
        [name for name, _ in mentions],
    )

    # Dispatch all mentions concurrently
    tasks = [
        handle_mention(
            bridge=bridge,
            task_id=task_id,
            agent_name=agent_name,
            query=query,
            caller_message_content=content,
            task_title=task_title,
        )
        for agent_name, query in mentions
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for (agent_name, _), result in zip(mentions, results, strict=False):
        if isinstance(result, Exception):
            logger.error(
                "[mention_handler] Failed to handle mention @%s on task %s: %s",
                agent_name,
                task_id,
                result,
            )

    return True


def _build_task_context(task_data: dict[str, Any] | None) -> str:
    """Build a [Task Context] section from task data.

    Includes title, description, status, assigned agent, tags, and board.
    Omits fields that are empty or None.

    Args:
        task_data: Task dict with snake_case keys, or None.

    Returns:
        Formatted "[Task Context]" section string, or "" if no task data.
    """
    if not task_data:
        return ""

    lines: list[str] = ["[Task Context]"]

    field_map = [
        ("title", "Title"),
        ("description", "Description"),
        ("status", "Status"),
        ("assigned_agent", "Assigned Agent"),
    ]
    for key, label in field_map:
        value = task_data.get(key)
        if value:
            lines.append(f"{label}: {value}")

    tags = task_data.get("tags")
    if tags and isinstance(tags, list):
        lines.append(f"Tags: {', '.join(str(t) for t in tags)}")

    board_id = task_data.get("board_id")
    if board_id:
        lines.append(f"Board ID: {board_id}")

    # Only return section if we have at least one field beyond the header
    if len(lines) <= 1:
        return ""

    return "\n".join(lines)


def _build_execution_plan_summary(task_data: dict[str, Any] | None) -> str:
    """Build a concise [Execution Plan] section from task data.

    Shows step title + status, one line per step.

    Args:
        task_data: Task dict with snake_case keys, or None.

    Returns:
        Formatted "[Execution Plan]" section, or "" if no plan exists.
    """
    if not task_data:
        return ""

    plan = task_data.get("execution_plan") or task_data.get("executionPlan")
    if not plan or not isinstance(plan, dict):
        return ""

    steps = plan.get("steps")
    if not steps or not isinstance(steps, list):
        return ""

    lines: list[str] = ["[Execution Plan]"]
    for i, step in enumerate(steps, 1):
        title = step.get("title") or step.get("name") or f"Step {i}"
        status = step.get("status", "unknown")
        lines.append(f"{i}. {title} — {status}")

    return "\n".join(lines)


def _build_task_files_section(task_data: dict[str, Any] | None) -> str:
    """Build a [Task Files] section listing attached files.

    Args:
        task_data: Task dict with snake_case keys, or None.

    Returns:
        Formatted "[Task Files]" section, or "" if no files attached.
    """
    if not task_data:
        return ""

    files = (
        task_data.get("files") or task_data.get("file_manifest") or task_data.get("fileManifest")
    )
    if not files or not isinstance(files, list):
        return ""

    lines: list[str] = ["[Task Files]"]
    for f in files:
        name = f.get("name", "unknown")
        desc = f.get("description", "")
        subfolder = f.get("subfolder", "")
        entry = f"- {name}"
        if subfolder:
            entry += f" ({subfolder})"
        if desc:
            entry += f" — {desc}"
        lines.append(entry)

    if len(lines) <= 1:
        return ""

    return "\n".join(lines)


def _list_available_agents(agents_dir: Path) -> str:
    """List available agent names from the agents directory."""
    if not agents_dir.is_dir():
        return "(none)"
    names = sorted(
        d.name for d in agents_dir.iterdir() if d.is_dir() and (d / "config.yaml").exists()
    )
    return ", ".join(f"@{n}" for n in names) if names else "(none)"
