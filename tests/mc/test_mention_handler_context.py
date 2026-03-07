"""Tests for enriched context in handle_mention().

Verifies that handle_mention injects task metadata, uses ThreadContextBuilder
with max_messages=20, includes execution plan summary, and removes
_build_mention_context entirely.

Story 13.2: Full Context for Mentioned Agents.
"""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock, patch

import pytest

import mc.mentions.handler as handler_module
from mc.mentions.handler import handle_mention


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


@pytest.fixture
def _mock_agent_env():
    """Mock all external dependencies used inside handle_mention.

    Since handle_mention uses local imports for config and validation,
    we must patch the source modules, not mc.mentions.handler attributes.
    """
    mock_config = _make_mock_config()

    mock_agents_dir = MagicMock()
    # AGENTS_DIR / agent_name / "config.yaml" — must return a path with exists()=True
    mock_config_path = MagicMock()
    mock_config_path.exists.return_value = True
    mock_agent_dir = MagicMock()
    mock_agent_dir.__truediv__ = MagicMock(return_value=mock_config_path)
    mock_agent_dir.mkdir = MagicMock()
    mock_agents_dir.__truediv__ = MagicMock(return_value=mock_agent_dir)

    with (
        patch(
            "mc.mentions.handler._known_agent_names",
            return_value={"researcher"},
        ),
        patch("mc.infrastructure.config.AGENTS_DIR", mock_agents_dir),
        patch(
            "mc.infrastructure.agents.yaml_validator.validate_agent_file",
            return_value=mock_config,
        ),
        patch("mc.infrastructure.orientation.load_orientation", return_value=None),
        patch("mc.types.is_tier_reference", return_value=False),
    ):
        yield mock_config


class _MentionResult:
    """Container for a handle_mention invocation result."""

    def __init__(self) -> None:
        self.content: str = ""


@pytest.fixture
def run_mention(mock_bridge, _mock_agent_env):
    """Fixture that runs handle_mention and captures the prompt sent to the agent.

    Returns an async callable that accepts optional overrides for handle_mention
    kwargs and returns a ``_MentionResult`` whose ``.content`` holds the captured
    prompt string.
    """

    async def _run(**overrides) -> _MentionResult:
        result = _MentionResult()

        async def _capture(**kwargs):
            result.content = kwargs.get("content", "")
            return "Agent response"

        mock_loop = MagicMock()
        mock_loop.process_direct = _capture
        mock_loop.tools = {}

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
                "mc.infrastructure.providers.factory.create_provider",
                return_value=("prov", "model"),
            ),
            patch("nanobot.agent.loop.AgentLoop", return_value=mock_loop),
            patch("nanobot.bus.queue.MessageBus"),
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

        content = result.content
        assert "[Task Context]" in content
        assert "Title: Research AI safety" in content
        assert "Description: Investigate alignment techniques" in content
        assert "Status: in_progress" in content
        assert "Assigned Agent: researcher" in content
        assert "Tags: ai, safety" in content
        assert "Board ID: board_sprint1" in content


class TestHandleMentionThreadContext:
    """AC2: ThreadContextBuilder used with max_messages=20."""

    @pytest.mark.asyncio
    async def test_uses_thread_context_builder(self, run_mention):
        """handle_mention calls ThreadContextBuilder.build with max_messages=20."""
        captured_args = {}

        class CapturingBuilder:
            def build(self, messages, max_messages=20, **kwargs):
                captured_args["messages"] = messages
                captured_args["max_messages"] = max_messages
                return "[Thread History]\nUser: test message"

        with patch("mc.mentions.handler.ThreadContextBuilder", CapturingBuilder):
            await run_mention()

        assert captured_args["max_messages"] == 20


class TestHandleMentionExecutionPlan:
    """AC3: Execution plan summary included/omitted correctly."""

    @pytest.mark.asyncio
    async def test_includes_execution_plan(self, run_mention):
        """handle_mention includes [Execution Plan] when plan exists."""
        result = await run_mention()

        content = result.content
        assert "[Execution Plan]" in content
        assert "1. Literature review — completed" in content
        assert "2. Summarize findings — in_progress" in content

    @pytest.mark.asyncio
    async def test_omits_plan_when_absent(self, mock_bridge, run_mention):
        """handle_mention omits [Execution Plan] when no plan exists."""
        mock_bridge.get_task.return_value = {
            "title": "Simple task",
            "status": "in_progress",
        }

        result = await run_mention(task_title="Simple task")

        assert "[Execution Plan]" not in result.content


class TestHandleMentionTaskFiles:
    """AC4: Task file references included/omitted correctly."""

    @pytest.mark.asyncio
    async def test_includes_task_files(self, run_mention):
        """handle_mention includes [Task Files] when files exist."""
        result = await run_mention()

        assert "[Task Files]" in result.content
        assert "reference.pdf" in result.content

    @pytest.mark.asyncio
    async def test_omits_files_when_absent(self, mock_bridge, run_mention):
        """handle_mention omits [Task Files] when no files attached."""
        mock_bridge.get_task.return_value = {
            "title": "No files task",
            "status": "in_progress",
        }

        result = await run_mention(task_title="No files task")

        assert "[Task Files]" not in result.content


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
    async def test_section_order(self, run_mention):
        """Sections appear in correct order: System > Mention > Task > Plan > Files."""
        result = await run_mention()

        content = result.content

        # Verify section order
        sys_idx = content.index("[System instructions]")
        mention_idx = content.index("[Mention]")
        task_idx = content.index("[Task Context]")
        plan_idx = content.index("[Execution Plan]")
        files_idx = content.index("[Task Files]")

        assert sys_idx < mention_idx < task_idx < plan_idx < files_idx

    @pytest.mark.asyncio
    async def test_no_system_instructions_when_prompt_none(
        self, _mock_agent_env, run_mention
    ):
        """Verifies [System instructions] section is omitted when agent prompt is None."""
        _mock_agent_env.prompt = None

        result = await run_mention()

        assert "[System instructions]" not in result.content
        assert "[Mention]" in result.content
