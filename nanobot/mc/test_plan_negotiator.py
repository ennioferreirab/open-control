"""Tests for the plan negotiation handler (Story 4.5, AC4 and AC10).

Covers:
- handle_plan_negotiation posts lead_agent_chat response via bridge
- handle_plan_negotiation updates execution plan when LLM returns a modified plan
- handle_plan_negotiation posts clarification without updating plan
- _parse_negotiation_response handles plain JSON and markdown-fenced JSON
- handle_plan_negotiation posts error message on LLM timeout
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanobot.mc.plan_negotiator import (
    _parse_negotiation_response,
    handle_plan_negotiation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bridge(
    post_lead_agent_message=None,
    update_execution_plan=None,
) -> MagicMock:
    """Return a mock ConvexBridge with spy methods."""
    bridge = MagicMock()
    bridge.post_lead_agent_message = post_lead_agent_message or MagicMock()
    bridge.update_execution_plan = update_execution_plan or MagicMock()
    return bridge


SAMPLE_PLAN: dict = {
    "steps": [
        {
            "tempId": "step_1",
            "title": "Extract data",
            "description": "Extract financial data",
            "assignedAgent": "financial-agent",
            "blockedBy": [],
            "parallelGroup": 1,
            "order": 1,
        }
    ],
    "generatedAt": "2026-02-25T00:00:00Z",
    "generatedBy": "lead-agent",
}

UPDATED_PLAN: dict = {
    "steps": [
        {
            "tempId": "step_1",
            "title": "Extract data",
            "description": "Extract financial data",
            "assignedAgent": "financial-agent",
            "blockedBy": [],
            "parallelGroup": 1,
            "order": 1,
        },
        {
            "tempId": "step_2",
            "title": "Write summary",
            "description": "Write a final summary report",
            "assignedAgent": "general-agent",
            "blockedBy": ["step_1"],
            "parallelGroup": 2,
            "order": 2,
        },
    ],
    "generatedAt": "2026-02-25T00:00:00Z",
    "generatedBy": "lead-agent",
}


# ---------------------------------------------------------------------------
# _parse_negotiation_response
# ---------------------------------------------------------------------------

class TestParseNegotiationResponse:
    def test_plain_json(self):
        raw = json.dumps({"action": "clarify", "message": "Could you clarify?"})
        result = _parse_negotiation_response(raw)
        assert result["action"] == "clarify"
        assert result["message"] == "Could you clarify?"

    def test_markdown_fenced_json(self):
        raw = "```json\n" + json.dumps({"action": "clarify", "message": "Hi"}) + "\n```"
        result = _parse_negotiation_response(raw)
        assert result["action"] == "clarify"

    def test_json_with_surrounding_text(self):
        payload = {"action": "update_plan", "updated_plan": UPDATED_PLAN, "explanation": "Added step 2."}
        raw = "Here is my response:\n" + json.dumps(payload) + "\nEnd."
        result = _parse_negotiation_response(raw)
        assert result["action"] == "update_plan"

    def test_invalid_json_raises(self):
        with pytest.raises(Exception):
            _parse_negotiation_response("not valid json at all")


# ---------------------------------------------------------------------------
# handle_plan_negotiation
# ---------------------------------------------------------------------------

class TestHandlePlanNegotiation:
    """Unit tests for handle_plan_negotiation function."""

    def _run(self, coro):
        """Helper to run async coroutines in sync tests."""
        return asyncio.run(coro)

    # --- AC10 / AC4: handler posts lead_agent_chat response via bridge -------

    def test_handler_posts_clarification_message(self):
        """When LLM responds with action=clarify, post_lead_agent_message is called."""
        bridge = _make_bridge()
        llm_response = json.dumps({
            "action": "clarify",
            "message": "Could you tell me more about what you need?",
        })

        with patch(
            "nanobot.mc.plan_negotiator.asyncio.to_thread",
            new=AsyncMock(side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)),
        ), patch(
            "nanobot.mc.provider_factory.create_provider"
        ) as mock_create_provider:
            mock_provider = MagicMock()
            mock_provider.chat.return_value = llm_response
            mock_create_provider.return_value = (mock_provider, "test-model")

            self._run(
                handle_plan_negotiation(
                    bridge,
                    task_id="task_abc",
                    user_message="Can you help me?",
                    current_plan=SAMPLE_PLAN,
                )
            )

        bridge.post_lead_agent_message.assert_called_once_with(
            "task_abc",
            "Could you tell me more about what you need?",
            "lead_agent_chat",
        )
        bridge.update_execution_plan.assert_not_called()

    # --- AC10: handler updates execution plan when LLM returns modified plan -

    def test_handler_updates_plan_on_update_action(self):
        """When LLM returns action=update_plan, both update and message are called."""
        bridge = _make_bridge()
        explanation = "I added a summary step at the end."
        llm_response = json.dumps({
            "action": "update_plan",
            "updated_plan": UPDATED_PLAN,
            "explanation": explanation,
        })

        with patch(
            "nanobot.mc.plan_negotiator.asyncio.to_thread",
            new=AsyncMock(side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)),
        ), patch(
            "nanobot.mc.provider_factory.create_provider"
        ) as mock_create_provider:
            mock_provider = MagicMock()
            mock_provider.chat.return_value = llm_response
            mock_create_provider.return_value = (mock_provider, "test-model")

            self._run(
                handle_plan_negotiation(
                    bridge,
                    task_id="task_abc",
                    user_message="Add a summary step",
                    current_plan=SAMPLE_PLAN,
                )
            )

        # Execution plan MUST be updated
        bridge.update_execution_plan.assert_called_once()
        call_args = bridge.update_execution_plan.call_args
        assert call_args[0][0] == "task_abc"
        updated_plan_dict = call_args[0][1]
        assert isinstance(updated_plan_dict, dict)
        assert len(updated_plan_dict["steps"]) == 2

        # Lead agent chat message MUST be posted with the explanation
        bridge.post_lead_agent_message.assert_called_once_with(
            "task_abc",
            explanation,
            "lead_agent_chat",
        )

    # --- AC10: handler posts clarification without updating plan when action=clarify

    def test_handler_does_not_update_plan_on_clarify(self):
        """When LLM responds with action=clarify, update_execution_plan is NOT called."""
        bridge = _make_bridge()
        llm_response = json.dumps({
            "action": "clarify",
            "message": "Which agent should handle the new step?",
        })

        with patch(
            "nanobot.mc.plan_negotiator.asyncio.to_thread",
            new=AsyncMock(side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)),
        ), patch(
            "nanobot.mc.provider_factory.create_provider"
        ) as mock_create_provider:
            mock_provider = MagicMock()
            mock_provider.chat.return_value = llm_response
            mock_create_provider.return_value = (mock_provider, "test-model")

            self._run(
                handle_plan_negotiation(
                    bridge,
                    task_id="task_xyz",
                    user_message="Add a step but I'm not sure which agent",
                    current_plan=SAMPLE_PLAN,
                )
            )

        # update_execution_plan MUST NOT be called
        bridge.update_execution_plan.assert_not_called()
        # But a chat message MUST be posted
        bridge.post_lead_agent_message.assert_called_once_with(
            "task_xyz",
            "Which agent should handle the new step?",
            "lead_agent_chat",
        )

    # --- Timeout handling ---

    def test_handler_posts_error_on_timeout(self):
        """When LLM times out, an error message is posted via bridge."""
        bridge = _make_bridge()

        async def _fake_to_thread(fn, *args, **kwargs):
            # For post_lead_agent_message, run normally
            if fn == bridge.post_lead_agent_message:
                return fn(*args, **kwargs)
            return fn(*args, **kwargs)

        async def _timeout_wait_for(coro, timeout):
            raise asyncio.TimeoutError

        with patch(
            "nanobot.mc.plan_negotiator.asyncio.to_thread",
            new=AsyncMock(side_effect=_fake_to_thread),
        ), patch(
            "nanobot.mc.plan_negotiator.asyncio.wait_for",
            new=AsyncMock(side_effect=_timeout_wait_for),
        ), patch(
            "nanobot.mc.provider_factory.create_provider"
        ) as mock_create_provider:
            mock_provider = MagicMock()
            mock_create_provider.return_value = (mock_provider, "test-model")

            self._run(
                handle_plan_negotiation(
                    bridge,
                    task_id="task_timeout",
                    user_message="Do something",
                    current_plan=SAMPLE_PLAN,
                )
            )

        bridge.post_lead_agent_message.assert_called_once()
        call_args = bridge.post_lead_agent_message.call_args[0]
        assert call_args[0] == "task_timeout"
        assert "timed out" in call_args[1].lower()
        assert call_args[2] == "lead_agent_chat"
        bridge.update_execution_plan.assert_not_called()

    # --- update_plan with missing updated_plan field falls back to clarify ---

    def test_handler_falls_back_when_updated_plan_missing(self):
        """When action=update_plan but updated_plan is missing, fallback to clarify."""
        bridge = _make_bridge()
        llm_response = json.dumps({
            "action": "update_plan",
            # No "updated_plan" key
            "explanation": "I updated the plan",
        })

        with patch(
            "nanobot.mc.plan_negotiator.asyncio.to_thread",
            new=AsyncMock(side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)),
        ), patch(
            "nanobot.mc.provider_factory.create_provider"
        ) as mock_create_provider:
            mock_provider = MagicMock()
            mock_provider.chat.return_value = llm_response
            mock_create_provider.return_value = (mock_provider, "test-model")

            self._run(
                handle_plan_negotiation(
                    bridge,
                    task_id="task_fallback",
                    user_message="Update the plan please",
                    current_plan=SAMPLE_PLAN,
                )
            )

        bridge.update_execution_plan.assert_not_called()
        bridge.post_lead_agent_message.assert_called_once()
