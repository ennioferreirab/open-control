"""Tests for the LLM-based task planner module (Story 4.5)."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.types import AgentData, ExecutionPlan, ExecutionPlanStep
from nanobot.providers.base import LLMResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(name: str, role: str, skills: list[str]) -> AgentData:
    """Create a test AgentData instance."""
    return AgentData(name=name, display_name=name, role=role, skills=skills)


SAMPLE_AGENTS = [
    _make_agent("code-agent", "developer", ["python", "javascript", "testing"]),
    _make_agent("docs-agent", "writer", ["documentation", "markdown"]),
    _make_agent("review-agent", "reviewer", ["code-review", "testing"]),
]


def _mock_llm_response(data: dict) -> LLMResponse:
    """Create a mock LLM response from a dict."""
    return LLMResponse(content=json.dumps(data))


@pytest.fixture(autouse=True)
def _stub_non_cc_default_model():
    """Keep planner unit tests on the non-CC path unless a test opts in explicitly."""
    cfg = SimpleNamespace(
        agents=SimpleNamespace(
            defaults=SimpleNamespace(model="anthropic/test-model")
        )
    )
    with patch("nanobot.config.loader.load_config", return_value=cfg):
        yield


def _single_step_plan_json() -> dict:
    """A valid single-step plan response."""
    return {
        "steps": [
            {
                "step_id": "step_1",
                "description": "Write the Python utility function",
                "assigned_agent": "code-agent",
                "depends_on": [],
            }
        ]
    }


def _multi_step_plan_json() -> dict:
    """A valid multi-step plan response with dependencies."""
    return {
        "steps": [
            {
                "step_id": "step_1",
                "description": "Write the backend API endpoint",
                "assigned_agent": "code-agent",
                "depends_on": [],
            },
            {
                "step_id": "step_2",
                "description": "Write API documentation",
                "assigned_agent": "docs-agent",
                "depends_on": ["step_1"],
            },
            {
                "step_id": "step_3",
                "description": "Review the implementation",
                "assigned_agent": "review-agent",
                "depends_on": ["step_1", "step_2"],
            },
        ]
    }


# ---------------------------------------------------------------------------
# Task 1 Tests: Core planner module — plan generation
# ---------------------------------------------------------------------------

class TestTaskPlannerSingleStep:
    """Test valid single-step plan generation (Task 4.2 / AC #1)."""

    @pytest.mark.asyncio
    async def test_single_step_plan_generation(self):
        """A simple task should produce a 1-step plan via LLM."""
        from mc.planner import TaskPlanner

        plan_json = _single_step_plan_json()
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=_mock_llm_response(plan_json))

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")):
            plan = await planner.plan_task(
                title="Write a utility function",
                description="Create a Python helper",
                agents=SAMPLE_AGENTS,
            )

        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) == 1
        assert plan.steps[0].temp_id == "step_1"
        assert plan.steps[0].assigned_agent == "code-agent"

    @pytest.mark.asyncio
    async def test_every_task_gets_a_plan(self):
        """Even simple tasks should always produce a plan (AC #1)."""
        from mc.planner import TaskPlanner

        plan_json = _single_step_plan_json()
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=_mock_llm_response(plan_json))

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")):
            plan = await planner.plan_task(
                title="Fix a typo",
                description=None,
                agents=SAMPLE_AGENTS,
            )

        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) >= 1


class TestTaskPlannerMultiStep:
    """Test valid multi-step plan with dependencies (Task 4.3 / AC #3, #6)."""

    @pytest.mark.asyncio
    async def test_multi_step_plan_with_dependencies(self):
        """A complex task should produce a multi-step plan with dependencies."""
        from mc.planner import TaskPlanner

        plan_json = _multi_step_plan_json()
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=_mock_llm_response(plan_json))

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")):
            plan = await planner.plan_task(
                title="Build API endpoint with docs",
                description="Create a REST endpoint, document it, then review",
                agents=SAMPLE_AGENTS,
            )

        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) == 3
        assert plan.steps[0].blocked_by == []
        assert plan.steps[1].blocked_by == ["step_1"]
        assert plan.steps[2].blocked_by == ["step_1", "step_2"]

    @pytest.mark.asyncio
    async def test_multi_step_plan_assigns_different_agents(self):
        """Multi-step plan should assign different agents to different steps."""
        from mc.planner import TaskPlanner

        plan_json = _multi_step_plan_json()
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=_mock_llm_response(plan_json))

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")):
            plan = await planner.plan_task(
                title="Build API endpoint with docs",
                description="Create, document, review",
                agents=SAMPLE_AGENTS,
            )

        agent_names = {s.assigned_agent for s in plan.steps}
        assert len(agent_names) > 1  # Different agents for different steps


class TestTaskPlannerPrompt:
    """Test that the LLM receives a structured prompt (AC #2)."""

    @pytest.mark.asyncio
    async def test_prompt_includes_task_info_and_agent_roster(self):
        """The LLM call should include task info and agent roster."""
        from mc.planner import TaskPlanner

        plan_json = _single_step_plan_json()
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=_mock_llm_response(plan_json))

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")):
            await planner.plan_task(
                title="Write tests",
                description="Unit tests for auth module",
                agents=SAMPLE_AGENTS,
            )

        # Verify chat was called
        mock_provider.chat.assert_called_once()
        call_kwargs = mock_provider.chat.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")

        # Should have system and user messages
        assert len(messages) == 2
        system_msg = messages[0]["content"]
        user_msg = messages[1]["content"]

        # System prompt should mention JSON response format
        assert "JSON" in system_msg or "json" in system_msg

        # User message should include task title and agent info
        assert "Write tests" in user_msg
        assert "Unit tests for auth module" in user_msg
        assert "code-agent" in user_msg
        assert "docs-agent" in user_msg
        assert "review-agent" in user_msg

    @pytest.mark.asyncio
    async def test_prompt_includes_agent_skills(self):
        """Agent skills should be listed in the prompt for LLM reasoning."""
        from mc.planner import TaskPlanner

        plan_json = _single_step_plan_json()
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=_mock_llm_response(plan_json))

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")):
            await planner.plan_task(
                title="Test task",
                description=None,
                agents=SAMPLE_AGENTS,
            )

        call_kwargs = mock_provider.chat.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
        user_msg = messages[1]["content"]

        # Should contain skill information
        assert "python" in user_msg
        assert "documentation" in user_msg
        assert "code-review" in user_msg

    @pytest.mark.asyncio
    async def test_prompt_includes_batch_parallelization_hint_for_multi_item_requests(self):
        """Multi-item requests should carry an explicit batching hint to the LLM."""
        from mc.planner import TaskPlanner

        plan_json = _single_step_plan_json()
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=_mock_llm_response(plan_json))

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")):
            await planner.plan_task(
                title="Transcrever e resumir os ultimos 5 videos deste canal",
                description="Gerar um consolidado dos 5 videos mais recentes do canal no YouTube",
                agents=SAMPLE_AGENTS,
            )

        call_kwargs = mock_provider.chat.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
        user_msg = messages[1]["content"]

        assert "The user explicitly asked for 5 items" in user_msg
        assert "final aggregation or synthesis step" in user_msg
        assert "distinct output artifact" in user_msg

    @pytest.mark.asyncio
    async def test_prompt_injects_lead_agent_planning_skill_content(self):
        """Direct planner path should inline configured planning skill content."""
        from mc.planner import TaskPlanner

        plan_json = _single_step_plan_json()
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=_mock_llm_response(plan_json))

        planner = TaskPlanner()

        with (
            patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")),
            patch(
                "mc.planner._load_lead_agent_planning_skills",
                return_value=(
                    ["writing-plans"],
                    "### Skill: writing-plans\n\nAlways decompose multi-step work carefully.",
                ),
            ),
        ):
            await planner.plan_task(
                title="Write tests",
                description="Unit tests for auth module",
                agents=SAMPLE_AGENTS,
            )

        messages = mock_provider.chat.call_args.kwargs["messages"]
        system_msg = messages[0]["content"]
        assert "Activated Lead-Agent Planning Skills" in system_msg
        assert "writing-plans" in system_msg
        assert "Always decompose multi-step work carefully." in system_msg


class TestTaskPlannerNanobotFallback:
    """Test nanobot fallback for unmatched steps (AC #5)."""

    @pytest.mark.asyncio
    async def test_llm_assigns_nanobot_when_no_specialist(self):
        """LLM plan with nanobot assignment should be preserved."""
        from mc.planner import TaskPlanner

        plan_json = {
            "steps": [
                {
                    "step_id": "step_1",
                    "description": "Do something obscure",
                    "assigned_agent": "nanobot",
                    "depends_on": [],
                }
            ]
        }
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=_mock_llm_response(plan_json))

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")):
            plan = await planner.plan_task(
                title="Obscure task",
                description=None,
                agents=SAMPLE_AGENTS,
            )

        assert plan.steps[0].assigned_agent == "nanobot"

    @pytest.mark.asyncio
    async def test_llm_lead_agent_assignment_is_rewritten_to_general(self):
        """Lead-agent step assignments should be rewritten to nanobot."""
        from mc.planner import TaskPlanner

        plan_json = {
            "steps": [
                {
                    "step_id": "step_1",
                    "description": "Do something obscure",
                    "assigned_agent": "lead-agent",
                    "depends_on": [],
                }
            ]
        }
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=_mock_llm_response(plan_json))

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")):
            plan = await planner.plan_task(
                title="Obscure task",
                description=None,
                agents=SAMPLE_AGENTS,
            )

        assert plan.steps[0].assigned_agent == "nanobot"


# ---------------------------------------------------------------------------
# Task 2 Tests: Agent name validation and fallback
# ---------------------------------------------------------------------------

class TestAgentNameValidation:
    """Test agent name validation — invalid names replaced with nanobot (Task 4.4 / AC #4)."""

    @pytest.mark.asyncio
    async def test_invalid_agent_name_replaced_with_nanobot(self):
        """Invalid agent names in LLM response should be replaced with nanobot."""
        from mc.planner import TaskPlanner

        plan_json = {
            "steps": [
                {
                    "step_id": "step_1",
                    "description": "Do something",
                    "assigned_agent": "nonexistent-agent",
                    "depends_on": [],
                }
            ]
        }
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=_mock_llm_response(plan_json))

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")):
            plan = await planner.plan_task(
                title="Test task",
                description=None,
                agents=SAMPLE_AGENTS,
            )

        assert plan.steps[0].assigned_agent == "nanobot"

    @pytest.mark.asyncio
    async def test_valid_agent_names_preserved(self):
        """Valid agent names in LLM response should remain unchanged."""
        from mc.planner import TaskPlanner

        plan_json = _single_step_plan_json()  # uses "code-agent"
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=_mock_llm_response(plan_json))

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")):
            plan = await planner.plan_task(
                title="Test task",
                description=None,
                agents=SAMPLE_AGENTS,
            )

        assert plan.steps[0].assigned_agent == "code-agent"


class TestAgentNameNoneHandling:
    """Test that None/missing assigned_agent defaults to nanobot (H1 fix)."""

    @pytest.mark.asyncio
    async def test_none_assigned_agent_defaults_to_nanobot(self):
        """When LLM omits assigned_agent, it should default to nanobot."""
        from mc.planner import TaskPlanner

        plan_json = {
            "steps": [
                {
                    "step_id": "step_1",
                    "description": "Do something",
                    "depends_on": [],
                }
            ]
        }
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=_mock_llm_response(plan_json))

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")):
            plan = await planner.plan_task(
                title="Test task",
                description=None,
                agents=SAMPLE_AGENTS,
            )

        assert plan.steps[0].assigned_agent == "nanobot"


class TestExplicitAgentOverride:
    """Test explicit agent override — all steps assigned to user-specified agent (Task 4.5 / AC #8)."""

    @pytest.mark.asyncio
    async def test_explicit_agent_overrides_all_steps(self):
        """When explicit_agent is set, all steps should be assigned to that agent."""
        from mc.planner import TaskPlanner

        plan_json = _multi_step_plan_json()  # 3 steps with different agents
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=_mock_llm_response(plan_json))

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")):
            plan = await planner.plan_task(
                title="Multi-step task",
                description="Complex task",
                agents=SAMPLE_AGENTS,
                explicit_agent="code-agent",
            )

        for step in plan.steps:
            assert step.assigned_agent == "code-agent"

    @pytest.mark.asyncio
    async def test_explicit_lead_agent_override_rewritten_to_general(self):
        """An explicit lead-agent override is blocked and replaced."""
        from mc.planner import TaskPlanner

        plan_json = _single_step_plan_json()
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=_mock_llm_response(plan_json))

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")):
            plan = await planner.plan_task(
                title="Task",
                description="desc",
                agents=SAMPLE_AGENTS,
                explicit_agent="lead-agent",
            )

        assert plan.steps[0].assigned_agent == "nanobot"


class TestLLMFailureFallback:
    """Test LLM failure fallback — provider error triggers heuristic planning (Task 4.6 / AC #9)."""

    @pytest.mark.asyncio
    async def test_provider_error_falls_back_to_heuristic(self):
        """When LLM provider raises an error, fallback to heuristic planning."""
        from mc.planner import TaskPlanner

        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(side_effect=RuntimeError("Provider unavailable"))

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")):
            plan = await planner.plan_task(
                title="Write python tests",
                description="Test the auth module",
                agents=SAMPLE_AGENTS,
            )

        # Should still produce a valid plan (from heuristic fallback)
        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) >= 1
        # Heuristic fallback should still assign an agent
        assert plan.steps[0].assigned_agent is not None

    @pytest.mark.asyncio
    async def test_timeout_error_falls_back_to_heuristic(self):
        """When LLM times out, fallback to heuristic planning."""
        from mc.planner import TaskPlanner

        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(side_effect=TimeoutError("Request timed out"))

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")):
            plan = await planner.plan_task(
                title="Write documentation",
                description="Document the API",
                agents=SAMPLE_AGENTS,
            )

        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) >= 1

    @pytest.mark.asyncio
    async def test_heuristic_fallback_never_returns_lead_agent(self):
        """Heuristic fallback should use nanobot when no specialist matches."""
        from mc.planner import TaskPlanner

        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(side_effect=RuntimeError("Provider unavailable"))
        agents = [
            _make_agent("finance-agent", "finance", ["boletos", "payments"]),
            _make_agent("docs-agent", "docs", ["markdown"]),
        ]

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")):
            plan = await planner.plan_task(
                title="Calibrate quantum transducer mesh",
                description=None,
                agents=agents,
            )

        assert plan.steps[0].assigned_agent == "nanobot"


class TestPlannerReasoningLevel:
    """Ensure reasoning-level config is forwarded into planner provider calls."""

    @pytest.mark.asyncio
    async def test_default_model_is_forwarded_to_provider(self):
        """Planner should pass the resolved default model into create_provider()."""
        from mc.planner import TaskPlanner

        plan_json = _single_step_plan_json()
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=_mock_llm_response(plan_json))

        planner = TaskPlanner()

        with patch(
            "mc.infrastructure.providers.factory.create_provider",
            return_value=(mock_provider, "test-model"),
        ) as create_provider_mock:
            await planner.plan_task(
                title="Write tests",
                description="Unit tests for planner",
                agents=SAMPLE_AGENTS,
            )

        assert create_provider_mock.call_args.kwargs["model"] == "anthropic/test-model"

    @pytest.mark.asyncio
    async def test_reasoning_level_is_forwarded_to_provider(self):
        """Non-CC provider calls should receive the planner reasoning level."""
        from mc.planner import TaskPlanner

        plan_json = _single_step_plan_json()
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=_mock_llm_response(plan_json))

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")):
            await planner.plan_task(
                title="Write tests",
                description="Unit tests for planner",
                agents=SAMPLE_AGENTS,
                reasoning_level="low",
            )

        call_kwargs = mock_provider.chat.call_args
        assert call_kwargs.kwargs["reasoning_level"] == "low"

    @pytest.mark.asyncio
    async def test_cc_planning_receives_configured_lead_agent_skills(self):
        """CC planner path should pass configured lead-agent skills into _cc_plan()."""
        from mc.planner import TaskPlanner

        planner = TaskPlanner(bridge=MagicMock())
        expected_plan = ExecutionPlan(
            steps=[
                ExecutionPlanStep(
                    temp_id="step_1",
                    title="Plan work",
                    description="Plan work",
                    assigned_agent="code-agent",
                    blocked_by=[],
                    parallel_group=1,
                    order=1,
                )
            ]
        )

        with (
            patch(
                "mc.planner._load_lead_agent_planning_skills",
                return_value=(["using-superpowers", "writing-plans"], "skill body"),
            ),
            patch.object(planner, "_cc_plan", AsyncMock(return_value=expected_plan)) as cc_plan_mock,
        ):
            plan = await planner.plan_task(
                title="Plan task",
                description="desc",
                agents=SAMPLE_AGENTS,
                model="cc/claude-sonnet-4-6",
            )

        assert plan is expected_plan
        assert cc_plan_mock.call_args.kwargs["lead_agent_skills"] == [
            "using-superpowers",
            "writing-plans",
        ]


class TestPlannerDiagnosticLogging:
    """Verify planner logs diagnostic details on failure."""

    @pytest.mark.asyncio
    async def test_timeout_logs_specific_message(self):
        """Timeout should log a distinct warning with timeout duration."""
        from mc.planner import TaskPlanner

        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(side_effect=asyncio.TimeoutError())

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")), \
             patch("mc.planner.logger") as mock_logger:
            await planner.plan_task(
                title="Test task",
                description=None,
                agents=SAMPLE_AGENTS,
            )

        # Should log timeout specifically
        timeout_calls = [
            c for c in mock_logger.warning.call_args_list
            if "timed out" in str(c)
        ]
        assert len(timeout_calls) >= 1

    @pytest.mark.asyncio
    async def test_general_error_logs_with_traceback(self):
        """General errors should log with exc_info=True."""
        from mc.planner import TaskPlanner

        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(side_effect=RuntimeError("API exploded"))

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")), \
             patch("mc.planner.logger") as mock_logger:
            await planner.plan_task(
                title="Test task",
                description=None,
                agents=SAMPLE_AGENTS,
            )

        # Should log with exc_info=True
        error_calls = [
            c for c in mock_logger.warning.call_args_list
            if "LLM planning failed" in str(c)
        ]
        assert len(error_calls) >= 1
        # Verify exc_info=True was passed
        assert error_calls[0].kwargs.get("exc_info") is True


class TestPlannerModelParameter:
    """Verify planner passes model to create_provider."""

    @pytest.mark.asyncio
    async def test_model_param_passed_to_provider(self):
        """When model is specified, it should be passed to create_provider."""
        from mc.planner import TaskPlanner

        plan_json = _single_step_plan_json()
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=_mock_llm_response(plan_json))

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "anthropic/claude-sonnet-4-6")) as mock_create:
            await planner.plan_task(
                title="Test task",
                description=None,
                agents=SAMPLE_AGENTS,
                model="anthropic/claude-sonnet-4-6",
            )

        mock_create.assert_called_once_with(model="anthropic/claude-sonnet-4-6")

    @pytest.mark.asyncio
    async def test_no_model_param_passes_none(self):
        """When no model specified, create_provider gets the resolved default model."""
        from mc.planner import TaskPlanner

        plan_json = _single_step_plan_json()
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=_mock_llm_response(plan_json))
        mock_config = MagicMock()
        mock_config.agents.defaults.model = "anthropic/claude-sonnet-4-6"

        planner = TaskPlanner()

        with (
            patch("nanobot.config.loader.load_config", return_value=mock_config),
            patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")) as mock_create,
        ):
            await planner.plan_task(
                title="Test task",
                description=None,
                agents=SAMPLE_AGENTS,
            )

        mock_create.assert_called_once_with(model="anthropic/claude-sonnet-4-6")

    @pytest.mark.asyncio
    async def test_cc_model_routes_to_claude_code_backend(self):
        """cc/ models must use Claude Code backend instead of LiteLLM create_provider()."""
        from mc.planner import TaskPlanner

        bridge = MagicMock()
        planner = TaskPlanner(bridge=bridge)
        mock_ipc = MagicMock()
        mock_ipc.start = AsyncMock()
        mock_ipc.stop = AsyncMock()
        mock_ws_mgr = MagicMock()
        mock_ws_mgr.prepare.return_value = MagicMock(cwd=".", mcp_config=".mcp.json", claude_md="CLAUDE.md", socket_path="/tmp/planner.sock")
        mock_cc_provider = MagicMock()
        mock_cc_provider.execute_task = AsyncMock(return_value=MagicMock(
            is_error=False,
            output=json.dumps(_single_step_plan_json()),
        ))
        mock_config = MagicMock()
        mock_config.agents.defaults.model = "cc/claude-sonnet-4-6"
        mock_config.claude_code = MagicMock(cli_path="claude")

        with (
            patch("nanobot.config.loader.load_config", return_value=mock_config),
            patch("mc.infrastructure.providers.factory.create_provider") as mock_create,
            patch("claude_code.workspace.CCWorkspaceManager", return_value=mock_ws_mgr),
            patch("claude_code.ipc_server.MCSocketServer", return_value=mock_ipc),
            patch("claude_code.provider.ClaudeCodeProvider", return_value=mock_cc_provider),
            patch("mc.infrastructure.orientation.load_orientation", return_value=None),
        ):
            plan = await planner.plan_task(
                title="Test task",
                description="Use CC backend",
                agents=SAMPLE_AGENTS,
                model="cc/claude-sonnet-4-6",
            )

        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) == 1
        assert plan.steps[0].assigned_agent == "code-agent"
        mock_create.assert_not_called()
        mock_cc_provider.execute_task.assert_awaited()


class TestMalformedJSONFallback:
    """Test malformed JSON fallback — invalid LLM output triggers heuristic (Task 4.7 / AC #10)."""

    @pytest.mark.asyncio
    async def test_invalid_json_falls_back_to_heuristic(self):
        """When LLM returns invalid JSON, fallback to heuristic planning."""
        from mc.planner import TaskPlanner

        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=LLMResponse(content="This is not JSON at all"))

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")):
            plan = await planner.plan_task(
                title="Write tests for auth",
                description="Testing task",
                agents=SAMPLE_AGENTS,
            )

        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) >= 1

    @pytest.mark.asyncio
    async def test_json_missing_steps_key_falls_back(self):
        """When LLM returns JSON without 'steps' key, fallback to heuristic."""
        from mc.planner import TaskPlanner

        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=LLMResponse(content='{"plan": "something"}'))

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")):
            plan = await planner.plan_task(
                title="Write tests for auth",
                description="Testing task",
                agents=SAMPLE_AGENTS,
            )

        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) >= 1

    @pytest.mark.asyncio
    async def test_markdown_fenced_json_is_parsed(self):
        """LLM response with markdown code fencing should still be parsed."""
        from mc.planner import TaskPlanner

        plan_json = _single_step_plan_json()
        fenced_response = f"```json\n{json.dumps(plan_json)}\n```"
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=LLMResponse(content=fenced_response))

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")):
            plan = await planner.plan_task(
                title="Test task",
                description=None,
                agents=SAMPLE_AGENTS,
            )

        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) == 1
        assert plan.steps[0].temp_id == "step_1"

    @pytest.mark.asyncio
    async def test_json_with_preamble_and_postamble_is_parsed(self):
        """LLM response with extra prose around JSON should still be parsed."""
        from mc.planner import TaskPlanner

        plan_json = _single_step_plan_json()
        wrapped_response = (
            "Here is the plan you requested:\n\n"
            f"{json.dumps(plan_json)}\n\n"
            "This satisfies the task."
        )
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=LLMResponse(content=wrapped_response))

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")):
            plan = await planner.plan_task(
                title="Test task",
                description=None,
                agents=SAMPLE_AGENTS,
            )

        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) == 1
        assert plan.steps[0].temp_id == "step_1"

    @pytest.mark.asyncio
    async def test_slightly_malformed_json_is_repaired(self):
        """LLM response with minor JSON formatting errors should be repaired."""
        from mc.planner import TaskPlanner

        malformed = """
        {
          "steps": [
            {
              "step_id": "step_1",
              "description": "Write the Python utility function",
              "assigned_agent": "code-agent",
              "depends_on": [],
            }
          ]
        }
        """
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=LLMResponse(content=malformed))

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")):
            plan = await planner.plan_task(
                title="Write a utility function",
                description="Create a Python helper",
                agents=SAMPLE_AGENTS,
            )

        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) == 1
        assert plan.steps[0].assigned_agent == "code-agent"


# ---------------------------------------------------------------------------
# Task 3 Tests: Orchestrator integration
# ---------------------------------------------------------------------------

class TestOrchestratorPlannerIntegration:
    """Test that orchestrator calls planner instead of heuristic routing (Task 4.8 / AC #7, #12)."""

    @pytest.mark.asyncio
    async def test_planning_task_uses_planner(self):
        """_process_planning_task should use TaskPlanner instead of heuristic scoring."""
        from mc.orchestrator import TaskOrchestrator

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.create_activity = MagicMock()
        mock_bridge.update_execution_plan = MagicMock()
        mock_bridge.list_agents = MagicMock(return_value=[
            {"name": "code-agent", "display_name": "Code", "role": "dev", "skills": ["python"]},
        ])

        plan = ExecutionPlan(steps=[
            ExecutionPlanStep(temp_id="step_1", title="Do it", description="Do it", assigned_agent="code-agent"),
        ])

        orch = TaskOrchestrator(mock_bridge)
        task_data = {
            "id": "task_planner_1",
            "title": "Write code",
            "description": "Write some Python",
        }

        with patch("mc.workers.planning.TaskPlanner") as MockPlanner, \
             patch("mc.workers.planning.asyncio.to_thread", side_effect=_to_thread_passthrough):
            mock_planner_instance = MockPlanner.return_value
            mock_planner_instance.plan_task = AsyncMock(return_value=plan)

            await orch._process_planning_task(task_data)

            mock_planner_instance.plan_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_explicit_agent_passed_to_planner(self):
        """When task has assigned_agent, it should be passed as explicit_agent to planner."""
        from mc.orchestrator import TaskOrchestrator

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.create_activity = MagicMock()
        mock_bridge.update_execution_plan = MagicMock()
        mock_bridge.list_agents = MagicMock(return_value=[
            {"name": "code-agent", "display_name": "Code", "role": "dev", "skills": ["python"]},
        ])

        plan = ExecutionPlan(steps=[
            ExecutionPlanStep(temp_id="step_1", title="Do it", description="Do it", assigned_agent="code-agent"),
        ])

        orch = TaskOrchestrator(mock_bridge)
        task_data = {
            "id": "task_planner_2",
            "title": "Write code",
            "description": None,
            "assigned_agent": "code-agent",
        }

        with patch("mc.workers.planning.TaskPlanner") as MockPlanner, \
             patch("mc.workers.planning.asyncio.to_thread", side_effect=_to_thread_passthrough):
            mock_planner_instance = MockPlanner.return_value
            mock_planner_instance.plan_task = AsyncMock(return_value=plan)

            await orch._process_planning_task(task_data)

            call_kwargs = mock_planner_instance.plan_task.call_args
            assert call_kwargs.kwargs.get("explicit_agent") == "code-agent" or \
                   (len(call_kwargs.args) >= 4 and call_kwargs.args[3] == "code-agent")

    @pytest.mark.asyncio
    async def test_plan_stored_and_dispatched(self):
        """After planning, plan should be stored and steps dispatched."""
        from mc.orchestrator import TaskOrchestrator

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.create_activity = MagicMock()
        mock_bridge.update_execution_plan = MagicMock()
        mock_bridge.list_agents = MagicMock(return_value=[
            {"name": "code-agent", "display_name": "Code", "role": "dev", "skills": ["python"]},
        ])

        plan = ExecutionPlan(steps=[
            ExecutionPlanStep(temp_id="step_1", title="Do it", description="Do it", assigned_agent="code-agent"),
        ])

        orch = TaskOrchestrator(mock_bridge)
        task_data = {
            "id": "task_planner_3",
            "title": "Write code",
            "description": None,
        }

        with patch("mc.workers.planning.TaskPlanner") as MockPlanner, \
             patch("mc.workers.planning.asyncio.to_thread", side_effect=_to_thread_passthrough):
            mock_planner_instance = MockPlanner.return_value
            mock_planner_instance.plan_task = AsyncMock(return_value=plan)

            await orch._process_planning_task(task_data)

        # Plan should be stored
        mock_bridge.update_execution_plan.assert_called()
        # Task should be assigned
        mock_bridge.update_task_status.assert_called()

    @pytest.mark.asyncio
    async def test_manual_task_still_skipped(self):
        """Manual tasks should still be skipped (not sent to planner)."""
        from mc.orchestrator import TaskOrchestrator

        mock_bridge = MagicMock()
        mock_bridge.update_task_status = MagicMock()
        mock_bridge.list_agents = MagicMock()

        orch = TaskOrchestrator(mock_bridge)
        task_data = {
            "id": "task_manual_1",
            "title": "Manual task",
            "is_manual": True,
        }

        with patch("mc.workers.planning.TaskPlanner") as MockPlanner, \
             patch("mc.workers.planning.asyncio.to_thread", side_effect=_to_thread_passthrough):
            await orch._process_planning_task(task_data)

            MockPlanner.assert_not_called()
        mock_bridge.update_task_status.assert_not_called()


# ---------------------------------------------------------------------------
# TestEnrichedPlannerFeatures: new roster format and SYSTEM_PROMPT content
# ---------------------------------------------------------------------------


class TestEnrichedPlannerFeatures:
    """Verify enriched planner features: roster format and SYSTEM_PROMPT content."""

    def test_enriched_roster_includes_tools(self):
        """_build_agent_roster output must include a 'Tools:' line with STANDARD_TOOLS."""
        from mc.planner import _build_agent_roster, STANDARD_TOOLS

        agents = [_make_agent("test-agent", "tester", ["python", "testing"])]
        roster = _build_agent_roster(agents)

        assert "Tools:" in roster
        for tool in STANDARD_TOOLS:
            assert tool in roster

    def test_enriched_roster_multiline_format(self):
        """_build_agent_roster uses bold-name multi-line format with Skills: line."""
        from mc.planner import _build_agent_roster

        agents = [_make_agent("code-agent", "developer", ["python", "javascript"])]
        roster = _build_agent_roster(agents)

        assert "**code-agent**" in roster
        assert "Skills: python, javascript" in roster

    def test_system_prompt_has_decomposition_guidance(self):
        """SYSTEM_PROMPT must contain key conceptual sections."""
        from mc.planner import SYSTEM_PROMPT

        assert "Decomposition" in SYSTEM_PROMPT
        assert "Anti-Patterns" in SYSTEM_PROMPT
        assert "Examples" in SYSTEM_PROMPT
        assert "Tool Awareness" in SYSTEM_PROMPT

    def test_system_prompt_encourages_multi_step_for_complex_tasks(self):
        """SYSTEM_PROMPT should NOT say 'most tasks need 1 step'."""
        from mc.planner import SYSTEM_PROMPT

        assert "most tasks need exactly 1 step" not in SYSTEM_PROMPT
        assert "most tasks need only 1 step" not in SYSTEM_PROMPT

    def test_system_prompt_has_few_shot_examples(self):
        """SYSTEM_PROMPT must include at least three numbered examples."""
        from mc.planner import SYSTEM_PROMPT

        assert "Example 1" in SYSTEM_PROMPT
        assert "Example 2" in SYSTEM_PROMPT
        assert "Example 3" in SYSTEM_PROMPT

    def test_user_prompt_template_does_not_bias_single_step(self):
        """USER_PROMPT_TEMPLATE should not bias toward single-step plans."""
        from mc.planner import USER_PROMPT_TEMPLATE

        lower = USER_PROMPT_TEMPLATE.lower()
        assert "most tasks need only 1 step" not in lower
        assert "most tasks need exactly 1 step" not in lower


class TestRemoteTerminalExclusion:
    """Verify remote-terminal agents are excluded from planning."""

    def test_roster_excludes_remote_terminal(self):
        """Agents with role='remote-terminal' must not appear in roster."""
        from mc.planner import _build_agent_roster

        agents = [
            _make_agent("nanobot", "generalist", ["general"]),
            _make_agent("Macbook", "remote-terminal", ["shell"]),
        ]
        roster = _build_agent_roster(agents)

        assert "nanobot" in roster
        assert "Macbook" not in roster

    @pytest.mark.asyncio
    async def test_remote_terminal_agent_replaced_with_nanobot(self):
        """If LLM assigns a remote-terminal agent, it should be replaced."""
        from mc.planner import TaskPlanner

        plan_json = {
            "steps": [{
                "step_id": "step_1",
                "description": "Research something",
                "assigned_agent": "Macbook",
                "depends_on": [],
            }]
        }
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=_mock_llm_response(plan_json))

        agents = [
            _make_agent("nanobot", "generalist", ["general"]),
            AgentData(name="Macbook", display_name="Macbook", role="remote-terminal", skills=["shell"]),
        ]

        planner = TaskPlanner()

        with patch("mc.infrastructure.providers.factory.create_provider", return_value=(mock_provider, "test-model")):
            plan = await planner.plan_task(
                title="Research task",
                description=None,
                agents=agents,
            )

        assert plan.steps[0].assigned_agent == "nanobot"


# ---------------------------------------------------------------------------
# TestOrientationRosterInterpolation: {agent_roster} placeholder substitution
# ---------------------------------------------------------------------------


class TestOrientationRosterInterpolation:
    """Verify that _maybe_inject_orientation interpolates {agent_roster} correctly."""

    def test_orientation_roster_interpolation(self):
        """{agent_roster} placeholder in orientation file is replaced with roster text."""
        from mc.step_dispatcher import _maybe_inject_orientation
        from unittest.mock import patch

        # Mock load_orientation to return interpolated text (roster interpolation
        # is tested in tests/mc/test_orientation.py; here we test delegation).
        with patch(
            "mc.infrastructure.orientation.load_orientation",
            return_value="# Orientation\n\n- **test-agent** — tester (skills: testing)\n\nEnd.",
        ):
            result = _maybe_inject_orientation("test-agent", None)

        assert result is not None
        assert "test-agent" in result
        assert "{agent_roster}" not in result

    def test_orientation_without_placeholder(self):
        """Orientation files without {agent_roster} are returned unchanged (backwards compat)."""
        from mc.step_dispatcher import _maybe_inject_orientation
        from unittest.mock import patch

        with patch(
            "mc.infrastructure.orientation.load_orientation",
            return_value="# Orientation\n\nNo placeholder here.\n\nEnd.",
        ):
            result = _maybe_inject_orientation("test-agent", None)

        assert result is not None
        assert "No placeholder here" in result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _to_thread_passthrough(fn, *args, **kwargs):
    """Replacement for asyncio.to_thread that calls synchronously."""
    return fn(*args, **kwargs)
