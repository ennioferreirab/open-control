"""Tests for mc.hooks.context — HookContext lifecycle, persistence, pruning."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from mc.hooks.config import HookConfig
from mc.hooks.context import HookContext, _safe_session_id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def state_dirs(tmp_path: Path):
    """Set up temporary state directory and patch project root / config."""
    state_dir = tmp_path / ".claude" / "hook-state"
    state_dir.mkdir(parents=True)

    config = HookConfig(
        plan_pattern="docs/plans/*.md",
        tracker_dir=".claude/plan-tracker",
        state_dir=".claude/hook-state",
    )
    with (
        patch("mc.hooks.context.get_project_root", return_value=tmp_path),
        patch("mc.hooks.context.get_config", return_value=config),
    ):
        yield tmp_path, state_dir


# ---------------------------------------------------------------------------
# Session ID sanitization
# ---------------------------------------------------------------------------

class TestSafeSessionId:
    def test_normal_id(self):
        assert _safe_session_id("normal-session-123") == "normal-session-123"

    def test_path_traversal(self):
        assert _safe_session_id("../../etc/passwd") == "______etc_passwd"

    def test_empty_string(self):
        assert _safe_session_id("") == "unknown"

    def test_special_characters(self):
        assert _safe_session_id("a/b\\c:d") == "a_b_c_d"

    def test_underscores_and_hyphens_preserved(self):
        assert _safe_session_id("my_session-id") == "my_session-id"

    def test_spaces_replaced(self):
        assert _safe_session_id("has spaces") == "has_spaces"

    def test_dots_replaced(self):
        assert _safe_session_id("file.json") == "file_json"


# ---------------------------------------------------------------------------
# HookContext construction
# ---------------------------------------------------------------------------

class TestHookContextInit:
    def test_initial_state(self):
        ctx = HookContext("test-session")
        assert ctx.session_id == "test-session"
        assert ctx.active_skill is None
        assert ctx.active_plan is None
        assert ctx.active_agents == {}

    def test_to_dict(self):
        ctx = HookContext("test")
        ctx.active_skill = "debugging"
        ctx.active_plan = "docs/plans/my-plan.md"
        ctx.active_agents = {"a1": {"type": "Explore"}}

        d = ctx.to_dict()
        assert d["session_id"] == "test"
        assert d["active_skill"] == "debugging"
        assert d["active_plan"] == "docs/plans/my-plan.md"
        assert d["active_agents"]["a1"]["type"] == "Explore"

    def test_from_dict_full(self):
        data = {
            "session_id": "s1",
            "active_skill": "brainstorming",
            "active_plan": "docs/plans/feat.md",
            "active_agents": {"ag1": {"type": "Plan", "started_at": "2026-01-01"}},
        }
        ctx = HookContext.from_dict(data)
        assert ctx.session_id == "s1"
        assert ctx.active_skill == "brainstorming"
        assert ctx.active_plan == "docs/plans/feat.md"
        assert ctx.active_agents["ag1"]["type"] == "Plan"

    def test_from_dict_minimal(self):
        data = {"session_id": "s1"}
        ctx = HookContext.from_dict(data)
        assert ctx.session_id == "s1"
        assert ctx.active_skill is None
        assert ctx.active_plan is None
        assert ctx.active_agents == {}

    def test_to_dict_from_dict_round_trip(self):
        ctx = HookContext("round-trip")
        ctx.active_skill = "coding"
        ctx.active_plan = "docs/plans/test.md"
        ctx.active_agents = {"a": {"type": "Explore"}}

        restored = HookContext.from_dict(ctx.to_dict())
        assert restored.session_id == ctx.session_id
        assert restored.active_skill == ctx.active_skill
        assert restored.active_plan == ctx.active_plan
        assert restored.active_agents == ctx.active_agents


# ---------------------------------------------------------------------------
# Persistence (save / load)
# ---------------------------------------------------------------------------

class TestHookContextPersistence:
    def test_save_and_load_round_trip(self, state_dirs):
        tmp_path, state_dir = state_dirs
        ctx = HookContext("persist-test")
        ctx.active_skill = "testing"
        ctx.active_plan = "docs/plans/persist.md"
        ctx.active_agents = {"agent-1": {"type": "Explore", "started_at": "2026-01-01T00:00:00Z"}}
        ctx.save()

        loaded = HookContext.load("persist-test")
        assert loaded.session_id == "persist-test"
        assert loaded.active_skill == "testing"
        assert loaded.active_plan == "docs/plans/persist.md"
        assert loaded.active_agents["agent-1"]["type"] == "Explore"

    def test_load_missing_creates_fresh(self, state_dirs):
        ctx = HookContext.load("nonexistent-session")
        assert ctx.session_id == "nonexistent-session"
        assert ctx.active_skill is None
        assert ctx.active_agents == {}

    def test_save_creates_json_file(self, state_dirs):
        tmp_path, state_dir = state_dirs
        ctx = HookContext("file-check")
        ctx.save()

        state_file = state_dir / "file-check.json"
        assert state_file.exists()

        data = json.loads(state_file.read_text())
        assert data["session_id"] == "file-check"

    def test_save_overwrites_existing(self, state_dirs):
        tmp_path, state_dir = state_dirs
        ctx1 = HookContext("overwrite")
        ctx1.active_skill = "first"
        ctx1.save()

        ctx2 = HookContext("overwrite")
        ctx2.active_skill = "second"
        ctx2.save()

        loaded = HookContext.load("overwrite")
        assert loaded.active_skill == "second"

    def test_load_with_corrupted_json(self, state_dirs):
        tmp_path, state_dir = state_dirs
        state_file = state_dir / "corrupted.json"
        state_file.write_text("{invalid json")

        ctx = HookContext.load("corrupted")
        # Should fallback to fresh context
        assert ctx.session_id == "corrupted"
        assert ctx.active_skill is None

    def test_save_creates_state_dir(self, state_dirs):
        tmp_path, _ = state_dirs
        # Remove state dir and patch to a new location
        new_config = HookConfig(state_dir=".claude/new-state")
        with patch("mc.hooks.context.get_config", return_value=new_config):
            ctx = HookContext("new-dir")
            ctx.save()
            assert (tmp_path / ".claude" / "new-state" / "new-dir.json").exists()


# ---------------------------------------------------------------------------
# Auto-prune
# ---------------------------------------------------------------------------

class TestHookContextAutoPrune:
    def test_prunes_old_state_files(self, state_dirs):
        tmp_path, state_dir = state_dirs
        # Create an old state file (2 days old)
        old_file = state_dir / "old-session.json"
        old_file.write_text('{"session_id":"old-session"}')
        old_time = time.time() - 172800  # 48 hours
        os.utime(old_file, (old_time, old_time))

        # Loading any session triggers prune
        HookContext.load("trigger-prune")
        assert not old_file.exists()

    def test_keeps_recent_state_files(self, state_dirs):
        tmp_path, state_dir = state_dirs
        # Create a recent state file
        recent_file = state_dir / "recent-session.json"
        recent_file.write_text('{"session_id":"recent-session"}')

        HookContext.load("trigger-prune")
        assert recent_file.exists()

    def test_prune_handles_oserror_gracefully(self, state_dirs):
        tmp_path, state_dir = state_dirs
        # Create an old file
        old_file = state_dir / "old-err.json"
        old_file.write_text('{"session_id":"old-err"}')
        old_time = time.time() - 172800
        os.utime(old_file, (old_time, old_time))

        # Patch unlink to raise OSError
        original_unlink = Path.unlink
        def failing_unlink(self, *args, **kwargs):
            if "old-err" in str(self):
                raise OSError("permission denied")
            return original_unlink(self, *args, **kwargs)

        with patch.object(Path, "unlink", failing_unlink):
            # Should not raise
            ctx = HookContext.load("safe-prune")
            assert ctx.session_id == "safe-prune"

    def test_sanitized_session_id_used_for_filename(self, state_dirs):
        tmp_path, state_dir = state_dirs
        raw_id = "unsafe/../../id"
        ctx = HookContext(raw_id)
        ctx.save()

        # The file should use the sanitized name
        safe_name = _safe_session_id(raw_id)
        expected_file = state_dir / f"{safe_name}.json"
        assert expected_file.exists()
