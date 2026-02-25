"""Unit tests for the Agent Registry Sync and Auto-Retry (gateway module)."""

from __future__ import annotations

import asyncio
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

from unittest.mock import patch as _patch

from nanobot.mc.gateway import AgentGateway, MAX_AUTO_RETRIES, sync_agent_registry
from nanobot.mc.types import AgentData

# All tests mock _config_default_model so they don't depend on ~/.nanobot/config.json
_CONFIG_DEFAULT = "anthropic-oauth/claude-sonnet-4-6"


@pytest.fixture(autouse=True)
def _mock_config_default_model():
    """Mock _config_default_model for all tests so they don't need ~/.nanobot/config.json."""
    with _patch("nanobot.mc.gateway._config_default_model", return_value=_CONFIG_DEFAULT):
        yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_yaml(tmp_path: Path, agent_name: str, content: str) -> Path:
    """Write an agent config.yaml inside agent_name/ subdirectory.

    sync_agent_registry expects: agents_dir/<agent_name>/config.yaml
    """
    agent_dir = tmp_path / agent_name
    agent_dir.mkdir(exist_ok=True)
    p = agent_dir / "config.yaml"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


def _make_bridge() -> MagicMock:
    """Create a mock ConvexBridge with the agent-related methods."""
    bridge = MagicMock()
    bridge.sync_agent.return_value = None
    bridge.deactivate_agents_except.return_value = None
    bridge.list_agents.return_value = []
    return bridge


# ---------------------------------------------------------------------------
# Test: Sync valid agents
# ---------------------------------------------------------------------------

class TestSyncValidAgents:
    """Tests for syncing valid agent YAML files.

    NOTE: sync_agent_registry() always auto-creates general-agent (Story 1.3),
    so all counts include it and "general-agent" always appears in active_names.
    """

    def test_all_valid_agents_synced(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path, "dev-agent", """\
            name: dev-agent
            role: Senior Developer
            prompt: "You are a senior developer."
            skills:
              - coding
              - debugging
            model: claude-sonnet-4-6
        """)
        _write_yaml(tmp_path, "test-agent", """\
            name: test-agent
            role: Tester
            prompt: "You test code."
            skills:
              - testing
        """)

        bridge = _make_bridge()
        agents, errors = sync_agent_registry(bridge, tmp_path)

        # general-agent is always auto-created, so 3 agents total
        assert len(agents) == 3
        assert errors == {}
        # dev-agent, test-agent, and general-agent
        assert bridge.sync_agent.call_count == 3
        bridge.deactivate_agents_except.assert_called_once()

        # Check agent names passed to deactivate — general-agent always included
        deactivate_call_args = bridge.deactivate_agents_except.call_args[0][0]
        assert set(deactivate_call_args) == {"dev-agent", "test-agent", "general-agent"}

    def test_single_agent_synced(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path, "solo-agent", """\
            name: solo-agent
            role: Helper
            prompt: "You help."
        """)

        bridge = _make_bridge()
        agents, errors = sync_agent_registry(bridge, tmp_path)

        # general-agent is always auto-created alongside solo-agent
        assert len(agents) == 2
        agent_names = {a.name for a in agents}
        assert "solo-agent" in agent_names
        assert "general-agent" in agent_names
        assert errors == {}
        # solo-agent + general-agent
        assert bridge.sync_agent.call_count == 2


# ---------------------------------------------------------------------------
# Test: Mixed valid and invalid agents
# ---------------------------------------------------------------------------

class TestMixedValidInvalid:
    """Tests that valid agents sync even when some are invalid."""

    def test_valid_synced_invalid_logged(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path, "good-agent", """\
            name: good-agent
            role: Worker
            prompt: "You work."
        """)
        _write_yaml(tmp_path, "bad-agent", """\
            name: "Invalid Name!"
            role: Breaker
            prompt: "Oops."
        """)

        bridge = _make_bridge()
        agents, errors = sync_agent_registry(bridge, tmp_path)

        # good-agent + general-agent (auto-created); bad-agent fails validation
        assert len(agents) == 2
        agent_names = {a.name for a in agents}
        assert "good-agent" in agent_names
        assert "general-agent" in agent_names
        assert "bad-agent" in errors
        # good-agent + general-agent synced
        assert bridge.sync_agent.call_count == 2

    def test_all_invalid_no_sync(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path, "bad1", """\
            role: Breaker
            prompt: "Missing name."
        """)
        _write_yaml(tmp_path, "bad2", """\
            name: "INVALID"
            role: Breaker
            prompt: "Bad name."
        """)

        bridge = _make_bridge()
        agents, errors = sync_agent_registry(bridge, tmp_path)

        # general-agent is always auto-created even when all user agents are invalid
        assert len(agents) == 1
        assert agents[0].name == "general-agent"
        assert len(errors) == 2
        # general-agent still synced
        bridge.sync_agent.assert_called_once()
        # deactivate_agents_except called with just general-agent
        bridge.deactivate_agents_except.assert_called_once_with(["general-agent"])


# ---------------------------------------------------------------------------
# Test: Model resolution
# ---------------------------------------------------------------------------

class TestModelResolution:
    """Tests for default model resolution chain."""

    def test_agent_with_model_keeps_it(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path, "custom-model", """\
            name: custom-model
            role: Developer
            prompt: "You code."
            model: gpt-4o
        """)

        bridge = _make_bridge()
        agents, _ = sync_agent_registry(bridge, tmp_path, default_model="claude-opus-4-6")

        assert agents[0].model == "gpt-4o"

    def test_agent_without_model_gets_provided_default(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path, "no-model", """\
            name: no-model
            role: Developer
            prompt: "You code."
        """)

        bridge = _make_bridge()
        agents, _ = sync_agent_registry(bridge, tmp_path, default_model="claude-opus-4-6")

        assert agents[0].model == "claude-opus-4-6"

    def test_agent_without_model_gets_config_default(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path, "no-model", """\
            name: no-model
            role: Developer
            prompt: "You code."
        """)

        bridge = _make_bridge()
        agents, _ = sync_agent_registry(bridge, tmp_path)

        assert agents[0].model == _CONFIG_DEFAULT

    def test_default_model_not_override_explicit_model(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path, "agent-a", """\
            name: agent-a
            role: Developer
            prompt: "Has model."
            model: my-model
        """)
        _write_yaml(tmp_path, "agent-b", """\
            name: agent-b
            role: Tester
            prompt: "No model."
        """)

        bridge = _make_bridge()
        agents, _ = sync_agent_registry(bridge, tmp_path, default_model="default-llm")

        agent_a = next(a for a in agents if a.name == "agent-a")
        agent_b = next(a for a in agents if a.name == "agent-b")

        assert agent_a.model == "my-model"
        assert agent_b.model == "default-llm"


# ---------------------------------------------------------------------------
# Test: Deactivation of removed agents
# ---------------------------------------------------------------------------

class TestDeactivation:
    """Tests for soft deactivation of removed agents."""

    def test_deactivate_called_with_active_names(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path, "agent-a", """\
            name: agent-a
            role: Worker
            prompt: "Work."
        """)
        _write_yaml(tmp_path, "agent-b", """\
            name: agent-b
            role: Builder
            prompt: "Build."
        """)

        bridge = _make_bridge()
        sync_agent_registry(bridge, tmp_path)

        bridge.deactivate_agents_except.assert_called_once()
        active_names = bridge.deactivate_agents_except.call_args[0][0]
        # general-agent is always auto-created and included in active names
        assert set(active_names) == {"agent-a", "agent-b", "general-agent"}

    def test_empty_dir_deactivates_all(self, tmp_path: Path) -> None:
        bridge = _make_bridge()
        agents, errors = sync_agent_registry(bridge, tmp_path)

        # general-agent is always auto-created, so 1 agent even in empty dir
        assert len(agents) == 1
        assert agents[0].name == "general-agent"
        assert errors == {}
        # deactivate_agents_except called with just general-agent
        bridge.deactivate_agents_except.assert_called_once_with(["general-agent"])


# ---------------------------------------------------------------------------
# Test: Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge case tests."""

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        # When agents_dir doesn't exist, ensure_general_agent() creates it
        # along with the general-agent subdirectory.
        missing = tmp_path / "nonexistent"
        bridge = _make_bridge()
        agents, errors = sync_agent_registry(bridge, missing)

        # general-agent is always created even when agents_dir was absent
        assert len(agents) == 1
        assert agents[0].name == "general-agent"
        assert errors == {}

    def test_sync_agent_failure_does_not_block_others(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path, "agent-a", """\
            name: agent-a
            role: Worker
            prompt: "Work."
        """)
        _write_yaml(tmp_path, "agent-b", """\
            name: agent-b
            role: Builder
            prompt: "Build."
        """)

        bridge = _make_bridge()
        # Three sync calls: agent-a (fails), agent-b (succeeds), general-agent (succeeds)
        bridge.sync_agent.side_effect = [Exception("network error"), None, None]

        agents, errors = sync_agent_registry(bridge, tmp_path)

        # All three agents validated (agent-a, agent-b, general-agent)
        assert len(agents) == 3
        # sync_agent was called for all three
        assert bridge.sync_agent.call_count == 3


# ---------------------------------------------------------------------------
# Auto-Retry Tests (Story 7.1)
# ---------------------------------------------------------------------------


def _make_crash_bridge() -> MagicMock:
    """Create a mock ConvexBridge with task and message methods for crash tests."""
    bridge = MagicMock()
    bridge.update_task_status.return_value = None
    bridge.send_message.return_value = None
    bridge.create_activity.return_value = None
    return bridge


class TestAgentGatewayFirstCrash:
    """Tests for auto-retry on first agent crash (FR37)."""

    def test_first_crash_transitions_to_retrying(self) -> None:
        """First crash should transition task in_progress -> retrying -> in_progress."""
        bridge = _make_crash_bridge()
        gw = AgentGateway(bridge)

        asyncio.get_event_loop().run_until_complete(
            gw.handle_agent_crash("dev-agent", "task_123", RuntimeError("segfault"))
        )

        # Should have called update_task_status twice:
        # 1. to "retrying" (crash detected)
        # 2. to "in_progress" (re-dispatch)
        assert bridge.update_task_status.call_count == 2
        first_call = bridge.update_task_status.call_args_list[0]
        assert first_call[0][0] == "task_123"
        assert first_call[0][1] == "retrying"
        assert first_call[0][2] == "dev-agent"

        second_call = bridge.update_task_status.call_args_list[1]
        assert second_call[0][0] == "task_123"
        assert second_call[0][1] == "in_progress"

    def test_first_crash_writes_error_to_thread(self) -> None:
        """First crash should write error details to the task thread."""
        bridge = _make_crash_bridge()
        gw = AgentGateway(bridge)

        asyncio.get_event_loop().run_until_complete(
            gw.handle_agent_crash("dev-agent", "task_123", ValueError("bad input"))
        )

        bridge.send_message.assert_called_once()
        msg_args = bridge.send_message.call_args[0]
        assert msg_args[0] == "task_123"
        assert msg_args[1] == "System"
        assert msg_args[2] == "system"
        assert "ValueError: bad input" in msg_args[3]
        assert "Auto-retrying" in msg_args[3]
        assert msg_args[4] == "system_event"

    def test_first_crash_increments_retry_count(self) -> None:
        """After first crash, retry count should be 1."""
        bridge = _make_crash_bridge()
        gw = AgentGateway(bridge)

        assert gw.get_retry_count("task_123") == 0
        asyncio.get_event_loop().run_until_complete(
            gw.handle_agent_crash("dev-agent", "task_123", RuntimeError("oops"))
        )
        assert gw.get_retry_count("task_123") == 1

    def test_retrying_description_includes_attempt(self) -> None:
        """Activity description should include attempt count."""
        bridge = _make_crash_bridge()
        gw = AgentGateway(bridge)

        asyncio.get_event_loop().run_until_complete(
            gw.handle_agent_crash("dev-agent", "task_123", RuntimeError("oops"))
        )

        first_call = bridge.update_task_status.call_args_list[0]
        description = first_call[0][3]
        assert "attempt 1/1" in description
        assert "dev-agent" in description


class TestAgentGatewaySecondCrash:
    """Tests for crash exhaustion on second crash (FR38)."""

    def test_second_crash_transitions_to_crashed(self) -> None:
        """Second crash should transition task to 'crashed'."""
        bridge = _make_crash_bridge()
        gw = AgentGateway(bridge)

        # First crash: auto-retry
        asyncio.get_event_loop().run_until_complete(
            gw.handle_agent_crash("dev-agent", "task_123", RuntimeError("first"))
        )
        bridge.reset_mock()

        # Second crash: exhausted
        asyncio.get_event_loop().run_until_complete(
            gw.handle_agent_crash("dev-agent", "task_123", RuntimeError("second"))
        )

        # Should only call update_task_status once (to "crashed")
        assert bridge.update_task_status.call_count == 1
        crash_call = bridge.update_task_status.call_args[0]
        assert crash_call[0] == "task_123"
        assert crash_call[1] == "crashed"
        assert crash_call[2] == "dev-agent"

    def test_second_crash_writes_full_error_to_thread(self) -> None:
        """Second crash should write full error details with retry-failed message."""
        bridge = _make_crash_bridge()
        gw = AgentGateway(bridge)

        asyncio.get_event_loop().run_until_complete(
            gw.handle_agent_crash("dev-agent", "task_123", RuntimeError("first"))
        )
        bridge.reset_mock()

        asyncio.get_event_loop().run_until_complete(
            gw.handle_agent_crash("dev-agent", "task_123", RuntimeError("second"))
        )

        bridge.send_message.assert_called_once()
        msg_args = bridge.send_message.call_args[0]
        assert "Retry failed" in msg_args[3]
        assert "RuntimeError: second" in msg_args[3]
        assert "Retry from Beginning" in msg_args[3]

    def test_second_crash_clears_retry_count(self) -> None:
        """After crash exhaustion, retry count should be cleared."""
        bridge = _make_crash_bridge()
        gw = AgentGateway(bridge)

        asyncio.get_event_loop().run_until_complete(
            gw.handle_agent_crash("dev-agent", "task_123", RuntimeError("first"))
        )
        assert gw.get_retry_count("task_123") == 1

        asyncio.get_event_loop().run_until_complete(
            gw.handle_agent_crash("dev-agent", "task_123", RuntimeError("second"))
        )
        assert gw.get_retry_count("task_123") == 0

    def test_crashed_description_mentions_retry_failed(self) -> None:
        """Crashed activity description should mention retry failure."""
        bridge = _make_crash_bridge()
        gw = AgentGateway(bridge)

        asyncio.get_event_loop().run_until_complete(
            gw.handle_agent_crash("dev-agent", "task_123", RuntimeError("first"))
        )
        bridge.reset_mock()

        asyncio.get_event_loop().run_until_complete(
            gw.handle_agent_crash("dev-agent", "task_123", RuntimeError("second"))
        )

        crash_call = bridge.update_task_status.call_args[0]
        description = crash_call[3]
        assert "Retry failed" in description
        assert "crashed" in description


class TestAgentGatewayRetryTracking:
    """Tests for per-task retry count tracking."""

    def test_retry_count_is_per_task(self) -> None:
        """Retry counts should be independent per task."""
        bridge = _make_crash_bridge()
        gw = AgentGateway(bridge)

        asyncio.get_event_loop().run_until_complete(
            gw.handle_agent_crash("dev-agent", "task_A", RuntimeError("crash"))
        )
        assert gw.get_retry_count("task_A") == 1
        assert gw.get_retry_count("task_B") == 0

    def test_clear_retry_count(self) -> None:
        """clear_retry_count should reset count for a specific task."""
        bridge = _make_crash_bridge()
        gw = AgentGateway(bridge)

        asyncio.get_event_loop().run_until_complete(
            gw.handle_agent_crash("dev-agent", "task_123", RuntimeError("crash"))
        )
        assert gw.get_retry_count("task_123") == 1

        gw.clear_retry_count("task_123")
        assert gw.get_retry_count("task_123") == 0

    def test_clear_nonexistent_task_is_noop(self) -> None:
        """Clearing retry count for unknown task should not raise."""
        bridge = _make_crash_bridge()
        gw = AgentGateway(bridge)
        gw.clear_retry_count("nonexistent")  # should not raise

    def test_max_auto_retries_constant(self) -> None:
        """MAX_AUTO_RETRIES should be 1 (single retry per FR37)."""
        assert MAX_AUTO_RETRIES == 1


class TestStateMachineRetryTransitions:
    """Test that the state machine supports the new retry transitions."""

    def test_retrying_to_in_progress_is_valid(self) -> None:
        from nanobot.mc.state_machine import is_valid_transition
        assert is_valid_transition("retrying", "in_progress") is True

    def test_retrying_to_crashed_is_valid(self) -> None:
        from nanobot.mc.state_machine import is_valid_transition
        assert is_valid_transition("retrying", "crashed") is True

    def test_retrying_to_inbox_is_invalid(self) -> None:
        from nanobot.mc.state_machine import is_valid_transition
        assert is_valid_transition("retrying", "inbox") is False

    def test_retrying_to_done_is_invalid(self) -> None:
        from nanobot.mc.state_machine import is_valid_transition
        assert is_valid_transition("retrying", "done") is False

    def test_retrying_to_in_progress_event_type(self) -> None:
        from nanobot.mc.state_machine import get_event_type
        assert get_event_type("retrying", "in_progress") == "task_retrying"

    def test_retrying_to_crashed_event_type(self) -> None:
        from nanobot.mc.state_machine import get_event_type
        assert get_event_type("retrying", "crashed") == "task_crashed"
