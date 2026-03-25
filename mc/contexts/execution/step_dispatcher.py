"""
Step dispatcher for autonomous execution-plan steps.

This module executes materialized steps (stored in Convex) by dispatching
"assigned" steps, running each step with its assigned agent, and managing
step lifecycle transitions.
"""

from __future__ import annotations

import asyncio
import contextlib
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
    is_orchestrator_agent,
)

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)


async def _transition_task_from_snapshot(
    bridge: Any,
    task_data: dict[str, Any],
    to_status: str,
    *,
    reason: str,
    agent_name: str | None = None,
    review_phase: str | None = None,
) -> Any:
    result = await asyncio.to_thread(
        bridge.transition_task_from_snapshot,
        task_data,
        to_status,
        reason=reason,
        agent_name=agent_name,
        review_phase=review_phase,
    )
    return result


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
        getattr(value, "is_error", False) or (hasattr(value, "success") and not value.success)
    )
    error_message = getattr(value, "error_message", None)
    return content, is_error, error_message


def _is_workflow_gate_step(step_type: str | None) -> bool:
    return step_type == "human"


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

    async def _resolve_review_loop_limit(
        self, task_id: str, task_data: dict[str, Any] | None = None
    ) -> int:
        """Resolve the review loop limit with 3-tier precedence.

        1. Workflow spec ``onReject.maxRetries`` (per-workflow)
        2. Global setting ``review_loop_limit`` (settings table)
        3. Hardcoded default: 5

        Returns 0 for unlimited.
        """
        # 1. Try workflow-spec override
        try:
            effective_task_data = task_data
            if not isinstance(effective_task_data, dict):
                effective_task_data = await asyncio.to_thread(
                    self._bridge.query, "tasks:getById", {"task_id": task_id}
                )
            if isinstance(effective_task_data, dict):
                workflow_spec_id = effective_task_data.get(
                    "workflow_spec_id"
                ) or effective_task_data.get("workflowSpecId")
                if workflow_spec_id:
                    spec = await asyncio.to_thread(
                        self._bridge.query,
                        "workflowSpecs:getById",
                        {"spec_id": str(workflow_spec_id)},
                    )
                    if isinstance(spec, dict):
                        on_reject = spec.get("on_reject") or spec.get("onReject")
                        if isinstance(on_reject, dict):
                            max_retries = on_reject.get("max_retries") or on_reject.get(
                                "maxRetries"
                            )
                            if max_retries is not None:
                                try:
                                    return int(max_retries)
                                except (TypeError, ValueError):
                                    pass
        except Exception:
            logger.debug(
                "[dispatcher] Could not read workflow spec for task %s; falling back",
                task_id,
                exc_info=True,
            )

        # 2. Global setting
        try:
            global_limit = await asyncio.to_thread(self._bridge.get_review_loop_limit)
            return global_limit
        except Exception:
            logger.debug(
                "[dispatcher] Could not read global review_loop_limit; using default",
                exc_info=True,
            )

        # 3. Hardcoded default
        logger.warning(
            "[dispatcher] Using hardcoded review loop limit (5) for task %s — "
            "both workflow spec and global settings were unavailable",
            task_id,
        )
        return 5

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

                # Allow re-dispatch of steps that returned to assigned
                # (e.g. review rejection rerouting or dependency unblocking).
                for s in steps:
                    sid = str(s.get("id", ""))
                    if s.get("status") == StepStatus.ASSIGNED and sid in dispatched_step_ids:
                        logger.info(
                            "[dispatcher] Step '%s' returned to assigned; allowing re-dispatch",
                            s.get("title", sid),
                        )
                        dispatched_step_ids.discard(sid)

                assigned_steps = [
                    step
                    for step in steps
                    if step.get("status") == StepStatus.ASSIGNED
                    and str(step.get("id", "")) not in dispatched_step_ids
                ]

                if not assigned_steps:
                    # Check if human/gate steps are still pending and could
                    # unblock blocked dependents when the user completes them.
                    # Without this, the loop exits and no one re-dispatches
                    # the newly-assigned steps after the human acts.
                    has_human_pending = any(
                        s.get("status") in (StepStatus.WAITING_HUMAN, StepStatus.RUNNING)
                        for s in steps
                        if s.get("workflow_step_type") == "human"
                        or s.get("assigned_agent") == "human"
                    )
                    has_blocked = any(s.get("status") == StepStatus.BLOCKED for s in steps)
                    if has_human_pending and has_blocked:
                        logger.info(
                            "[dispatcher] Waiting for human step resolution on task %s via subscription",
                            task_id,
                        )
                        resolved = await self._wait_for_human_step_resolution(task_id)
                        if resolved:
                            continue
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
                task_data = await asyncio.to_thread(self._bridge.get_task, task_id)
                if isinstance(task_data, dict):
                    await _transition_task_from_snapshot(
                        self._bridge,
                        task_data,
                        TaskStatus.CRASHED,
                        agent_name=NANOBOT_AGENT_NAME,
                        reason="One or more steps crashed",
                    )
                else:
                    logger.warning(
                        "[dispatcher] Could not load task %s before crashed transition",
                        task_id,
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
                final_status = resolve_completion_status()
                transition_result = await _transition_task_from_snapshot(
                    self._bridge,
                    task_data,
                    final_status,
                    reason=f"All {step_count} steps completed",
                )
                if not isinstance(transition_result, dict) or transition_result.get("kind") not in {
                    "applied",
                    "noop",
                }:
                    logger.warning(
                        "[dispatcher] Final task transition for %s did not apply: %s",
                        task_id,
                        transition_result,
                    )
                    return
                await asyncio.to_thread(
                    self._bridge.create_activity,
                    ActivityEventType.TASK_COMPLETED,
                    f"Execution completed -- all {step_count} steps finished",
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

    async def _wait_for_human_step_resolution(self, task_id: str) -> bool:
        """Wait indefinitely for step changes via Convex subscription (WebSocket).

        Human gate steps are approval checkpoints — no timeout.
        The workflow stays paused until the human acts.

        Returns True if new assigned steps appeared (human approved),
        False if the task left the waiting state (paused, cancelled, etc.).
        """
        queue = self._bridge.async_subscribe(
            "steps:getByTask",
            {"task_id": task_id},
        )
        while True:
            steps_snapshot = await queue.get()
            if not isinstance(steps_snapshot, list):
                continue

            has_assigned = any(s.get("status") == StepStatus.ASSIGNED for s in steps_snapshot)
            if has_assigned:
                return True

            # If no longer waiting on human + blocked, stop watching
            has_human_pending = any(
                s.get("status") in (StepStatus.WAITING_HUMAN, StepStatus.RUNNING)
                for s in steps_snapshot
                if s.get("workflow_step_type") == "human" or s.get("assigned_agent") == "human"
            )
            has_blocked = any(s.get("status") == StepStatus.BLOCKED for s in steps_snapshot)
            if not (has_human_pending and has_blocked):
                return False

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
        step_tasks: dict[str, asyncio.Task[Any]] = {}
        for step in steps:
            step_id = str(step.get("id", ""))
            step_tasks[step_id] = asyncio.create_task(
                self._execute_step(task_id, step), name=f"step-{step_id}"
            )

        monitor = asyncio.create_task(self._monitor_step_cancellation(task_id, step_tasks))
        try:
            results = await asyncio.gather(*step_tasks.values(), return_exceptions=True)
        finally:
            monitor.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await monitor

        for step, result in zip(steps, results, strict=False):
            if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                logger.error(
                    "[dispatcher] Step '%s' failed in parallel group: %s",
                    step.get("title", step.get("id", "<unknown-step>")),
                    result,
                )

    async def _monitor_step_cancellation(
        self, task_id: str, step_tasks: dict[str, asyncio.Task[Any]]
    ) -> None:
        """Watch for externally-crashed steps and cancel their asyncio Tasks.

        Uses the existing async_subscribe infrastructure (same pattern as
        TaskExecutor and orchestrator loops) instead of a manual polling loop.
        """
        active = dict(step_tasks)  # shallow copy — we mutate this
        queue = self._bridge.async_subscribe(
            "steps:getByTask",
            {"task_id": task_id},
            poll_interval=2.0,
        )
        try:
            while active:
                steps_snapshot = await queue.get()
                if not isinstance(steps_snapshot, list):
                    continue
                for step_data in steps_snapshot:
                    step_id = str(step_data.get("id", ""))
                    if step_id not in active:
                        continue
                    task = active[step_id]
                    if step_data.get("status") == StepStatus.CRASHED and not task.done():
                        logger.info(
                            "[dispatcher] Step %s externally crashed — cancelling task",
                            step_id,
                        )
                        await self._kill_step_process(task_id, step_id)
                        task.cancel()
                        del active[step_id]
        except asyncio.CancelledError:
            raise

    async def _kill_step_process(self, task_id: str, step_id: str) -> None:
        """Best-effort kill of the provider-cli subprocess for a step.

        After stopping the process, cleans up registry and parser so the
        session ID can be re-used on retry.
        """
        if self._provider_cli_control_plane is None:
            return
        mc_session_id = f"{task_id}-{step_id}"
        try:
            result = await self._provider_cli_control_plane.stop(mc_session_id)
            logger.info("[dispatcher] Kill result for %s: %s", mc_session_id, result)
        except Exception:
            logger.warning(
                "[dispatcher] Failed to kill process for session %s",
                mc_session_id,
                exc_info=True,
            )
        # Clean up registry so the session ID can be re-registered on retry
        self._provider_cli_control_plane.unregister_parser(mc_session_id)
        if self._provider_cli_registry is not None:
            self._provider_cli_registry.remove(mc_session_id)

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
        if is_orchestrator_agent(agent_name):
            logger.warning(
                "[dispatcher] Step '%s' assigned to orchestrator-agent; rerouting to '%s'",
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
        workflow_step_type = step.get("workflow_step_type")
        is_gate_step = _is_workflow_gate_step(workflow_step_type)

        if agent_name == "human" or is_gate_step:
            # Gate steps and human-assigned steps go to waiting_human immediately.
            # They stay there until a human explicitly acts via the dashboard.
            await asyncio.to_thread(
                self._bridge.update_step_status,
                step_id,
                StepStatus.WAITING_HUMAN,
            )
            logger.info(
                "[dispatcher] Step '%s' (agent=%s, type=%s) set to waiting_human, skipping dispatch",
                step_title,
                agent_name,
                workflow_step_type,
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

            # Dump the final interpolated prompt for debugging/analysis.
            try:
                from mc.contexts.execution.output_artifacts import write_prompt_log

                prompt_log_parts = [
                    "=== MC Step Prompt Log ===",
                    f"step_id: {step_id}",
                    f"step_title: {step_title}",
                    f"agent_name: {agent_name}",
                    f"agent_model: {agent_model}",
                    f"runner_type: {req.runner_type}",
                    f"memory_workspace: {memory_workspace}",
                    f"board_name: {board_name}",
                    f"predecessor_step_ids: {req.predecessor_step_ids}",
                    f"reasoning_level: {reasoning_level}",
                    "",
                    "=== AGENT PROMPT (system instructions) ===",
                    agent_prompt or "(none)",
                    "",
                    "=== DESCRIPTION (enriched context: files, thread, tags, review) ===",
                    execution_description or "(none)",
                    "",
                    "=== FILE MANIFEST ===",
                    str(req.file_manifest) if req.file_manifest else "(none)",
                    "",
                    "=== THREAD CONTEXT ===",
                    req.thread_context or "(none)",
                    "",
                    "=== TAG ATTRIBUTES ===",
                    req.tag_attributes or "(none)",
                    "",
                    "=== FINAL ASSEMBLED PROMPT (sent to agent) ===",
                    req.prompt or "(none)",
                ]
                await asyncio.to_thread(
                    write_prompt_log,
                    task_id,
                    "system_prompt_log_{DDHHMMSS}.txt",
                    "\n".join(prompt_log_parts),
                )
            except Exception:
                logger.warning(
                    "[dispatcher] Failed to write prompt log for step %s",
                    step_id,
                    exc_info=True,
                )

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
                task_description=execution_description or "",
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

            review_result = None
            if workflow_step_type == "review":
                from mc.domain.workflow.review_result import parse_review_result

                review_result = parse_review_result(result_content)

            # Collect artifacts and post structured completion message (Story 2.5).
            artifacts = await asyncio.to_thread(collect_output_artifacts, task_id, pre_snapshot)

            # Sync output file manifest to Convex (best-effort, non-blocking) (Story 6.2).
            try:
                await asyncio.to_thread(
                    self._bridge.sync_task_output_files,
                    task_id,
                    task_data,
                    agent_name,
                    step_id=step_id,
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

            if review_result is not None and review_result.verdict == "rejected":
                # ── Review loop limit enforcement ────────────────────────
                # Increment rejection count on the review step.
                rejection_count = await asyncio.to_thread(
                    self._bridge.increment_rejection_count, step_id
                )

                # Resolve the limit: workflow spec → global setting → hardcoded 5
                review_loop_limit = await self._resolve_review_loop_limit(task_id, task_data)

                if review_loop_limit != 0 and rejection_count >= review_loop_limit:
                    error_msg = (
                        f"Review limit reached ({rejection_count}/{review_loop_limit}). "
                        f"Requires human intervention."
                    )
                    logger.warning(
                        "[dispatcher] %s for review step '%s' on task %s",
                        error_msg,
                        step_title,
                        task_id,
                    )
                    await asyncio.to_thread(
                        self._bridge.send_message,
                        task_id,
                        "System",
                        AuthorType.SYSTEM,
                        f'Review step "{step_title}" exceeded the maximum rejection limit. '
                        f"{error_msg}",
                        MessageType.SYSTEM_EVENT,
                    )
                    raise RuntimeError(error_msg)

                raw_reject_target = (
                    step.get("on_reject_step_id") or review_result.recommended_return_step
                )
                if not raw_reject_target:
                    raise ValueError(
                        f"Review step '{step_title}' rejected without an onReject target"
                    )

                # Parse "key:Title" format — extract just the key part
                reject_target_key = raw_reject_target.split(":")[0].strip()

                # Resolve step key → Convex step ID.  on_reject_step_id stores
                # the workflow step key (e.g. "write"), not the real Convex _id.
                all_steps = await asyncio.to_thread(self._bridge.get_steps_by_task, task_id)
                resolved_target_id: str | None = None
                target_step_title = reject_target_key
                for s in all_steps:
                    if s.get("workflow_step_id") == reject_target_key:
                        resolved_target_id = str(s.get("id"))
                        target_step_title = s.get("title", reject_target_key)
                        break
                    # Also accept a raw Convex ID (defensive)
                    if str(s.get("id")) == reject_target_key:
                        resolved_target_id = reject_target_key
                        target_step_title = s.get("title", reject_target_key)
                        break
                if not resolved_target_id:
                    raise ValueError(
                        f"Review step '{step_title}' onReject target "
                        f"'{reject_target_key}' not found in task steps"
                    )

                await asyncio.to_thread(
                    self._bridge.update_step_status,
                    step_id,
                    StepStatus.BLOCKED,
                )
                await asyncio.to_thread(
                    self._bridge.update_step_status,
                    resolved_target_id,
                    StepStatus.ASSIGNED,
                )

                # Post rejection feedback to task thread for visibility
                issues_summary = (
                    "; ".join(review_result.issues[:3]) if review_result.issues else "see feedback"
                )
                await asyncio.to_thread(
                    self._bridge.send_message,
                    task_id,
                    agent_name,
                    AuthorType.AGENT,
                    f'Review rejected step "{target_step_title}". Issues: {issues_summary}. '
                    f'Returning to "{target_step_title}" for revision. '
                    f"(rejection {rejection_count}/{review_loop_limit if review_loop_limit else '∞'})",
                    MessageType.REVIEW_FEEDBACK,
                )

                await asyncio.to_thread(
                    self._bridge.create_activity,
                    ActivityEventType.REVIEW_FEEDBACK,
                    f"Review step '{step_title}' rejected; rerouting to '{target_step_title}'"
                    f" (rejection {rejection_count}/{review_loop_limit if review_loop_limit else '∞'})",
                    task_id,
                    agent_name,
                )

                logger.info(
                    "[dispatcher] Review rejection: '%s' → blocked, '%s' → assigned for revision"
                    " (rejection %d/%s)",
                    step_title,
                    target_step_title,
                    rejection_count,
                    review_loop_limit if review_loop_limit else "∞",
                )
                return []

            await asyncio.to_thread(
                self._bridge.update_step_status,
                step_id,
                StepStatus.COMPLETED,
            )
            await asyncio.to_thread(
                self._bridge.create_activity,
                (
                    ActivityEventType.REVIEW_APPROVED
                    if review_result is not None
                    else ActivityEventType.STEP_COMPLETED
                ),
                (
                    f"Review step approved: {step_title}"
                    if review_result is not None
                    else f"Agent {agent_name} completed step: {step_title}"
                ),
                task_id,
                agent_name,
            )

            unblocked_ids = await asyncio.to_thread(
                self._bridge.check_and_unblock_dependents, step_id
            )
            if not isinstance(unblocked_ids, list):
                return []
            return [str(unblocked_id) for unblocked_id in unblocked_ids]
        except asyncio.CancelledError:
            logger.info("[dispatcher] Step '%s' cancelled (user stop)", step_title)
            raise  # propagate to gather
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
