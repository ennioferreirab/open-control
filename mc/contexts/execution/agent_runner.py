"""Agent-run plumbing extracted from the task executor."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mc.contexts.execution.message_builder import build_task_message
from mc.contexts.execution.session_keys import build_agent_session_key
from mc.types import LeadAgentExecutionError, is_lead_agent

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)


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


def _make_provider(model: str | None = None):
    """Create the LLM provider from the user's nanobot config."""
    from mc.infrastructure.providers.factory import create_provider

    return create_provider(model)


def _call_provider_factory(model: str | None = None):
    """Preserve the historical executor patch seam during the hotspot split."""
    executor_mod = sys.modules.get("mc.contexts.execution.executor")
    provider_factory = getattr(executor_mod, "_make_provider", _make_provider)
    return provider_factory(model)


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
    """Run the nanobot agent loop on a task and return the result."""
    if is_lead_agent(agent_name):
        raise LeadAgentExecutionError(
            "INVARIANT VIOLATION: Lead Agent must never be passed to "
            "_run_agent_on_task(). Execution structurally blocked."
        )

    from nanobot.agent.loop import AgentLoop
    from nanobot.bus.queue import MessageBus

    workspace = Path.home() / ".nanobot" / "agents" / agent_name
    workspace.mkdir(parents=True, exist_ok=True)
    global_skills_dir = Path.home() / ".nanobot" / "workspace" / "skills"

    message = build_task_message(task_title, task_description)
    if agent_prompt:
        message = f"[System instructions]\n{agent_prompt}\n\n[Task]\n{message}"

    logger.info(
        "[_run_agent_on_task] Agent '%s': workspace=%s, memory_workspace=%s",
        agent_name,
        workspace,
        memory_workspace,
    )
    logger.info(
        "[_run_agent_on_task] Agent '%s': final message len=%d, first 500 chars:\n%s",
        agent_name,
        len(message),
        repr(message[:500]),
    )

    session_key = build_agent_session_key(
        agent_name=agent_name,
        task_id=task_id,
        board_name=board_name,
    )
    logger.info(
        "[_run_agent_on_task] Agent '%s': session_key='%s', board_name=%s",
        agent_name,
        session_key,
        board_name,
    )

    provider, resolved_model = _call_provider_factory(agent_model)

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

    loop.tools.unregister("delegate_task")

    if cron_tool := loop.tools.get("cron"):
        from nanobot.agent.tools.cron import CronTool as _CronTool

        if isinstance(cron_tool, _CronTool):
            from nanobot.config.loader import load_config as _load_config

            cfg = _load_config()
            telegram_ids = [
                x
                for x in cfg.channels.telegram.allow_from
                if x.lstrip("-").isdigit()
            ]
            if telegram_ids:
                cron_tool.set_telegram_default(telegram_ids[0])

    if ask_tool := loop.tools.get("ask_agent"):
        from nanobot.agent.tools.ask_agent import AskAgentTool

        if isinstance(ask_tool, AskAgentTool):
            ask_tool.set_context(
                caller_agent=agent_name,
                task_id=task_id,
                depth=0,
                bridge=bridge,
            )

    ask_user_cleanup: tuple[Any | None, str | None] | None = None
    if ask_user_tool := loop.tools.get("ask_user"):
        from nanobot.agent.tools.ask_user import AskUserTool

        if isinstance(ask_user_tool, AskUserTool):
            from mc.contexts.conversation.ask_user.handler import AskUserHandler

            handler = AskUserHandler()
            if ask_user_registry and task_id:
                ask_user_registry.register(task_id, handler)
            ask_user_tool.set_context(
                agent_name=agent_name,
                task_id=task_id,
                bridge=bridge,
                handler=handler,
            )
            ask_user_cleanup = (ask_user_registry, task_id)

    try:
        result = await loop.process_direct(
            content=message,
            session_key=session_key,
            channel="mc",
            chat_id=agent_name,
            task_id=task_id,
        )
    finally:
        if ask_user_cleanup is not None:
            registry, cleanup_task_id = ask_user_cleanup
            if registry and cleanup_task_id:
                registry.unregister(cleanup_task_id)

    return result, session_key, loop
