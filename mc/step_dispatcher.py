"""
Step dispatcher for autonomous execution-plan steps.

This module executes materialized steps (stored in Convex) by dispatching
"assigned" steps, running each step with its assigned agent, and managing
step lifecycle transitions.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mc.types import (
    NANOBOT_AGENT_NAME,
    ActivityEventType,
    AgentData,
    AuthorType,
    MessageType,
    StepStatus,
    TaskStatus,
    is_lead_agent,
)

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)


def _as_positive_int(value: Any, default: int) -> int:
    """Convert a value to a positive int, with fallback."""
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default



def _load_agent_config(
    agent_name: str,
) -> tuple[str | None, str | None, list[str] | None]:
    """Load prompt, model and skills from an agent config."""
    from mc.gateway import AGENTS_DIR
    from mc.yaml_validator import validate_agent_file

    config_file = AGENTS_DIR / agent_name / "config.yaml"
    if not config_file.exists():
        return None, None, None

    result = validate_agent_file(config_file)
    if isinstance(result, list):
        logger.warning(
            "[dispatcher] Agent '%s' config invalid: %s", agent_name, result
        )
        return None, None, None

    return result.prompt, result.model, result.skills


def _maybe_inject_orientation(
    agent_name: str, agent_prompt: str | None
) -> str | None:
    """Prepend global orientation for non-lead agents."""
    from mc.orientation import load_orientation

    orientation = load_orientation(agent_name)
    if not orientation:
        return agent_prompt

    if agent_prompt:
        return f"{orientation}\n\n---\n\n{agent_prompt}"
    return orientation


def _build_step_thread_context(
    messages: list[dict[str, Any]],
    max_messages: int = 20,
    predecessor_step_ids: list[str] | None = None,
) -> str:
    """Format thread messages as execution context for a step agent.

    Delegates to ThreadContextBuilder with predecessor awareness (AC #3).
    When predecessor_step_ids is provided, ensures their completion messages
    are always included even outside the 20-message window.
    """
    from mc.thread_context import ThreadContextBuilder

    return ThreadContextBuilder().build(
        messages,
        max_messages=max_messages,
        predecessor_step_ids=predecessor_step_ids,
    )


async def _run_step_agent(
    *,
    agent_name: str,
    agent_prompt: str | None,
    agent_model: str | None,
    reasoning_level: str | None = None,
    task_title: str,
    task_description: str,
    agent_skills: list[str] | None,
    board_name: str | None,
    memory_workspace: Path | None,
    task_id: str,
    cron_service: Any | None = None,
    bridge: Any | None = None,
    ask_user_registry: Any | None = None,
) -> str:
    """Lazily delegate step execution to executor helper."""
    from mc.executor import _background_tasks, _relocate_invalid_memory_files, _run_agent_on_task

    result, session_key, loop = await _run_agent_on_task(
        agent_name=agent_name,
        agent_prompt=agent_prompt,
        agent_model=agent_model,
        reasoning_level=reasoning_level,
        task_title=task_title,
        task_description=task_description,
        agent_skills=agent_skills,
        board_name=board_name,
        memory_workspace=memory_workspace,
        task_id=task_id,
        cron_service=cron_service,
        bridge=bridge,
        ask_user_registry=ask_user_registry,
    )

    await asyncio.to_thread(
        _relocate_invalid_memory_files,
        task_id,
        loop.memory_workspace,
    )

    # Fire-and-forget memory consolidation after step completion.
    # Runs async so the caller sees the result immediately.
    async def _post_step_consolidate():
        try:
            await loop.end_task_session(session_key)
            logger.info(
                "[dispatcher] Post-step memory consolidation done for agent '%s' session '%s'",
                agent_name, session_key,
            )
        except Exception:
            logger.warning(
                "[dispatcher] Post-step memory consolidation failed for agent '%s' session '%s'",
                agent_name, session_key, exc_info=True,
            )

    _task = asyncio.create_task(_post_step_consolidate())
    _background_tasks.add(_task)
    _task.add_done_callback(_background_tasks.discard)
    return result


class StepDispatcher:
    """Dispatches and executes materialized task steps."""

    def __init__(self, bridge: ConvexBridge, cron_service: Any | None = None,
                 ask_user_registry: Any | None = None) -> None:
        self._bridge = bridge
        self._cron_service = cron_service
        self._tier_resolver: Any | None = None
        self._ask_user_registry = ask_user_registry

    def _get_tier_resolver(self) -> Any:
        """Lazily create and return a TierResolver instance (shared across steps)."""
        if self._tier_resolver is None:
            from mc.tier_resolver import TierResolver
            self._tier_resolver = TierResolver(self._bridge)
        return self._tier_resolver

    async def dispatch_steps(self, task_id: str, step_ids: list[str]) -> None:
        """Dispatch assigned steps for a task until no runnable work remains."""
        logger.info(
            "[dispatcher] Starting dispatch for task %s (%d materialized step ids)",
            task_id,
            len(step_ids),
        )

        dispatched_step_ids: set[str] = set()
        try:
            await asyncio.to_thread(
                self._bridge.create_activity,
                ActivityEventType.TASK_DISPATCH_STARTED,
                "Steps dispatched in autonomous mode",
                task_id,
            )

            while True:
                # Pre-dispatch task status check (AC 7, Story 7.4):
                # If task is not in_progress (e.g., paused/review), skip new dispatches.
                task_check = await asyncio.to_thread(
                    self._bridge.query,
                    "tasks:getById",
                    {"task_id": task_id},
                )
                current_status = (
                    task_check.get("status", "unknown")
                    if isinstance(task_check, dict)
                    else "unknown"
                )
                if current_status != TaskStatus.IN_PROGRESS:
                    logger.info(
                        "[dispatcher] Task %s is not in_progress (status=%s); skipping dispatch",
                        task_id,
                        current_status,
                    )
                    break

                steps = await asyncio.to_thread(self._bridge.get_steps_by_task, task_id)
                assigned_steps = [
                    step
                    for step in steps
                    if step.get("status") == StepStatus.ASSIGNED
                    and str(step.get("id", "")) not in dispatched_step_ids
                ]

                if not assigned_steps:
                    break

                groups = self._group_by_parallel_group(assigned_steps)
                next_group = min(groups.keys())
                group_steps = groups[next_group]
                await self._dispatch_parallel_group(task_id, group_steps)
                dispatched_step_ids.update(
                    str(step.get("id")) for step in group_steps if step.get("id")
                )

            final_steps = await asyncio.to_thread(self._bridge.get_steps_by_task, task_id)
            all_completed = bool(final_steps) and all(
                step.get("status") == StepStatus.COMPLETED for step in final_steps
            )
            if all_completed:
                step_count = len(final_steps)
                await asyncio.to_thread(
                    self._bridge.update_task_status,
                    task_id,
                    TaskStatus.DONE,
                    None,
                    f"All {step_count} steps completed",
                )
                await asyncio.to_thread(
                    self._bridge.create_activity,
                    ActivityEventType.TASK_COMPLETED,
                    f"Task completed -- all {step_count} steps finished",
                    task_id,
                )
        except Exception as exc:
            logger.error(
                "[dispatcher] Dispatch failed for task %s",
                task_id,
                exc_info=True,
            )
            try:
                await asyncio.to_thread(
                    self._bridge.send_message,
                    task_id,
                    "System",
                    AuthorType.SYSTEM,
                    (
                        "Step dispatch failed:\n"
                        f"```\n{type(exc).__name__}: {exc}\n```"
                    ),
                    MessageType.SYSTEM_EVENT,
                )
            except Exception:
                logger.error(
                    "[dispatcher] Failed to post dispatch failure message",
                    exc_info=True,
                )

    @staticmethod
    def _group_by_parallel_group(
        steps: list[dict[str, Any]]
    ) -> dict[int, list[dict[str, Any]]]:
        """Group steps by parallel_group and sort each group by order."""
        groups: dict[int, list[dict[str, Any]]] = {}
        for step in steps:
            parallel_group = _as_positive_int(step.get("parallel_group"), 1)
            groups.setdefault(parallel_group, []).append(step)

        for grouped_steps in groups.values():
            grouped_steps.sort(
                key=lambda step: _as_positive_int(step.get("order"), 1)
            )
        return groups

    async def _dispatch_parallel_group(
        self, task_id: str, steps: list[dict[str, Any]]
    ) -> None:
        """Execute all steps in a parallel group concurrently."""
        results = await asyncio.gather(
            *[self._execute_step(task_id, step) for step in steps],
            return_exceptions=True,
        )

        for step, result in zip(steps, results):
            if isinstance(result, Exception):
                logger.error(
                    "[dispatcher] Step '%s' failed in parallel group: %s",
                    step.get("title", step.get("id", "<unknown-step>")),
                    result,
                )

    async def _execute_step(self, task_id: str, step: dict[str, Any]) -> list[str]:
        """Execute one assigned step and return any newly unblocked step IDs."""
        # Deferred imports to break circular dependency:
        # step_dispatcher -> executor -> gateway -> orchestrator -> step_dispatcher
        from mc.executor import (
            _collect_output_artifacts,
            _relocate_invalid_memory_files,
            _snapshot_output_dir,
        )

        step_id = step.get("id")
        if not step_id:
            logger.warning("[dispatcher] Skipping step without id: %s", step)
            return []

        step_title = (step.get("title") or "Untitled Step").strip()
        agent_name = (step.get("assigned_agent") or NANOBOT_AGENT_NAME).strip()
        if is_lead_agent(agent_name):
            logger.warning(
                "[dispatcher] Step '%s' assigned to lead-agent; rerouting to '%s'",
                step_title,
                NANOBOT_AGENT_NAME,
            )
            agent_name = NANOBOT_AGENT_NAME

        await asyncio.to_thread(
            self._bridge.create_activity,
            ActivityEventType.STEP_DISPATCHED,
            f"Step assigned to {agent_name}: {step_title}",
            task_id,
            agent_name,
        )
        await asyncio.to_thread(
            self._bridge.update_step_status,
            step_id,
            StepStatus.RUNNING,
        )
        await asyncio.to_thread(
            self._bridge.create_activity,
            ActivityEventType.STEP_STARTED,
            f"Agent {agent_name} started step: {step_title}",
            task_id,
            agent_name,
        )

        try:
            # ── Unified context pipeline (Story 16.1) ─────────────────────
            # Delegate all context building to the shared ContextBuilder.
            from mc.application.execution.context_builder import ContextBuilder

            try:
                ctx_builder = ContextBuilder(self._bridge)
                ctx_builder._tier_resolver = self._tier_resolver  # share resolver
                req = await ctx_builder.build_step_context(task_id, step)
            except ValueError as exc:
                error_msg = (
                    f"Model tier resolution failed for agent "
                    f"'{agent_name}': {exc}"
                )
                logger.error("[dispatcher] %s", error_msg)
                await asyncio.to_thread(
                    self._bridge.send_message,
                    task_id,
                    "System",
                    AuthorType.SYSTEM,
                    f'Step "{step_title}" failed: {error_msg}',
                    MessageType.SYSTEM_EVENT,
                )
                raise

            # Unpack unified request into local variables
            agent_prompt = req.agent_prompt
            agent_model = req.agent_model
            agent_skills = req.agent_skills
            reasoning_level = req.reasoning_level
            execution_description = req.description
            task_data = req.task_data
            board_name = req.board_name
            memory_workspace = req.memory_workspace

            # Snapshot output dir before agent execution for artifact detection
            # (Story 2.5).
            pre_snapshot = await asyncio.to_thread(_snapshot_output_dir, task_id)

            # Route to Claude Code backend when model starts with cc/
            if req.is_cc:
                cc_model_name = req.model

                # Use AgentData from unified pipeline, or build a fallback
                if req.agent:
                    agent_data_for_cc = req.agent
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

                # Try to enrich from Convex agent data
                # (for claude_code_opts not in config.yaml)
                try:
                    convex_agent_raw = await asyncio.to_thread(
                        self._bridge.get_agent_by_name, agent_name
                    )
                    if convex_agent_raw:
                        agent_data_for_cc.display_name = convex_agent_raw.get(
                            "display_name", agent_name
                        )
                        agent_data_for_cc.role = convex_agent_raw.get(
                            "role", "agent"
                        )
                        convex_skills = convex_agent_raw.get("skills")
                        if convex_skills is not None:
                            agent_data_for_cc.skills = convex_skills
                        cc_opts_raw = convex_agent_raw.get("claude_code_opts")
                        if cc_opts_raw and isinstance(cc_opts_raw, dict):
                            from mc.types import ClaudeCodeOpts
                            agent_data_for_cc.claude_code_opts = ClaudeCodeOpts(
                                max_budget_usd=cc_opts_raw.get("max_budget_usd"),
                                max_turns=cc_opts_raw.get("max_turns"),
                                permission_mode=cc_opts_raw.get(
                                    "permission_mode", "acceptEdits"
                                ),
                                allowed_tools=cc_opts_raw.get("allowed_tools"),
                                disallowed_tools=cc_opts_raw.get(
                                    "disallowed_tools"
                                ),
                            )
                except Exception:
                    logger.warning(
                        "[dispatcher] Could not enrich agent data for CC"
                    )

                # Execute step via CC backend
                from claude_code.ipc_server import MCSocketServer
                from claude_code.provider import ClaudeCodeProvider
                from claude_code.workspace import CCWorkspaceManager

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
                ipc_server = MCSocketServer(self._bridge, None)
                ipc_server.set_ask_user_handler(ask_handler)
                if self._ask_user_registry is not None:
                    self._ask_user_registry.register(task_id, ask_handler)
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
                    if self._ask_user_registry is not None:
                        self._ask_user_registry.unregister(task_id)
                    await ipc_server.stop()

                # Post completion — same as nanobot path
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
                        self._bridge.sync_task_output_files,
                        task_id,
                        task_data,
                        agent_name,
                    )
                except Exception:
                    logger.exception(
                        "[dispatcher] Failed to sync output files for step %s", step_id
                    )

                await asyncio.to_thread(
                    self._bridge.post_step_completion,
                    task_id,
                    step_id,
                    agent_name,
                    result,
                    artifacts or None,
                )
                await asyncio.to_thread(
                    self._bridge.update_step_status,
                    step_id,
                    StepStatus.COMPLETED,
                )
                await asyncio.to_thread(
                    self._bridge.create_activity,
                    ActivityEventType.STEP_COMPLETED,
                    f"Agent {agent_name} completed step: {step_title}",
                    task_id,
                    agent_name,
                )
                unblocked_ids = await asyncio.to_thread(
                    self._bridge.check_and_unblock_dependents, step_id
                )
                return unblocked_ids if isinstance(unblocked_ids, list) else []

            result = await _run_step_agent(
                agent_name=agent_name,
                agent_prompt=agent_prompt,
                agent_model=agent_model,
                reasoning_level=reasoning_level,
                task_title=step_title,
                task_description=execution_description,
                agent_skills=agent_skills,
                board_name=board_name,
                memory_workspace=memory_workspace,
                task_id=task_id,
                cron_service=self._cron_service,
                bridge=self._bridge,
                ask_user_registry=self._ask_user_registry,
            )

            # Collect artifacts and post structured completion message (Story 2.5).
            artifacts = await asyncio.to_thread(
                _collect_output_artifacts, task_id, pre_snapshot
            )

            # Sync output file manifest to Convex (best-effort, non-blocking) (Story 6.2).
            try:
                await asyncio.to_thread(
                    self._bridge.sync_task_output_files,
                    task_id,
                    task_data,
                    agent_name,
                )
            except Exception:
                logger.exception(
                    "[dispatcher] Failed to sync output files for step %s",
                    step_id,
                )

            await asyncio.to_thread(
                self._bridge.post_step_completion,
                task_id,
                step_id,
                agent_name,
                result,
                artifacts or None,
            )
            await asyncio.to_thread(
                self._bridge.update_step_status,
                step_id,
                StepStatus.COMPLETED,
            )
            await asyncio.to_thread(
                self._bridge.create_activity,
                ActivityEventType.STEP_COMPLETED,
                f"Agent {agent_name} completed step: {step_title}",
                task_id,
                agent_name,
            )

            unblocked_ids = await asyncio.to_thread(
                self._bridge.check_and_unblock_dependents, step_id
            )
            if not isinstance(unblocked_ids, list):
                return []
            return [str(unblocked_id) for unblocked_id in unblocked_ids]
        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}"

            try:
                await asyncio.to_thread(
                    self._bridge.update_step_status,
                    step_id,
                    StepStatus.CRASHED,
                    error_message,
                )
            except Exception:
                logger.error(
                    "[dispatcher] Failed to mark step %s as crashed",
                    step_id,
                    exc_info=True,
                )

            try:
                await asyncio.to_thread(
                    self._bridge.send_message,
                    task_id,
                    "System",
                    AuthorType.SYSTEM,
                    (
                        f'Step "{step_title}" crashed:\n'
                        f"```\n{error_message}\n```\n"
                        f"Agent: {agent_name}"
                    ),
                    MessageType.SYSTEM_EVENT,
                )
            except Exception:
                logger.error(
                    "[dispatcher] Failed to write crash message for step %s",
                    step_id,
                    exc_info=True,
                )

            raise
