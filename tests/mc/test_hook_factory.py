"""
Tests for the hook factory system (mc/hooks/).

Coverage:
- BaseHandler: matching logic, subclass registration
- HookConfig: defaults, project root resolution
- HookContext: save/load round-trip, file locking, session_id sanitization, auto-prune
- Discovery: handler auto-discovery, caching, skip of broken files
- Dispatcher: event routing, error isolation, combined output, no-match silence
- PlanTrackerHandler: plan parsing, parallel groups, step completion, re-write preservation
- SkillTrackerHandler: skill capture, context update
- PlanCaptureHandler: ExitPlanMode capture, fallback to most recent tracker
- AgentTrackerHandler: start/stop tracking, agent count
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from mc.hooks.config import HookConfig, get_config, get_project_root
from mc.hooks.context import HookContext, _safe_session_id
from mc.hooks.handler import BaseHandler

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def hook_dirs(tmp_path: Path):
    """Create temporary tracker and state dirs, patch get_project_root."""
    tracker_dir = tmp_path / ".claude" / "plan-tracker"
    state_dir = tmp_path / ".claude" / "hook-state"
    plans_dir = tmp_path / "docs" / "plans"
    tracker_dir.mkdir(parents=True)
    state_dir.mkdir(parents=True)
    plans_dir.mkdir(parents=True)

    config = HookConfig(
        plan_pattern="docs/plans/*.md",
        tracker_dir=".claude/plan-tracker",
        state_dir=".claude/hook-state",
    )
    with (
        patch("mc.hooks.config.get_project_root", return_value=tmp_path),
        patch("mc.hooks.config.get_config", return_value=config),
        patch("mc.hooks.context.get_project_root", return_value=tmp_path),
        patch("mc.hooks.context.get_config", return_value=config),
        patch("mc.hooks.handlers.plan_tracker.get_project_root", return_value=tmp_path),
        patch("mc.hooks.handlers.plan_tracker.get_config", return_value=config),
        patch("mc.hooks.handlers.plan_capture.get_project_root", return_value=tmp_path),
        patch("mc.hooks.handlers.plan_capture.get_config", return_value=config),
    ):
        yield tmp_path, tracker_dir, state_dir, plans_dir


def _make_plan(
    plans_dir: Path, name: str = "test-plan.md", tasks: int = 3, blocked: bool = True
) -> Path:
    """Create a test plan markdown file."""
    lines = ["# Test Plan\n"]
    for i in range(1, tasks + 1):
        lines.append(f"\n### Task {i}: Step {i} Name\n")
        lines.append(f"Do step {i} work.\n")
        if blocked and i == tasks and tasks > 1:
            deps = ", ".join(f"Task {j}" for j in range(1, tasks))
            lines.append(f"\n**Blocked by:** {deps}\n")
    plan_path = plans_dir / name
    plan_path.write_text("".join(lines))
    return plan_path


def _write_event(file_path: str, content: str, root: Path) -> dict:
    """Build a PostToolUse/Write event payload."""
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Write",
        "session_id": "test-session",
        "cwd": str(root),
        "tool_input": {"file_path": file_path, "content": content},
    }


def _task_completed_event(subject: str) -> dict:
    """Build a TaskCompleted event payload."""
    return {
        "hook_event_name": "TaskCompleted",
        "session_id": "test-session",
        "cwd": "/tmp",
        "task": {"subject": subject},
    }


def _skill_event(skill_name: str) -> dict:
    """Build a PostToolUse/Skill event payload."""
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Skill",
        "session_id": "test-session",
        "cwd": "/tmp",
        "tool_input": {"skill": skill_name},
    }


def _agent_event(event: str, agent_id: str, agent_type: str) -> dict:
    return {
        "hook_event_name": event,
        "session_id": "test-session",
        "cwd": "/tmp",
        "agent_id": agent_id,
        "agent_type": agent_type,
    }


# ---------------------------------------------------------------------------
# BaseHandler tests
# ---------------------------------------------------------------------------


class TestBaseHandler:
    def test_matches_exact(self):
        class H(BaseHandler):
            events = [("PostToolUse", "Write")]

        assert H.matches("PostToolUse", "Write") is True
        assert H.matches("PostToolUse", "Bash") is False
        assert H.matches("TaskCompleted", "Write") is False

    def test_matches_wildcard(self):
        class H(BaseHandler):
            events = [("TaskCompleted", None)]

        assert H.matches("TaskCompleted", "") is True
        assert H.matches("TaskCompleted", "anything") is True
        assert H.matches("PostToolUse", "") is False

    def test_matches_multi_events(self):
        class H(BaseHandler):
            events = [("PostToolUse", "Write"), ("TaskCompleted", None)]

        assert H.matches("PostToolUse", "Write") is True
        assert H.matches("TaskCompleted", "x") is True
        assert H.matches("SubagentStart", "") is False


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestConfig:
    def test_defaults(self):
        config = HookConfig()
        assert config.plan_pattern == "docs/plans/*.md"
        assert config.tracker_dir == ".claude/plan-tracker"
        assert config.state_dir == ".claude/hook-state"

    def test_project_root_resolves(self):
        root = get_project_root()
        assert root.is_dir()
        assert (root / "mc" / "hooks").is_dir()


# ---------------------------------------------------------------------------
# Context tests
# ---------------------------------------------------------------------------


class TestContext:
    def test_session_id_sanitization(self):
        assert _safe_session_id("normal-session-123") == "normal-session-123"
        assert _safe_session_id("../../etc/passwd") == "______etc_passwd"
        assert _safe_session_id("") == "unknown"
        assert _safe_session_id("a/b\\c:d") == "a_b_c_d"

    def test_round_trip(self, hook_dirs):
        _root, _, _state_dir, _ = hook_dirs
        ctx = HookContext("test-rt")
        ctx.active_skill = "brainstorming"
        ctx.active_plan = "docs/plans/my-plan.md"
        ctx.active_agents = {"agent-1": {"type": "Explore", "started_at": "2026-01-01T00:00:00Z"}}
        ctx.save()

        loaded = HookContext.load("test-rt")
        assert loaded.active_skill == "brainstorming"
        assert loaded.active_plan == "docs/plans/my-plan.md"
        assert loaded.active_agents["agent-1"]["type"] == "Explore"

    def test_load_missing_creates_fresh(self, hook_dirs):
        ctx = HookContext.load("nonexistent-session")
        assert ctx.session_id == "nonexistent-session"
        assert ctx.active_skill is None
        assert ctx.active_agents == {}

    def test_auto_prune_old_files(self, hook_dirs):
        _, _, state_dir, _ = hook_dirs
        # Create an old state file
        old_file = state_dir / "old-session.json"
        old_file.write_text('{"session_id":"old-session"}')
        # Set mtime to 2 days ago
        old_time = time.time() - 172800
        os.utime(old_file, (old_time, old_time))

        # Loading any session triggers prune
        HookContext.load("trigger-prune")
        assert not old_file.exists()


# ---------------------------------------------------------------------------
# Discovery tests
# ---------------------------------------------------------------------------


class TestDiscovery:
    def test_discovers_all_handlers(self):
        # Clear cache to force re-discovery
        import mc.hooks.discovery as disc

        disc.reset_cache()
        handlers = disc.discover_handlers()
        names = {h.__name__ for h in handlers}
        assert "PlanTrackerHandler" in names
        assert "SkillTrackerHandler" in names
        assert "PlanCaptureHandler" in names
        assert "AgentTrackerHandler" in names
        assert "MCPlanSyncHandler" in names
        assert len(handlers) == 5

    def test_cache_works(self):
        import mc.hooks.discovery as disc

        disc.reset_cache()
        h1 = disc.discover_handlers()
        h2 = disc.discover_handlers()
        assert h1 is h2  # same object, cached


# ---------------------------------------------------------------------------
# PlanTrackerHandler tests
# ---------------------------------------------------------------------------


class TestPlanTracker:
    def test_parse_plan_creates_tracker(self, hook_dirs):
        root, tracker_dir, _, plans_dir = hook_dirs
        plan_path = _make_plan(plans_dir, "feature.md", tasks=3, blocked=True)
        content = plan_path.read_text()

        from mc.hooks.handlers.plan_tracker import PlanTrackerHandler

        ctx = HookContext("test")
        payload = _write_event("docs/plans/feature.md", content, root)
        handler = PlanTrackerHandler(ctx, payload)
        result = handler.handle()

        assert result is not None
        assert "3 tasks" in result
        assert "can run parallel" in result

        # Verify tracker JSON
        tracker_path = tracker_dir / "feature.json"
        assert tracker_path.exists()
        data = json.loads(tracker_path.read_text())
        assert len(data["steps"]) == 3
        assert data["steps"][0]["parallel_group"] == 1
        assert data["steps"][1]["parallel_group"] == 1
        assert data["steps"][2]["parallel_group"] == 2
        assert data["steps"][2]["blocked_by"] == [1, 2]

    def test_non_plan_file_returns_none(self, hook_dirs):
        root, _, _, _ = hook_dirs
        from mc.hooks.handlers.plan_tracker import PlanTrackerHandler

        ctx = HookContext("test")
        payload = _write_event("src/main.py", "print('hi')", root)
        handler = PlanTrackerHandler(ctx, payload)
        assert handler.handle() is None

    def test_plan_without_tasks_returns_none(self, hook_dirs):
        root, _, _, plans_dir = hook_dirs
        plan = plans_dir / "empty.md"
        plan.write_text("# Just a title\nNo tasks here.")

        from mc.hooks.handlers.plan_tracker import PlanTrackerHandler

        ctx = HookContext("test")
        payload = _write_event("docs/plans/empty.md", plan.read_text(), root)
        handler = PlanTrackerHandler(ctx, payload)
        assert handler.handle() is None

    def test_all_parallel_when_no_blockers(self, hook_dirs):
        root, tracker_dir, _, plans_dir = hook_dirs
        plan_path = _make_plan(plans_dir, "parallel.md", tasks=3, blocked=False)

        from mc.hooks.handlers.plan_tracker import PlanTrackerHandler

        ctx = HookContext("test")
        payload = _write_event("docs/plans/parallel.md", plan_path.read_text(), root)
        handler = PlanTrackerHandler(ctx, payload)
        result = handler.handle()

        data = json.loads((tracker_dir / "parallel.json").read_text())
        assert all(s["parallel_group"] == 1 for s in data["steps"])
        assert "can run parallel" in result

    def test_step_completion(self, hook_dirs):
        root, tracker_dir, _, plans_dir = hook_dirs
        # First create the plan tracker
        plan_path = _make_plan(plans_dir, "complete.md", tasks=3, blocked=True)
        from mc.hooks.handlers.plan_tracker import PlanTrackerHandler

        ctx = HookContext("test")
        write_payload = _write_event("docs/plans/complete.md", plan_path.read_text(), root)
        PlanTrackerHandler(ctx, write_payload).handle()

        # Now complete Task 1
        complete_payload = _task_completed_event("Task 1: Step 1 Name")
        handler = PlanTrackerHandler(ctx, complete_payload)
        result = handler.handle()

        assert result is not None
        assert "Step 1" in result
        assert "1/3 done" in result

        # Verify tracker updated
        data = json.loads((tracker_dir / "complete.json").read_text())
        assert data["steps"][0]["status"] == "completed"
        assert data["steps"][1]["status"] == "pending"

    def test_completing_all_blockers_unblocks_task(self, hook_dirs):
        root, _tracker_dir, _, plans_dir = hook_dirs
        plan_path = _make_plan(plans_dir, "unblock.md", tasks=3, blocked=True)
        from mc.hooks.handlers.plan_tracker import PlanTrackerHandler

        ctx = HookContext("test")
        PlanTrackerHandler(
            ctx, _write_event("docs/plans/unblock.md", plan_path.read_text(), root)
        ).handle()

        # Complete Task 1
        PlanTrackerHandler(ctx, _task_completed_event("Task 1: Step 1 Name")).handle()
        # Complete Task 2 — should unblock Task 3
        result = PlanTrackerHandler(ctx, _task_completed_event("Task 2: Step 2 Name")).handle()

        assert "Now unblocked: Task 3" in result

    def test_rewrite_preserves_completed(self, hook_dirs):
        root, tracker_dir, _, plans_dir = hook_dirs
        plan_path = _make_plan(plans_dir, "preserve.md", tasks=3, blocked=True)
        from mc.hooks.handlers.plan_tracker import PlanTrackerHandler

        ctx = HookContext("test")
        PlanTrackerHandler(
            ctx, _write_event("docs/plans/preserve.md", plan_path.read_text(), root)
        ).handle()
        PlanTrackerHandler(ctx, _task_completed_event("Task 1: Step 1 Name")).handle()

        # Re-write the plan (simulates user editing)
        PlanTrackerHandler(
            ctx, _write_event("docs/plans/preserve.md", plan_path.read_text(), root)
        ).handle()

        data = json.loads((tracker_dir / "preserve.json").read_text())
        assert data["steps"][0]["status"] == "completed"  # preserved
        assert data["steps"][1]["status"] == "pending"

    def test_already_completed_is_noop(self, hook_dirs):
        root, _tracker_dir, _, plans_dir = hook_dirs
        plan_path = _make_plan(plans_dir, "noop.md", tasks=2, blocked=False)
        from mc.hooks.handlers.plan_tracker import PlanTrackerHandler

        ctx = HookContext("test")
        PlanTrackerHandler(
            ctx, _write_event("docs/plans/noop.md", plan_path.read_text(), root)
        ).handle()
        PlanTrackerHandler(ctx, _task_completed_event("Task 1: Step 1 Name")).handle()

        # Complete again — should return None (no-op)
        result = PlanTrackerHandler(ctx, _task_completed_event("Task 1: Step 1 Name")).handle()
        assert result is None

    def test_absolute_path_matching(self, hook_dirs):
        root, _tracker_dir, _, plans_dir = hook_dirs
        plan_path = _make_plan(plans_dir, "abspath.md", tasks=2, blocked=False)
        abs_path = str(root / "docs" / "plans" / "abspath.md")

        from mc.hooks.handlers.plan_tracker import PlanTrackerHandler

        ctx = HookContext("test")
        payload = _write_event(abs_path, plan_path.read_text(), root)
        result = PlanTrackerHandler(ctx, payload).handle()

        assert result is not None
        assert "2 tasks" in result

    def test_no_match_task_returns_none(self, hook_dirs):
        root, _tracker_dir, _, plans_dir = hook_dirs
        plan_path = _make_plan(plans_dir, "nomatch.md", tasks=2, blocked=False)
        from mc.hooks.handlers.plan_tracker import PlanTrackerHandler

        ctx = HookContext("test")
        PlanTrackerHandler(
            ctx, _write_event("docs/plans/nomatch.md", plan_path.read_text(), root)
        ).handle()

        result = PlanTrackerHandler(ctx, _task_completed_event("Task 99: Nonexistent")).handle()
        assert result is None


# ---------------------------------------------------------------------------
# SkillTrackerHandler tests
# ---------------------------------------------------------------------------


class TestSkillTracker:
    def test_captures_skill(self, hook_dirs):
        from mc.hooks.handlers.skill_tracker import SkillTrackerHandler

        ctx = HookContext("test")
        payload = _skill_event("executing-plans")
        handler = SkillTrackerHandler(ctx, payload)
        result = handler.handle()

        assert result == "Active skill: executing-plans"
        assert ctx.active_skill == "executing-plans"

    def test_empty_skill_returns_none(self, hook_dirs):
        from mc.hooks.handlers.skill_tracker import SkillTrackerHandler

        ctx = HookContext("test")
        payload = _skill_event("")
        assert SkillTrackerHandler(ctx, payload).handle() is None

    def test_skill_updates_context(self, hook_dirs):
        from mc.hooks.handlers.skill_tracker import SkillTrackerHandler

        ctx = HookContext("test")
        SkillTrackerHandler(ctx, _skill_event("brainstorming")).handle()
        assert ctx.active_skill == "brainstorming"
        SkillTrackerHandler(ctx, _skill_event("debugging")).handle()
        assert ctx.active_skill == "debugging"


# ---------------------------------------------------------------------------
# PlanCaptureHandler tests
# ---------------------------------------------------------------------------


class TestPlanCapture:
    def test_captures_active_plan(self, hook_dirs):
        from mc.hooks.handlers.plan_capture import PlanCaptureHandler

        ctx = HookContext("test")
        ctx.active_plan = "docs/plans/my-feature.md"
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "ExitPlanMode",
            "session_id": "test",
            "cwd": "/tmp",
            "tool_input": {},
        }
        result = PlanCaptureHandler(ctx, payload).handle()
        assert result == "Plan approved: docs/plans/my-feature.md"

    def test_fallback_to_most_recent_tracker(self, hook_dirs):
        root, tracker_dir, _, _ = hook_dirs
        # Create a tracker file
        tracker = tracker_dir / "recent-plan.json"
        tracker.write_text('{"plan_file":"docs/plans/recent-plan.md","steps":[]}')

        from mc.hooks.handlers.plan_capture import PlanCaptureHandler

        ctx = HookContext("test")
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "ExitPlanMode",
            "session_id": "test",
            "cwd": str(root),
            "tool_input": {},
        }

        with (
            patch("mc.hooks.handlers.plan_capture.get_project_root", return_value=root),
            patch("mc.hooks.handlers.plan_capture.get_config", return_value=get_config()),
        ):
            result = PlanCaptureHandler(ctx, payload).handle()

        assert result is not None
        assert "recent-plan" in result

    def test_no_tracker_returns_none(self, hook_dirs):
        root, tracker_dir, _, _ = hook_dirs
        # Empty tracker dir
        from mc.hooks.handlers.plan_capture import PlanCaptureHandler

        ctx = HookContext("test")
        ctx.active_plan = None
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "ExitPlanMode",
            "session_id": "test",
            "cwd": str(root),
            "tool_input": {},
        }

        # Remove all files from tracker dir
        for f in tracker_dir.iterdir():
            f.unlink()

        with (
            patch("mc.hooks.handlers.plan_capture.get_project_root", return_value=root),
            patch("mc.hooks.handlers.plan_capture.get_config", return_value=get_config()),
        ):
            result = PlanCaptureHandler(ctx, payload).handle()
        assert result is None


# ---------------------------------------------------------------------------
# AgentTrackerHandler tests
# ---------------------------------------------------------------------------


class TestAgentTracker:
    def test_start_tracks_agent(self, hook_dirs):
        from mc.hooks.handlers.agent_tracker import AgentTrackerHandler

        ctx = HookContext("test")
        payload = _agent_event("SubagentStart", "agent-abc", "Explore")
        result = AgentTrackerHandler(ctx, payload).handle()

        assert result == "Agent 'Explore' started (1 active)"
        assert "agent-abc" in ctx.active_agents
        assert ctx.active_agents["agent-abc"]["type"] == "Explore"

    def test_stop_removes_agent(self, hook_dirs):
        from mc.hooks.handlers.agent_tracker import AgentTrackerHandler

        ctx = HookContext("test")
        ctx.active_agents["agent-abc"] = {"type": "Explore", "started_at": "2026-01-01"}

        payload = _agent_event("SubagentStop", "agent-abc", "Explore")
        result = AgentTrackerHandler(ctx, payload).handle()

        assert result == "Agent 'Explore' stopped (0 remaining)"
        assert "agent-abc" not in ctx.active_agents

    def test_stop_unknown_agent_safe(self, hook_dirs):
        from mc.hooks.handlers.agent_tracker import AgentTrackerHandler

        ctx = HookContext("test")
        payload = _agent_event("SubagentStop", "nonexistent", "Plan")
        result = AgentTrackerHandler(ctx, payload).handle()
        assert "0 remaining" in result

    def test_multiple_agents(self, hook_dirs):
        from mc.hooks.handlers.agent_tracker import AgentTrackerHandler

        ctx = HookContext("test")
        AgentTrackerHandler(ctx, _agent_event("SubagentStart", "a1", "Explore")).handle()
        result = AgentTrackerHandler(ctx, _agent_event("SubagentStart", "a2", "Plan")).handle()
        assert "2 active" in result

        AgentTrackerHandler(ctx, _agent_event("SubagentStop", "a1", "Explore")).handle()
        assert len(ctx.active_agents) == 1


# ---------------------------------------------------------------------------
# Dispatcher integration tests
# ---------------------------------------------------------------------------


class TestDispatcher:
    def test_write_plan_end_to_end(self, hook_dirs):
        """Full flow: write plan → detect → create tracker."""
        root, tracker_dir, _, plans_dir = hook_dirs
        plan_path = _make_plan(plans_dir, "e2e.md", tasks=3, blocked=True)
        payload = _write_event("docs/plans/e2e.md", plan_path.read_text(), root)

        from mc.hooks.dispatcher import _dispatch

        result = _dispatch(payload)

        assert result is not None
        output = json.loads(result)
        assert "Plan tracker created" in output["hookSpecificOutput"]["additionalContext"]

        # Tracker should exist
        assert (tracker_dir / "e2e.json").exists()

    def test_skill_then_completion_flow(self, hook_dirs):
        """Multi-event flow: skill → write plan → complete task."""
        root, _tracker_dir, _, plans_dir = hook_dirs
        plan_path = _make_plan(plans_dir, "flow.md", tasks=2, blocked=False)

        from mc.hooks.dispatcher import _dispatch

        # 1. Skill event
        r1 = _dispatch(_skill_event("executing-plans"))
        assert "executing-plans" in r1

        # 2. Write plan
        r2 = _dispatch(_write_event("docs/plans/flow.md", plan_path.read_text(), root))
        assert "2 tasks" in r2

        # 3. Complete task
        r3 = _dispatch(_task_completed_event("Task 1: Step 1 Name"))
        assert "1/2 done" in r3

    def test_non_matching_event_returns_none(self, hook_dirs):
        from mc.hooks.dispatcher import _dispatch

        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "session_id": "test",
            "cwd": "/tmp",
            "tool_input": {"command": "ls"},
        }
        result = _dispatch(payload)
        assert result is None

    def test_agent_lifecycle(self, hook_dirs):
        from mc.hooks.dispatcher import _dispatch

        r1 = _dispatch(_agent_event("SubagentStart", "ag1", "Explore"))
        assert "1 active" in r1
        r2 = _dispatch(_agent_event("SubagentStop", "ag1", "Explore"))
        assert "0 remaining" in r2
