"""Unit tests for executor helpers added in Story 2.5.

Covers:
- _snapshot_output_dir()
- _collect_output_artifacts()
- _build_thread_context() with step_completion messages
- StepCompletionArtifact dataclass serialisation
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mc.contexts.execution.executor import (
    _collect_output_artifacts,
    _snapshot_output_dir,
    _build_thread_context,
    _human_size,
    _relocate_invalid_memory_files,
)
from mc.types import StepCompletionArtifact


# ── _human_size ─────────────────────────────────────────────────────────


class TestHumanSize:
    def test_bytes_below_mb(self):
        assert _human_size(512 * 1024) == "512 KB"

    def test_one_kb(self):
        assert _human_size(1024) == "1 KB"

    def test_megabytes(self):
        assert _human_size(2 * 1024 * 1024) == "2.0 MB"

    def test_zero(self):
        assert _human_size(0) == "0 KB"


# ── StepCompletionArtifact ───────────────────────────────────────────────


class TestStepCompletionArtifact:
    def test_to_dict_created_with_description(self):
        artifact = StepCompletionArtifact(
            path="output/report.pdf",
            action="created",
            description="PDF, 245 KB",
        )
        d = artifact.to_dict()
        assert d == {
            "path": "output/report.pdf",
            "action": "created",
            "description": "PDF, 245 KB",
        }

    def test_to_dict_modified_with_diff(self):
        artifact = StepCompletionArtifact(
            path="output/data.json",
            action="modified",
            diff="+12 KB",
        )
        d = artifact.to_dict()
        assert d == {
            "path": "output/data.json",
            "action": "modified",
            "diff": "+12 KB",
        }

    def test_to_dict_minimal(self):
        artifact = StepCompletionArtifact(path="output/file.txt", action="created")
        d = artifact.to_dict()
        assert d == {"path": "output/file.txt", "action": "created"}
        assert "description" not in d
        assert "diff" not in d

    def test_to_dict_excludes_none_fields(self):
        artifact = StepCompletionArtifact(
            path="output/x.csv",
            action="deleted",
            description=None,
            diff=None,
        )
        d = artifact.to_dict()
        assert "description" not in d
        assert "diff" not in d

    def test_to_dict_all_fields(self):
        artifact = StepCompletionArtifact(
            path="output/r.md",
            action="modified",
            description="Markdown file",
            diff="+3 KB",
        )
        d = artifact.to_dict()
        assert d["description"] == "Markdown file"
        assert d["diff"] == "+3 KB"


# ── _snapshot_output_dir ────────────────────────────────────────────────


def _make_home_patch(tmp_path: Path):
    """Patch Path.home() to return tmp_path for both executor functions."""
    # patch.object on the Path class used within the executor module.
    # Since executor imports Path via `from pathlib import Path`, the class
    # reference is shared, so patching pathlib.Path.home is sufficient.
    from pathlib import Path as _Path

    return patch.object(_Path, "home", return_value=tmp_path)


class TestSnapshotOutputDir:
    def test_empty_dir_returns_empty_snapshot(self, tmp_path):
        # safe_id keeps hyphens: re.sub(r'[^\w\-]', '_', 'snap-task-001') == 'snap-task-001'
        safe_id = "snap-task-001"
        output_dir = tmp_path / ".nanobot" / "tasks" / safe_id / "output"
        output_dir.mkdir(parents=True)

        with _make_home_patch(tmp_path):
            snapshot = _snapshot_output_dir("snap-task-001")

        assert snapshot == {}

    def test_snapshot_captures_existing_files(self, tmp_path):
        safe_id = "snap-task-002"
        output_dir = tmp_path / ".nanobot" / "tasks" / safe_id / "output"
        output_dir.mkdir(parents=True)
        (output_dir / "report.pdf").write_bytes(b"A" * 1024)
        (output_dir / "data.json").write_text('{"x": 1}')

        with _make_home_patch(tmp_path):
            snapshot = _snapshot_output_dir("snap-task-002")

        assert "output/report.pdf" in snapshot
        assert "output/data.json" in snapshot
        assert isinstance(snapshot["output/report.pdf"], float)

    def test_snapshot_missing_dir_returns_empty(self, tmp_path):
        # No output dir created at all
        with _make_home_patch(tmp_path):
            snapshot = _snapshot_output_dir("nonexistent-task-xyz")

        assert snapshot == {}


# ── _collect_output_artifacts ────────────────────────────────────────────


class TestCollectOutputArtifacts:
    def test_new_file_is_created_artifact(self, tmp_path):
        safe_id = "collect-task-001"
        output_dir = tmp_path / ".nanobot" / "tasks" / safe_id / "output"
        output_dir.mkdir(parents=True)

        # No pre-snapshot (empty dir before execution)
        pre_snapshot: dict[str, float] = {}

        # Agent creates a file
        (output_dir / "summary.md").write_text("# Summary")

        with _make_home_patch(tmp_path):
            artifacts = _collect_output_artifacts("collect-task-001", pre_snapshot)

        assert len(artifacts) == 1
        a = artifacts[0]
        assert a["path"] == "output/summary.md"
        assert a["action"] == "created"
        assert "description" in a
        assert "MD" in a["description"]

    def test_modified_file_is_modified_artifact(self, tmp_path):
        safe_id = "collect-task-002"
        output_dir = tmp_path / ".nanobot" / "tasks" / safe_id / "output"
        output_dir.mkdir(parents=True)

        f = output_dir / "data.json"
        f.write_text('{"v": 1}')

        # Snapshot before modification
        with _make_home_patch(tmp_path):
            pre_snapshot = _snapshot_output_dir("collect-task-002")

        # Simulate modification — wait and rewrite so mtime changes
        time.sleep(0.05)
        f.write_text('{"v": 2}')
        new_mtime = f.stat().st_mtime
        assert new_mtime > pre_snapshot["output/data.json"]

        with _make_home_patch(tmp_path):
            artifacts = _collect_output_artifacts("collect-task-002", pre_snapshot)

        assert len(artifacts) == 1
        a = artifacts[0]
        assert a["path"] == "output/data.json"
        assert a["action"] == "modified"
        assert "diff" in a

    def test_unchanged_file_excluded(self, tmp_path):
        safe_id = "collect-task-003"
        output_dir = tmp_path / ".nanobot" / "tasks" / safe_id / "output"
        output_dir.mkdir(parents=True)
        (output_dir / "old.txt").write_text("old content")

        with _make_home_patch(tmp_path):
            pre_snapshot = _snapshot_output_dir("collect-task-003")

        # Nothing changed — re-scan without writing anything new
        with _make_home_patch(tmp_path):
            artifacts = _collect_output_artifacts("collect-task-003", pre_snapshot)

        assert artifacts == []

    def test_none_pre_snapshot_treats_all_as_created(self, tmp_path):
        safe_id = "collect-task-004"
        output_dir = tmp_path / ".nanobot" / "tasks" / safe_id / "output"
        output_dir.mkdir(parents=True)
        (output_dir / "report.pdf").write_bytes(b"PDF" * 100)

        with _make_home_patch(tmp_path):
            artifacts = _collect_output_artifacts("collect-task-004", None)

        assert len(artifacts) == 1
        assert artifacts[0]["action"] == "created"

    def test_missing_output_dir_returns_empty(self, tmp_path):
        with _make_home_patch(tmp_path):
            artifacts = _collect_output_artifacts("no-such-task-zzz", {})

        assert artifacts == []

    def test_mixed_created_and_modified(self, tmp_path):
        safe_id = "collect-task-005"
        output_dir = tmp_path / ".nanobot" / "tasks" / safe_id / "output"
        output_dir.mkdir(parents=True)
        existing = output_dir / "existing.txt"
        existing.write_text("before")

        with _make_home_patch(tmp_path):
            pre_snapshot = _snapshot_output_dir("collect-task-005")

        time.sleep(0.05)
        existing.write_text("after")
        (output_dir / "new.md").write_text("# New")

        with _make_home_patch(tmp_path):
            artifacts = _collect_output_artifacts("collect-task-005", pre_snapshot)

        actions = {a["path"]: a["action"] for a in artifacts}
        assert actions.get("output/existing.txt") == "modified"
        assert actions.get("output/new.md") == "created"


class TestRelocateInvalidMemoryFiles:
    def test_moves_invalid_memory_file_to_output(self, tmp_path):
        safe_id = "memory-relocate-task"
        workspace = tmp_path / "agent"
        memory_dir = workspace / "memory"
        memory_dir.mkdir(parents=True)
        (memory_dir / "MEMORY.md").write_text("valid", encoding="utf-8")
        rogue = memory_dir / "rogue.md"
        rogue.write_text("artifact", encoding="utf-8")

        with _make_home_patch(tmp_path):
            moved = _relocate_invalid_memory_files(safe_id, workspace)

        assert len(moved) == 1
        relocated = (
            tmp_path / ".nanobot" / "tasks" / safe_id / "output" / "memory-relocated-rogue.md"
        )
        assert moved[0] == relocated
        assert relocated.read_text(encoding="utf-8") == "artifact"
        assert not rogue.exists()
        assert (memory_dir / "MEMORY.md").exists()


# ── _build_thread_context with step_completion ──────────────────────────


class TestBuildThreadContextWithArtifacts:
    def _user_msg(self, content: str) -> dict[str, Any]:
        return {
            "author_name": "User",
            "author_type": "user",
            "message_type": "user_message",
            "timestamp": "2026-01-01T10:00:00Z",
            "content": content,
        }

    def _step_completion_msg(
        self,
        content: str,
        artifacts: list[dict] | None = None,
    ) -> dict[str, Any]:
        msg: dict[str, Any] = {
            "author_name": "nanobot",
            "author_type": "agent",
            "message_type": "work",
            "type": "step_completion",
            "timestamp": "2026-01-01T10:05:00Z",
            "content": content,
        }
        if artifacts is not None:
            msg["artifacts"] = artifacts
        return msg

    def test_step_completion_message_labeled(self):
        messages = [
            self._step_completion_msg("Analyzed the dataset."),
            self._user_msg("Follow up question"),
        ]
        ctx = _build_thread_context(messages)
        assert "[Step Completion]" in ctx
        assert "Analyzed the dataset." in ctx

    def test_step_completion_with_created_artifact(self):
        messages = [
            self._step_completion_msg(
                "Generated report.",
                artifacts=[
                    {
                        "path": "output/report.pdf",
                        "action": "created",
                        "description": "PDF, 245 KB",
                    }
                ],
            ),
            self._user_msg("Please also add a chart"),
        ]
        ctx = _build_thread_context(messages)
        # Story 2.6: new ThreadContextBuilder format uses "Files:" and "CREATED:"
        assert "Files:" in ctx
        assert "CREATED: output/report.pdf" in ctx
        assert "PDF, 245 KB" in ctx

    def test_step_completion_with_modified_artifact(self):
        messages = [
            self._step_completion_msg(
                "Updated data file.",
                artifacts=[
                    {
                        "path": "output/data.json",
                        "action": "modified",
                        "diff": "File updated (12 KB)",
                    }
                ],
            ),
            self._user_msg("Thanks"),
        ]
        ctx = _build_thread_context(messages)
        # Story 2.6: new ThreadContextBuilder format uses "MODIFIED:" and "diff: ..."
        assert "MODIFIED: output/data.json" in ctx
        assert "diff: File updated (12 KB)" in ctx

    def test_step_completion_with_empty_artifacts_no_artifacts_section(self):
        messages = [
            self._step_completion_msg("Did some analysis.", artifacts=[]),
            self._user_msg("Ok"),
        ]
        ctx = _build_thread_context(messages)
        assert "[Step Completion]" in ctx
        assert "Files:" not in ctx

    def test_step_completion_with_no_artifacts_key(self):
        messages = [
            self._step_completion_msg("Did some analysis."),  # no artifacts key
            self._user_msg("Ok"),
        ]
        ctx = _build_thread_context(messages)
        assert "[Step Completion]" in ctx
        assert "Files:" not in ctx

    def test_multiple_artifacts_all_rendered(self):
        messages = [
            self._step_completion_msg(
                "Processed files.",
                artifacts=[
                    {"path": "output/a.pdf", "action": "created", "description": "PDF, 10 KB"},
                    {"path": "output/b.json", "action": "modified", "diff": "+2 KB"},
                ],
            ),
            self._user_msg("Good work"),
        ]
        ctx = _build_thread_context(messages)
        # Story 2.6: new format — CREATED/MODIFIED with " — " separator
        assert "CREATED: output/a.pdf" in ctx
        assert "PDF, 10 KB" in ctx
        assert "MODIFIED: output/b.json" in ctx
        assert "diff: +2 KB" in ctx

    def test_non_step_completion_message_not_labeled(self):
        messages = [
            {
                "author_name": "nanobot",
                "author_type": "agent",
                "message_type": "work",
                "timestamp": "2026-01-01T10:00:00Z",
                "content": "Plain work message",
            },
            self._user_msg("Ok"),
        ]
        ctx = _build_thread_context(messages)
        assert "[Step Completion]" not in ctx
        assert "Plain work message" in ctx

    def test_step_completion_artifact_with_path_only(self):
        messages = [
            self._step_completion_msg(
                "Created file.",
                artifacts=[{"path": "output/x.bin", "action": "created"}],
            ),
            self._user_msg("Review please"),
        ]
        ctx = _build_thread_context(messages)
        # Story 2.6: new format — "CREATED: output/x.bin" with no separator
        assert "CREATED: output/x.bin" in ctx

    def test_empty_messages_returns_empty_string(self):
        assert _build_thread_context([]) == ""

    def test_no_user_messages_returns_empty_string(self):
        messages = [
            self._step_completion_msg("Some work done."),
        ]
        assert _build_thread_context(messages) == ""


# ── delegate_task removal in MC step execution ────────────────────────


class TestDelegateTaskNotAvailableInMCSteps:
    """Agents executing MC steps must NOT have delegate_task in their toolset.

    This prevents circular delegation loops (e.g. youtube-summarizer
    delegating a cron job to itself instead of using the cron tool directly).
    """

    @pytest.mark.asyncio
    async def test_delegate_task_removed_before_agent_runs(self):
        """_run_agent_on_task must unregister delegate_task from the AgentLoop."""
        from mc.contexts.execution.executor import _run_agent_on_task

        captured_loop = {}

        # Patch AgentLoop to capture the instance and skip actual LLM execution
        original_init = None

        class FakeAgentLoop:
            def __init__(self, **kwargs):
                from nanobot.agent.tools.registry import ToolRegistry
                from nanobot.agent.tools.mc_delegate import McDelegateTool

                self.tools = ToolRegistry()
                # Simulate what the real __init__ does: register delegate_task
                self.tools.register(McDelegateTool())
                captured_loop["instance"] = self

            async def process_direct(self, **kwargs):
                return "mocked result"

        with (
            patch("nanobot.agent.loop.AgentLoop", FakeAgentLoop),
            patch.dict("sys.modules", {"nanobot.agent.loop": MagicMock(AgentLoop=FakeAgentLoop)}),
            patch(
                "mc.contexts.execution.executor._make_provider",
                return_value=(MagicMock(), "mock-model"),
            ),
        ):
            await _run_agent_on_task(
                agent_name="youtube-summarizer",
                agent_prompt="You are a test agent",
                agent_model="mock-model",
                task_title="Test task",
            )

        loop = captured_loop["instance"]
        assert "delegate_task" not in loop.tools, (
            "delegate_task should be removed from agent tools in MC step execution"
        )
