"""Tests for ensure_low_agent in gateway."""
from unittest.mock import MagicMock
from mc.gateway import ensure_low_agent
from mc.types import LOW_AGENT_NAME, AgentData


def _make_bridge():
    bridge = MagicMock()
    bridge.sync_agent.return_value = None
    return bridge


def test_ensure_low_agent_upserts_system_agent():
    bridge = _make_bridge()
    ensure_low_agent(bridge)
    bridge.sync_agent.assert_called_once()
    agent: AgentData = bridge.sync_agent.call_args[0][0]
    assert agent.name == LOW_AGENT_NAME
    assert agent.is_system is True
    assert agent.model == "tier:standard-low"


def test_ensure_low_agent_is_idempotent():
    bridge = _make_bridge()
    ensure_low_agent(bridge)
    ensure_low_agent(bridge)
    assert bridge.sync_agent.call_count == 2  # upsert is idempotent, called each time
