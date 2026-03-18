"""Unit tests for StepDispatcher."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.contexts.execution.step_dispatcher import StepDispatcher
from mc.types import ActivityEventType, AuthorType, MessageType, ReviewPhase, StepStatus, TaskStatus


async def _sync_to_thread(func, *args, **kwargs):
    """Run to_thread payloads synchronously in tests."""
    return func(*args, **kwargs)


def _step(
    step_id: str,
    title: str,
    *,
    status: str = "assigned",
    parallel_group: int = 1,
    order: int = 1,
    blocked_by: list[str] | None = None,
    assigned_agent: str = "nanobot",
    **extra_fields: Any,
) -> dict[str, Any]:
    step = {
        "id": step_id,
        "task_id": "task-1",
        "title": title,
        "description": f"Do {title}",
        "assigned_agent": assigned_agent,
        "status": status,
        "parallel_group": parallel_group,
        "order": order,
        "blocked_by": blocked_by or [],
    }
    step.update(extra_fields)
    return step


def _make_stateful_bridge(
    steps: list[dict[str, Any]],
    dependency_map: dict[str, list[str]] | None = None,
) -> tuple[MagicMock, dict[str, dict[str, Any]]]:
    bridge = MagicMock()
    state = {step["id"]: dict(step) for step in steps}
    dependency_map = dependency_map or {}

    def _ordered_steps() -> list[dict[str, Any]]:
        sorted_steps = sorted(
            state.values(),
            key=lambda step: (int(step.get("parallel_group", 1)), int(step.get("order", 1))),
        )
        return [dict(step) for step in sorted_steps]

    def _update_step_status(step_id: str, status: str, error_message: str | None = None) -> None:
        state[step_id]["status"] = status
        if error_message is not None:
            state[step_id]["error_message"] = error_message

    def _check_and_unblock_dependents(step_id: str) -> list[str]:
        unblocked: list[str] = []
        for dependent_id in dependency_map.get(step_id, []):
            dependent = state.get(dependent_id)
            if not dependent or dependent.get("status") != StepStatus.BLOCKED:
                continue
            blocked_by_ids = dependent.get("blocked_by", [])
            if all(state[dep_id]["status"] == StepStatus.COMPLETED for dep_id in blocked_by_ids):
                dependent["status"] = StepStatus.ASSIGNED
                unblocked.append(dependent_id)
        return unblocked

    bridge.get_steps_by_task.side_effect = lambda _task_id: _ordered_steps()
    bridge.update_step_status.side_effect = _update_step_status
    bridge.check_and_unblock_dependents.side_effect = _check_and_unblock_dependents
    bridge.update_task_status.return_value = None
    bridge.transition_task_from_snapshot.return_value = {"kind": "applied"}
    bridge.create_activity.return_value = None
    bridge.get_task_messages.return_value = []
    bridge.query.return_value = {"title": "Main Task", "status": "in_progress"}
    bridge.get_board_by_id.return_value = None
    bridge.send_message.return_value = None
    bridge.post_step_completion.return_value = None
    bridge.sync_task_output_files.return_value = None

    return bridge, state


def _patch_executor_helpers():
    """Return a context manager stack that stubs out executor artifact helpers."""
    return (
        patch(
            "mc.contexts.execution.executor._snapshot_output_dir",
            return_value={},
        ),
        patch(
            "mc.contexts.execution.executor._collect_output_artifacts",
            return_value=[],
        ),
    )


def _make_step_execution_request(step: dict[str, Any]) -> Any:
    """Build a mock ExecutionRequest from a step dict for ContextBuilder mocking."""
    from mc.application.execution.request import EntityType, ExecutionRequest

    step_title = (step.get("title") or "Untitled Step").strip()
    step_description = step.get("description") or ""
    agent_name = (step.get("assigned_agent") or "nanobot").strip()
    task_id = step.get("task_id", "task-1")
    step_id = step.get("id", "")

    # Build a realistic execution description matching the unified pipeline
    from mc.application.execution.file_enricher import (
        build_file_context,
        resolve_task_dirs,
    )

    files_dir, output_dir = resolve_task_dirs(task_id)

    return ExecutionRequest(
        entity_type=EntityType.STEP,
        entity_id=step_id,
        task_id=task_id,
        title="Main Task",
        step_title=step_title,
        step_description=step_description,
        agent_name=agent_name,
        agent_prompt=None,
        agent_model=None,
        agent_skills=None,
        reasoning_level=None,
        description=build_file_context(
            [],
            files_dir,
            output_dir,
            is_step=True,
            step_title=step_title,
            step_description=step_description,
            task_title="Main Task",
        ),
        board_name=None,
        memory_workspace=None,
        files_dir=files_dir,
        output_dir=output_dir,
        file_manifest=[],
        task_data={"title": "Main Task", "status": "in_progress"},
        predecessor_step_ids=[str(pid) for pid in (step.get("blocked_by") or []) if pid],
        is_cc=False,
    )


def _patch_context_builder(bridge_or_query_return=None):
    """Return a patch that mocks ContextBuilder.build_step_context.

    The mock builds a realistic ExecutionRequest from the step dict
    passed to it, so the rest of the dispatcher logic works correctly.
    """

    async def _mock_build_step_context(self, task_id, step):
        return _make_step_execution_request(step)

    return patch(
        "mc.application.execution.context_builder.ContextBuilder.build_step_context",
        new=_mock_build_step_context,
    )


def _patch_context_builder_cc():
    """Return a patch that mocks ContextBuilder.build_step_context for CC steps."""

    async def _mock_build_step_context(self, task_id, step):
        req = _make_step_execution_request(step)
        from mc.types import AgentData

        req.is_cc = True
        req.model = "claude-sonnet-4-6"
        req.agent_model = "cc/claude-sonnet-4-6"
        req.agent = AgentData(
            name=step.get("assigned_agent") or "cc-agent",
            display_name="CC Agent",
            role="developer",
            backend="claude-code",
            model="claude-sonnet-4-6",
        )
        return req

    return patch(
        "mc.application.execution.context_builder.ContextBuilder.build_step_context",
        new=_mock_build_step_context,
    )


def _patch_context_builder_with_files(query_return):
    """Return a patch that mocks ContextBuilder.build_step_context with file data.

    Uses the task data from query_return to build file manifest into the request.
    """

    async def _mock_build_step_context(self, task_id, step):
        req = _make_step_execution_request(step)
        # Inject file data from the query_return
        raw_files = query_return.get("files") or []
        if raw_files:
            from mc.application.execution.file_enricher import (
                build_file_context,
                build_file_manifest,
            )

            req.files = raw_files
            req.file_manifest = build_file_manifest(raw_files)
            req.task_data = query_return
            req.description = build_file_context(
                req.file_manifest,
                req.files_dir,
                req.output_dir,
                is_step=True,
                step_title=req.step_title,
                step_description=req.step_description,
                task_title=query_return.get("title", "Main Task"),
                raw_files=raw_files,
            )
        return req

    return patch(
        "mc.application.execution.context_builder.ContextBuilder.build_step_context",
        new=_mock_build_step_context,
    )


class TestStepDispatcher:
    @pytest.mark.asyncio
    async def test_dispatch_cc_step_routes_through_execution_engine(self) -> None:
        bridge, _state = _make_stateful_bridge(
            [_step("step-cc-1", "Implement via CC", assigned_agent="cc-agent")]
        )
        dispatcher = StepDispatcher(bridge)

        from mc.application.execution.request import ExecutionResult, RunnerType

        engine = MagicMock()
        engine.run = AsyncMock(return_value=ExecutionResult(success=True, output="cc step output"))
        snap_patch, collect_patch = _patch_executor_helpers()

        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder_cc(),
            patch.object(
                dispatcher,
                "_build_execution_engine",
                return_value=engine,
                create=True,
            ),
            snap_patch,
            collect_patch,
        ):
            await dispatcher.dispatch_steps("task-1", ["step-cc-1"])

        engine.run.assert_awaited_once()
        request = engine.run.await_args.args[0]
        assert request.runner_type == RunnerType.PROVIDER_CLI
        assert request.agent_name == "cc-agent"

    @pytest.mark.asyncio
    async def test_dispatch_single_step_completes_task(self) -> None:
        bridge, state = _make_stateful_bridge([_step("step-1", "Analyze", order=1)])
        dispatcher = StepDispatcher(bridge)

        snap_patch, collect_patch = _patch_executor_helpers()
        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder(),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                new=AsyncMock(return_value="step output"),
            ),
            snap_patch,
            collect_patch,
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        assert state["step-1"]["status"] == StepStatus.COMPLETED
        bridge.transition_task_from_snapshot.assert_called_once()
        status_call = bridge.transition_task_from_snapshot.call_args
        assert status_call.args[0]["status"] == TaskStatus.IN_PROGRESS
        assert status_call.args[1] == TaskStatus.REVIEW
        assert status_call.kwargs["reason"] == "All 1 steps completed"
        assert status_call.kwargs["review_phase"] == ReviewPhase.FINAL_APPROVAL
        bridge.create_activity.assert_any_call(
            ActivityEventType.TASK_DISPATCH_STARTED,
            "Steps dispatched in autonomous mode",
            "task-1",
        )
        bridge.create_activity.assert_any_call(
            ActivityEventType.STEP_STARTED,
            "Agent nanobot started step: Analyze",
            "task-1",
            "nanobot",
        )
        bridge.create_activity.assert_any_call(
            ActivityEventType.STEP_COMPLETED,
            "Agent nanobot completed step: Analyze",
            "task-1",
            "nanobot",
        )
        bridge.create_activity.assert_any_call(
            ActivityEventType.REVIEW_REQUESTED,
            "Execution completed -- all 1 steps finished; awaiting explicit approval",
            "task-1",
        )

    @pytest.mark.asyncio
    async def test_dispatch_single_step_completes_cron_task_to_done(self) -> None:
        bridge, state = _make_stateful_bridge([_step("step-1", "Analyze", order=1)])
        bridge.query.return_value = {
            "title": "Main Task",
            "status": "in_progress",
            "active_cron_job_id": "cron-job-1",
        }
        dispatcher = StepDispatcher(bridge)

        snap_patch, collect_patch = _patch_executor_helpers()
        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder(),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                new=AsyncMock(return_value="step output"),
            ),
            snap_patch,
            collect_patch,
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        assert state["step-1"]["status"] == StepStatus.COMPLETED
        bridge.transition_task_from_snapshot.assert_called_once()
        status_call = bridge.transition_task_from_snapshot.call_args
        assert status_call.args[1] == TaskStatus.DONE
        assert status_call.kwargs["reason"] == "All 1 steps completed"
        assert not any(
            call.args[0] == ActivityEventType.REVIEW_REQUESTED
            for call in bridge.create_activity.call_args_list
        )

    @pytest.mark.asyncio
    async def test_dispatch_human_step_stays_assigned_and_does_not_complete_task(self) -> None:
        """Human steps must NEVER spawn a process, change status, or auto-complete.

        The dispatcher must leave the step in 'assigned' status and return
        immediately — no status transition, no context building, no runner execution.
        """
        bridge, state = _make_stateful_bridge(
            [_step("step-human-1", "Approve output", assigned_agent="human", order=1)]
        )
        dispatcher = StepDispatcher(bridge)

        run_agent_mock = AsyncMock()

        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                new=run_agent_mock,
            ),
        ):
            await dispatcher.dispatch_steps("task-1", ["step-human-1"])

        # Step must remain in 'assigned' — the dispatcher must NOT change its status
        assert state["step-human-1"]["status"] == StepStatus.ASSIGNED
        # The agent runner must NEVER be called for human steps
        run_agent_mock.assert_not_called()
        # No step completion posted
        bridge.post_step_completion.assert_not_called()
        # Task must NOT transition to done
        assert not any(
            call.args[1] == TaskStatus.DONE for call in bridge.update_task_status.call_args_list
        )
        # Task must NOT transition to review (human step is not completed)
        assert not any(
            call.args[1] == TaskStatus.REVIEW for call in bridge.update_task_status.call_args_list
        )

    @pytest.mark.asyncio
    async def test_review_step_approved_verdict_completes_normally(self) -> None:
        bridge, state = _make_stateful_bridge(
            [
                _step(
                    "step-review-1",
                    "Review draft",
                    workflow_step_type="review",
                    review_spec_id="review-spec-1",
                    on_reject_step_id="step-write-1",
                )
            ]
        )
        dispatcher = StepDispatcher(bridge)

        snap_patch, collect_patch = _patch_executor_helpers()
        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder(),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                new=AsyncMock(
                    return_value=(
                        '{"verdict":"approved","issues":[],"strengths":["Looks good"],'
                        '"scores":{"overall":0.98},"vetoesTriggered":[],'
                        '"recommendedReturnStep":null}'
                    )
                ),
            ),
            snap_patch,
            collect_patch,
        ):
            await dispatcher.dispatch_steps("task-1", ["step-review-1"])

        assert state["step-review-1"]["status"] == StepStatus.COMPLETED
        bridge.post_step_completion.assert_called_once()

    @pytest.mark.asyncio
    async def test_review_step_rejection_blocks_review_and_reassigns_target(self) -> None:
        bridge, state = _make_stateful_bridge(
            [
                _step("step-write-1", "Rewrite draft", status=StepStatus.COMPLETED, order=1),
                _step(
                    "step-review-1",
                    "Review draft",
                    order=2,
                    workflow_step_type="review",
                    review_spec_id="review-spec-1",
                    on_reject_step_id="step-write-1",
                ),
            ]
        )
        dispatcher = StepDispatcher(bridge)

        snap_patch, collect_patch = _patch_executor_helpers()
        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder(),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                new=AsyncMock(
                    return_value=(
                        '{"verdict":"rejected","issues":["Fix alignment"],'
                        '"strengths":[],"scores":{"overall":0.41},'
                        '"vetoesTriggered":["alignment"],'
                        '"recommendedReturnStep":"step-write-1"}'
                    )
                ),
            ),
            snap_patch,
            collect_patch,
        ):
            await dispatcher.dispatch_steps("task-1", ["step-review-1"])

        assert state["step-review-1"]["status"] == StepStatus.BLOCKED
        bridge.update_step_status.assert_any_call("step-write-1", StepStatus.ASSIGNED)

    @pytest.mark.asyncio
    async def test_dispatch_parallel_group_runs_concurrently(self) -> None:
        bridge, state = _make_stateful_bridge(
            [
                _step("step-1", "Parallel A", parallel_group=1, order=1),
                _step("step-2", "Parallel B", parallel_group=1, order=2),
            ]
        )
        dispatcher = StepDispatcher(bridge)

        running = 0
        peak_running = 0

        async def _run_agent(*args, **kwargs):
            nonlocal running, peak_running
            running += 1
            peak_running = max(peak_running, running)
            await asyncio.sleep(0.01)
            running -= 1
            return f"done {kwargs['task_title']}"

        snap_patch, collect_patch = _patch_executor_helpers()
        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder(),
            patch("mc.contexts.execution.step_dispatcher._run_step_agent", side_effect=_run_agent),
            snap_patch,
            collect_patch,
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1", "step-2"])

        assert state["step-1"]["status"] == StepStatus.COMPLETED
        assert state["step-2"]["status"] == StepStatus.COMPLETED
        assert peak_running == 2

    @pytest.mark.asyncio
    async def test_dispatch_sequential_groups_order(self) -> None:
        bridge, state = _make_stateful_bridge(
            [
                _step("step-1", "Group 1", parallel_group=1, order=1),
                _step("step-2", "Group 2", parallel_group=2, order=2),
            ]
        )
        dispatcher = StepDispatcher(bridge)
        execution_order: list[str] = []

        async def _run_agent(*args, **kwargs):
            execution_order.append(kwargs["task_title"])
            return "ok"

        snap_patch, collect_patch = _patch_executor_helpers()
        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder(),
            patch("mc.contexts.execution.step_dispatcher._run_step_agent", side_effect=_run_agent),
            snap_patch,
            collect_patch,
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1", "step-2"])

        assert execution_order == ["Group 1", "Group 2"]
        assert state["step-1"]["status"] == StepStatus.COMPLETED
        assert state["step-2"]["status"] == StepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_step_crash_does_not_cancel_sibling(self) -> None:
        bridge, state = _make_stateful_bridge(
            [
                _step("step-1", "Crash", parallel_group=1, order=1),
                _step("step-2", "Sibling", parallel_group=1, order=2),
            ]
        )
        dispatcher = StepDispatcher(bridge)

        async def _run_agent(*args, **kwargs):
            title = kwargs["task_title"]
            if title == "Crash":
                await asyncio.sleep(0.005)
                raise RuntimeError("boom")
            await asyncio.sleep(0.01)
            return "ok"

        snap_patch, collect_patch = _patch_executor_helpers()
        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder(),
            patch("mc.contexts.execution.step_dispatcher._run_step_agent", side_effect=_run_agent),
            snap_patch,
            collect_patch,
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1", "step-2"])

        assert state["step-1"]["status"] == StepStatus.CRASHED
        assert state["step-2"]["status"] == StepStatus.COMPLETED
        bridge.update_task_status.assert_any_call(
            "task-1",
            TaskStatus.CRASHED,
            "nanobot",
            'Step "Crash" crashed',
        )
        bridge.send_message.assert_any_call(
            "task-1",
            "System",
            AuthorType.SYSTEM,
            'Step "Crash" crashed:\n```\nRuntimeError: boom\n```\nAgent: nanobot',
            MessageType.SYSTEM_EVENT,
        )

    @pytest.mark.asyncio
    async def test_dependency_unblocking_triggers_dispatch(self) -> None:
        bridge, state = _make_stateful_bridge(
            [
                _step("step-1", "Root", status=StepStatus.ASSIGNED, parallel_group=1, order=1),
                _step(
                    "step-2",
                    "Blocked",
                    status=StepStatus.BLOCKED,
                    parallel_group=2,
                    order=2,
                    blocked_by=["step-1"],
                ),
            ],
            dependency_map={"step-1": ["step-2"]},
        )
        dispatcher = StepDispatcher(bridge)
        titles: list[str] = []

        async def _run_agent(*args, **kwargs):
            titles.append(kwargs["task_title"])
            return "ok"

        snap_patch, collect_patch = _patch_executor_helpers()
        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder(),
            patch("mc.contexts.execution.step_dispatcher._run_step_agent", side_effect=_run_agent),
            snap_patch,
            collect_patch,
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1", "step-2"])

        assert titles == ["Root", "Blocked"]
        assert state["step-1"]["status"] == StepStatus.COMPLETED
        assert state["step-2"]["status"] == StepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_all_steps_completed_transitions_task_to_done(self) -> None:
        bridge, _state = _make_stateful_bridge(
            [
                _step("step-1", "One", status=StepStatus.ASSIGNED, parallel_group=1, order=1),
                _step("step-2", "Two", status=StepStatus.ASSIGNED, parallel_group=1, order=2),
            ]
        )
        dispatcher = StepDispatcher(bridge)

        snap_patch, collect_patch = _patch_executor_helpers()
        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder(),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                new=AsyncMock(return_value="ok"),
            ),
            snap_patch,
            collect_patch,
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1", "step-2"])

        bridge.transition_task_from_snapshot.assert_called_once()
        status_call = bridge.transition_task_from_snapshot.call_args
        assert status_call.args[1] == TaskStatus.REVIEW
        assert status_call.kwargs["reason"] == "All 2 steps completed"
        assert status_call.kwargs["review_phase"] == ReviewPhase.FINAL_APPROVAL

    @pytest.mark.asyncio
    async def test_step_completion_calls_post_step_completion(self) -> None:
        """After a step runs successfully, post_step_completion is called (Story 2.5)."""
        bridge, _state = _make_stateful_bridge([_step("step-1", "Write Report", order=1)])
        dispatcher = StepDispatcher(bridge)

        snap_patch, collect_patch = _patch_executor_helpers()
        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder(),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                new=AsyncMock(return_value="Report written."),
            ),
            snap_patch,
            collect_patch,
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        # post_step_completion should be called instead of send_message for the success path
        bridge.post_step_completion.assert_called_once()
        call_args = bridge.post_step_completion.call_args
        assert call_args[0][0] == "task-1"  # task_id
        assert call_args[0][1] == "step-1"  # step_id
        assert call_args[0][2] == "nanobot"  # agent_name
        assert call_args[0][3] == "Report written."  # content

    @pytest.mark.asyncio
    async def test_step_completion_passes_artifacts(self) -> None:
        """Artifacts collected are forwarded to post_step_completion."""
        bridge, _state = _make_stateful_bridge([_step("step-1", "Analyze", order=1)])
        dispatcher = StepDispatcher(bridge)

        fake_artifacts = [
            {"path": "output/report.pdf", "action": "created", "description": "PDF, 10 KB"}
        ]

        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder(),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                new=AsyncMock(return_value="Analysis done."),
            ),
            patch("mc.contexts.execution.executor._snapshot_output_dir", return_value={}),
            patch(
                "mc.contexts.execution.executor._collect_output_artifacts",
                return_value=fake_artifacts,
            ),
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        bridge.post_step_completion.assert_called_once()
        call_args = bridge.post_step_completion.call_args
        # When artifacts is non-empty, it is passed as the last positional arg
        assert call_args[0][4] == fake_artifacts

    @pytest.mark.asyncio
    async def test_step_completion_no_artifacts_passes_none(self) -> None:
        """When no artifacts are produced, None is passed to post_step_completion."""
        bridge, _state = _make_stateful_bridge([_step("step-1", "Compute", order=1)])
        dispatcher = StepDispatcher(bridge)

        snap_patch, collect_patch = _patch_executor_helpers()
        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder(),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                new=AsyncMock(return_value="Computation done."),
            ),
            snap_patch,
            collect_patch,
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        bridge.post_step_completion.assert_called_once()
        call_args = bridge.post_step_completion.call_args
        # Empty artifacts list → None passed
        assert call_args[0][4] is None

    @pytest.mark.asyncio
    async def test_dispatch_failure_posts_system_message(self) -> None:
        """When dispatch_steps crashes entirely, a system message is posted."""
        bridge = MagicMock()
        bridge.create_activity.side_effect = RuntimeError("bridge down")
        bridge.send_message.return_value = None
        dispatcher = StepDispatcher(bridge)

        with patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread):
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        bridge.send_message.assert_called_once()
        call_args = bridge.send_message.call_args
        assert call_args[0][0] == "task-1"
        assert call_args[0][2] == AuthorType.SYSTEM
        assert "Step dispatch failed" in call_args[0][3]


class TestTaskFileManifestInjection:
    """Story 6.1: Verify task-level file manifest injected into execution_description."""

    @pytest.mark.asyncio
    async def test_step_with_task_files_includes_manifest_in_description(self) -> None:
        """Task-level file manifest is injected into execution_description when task has files."""
        bridge, _state = _make_stateful_bridge([_step("step-1", "Analyze", order=1)])
        query_data = {
            "title": "Main Task",
            "status": "in_progress",
            "files": [
                {
                    "name": "report.pdf",
                    "type": "application/pdf",
                    "size": 867328,
                    "subfolder": "attachments",
                    "uploaded_at": "2026-02-25T00:00:00Z",
                },
                {
                    "name": "notes.md",
                    "type": "text/markdown",
                    "size": 12288,
                    "subfolder": "attachments",
                    "uploaded_at": "2026-02-25T00:00:00Z",
                },
            ],
        }
        bridge.query.return_value = query_data
        dispatcher = StepDispatcher(bridge)

        captured_description: list[str] = []

        async def _capture_run_agent(*args: Any, **kwargs: Any) -> str:
            captured_description.append(kwargs["task_description"])
            return "done"

        snap_patch, collect_patch = _patch_executor_helpers()
        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder_with_files(query_data),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                side_effect=_capture_run_agent,
            ),
            snap_patch,
            collect_patch,
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        assert len(captured_description) == 1
        desc = captured_description[0]
        assert "2 file(s) in its manifest" in desc
        assert "report.pdf" in desc
        assert "notes.md" in desc
        assert "attachments" in desc
        assert "847 KB" in desc  # 867328 // 1024 = 847
        assert "12 KB" in desc  # 12288 // 1024 = 12
        assert "Review the file manifest" in desc

    @pytest.mark.asyncio
    async def test_step_without_task_files_does_not_include_manifest(self) -> None:
        """When a task has no files, no file manifest section appears in the description."""
        bridge, _state = _make_stateful_bridge([_step("step-1", "Compute", order=1)])
        bridge.query.return_value = {"title": "Main Task", "status": "in_progress", "files": []}
        dispatcher = StepDispatcher(bridge)

        captured_description: list[str] = []

        async def _capture_run_agent(*args: Any, **kwargs: Any) -> str:
            captured_description.append(kwargs["task_description"])
            return "done"

        snap_patch, collect_patch = _patch_executor_helpers()
        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder(),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                side_effect=_capture_run_agent,
            ),
            snap_patch,
            collect_patch,
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        assert len(captured_description) == 1
        desc = captured_description[0]
        assert "file(s) in its manifest" not in desc
        assert "File manifest:" not in desc

    @pytest.mark.asyncio
    async def test_step_without_task_files_key_does_not_include_manifest(self) -> None:
        """When a task dict has no 'files' key, no file manifest section appears."""
        bridge, _state = _make_stateful_bridge([_step("step-1", "Compute", order=1)])
        # Default _make_stateful_bridge returns {"title": "Main Task"} -- no 'files' key
        dispatcher = StepDispatcher(bridge)

        captured_description: list[str] = []

        async def _capture_run_agent(*args: Any, **kwargs: Any) -> str:
            captured_description.append(kwargs["task_description"])
            return "done"

        snap_patch, collect_patch = _patch_executor_helpers()
        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder(),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                side_effect=_capture_run_agent,
            ),
            snap_patch,
            collect_patch,
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        assert len(captured_description) == 1
        desc = captured_description[0]
        assert "file(s) in its manifest" not in desc
        assert "File manifest:" not in desc

    @pytest.mark.asyncio
    async def test_manifest_includes_human_readable_sizes(self) -> None:
        """Manifest summary includes human-readable sizes for various file sizes."""
        bridge, _state = _make_stateful_bridge([_step("step-1", "Analyze", order=1)])
        query_data = {
            "title": "Main Task",
            "status": "in_progress",
            "files": [
                {
                    "name": "tiny.txt",
                    "type": "text/plain",
                    "size": 512,
                    "subfolder": "attachments",
                    "uploaded_at": "2026-02-25T00:00:00Z",
                },
                {
                    "name": "medium.bin",
                    "type": "application/octet-stream",
                    "size": 1048576,
                    "subfolder": "attachments",
                    "uploaded_at": "2026-02-25T00:00:00Z",
                },
                {
                    "name": "large.zip",
                    "type": "application/zip",
                    "size": 2621440,
                    "subfolder": "attachments",
                    "uploaded_at": "2026-02-25T00:00:00Z",
                },
            ],
        }
        bridge.query.return_value = query_data
        dispatcher = StepDispatcher(bridge)

        captured_description: list[str] = []

        async def _capture_run_agent(*args: Any, **kwargs: Any) -> str:
            captured_description.append(kwargs["task_description"])
            return "done"

        snap_patch, collect_patch = _patch_executor_helpers()
        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder_with_files(query_data),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                side_effect=_capture_run_agent,
            ),
            snap_patch,
            collect_patch,
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        assert len(captured_description) == 1
        desc = captured_description[0]
        assert "0 KB" in desc  # 512 // 1024 = 0
        assert "1.0 MB" in desc  # 1048576 / (1024*1024) = 1.0
        assert "2.5 MB" in desc  # 2621440 / (1024*1024) = 2.5

    @pytest.mark.asyncio
    async def test_manifest_single_file_correct_count(self) -> None:
        """A task with one file shows '1 file(s) in its manifest'."""
        bridge, _state = _make_stateful_bridge([_step("step-1", "Process", order=1)])
        query_data = {
            "title": "Main Task",
            "status": "in_progress",
            "files": [
                {
                    "name": "report.pdf",
                    "type": "application/pdf",
                    "size": 51200,
                    "subfolder": "attachments",
                    "uploaded_at": "2026-02-25T00:00:00Z",
                },
            ],
        }
        bridge.query.return_value = query_data
        dispatcher = StepDispatcher(bridge)

        captured_description: list[str] = []

        async def _capture_run_agent(*args: Any, **kwargs: Any) -> str:
            captured_description.append(kwargs["task_description"])
            return "done"

        snap_patch, collect_patch = _patch_executor_helpers()
        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder_with_files(query_data),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                side_effect=_capture_run_agent,
            ),
            snap_patch,
            collect_patch,
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        assert len(captured_description) == 1
        desc = captured_description[0]
        assert "1 file(s) in its manifest" in desc
        assert "report.pdf" in desc
        assert "50 KB" in desc  # 51200 // 1024 = 50


class TestStepOutputFileSync:
    """Story 6.2: Verify sync_task_output_files is called BEFORE post_step_completion (AC 7)."""

    @pytest.mark.asyncio
    async def test_step_completion_calls_sync_task_output_files(self) -> None:
        """After a step completes, sync_task_output_files is called with correct args."""
        bridge, state = _make_stateful_bridge([_step("step-1", "Analyze", order=1)])
        bridge.sync_task_output_files.return_value = None
        dispatcher = StepDispatcher(bridge)

        snap_patch, collect_patch = _patch_executor_helpers()
        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder(),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                new=AsyncMock(return_value="analysis done"),
            ),
            snap_patch,
            collect_patch,
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        # sync_task_output_files must be called once with (task_id, task_data_dict, agent_name)
        bridge.sync_task_output_files.assert_called_once()
        call_args = bridge.sync_task_output_files.call_args
        assert call_args[0][0] == "task-1"  # task_id
        assert isinstance(call_args[0][1], dict)  # task_data is a dict
        assert call_args[0][2] == "nanobot"  # agent_name

        # Step must still be completed
        assert state["step-1"]["status"] == StepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_sync_output_files_failure_does_not_crash_step(self) -> None:
        """A sync_task_output_files failure must not crash the step or the dispatcher."""
        bridge, state = _make_stateful_bridge([_step("step-1", "Build", order=1)])
        bridge.sync_task_output_files.side_effect = RuntimeError("sync fail")
        dispatcher = StepDispatcher(bridge)

        snap_patch, collect_patch = _patch_executor_helpers()
        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder(),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                new=AsyncMock(return_value="build done"),
            ),
            snap_patch,
            collect_patch,
        ):
            # Should NOT raise even though sync raises RuntimeError
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        # Step must complete successfully despite the sync failure
        assert state["step-1"]["status"] == StepStatus.COMPLETED
        # Task must also complete
        bridge.transition_task_from_snapshot.assert_called_once()
        status_call = bridge.transition_task_from_snapshot.call_args
        assert status_call.args[1] == TaskStatus.REVIEW
        assert status_call.kwargs["reason"] == "All 1 steps completed"
        assert status_call.kwargs["review_phase"] == ReviewPhase.FINAL_APPROVAL

    @pytest.mark.asyncio
    async def test_sync_called_before_post_step_completion(self) -> None:
        """AC 7: sync_task_output_files must be called BEFORE post_step_completion.

        Regression guard: ensures future refactors cannot reorder these two calls
        without a test failure.
        """
        bridge, _state = _make_stateful_bridge([_step("step-1", "Report", order=1)])
        bridge.sync_task_output_files.return_value = None

        call_order: list[str] = []

        def _record_sync(*args: Any, **kwargs: Any) -> None:
            call_order.append("sync")

        def _record_post(*args: Any, **kwargs: Any) -> None:
            call_order.append("post_step_completion")

        bridge.sync_task_output_files.side_effect = _record_sync
        bridge.post_step_completion.side_effect = _record_post

        dispatcher = StepDispatcher(bridge)
        snap_patch, collect_patch = _patch_executor_helpers()
        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder(),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                new=AsyncMock(return_value="report done"),
            ),
            snap_patch,
            collect_patch,
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        assert call_order == ["sync", "post_step_completion"], (
            f"sync_task_output_files must be called before post_step_completion, "
            f"but actual order was: {call_order}"
        )

    @pytest.mark.asyncio
    async def test_sync_not_called_when_step_crashes(self) -> None:
        """sync_task_output_files must NOT be called when the step agent raises (crash path).

        Dev Note: The sync call is in the success path only. If the step crashes,
        output files may be incomplete/invalid, so the manifest must not be updated.
        """
        bridge, state = _make_stateful_bridge([_step("step-1", "Crash", order=1)])
        bridge.sync_task_output_files.return_value = None
        dispatcher = StepDispatcher(bridge)

        snap_patch, collect_patch = _patch_executor_helpers()
        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder(),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                new=AsyncMock(side_effect=RuntimeError("agent exploded")),
            ),
            snap_patch,
            collect_patch,
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        # Step must be marked crashed
        assert state["step-1"]["status"] == StepStatus.CRASHED
        # Sync must NOT be called on crash path — output may be incomplete
        bridge.sync_task_output_files.assert_not_called()

    @pytest.mark.asyncio
    async def test_model_error_result_marks_step_and_task_crashed(self) -> None:
        """Structured model errors must not escape as completed step output."""
        bridge, state = _make_stateful_bridge([_step("step-1", "Crash", order=1)])
        dispatcher = StepDispatcher(bridge)

        snap_patch, collect_patch = _patch_executor_helpers()
        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder(),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        content="Error calling Codex:",
                        is_error=True,
                        error_message="Error calling Codex:",
                    )
                ),
            ),
            snap_patch,
            collect_patch,
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        assert state["step-1"]["status"] == StepStatus.CRASHED
        bridge.post_step_completion.assert_not_called()
        bridge.update_task_status.assert_any_call(
            "task-1",
            TaskStatus.CRASHED,
            "nanobot",
            'Step "Crash" crashed',
        )
        assert not any(
            call_args[0][0] == ActivityEventType.STEP_COMPLETED
            for call_args in bridge.create_activity.call_args_list
        )

    @pytest.mark.asyncio
    async def test_runtime_step_crash_marks_parent_task_crashed(self) -> None:
        """A crashed step should push the parent task into crashed state."""
        bridge, state = _make_stateful_bridge([_step("step-1", "Crash", order=1)])
        dispatcher = StepDispatcher(bridge)

        snap_patch, collect_patch = _patch_executor_helpers()
        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder(),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                new=AsyncMock(side_effect=RuntimeError("agent exploded")),
            ),
            snap_patch,
            collect_patch,
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        assert state["step-1"]["status"] == StepStatus.CRASHED
        bridge.update_task_status.assert_any_call(
            "task-1",
            TaskStatus.CRASHED,
            "nanobot",
            'Step "Crash" crashed',
        )


class TestSupervisedModeSkipsDispatch:
    """Verify supervised mode guard at orchestrator level (AC4)."""

    @pytest.mark.asyncio
    async def test_supervised_mode_does_not_trigger_dispatch(self) -> None:
        from mc.runtime.orchestrator import TaskOrchestrator
        from mc.types import ExecutionPlan, ExecutionPlanStep

        bridge = MagicMock()
        bridge.list_agents.return_value = [
            {
                "name": "nanobot",
                "display_name": "Owl",
                "role": "general",
                "status": "active",
                "model": "test",
            }
        ]
        orchestrator = TaskOrchestrator(bridge)
        orchestrator._planning_worker._step_dispatcher = MagicMock()
        orchestrator._planning_worker._step_dispatcher.dispatch_steps = AsyncMock()

        task = {
            "id": "task-1",
            "title": "Supervised task",
            "description": "test",
            "status": "planning",
            "supervision_mode": "supervised",
        }

        plan = ExecutionPlan(
            steps=[
                ExecutionPlanStep(
                    temp_id="s1",
                    title="Step",
                    description="d",
                    assigned_agent="nanobot",
                    blocked_by=[],
                    parallel_group=1,
                    order=1,
                )
            ]
        )

        with (
            patch("mc.runtime.workers.planning.asyncio.to_thread", new=_sync_to_thread),
            patch("mc.runtime.workers.planning.asyncio.create_task") as mock_create_task,
            patch("mc.runtime.workers.planning.TaskPlanner") as planner_cls,
        ):
            planner = planner_cls.return_value
            planner.plan_task = AsyncMock(return_value=plan)
            await orchestrator._planning_worker.process_task(task)

        # Supervised mode should NOT trigger dispatch or materialization
        bridge.batch_create_steps.assert_not_called()
        bridge.kick_off_task.assert_not_called()
        orchestrator._planning_worker._step_dispatcher.dispatch_steps.assert_not_called()
        mock_create_task.assert_not_called()


class TestPausedTaskDispatch:
    """Story 7.4: Dispatcher respects paused task state (AC 7)."""

    @pytest.mark.asyncio
    async def test_dispatcher_skips_dispatch_when_task_is_paused(self) -> None:
        """AC 7: dispatcher skips new step dispatch when task status is 'review' (paused).

        Story 7.4: When a task is paused (status=review, no awaitingKickoff), the
        pre-dispatch check must see status != in_progress and skip the dispatch.
        The step must remain in 'assigned' status (not dispatched).
        """
        bridge, state = _make_stateful_bridge([_step("step-1", "Analyze", order=1)])
        # Simulate a paused task: bridge.query returns status=review
        bridge.query.return_value = {"title": "Main Task", "status": "review"}
        dispatcher = StepDispatcher(bridge)

        run_agent_called = False

        async def _should_not_run(*args: Any, **kwargs: Any) -> str:
            nonlocal run_agent_called
            run_agent_called = True
            return "should not be reached"

        snap_patch, collect_patch = _patch_executor_helpers()
        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder(),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent", side_effect=_should_not_run
            ),
            snap_patch,
            collect_patch,
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        # The step agent must NOT have been called — dispatch was skipped
        assert not run_agent_called, (
            "Step agent was called despite task being paused (review status)"
        )
        # Step must remain in 'assigned' status (not completed or crashed)
        assert state["step-1"]["status"] == StepStatus.ASSIGNED
        # Task must NOT be marked done
        bridge.update_task_status.assert_not_called()


class TestTaskLevelFileSummaryInDelegationContext:
    """Story 6.3: Task-level file summary (using _build_file_summary) in delegation context.

    These tests verify FR-F29: the step delegation context includes file metadata
    (number of files, types, total size, and names) from the task-level file summary
    produced by planner._build_file_summary().
    """

    @pytest.mark.asyncio
    async def test_step_execution_includes_task_level_file_summary_when_task_has_files(
        self,
    ) -> None:
        """AC #2: delegation context includes task-level file summary when task has files."""
        bridge, _state = _make_stateful_bridge([_step("step-1", "Analyze", order=1)])
        query_data = {
            "title": "Main Task",
            "status": "in_progress",
            "files": [
                {
                    "name": "invoice.pdf",
                    "type": "application/pdf",
                    "size": 867328,
                    "subfolder": "attachments",
                },
                {
                    "name": "notes.md",
                    "type": "text/markdown",
                    "size": 12288,
                    "subfolder": "attachments",
                },
            ],
        }
        bridge.query.return_value = query_data
        dispatcher = StepDispatcher(bridge)

        captured_description: list[str] = []

        async def _capture_run_agent(*args: Any, **kwargs: Any) -> str:
            captured_description.append(kwargs["task_description"])
            return "done"

        snap_patch, collect_patch = _patch_executor_helpers()
        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder_with_files(query_data),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                side_effect=_capture_run_agent,
            ),
            snap_patch,
            collect_patch,
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        assert len(captured_description) == 1
        desc = captured_description[0]
        # Task-level file summary from _build_file_summary() must appear
        assert "2 attached file(s)" in desc
        assert "invoice.pdf" in desc
        assert "application/pdf" in desc
        assert "notes.md" in desc
        assert "text/markdown" in desc
        # Executor delegation context must contain "Files available at:" (not planner advisory)
        assert "Files available at:" in desc
        assert "attachments" in desc
        # The planner-only routing advisory must NOT appear in executor delegation context
        assert "Consider file types when selecting the best agent" not in desc

    @pytest.mark.asyncio
    async def test_step_execution_excludes_task_level_file_summary_when_task_has_no_files(
        self,
    ) -> None:
        """AC #3: no file summary noise when task has no file attachments."""
        bridge, _state = _make_stateful_bridge([_step("step-1", "Compute", order=1)])
        bridge.query.return_value = {"title": "Main Task", "status": "in_progress", "files": []}
        dispatcher = StepDispatcher(bridge)

        captured_description: list[str] = []

        async def _capture_run_agent(*args: Any, **kwargs: Any) -> str:
            captured_description.append(kwargs["task_description"])
            return "done"

        snap_patch, collect_patch = _patch_executor_helpers()
        with (
            patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread),
            _patch_context_builder(),
            patch(
                "mc.contexts.execution.step_dispatcher._run_step_agent",
                side_effect=_capture_run_agent,
            ),
            snap_patch,
            collect_patch,
        ):
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        assert len(captured_description) == 1
        desc = captured_description[0]
        # No routing advisory noise when there are no files (AC #3)
        assert "Consider file types" not in desc
        assert "Files available at:" not in desc
