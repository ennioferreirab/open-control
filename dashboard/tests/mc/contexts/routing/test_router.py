"""Tests for the DirectDelegationRouter."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mc.contexts.routing.router import DirectDelegationRouter, RoutingDecision


def make_bridge(agents: list[dict]) -> MagicMock:
    """Create a mock bridge that returns the provided agents from list_active_registry_view."""
    bridge = MagicMock()
    bridge.list_active_registry_view.return_value = agents
    bridge.get_board_by_id.return_value = None
    return bridge


def make_agent(name: str, role: str = "agent", tasks_executed: int = 0) -> dict:
    return {"name": name, "role": role, "tasksExecuted": tasks_executed, "enabled": True}


class TestDirectDelegationRouter:
    def test_picks_least_loaded_agent(self) -> None:
        agents = [
            make_agent("agent-a", tasks_executed=5),
            make_agent("agent-b", tasks_executed=2),
            make_agent("agent-c", tasks_executed=8),
        ]
        bridge = make_bridge(agents)
        router = DirectDelegationRouter(bridge)
        decision = router.route({"title": "test task"})

        assert decision is not None
        assert decision.target_agent == "agent-b"
        assert decision.reason_code == "least_loaded"

    def test_returns_none_when_registry_is_empty(self) -> None:
        bridge = make_bridge([])
        router = DirectDelegationRouter(bridge)
        decision = router.route({"title": "test task"})

        assert decision is None

    def test_explicit_assigned_agent_takes_priority(self) -> None:
        agents = [
            make_agent("agent-a", tasks_executed=0),
            make_agent("agent-b", tasks_executed=10),
        ]
        bridge = make_bridge(agents)
        router = DirectDelegationRouter(bridge)
        decision = router.route({"assignedAgent": "agent-b"})

        assert decision is not None
        assert decision.target_agent == "agent-b"
        assert decision.reason_code == "explicit_assignment"

    def test_explicit_assigned_agent_snake_case(self) -> None:
        agents = [
            make_agent("agent-a", tasks_executed=0),
            make_agent("agent-b", tasks_executed=10),
        ]
        bridge = make_bridge(agents)
        router = DirectDelegationRouter(bridge)
        decision = router.route({"assigned_agent": "agent-b"})

        assert decision is not None
        assert decision.target_agent == "agent-b"
        assert decision.reason_code == "explicit_assignment"

    def test_board_filtering(self) -> None:
        agents = [
            make_agent("agent-a", tasks_executed=0),
            make_agent("agent-b", tasks_executed=2),
        ]
        bridge = make_bridge(agents)
        bridge.get_board_by_id.return_value = {"enabledAgents": ["agent-b"]}
        router = DirectDelegationRouter(bridge)
        decision = router.route({"boardId": "board-123"})

        assert decision is not None
        assert decision.target_agent == "agent-b"

    def test_board_filtering_returns_none_when_no_candidates(self) -> None:
        agents = [
            make_agent("agent-a", tasks_executed=0),
        ]
        bridge = make_bridge(agents)
        # Board only allows agents not in the registry
        bridge.get_board_by_id.return_value = {"enabledAgents": ["agent-z"]}
        router = DirectDelegationRouter(bridge)
        decision = router.route({"boardId": "board-456"})

        assert decision is None

    def test_routing_decision_includes_registry_snapshot(self) -> None:
        agents = [
            make_agent("agent-a"),
            make_agent("agent-b"),
        ]
        bridge = make_bridge(agents)
        router = DirectDelegationRouter(bridge)
        decision = router.route({})

        assert decision is not None
        assert len(decision.registry_snapshot) == 2
        snapshot_names = {s["name"] for s in decision.registry_snapshot}
        assert snapshot_names == {"agent-a", "agent-b"}

    def test_routing_decision_has_routed_at_timestamp(self) -> None:
        agents = [make_agent("agent-x")]
        bridge = make_bridge(agents)
        router = DirectDelegationRouter(bridge)
        decision = router.route({})

        assert decision is not None
        assert decision.routed_at != ""
        # ISO format check
        assert "T" in decision.routed_at

    def test_board_filtering_with_enabled_agents_field(self) -> None:
        agents = [
            make_agent("agent-a", tasks_executed=3),
            make_agent("agent-b", tasks_executed=1),
        ]
        bridge = make_bridge(agents)
        bridge.get_board_by_id.return_value = {"enabled_agents": ["agent-a"]}
        router = DirectDelegationRouter(bridge)
        decision = router.route({"board_id": "board-789"})

        assert decision is not None
        assert decision.target_agent == "agent-a"

    def test_board_fetch_failure_falls_through_to_all_candidates(self) -> None:
        agents = [
            make_agent("agent-a", tasks_executed=5),
            make_agent("agent-b", tasks_executed=1),
        ]
        bridge = make_bridge(agents)
        bridge.get_board_by_id.side_effect = Exception("Network error")
        router = DirectDelegationRouter(bridge)
        decision = router.route({"boardId": "board-err"})

        # Should fall through to all candidates and pick least-loaded
        assert decision is not None
        assert decision.target_agent == "agent-b"
