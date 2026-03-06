"""Tests for the ask_agent tool (Story 10.3)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanobot.agent.tools.ask_agent import AskAgentTool
from mc.types import AgentData, LEAD_AGENT_NAME


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent_data(name: str = "secretary") -> AgentData:
    """Create a valid AgentData for testing."""
    return AgentData(
        name=name,
        display_name=name.title(),
        role="Test role",
        prompt="You are a helpful assistant.",
        skills=["research"],
        model="anthropic/claude-sonnet-4-6",
    )


def _make_tool(
    caller: str = "researcher",
    task_id: str = "task_123",
    depth: int = 0,
    bridge: MagicMock | None = None,
) -> AskAgentTool:
    """Create an AskAgentTool with context set."""
    tool = AskAgentTool()
    tool.set_context(
        caller_agent=caller,
        task_id=task_id,
        depth=depth,
        bridge=bridge,
    )
    return tool


def _make_bridge() -> MagicMock:
    """Create a mock ConvexBridge."""
    bridge = MagicMock()
    bridge.send_message = MagicMock()
    return bridge


@pytest.fixture
def agents_dir(tmp_path: Path) -> Path:
    """Create a fake agents directory with a secretary agent."""
    d = tmp_path / "agents"
    sec = d / "secretary"
    sec.mkdir(parents=True)
    (sec / "config.yaml").write_text(
        "name: secretary\nrole: Secretary\nprompt: You are a helpful assistant.\n"
    )
    return d


def _setup_agent_dir(agents_dir: Path, name: str) -> None:
    """Create a minimal agent directory inside the given agents_dir."""
    agent = agents_dir / name
    agent.mkdir(parents=True, exist_ok=True)
    (agent / "config.yaml").write_text(
        f"name: {name}\nrole: Test Agent\nprompt: System prompt.\n"
    )


# ---------------------------------------------------------------------------
# AC1: Tool definition
# ---------------------------------------------------------------------------


class TestAskAgentToolDefinition:
    """Tool has correct name, description, and parameters."""

    def test_name(self) -> None:
        tool = AskAgentTool()
        assert tool.name == "ask_agent"

    def test_description_mentions_synchronous(self) -> None:
        tool = AskAgentTool()
        assert "synchronously" in tool.description

    def test_parameters_has_target_agent(self) -> None:
        tool = AskAgentTool()
        props = tool.parameters["properties"]
        assert "target_agent" in props
        assert props["target_agent"]["type"] == "string"

    def test_parameters_has_question(self) -> None:
        tool = AskAgentTool()
        props = tool.parameters["properties"]
        assert "question" in props
        assert props["question"]["type"] == "string"

    def test_required_fields(self) -> None:
        tool = AskAgentTool()
        assert set(tool.parameters["required"]) == {"target_agent", "question"}

    def test_to_schema(self) -> None:
        tool = AskAgentTool()
        schema = tool.to_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "ask_agent"


# ---------------------------------------------------------------------------
# AC5: Lead agent protection (tested before others since it short-circuits)
# ---------------------------------------------------------------------------


class TestAskAgentLeadAgentProtection:
    """Cannot target the lead agent."""

    @pytest.mark.asyncio
    async def test_lead_agent_string_rejected(self) -> None:
        tool = _make_tool()
        result = await tool.execute(
            target_agent="lead-agent",
            question="Any question?",
        )
        assert "Cannot ask the Lead Agent" in result

    @pytest.mark.asyncio
    async def test_lead_agent_constant_rejected(self) -> None:
        tool = _make_tool()
        result = await tool.execute(
            target_agent=LEAD_AGENT_NAME,
            question="Any question?",
        )
        assert "Cannot ask the Lead Agent" in result

    @pytest.mark.asyncio
    async def test_lead_agent_rejected_before_agent_loading(self) -> None:
        """Lead agent check must happen before any config loading."""
        tool = _make_tool()

        with patch(
            "mc.yaml_validator.validate_agent_file",
        ) as mock_validate:
            result = await tool.execute(
                target_agent="lead-agent",
                question="Any question?",
            )

        mock_validate.assert_not_called()
        assert "Cannot ask the Lead Agent" in result


# ---------------------------------------------------------------------------
# AC3: Depth limit
# ---------------------------------------------------------------------------


class TestAskAgentDepthLimit:
    """Depth >= 2 is rejected."""

    @pytest.mark.asyncio
    async def test_depth_2_returns_error(self) -> None:
        tool = _make_tool(depth=2)
        result = await tool.execute(
            target_agent="secretary",
            question="Anything?",
        )
        assert "depth limit" in result.lower()

    @pytest.mark.asyncio
    async def test_depth_3_returns_error(self) -> None:
        tool = _make_tool(depth=3)
        result = await tool.execute(
            target_agent="secretary",
            question="Anything?",
        )
        assert "depth limit" in result.lower()

    @pytest.mark.asyncio
    async def test_depth_0_is_allowed(self, agents_dir: Path) -> None:
        """Depth 0 is the initial call and should be allowed."""
        bridge = _make_bridge()
        tool = _make_tool(depth=0, bridge=bridge)
        agent_data = _make_agent_data("secretary")

        with (
            patch("mc.infrastructure.config.AGENTS_DIR", agents_dir),
            patch(
                "mc.yaml_validator.validate_agent_file",
                return_value=agent_data,
            ),
            patch(
                "mc.provider_factory.create_provider",
                return_value=(MagicMock(), "anthropic/claude-sonnet-4-6"),
            ),
            patch("nanobot.agent.loop.AgentLoop") as MockLoop,
            patch("nanobot.bus.queue.MessageBus"),
        ):
            mock_inst = MagicMock()
            mock_inst.tools.get.return_value = None
            mock_inst.process_direct = AsyncMock(return_value="OK")
            MockLoop.return_value = mock_inst

            result = await tool.execute(
                target_agent="secretary", question="Test?"
            )

        assert result == "OK"

    @pytest.mark.asyncio
    async def test_depth_1_is_allowed(self, agents_dir: Path) -> None:
        """Depth 1 (A->B) should still be allowed."""
        bridge = _make_bridge()
        tool = _make_tool(depth=1, bridge=bridge)
        agent_data = _make_agent_data("secretary")

        with (
            patch("mc.infrastructure.config.AGENTS_DIR", agents_dir),
            patch(
                "mc.yaml_validator.validate_agent_file",
                return_value=agent_data,
            ),
            patch(
                "mc.provider_factory.create_provider",
                return_value=(MagicMock(), "anthropic/claude-sonnet-4-6"),
            ),
            patch("nanobot.agent.loop.AgentLoop") as MockLoop,
            patch("nanobot.bus.queue.MessageBus"),
        ):
            mock_inst = MagicMock()
            mock_inst.tools.get.return_value = None
            mock_inst.process_direct = AsyncMock(return_value="OK")
            MockLoop.return_value = mock_inst

            result = await tool.execute(
                target_agent="secretary", question="Test?"
            )

        assert result == "OK"

    @pytest.mark.asyncio
    async def test_child_loop_gets_incremented_depth(self, agents_dir: Path) -> None:
        """Child loop's ask_agent tool receives depth + 1."""
        bridge = _make_bridge()
        tool = _make_tool(depth=0, bridge=bridge)
        agent_data = _make_agent_data("secretary")
        child_ask_tool = AskAgentTool()

        with (
            patch("mc.infrastructure.config.AGENTS_DIR", agents_dir),
            patch(
                "mc.yaml_validator.validate_agent_file",
                return_value=agent_data,
            ),
            patch(
                "mc.provider_factory.create_provider",
                return_value=(MagicMock(), "anthropic/claude-sonnet-4-6"),
            ),
            patch("nanobot.agent.loop.AgentLoop") as MockLoop,
            patch("nanobot.bus.queue.MessageBus"),
        ):
            mock_inst = MagicMock()
            mock_inst.tools.get.return_value = child_ask_tool
            mock_inst.process_direct = AsyncMock(return_value="Response")
            MockLoop.return_value = mock_inst

            await tool.execute(
                target_agent="secretary", question="Test?"
            )

        assert child_ask_tool._depth == 1
        assert child_ask_tool._caller_agent == "secretary"
        assert child_ask_tool._task_id == "task_123"
        assert child_ask_tool._bridge is bridge


# ---------------------------------------------------------------------------
# AC2: Successful ask (synchronous execution)
# ---------------------------------------------------------------------------


class TestAskAgentSuccess:
    """Successful inter-agent question-answer flow."""

    @pytest.mark.asyncio
    async def test_successful_ask_returns_response(self, agents_dir: Path) -> None:
        bridge = _make_bridge()
        tool = _make_tool(bridge=bridge)
        agent_data = _make_agent_data("secretary")

        with (
            patch("mc.infrastructure.config.AGENTS_DIR", agents_dir),
            patch(
                "mc.yaml_validator.validate_agent_file",
                return_value=agent_data,
            ),
            patch(
                "mc.provider_factory.create_provider",
                return_value=(MagicMock(), "anthropic/claude-sonnet-4-6"),
            ),
            patch("nanobot.agent.loop.AgentLoop") as MockLoop,
            patch("nanobot.bus.queue.MessageBus"),
        ):
            mock_inst = MagicMock()
            mock_inst.tools.get.return_value = None
            mock_inst.process_direct = AsyncMock(
                return_value="The report should use PDF format."
            )
            MockLoop.return_value = mock_inst

            result = await tool.execute(
                target_agent="secretary",
                question="What format should the report use?",
            )

        assert "PDF format" in result

    @pytest.mark.asyncio
    async def test_successful_ask_logs_to_thread(self, agents_dir: Path) -> None:
        bridge = _make_bridge()
        tool = _make_tool(bridge=bridge, task_id="task_456")
        agent_data = _make_agent_data("secretary")

        with (
            patch("mc.infrastructure.config.AGENTS_DIR", agents_dir),
            patch(
                "mc.yaml_validator.validate_agent_file",
                return_value=agent_data,
            ),
            patch(
                "mc.provider_factory.create_provider",
                return_value=(MagicMock(), "anthropic/claude-sonnet-4-6"),
            ),
            patch("nanobot.agent.loop.AgentLoop") as MockLoop,
            patch("nanobot.bus.queue.MessageBus"),
        ):
            mock_inst = MagicMock()
            mock_inst.tools.get.return_value = None
            mock_inst.process_direct = AsyncMock(
                return_value="Use markdown format."
            )
            MockLoop.return_value = mock_inst

            await tool.execute(
                target_agent="secretary",
                question="What format?",
            )

        bridge.send_message.assert_called_once()
        call_args = bridge.send_message.call_args
        assert call_args[0][0] == "task_456"
        assert call_args[0][1] == "System"
        assert call_args[0][2] == "system"
        assert "researcher asked secretary" in call_args[0][3]
        assert call_args[0][4] == "system_event"


# ---------------------------------------------------------------------------
# AC4: Timeout protection
# ---------------------------------------------------------------------------


class TestAskAgentTimeout:
    """Timeout after 120 seconds."""

    @pytest.mark.asyncio
    async def test_timeout_returns_error_message(self, agents_dir: Path) -> None:
        tool = _make_tool()
        agent_data = _make_agent_data("secretary")

        async def slow_process(*args, **kwargs):
            await asyncio.sleep(300)
            return "Too late"

        with (
            patch("mc.infrastructure.config.AGENTS_DIR", agents_dir),
            patch(
                "mc.yaml_validator.validate_agent_file",
                return_value=agent_data,
            ),
            patch(
                "mc.provider_factory.create_provider",
                return_value=(MagicMock(), "anthropic/claude-sonnet-4-6"),
            ),
            patch("nanobot.agent.loop.AgentLoop") as MockLoop,
            patch("nanobot.bus.queue.MessageBus"),
        ):
            mock_inst = MagicMock()
            mock_inst.tools.get.return_value = None
            mock_inst.process_direct = slow_process
            MockLoop.return_value = mock_inst

            # Patch asyncio.wait_for in ask_agent to use short timeout
            original_wait_for = asyncio.wait_for

            async def quick_wait_for(coro, *, timeout=None):
                return await original_wait_for(coro, timeout=0.05)

            with patch(
                "nanobot.agent.tools.ask_agent.asyncio.wait_for",
                side_effect=quick_wait_for,
            ):
                result = await tool.execute(
                    target_agent="secretary",
                    question="This will time out",
                )

        assert "timed out" in result.lower()
        assert "secretary" in result


# ---------------------------------------------------------------------------
# AC6: Thread logging
# ---------------------------------------------------------------------------


class TestAskAgentThreadLogging:
    """Inter-agent conversations are logged to the task thread."""

    @pytest.mark.asyncio
    async def test_log_includes_caller_and_target(self, agents_dir: Path) -> None:
        bridge = _make_bridge()
        tool = _make_tool(caller="researcher", bridge=bridge, task_id="t_1")
        agent_data = _make_agent_data("secretary")

        with (
            patch("mc.infrastructure.config.AGENTS_DIR", agents_dir),
            patch(
                "mc.yaml_validator.validate_agent_file",
                return_value=agent_data,
            ),
            patch(
                "mc.provider_factory.create_provider",
                return_value=(MagicMock(), "anthropic/claude-sonnet-4-6"),
            ),
            patch("nanobot.agent.loop.AgentLoop") as MockLoop,
            patch("nanobot.bus.queue.MessageBus"),
        ):
            mock_inst = MagicMock()
            mock_inst.tools.get.return_value = None
            mock_inst.process_direct = AsyncMock(return_value="Use CSV.")
            MockLoop.return_value = mock_inst

            await tool.execute(
                target_agent="secretary",
                question="What format?",
            )

        call_args = bridge.send_message.call_args[0]
        content = call_args[3]
        assert "researcher asked secretary" in content
        assert "What format?" in content
        assert "Use CSV." in content

    @pytest.mark.asyncio
    async def test_no_log_without_bridge(self, agents_dir: Path) -> None:
        """No thread logging when bridge is None."""
        tool = _make_tool(bridge=None)
        agent_data = _make_agent_data("secretary")

        with (
            patch("mc.infrastructure.config.AGENTS_DIR", agents_dir),
            patch(
                "mc.yaml_validator.validate_agent_file",
                return_value=agent_data,
            ),
            patch(
                "mc.provider_factory.create_provider",
                return_value=(MagicMock(), "anthropic/claude-sonnet-4-6"),
            ),
            patch("nanobot.agent.loop.AgentLoop") as MockLoop,
            patch("nanobot.bus.queue.MessageBus"),
        ):
            mock_inst = MagicMock()
            mock_inst.tools.get.return_value = None
            mock_inst.process_direct = AsyncMock(return_value="OK")
            MockLoop.return_value = mock_inst

            result = await tool.execute(
                target_agent="secretary",
                question="Test?",
            )

        assert result == "OK"

    @pytest.mark.asyncio
    async def test_log_truncates_long_response(self, agents_dir: Path) -> None:
        """Response in thread log is truncated to 500 chars."""
        bridge = _make_bridge()
        tool = _make_tool(bridge=bridge)
        agent_data = _make_agent_data("secretary")
        long_response = "A" * 1000

        with (
            patch("mc.infrastructure.config.AGENTS_DIR", agents_dir),
            patch(
                "mc.yaml_validator.validate_agent_file",
                return_value=agent_data,
            ),
            patch(
                "mc.provider_factory.create_provider",
                return_value=(MagicMock(), "anthropic/claude-sonnet-4-6"),
            ),
            patch("nanobot.agent.loop.AgentLoop") as MockLoop,
            patch("nanobot.bus.queue.MessageBus"),
        ):
            mock_inst = MagicMock()
            mock_inst.tools.get.return_value = None
            mock_inst.process_direct = AsyncMock(return_value=long_response)
            MockLoop.return_value = mock_inst

            result = await tool.execute(
                target_agent="secretary", question="Long answer?"
            )

        # Full response returned to caller
        assert result == long_response
        # Thread log truncated
        logged_content = bridge.send_message.call_args[0][3]
        assert len(logged_content) < len(long_response)
        response_part = logged_content.split("Response: ")[1]
        assert len(response_part) == 500

    @pytest.mark.asyncio
    async def test_thread_log_failure_does_not_break_tool(
        self, agents_dir: Path
    ) -> None:
        """If thread logging fails, the tool still returns the response."""
        bridge = _make_bridge()
        bridge.send_message.side_effect = Exception("Convex down")
        tool = _make_tool(bridge=bridge)
        agent_data = _make_agent_data("secretary")

        with (
            patch("mc.infrastructure.config.AGENTS_DIR", agents_dir),
            patch(
                "mc.yaml_validator.validate_agent_file",
                return_value=agent_data,
            ),
            patch(
                "mc.provider_factory.create_provider",
                return_value=(MagicMock(), "anthropic/claude-sonnet-4-6"),
            ),
            patch("nanobot.agent.loop.AgentLoop") as MockLoop,
            patch("nanobot.bus.queue.MessageBus"),
        ):
            mock_inst = MagicMock()
            mock_inst.tools.get.return_value = None
            mock_inst.process_direct = AsyncMock(return_value="OK")
            MockLoop.return_value = mock_inst

            result = await tool.execute(
                target_agent="secretary", question="Test?"
            )

        assert result == "OK"


# ---------------------------------------------------------------------------
# AC7: Agent not found
# ---------------------------------------------------------------------------


class TestAskAgentNotFound:
    """Target agent not found returns available agents list."""

    @pytest.mark.asyncio
    async def test_agent_not_found_lists_available(self, tmp_path: Path) -> None:
        tool = _make_tool()

        agents_dir = tmp_path / "agents"
        _setup_agent_dir(agents_dir, "researcher")
        _setup_agent_dir(agents_dir, "writer")

        with patch("mc.infrastructure.config.AGENTS_DIR", agents_dir):
            result = await tool.execute(
                target_agent="nonexistent",
                question="Any question?",
            )

        assert "not found" in result.lower()
        assert "researcher" in result
        assert "writer" in result

    @pytest.mark.asyncio
    async def test_agent_config_invalid_lists_available(
        self, tmp_path: Path
    ) -> None:
        tool = _make_tool()

        agents_dir = tmp_path / "agents"
        _setup_agent_dir(agents_dir, "bad-agent")
        _setup_agent_dir(agents_dir, "good-agent")

        with (
            patch("mc.infrastructure.config.AGENTS_DIR", agents_dir),
            patch(
                "mc.yaml_validator.validate_agent_file",
                return_value=["Missing required field: name"],
            ),
        ):
            result = await tool.execute(
                target_agent="bad-agent",
                question="Any question?",
            )

        assert "invalid" in result.lower()


# ---------------------------------------------------------------------------
# Context / no-context edge cases
# ---------------------------------------------------------------------------


class TestAskAgentNoContext:
    """Tool returns error when called without MC context."""

    @pytest.mark.asyncio
    async def test_no_caller_returns_error(self) -> None:
        tool = AskAgentTool()
        result = await tool.execute(
            target_agent="secretary",
            question="Any question?",
        )
        assert "no caller context" in result.lower()


# ---------------------------------------------------------------------------
# Provider error handling
# ---------------------------------------------------------------------------


class TestAskAgentProviderError:
    """Provider creation failure is handled gracefully."""

    @pytest.mark.asyncio
    async def test_provider_error_returns_message(self, agents_dir: Path) -> None:
        tool = _make_tool()
        agent_data = _make_agent_data("secretary")

        with (
            patch("mc.infrastructure.config.AGENTS_DIR", agents_dir),
            patch(
                "mc.yaml_validator.validate_agent_file",
                return_value=agent_data,
            ),
            patch(
                "mc.provider_factory.create_provider",
                side_effect=Exception("OAuth expired"),
            ),
        ):
            result = await tool.execute(
                target_agent="secretary",
                question="What format?",
            )

        assert "Failed to create provider" in result
        assert "secretary" in result

    @pytest.mark.asyncio
    async def test_generic_execution_error(self, agents_dir: Path) -> None:
        """Unhandled exception during process_direct is caught."""
        tool = _make_tool()
        agent_data = _make_agent_data("secretary")

        with (
            patch("mc.infrastructure.config.AGENTS_DIR", agents_dir),
            patch(
                "mc.yaml_validator.validate_agent_file",
                return_value=agent_data,
            ),
            patch(
                "mc.provider_factory.create_provider",
                return_value=(MagicMock(), "anthropic/claude-sonnet-4-6"),
            ),
            patch("nanobot.agent.loop.AgentLoop") as MockLoop,
            patch("nanobot.bus.queue.MessageBus"),
        ):
            mock_inst = MagicMock()
            mock_inst.tools.get.return_value = None
            mock_inst.process_direct = AsyncMock(
                side_effect=RuntimeError("Something broke")
            )
            MockLoop.return_value = mock_inst

            result = await tool.execute(
                target_agent="secretary",
                question="This will break",
            )

        assert "ask_agent failed" in result
        assert "Something broke" in result


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


class TestAskAgentPromptConstruction:
    """Verify the prompt passed to the child AgentLoop."""

    @pytest.mark.asyncio
    async def test_prompt_includes_system_instructions_when_agent_has_prompt(
        self, agents_dir: Path
    ) -> None:
        tool = _make_tool()
        agent_data = _make_agent_data("secretary")

        with (
            patch("mc.infrastructure.config.AGENTS_DIR", agents_dir),
            patch(
                "mc.yaml_validator.validate_agent_file",
                return_value=agent_data,
            ),
            patch(
                "mc.provider_factory.create_provider",
                return_value=(MagicMock(), "anthropic/claude-sonnet-4-6"),
            ),
            patch("nanobot.agent.loop.AgentLoop") as MockLoop,
            patch("nanobot.bus.queue.MessageBus"),
        ):
            mock_inst = MagicMock()
            mock_inst.tools.get.return_value = None
            mock_inst.process_direct = AsyncMock(return_value="OK")
            MockLoop.return_value = mock_inst

            await tool.execute(
                target_agent="secretary",
                question="What format?",
            )

            # Check content passed to process_direct
            call_kwargs = mock_inst.process_direct.call_args
            content = call_kwargs.kwargs.get("content", "")
            assert "[System instructions]" in content
            assert "You are a helpful assistant." in content
            assert "[Inter-agent query]" in content
            assert "What format?" in content

    @pytest.mark.asyncio
    async def test_prompt_without_agent_prompt(self, agents_dir: Path) -> None:
        """When agent has no prompt, just the focused query is passed."""
        tool = _make_tool()
        agent_data = _make_agent_data("secretary")
        agent_data.prompt = None

        with (
            patch("mc.infrastructure.config.AGENTS_DIR", agents_dir),
            patch(
                "mc.yaml_validator.validate_agent_file",
                return_value=agent_data,
            ),
            patch(
                "mc.provider_factory.create_provider",
                return_value=(MagicMock(), "anthropic/claude-sonnet-4-6"),
            ),
            patch("nanobot.agent.loop.AgentLoop") as MockLoop,
            patch("nanobot.bus.queue.MessageBus"),
        ):
            mock_inst = MagicMock()
            mock_inst.tools.get.return_value = None
            mock_inst.process_direct = AsyncMock(return_value="OK")
            MockLoop.return_value = mock_inst

            await tool.execute(
                target_agent="secretary",
                question="What format?",
            )

            content = mock_inst.process_direct.call_args.kwargs.get("content", "")
            assert "[System instructions]" not in content
            assert "What format?" in content
            assert "researcher" in content

    @pytest.mark.asyncio
    async def test_session_key_format(self, agents_dir: Path) -> None:
        """Session key follows mc:ask:{caller}:{target}:{uuid} format."""
        tool = _make_tool(caller="researcher")
        agent_data = _make_agent_data("secretary")

        with (
            patch("mc.infrastructure.config.AGENTS_DIR", agents_dir),
            patch(
                "mc.yaml_validator.validate_agent_file",
                return_value=agent_data,
            ),
            patch(
                "mc.provider_factory.create_provider",
                return_value=(MagicMock(), "anthropic/claude-sonnet-4-6"),
            ),
            patch("nanobot.agent.loop.AgentLoop") as MockLoop,
            patch("nanobot.bus.queue.MessageBus"),
        ):
            mock_inst = MagicMock()
            mock_inst.tools.get.return_value = None
            mock_inst.process_direct = AsyncMock(return_value="OK")
            MockLoop.return_value = mock_inst

            await tool.execute(
                target_agent="secretary",
                question="Test?",
            )

            session_key = mock_inst.process_direct.call_args.kwargs.get(
                "session_key", ""
            )
            assert session_key.startswith("mc:ask:researcher:secretary:")
            uuid_part = session_key.split(":")[-1]
            assert len(uuid_part) == 8


# ---------------------------------------------------------------------------
# Tier model resolution (regression: tier:xxx was passed raw to litellm → crash)
# ---------------------------------------------------------------------------


class TestAskAgentTierResolution:
    """Tier-based model references must be resolved before create_provider is called."""

    @pytest.fixture
    def agents_dir_with_nanobot(self, agents_dir: Path) -> Path:
        """agents_dir with a nanobot agent using a tier model."""
        nanobot_dir = agents_dir / "nanobot"
        nanobot_dir.mkdir(parents=True, exist_ok=True)
        (nanobot_dir / "config.yaml").write_text(
            "name: nanobot\nrole: Assistant\nprompt: You are nanobot.\nmodel: tier:standard-medium\n"
        )
        return agents_dir

    @pytest.mark.asyncio
    async def test_tier_model_resolved_before_provider_creation(
        self, agents_dir_with_nanobot: Path
    ) -> None:
        """tier:standard-medium is resolved to a real model ID before create_provider."""
        bridge = _make_bridge()
        tool = _make_tool(bridge=bridge)
        agent_data = _make_agent_data("nanobot")
        agent_data.model = "tier:standard-medium"  # real tier string triggers resolution

        with (
            patch("mc.infrastructure.config.AGENTS_DIR", agents_dir_with_nanobot),
            patch("mc.yaml_validator.validate_agent_file", return_value=agent_data),
            patch("mc.tier_resolver.TierResolver") as MockResolver,
            patch("mc.provider_factory.create_provider", return_value=(MagicMock(), "claude-sonnet-4-6")) as mock_create,
            patch("nanobot.agent.loop.AgentLoop") as MockLoop,
            patch("nanobot.bus.queue.MessageBus"),
        ):
            MockResolver.return_value.resolve_model.return_value = "claude-sonnet-4-6"
            mock_inst = MagicMock()
            mock_inst.tools.get.return_value = None
            mock_inst.process_direct = AsyncMock(return_value="OK")
            MockLoop.return_value = mock_inst

            await tool.execute(target_agent="nanobot", question="Help?")

        assert mock_create.called, "create_provider was never called"
        called_model = mock_create.call_args[0][0]
        assert "tier:" not in (called_model or ""), (
            f"Tier reference leaked into create_provider: {called_model!r} — litellm would crash"
        )
        assert called_model == "claude-sonnet-4-6"

    @pytest.mark.asyncio
    async def test_tier_model_without_bridge_returns_error(
        self, agents_dir_with_nanobot: Path
    ) -> None:
        """Without a bridge, tier resolution is impossible — return a clear error."""
        tool = _make_tool(bridge=None)
        agent_data = _make_agent_data("nanobot")
        agent_data.model = "tier:standard-medium"

        with (
            patch("mc.infrastructure.config.AGENTS_DIR", agents_dir_with_nanobot),
            patch("mc.yaml_validator.validate_agent_file", return_value=agent_data),
        ):
            result = await tool.execute(target_agent="nanobot", question="Help?")

        assert "tier" in result.lower()
        assert "tier:standard-medium" in result


# ---------------------------------------------------------------------------
# set_context
# ---------------------------------------------------------------------------


class TestSetContext:
    """set_context() properly stores all context variables."""

    def test_set_context_stores_all_values(self) -> None:
        tool = AskAgentTool()
        bridge = _make_bridge()
        tool.set_context(
            caller_agent="agent-a",
            task_id="task_x",
            depth=1,
            bridge=bridge,
        )
        assert tool._caller_agent == "agent-a"
        assert tool._task_id == "task_x"
        assert tool._depth == 1
        assert tool._bridge is bridge

    def test_initial_state(self) -> None:
        tool = AskAgentTool()
        assert tool._caller_agent is None
        assert tool._task_id is None
        assert tool._depth == 0
        assert tool._bridge is None
