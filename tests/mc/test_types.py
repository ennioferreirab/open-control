"""Unit tests for mc.types — ClaudeCodeOpts and related dataclasses (CC-1)."""

from __future__ import annotations

import pytest
from nanobot.config.schema import ClaudeCodeConfig
from pydantic import ValidationError

from mc.types import (
    CC_AVAILABLE_MODELS,
    AgentData,
    ClaudeCodeOpts,
    ExecutionPlan,
    ExecutionPlanStep,
    extract_cc_model_name,
    is_cc_model,
)


class TestClaudeCodeOpts:
    """Tests for the ClaudeCodeOpts dataclass."""

    def test_default_values(self) -> None:
        opts = ClaudeCodeOpts()
        assert opts.max_budget_usd is None
        assert opts.max_turns is None
        assert opts.permission_mode == "acceptEdits"
        assert opts.allowed_tools is None
        assert opts.disallowed_tools is None

    def test_custom_values(self) -> None:
        opts = ClaudeCodeOpts(
            max_budget_usd=20.0,
            max_turns=100,
            permission_mode="bypassPermissions",
            allowed_tools=["Bash", "Edit", "Read"],
            disallowed_tools=["WebFetch"],
        )
        assert opts.max_budget_usd == 20.0
        assert opts.max_turns == 100
        assert opts.permission_mode == "bypassPermissions"
        assert opts.allowed_tools == ["Bash", "Edit", "Read"]
        assert opts.disallowed_tools == ["WebFetch"]

    def test_partial_values(self) -> None:
        opts = ClaudeCodeOpts(max_budget_usd=5.0)
        assert opts.max_budget_usd == 5.0
        assert opts.max_turns is None
        assert opts.permission_mode == "acceptEdits"

    def test_max_turns_only(self) -> None:
        opts = ClaudeCodeOpts(max_turns=50)
        assert opts.max_budget_usd is None
        assert opts.max_turns == 50

    def test_allowed_tools_empty_list(self) -> None:
        opts = ClaudeCodeOpts(allowed_tools=[])
        assert opts.allowed_tools == []

    def test_disallowed_tools_multiple(self) -> None:
        opts = ClaudeCodeOpts(disallowed_tools=["WebFetch", "Bash"])
        assert opts.disallowed_tools == ["WebFetch", "Bash"]


class TestAgentDataBackendFields:
    """Tests for backend and claude_code_opts fields on AgentData."""

    def test_agent_data_default_backend(self) -> None:
        agent = AgentData(name="test-agent", display_name="Test Agent", role="Tester")
        assert agent.backend == "nanobot"
        assert agent.claude_code_opts is None

    def test_agent_data_claude_code_backend(self) -> None:
        opts = ClaudeCodeOpts(max_budget_usd=10.0, max_turns=30)
        agent = AgentData(
            name="cc-agent",
            display_name="CC Agent",
            role="Claude Code Agent",
            backend="claude-code",
            claude_code_opts=opts,
        )
        assert agent.backend == "claude-code"
        assert agent.claude_code_opts is opts
        assert agent.claude_code_opts.max_budget_usd == 10.0
        assert agent.claude_code_opts.max_turns == 30

    def test_agent_data_nanobot_backend_explicit(self) -> None:
        agent = AgentData(
            name="nano-agent",
            display_name="Nano Agent",
            role="Nanobot Agent",
            backend="nanobot",
        )
        assert agent.backend == "nanobot"
        assert agent.claude_code_opts is None

    def test_agent_data_claude_code_opts_none_with_claude_code_backend(self) -> None:
        """Backend can be set to claude-code without opts (opts is optional)."""
        agent = AgentData(
            name="cc-agent",
            display_name="CC Agent",
            role="Claude Code Agent",
            backend="claude-code",
            claude_code_opts=None,
        )
        assert agent.backend == "claude-code"
        assert agent.claude_code_opts is None


class TestClaudeCodeConfig:
    """Tests for the ClaudeCodeConfig global schema model (CC-1)."""

    def test_default_values(self) -> None:
        cfg = ClaudeCodeConfig()
        assert cfg.cli_path == "claude"
        assert cfg.default_model == "claude-sonnet-4-6"
        assert cfg.default_max_budget_usd == 5.0
        assert cfg.default_max_turns == 50
        assert cfg.default_permission_mode == "acceptEdits"
        assert cfg.auth_method == "oauth"

    def test_valid_auth_method_api_key(self) -> None:
        cfg = ClaudeCodeConfig(auth_method="api_key")
        assert cfg.auth_method == "api_key"

    def test_invalid_auth_method_raises_error(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ClaudeCodeConfig(auth_method="token")
        assert "auth_method" in str(exc_info.value)

    def test_negative_budget_raises_error(self) -> None:
        with pytest.raises(ValidationError):
            ClaudeCodeConfig(default_max_budget_usd=-1.0)

    def test_zero_budget_is_valid(self) -> None:
        cfg = ClaudeCodeConfig(default_max_budget_usd=0.0)
        assert cfg.default_max_budget_usd == 0.0

    def test_zero_max_turns_raises_error(self) -> None:
        with pytest.raises(ValidationError):
            ClaudeCodeConfig(default_max_turns=0)

    def test_negative_max_turns_raises_error(self) -> None:
        with pytest.raises(ValidationError):
            ClaudeCodeConfig(default_max_turns=-5)

    def test_invalid_permission_mode_raises_error(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ClaudeCodeConfig(default_permission_mode="superAdmin")
        assert "default_permission_mode" in str(exc_info.value)

    def test_valid_permission_modes(self) -> None:
        for mode in ("default", "acceptEdits", "bypassPermissions"):
            cfg = ClaudeCodeConfig(default_permission_mode=mode)
            assert cfg.default_permission_mode == mode


class TestExecutionPlanFromDict:
    """Tests for ExecutionPlan.from_dict — workflow metadata deserialization."""

    def test_from_dict_preserves_workflow_step_id(self) -> None:
        data = {
            "steps": [
                {
                    "temp_id": "step_1",
                    "title": "Analyze",
                    "description": "Analyze requirements",
                    "assigned_agent": "nanobot",
                    "blocked_by": [],
                    "parallel_group": 1,
                    "order": 1,
                    "workflow_step_id": "analyze-step",
                    "workflow_step_type": "agent",
                    "agent_id": "agent-123",
                }
            ],
            "generated_at": "2026-03-14T10:00:00Z",
            "generated_by": "workflow",
        }
        plan = ExecutionPlan.from_dict(data)
        assert len(plan.steps) == 1
        step = plan.steps[0]
        assert step.workflow_step_id == "analyze-step"
        assert step.workflow_step_type == "agent"
        assert step.agent_id == "agent-123"

    def test_from_dict_preserves_review_spec_id_and_on_reject(self) -> None:
        data = {
            "steps": [
                {
                    "temp_id": "step_2",
                    "title": "Review",
                    "description": "Review output",
                    "assigned_agent": "nanobot",
                    "blocked_by": [],
                    "parallel_group": 1,
                    "order": 2,
                    "workflow_step_id": "review-step",
                    "workflow_step_type": "review",
                    "review_spec_id": "review-spec-456",
                    "on_reject_step_id": "step_1",
                }
            ],
            "generated_at": "2026-03-14T10:00:00Z",
            "generated_by": "workflow",
        }
        plan = ExecutionPlan.from_dict(data)
        step = plan.steps[0]
        assert step.workflow_step_type == "review"
        assert step.review_spec_id == "review-spec-456"
        assert step.on_reject_step_id == "step_1"

    def test_from_dict_workflow_metadata_none_when_absent(self) -> None:
        data = {
            "steps": [
                {
                    "temp_id": "step_1",
                    "title": "Plain step",
                    "description": "No workflow metadata",
                    "assigned_agent": "nanobot",
                    "blocked_by": [],
                    "parallel_group": 1,
                    "order": 1,
                }
            ],
            "generated_at": "2026-03-14T10:00:00Z",
            "generated_by": "lead-agent",
        }
        plan = ExecutionPlan.from_dict(data)
        step = plan.steps[0]
        assert step.workflow_step_id is None
        assert step.workflow_step_type is None
        assert step.agent_spec_id is None
        assert step.review_spec_id is None
        assert step.on_reject_step_id is None

    def test_from_dict_accepts_snake_case_workflow_keys(self) -> None:
        data = {
            "steps": [
                {
                    "temp_id": "step_1",
                    "title": "Analyze",
                    "description": "Analyze",
                    "assigned_agent": "nanobot",
                    "blocked_by": [],
                    "parallel_group": 1,
                    "order": 1,
                    "workflow_step_id": "analyze",
                    "workflow_step_type": "agent",
                    "agent_id": "agent-1",
                    "on_reject_step_id": "step_0",
                }
            ],
            "generatedAt": "2026-03-14T10:00:00Z",
            "generatedBy": "workflow",
        }
        plan = ExecutionPlan.from_dict(data)
        step = plan.steps[0]
        assert step.workflow_step_id == "analyze"
        assert step.workflow_step_type == "agent"
        assert step.agent_id == "agent-1"
        assert step.on_reject_step_id == "step_0"


class TestExecutionPlanRoundTrip:
    """Tests for ExecutionPlan.to_dict / from_dict round-trip fidelity."""

    def test_round_trip_workflow_metadata_preserved(self) -> None:
        """Workflow metadata fields survive to_dict → from_dict."""
        step = ExecutionPlanStep(
            temp_id="step-analyze",
            title="Analyze",
            description="Analyze requirements",
            assigned_agent="nanobot",
            blocked_by=[],
            parallel_group=1,
            order=0,
            workflow_step_id="analyze-step",
            workflow_step_type="agent",
            agent_id="agent-123",
            on_reject_step_id=None,
            review_spec_id=None,
        )
        plan = ExecutionPlan(steps=[step], generated_by="workflow")
        plan.generated_at = "2026-03-14T10:00:00Z"

        d = plan.to_dict()
        restored = ExecutionPlan.from_dict(d)

        assert len(restored.steps) == 1
        s = restored.steps[0]
        assert s.workflow_step_id == "analyze-step"
        assert s.workflow_step_type == "agent"
        assert s.agent_id == "agent-123"
        assert s.review_spec_id is None
        assert s.on_reject_step_id is None

    def test_round_trip_review_spec_and_on_reject(self) -> None:
        """review_spec_id and on_reject_step_id survive round-trip."""
        step = ExecutionPlanStep(
            temp_id="step-review",
            title="Review",
            description="Review output",
            assigned_agent="nanobot",
            blocked_by=["step-analyze"],
            parallel_group=2,
            order=1,
            workflow_step_id="review-step",
            workflow_step_type="review",
            agent_spec_id=None,
            review_spec_id="review-spec-456",
            on_reject_step_id="step-analyze",
        )
        plan = ExecutionPlan(steps=[step], generated_by="workflow")
        plan.generated_at = "2026-03-14T10:00:00Z"

        d = plan.to_dict()
        # Verify snake_case keys in dict (bridge converts to camelCase for Convex)
        assert d["steps"][0]["review_spec_id"] == "review-spec-456"
        assert d["steps"][0]["on_reject_step_id"] == "step-analyze"
        assert d["steps"][0]["workflow_step_id"] == "review-step"
        assert d["steps"][0]["workflow_step_type"] == "review"
        assert d["generated_by"] == "workflow"

        restored = ExecutionPlan.from_dict(d)
        s = restored.steps[0]
        assert s.review_spec_id == "review-spec-456"
        assert s.on_reject_step_id == "step-analyze"
        assert s.workflow_step_id == "review-step"
        assert s.workflow_step_type == "review"

    def test_round_trip_none_fields_omitted_from_dict(self) -> None:
        """None workflow metadata fields must NOT appear as keys in to_dict output."""
        step = ExecutionPlanStep(
            temp_id="plain-step",
            title="Plain",
            description="A plain step",
            assigned_agent="nanobot",
            blocked_by=[],
            parallel_group=1,
            order=0,
        )
        plan = ExecutionPlan(steps=[step])
        d = plan.to_dict()
        step_dict = d["steps"][0]
        assert "workflow_step_id" not in step_dict
        assert "workflow_step_type" not in step_dict
        assert "agent_id" not in step_dict
        assert "agent_spec_id" not in step_dict
        assert "review_spec_id" not in step_dict
        assert "on_reject_step_id" not in step_dict

    def test_round_trip_generated_by_workflow(self) -> None:
        """generated_by='workflow' is always preserved in to_dict."""
        plan = ExecutionPlan(steps=[], generated_by="workflow")
        d = plan.to_dict()
        assert d["generated_by"] == "workflow"

    def test_round_trip_generated_by_lead_agent(self) -> None:
        """generated_by='lead-agent' is always preserved in to_dict."""
        plan = ExecutionPlan(steps=[], generated_by="lead-agent")
        d = plan.to_dict()
        assert d["generated_by"] == "lead-agent"


class TestCCModelHelpers:
    """Tests for cc/ model prefix helpers."""

    def test_is_cc_model_with_cc_prefix(self) -> None:
        assert is_cc_model("cc/claude-sonnet-4-6") is True

    def test_is_cc_model_without_prefix(self) -> None:
        assert is_cc_model("anthropic/claude-sonnet-4-6") is False

    def test_is_cc_model_none(self) -> None:
        assert is_cc_model(None) is False

    def test_is_cc_model_empty(self) -> None:
        assert is_cc_model("") is False

    def test_extract_cc_model_name(self) -> None:
        assert extract_cc_model_name("cc/claude-sonnet-4-6") == "claude-sonnet-4-6"

    def test_extract_cc_model_name_opus(self) -> None:
        assert extract_cc_model_name("cc/claude-opus-4-6") == "claude-opus-4-6"

    def test_cc_available_models_all_have_prefix(self) -> None:
        for m in CC_AVAILABLE_MODELS:
            assert m.startswith("cc/"), f"{m} missing cc/ prefix"

    def test_cc_available_models_non_empty(self) -> None:
        assert len(CC_AVAILABLE_MODELS) >= 3
