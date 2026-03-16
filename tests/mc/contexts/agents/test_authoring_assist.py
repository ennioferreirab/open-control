"""Tests for the shared authoring engine and draft-graph contract.

Canonical phases: discovery, proposal, refinement, approval.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mc.contexts.agents.authoring_assist import (
    CANONICAL_PHASES,
    AuthoringMode,
    AuthoringResponse,
    build_agent_authoring_response,
)


class TestCanonicalPhases:
    """Canonical phase set is exactly the four defined phases."""

    def test_canonical_phases_set(self) -> None:
        assert CANONICAL_PHASES == {"discovery", "proposal", "refinement", "approval"}

    def test_canonical_phases_is_frozenset(self) -> None:
        assert isinstance(CANONICAL_PHASES, frozenset)


class TestAuthoringMode:
    """AuthoringMode enum covers the remaining agent mode."""

    def test_agent_mode(self) -> None:
        assert AuthoringMode.AGENT == "agent"

class TestAuthoringResponseModel:
    """AuthoringResponse dataclass contract."""

    def test_agent_response_fields(self) -> None:
        resp = AuthoringResponse(
            assistant_message="Here is your agent proposal.",
            phase="proposal",
            draft_graph_patch={"agents": [{"key": "researcher", "role": "Researcher"}]},
            unresolved_questions=["What data sources should the agent use?"],
            preview={"agents_count": 1},
            readiness=0.4,
            mode=AuthoringMode.AGENT,
        )
        assert resp.assistant_message == "Here is your agent proposal."
        assert resp.phase == "proposal"
        assert resp.draft_graph_patch == {"agents": [{"key": "researcher", "role": "Researcher"}]}
        assert resp.unresolved_questions == ["What data sources should the agent use?"]
        assert resp.preview == {"agents_count": 1}
        assert resp.readiness == 0.4
        assert resp.mode == AuthoringMode.AGENT

    def test_invalid_phase_raises(self) -> None:
        with pytest.raises(ValueError, match="phase"):
            AuthoringResponse(
                assistant_message="msg",
                phase="ideation",  # not a canonical phase
                draft_graph_patch={},
                unresolved_questions=[],
                preview={},
                readiness=0.0,
                mode=AuthoringMode.AGENT,
            )

    def test_all_canonical_phases_are_valid(self) -> None:
        for phase in CANONICAL_PHASES:
            resp = AuthoringResponse(
                assistant_message="msg",
                phase=phase,
                draft_graph_patch={},
                unresolved_questions=[],
                preview={},
                readiness=0.0,
                mode=AuthoringMode.AGENT,
            )
            assert resp.phase == phase

    def test_to_dict_has_canonical_keys(self) -> None:
        resp = AuthoringResponse(
            assistant_message="Hello",
            phase="discovery",
            draft_graph_patch={"agents": []},
            unresolved_questions=["Q1"],
            preview={},
            readiness=0.1,
            mode=AuthoringMode.AGENT,
        )
        d = resp.to_dict()
        assert "assistant_message" in d
        assert "phase" in d
        assert "draft_graph_patch" in d
        assert "unresolved_questions" in d
        assert "preview" in d
        assert "readiness" in d
        assert "mode" in d


class TestBuildAgentAuthoringResponse:
    """build_agent_authoring_response constructs a valid AuthoringResponse."""

    @pytest.mark.asyncio
    async def test_returns_authoring_response(self) -> None:
        mock_response = MagicMock()
        mock_response.content = (
            '{"assistant_message": "I propose a researcher agent.", '
            '"phase": "proposal", '
            '"draft_graph_patch": {"agents": [{"key": "researcher", "role": "Researcher"}]}, '
            '"unresolved_questions": [], '
            '"preview": {}, '
            '"readiness": 0.5}'
        )
        provider = MagicMock()
        provider.chat = AsyncMock(return_value=mock_response)

        result = await build_agent_authoring_response(
            provider=provider,
            messages=[{"role": "user", "content": "Create a researcher agent"}],
            current_phase="proposal",
        )

        assert isinstance(result, AuthoringResponse)
        assert result.phase in CANONICAL_PHASES
        assert result.mode == AuthoringMode.AGENT

    @pytest.mark.asyncio
    async def test_uses_canonical_phase_from_payload(self) -> None:
        mock_response = MagicMock()
        mock_response.content = (
            '{"assistant_message": "Starting discovery.", '
            '"phase": "discovery", '
            '"draft_graph_patch": {}, '
            '"unresolved_questions": ["What does this agent do?"], '
            '"preview": {}, '
            '"readiness": 0.0}'
        )
        provider = MagicMock()
        provider.chat = AsyncMock(return_value=mock_response)

        result = await build_agent_authoring_response(
            provider=provider,
            messages=[{"role": "user", "content": "I want an agent"}],
            current_phase="discovery",
        )

        assert result.phase == "discovery"
        assert result.unresolved_questions == ["What does this agent do?"]

    @pytest.mark.asyncio
    async def test_fallback_on_invalid_llm_response(self) -> None:
        mock_response = MagicMock()
        mock_response.content = "Not valid JSON at all"
        provider = MagicMock()
        provider.chat = AsyncMock(return_value=mock_response)

        result = await build_agent_authoring_response(
            provider=provider,
            messages=[{"role": "user", "content": "Create an agent"}],
            current_phase="discovery",
        )

        assert isinstance(result, AuthoringResponse)
        assert result.phase in CANONICAL_PHASES
        assert result.mode == AuthoringMode.AGENT
