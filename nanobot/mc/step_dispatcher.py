"""
Step dispatcher for autonomous execution-plan steps.

This module executes materialized steps (stored in Convex) by dispatching
"assigned" steps, running each step with its assigned agent, and managing
step lifecycle transitions.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nanobot.mc.types import (
    ActivityEventType,
    AuthorType,
    GENERAL_AGENT_NAME,
    MessageType,
    StepStatus,
    TaskStatus,
    is_lead_agent,
)

if TYPE_CHECKING:
    from nanobot.mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)


def _as_positive_int(value: Any, default: int) -> int:
    """Convert a value to a positive int, with fallback."""
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _resolve_board_workspace(board_name: str, agent_name: str) -> Path:
    """Resolve and initialize the board-scoped memory workspace for an agent."""
    board_workspace = (
        Path.home() / ".nanobot" / "boards" / board_name / "agents" / agent_name
    )
    memory_dir = board_workspace / "memory"
    sessions_dir = board_workspace / "sessions"
    memory_dir.mkdir(parents=True, exist_ok=True)
    sessions_dir.mkdir(parents=True, exist_ok=True)

    memory_md = memory_dir / "MEMORY.md"
    if not memory_md.exists():
        global_memory = (
            Path.home() / ".nanobot" / "agents" / agent_name / "memory" / "MEMORY.md"
        )
        if global_memory.exists():
            shutil.copy2(global_memory, memory_md)
        else:
            memory_md.write_text("", encoding="utf-8")

    history_md = memory_dir / "HISTORY.md"
    if not history_md.exists():
        history_md.write_text("", encoding="utf-8")

    return board_workspace


def _load_agent_config(
    agent_name: str,
) -> tuple[str | None, str | None, list[str] | None]:
    """Load prompt, model and skills from an agent config."""
    from nanobot.mc.gateway import AGENTS_DIR
    from nanobot.mc.yaml_validator import validate_agent_file

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
    if is_lead_agent(agent_name):
        return agent_prompt

    orientation_path = Path.home() / ".nanobot" / "mc" / "agent-orientation.md"
    if not orientation_path.exists():
        return agent_prompt

    orientation = orientation_path.read_text(encoding="utf-8").strip()
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
    from nanobot.mc.thread_context import ThreadContextBuilder

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
    task_title: str,
    task_description: str,
    agent_skills: list[str] | None,
    board_name: str | None,
    memory_workspace: Path | None,
    task_id: str,
) -> str:
    """Lazily delegate step execution to executor helper."""
    from nanobot.mc.executor import _run_agent_on_task

    return await _run_agent_on_task(
        agent_name=agent_name,
        agent_prompt=agent_prompt,
        agent_model=agent_model,
        task_title=task_title,
        task_description=task_description,
        agent_skills=agent_skills,
        board_name=board_name,
        memory_workspace=memory_workspace,
        task_id=task_id,
    )


class StepDispatcher:
    """Dispatches and executes materialized task steps."""

    def __init__(self, bridge: ConvexBridge) -> None:
        self._bridge = bridge

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
        step_id = step.get("id")
        if not step_id:
            logger.warning("[dispatcher] Skipping step without id: %s", step)
            return []

        step_title = (step.get("title") or "Untitled Step").strip()
        step_description = step.get("description") or ""
        agent_name = (step.get("assigned_agent") or GENERAL_AGENT_NAME).strip()
        if is_lead_agent(agent_name):
            logger.warning(
                "[dispatcher] Step '%s' assigned to lead-agent; rerouting to '%s'",
                step_title,
                GENERAL_AGENT_NAME,
            )
            agent_name = GENERAL_AGENT_NAME

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
            agent_prompt, agent_model, agent_skills = _load_agent_config(agent_name)
            agent_prompt = _maybe_inject_orientation(agent_name, agent_prompt)

            thread_messages = await asyncio.to_thread(
                self._bridge.get_task_messages, task_id
            )
            # Resolve predecessor step IDs from the step's blockedBy list (AC #3, AC #6).
            predecessor_step_ids: list[str] = [
                str(pid) for pid in (step.get("blocked_by") or []) if pid
            ]
            thread_context = _build_step_thread_context(
                thread_messages, predecessor_step_ids=predecessor_step_ids
            )

            task_data = await asyncio.to_thread(
                self._bridge.query,
                "tasks:getById",
                {"task_id": task_id},
            )
            task_data = task_data if isinstance(task_data, dict) else {}
            task_title = task_data.get("title", "Untitled Task")

            safe_task_id = re.sub(r"[^\w\-]", "_", task_id)
            files_dir = str(Path.home() / ".nanobot" / "tasks" / safe_task_id)
            output_dir = str(Path.home() / ".nanobot" / "tasks" / safe_task_id / "output")

            board_name: str | None = None
            memory_workspace: Path | None = None
            board_id = task_data.get("board_id")
            if board_id:
                board = await asyncio.to_thread(self._bridge.get_board_by_id, board_id)
                if isinstance(board, dict):
                    board_name = board.get("name")
                    if board_name:
                        memory_workspace = _resolve_board_workspace(board_name, agent_name)

            execution_description = (
                f'You are executing step: "{step_title}"\n'
                f"Step description: {step_description}\n\n"
                f'This step is part of task: "{task_title}"\n'
                f"Task workspace: {files_dir}\n"
                f"Save ALL output files to: {output_dir}\n"
                "Do NOT save output files outside this directory."
            )
            if thread_context:
                execution_description += f"\n{thread_context}"

            # Snapshot output dir before agent execution for artifact detection (Story 2.5).
            from nanobot.mc.executor import _snapshot_output_dir, _collect_output_artifacts
            pre_snapshot = await asyncio.to_thread(_snapshot_output_dir, task_id)

            result = await _run_step_agent(
                agent_name=agent_name,
                agent_prompt=agent_prompt,
                agent_model=agent_model,
                task_title=step_title,
                task_description=execution_description,
                agent_skills=agent_skills,
                board_name=board_name,
                memory_workspace=memory_workspace,
                task_id=task_id,
            )

            # Collect artifacts and post structured completion message (Story 2.5).
            artifacts = await asyncio.to_thread(
                _collect_output_artifacts, task_id, pre_snapshot
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
