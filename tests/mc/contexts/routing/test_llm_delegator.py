"""Tests for LLMDelegationRouter — all paths and error cases."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.contexts.routing.llm_delegator import LLMDelegationRouter
from mc.contexts.routing.router import RoutingDecision


def make_bridge(agents: list[dict] | None = None) -> MagicMock:
    bridge = MagicMock()
    bridge.list_active_registry_view.return_value = agents or []
    bridge.get_board_by_id.return_value = None
    bridge.get_agent_by_name.return_value = None
    return bridge


def make_agent(
    name: str,
    role: str = "agent",
    tasks_executed: int = 0,
    status: str = "idle",
    skills: list[str] | None = None,
) -> dict:
    return {
        "name": name,
        "role": role,
        "tasksExecuted": tasks_executed,
        "status": status,
        "skills": skills or [],
        "enabled": True,
    }


def make_llm_response(target_agent: str, reasoning: str = "best fit", confidence: str = "high"):
    """Create a mock LLM response with valid JSON."""
    import json

    content = json.dumps(
        {
            "target_agent": target_agent,
            "reasoning": reasoning,
            "confidence": confidence,
        }
    )
    resp = MagicMock()
    resp.content = content
    resp.finish_reason = "stop"
    return resp


class TestPathAExplicitAssignment:
    """Path A: User selected an agent → direct assignment."""

    @pytest.mark.asyncio
    async def test_explicit_agent_routes_directly(self) -> None:
        agents = [make_agent("agent-a"), make_agent("agent-b")]
        bridge = make_bridge(agents)
        router = LLMDelegationRouter(bridge)

        decision = await router.route({"assigned_agent": "agent-b"})

        assert decision.target_agent == "agent-b"
        assert decision.reason_code == "explicit_assignment"

    @pytest.mark.asyncio
    async def test_explicit_agent_snake_case(self) -> None:
        agents = [make_agent("agent-a")]
        bridge = make_bridge(agents)
        router = LLMDelegationRouter(bridge)

        decision = await router.route({"assigned_agent": "agent-a"})

        assert decision.target_agent == "agent-a"
        assert decision.reason_code == "explicit_assignment"

    @pytest.mark.asyncio
    async def test_explicit_agent_not_in_registry_raises(self) -> None:
        # Empty registry so DirectDelegationRouter returns None
        bridge = make_bridge([])
        router = LLMDelegationRouter(bridge)

        with pytest.raises(RuntimeError, match="not found in active registry"):
            await router.route({"assigned_agent": "nonexistent"})


class TestPathBLLMDelegation:
    """Path B: No agent → LLM picks the best one."""

    @pytest.mark.asyncio
    async def test_llm_picks_best_agent(self) -> None:
        agents = [make_agent("agent-a"), make_agent("agent-b", skills=["research"])]
        bridge = make_bridge(agents)
        router = LLMDelegationRouter(bridge)

        response = make_llm_response("agent-b", "research skills match", "high")
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=response)

        with (
            patch(
                "mc.contexts.routing.llm_delegator.create_provider",
                return_value=(mock_provider, "test-model"),
            ),
            patch.object(router, "_resolve_model", new=AsyncMock(return_value=None)),
        ):
            decision = await router.route({"title": "Research task", "description": "Do research"})

        assert decision.target_agent == "agent-b"
        assert decision.reason_code == "llm_delegation"
        assert "research" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_llm_timeout_raises(self) -> None:
        import asyncio

        agents = [make_agent("agent-a")]
        bridge = make_bridge(agents)
        router = LLMDelegationRouter(bridge)

        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(side_effect=asyncio.TimeoutError())

        with (
            patch(
                "mc.contexts.routing.llm_delegator.create_provider",
                return_value=(mock_provider, "test-model"),
            ),
            patch.object(router, "_resolve_model", new=AsyncMock(return_value=None)),
            patch("mc.contexts.routing.llm_delegator.LLM_TIMEOUT_SECONDS", 0.01),
        ):
            with pytest.raises(RuntimeError, match="timed out"):
                await router.route({"title": "Test"})

    @pytest.mark.asyncio
    async def test_llm_error_response_raises(self) -> None:
        agents = [make_agent("agent-a")]
        bridge = make_bridge(agents)
        router = LLMDelegationRouter(bridge)

        resp = MagicMock()
        resp.content = "some error"
        resp.finish_reason = "error"
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=resp)

        with (
            patch(
                "mc.contexts.routing.llm_delegator.create_provider",
                return_value=(mock_provider, "test-model"),
            ),
            patch.object(router, "_resolve_model", new=AsyncMock(return_value=None)),
        ):
            with pytest.raises(RuntimeError, match="returned error"):
                await router.route({"title": "Test"})

    @pytest.mark.asyncio
    async def test_llm_empty_response_raises(self) -> None:
        agents = [make_agent("agent-a")]
        bridge = make_bridge(agents)
        router = LLMDelegationRouter(bridge)

        resp = MagicMock()
        resp.content = ""
        resp.finish_reason = "stop"
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=resp)

        with (
            patch(
                "mc.contexts.routing.llm_delegator.create_provider",
                return_value=(mock_provider, "test-model"),
            ),
            patch.object(router, "_resolve_model", new=AsyncMock(return_value=None)),
        ):
            with pytest.raises(RuntimeError, match="empty response"):
                await router.route({"title": "Test"})

    @pytest.mark.asyncio
    async def test_llm_invalid_json_raises(self) -> None:
        agents = [make_agent("agent-a")]
        bridge = make_bridge(agents)
        router = LLMDelegationRouter(bridge)

        resp = MagicMock()
        resp.content = "not json at all"
        resp.finish_reason = "stop"
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=resp)

        with (
            patch(
                "mc.contexts.routing.llm_delegator.create_provider",
                return_value=(mock_provider, "test-model"),
            ),
            patch.object(router, "_resolve_model", new=AsyncMock(return_value=None)),
        ):
            with pytest.raises(RuntimeError, match="invalid JSON"):
                await router.route({"title": "Test"})

    @pytest.mark.asyncio
    async def test_llm_missing_target_agent_raises(self) -> None:
        agents = [make_agent("agent-a")]
        bridge = make_bridge(agents)
        router = LLMDelegationRouter(bridge)

        import json

        resp = MagicMock()
        resp.content = json.dumps({"reasoning": "no agent key"})
        resp.finish_reason = "stop"
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=resp)

        with (
            patch(
                "mc.contexts.routing.llm_delegator.create_provider",
                return_value=(mock_provider, "test-model"),
            ),
            patch.object(router, "_resolve_model", new=AsyncMock(return_value=None)),
        ):
            with pytest.raises(RuntimeError, match="missing 'target_agent'"):
                await router.route({"title": "Test"})

    @pytest.mark.asyncio
    async def test_llm_selects_nonexistent_agent_raises(self) -> None:
        agents = [make_agent("agent-a")]
        bridge = make_bridge(agents)
        router = LLMDelegationRouter(bridge)

        response = make_llm_response("agent-z")
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=response)

        with (
            patch(
                "mc.contexts.routing.llm_delegator.create_provider",
                return_value=(mock_provider, "test-model"),
            ),
            patch.object(router, "_resolve_model", new=AsyncMock(return_value=None)),
        ):
            with pytest.raises(RuntimeError, match="not found in active registry"):
                await router.route({"title": "Test"})

    @pytest.mark.asyncio
    async def test_provider_creation_failure_raises(self) -> None:
        agents = [make_agent("agent-a")]
        bridge = make_bridge(agents)
        router = LLMDelegationRouter(bridge)

        with (
            patch(
                "mc.contexts.routing.llm_delegator.create_provider",
                side_effect=Exception("No API key"),
            ),
            patch.object(router, "_resolve_model", new=AsyncMock(return_value=None)),
        ):
            with pytest.raises(RuntimeError, match="Failed to create LLM provider"):
                await router.route({"title": "Test"})


class TestEmptyRegistry:
    """Edge cases with empty or filtered-out registries."""

    @pytest.mark.asyncio
    async def test_empty_registry_raises(self) -> None:
        bridge = make_bridge([])
        router = LLMDelegationRouter(bridge)

        with pytest.raises(RuntimeError, match="No active agents"):
            await router.route({"title": "Test"})

    @pytest.mark.asyncio
    async def test_board_filters_out_all_agents_raises(self) -> None:
        agents = [make_agent("agent-a")]
        bridge = make_bridge(agents)
        bridge.get_board_by_id.return_value = {"enabled_agents": ["agent-z"]}
        router = LLMDelegationRouter(bridge)

        with pytest.raises(RuntimeError, match="No delegatable agents after board filtering"):
            await router.route({"title": "Test", "board_id": "board-1"})

    @pytest.mark.asyncio
    async def test_all_agents_crashed_raises(self) -> None:
        agents = [make_agent("agent-a", status="crashed")]
        bridge = make_bridge(agents)
        router = LLMDelegationRouter(bridge)

        with pytest.raises(RuntimeError, match="crashed state"):
            await router.route({"title": "Test"})


class TestBoardScoping:
    """Board-scoped agent filtering."""

    @pytest.mark.asyncio
    async def test_board_scoping_filters_candidates(self) -> None:
        agents = [
            make_agent("agent-a", skills=["web"]),
            make_agent("agent-b", skills=["research"]),
        ]
        bridge = make_bridge(agents)
        bridge.get_board_by_id.return_value = {"enabled_agents": ["agent-b"]}
        router = LLMDelegationRouter(bridge)

        response = make_llm_response("agent-b")
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=response)

        with (
            patch(
                "mc.contexts.routing.llm_delegator.create_provider",
                return_value=(mock_provider, "test-model"),
            ),
            patch.object(router, "_resolve_model", new=AsyncMock(return_value=None)),
        ):
            decision = await router.route({"title": "Test", "board_id": "board-1"})

        assert decision.target_agent == "agent-b"

    @pytest.mark.asyncio
    async def test_board_fetch_failure_continues_with_all(self) -> None:
        agents = [make_agent("agent-a")]
        bridge = make_bridge(agents)
        bridge.get_board_by_id.side_effect = Exception("Network error")
        router = LLMDelegationRouter(bridge)

        response = make_llm_response("agent-a")
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=response)

        with (
            patch(
                "mc.contexts.routing.llm_delegator.create_provider",
                return_value=(mock_provider, "test-model"),
            ),
            patch.object(router, "_resolve_model", new=AsyncMock(return_value=None)),
        ):
            decision = await router.route({"title": "Test", "board_id": "board-err"})

        assert decision.target_agent == "agent-a"


class TestLLMResponseParsing:
    """Edge cases in LLM response parsing."""

    @pytest.mark.asyncio
    async def test_markdown_fenced_json_parsed(self) -> None:
        agents = [make_agent("agent-a")]
        bridge = make_bridge(agents)
        router = LLMDelegationRouter(bridge)

        resp = MagicMock()
        resp.content = (
            '```json\n{"target_agent": "agent-a", "reasoning": "ok", "confidence": "high"}\n```'
        )
        resp.finish_reason = "stop"
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=resp)

        with (
            patch(
                "mc.contexts.routing.llm_delegator.create_provider",
                return_value=(mock_provider, "test-model"),
            ),
            patch.object(router, "_resolve_model", new=AsyncMock(return_value=None)),
        ):
            decision = await router.route({"title": "Test"})

        assert decision.target_agent == "agent-a"

    @pytest.mark.asyncio
    async def test_description_truncated(self) -> None:
        agents = [make_agent("agent-a")]
        bridge = make_bridge(agents)
        router = LLMDelegationRouter(bridge)

        response = make_llm_response("agent-a")
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=response)

        long_desc = "x" * 5000
        with (
            patch(
                "mc.contexts.routing.llm_delegator.create_provider",
                return_value=(mock_provider, "test-model"),
            ),
            patch.object(router, "_resolve_model", new=AsyncMock(return_value=None)),
        ):
            decision = await router.route({"title": "Test", "description": long_desc})

        # Should succeed — description truncated internally
        assert decision.target_agent == "agent-a"


class TestFormatAgentRoster:
    """Unit tests for static roster formatting."""

    def test_formats_agents_correctly(self) -> None:
        agents = [
            make_agent("web-agent", role="web", skills=["search", "scrape"], tasks_executed=3),
            make_agent("dev-agent", role="developer", skills=["code"], tasks_executed=1),
        ]

        result = LLMDelegationRouter._format_agent_roster(agents)

        assert "web-agent" in result
        assert "search, scrape" in result
        assert "tasks_executed: 3" in result
        assert "dev-agent" in result
        assert "code" in result

    def test_empty_skills_shows_general(self) -> None:
        agents = [make_agent("agent-a")]
        result = LLMDelegationRouter._format_agent_roster(agents)
        assert "general" in result
