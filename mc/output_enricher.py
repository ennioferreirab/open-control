"""Output enrichment, artifact handling, and agent execution helpers.

Extracted from executor.py to keep module sizes manageable.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mc.types import (
    is_lead_agent,
    LeadAgentExecutionError,
    task_safe_id,
)

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)


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
    from mc.thread_context import ThreadContextBuilder

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


def _collect_provider_error_types() -> tuple[type[Exception], ...]:
    """Collect provider-specific exception types for targeted catching.

    Returns a tuple of exception classes that represent provider/OAuth
    errors (as opposed to agent runtime errors). These are caught
    separately in _execute_task so they get surfaced with actionable
    instructions instead of being buried in generic crash handling.
    """
    from mc.provider_factory import ProviderError

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
    from mc.provider_factory import ProviderError

    if isinstance(exc, ProviderError) and exc.action:
        return exc.action
    # AnthropicOAuthExpired messages include "Run: nanobot provider login ..."
    msg = str(exc)
    if "Run:" in msg:
        return msg[msg.index("Run:"):]
    return "Check provider configuration in ~/.nanobot/config.json"


def _make_provider(model: str | None = None):
    """Create the LLM provider from the user's nanobot config.

    Delegates to the shared provider_factory.create_provider() to avoid
    duplication with nanobot/cli/commands.py.
    """
    from mc.provider_factory import create_provider

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


def _get_iana_timezone() -> str | None:
    """Resolve IANA timezone name from system (e.g. 'America/Vancouver')."""
    import os
    try:
        resolved = str(Path("/etc/localtime").resolve())
        if "zoneinfo/" in resolved:
            return resolved.split("zoneinfo/")[-1]
    except OSError:
        pass
    tz_env = os.environ.get("TZ")
    if tz_env and "/" in tz_env:
        return tz_env.lstrip(":")
    return None


def build_executor_agent_roster() -> str:
    """Build a roster of available agents for injection into executor orientation.

    Reads ~/.nanobot/agents/*/config.yaml, excludes system agents and lead-agent.
    Returns formatted list for agent orientation interpolation.
    """
    from mc.gateway import AGENTS_DIR
    from mc.yaml_validator import validate_agent_file

    lines: list[str] = []
    if not AGENTS_DIR.is_dir():
        return "(no other agents available)"
    for agent_dir in sorted(AGENTS_DIR.iterdir()):
        if not agent_dir.is_dir():
            continue
        config_path = agent_dir / "config.yaml"
        if not config_path.exists():
            continue
        result = validate_agent_file(config_path)
        if isinstance(result, list):
            continue
        # Skip system agents and lead-agent
        if getattr(result, "is_system", False) or is_lead_agent(result.name):
            continue
        skill_str = ", ".join(result.skills) if result.skills else "general"
        lines.append(f"- **{result.name}** — {result.role} (skills: {skill_str})")
    if not lines:
        return "(no other agents available)"
    return "\n".join(lines)


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
    # Resolve through mc.executor so test patches on "mc.executor._make_provider" work.
    import mc.executor as _exe
    provider, resolved_model = _exe._make_provider(agent_model)

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


async def _enrich_nanobot_description(
    bridge: Any, task_id: str, title: str,
    description: str | None, task_data: dict | None,
) -> str:
    """Enrich nanobot task description with file manifest, thread context, and tag attributes.

    Uses mc.executor module references so that test patches on
    "mc.executor._build_thread_context" etc. take effect.
    """
    import asyncio
    import mc.executor as _exe

    description = description or ""
    safe_id = task_safe_id(task_id)
    files_dir = str(Path.home() / ".nanobot" / "tasks" / safe_id)
    try:
        fresh_task = await asyncio.to_thread(bridge.query, "tasks:getById", {"task_id": task_id})
        raw_files = (fresh_task or {}).get("files") or []
    except Exception:
        logger.warning("[executor] Failed to fetch fresh task data for '%s', using snapshot", title)
        raw_files = (task_data or {}).get("files") or []
    file_manifest = [
        {"name": f.get("name", "unknown"), "type": f.get("type", "application/octet-stream"),
         "size": f.get("size", 0), "subfolder": f.get("subfolder", "attachments")}
        for f in raw_files
    ]
    output_dir = str(Path.home() / ".nanobot" / "tasks" / safe_id / "output")
    task_instruction = (
        f"Task workspace: {files_dir}\n"
        f"Save ALL output files (reports, summaries, generated content) to: {output_dir}\n"
        f"Do NOT save output files outside this directory."
    )
    if file_manifest:
        manifest_summary = ", ".join(f"{f['name']} ({f['subfolder']}, {_exe._human_size(f['size'])})" for f in file_manifest)
        task_instruction += f"\nTask has {len(file_manifest)} attached file(s) at {files_dir}/attachments. File manifest: {manifest_summary}"
    description = (description or "") + f"\n\n{task_instruction}"
    try:
        thread_messages = await asyncio.to_thread(bridge.get_task_messages, task_id)
        thread_context = _exe._build_thread_context(thread_messages)
        if thread_context:
            description = (description or "") + f"\n{thread_context}"
    except Exception:
        logger.warning("[executor] Failed to fetch thread messages for '%s'", title, exc_info=True)
    try:
        task_tags = (task_data or {}).get("tags") or []
        if task_tags:
            tag_attr_values = await asyncio.to_thread(bridge.query, "tagAttributeValues:getByTask", {"task_id": task_id})
            tag_attr_catalog = await asyncio.to_thread(bridge.query, "tagAttributes:list", {})
            tag_attrs_context = _exe._build_tag_attributes_context(
                task_tags,
                tag_attr_values if isinstance(tag_attr_values, list) else [],
                tag_attr_catalog if isinstance(tag_attr_catalog, list) else [],
            )
            if tag_attrs_context:
                description = (description or "") + f"\n\n{tag_attrs_context}"
    except Exception:
        logger.warning("[executor] Failed to fetch tag attributes for '%s'", title, exc_info=True)
    return description

