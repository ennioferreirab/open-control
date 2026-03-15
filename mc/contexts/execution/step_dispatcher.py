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

from mc.application.execution.completion_status import resolve_completion_status
from mc.application.execution.interactive_mode import resolve_step_runner_type
from mc.types import (
    NANOBOT_AGENT_NAME,
    ActivityEventType,
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


def _coerce_step_run_result(value: Any) -> tuple[str, bool, str | None]:
    """Normalize legacy string results and structured execution results."""
    if isinstance(value, str):
        return value, False, None
    content = getattr(value, "content", None) or getattr(value, "output", "") or ""
    is_error = bool(
        getattr(value, "is_error", False)
        or (hasattr(value, "success") and not getattr(value, "success"))
    )
    error_message = getattr(value, "error_message", None)
    return content, is_error, error_message


def _maybe_inject_orientation(
    agent_name: str,
    agent_prompt: str | None,
) -> str | None:
    """Compatibility shim for older planner/executor orientation tests."""
    from mc.infrastructure.orientation import load_orientation

    orientation = load_orientation(agent_name)
    if not orientation:
        return agent_prompt
    if agent_prompt:
        return f"{orientation}\n\n---\n\n{agent_prompt}"
    return orientation


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
    request: Any | None = None,
    runner_type: Any | None = None,
    engine_builder: Any | None = None,
    provider_cli_registry: Any | None = None,
    provider_cli_supervisor: Any | None = None,
    provider_cli_projector: Any | None = None,
    provider_cli_supervision_sink: Any | None = None,
    provider_cli_control_plane: Any | None = None,
) -> Any:
    """Execute a step through the shared execution engine."""
    from mc.application.execution.post_processing import build_execution_engine
    from mc.application.execution.request import (
        EntityType,
        ExecutionRequest,
        RunnerType,
    )

    execution_request = request
    if execution_request is None:
        execution_request = ExecutionRequest(
            entity_type=EntityType.STEP,
            entity_id=task_id,
            task_id=task_id,
            title=task_title,
            description=task_description,
            agent_name=agent_name,
            agent_prompt=agent_prompt,
            agent_model=agent_model,
            agent_skills=agent_skills,
            reasoning_level=reasoning_level,
            board_name=board_name,
            memory_workspace=memory_workspace,
            runner_type=runner_type or RunnerType.NANOBOT,
        )
    elif runner_type is not None:
        execution_request.runner_type = runner_type

    if engine_builder is None:
        engine = build_execution_engine(
            bridge=bridge,
            cron_service=cron_service,
            ask_user_registry=ask_user_registry,
            provider_cli_registry=provider_cli_registry,
            provider_cli_supervisor=provider_cli_supervisor,
            provider_cli_projector=provider_cli_projector,
            provider_cli_supervision_sink=provider_cli_supervision_sink,
            provider_cli_control_plane=provider_cli_control_plane,
        )
    else:
        engine = engine_builder()
    return await engine.run(execution_request)


class StepDispatcher:
    """Dispatches and executes materialized task steps."""

    def __init__(
        self,
        bridge: ConvexBridge,
        cron_service: Any | None = None,
        ask_user_registry: Any | None = None,
        interactive_session_coordinator: Any | None = None,
        provider_cli_registry: Any | None = None,
        provider_cli_supervisor: Any | None = None,
        provider_cli_projector: Any | None = None,
        provider_cli_supervision_sink: Any | None = None,
        provider_cli_control_plane: Any | None = None,
    ) -> None:
        self._bridge = bridge
        self._cron_service = cron_service
        self._tier_resolver: Any | None = None
        self._ask_user_registry = ask_user_registry
        self._interactive_session_coordinator = interactive_session_coordinator
        self._provider_cli_registry = provider_cli_registry
        self._provider_cli_supervisor = provider_cli_supervisor
        self._provider_cli_projector = provider_cli_projector
        self._provider_cli_supervision_sink = provider_cli_supervision_sink
        self._provider_cli_control_plane = provider_cli_control_plane

    def _get_tier_resolver(self) -> Any:
        """Lazily create and return a TierResolver instance (shared across steps)."""
        if self._tier_resolver is None:
            from mc.infrastructure.providers.tier_resolver import TierResolver

            self._tier_resolver = TierResolver(self._bridge)
        return self._tier_resolver

    def _build_execution_engine(self) -> Any:
        """Build the canonical execution engine with dispatcher dependencies."""
        from mc.application.execution.post_processing import build_execution_engine

        return build_execution_engine(
            bridge=self._bridge,
            cron_service=self._cron_service,
            ask_user_registry=self._ask_user_registry,
            interactive_session_coordinator=self._interactive_session_coordinator,
            provider_cli_registry=self._provider_cli_registry,
            provider_cli_supervisor=self._provider_cli_supervisor,
            provider_cli_projector=self._provider_cli_projector,
            provider_cli_supervision_sink=self._provider_cli_supervision_sink,
            provider_cli_control_plane=self._provider_cli_control_plane,
        )

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

            task_left_in_progress = False
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
                    task_left_in_progress = True
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

            # Only attempt final status transitions when the task is still in_progress.
            # If another process (e.g. plan_negotiator) moved it to inbox/review, skip.
            if task_left_in_progress:
                return

            final_steps = await asyncio.to_thread(self._bridge.get_steps_by_task, task_id)
            any_crashed = any(step.get("status") == StepStatus.CRASHED for step in final_steps)
            if any_crashed:
                await asyncio.to_thread(
                    self._bridge.update_task_status,
                    task_id,
                    TaskStatus.CRASHED,
                    NANOBOT_AGENT_NAME,
                    "One or more steps crashed",
                )
                return
            all_completed = bool(final_steps) and all(
                step.get("status") == StepStatus.COMPLETED for step in final_steps
            )
            if all_completed:
                step_count = len(final_steps)
                task_data = await asyncio.to_thread(
                    self._bridge.query,
                    "tasks:getById",
                    {"task_id": task_id},
                )
                final_status = resolve_completion_status(task_data)
                await asyncio.to_thread(
                    self._bridge.update_task_status,
                    task_id,
                    final_status,
                    None,
                    f"All {step_count} steps completed",
                )
                if final_status == TaskStatus.REVIEW:
                    await asyncio.to_thread(
                        self._bridge.create_activity,
                        ActivityEventType.REVIEW_REQUESTED,
                        (
                            f"Execution completed -- all {step_count} steps finished; "
                            "awaiting explicit approval"
                        ),
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
                    (f"Step dispatch failed:\n```\n{type(exc).__name__}: {exc}\n```"),
                    MessageType.SYSTEM_EVENT,
                )
            except Exception:
                logger.error(
                    "[dispatcher] Failed to post dispatch failure message",
                    exc_info=True,
                )

    @staticmethod
    def _group_by_parallel_group(steps: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
        """Group steps by parallel_group and sort each group by order."""
        groups: dict[int, list[dict[str, Any]]] = {}
        for step in steps:
            parallel_group = _as_positive_int(step.get("parallel_group"), 1)
            groups.setdefault(parallel_group, []).append(step)

        for grouped_steps in groups.values():
            grouped_steps.sort(key=lambda step: _as_positive_int(step.get("order"), 1))
        return groups

    async def _dispatch_parallel_group(self, task_id: str, steps: list[dict[str, Any]]) -> None:
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
        from mc.application.execution.runtime import (
            collect_output_artifacts,
            snapshot_output_dir,
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
        # Workflow gate steps (human, checkpoint, review) transition directly to
        # waiting_human so the dashboard can surface them for human action.
        workflow_step_type = step.get("workflow_step_type")
        is_gate_step = workflow_step_type in ("human", "checkpoint", "review")

        if agent_name == "human" or is_gate_step:
            # Gate steps and human-assigned steps go to waiting_human immediately.
            # They stay there until a human explicitly acts via the dashboard.
            if is_gate_step and agent_name != "human":
                await asyncio.to_thread(
                    self._bridge.update_step_status,
                    step_id,
                    StepStatus.WAITING_HUMAN,
                )
                logger.info(
                    "[dispatcher] Step '%s' (type=%s) set to waiting_human",
                    step_title,
                    workflow_step_type,
                )
            else:
                logger.info(
                    "[dispatcher] Step '%s' assigned to human — leaving as assigned, skipping dispatch",
                    step_title,
                )
            return []

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
                error_msg = f"Model tier resolution failed for agent '{agent_name}': {exc}"
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
            pre_snapshot = await asyncio.to_thread(snapshot_output_dir, task_id)

            req.runner_type = resolve_step_runner_type(req)

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
                request=req,
                runner_type=req.runner_type,
                engine_builder=self._build_execution_engine,
            )
            transition_status = getattr(result, "transition_status", None)
            result_content, is_error_result, error_message = _coerce_step_run_result(result)
            if is_error_result:
                raise RuntimeError(
                    error_message or result_content or "Agent returned an execution error"
                )

            if transition_status == StepStatus.WAITING_HUMAN:
                await asyncio.to_thread(
                    self._bridge.update_step_status,
                    step_id,
                    StepStatus.WAITING_HUMAN,
                )
                return []

            # Collect artifacts and post structured completion message (Story 2.5).
            artifacts = await asyncio.to_thread(collect_output_artifacts, task_id, pre_snapshot)

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
                result_content,
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
                    self._bridge.update_task_status,
                    task_id,
                    TaskStatus.CRASHED,
                    agent_name,
                    f'Step "{step_title}" crashed',
                )
            except Exception:
                logger.error(
                    "[dispatcher] Failed to mark task %s as crashed after step failure",
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
