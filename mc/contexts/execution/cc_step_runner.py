"""DEPRECATED: Claude Code step execution backend.

Uses the legacy ClaudeCodeRunnerStrategy (Python SDK path).  New step
execution should use ProviderCliRunnerStrategy (headless ``-p`` flag).

Handles step execution through the Claude Code CLI when a step's model
uses the cc/ prefix (e.g. cc/claude-sonnet-4-6). Delegates to
ExecutionEngine.run() with a ClaudeCodeRunnerStrategy so that all
execution flows through the single entrypoint.

Extracted from mc.step_dispatcher to separate backend concerns.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from mc.application.execution.engine import ExecutionEngine
from mc.application.execution.request import (
    EntityType,
    ExecutionRequest,
    ExecutionResult,
    RunnerType,
)
from mc.application.execution.runtime import (
    collect_output_artifacts,
    relocate_invalid_memory_files,
)
from mc.types import (
    ActivityEventType,
    AgentData,
    ClaudeCodeOpts,
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
    """Execute a step using the Claude Code backend via ExecutionEngine.

    Builds an ExecutionRequest with step context and delegates to
    ExecutionEngine.run(). Post-execution steps (artifact collection,
    memory relocation, completion posting) are handled after the engine
    returns.

    Returns list of unblocked step IDs after completion.
    """
    from mc.infrastructure.agents.yaml_validator import validate_agent_file
    from mc.infrastructure.config import AGENTS_DIR

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
        convex_agent_raw = await asyncio.to_thread(bridge.get_agent_by_name, agent_name)
        if convex_agent_raw:
            agent_data_for_cc.display_name = convex_agent_raw.get("display_name", agent_name)
            agent_data_for_cc.role = convex_agent_raw.get("role", "agent")
            # Sync skills from Convex (same pattern as prompt/model)
            convex_skills = convex_agent_raw.get("skills")
            if convex_skills is not None:
                if convex_skills != agent_data_for_cc.skills:
                    logger.info(
                        "[dispatcher] CC skills synced from Convex for '%s': %s -> %s",
                        agent_name,
                        agent_data_for_cc.skills,
                        convex_skills,
                    )
                agent_data_for_cc.skills = convex_skills
            cc_opts_raw = convex_agent_raw.get("claude_code_opts")
            if cc_opts_raw and isinstance(cc_opts_raw, dict):
                agent_data_for_cc.claude_code_opts = ClaudeCodeOpts(
                    max_budget_usd=cc_opts_raw.get("max_budget_usd"),
                    max_turns=cc_opts_raw.get("max_turns"),
                    permission_mode=cc_opts_raw.get("permission_mode", "bypassPermissions"),
                    allowed_tools=cc_opts_raw.get("allowed_tools"),
                    disallowed_tools=cc_opts_raw.get("disallowed_tools"),
                )
    except Exception:
        logger.warning("[dispatcher] Could not enrich agent data for CC routing")

    # Build ExecutionRequest for the step
    request = ExecutionRequest(
        entity_type=EntityType.STEP,
        entity_id=step_id,
        task_id=task_id,
        title=step_title,
        description=execution_description,
        agent=agent_data_for_cc,
        agent_name=agent_name,
        agent_prompt=agent_prompt,
        agent_model=agent_model,
        agent_skills=agent_skills,
        runner_type=RunnerType.CLAUDE_CODE,
        step_id=step_id,
        task_data=task_data,
        is_cc=True,
    )

    # Execute via ExecutionEngine
    engine = ExecutionEngine(
        strategies={
            RunnerType.CLAUDE_CODE: _make_cc_strategy(
                bridge=bridge,
                ask_user_registry=ask_user_registry,
            ),
        },
    )
    engine_result: ExecutionResult = await engine.run(request)

    if not engine_result.success:
        raise RuntimeError(
            engine_result.error_message or f"CC execution failed for step '{step_title}'"
        )

    output = engine_result.output

    # Post completion — relocate invalid memory files and collect artifacts
    if engine_result.memory_workspace:
        await asyncio.to_thread(
            relocate_invalid_memory_files,
            task_id,
            engine_result.memory_workspace,
        )
    artifacts = await asyncio.to_thread(collect_output_artifacts, task_id, pre_snapshot)
    try:
        await asyncio.to_thread(
            bridge.sync_task_output_files,
            task_id,
            task_data,
            agent_name,
        )
    except Exception:
        logger.exception("[dispatcher] Failed to sync output files for step %s", step_id)

    await asyncio.to_thread(
        bridge.post_step_completion,
        task_id,
        step_id,
        agent_name,
        output,
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
    unblocked_ids = await asyncio.to_thread(bridge.check_and_unblock_dependents, step_id)
    return unblocked_ids if isinstance(unblocked_ids, list) else []


def _make_cc_strategy(
    *,
    bridge: Any,
    ask_user_registry: Any | None = None,
) -> Any:
    """Create a ClaudeCodeRunnerStrategy wired to the given bridge."""
    from mc.application.execution.strategies.claude_code import (
        ClaudeCodeRunnerStrategy,
    )

    return ClaudeCodeRunnerStrategy(
        bridge=bridge,
        ask_user_registry=ask_user_registry,
    )
