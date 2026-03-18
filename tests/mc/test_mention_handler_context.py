"""Tests for enriched context in handle_mention().

Verifies that handle_mention injects mention-specific sections
([Mention], [Task Context], [Execution Plan], [Task Files]) into
the ExecutionRequest built by ContextBuilder, then runs through
ExecutionEngine.

Story 13.2: Full Context for Mentioned Agents.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import mc.contexts.conversation.mentions.handler as handler_module
from mc.application.execution.request import ExecutionRequest, ExecutionResult
from mc.contexts.conversation.mentions.handler import handle_mention


@pytest.fixture
def mock_bridge():
    """Create a mock ConvexBridge with get_task and get_task_messages."""
    bridge = MagicMock()
    bridge.get_task_messages.return_value = [
        {
            "author_name": "User",
            "author_type": "user",
            "message_type": "user_message",
            "content": "Please help with this task.",
        },
    ]
    bridge.get_task.return_value = {
        "title": "Research AI safety",
        "description": "Investigate alignment techniques",
        "status": "in_progress",
        "assigned_agent": "researcher",
        "tags": ["ai", "safety"],
        "board_id": "board_sprint1",
        "execution_plan": {
            "steps": [
                {"title": "Literature review", "status": "completed"},
                {"title": "Summarize findings", "status": "in_progress"},
            ]
        },
        "files": [
            {
                "name": "reference.pdf",
                "description": "Key paper",
                "subfolder": "attachments",
            },
        ],
    }
    bridge.send_message.return_value = None
    bridge.create_activity.return_value = None
    return bridge


def _make_mock_config(prompt="You are a helpful researcher."):
    """Create a mock agent config result."""
    mock_config = MagicMock()
    mock_config.prompt = prompt
    mock_config.model = "gpt-4"
    mock_config.skills = []
    mock_config.display_name = "Researcher"
    return mock_config


class _MentionResult:
    """Container for a handle_mention invocation result."""

    def __init__(self) -> None:
        self.prompt: str = ""


@pytest.fixture
def _mock_agent_env():
    """Mock external dependencies for handle_mention (config validation only).

    ContextBuilder and ExecutionEngine are mocked separately in run_mention.
    """
    mock_config = _make_mock_config()

    mock_agents_dir = MagicMock()
    mock_config_path = MagicMock()
    mock_config_path.exists.return_value = True
    mock_agent_dir = MagicMock()
    mock_agent_dir.__truediv__ = MagicMock(return_value=mock_config_path)
    mock_agent_dir.mkdir = MagicMock()
    mock_agents_dir.__truediv__ = MagicMock(return_value=mock_agent_dir)

    with (
        patch(
            "mc.contexts.conversation.mentions.handler._known_agent_names",
            return_value={"researcher"},
        ),
        patch("mc.infrastructure.config.AGENTS_DIR", mock_agents_dir),
        patch(
            "mc.infrastructure.agents.yaml_validator.validate_agent_file",
            return_value=mock_config,
        ),
    ):
        yield mock_config


@pytest.fixture
def run_mention(mock_bridge, _mock_agent_env):
    """Fixture that runs handle_mention and captures the prompt.

    Mocks ContextBuilder to return a controllable ExecutionRequest and
    captures the final prompt from engine.run().
    """

    async def _run(**overrides) -> _MentionResult:
        result = _MentionResult()

        # Build a base ExecutionRequest that ContextBuilder would return
        base_req = ExecutionRequest(
            entity_type="task",
            entity_id="task123",
            task_id="task123",
            title="Test task",
            description="Base description from ContextBuilder",
            agent_name="researcher",
            agent_prompt=overrides.pop("agent_prompt", "You are a helpful researcher."),
        )

        mock_ctx_builder = MagicMock()
        mock_ctx_builder.build_task_context = AsyncMock(return_value=base_req)

        async def _capture_run(req):
            result.prompt = req.prompt
            return ExecutionResult(success=True, output="Agent response")

        mock_engine = MagicMock()
        mock_engine.run = _capture_run

        defaults = dict(
            bridge=mock_bridge,
            task_id="task123",
            agent_name="researcher",
            query="help",
            caller_message_content="@researcher help",
            task_title="Test task",
        )
        defaults.update(overrides)

        with (
            patch(
                "mc.application.execution.context_builder.ContextBuilder",
                return_value=mock_ctx_builder,
            ),
            patch(
                "mc.application.execution.post_processing.build_execution_engine",
                return_value=mock_engine,
            ),
        ):
            await handle_mention(**defaults)

        return result

    return _run


class TestHandleMentionTaskMetadata:
    """AC1: Task metadata injected into prompt."""

    @pytest.mark.asyncio
    async def test_injects_task_context_section(self, run_mention):
        """handle_mention includes [Task Context] with task metadata."""
        result = await run_mention(
            query="What about alignment?",
            caller_message_content="@researcher What about alignment?",
            task_title="Research AI safety",
        )

        prompt = result.prompt
        assert "[Task Context]" in prompt
        assert "Title: Research AI safety" in prompt
        assert "Description: Investigate alignment techniques" in prompt
        assert "Status: in_progress" in prompt
        assert "Assigned Agent: researcher" in prompt
        assert "Tags: ai, safety" in prompt
        assert "Board ID: board_sprint1" in prompt


class TestHandleMentionExecutionPlan:
    """AC3: Execution plan summary included/omitted correctly."""

    @pytest.mark.asyncio
    async def test_includes_execution_plan(self, run_mention):
        """handle_mention includes [Execution Plan] when plan exists."""
        result = await run_mention()

        prompt = result.prompt
        assert "[Execution Plan]" in prompt
        assert "1. Literature review — completed" in prompt
        assert "2. Summarize findings — in_progress" in prompt

    @pytest.mark.asyncio
    async def test_omits_plan_when_absent(self, mock_bridge, run_mention):
        """handle_mention omits [Execution Plan] when no plan exists."""
        mock_bridge.get_task.return_value = {
            "title": "Simple task",
            "status": "in_progress",
        }

        result = await run_mention(task_title="Simple task")

        assert "[Execution Plan]" not in result.prompt


class TestHandleMentionTaskFiles:
    """AC4: Task file references included/omitted correctly."""

    @pytest.mark.asyncio
    async def test_includes_task_files(self, run_mention):
        """handle_mention includes [Task Files] when files exist."""
        result = await run_mention()

        assert "[Task Files]" in result.prompt
        assert "reference.pdf" in result.prompt

    @pytest.mark.asyncio
    async def test_omits_files_when_absent(self, mock_bridge, run_mention):
        """handle_mention omits [Task Files] when no files attached."""
        mock_bridge.get_task.return_value = {
            "title": "No files task",
            "status": "in_progress",
        }

        result = await run_mention(task_title="No files task")

        assert "[Task Files]" not in result.prompt


class TestBuildMentionContextRemoved:
    """AC2 negative: _build_mention_context is fully removed."""

    def test_no_build_mention_context_function(self):
        """Verify _build_mention_context no longer exists in the module."""
        assert not hasattr(handler_module, "_build_mention_context"), (
            "_build_mention_context should have been removed"
        )

    def test_no_build_mention_context_in_source(self):
        """Verify _build_mention_context is not referenced in handler source."""
        source = inspect.getsource(handler_module)
        assert "_build_mention_context" not in source


class TestHandleMentionPromptStructure:
    """AC5: Prompt structure follows the specified section order."""

    @pytest.mark.asyncio
    async def test_mention_sections_order(self, run_mention):
        """Mention-specific sections appear in correct order: Mention > Task > Plan > Files."""
        result = await run_mention()

        prompt = result.prompt
        mention_idx = prompt.index("[Mention]")
        task_idx = prompt.index("[Task Context]")
        plan_idx = prompt.index("[Execution Plan]")
        files_idx = prompt.index("[Task Files]")

        assert mention_idx < task_idx < plan_idx < files_idx

    @pytest.mark.asyncio
    async def test_agent_prompt_before_mention_sections(self, run_mention):
        """Agent prompt appears before mention-specific sections."""
        result = await run_mention()

        prompt = result.prompt
        researcher_idx = prompt.index("You are a helpful researcher.")
        mention_idx = prompt.index("[Mention]")

        assert researcher_idx < mention_idx

    @pytest.mark.asyncio
    async def test_no_agent_prompt_when_none(self, run_mention):
        """When agent_prompt is None, prompt is just the description."""
        result = await run_mention(agent_prompt=None)

        assert "[Mention]" in result.prompt
        assert "---" not in result.prompt.split("[Mention]")[0]


class TestHandleMentionUsesExecutionEngine:
    """Verify mention handler routes through ExecutionEngine."""

    @pytest.mark.asyncio
    async def test_sets_session_boundary_reason(self, mock_bridge, _mock_agent_env):
        """handle_mention sets session_boundary_reason='mention' on the request."""
        captured_req = {}

        base_req = ExecutionRequest(
            entity_type="task",
            entity_id="task123",
            task_id="task123",
            title="Test task",
            agent_name="researcher",
            agent_prompt="You are a researcher.",
        )

        mock_ctx_builder = MagicMock()
        mock_ctx_builder.build_task_context = AsyncMock(return_value=base_req)

        async def _capture_run(req):
            captured_req["req"] = req
            return ExecutionResult(success=True, output="Agent response")

        mock_engine = MagicMock()
        mock_engine.run = _capture_run

        with (
            patch(
                "mc.application.execution.context_builder.ContextBuilder",
                return_value=mock_ctx_builder,
            ),
            patch(
                "mc.application.execution.post_processing.build_execution_engine",
                return_value=mock_engine,
            ),
        ):
            await handle_mention(
                bridge=mock_bridge,
                task_id="task123",
                agent_name="researcher",
                query="help",
                caller_message_content="@researcher help",
                task_title="Test task",
            )

        assert captured_req["req"].session_boundary_reason == "mention"

    @pytest.mark.asyncio
    async def test_posts_error_on_engine_failure(self, mock_bridge, _mock_agent_env):
        """handle_mention posts error message when engine returns failure."""
        base_req = ExecutionRequest(
            entity_type="task",
            entity_id="task123",
            task_id="task123",
            title="Test task",
            agent_name="researcher",
        )

        mock_ctx_builder = MagicMock()
        mock_ctx_builder.build_task_context = AsyncMock(return_value=base_req)

        async def _fail_run(req):
            return ExecutionResult(success=False, error_message="Model not found")

        mock_engine = MagicMock()
        mock_engine.run = _fail_run

        with (
            patch(
                "mc.application.execution.context_builder.ContextBuilder",
                return_value=mock_ctx_builder,
            ),
            patch(
                "mc.application.execution.post_processing.build_execution_engine",
                return_value=mock_engine,
            ),
        ):
            await handle_mention(
                bridge=mock_bridge,
                task_id="task123",
                agent_name="researcher",
                query="help",
                caller_message_content="@researcher help",
                task_title="Test task",
            )

        # Verify error is posted to the thread
        sent = mock_bridge.send_message.call_args
        assert "error" in sent[0][3].lower() or "Error" in sent[0][3]
        assert "Model not found" in sent[0][3]
