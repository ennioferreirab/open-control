"""Tests for SK.2: Convex as Source of Truth for Agent Skills at Dispatch.

Covers all three dispatch paths:
- executor._execute_task() nanobot path
- step_dispatcher nanobot path
- step_dispatcher CC path

Updated for Story 16.1: Tests now mock ContextBuilder (unified pipeline)
instead of the old per-module _load_agent_config / _maybe_inject_orientation.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.application.execution.request import EntityType, ExecutionRequest
from mc.types import AgentData

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _sync_to_thread(func, *args, **kwargs):
    """Run to_thread payloads synchronously in tests."""
    return func(*args, **kwargs)


def _make_bridge(convex_agent: dict | None = None):
    """Create a mock bridge with configurable get_agent_by_name return."""
    bridge = MagicMock()
    bridge.query = MagicMock(return_value=None)
    bridge.get_task_messages = MagicMock(return_value=[])
    bridge.get_agent_by_name = MagicMock(return_value=convex_agent)
    bridge.send_message = MagicMock(return_value=None)
    bridge.create_activity = MagicMock(return_value=None)
    bridge.update_task_status = MagicMock(return_value=None)
    bridge.mutation = MagicMock(return_value=None)
    bridge.write_agent_config = MagicMock(return_value=None)
    bridge.get_board_by_id = MagicMock(return_value=None)
    bridge.get_steps_by_task = MagicMock(return_value=[])
    bridge.update_step_status = MagicMock(return_value=None)
    bridge.check_and_unblock_dependents = MagicMock(return_value=[])
    bridge.post_step_completion = MagicMock(return_value=None)
    bridge.sync_task_output_files = MagicMock(return_value=None)
    return bridge


def _make_task_execution_request(
    *,
    agent_skills: list[str] | None = None,
    agent_name: str = "test-agent",
    agent_prompt: str | None = "test prompt",
    agent_model: str | None = "model-1",
    is_cc: bool = False,
    model: str | None = None,
    agent: AgentData | None = None,
) -> ExecutionRequest:
    """Build an ExecutionRequest for task-level tests."""
    return ExecutionRequest(
        entity_type=EntityType.TASK,
        entity_id="task-1",
        task_id="task-1",
        title="Test Task",
        description="A test task",
        agent_name=agent_name,
        agent_prompt=agent_prompt,
        agent_model=agent_model,
        agent_skills=agent_skills,
        is_cc=is_cc,
        model=model,
        agent=agent,
        files_dir="/tmp/test-files",
        output_dir="/tmp/test-output",
    )


def _make_step_execution_request(
    *,
    agent_skills: list[str] | None = None,
    agent_name: str = "test-agent",
    agent_prompt: str | None = "test prompt",
    agent_model: str | None = "model-1",
    is_cc: bool = False,
    model: str | None = None,
    agent: AgentData | None = None,
) -> ExecutionRequest:
    """Build an ExecutionRequest for step-level tests."""
    return ExecutionRequest(
        entity_type=EntityType.STEP,
        entity_id="step-1",
        task_id="task-1",
        title="Main Task",
        step_title="Test Step",
        step_description="A test step",
        description='You are executing step: "Test Step"\nStep description: A test step',
        agent_name=agent_name,
        agent_prompt=agent_prompt,
        agent_model=agent_model,
        agent_skills=agent_skills,
        is_cc=is_cc,
        model=model,
        agent=agent,
        files_dir="/tmp/test-files",
        output_dir="/tmp/test-output",
    )


@contextmanager
def _patch_task_context_builder(req: ExecutionRequest):
    """Mock ContextBuilder.build_task_context to return the given request."""
    with patch(
        "mc.application.execution.context_builder.ContextBuilder.build_task_context",
        new_callable=AsyncMock,
        return_value=req,
    ):
        yield


@contextmanager
def _patch_step_context_builder(req: ExecutionRequest):
    """Mock ContextBuilder.build_step_context to return the given request."""
    with patch(
        "mc.application.execution.context_builder.ContextBuilder.build_step_context",
        new_callable=AsyncMock,
        return_value=req,
    ):
        yield


# ===========================================================================
# Task 4a: Executor _execute_task() -- Convex skills override
# ===========================================================================


class TestExecutorSkillsOverride:
    """Test that executor._execute_task() passes skills from unified pipeline."""

    @pytest.mark.asyncio
    async def test_convex_skills_override_when_present(self):
        """When Convex agent has skills list, those skills should be used instead of YAML skills."""
        from mc.contexts.execution.executor import TaskExecutor

        bridge = _make_bridge()
        executor = TaskExecutor(bridge, on_task_completed=None)

        captured_skills = {}

        async def fake_run_agent_on_task(**kwargs):
            captured_skills["value"] = kwargs.get("agent_skills")
            return ("result", "session-key", MagicMock())

        req = _make_task_execution_request(agent_skills=["github", "memory"])

        with _patch_task_context_builder(req), \
             patch("mc.contexts.execution.executor._run_agent_on_task", side_effect=fake_run_agent_on_task), \
             patch.object(executor, "_load_agent_data", return_value=None), \
             patch("mc.contexts.execution.executor._snapshot_output_dir", return_value={}), \
             patch("mc.contexts.execution.executor._collect_output_artifacts", return_value=[]), \
             patch("mc.contexts.execution.executor.asyncio.to_thread", new=_sync_to_thread):
            try:
                await executor._execute_task(
                    task_id="task-1",
                    title="Test Task",
                    description="A test task",
                    agent_name="test-agent",
                    trust_level="autonomous",
                    task_data={},
                )
            except Exception:
                pass  # May fail in later stages, but we captured skills

        assert captured_skills.get("value") == ["github", "memory"]

    @pytest.mark.asyncio
    async def test_yaml_skills_kept_when_convex_returns_none(self):
        """When Convex agent has no skills field (None), YAML skills should be used."""
        from mc.contexts.execution.executor import TaskExecutor

        bridge = _make_bridge()
        executor = TaskExecutor(bridge, on_task_completed=None)

        captured_skills = {}

        async def fake_run_agent_on_task(**kwargs):
            captured_skills["value"] = kwargs.get("agent_skills")
            return ("result", "session-key", MagicMock())

        yaml_skills = ["yaml-skill-1", "yaml-skill-2"]
        req = _make_task_execution_request(agent_skills=yaml_skills)

        with _patch_task_context_builder(req), \
             patch("mc.contexts.execution.executor._run_agent_on_task", side_effect=fake_run_agent_on_task), \
             patch.object(executor, "_load_agent_data", return_value=None), \
             patch("mc.contexts.execution.executor._snapshot_output_dir", return_value={}), \
             patch("mc.contexts.execution.executor._collect_output_artifacts", return_value=[]), \
             patch("mc.contexts.execution.executor.asyncio.to_thread", new=_sync_to_thread):
            try:
                await executor._execute_task(
                    task_id="task-1",
                    title="Test Task",
                    description="A test task",
                    agent_name="test-agent",
                    trust_level="autonomous",
                    task_data={},
                )
            except Exception:
                pass

        assert captured_skills.get("value") == yaml_skills

    @pytest.mark.asyncio
    async def test_convex_empty_skills_overrides_yaml(self):
        """Empty list [] from Convex IS a valid override (meaning 'no skills')."""
        from mc.contexts.execution.executor import TaskExecutor

        bridge = _make_bridge()
        executor = TaskExecutor(bridge, on_task_completed=None)

        captured_skills = {}

        async def fake_run_agent_on_task(**kwargs):
            captured_skills["value"] = kwargs.get("agent_skills")
            return ("result", "session-key", MagicMock())

        req = _make_task_execution_request(agent_skills=[])

        with _patch_task_context_builder(req), \
             patch("mc.contexts.execution.executor._run_agent_on_task", side_effect=fake_run_agent_on_task), \
             patch.object(executor, "_load_agent_data", return_value=None), \
             patch("mc.contexts.execution.executor._snapshot_output_dir", return_value={}), \
             patch("mc.contexts.execution.executor._collect_output_artifacts", return_value=[]), \
             patch("mc.contexts.execution.executor.asyncio.to_thread", new=_sync_to_thread):
            try:
                await executor._execute_task(
                    task_id="task-1",
                    title="Test Task",
                    description="A test task",
                    agent_name="test-agent",
                    trust_level="autonomous",
                    task_data={},
                )
            except Exception:
                pass

        assert captured_skills.get("value") == []


# ===========================================================================
# Task 4b: Step dispatcher nanobot path -- Convex skills override
# ===========================================================================


class TestStepDispatcherNanobotSkillsOverride:
    """Test that step_dispatcher nanobot path passes skills from unified pipeline."""

    @pytest.mark.asyncio
    async def test_convex_skills_override_in_nanobot_path(self):
        """When Convex agent has skills, dispatcher should use Convex skills."""
        from mc.contexts.execution.step_dispatcher import StepDispatcher

        bridge = _make_bridge()
        bridge.get_steps_by_task = MagicMock(return_value=[
            {
                "id": "step-1",
                "task_id": "task-1",
                "title": "Test Step",
                "description": "A test step",
                "assigned_agent": "test-agent",
                "status": "assigned",
                "parallel_group": 1,
                "order": 1,
                "blocked_by": [],
            }
        ])
        bridge.query = MagicMock(return_value={"title": "Main Task", "status": "in_progress"})

        dispatcher = StepDispatcher(bridge)

        captured_skills = {}

        async def fake_run_step_agent(**kwargs):
            captured_skills["value"] = kwargs.get("agent_skills")
            return "step output"

        req = _make_step_execution_request(agent_skills=["github", "memory"])

        with _patch_step_context_builder(req), \
             patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread), \
             patch("mc.contexts.execution.step_dispatcher._run_step_agent", new=AsyncMock(side_effect=fake_run_step_agent)), \
             patch("mc.contexts.execution.executor._snapshot_output_dir", return_value={}), \
             patch("mc.contexts.execution.executor._collect_output_artifacts", return_value=[]):
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        assert captured_skills.get("value") == ["github", "memory"]

    @pytest.mark.asyncio
    async def test_yaml_skills_kept_when_convex_none_nanobot_path(self):
        """When Convex has no skills field, YAML skills should be preserved."""
        from mc.contexts.execution.step_dispatcher import StepDispatcher

        bridge = _make_bridge()
        bridge.get_steps_by_task = MagicMock(return_value=[
            {
                "id": "step-1",
                "task_id": "task-1",
                "title": "Test Step",
                "description": "A test step",
                "assigned_agent": "test-agent",
                "status": "assigned",
                "parallel_group": 1,
                "order": 1,
                "blocked_by": [],
            }
        ])
        bridge.query = MagicMock(return_value={"title": "Main Task", "status": "in_progress"})

        dispatcher = StepDispatcher(bridge)

        captured_skills = {}

        async def fake_run_step_agent(**kwargs):
            captured_skills["value"] = kwargs.get("agent_skills")
            return "step output"

        yaml_skills = ["yaml-skill-1", "yaml-skill-2"]
        req = _make_step_execution_request(agent_skills=yaml_skills)

        with _patch_step_context_builder(req), \
             patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread), \
             patch("mc.contexts.execution.step_dispatcher._run_step_agent", new=AsyncMock(side_effect=fake_run_step_agent)), \
             patch("mc.contexts.execution.executor._snapshot_output_dir", return_value={}), \
             patch("mc.contexts.execution.executor._collect_output_artifacts", return_value=[]):
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        assert captured_skills.get("value") == yaml_skills

    @pytest.mark.asyncio
    async def test_convex_empty_skills_overrides_yaml_nanobot_path(self):
        """Empty list from Convex should override YAML skills in nanobot path."""
        from mc.contexts.execution.step_dispatcher import StepDispatcher

        bridge = _make_bridge()
        bridge.get_steps_by_task = MagicMock(return_value=[
            {
                "id": "step-1",
                "task_id": "task-1",
                "title": "Test Step",
                "description": "A test step",
                "assigned_agent": "test-agent",
                "status": "assigned",
                "parallel_group": 1,
                "order": 1,
                "blocked_by": [],
            }
        ])
        bridge.query = MagicMock(return_value={"title": "Main Task", "status": "in_progress"})

        dispatcher = StepDispatcher(bridge)

        captured_skills = {}

        async def fake_run_step_agent(**kwargs):
            captured_skills["value"] = kwargs.get("agent_skills")
            return "step output"

        req = _make_step_execution_request(agent_skills=[])

        with _patch_step_context_builder(req), \
             patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread), \
             patch("mc.contexts.execution.step_dispatcher._run_step_agent", new=AsyncMock(side_effect=fake_run_step_agent)), \
             patch("mc.contexts.execution.executor._snapshot_output_dir", return_value={}), \
             patch("mc.contexts.execution.executor._collect_output_artifacts", return_value=[]):
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        assert captured_skills.get("value") == []


# ===========================================================================
# Task 4c: Step dispatcher CC path -- Convex skills override on agent_data_for_cc
# ===========================================================================


class TestStepDispatcherCCSkillsOverride:
    """Test that step_dispatcher CC path overrides skills on agent_data_for_cc."""

    @pytest.mark.asyncio
    async def test_convex_skills_override_in_cc_path(self):
        """When Convex agent has skills, CC path should set agent_data_for_cc.skills."""
        from mc.contexts.execution.step_dispatcher import StepDispatcher

        convex_agent = {
            "skills": ["github", "memory"],
            "display_name": "Test Agent",
            "role": "agent",
        }
        bridge = _make_bridge(convex_agent)
        bridge.get_steps_by_task = MagicMock(return_value=[
            {
                "id": "step-1",
                "task_id": "task-1",
                "title": "Test Step",
                "description": "A test step",
                "assigned_agent": "test-agent",
                "status": "assigned",
                "parallel_group": 1,
                "order": 1,
                "blocked_by": [],
            }
        ])
        bridge.query = MagicMock(return_value={"title": "Main Task", "status": "in_progress"})

        dispatcher = StepDispatcher(bridge)

        captured_agent_data = {}

        def capture_ws_prepare(agent_name, agent_data, task_id, **kw):
            captured_agent_data["skills"] = list(agent_data.skills)
            raise RuntimeError("abort-after-capture")  # Stop execution cleanly

        # Build request with CC model detected
        cc_agent = AgentData(
            name="test-agent",
            display_name="Test Agent",
            role="agent",
            model="claude-sonnet-4-6",
            backend="claude-code",
            skills=["github", "memory"],
        )
        req = _make_step_execution_request(
            is_cc=True,
            model="claude-sonnet-4-6",
            agent=cc_agent,
            agent_skills=["github", "memory"],
        )

        with _patch_step_context_builder(req), \
             patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread), \
             patch("mc.contexts.execution.executor._snapshot_output_dir", return_value={}), \
             patch("mc.contexts.execution.executor._collect_output_artifacts", return_value=[]), \
             patch("claude_code.workspace.CCWorkspaceManager") as mock_ws:
            mock_ws.return_value.prepare.side_effect = capture_ws_prepare
            try:
                await dispatcher.dispatch_steps("task-1", ["step-1"])
            except Exception:
                pass  # Expected -- we abort after capture

        assert captured_agent_data.get("skills") == ["github", "memory"]

    @pytest.mark.asyncio
    async def test_cc_path_keeps_default_skills_when_convex_none(self):
        """When Convex has no skills, CC path should keep default skills."""
        from mc.contexts.execution.step_dispatcher import StepDispatcher

        convex_agent = {
            "display_name": "Test Agent",
            "role": "agent",
            # No "skills" key
        }
        bridge = _make_bridge(convex_agent)
        bridge.get_steps_by_task = MagicMock(return_value=[
            {
                "id": "step-1",
                "task_id": "task-1",
                "title": "Test Step",
                "description": "A test step",
                "assigned_agent": "test-agent",
                "status": "assigned",
                "parallel_group": 1,
                "order": 1,
                "blocked_by": [],
            }
        ])
        bridge.query = MagicMock(return_value={"title": "Main Task", "status": "in_progress"})

        dispatcher = StepDispatcher(bridge)

        captured_agent_data = {}

        def capture_ws_prepare(agent_name, agent_data, task_id, **kw):
            captured_agent_data["skills"] = list(agent_data.skills)
            raise RuntimeError("abort-after-capture")

        # Build request with CC model but no skills override
        cc_agent = AgentData(
            name="test-agent",
            display_name="Test Agent",
            role="agent",
            model="claude-sonnet-4-6",
            backend="claude-code",
        )
        req = _make_step_execution_request(
            is_cc=True,
            model="claude-sonnet-4-6",
            agent=cc_agent,
        )

        with _patch_step_context_builder(req), \
             patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread), \
             patch("mc.contexts.execution.executor._snapshot_output_dir", return_value={}), \
             patch("mc.contexts.execution.executor._collect_output_artifacts", return_value=[]), \
             patch("claude_code.workspace.CCWorkspaceManager") as mock_ws:
            mock_ws.return_value.prepare.side_effect = capture_ws_prepare
            try:
                await dispatcher.dispatch_steps("task-1", ["step-1"])
            except Exception:
                pass

        # Without Convex skills, agent_data_for_cc.skills should remain the default (empty list)
        assert captured_agent_data.get("skills") == []

    @pytest.mark.asyncio
    async def test_cc_path_empty_list_overrides(self):
        """Empty list from Convex should override existing skills in CC path."""
        from mc.contexts.execution.step_dispatcher import StepDispatcher

        convex_agent = {
            "skills": [],
            "display_name": "Test Agent",
            "role": "agent",
        }
        bridge = _make_bridge(convex_agent)
        bridge.get_steps_by_task = MagicMock(return_value=[
            {
                "id": "step-1",
                "task_id": "task-1",
                "title": "Test Step",
                "description": "A test step",
                "assigned_agent": "test-agent",
                "status": "assigned",
                "parallel_group": 1,
                "order": 1,
                "blocked_by": [],
            }
        ])
        bridge.query = MagicMock(return_value={"title": "Main Task", "status": "in_progress"})

        dispatcher = StepDispatcher(bridge)

        captured_agent_data = {}

        def capture_ws_prepare(agent_name, agent_data, task_id, **kw):
            captured_agent_data["skills"] = list(agent_data.skills)
            raise RuntimeError("abort-after-capture")

        # Build request with CC model and empty skills override
        cc_agent = AgentData(
            name="test-agent",
            display_name="Test Agent",
            role="agent",
            model="claude-sonnet-4-6",
            backend="claude-code",
            skills=[],
        )
        req = _make_step_execution_request(
            is_cc=True,
            model="claude-sonnet-4-6",
            agent=cc_agent,
            agent_skills=[],
        )

        with _patch_step_context_builder(req), \
             patch("mc.contexts.execution.step_dispatcher.asyncio.to_thread", new=_sync_to_thread), \
             patch("mc.contexts.execution.executor._snapshot_output_dir", return_value={}), \
             patch("mc.contexts.execution.executor._collect_output_artifacts", return_value=[]), \
             patch("claude_code.workspace.CCWorkspaceManager") as mock_ws:
            mock_ws.return_value.prepare.side_effect = capture_ws_prepare
            try:
                await dispatcher.dispatch_steps("task-1", ["step-1"])
            except Exception:
                pass

        assert captured_agent_data.get("skills") == []
