"""Tests for SK.2: Convex as Source of Truth for Agent Skills at Dispatch.

Covers all three dispatch paths:
- executor._execute_task() nanobot path
- step_dispatcher nanobot path
- step_dispatcher CC path
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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


# ===========================================================================
# Task 4a: Executor _execute_task() -- Convex skills override
# ===========================================================================


class TestExecutorSkillsOverride:
    """Test that executor._execute_task() overrides skills from Convex."""

    @pytest.mark.asyncio
    async def test_convex_skills_override_when_present(self):
        """When Convex agent has skills list, those skills should be used instead of YAML skills."""
        from mc.executor import TaskExecutor

        convex_agent = {
            "skills": ["github", "memory"],
            "prompt": "test prompt",
        }
        bridge = _make_bridge(convex_agent)

        executor = TaskExecutor(bridge, on_task_completed=None)

        # Track what skills are passed to _run_agent_on_task
        captured_skills = {}

        async def fake_run_agent_on_task(**kwargs):
            captured_skills["value"] = kwargs.get("agent_skills")
            return ("result", "session-key", MagicMock())

        with patch("mc.executor._run_agent_on_task", side_effect=fake_run_agent_on_task), \
             patch.object(executor, "_load_agent_config", return_value=("yaml prompt", "model-1", ["yaml-skill"])), \
             patch.object(executor, "_load_agent_data", return_value=None), \
             patch.object(executor, "_maybe_inject_orientation", side_effect=lambda name, prompt: prompt), \
             patch.object(executor, "_build_agent_roster", return_value=""), \
             patch("mc.executor.is_tier_reference", return_value=False), \
             patch("mc.executor.is_lead_agent", return_value=False), \
             patch("mc.executor.is_cc_model", return_value=False), \
             patch("mc.executor._snapshot_output_dir", return_value={}), \
             patch("mc.executor._collect_output_artifacts", return_value=[]), \
             patch("mc.executor.asyncio.to_thread", new=_sync_to_thread):
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
        from mc.executor import TaskExecutor

        convex_agent = {
            "prompt": "test prompt",
            # No "skills" key -- .get("skills") returns None
        }
        bridge = _make_bridge(convex_agent)

        executor = TaskExecutor(bridge, on_task_completed=None)

        captured_skills = {}

        async def fake_run_agent_on_task(**kwargs):
            captured_skills["value"] = kwargs.get("agent_skills")
            return ("result", "session-key", MagicMock())

        yaml_skills = ["yaml-skill-1", "yaml-skill-2"]

        with patch("mc.executor._run_agent_on_task", side_effect=fake_run_agent_on_task), \
             patch.object(executor, "_load_agent_config", return_value=("yaml prompt", "model-1", yaml_skills)), \
             patch.object(executor, "_load_agent_data", return_value=None), \
             patch.object(executor, "_maybe_inject_orientation", side_effect=lambda name, prompt: prompt), \
             patch.object(executor, "_build_agent_roster", return_value=""), \
             patch("mc.executor.is_tier_reference", return_value=False), \
             patch("mc.executor.is_lead_agent", return_value=False), \
             patch("mc.executor.is_cc_model", return_value=False), \
             patch("mc.executor._snapshot_output_dir", return_value={}), \
             patch("mc.executor._collect_output_artifacts", return_value=[]), \
             patch("mc.executor.asyncio.to_thread", new=_sync_to_thread):
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
        from mc.executor import TaskExecutor

        convex_agent = {
            "skills": [],
            "prompt": "test prompt",
        }
        bridge = _make_bridge(convex_agent)

        executor = TaskExecutor(bridge, on_task_completed=None)

        captured_skills = {}

        async def fake_run_agent_on_task(**kwargs):
            captured_skills["value"] = kwargs.get("agent_skills")
            return ("result", "session-key", MagicMock())

        with patch("mc.executor._run_agent_on_task", side_effect=fake_run_agent_on_task), \
             patch.object(executor, "_load_agent_config", return_value=("yaml prompt", "model-1", ["yaml-skill"])), \
             patch.object(executor, "_load_agent_data", return_value=None), \
             patch.object(executor, "_maybe_inject_orientation", side_effect=lambda name, prompt: prompt), \
             patch.object(executor, "_build_agent_roster", return_value=""), \
             patch("mc.executor.is_tier_reference", return_value=False), \
             patch("mc.executor.is_lead_agent", return_value=False), \
             patch("mc.executor.is_cc_model", return_value=False), \
             patch("mc.executor._snapshot_output_dir", return_value={}), \
             patch("mc.executor._collect_output_artifacts", return_value=[]), \
             patch("mc.executor.asyncio.to_thread", new=_sync_to_thread):
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
    """Test that step_dispatcher nanobot path overrides skills from Convex."""

    @pytest.mark.asyncio
    async def test_convex_skills_override_in_nanobot_path(self):
        """When Convex agent has skills, dispatcher should use Convex skills."""
        from mc.step_dispatcher import StepDispatcher

        convex_agent = {
            "skills": ["github", "memory"],
            "prompt": "test prompt",
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

        captured_skills = {}

        async def fake_run_step_agent(**kwargs):
            captured_skills["value"] = kwargs.get("agent_skills")
            return "step output"

        with patch("mc.step_dispatcher.asyncio.to_thread", new=_sync_to_thread), \
             patch("mc.step_dispatcher._load_agent_config", return_value=("yaml prompt", "model-1", ["yaml-skill"])), \
             patch("mc.step_dispatcher._maybe_inject_orientation", side_effect=lambda agent_name, prompt: prompt), \
             patch("mc.step_dispatcher._run_step_agent", new=AsyncMock(side_effect=fake_run_step_agent)), \
             patch("mc.step_dispatcher.is_tier_reference", return_value=False), \
             patch("mc.step_dispatcher.is_cc_model", return_value=False), \
             patch("mc.executor._snapshot_output_dir", return_value={}), \
             patch("mc.executor._collect_output_artifacts", return_value=[]):
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        assert captured_skills.get("value") == ["github", "memory"]

    @pytest.mark.asyncio
    async def test_yaml_skills_kept_when_convex_none_nanobot_path(self):
        """When Convex has no skills field, YAML skills should be preserved."""
        from mc.step_dispatcher import StepDispatcher

        convex_agent = {
            "prompt": "test prompt",
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

        captured_skills = {}

        async def fake_run_step_agent(**kwargs):
            captured_skills["value"] = kwargs.get("agent_skills")
            return "step output"

        yaml_skills = ["yaml-skill-1", "yaml-skill-2"]

        with patch("mc.step_dispatcher.asyncio.to_thread", new=_sync_to_thread), \
             patch("mc.step_dispatcher._load_agent_config", return_value=("yaml prompt", "model-1", yaml_skills)), \
             patch("mc.step_dispatcher._maybe_inject_orientation", side_effect=lambda agent_name, prompt: prompt), \
             patch("mc.step_dispatcher._run_step_agent", new=AsyncMock(side_effect=fake_run_step_agent)), \
             patch("mc.step_dispatcher.is_tier_reference", return_value=False), \
             patch("mc.step_dispatcher.is_cc_model", return_value=False), \
             patch("mc.executor._snapshot_output_dir", return_value={}), \
             patch("mc.executor._collect_output_artifacts", return_value=[]):
            await dispatcher.dispatch_steps("task-1", ["step-1"])

        assert captured_skills.get("value") == yaml_skills

    @pytest.mark.asyncio
    async def test_convex_empty_skills_overrides_yaml_nanobot_path(self):
        """Empty list from Convex should override YAML skills in nanobot path."""
        from mc.step_dispatcher import StepDispatcher

        convex_agent = {
            "skills": [],
            "prompt": "test prompt",
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

        captured_skills = {}

        async def fake_run_step_agent(**kwargs):
            captured_skills["value"] = kwargs.get("agent_skills")
            return "step output"

        with patch("mc.step_dispatcher.asyncio.to_thread", new=_sync_to_thread), \
             patch("mc.step_dispatcher._load_agent_config", return_value=("yaml prompt", "model-1", ["yaml-skill"])), \
             patch("mc.step_dispatcher._maybe_inject_orientation", side_effect=lambda agent_name, prompt: prompt), \
             patch("mc.step_dispatcher._run_step_agent", new=AsyncMock(side_effect=fake_run_step_agent)), \
             patch("mc.step_dispatcher.is_tier_reference", return_value=False), \
             patch("mc.step_dispatcher.is_cc_model", return_value=False), \
             patch("mc.executor._snapshot_output_dir", return_value={}), \
             patch("mc.executor._collect_output_artifacts", return_value=[]):
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
        from mc.step_dispatcher import StepDispatcher
        from mc.types import AgentData

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

        # Capture the agent_data_for_cc passed to workspace prepare
        original_prepare = None

        def capture_ws_prepare(agent_name, agent_data, task_id, **kw):
            captured_agent_data["skills"] = list(agent_data.skills)
            raise RuntimeError("abort-after-capture")  # Stop execution cleanly

        with patch("mc.step_dispatcher.asyncio.to_thread", new=_sync_to_thread), \
             patch("mc.step_dispatcher._load_agent_config", return_value=("yaml prompt", "cc/claude-sonnet-4-6", ["yaml-skill"])), \
             patch("mc.step_dispatcher._maybe_inject_orientation", side_effect=lambda agent_name, prompt: prompt), \
             patch("mc.step_dispatcher.is_tier_reference", return_value=False), \
             patch("mc.step_dispatcher.is_cc_model", return_value=True), \
             patch("mc.step_dispatcher.extract_cc_model_name", return_value="claude-sonnet-4-6"), \
             patch("mc.executor._snapshot_output_dir", return_value={}), \
             patch("mc.executor._collect_output_artifacts", return_value=[]), \
             patch("claude_code.workspace.CCWorkspaceManager") as MockWS:
            MockWS.return_value.prepare.side_effect = capture_ws_prepare
            try:
                await dispatcher.dispatch_steps("task-1", ["step-1"])
            except Exception:
                pass  # Expected -- we abort after capture

        assert captured_agent_data.get("skills") == ["github", "memory"]

    @pytest.mark.asyncio
    async def test_cc_path_keeps_default_skills_when_convex_none(self):
        """When Convex has no skills, CC path should keep default skills."""
        from mc.step_dispatcher import StepDispatcher
        from mc.types import AgentData

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

        with patch("mc.step_dispatcher.asyncio.to_thread", new=_sync_to_thread), \
             patch("mc.step_dispatcher._load_agent_config", return_value=("yaml prompt", "cc/claude-sonnet-4-6", ["yaml-skill"])), \
             patch("mc.step_dispatcher._maybe_inject_orientation", side_effect=lambda agent_name, prompt: prompt), \
             patch("mc.step_dispatcher.is_tier_reference", return_value=False), \
             patch("mc.step_dispatcher.is_cc_model", return_value=True), \
             patch("mc.step_dispatcher.extract_cc_model_name", return_value="claude-sonnet-4-6"), \
             patch("mc.executor._snapshot_output_dir", return_value={}), \
             patch("mc.executor._collect_output_artifacts", return_value=[]), \
             patch("claude_code.workspace.CCWorkspaceManager") as MockWS:
            MockWS.return_value.prepare.side_effect = capture_ws_prepare
            try:
                await dispatcher.dispatch_steps("task-1", ["step-1"])
            except Exception:
                pass

        # Without Convex skills, agent_data_for_cc.skills should remain the default (empty list)
        # since the CC path creates a fresh AgentData when no config.yaml exists
        assert captured_agent_data.get("skills") == []

    @pytest.mark.asyncio
    async def test_cc_path_empty_list_overrides(self):
        """Empty list from Convex should override existing skills in CC path."""
        from mc.step_dispatcher import StepDispatcher
        from mc.types import AgentData

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

        with patch("mc.step_dispatcher.asyncio.to_thread", new=_sync_to_thread), \
             patch("mc.step_dispatcher._load_agent_config", return_value=("yaml prompt", "cc/claude-sonnet-4-6", ["yaml-skill"])), \
             patch("mc.step_dispatcher._maybe_inject_orientation", side_effect=lambda agent_name, prompt: prompt), \
             patch("mc.step_dispatcher.is_tier_reference", return_value=False), \
             patch("mc.step_dispatcher.is_cc_model", return_value=True), \
             patch("mc.step_dispatcher.extract_cc_model_name", return_value="claude-sonnet-4-6"), \
             patch("mc.executor._snapshot_output_dir", return_value={}), \
             patch("mc.executor._collect_output_artifacts", return_value=[]), \
             patch("claude_code.workspace.CCWorkspaceManager") as MockWS:
            MockWS.return_value.prepare.side_effect = capture_ws_prepare
            try:
                await dispatcher.dispatch_steps("task-1", ["step-1"])
            except Exception:
                pass

        assert captured_agent_data.get("skills") == []
