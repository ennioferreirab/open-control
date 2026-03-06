"""Tests for the unified ContextBuilder pipeline.

Covers AC1-AC4:
- Task context assembly (full pipeline)
- Step context assembly (with predecessor context)
- CC execution context
- Human-step context (minimal, no process spawn)
- Mention context reusing ThreadContextBuilder
"""

from __future__ import annotations

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
    async def test_basic_task_context(
        self, mock_config: MagicMock, bridge: MagicMock
    ) -> None:
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
    async def test_agent_config_loaded(
        self, mock_config: MagicMock, bridge: MagicMock
    ) -> None:
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
    async def test_convex_sync_overrides_yaml(
        self, mock_config: MagicMock
    ) -> None:
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
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, None, None),
    )
    async def test_file_manifest_injected(
        self, mock_config: MagicMock
    ) -> None:
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
    async def test_thread_context_injected(
        self, mock_config: MagicMock
    ) -> None:
        bridge = _make_mock_bridge(
            messages=[_user_msg("Please help me")]
        )
        builder = ContextBuilder(bridge)
        req = await builder.build_task_context(
            task_id="task_123",
            title="Test",
            description=None,
            agent_name="test-agent",
        )
        assert req.thread_context != ""
        assert "help me" in req.thread_context

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, None, None),
    )
    async def test_nanobot_prompt_cleared(
        self, mock_config: MagicMock, bridge: MagicMock
    ) -> None:
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
    async def test_trust_level_propagated(
        self, mock_config: MagicMock, bridge: MagicMock
    ) -> None:
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


# ── Step Context Tests ───────────────────────────────────────────────────────


class TestBuildStepContext:
    """Tests for ContextBuilder.build_step_context (AC1, AC3)."""

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, None, None),
    )
    async def test_basic_step_context(
        self, mock_config: MagicMock
    ) -> None:
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
        assert req.task_id == "task_123"
        assert req.step_title == "Analyze data"
        assert req.agent_name == "data-agent"
        assert req.is_step is True

    @pytest.mark.asyncio
    @patch(
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, None, None),
    )
    async def test_step_with_predecessors(
        self, mock_config: MagicMock
    ) -> None:
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
    async def test_step_execution_description_format(
        self, mock_config: MagicMock
    ) -> None:
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
        "mc.application.execution.roster_builder.load_agent_config",
        return_value=(None, None, None),
    )
    async def test_lead_agent_rerouted(
        self, mock_config: MagicMock
    ) -> None:
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
    async def test_cc_model_detected(
        self, mock_config: MagicMock
    ) -> None:
        bridge = _make_mock_bridge(
            agent_data={"model": "cc/claude-sonnet-4-20250514"}
        )
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
    async def test_cc_step_detected(
        self, mock_config: MagicMock
    ) -> None:
        bridge = _make_mock_bridge(
            agent_data={"model": "cc/claude-sonnet-4-20250514"}
        )
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
    async def test_human_step_has_minimal_context(
        self, mock_config: MagicMock
    ) -> None:
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
    async def test_tier_resolved_in_task_context(
        self, mock_config: MagicMock
    ) -> None:
        bridge = _make_mock_bridge(
            agent_data={"model": "tier:standard-high"}
        )
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
