"""Tests for the structured authoring assist module.

Covers:
- agent wizard responses return the next deep question plus a structured draft patch
- squad wizard responses can refine agents, workflows, and review policy together
- the contract returns readiness, summary sections, and recommended next phase
- phase progression logic
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from mc.contexts.agents.authoring_assist import (
    AuthoringPhase,
    AuthoringResponse,
    SpecDraftPatch,
    advance_agent_phase,
    advance_squad_phase,
    build_agent_question,
    build_squad_question,
    compute_readiness,
    generate_agent_assist_response,
    generate_squad_assist_response,
)

# ---------------------------------------------------------------------------
# AuthoringPhase enum
# ---------------------------------------------------------------------------


class TestAuthoringPhase:
    """Verify phase ordering."""

    def test_agent_phases_exist(self) -> None:
        assert AuthoringPhase.PURPOSE in AuthoringPhase
        assert AuthoringPhase.OPERATING_CONTEXT in AuthoringPhase
        assert AuthoringPhase.WORKING_STYLE in AuthoringPhase
        assert AuthoringPhase.EXECUTION_POLICY in AuthoringPhase
        assert AuthoringPhase.REVIEW_POLICY in AuthoringPhase
        assert AuthoringPhase.SUMMARY in AuthoringPhase

    def test_phases_are_ordered(self) -> None:
        phases = list(AuthoringPhase)
        assert phases.index(AuthoringPhase.PURPOSE) < phases.index(AuthoringPhase.OPERATING_CONTEXT)
        assert phases.index(AuthoringPhase.OPERATING_CONTEXT) < phases.index(
            AuthoringPhase.WORKING_STYLE
        )
        assert phases.index(AuthoringPhase.WORKING_STYLE) < phases.index(
            AuthoringPhase.EXECUTION_POLICY
        )
        assert phases.index(AuthoringPhase.EXECUTION_POLICY) < phases.index(
            AuthoringPhase.REVIEW_POLICY
        )
        assert phases.index(AuthoringPhase.REVIEW_POLICY) < phases.index(AuthoringPhase.SUMMARY)


# ---------------------------------------------------------------------------
# AuthoringResponse shape
# ---------------------------------------------------------------------------


class TestAuthoringResponse:
    """Verify the structured response contract."""

    def test_response_has_required_fields(self) -> None:
        resp = AuthoringResponse(
            question="What is the agent's main purpose?",
            draft_patch=SpecDraftPatch(fields={}),
            phase=AuthoringPhase.PURPOSE,
            readiness=0.0,
            summary_sections={},
            recommended_next_phase=AuthoringPhase.OPERATING_CONTEXT,
        )
        assert resp.question
        assert resp.phase == AuthoringPhase.PURPOSE
        assert 0.0 <= resp.readiness <= 1.0

    def test_response_serializes_to_dict(self) -> None:
        resp = AuthoringResponse(
            question="Describe the agent's operating context.",
            draft_patch=SpecDraftPatch(fields={"purpose": "Test purpose"}),
            phase=AuthoringPhase.OPERATING_CONTEXT,
            readiness=0.2,
            summary_sections={"purpose": "Test purpose"},
            recommended_next_phase=AuthoringPhase.WORKING_STYLE,
        )
        data = resp.to_dict()
        assert data["question"] == "Describe the agent's operating context."
        assert data["phase"] == "operating_context"
        assert data["readiness"] == 0.2
        assert "draft_patch" in data
        assert "summary_sections" in data
        assert data["recommended_next_phase"] == "working_style"

    def test_draft_patch_contains_fields(self) -> None:
        patch = SpecDraftPatch(
            fields={
                "purpose": "Analyze financial data",
                "responsibilities": ["Track payments", "Generate reports"],
            }
        )
        assert patch.fields["purpose"] == "Analyze financial data"
        assert len(patch.fields["responsibilities"]) == 2


# ---------------------------------------------------------------------------
# compute_readiness
# ---------------------------------------------------------------------------


class TestComputeReadiness:
    """Verify readiness scoring based on filled sections."""

    def test_empty_spec_has_zero_readiness(self) -> None:
        assert compute_readiness({}) == 0.0

    def test_full_spec_has_full_readiness(self) -> None:
        spec = {
            "purpose": "Test purpose",
            "operating_context": "Test context",
            "working_style": "Test style",
            "execution_policy": "Test policy",
            "review_policy": "Test review",
        }
        readiness = compute_readiness(spec)
        assert readiness == 1.0

    def test_partial_spec_has_proportional_readiness(self) -> None:
        spec = {
            "purpose": "Test purpose",
            "operating_context": "Test context",
        }
        readiness = compute_readiness(spec)
        assert 0.0 < readiness < 1.0

    def test_empty_string_fields_do_not_count(self) -> None:
        spec = {"purpose": "", "operating_context": ""}
        readiness = compute_readiness(spec)
        assert readiness == 0.0


# ---------------------------------------------------------------------------
# build_agent_question
# ---------------------------------------------------------------------------


class TestBuildAgentQuestion:
    """Verify question generation for each phase."""

    def test_purpose_phase_asks_about_purpose(self) -> None:
        question = build_agent_question(AuthoringPhase.PURPOSE, {})
        assert question
        assert len(question) > 0

    def test_operating_context_phase(self) -> None:
        question = build_agent_question(AuthoringPhase.OPERATING_CONTEXT, {"purpose": "Finance"})
        assert question

    def test_working_style_phase(self) -> None:
        question = build_agent_question(
            AuthoringPhase.WORKING_STYLE,
            {"purpose": "Finance", "operating_context": "Banking"},
        )
        assert question

    def test_execution_policy_phase(self) -> None:
        question = build_agent_question(AuthoringPhase.EXECUTION_POLICY, {})
        assert question

    def test_review_policy_phase(self) -> None:
        question = build_agent_question(AuthoringPhase.REVIEW_POLICY, {})
        assert question

    def test_summary_phase_returns_summary_prompt(self) -> None:
        spec = {
            "purpose": "Finance assistant",
            "operating_context": "Banking sector",
            "working_style": "Concise and accurate",
            "execution_policy": "Autonomous with review",
            "review_policy": "Peer review required",
        }
        question = build_agent_question(AuthoringPhase.SUMMARY, spec)
        assert question


# ---------------------------------------------------------------------------
# advance_agent_phase
# ---------------------------------------------------------------------------


class TestAdvanceAgentPhase:
    """Verify phase advancement logic."""

    def test_advances_from_purpose_to_operating_context(self) -> None:
        next_phase = advance_agent_phase(AuthoringPhase.PURPOSE, {"purpose": "Finance agent"})
        assert next_phase == AuthoringPhase.OPERATING_CONTEXT

    def test_advances_from_operating_context_to_working_style(self) -> None:
        next_phase = advance_agent_phase(
            AuthoringPhase.OPERATING_CONTEXT,
            {"purpose": "Finance", "operating_context": "Banking"},
        )
        assert next_phase == AuthoringPhase.WORKING_STYLE

    def test_stays_at_phase_when_current_empty(self) -> None:
        next_phase = advance_agent_phase(AuthoringPhase.PURPOSE, {})
        assert next_phase == AuthoringPhase.PURPOSE

    def test_advances_all_the_way_to_summary(self) -> None:
        spec = {
            "purpose": "Test",
            "operating_context": "Test",
            "working_style": "Test",
            "execution_policy": "Test",
            "review_policy": "Test",
        }
        phase = AuthoringPhase.REVIEW_POLICY
        next_phase = advance_agent_phase(phase, spec)
        assert next_phase == AuthoringPhase.SUMMARY


# ---------------------------------------------------------------------------
# generate_agent_assist_response (mocked LLM)
# ---------------------------------------------------------------------------


class TestGenerateAgentAssistResponse:
    """Tests for the full agent authoring assist flow with mocked LLM."""

    @pytest.mark.asyncio
    async def test_returns_authoring_response(self) -> None:
        mock_response = MagicMock()
        mock_response.content = "This agent will handle financial analysis and reporting."

        provider = MagicMock()
        provider.chat = AsyncMock(return_value=mock_response)

        messages = [{"role": "user", "content": "I want a finance agent"}]
        current_spec: dict[str, Any] = {}

        result = await generate_agent_assist_response(
            provider=provider,
            messages=messages,
            current_spec=current_spec,
            phase=AuthoringPhase.PURPOSE,
        )

        assert isinstance(result, AuthoringResponse)
        assert result.phase in AuthoringPhase
        assert 0.0 <= result.readiness <= 1.0
        assert result.question

    @pytest.mark.asyncio
    async def test_response_never_returns_raw_yaml(self) -> None:
        mock_response = MagicMock()
        mock_response.content = "name: finance-agent\nrole: Finance\nprompt: Test"

        provider = MagicMock()
        provider.chat = AsyncMock(return_value=mock_response)

        messages = [{"role": "user", "content": "I want a finance agent"}]
        result = await generate_agent_assist_response(
            provider=provider,
            messages=messages,
            current_spec={},
            phase=AuthoringPhase.PURPOSE,
        )

        # Response contract must not expose raw YAML as a top-level field
        data = result.to_dict()
        assert "yaml" not in data

    @pytest.mark.asyncio
    async def test_updates_draft_patch_from_user_input(self) -> None:
        mock_response = MagicMock()
        mock_response.content = (
            "This agent specializes in financial analysis, tracking payments and boletos."
        )

        provider = MagicMock()
        provider.chat = AsyncMock(return_value=mock_response)

        messages = [{"role": "user", "content": "Create a finance agent that tracks payments"}]
        result = await generate_agent_assist_response(
            provider=provider,
            messages=messages,
            current_spec={},
            phase=AuthoringPhase.PURPOSE,
        )

        # Draft patch should contain structured fields, not YAML
        assert isinstance(result.draft_patch.fields, dict)

    @pytest.mark.asyncio
    async def test_includes_summary_sections(self) -> None:
        mock_response = MagicMock()
        mock_response.content = "This is a useful response about the agent purpose."

        provider = MagicMock()
        provider.chat = AsyncMock(return_value=mock_response)

        current_spec = {"purpose": "Finance tracking"}
        result = await generate_agent_assist_response(
            provider=provider,
            messages=[{"role": "user", "content": "Tell me more"}],
            current_spec=current_spec,
            phase=AuthoringPhase.OPERATING_CONTEXT,
        )

        assert isinstance(result.summary_sections, dict)

    @pytest.mark.asyncio
    async def test_recommended_next_phase_is_valid(self) -> None:
        mock_response = MagicMock()
        mock_response.content = "Great purpose! Now let's explore the operating context."

        provider = MagicMock()
        provider.chat = AsyncMock(return_value=mock_response)

        result = await generate_agent_assist_response(
            provider=provider,
            messages=[{"role": "user", "content": "I want a research agent"}],
            current_spec={"purpose": "Research and analysis"},
            phase=AuthoringPhase.PURPOSE,
        )

        assert result.recommended_next_phase in AuthoringPhase


# ---------------------------------------------------------------------------
# build_squad_question
# ---------------------------------------------------------------------------


class TestBuildSquadQuestion:
    """Verify question generation for squad wizard."""

    def test_team_design_phase(self) -> None:
        question = build_squad_question("team_design", {})
        assert question
        assert len(question) > 0

    def test_workflow_design_phase(self) -> None:
        question = build_squad_question("workflow_design", {"team_design": "3 agents"})
        assert question

    def test_review_design_phase(self) -> None:
        question = build_squad_question("review_design", {})
        assert question

    def test_approval_phase(self) -> None:
        question = build_squad_question(
            "approval",
            {
                "team_design": "3 agents",
                "workflow_design": "Sequential",
                "review_design": "Peer review",
            },
        )
        assert question


# ---------------------------------------------------------------------------
# advance_squad_phase
# ---------------------------------------------------------------------------


class TestAdvanceSquadPhase:
    """Verify squad phase advancement."""

    def test_advances_from_team_design_to_workflow_design(self) -> None:
        next_phase = advance_squad_phase("team_design", {"team_design": "3 agents"})
        assert next_phase == "workflow_design"

    def test_stays_at_phase_when_current_empty(self) -> None:
        next_phase = advance_squad_phase("team_design", {})
        assert next_phase == "team_design"

    def test_advances_through_all_squad_phases(self) -> None:
        spec: dict[str, Any] = {}
        phase = "team_design"
        spec["team_design"] = "3 specialized agents"
        phase = advance_squad_phase(phase, spec)
        assert phase == "workflow_design"

        spec["workflow_design"] = "Sequential pipeline"
        phase = advance_squad_phase(phase, spec)
        assert phase == "review_design"

        spec["review_design"] = "Peer review with rubric"
        phase = advance_squad_phase(phase, spec)
        assert phase == "approval"


# ---------------------------------------------------------------------------
# generate_squad_assist_response (mocked LLM)
# ---------------------------------------------------------------------------


class TestGenerateSquadAssistResponse:
    """Tests for the squad authoring assist with mocked LLM."""

    @pytest.mark.asyncio
    async def test_returns_structured_response(self) -> None:
        mock_response = MagicMock()
        mock_response.content = "Your squad needs a lead, a researcher, and a writer."

        provider = MagicMock()
        provider.chat = AsyncMock(return_value=mock_response)

        result = await generate_squad_assist_response(
            provider=provider,
            messages=[{"role": "user", "content": "I need a research squad"}],
            current_spec={},
            phase="team_design",
        )

        assert isinstance(result, dict)
        assert "question" in result
        assert "draft_patch" in result
        assert "readiness" in result
        assert "summary_sections" in result
        assert "recommended_next_phase" in result

    @pytest.mark.asyncio
    async def test_never_returns_raw_yaml(self) -> None:
        mock_response = MagicMock()
        mock_response.content = "name: research-squad\nagents: [researcher, writer]"

        provider = MagicMock()
        provider.chat = AsyncMock(return_value=mock_response)

        result = await generate_squad_assist_response(
            provider=provider,
            messages=[{"role": "user", "content": "Research squad"}],
            current_spec={},
            phase="team_design",
        )

        assert "yaml" not in result

    @pytest.mark.asyncio
    async def test_can_refine_agents_workflows_and_review(self) -> None:
        mock_response = MagicMock()
        mock_response.content = "The workflow should have 3 steps: research, draft, and review."

        provider = MagicMock()
        provider.chat = AsyncMock(return_value=mock_response)

        current_spec = {
            "team_design": "Lead, researcher, writer",
            "workflow_design": "Draft workflow",
        }
        result = await generate_squad_assist_response(
            provider=provider,
            messages=[{"role": "user", "content": "Refine the workflow"}],
            current_spec=current_spec,
            phase="workflow_design",
        )

        assert "recommended_next_phase" in result
        assert "summary_sections" in result
