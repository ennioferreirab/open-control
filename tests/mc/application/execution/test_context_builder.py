"""Tests for the unified ContextBuilder pipeline.

Covers AC1-AC4:
- Task context assembly (full pipeline)
- Step context assembly (with predecessor context)
- CC execution context
- Human-step context (minimal, no process spawn)
- Mention context reusing ThreadContextBuilder
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mc.application.execution.context_builder import ContextBuilder
from mc.application.execution.request import EntityType, ExecutionRequest

# ── Mock bridge factory ──────────────────────────────────────────────────────


def _make_mock_bridge(
    *,
    task_data: dict[str, Any] | None = None,
    agent_data: dict[str, Any] | None = None,
    messages: list[dict[str, Any]] | None = None,
    board_data: dict[str, Any] | None = None,
    tag_attr_values: list[dict[str, Any]] | None = None,
    tag_attr_catalog: list[dict[str, Any]] | None = None,
) -> MagicMock:
    """Create a mock ConvexBridge with configurable return values."""
    bridge = MagicMock()

    default_task = task_data or {
        "id": "task_123",
        "title": "Test Task",
        "description": "A test task",
        "files": [],
        "tags": [],
    }

    def mock_query(fn_name: str, args: dict) -> Any:
        if fn_name == "tasks:getById":
            return default_task
        if fn_name == "tagAttributeValues:getByTask":
            return tag_attr_values or []
        if fn_name == "tagAttributes:list":
            return tag_attr_catalog or []
        return None

    bridge.query = mock_query
    bridge.get_agent_by_name = MagicMock(return_value=agent_data)
    bridge.get_task_messages = MagicMock(return_value=messages or [])
    bridge.get_board_by_id = MagicMock(return_value=board_data)
    bridge.get_steps_by_task = MagicMock(return_value=[])

    return bridge


# ── Test helpers ─────────────────────────────────────────────────────────────


def _user_msg(content: str) -> dict[str, Any]:
    return {
        "author_name": "User",
        "author_type": "user",
        "message_type": "user_message",
        "timestamp": "2026-01-01T10:00:00Z",
        "content": content,
    }


def _step_completion(step_id: str, content: str) -> dict[str, Any]:
    return {
        "author_name": "agent-1",
        "author_type": "agent",
        "step_id": step_id,
        "type": "step_completion",
        "timestamp": "2026-01-01T10:02:00Z",
        "content": content,
    }


# ── Task Context Tests ───────────────────────────────────────────────────────


class TestBuildTaskContext:
    """Tests for ContextBuilder.build_task_context (AC1, AC3)."""

    @pytest.fixture
    def bridge(self) -> MagicMock:
        return _make_mock_bridge()

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, None, None),
    )
    async def test_basic_task_context(self, mock_config: MagicMock, bridge: MagicMock) -> None:
        builder = ContextBuilder(bridge)
        req = await builder.build_task_context(
            task_id="task_123",
            title="Test Task",
            description="Do something",
            agent_name="test-agent",
        )
        assert isinstance(req, ExecutionRequest)
        assert req.entity_type == EntityType.TASK
        assert req.entity_id == "task_123"
        assert req.task_id == "task_123"
        assert req.title == "Test Task"
        assert req.agent_name == "test-agent"
        assert req.is_task is True
        assert req.is_step is False

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.context_builder.load_agent_config",
        return_value=("yaml prompt", "gpt-4", ["code"]),
    )
    async def test_agent_config_loaded(self, mock_config: MagicMock, bridge: MagicMock) -> None:
        builder = ContextBuilder(bridge)
        await builder.build_task_context(
            task_id="task_123",
            title="Test",
            description=None,
            agent_name="test-agent",
        )
        # Agent config should be loaded (even if overridden by Convex later)
        mock_config.assert_called_once_with("test-agent")

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, None, None),
    )
    async def test_convex_sync_overrides_yaml(self, mock_config: MagicMock) -> None:
        bridge = _make_mock_bridge(
            agent_data={
                "prompt": "convex prompt",
                "model": "gpt-5",
                "skills": ["write"],
            }
        )
        builder = ContextBuilder(bridge)
        req = await builder.build_task_context(
            task_id="task_123",
            title="Test",
            description=None,
            agent_name="test-agent",
        )
        assert req.agent_prompt is not None
        # Convex prompt gets orientation injected on top
        assert req.agent_model == "gpt-5"
        assert req.agent_skills == ["write"]

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.context_builder.load_agent_config",
        return_value=("agent system prompt", "gpt-4", ["code"]),
    )
    @patch(
        "mc.application.execution.context_builder.inject_orientation",
        side_effect=lambda _name, prompt, **_kwargs: prompt,
    )
    @patch("mc.application.execution.context_builder.resolve_tier", return_value=("gpt-4", None))
    async def test_task_prompt_preserves_agent_prompt_and_operational_context(
        self,
        mock_tier: MagicMock,
        mock_orientation: MagicMock,
        mock_config: MagicMock,
        bridge: MagicMock,
    ) -> None:
        builder = ContextBuilder(bridge)
        req = await builder.build_task_context(
            task_id="task_123",
            title="Test Task",
            description="Do the mission",
            agent_name="test-agent",
        )

        assert req.agent_prompt == "agent system prompt"
        assert req.prompt.startswith("agent system prompt\n\n---\n\n")
        assert "Do the mission" in req.prompt

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, None, None),
    )
    async def test_file_manifest_injected(self, mock_config: MagicMock) -> None:
        bridge = _make_mock_bridge(
            task_data={
                "id": "task_123",
                "title": "Test",
                "files": [
                    {"name": "doc.pdf", "type": "application/pdf", "size": 1024},
                ],
            }
        )
        builder = ContextBuilder(bridge)
        req = await builder.build_task_context(
            task_id="task_123",
            title="Test",
            description=None,
            agent_name="test-agent",
        )
        assert len(req.file_manifest) == 1
        assert req.file_manifest[0]["name"] == "doc.pdf"
        assert "doc.pdf" in (req.description or "")

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, None, None),
    )
    async def test_merge_sources_include_absolute_paths_and_delimited_threads(
        self, mock_config: MagicMock
    ) -> None:
        source_a_path = str(
            Path.home() / ".nanobot" / "tasks" / "task_a" / "attachments" / "source-a.pdf"
        )
        source_b_path = str(
            Path.home() / ".nanobot" / "tasks" / "task_b" / "output" / "source-b.md"
        )

        current_task = {
            "id": "task_merge",
            "title": "Merged Task C",
            "description": "Continue from merged context",
            "files": [],
            "tags": [],
            "is_merge_task": True,
            "merge_source_task_ids": ["task_a", "task_b"],
            "merge_source_labels": ["A", "B"],
        }
        source_tasks = {
            "task_merge": current_task,
            "task_a": {
                "id": "task_a",
                "title": "Task A",
                "description": "First source",
                "status": "done",
                "files": [
                    {
                        "name": "source-a.pdf",
                        "type": "application/pdf",
                        "size": 1024,
                        "subfolder": "attachments",
                    },
                ],
            },
            "task_b": {
                "id": "task_b",
                "title": "Task B",
                "description": "Second source",
                "status": "done",
                "files": [
                    {
                        "name": "source-b.md",
                        "type": "text/markdown",
                        "size": 512,
                        "subfolder": "output",
                    },
                ],
            },
        }

        bridge = MagicMock()

        def query_side_effect(fn_name: str, args: dict) -> Any:
            if fn_name == "tasks:getById":
                return source_tasks.get(args["task_id"])
            if fn_name == "tagAttributeValues:getByTask":
                return []
            if fn_name == "tagAttributes:list":
                return []
            return None

        def message_side_effect(task_id: str) -> list[dict[str, Any]]:
            if task_id == "task_merge":
                return [_user_msg("Continue from both sources")]
            if task_id == "task_a":
                return [
                    {
                        "author_name": "agent-a",
                        "author_type": "agent",
                        "timestamp": "2026-01-01T10:00:00Z",
                        "content": "Task A completed",
                        "type": "step_completion",
                        "artifacts": [{"path": "output/report-a.md", "action": "created"}],
                    },
                ]
            if task_id == "task_b":
                return [
                    {
                        "author_name": "agent-b",
                        "author_type": "agent",
                        "timestamp": "2026-01-01T10:05:00Z",
                        "content": "Task B completed",
                        "type": "step_completion",
                        "artifacts": [{"path": "output/report-b.md", "action": "created"}],
                    },
                ]
            return []

        bridge.query = MagicMock(side_effect=query_side_effect)
        bridge.get_agent_by_name = MagicMock(return_value=None)
        bridge.get_task_messages = MagicMock(side_effect=message_side_effect)
        bridge.get_board_by_id = MagicMock(return_value=None)
        bridge.get_steps_by_task = MagicMock(return_value=[])

        builder = ContextBuilder(bridge)
        req = await builder.build_task_context(
            task_id="task_merge",
            title="Merged Task C",
            description="Base description",
            agent_name="test-agent",
            task_data=current_task,
        )

        assert "[Merged Task Origins]" in (req.description or "")
        assert "[Source Task A Files]" in (req.description or "")
        assert "[Source Task B Files]" in (req.description or "")
        assert "[Source Thread A]" in (req.description or "")
        assert "[Source Thread B]" in (req.description or "")
        assert source_a_path in (req.description or "")
        assert source_b_path in (req.description or "")
        assert str(Path.home() / ".nanobot" / "tasks" / "task_a" / "output" / "report-a.md") in (
            req.description or ""
        )
        assert str(Path.home() / ".nanobot" / "tasks" / "task_b" / "output" / "report-b.md") in (
            req.description or ""
        )

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, None, None),
    )
    async def test_nested_merge_sources_are_flattened_recursively(
        self, mock_config: MagicMock
    ) -> None:
        current_task = {
            "id": "task_merge_2",
            "title": "Merged Task D",
            "description": "Continue from merged context",
            "files": [],
            "tags": [],
            "is_merge_task": True,
            "merge_source_task_ids": ["task_merge_1", "task_c"],
            "merge_source_labels": ["A", "B"],
        }
        source_tasks = {
            "task_merge_2": current_task,
            "task_merge_1": {
                "id": "task_merge_1",
                "title": "Merged Task C",
                "description": "Inner merge",
                "status": "review",
                "files": [{"name": "inner.md", "subfolder": "output"}],
                "is_merge_task": True,
                "merge_source_task_ids": ["task_a", "task_b"],
                "merge_source_labels": ["A", "B"],
            },
            "task_a": {
                "id": "task_a",
                "title": "Task A",
                "description": "First source",
                "status": "done",
                "files": [{"name": "source-a.pdf", "subfolder": "attachments"}],
            },
            "task_b": {
                "id": "task_b",
                "title": "Task B",
                "description": "Second source",
                "status": "done",
                "files": [{"name": "source-b.md", "subfolder": "output"}],
            },
            "task_c": {
                "id": "task_c",
                "title": "Task C",
                "description": "Third source",
                "status": "done",
                "files": [{"name": "source-c.txt", "subfolder": "attachments"}],
            },
        }

        bridge = MagicMock()

        def query_side_effect(fn_name: str, args: dict) -> Any:
            if fn_name == "tasks:getById":
                return source_tasks.get(args["task_id"])
            if fn_name == "tagAttributeValues:getByTask":
                return []
            if fn_name == "tagAttributes:list":
                return []
            return None

        def message_side_effect(task_id: str) -> list[dict[str, Any]]:
            return [
                {
                    "author_name": "agent",
                    "author_type": "agent",
                    "timestamp": "2026-01-01T10:00:00Z",
                    "content": f"{task_id} completed",
                    "type": "step_completion",
                }
            ]

        bridge.query = MagicMock(side_effect=query_side_effect)
        bridge.get_agent_by_name = MagicMock(return_value=None)
        bridge.get_task_messages = MagicMock(side_effect=message_side_effect)
        bridge.get_board_by_id = MagicMock(return_value=None)
        bridge.get_steps_by_task = MagicMock(return_value=[])

        builder = ContextBuilder(bridge)
        req = await builder.build_task_context(
            task_id="task_merge_2",
            title="Merged Task D",
            description="Base description",
            agent_name="test-agent",
            task_data=current_task,
        )

        assert "A: Merged Task C [review]" in (req.description or "")
        assert "A.A: Task A [done]" in (req.description or "")
        assert "A.B: Task B [done]" in (req.description or "")
        assert "B: Task C [done]" in (req.description or "")

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, None, None),
    )
    async def test_thread_context_injected(self, mock_config: MagicMock) -> None:
        bridge = _make_mock_bridge(messages=[_user_msg("Please help me")])
        builder = ContextBuilder(bridge)
        req = await builder.build_task_context(
            task_id="task_123",
            title="Test",
            description=None,
            agent_name="test-agent",
        )
        assert req.thread_context != ""
        assert "help me" in req.thread_context
        assert "[Thread Journal]" in req.thread_context
        assert req.thread_journal_path.endswith("/THREAD_JOURNAL.md")

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, None, None),
    )
    async def test_nanobot_prompt_cleared(self, mock_config: MagicMock, bridge: MagicMock) -> None:
        """System agent (nanobot) should have prompt cleared."""
        builder = ContextBuilder(bridge)
        req = await builder.build_task_context(
            task_id="task_123",
            title="Test",
            description=None,
            agent_name="nanobot",
        )
        assert req.agent_prompt is None

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, None, None),
    )
    async def test_trust_level_propagated(self, mock_config: MagicMock, bridge: MagicMock) -> None:
        builder = ContextBuilder(bridge)
        req = await builder.build_task_context(
            task_id="task_123",
            title="Test",
            description=None,
            agent_name="test-agent",
            trust_level="human_approved",
        )
        assert req.trust_level == "human_approved"

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, None, None),
    )
    async def test_files_dir_and_output_dir_set(
        self, mock_config: MagicMock, bridge: MagicMock
    ) -> None:
        builder = ContextBuilder(bridge)
        req = await builder.build_task_context(
            task_id="task_123",
            title="Test",
            description=None,
            agent_name="test-agent",
        )
        assert req.files_dir != ""
        assert req.output_dir != ""
        assert req.output_dir.endswith("/output")

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, None, None),
    )
    async def test_with_history_board_uses_shared_agent_memory_workspace(
        self, mock_config: MagicMock, tmp_path: Path
    ) -> None:
        bridge = _make_mock_bridge(
            task_data={
                "id": "task_123",
                "title": "Test",
                "files": [],
                "tags": [],
                "board_id": "board_default",
            },
            board_data={
                "id": "board_default",
                "name": "default",
                "agent_memory_modes": [
                    {"agent_name": "test-agent", "mode": "with_history"},
                ],
            },
        )

        with patch("pathlib.Path.home", return_value=tmp_path):
            builder = ContextBuilder(bridge)
            req = await builder.build_task_context(
                task_id="task_123",
                title="Test",
                description=None,
                agent_name="test-agent",
            )

        assert req.board_name == "default"
        assert req.memory_workspace == (tmp_path / ".nanobot" / "agents" / "test-agent")

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, None, None),
    )
    async def test_clean_board_uses_board_scoped_memory_workspace(
        self, mock_config: MagicMock, tmp_path: Path
    ) -> None:
        bridge = _make_mock_bridge(
            task_data={
                "id": "task_123",
                "title": "Test",
                "files": [],
                "tags": [],
                "board_id": "board_default",
            },
            board_data={
                "id": "board_default",
                "name": "default",
                "agent_memory_modes": [
                    {"agent_name": "test-agent", "mode": "clean"},
                ],
            },
        )

        with patch("pathlib.Path.home", return_value=tmp_path):
            builder = ContextBuilder(bridge)
            req = await builder.build_task_context(
                task_id="task_123",
                title="Test",
                description=None,
                agent_name="test-agent",
            )

        assert req.board_name == "default"
        assert req.memory_workspace == (
            tmp_path / ".nanobot" / "boards" / "default" / "agents" / "test-agent"
        )


# ── Step Context Tests ───────────────────────────────────────────────────────


class TestBuildStepContext:
    """Tests for ContextBuilder.build_step_context (AC1, AC3)."""

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, None, None),
    )
    async def test_basic_step_context(self, mock_config: MagicMock) -> None:
        bridge = _make_mock_bridge()
        builder = ContextBuilder(bridge)
        step = {
            "id": "step_1",
            "title": "Analyze data",
            "description": "Analyze the CSV data",
            "assigned_agent": "data-agent",
            "blocked_by": [],
        }
        req = await builder.build_step_context("task_123", step)
        assert isinstance(req, ExecutionRequest)
        assert req.entity_type == EntityType.STEP
        assert req.entity_id == "step_1"
        assert req.step_id == "step_1"
        assert req.task_id == "task_123"
        assert req.step_title == "Analyze data"
        assert req.agent_name == "data-agent"
        assert req.is_step is True

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, None, None),
    )
    async def test_step_with_predecessors(self, mock_config: MagicMock) -> None:
        bridge = _make_mock_bridge(
            messages=[
                _step_completion("step_0", "Step 0 completed"),
                _user_msg("Go ahead"),
            ]
        )
        builder = ContextBuilder(bridge)
        step = {
            "id": "step_1",
            "title": "Build feature",
            "description": "Build it",
            "assigned_agent": "dev-agent",
            "blocked_by": ["step_0"],
        }
        req = await builder.build_step_context("task_123", step)
        assert req.predecessor_step_ids == ["step_0"]
        # Thread context should include predecessor content
        assert "Step 0 completed" in req.thread_context

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, None, None),
    )
    async def test_rerun_context_explicitly_surfaces_review_feedback(
        self, mock_config: MagicMock
    ) -> None:
        bridge = _make_mock_bridge(
            messages=[
                _step_completion("step_1", "Attempt 1 draft output"),
                {
                    "author_name": "reviewer",
                    "author_type": "agent",
                    "type": "comment",
                    "timestamp": "2026-01-01T10:03:00Z",
                    "content": "Rejected: fix alignment and strengthen CTA contrast.",
                },
                _user_msg("Please rework this with the latest reviewer feedback."),
            ]
        )
        builder = ContextBuilder(bridge)
        step = {
            "id": "step_1",
            "title": "Revise draft",
            "description": "Apply reviewer feedback",
            "assigned_agent": "writer",
            "blocked_by": [],
        }

        req = await builder.build_step_context("task_123", step)

        assert "[Previous Review Feedback]" in req.description
        assert "Rejected: fix alignment and strengthen CTA contrast." in req.description
        assert "Attempt 1 draft output" in req.description

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, None, None),
    )
    async def test_review_step_description_requires_structured_json_output(
        self, mock_config: MagicMock
    ) -> None:
        bridge = _make_mock_bridge()
        builder = ContextBuilder(bridge)
        step = {
            "id": "step_review",
            "title": "Review package",
            "description": "Validate the final package",
            "assigned_agent": "reviewer",
            "workflow_step_type": "review",
            "review_spec_id": "review-spec-1",
            "on_reject_step_id": "step_package",
        }

        req = await builder.build_step_context("task_123", step)

        assert "[Review Output Contract]" in req.description
        assert '"verdict": "approved" | "rejected"' in req.description
        assert '"recommendedReturnStep": "step_package" | null' in req.description
        assert "Return ONLY a single JSON object" in req.description
        assert "Do not write a separate review file" in req.description

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, None, None),
    )
    async def test_step_execution_description_format(self, mock_config: MagicMock) -> None:
        bridge = _make_mock_bridge()
        builder = ContextBuilder(bridge)
        step = {
            "id": "step_1",
            "title": "Write report",
            "description": "Write the final report",
            "assigned_agent": "writer",
        }
        req = await builder.build_step_context("task_123", step)
        assert 'You are executing step: "Write report"' in req.description
        assert "Step description: Write the final report" in req.description
        assert "Task workspace:" in req.description

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.context_builder.load_agent_config",
        return_value=("step agent prompt", None, None),
    )
    @patch(
        "mc.application.execution.context_builder.inject_orientation",
        side_effect=lambda _name, prompt, **_kwargs: prompt,
    )
    @patch("mc.application.execution.context_builder.resolve_tier", return_value=(None, None))
    async def test_step_prompt_preserves_agent_prompt_and_execution_description(
        self,
        mock_tier: MagicMock,
        mock_orientation: MagicMock,
        mock_config: MagicMock,
    ) -> None:
        bridge = _make_mock_bridge()
        builder = ContextBuilder(bridge)
        step = {
            "id": "step_1",
            "title": "Write report",
            "description": "Write the final report",
            "assigned_agent": "writer",
            "blocked_by": [],
        }

        req = await builder.build_step_context("task_123", step)

        assert req.agent_prompt == "step agent prompt"
        assert req.prompt.startswith("step agent prompt\n\n---\n\n")
        assert 'You are executing step: "Write report"' in req.prompt

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, None, None),
    )
    async def test_lead_agent_rerouted(self, mock_config: MagicMock) -> None:
        bridge = _make_mock_bridge()
        builder = ContextBuilder(bridge)
        step = {
            "id": "step_1",
            "title": "Test step",
            "assigned_agent": "lead-agent",
        }
        req = await builder.build_step_context("task_123", step)
        assert req.agent_name == "nanobot"


# ── CC Execution Context Tests ──────────────────────────────────────────────


class TestCCExecutionContext:
    """Tests for CC execution context building (AC4)."""

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, "cc/claude-sonnet-4-20250514", None),
    )
    async def test_cc_model_detected(self, mock_config: MagicMock) -> None:
        bridge = _make_mock_bridge(agent_data={"model": "cc/claude-sonnet-4-20250514"})
        builder = ContextBuilder(bridge)
        req = await builder.build_task_context(
            task_id="task_123",
            title="CC Task",
            description=None,
            agent_name="cc-agent",
        )
        assert req.is_cc is True
        assert req.model == "claude-sonnet-4-20250514"

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, "cc/claude-sonnet-4-20250514", None),
    )
    async def test_cc_step_detected(self, mock_config: MagicMock) -> None:
        bridge = _make_mock_bridge(agent_data={"model": "cc/claude-sonnet-4-20250514"})
        builder = ContextBuilder(bridge)
        step = {
            "id": "step_1",
            "title": "CC step",
            "assigned_agent": "cc-agent",
        }
        req = await builder.build_step_context("task_123", step)
        assert req.is_cc is True


# ── Human Step Context Tests ────────────────────────────────────────────────


class TestHumanStepContext:
    """Tests for human step context (AC4 -- minimal, no process spawn)."""

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, None, None),
    )
    async def test_human_step_has_minimal_context(self, mock_config: MagicMock) -> None:
        """Human steps get the same context structure but no agent execution."""
        bridge = _make_mock_bridge()
        builder = ContextBuilder(bridge)
        step = {
            "id": "step_1",
            "title": "Review design",
            "description": "Human review of design doc",
            "assigned_agent": "nanobot",
        }
        req = await builder.build_step_context("task_123", step)
        # Should have the basic structure
        assert req.entity_type == EntityType.STEP
        assert req.step_title == "Review design"
        # Human steps still get file context etc.
        assert "Task workspace:" in req.description


# ── Mention Context Tests ───────────────────────────────────────────────────


class TestMentionContextReuse:
    """Tests that mention context reuses ThreadContextBuilder (AC4)."""

    def test_mention_uses_same_builder_as_tasks(self) -> None:
        """The unified thread context builder is the same function used
        for mentions, tasks, and steps."""
        from mc.application.execution.thread_context_builder import (
            build_thread_context,
        )

        msgs = [_user_msg("@agent please help")]
        result = build_thread_context(msgs)
        assert "help" in result

    def test_mention_with_predecessors(self) -> None:
        """Mention context can optionally include predecessor context."""
        from mc.application.execution.thread_context_builder import (
            build_thread_context,
        )

        msgs = [
            _step_completion("s0", "Done"),
            _user_msg("@agent continue"),
        ]
        result = build_thread_context(msgs, predecessor_step_ids=["s0"])
        assert "Done" in result
        assert "continue" in result


# ── Tier Resolution Tests ───────────────────────────────────────────────────


class TestTierResolution:
    """Tests for tier resolution in context builder."""

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, "tier:standard-high", None),
    )
    async def test_tier_resolved_in_task_context(self, mock_config: MagicMock) -> None:
        bridge = _make_mock_bridge(agent_data={"model": "tier:standard-high"})
        # Mock the TierResolver
        with patch("mc.application.execution.context_builder.resolve_tier") as mock_resolve:
            mock_resolve.return_value = ("gpt-4o", "high")
            builder = ContextBuilder(bridge)
            req = await builder.build_task_context(
                task_id="task_123",
                title="Test",
                description=None,
                agent_name="test-agent",
            )
            assert req.model == "gpt-4o"
            assert req.reasoning_level == "high"
