"""Claude Code step execution backend.

Handles step execution through the Claude Code CLI when a step's model
uses the cc/ prefix (e.g. cc/claude-sonnet-4-6). Sets up workspace,
IPC server, and delegates to ClaudeCodeProvider.

Extracted from mc.step_dispatcher to separate backend concerns.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from mc.types import (
    AgentData,
    ClaudeCodeOpts,
    ActivityEventType,
    StepStatus,
    extract_cc_model_name,
)

logger = logging.getLogger(__name__)


async def execute_step_via_cc(
    *,
    bridge: Any,
    step_id: str,
    task_id: str,
    agent_name: str,
    agent_model: str,  # already has cc/ prefix
    agent_prompt: str | None,
    agent_skills: list[str] | None,
    step_title: str,
    execution_description: str,
    task_data: dict,
    pre_snapshot: Any,
    ask_user_registry: Any | None = None,
) -> list[str]:
    """Execute a step using the Claude Code backend.

    Returns list of unblocked step IDs after completion.
    """
    from mc.executor import (
        _collect_output_artifacts,
        _relocate_invalid_memory_files,
    )
    from mc.gateway import AGENTS_DIR
    from mc.yaml_validator import validate_agent_file

    cc_model_name = extract_cc_model_name(agent_model)

    # Load full AgentData from config.yaml for CC context enrichment (CC-9)
    config_path = AGENTS_DIR / agent_name / "config.yaml"
    full_agent_data = None
    if config_path.exists():
        result = validate_agent_file(config_path)
        if isinstance(result, AgentData):
            full_agent_data = result

    if full_agent_data:
        agent_data_for_cc = full_agent_data
        agent_data_for_cc.model = cc_model_name
        agent_data_for_cc.backend = "claude-code"
    else:
        agent_data_for_cc = AgentData(
            name=agent_name,
            display_name=agent_name,
            role="agent",
            model=cc_model_name,
            backend="claude-code",
        )

    # Try to enrich from Convex agent data (for claude_code_opts not in config.yaml)
    try:
        convex_agent_raw = await asyncio.to_thread(
            bridge.get_agent_by_name, agent_name
        )
        if convex_agent_raw:
            agent_data_for_cc.display_name = convex_agent_raw.get("display_name", agent_name)
            agent_data_for_cc.role = convex_agent_raw.get("role", "agent")
            # Sync skills from Convex (same pattern as prompt/model)
            convex_skills = convex_agent_raw.get("skills")
            if convex_skills is not None:
                if convex_skills != agent_data_for_cc.skills:
                    logger.info(
                        "[dispatcher] CC skills synced from Convex for '%s': %s -> %s",
                        agent_name, agent_data_for_cc.skills, convex_skills,
                    )
                agent_data_for_cc.skills = convex_skills
            cc_opts_raw = convex_agent_raw.get("claude_code_opts")
            if cc_opts_raw and isinstance(cc_opts_raw, dict):
                agent_data_for_cc.claude_code_opts = ClaudeCodeOpts(
                    max_budget_usd=cc_opts_raw.get("max_budget_usd"),
                    max_turns=cc_opts_raw.get("max_turns"),
                    permission_mode=cc_opts_raw.get("permission_mode", "acceptEdits"),
                    allowed_tools=cc_opts_raw.get("allowed_tools"),
                    disallowed_tools=cc_opts_raw.get("disallowed_tools"),
                )
    except Exception:
        logger.warning("[dispatcher] Could not enrich agent data for CC routing")

    # Execute step via CC backend
    from claude_code.workspace import CCWorkspaceManager
    from claude_code.provider import ClaudeCodeProvider
    from claude_code.ipc_server import MCSocketServer

    try:
        ws_mgr = CCWorkspaceManager()
        from mc.orientation import load_orientation
        orientation = load_orientation(agent_name)
        ws_ctx = ws_mgr.prepare(agent_name, agent_data_for_cc, task_id, orientation=orientation,
                                task_prompt=step_title)
    except Exception as exc:
        error_msg = f"CC workspace preparation failed for step '{step_title}': {exc}"
        logger.error("[dispatcher] %s", error_msg)
        raise

    from mc.ask_user_handler import AskUserHandler

    ask_handler = AskUserHandler()
    ipc_server = MCSocketServer(bridge, None)
    ipc_server.set_ask_user_handler(ask_handler)
    if ask_user_registry is not None:
        ask_user_registry.register(task_id, ask_handler)
    try:
        await ipc_server.start(ws_ctx.socket_path)
    except Exception as exc:
        error_msg = f"MCP IPC server failed for step '{step_title}': {exc}"
        logger.error("[dispatcher] %s", error_msg)
        raise

    try:
        from nanobot.config.loader import load_config
        _cfg = load_config()
        provider = ClaudeCodeProvider(
            cli_path=_cfg.claude_code.cli_path,
            defaults=_cfg.claude_code,
        )

        prompt = f"{step_title}\n\n{execution_description}"

        result_obj = await provider.execute_task(
            prompt=prompt,
            agent_config=agent_data_for_cc,
            task_id=task_id,
            workspace_ctx=ws_ctx,
            session_id=None,
        )
        if result_obj.is_error:
            raise RuntimeError(
                f"Claude Code error: {result_obj.output[:1000]}"
            )
        result = result_obj.output
    except Exception as exc:
        error_msg = f"CC execution failed for step '{step_title}': {exc}"
        logger.error("[dispatcher] %s", error_msg)
        raise
    finally:
        if ask_user_registry is not None:
            ask_user_registry.unregister(task_id)
        await ipc_server.stop()

    # Post completion -- same as nanobot path
    await asyncio.to_thread(
        _relocate_invalid_memory_files,
        task_id,
        ws_ctx.cwd,
    )
    artifacts = await asyncio.to_thread(
        _collect_output_artifacts, task_id, pre_snapshot
    )
    try:
        await asyncio.to_thread(
            bridge.sync_task_output_files,
            task_id,
            task_data,
            agent_name,
        )
    except Exception:
        logger.exception(
            "[dispatcher] Failed to sync output files for step %s", step_id
        )

    await asyncio.to_thread(
        bridge.post_step_completion,
        task_id,
        step_id,
        agent_name,
        result,
        artifacts or None,
    )
    await asyncio.to_thread(
        bridge.update_step_status,
        step_id,
        StepStatus.COMPLETED,
    )
    await asyncio.to_thread(
        bridge.create_activity,
        ActivityEventType.STEP_COMPLETED,
        f"Agent {agent_name} completed step: {step_title}",
        task_id,
        agent_name,
    )
    unblocked_ids = await asyncio.to_thread(
        bridge.check_and_unblock_dependents, step_id
    )
    return unblocked_ids if isinstance(unblocked_ids, list) else []
