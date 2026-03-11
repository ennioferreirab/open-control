"""Tests for the plan negotiation handler (Story 4.5, AC4 and AC10).

Covers:
- handle_plan_negotiation posts lead_agent_chat response via bridge
- handle_plan_negotiation updates execution plan when LLM returns a modified plan
- handle_plan_negotiation posts clarification without updating plan
- _parse_negotiation_response handles plain JSON and markdown-fenced JSON
- handle_plan_negotiation posts error message on LLM timeout

Story 7.3 additions:
- handle_plan_negotiation fetches step statuses when task is in_progress
- handle_plan_negotiation includes step status context in LLM prompt
- handle_plan_negotiation returns clarify (not update_plan) for locked steps
- start_plan_negotiation_loop handles in_progress tasks (not only review)
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from mc.contexts.planning.negotiation import (
    _has_current_plan_review_request,
    _parse_negotiation_response,
    create_initial_plan_from_message,
    handle_plan_negotiation,
    start_plan_negotiation_loop,
)
from mc.types import ExecutionPlan, ExecutionPlanStep


class _FakeLLMResponse:
    """Mimics LLMResponse with a .content attribute for test mocking."""

    def __init__(self, content: str):
        self.content = content


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
            "assignedAgent": "nanobot",
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
        payload = {
            "action": "update_plan",
            "updated_plan": UPDATED_PLAN,
            "explanation": "Added step 2.",
        }
        raw = "Here is my response:\n" + json.dumps(payload) + "\nEnd."
        result = _parse_negotiation_response(raw)
        assert result["action"] == "update_plan"

    def test_invalid_json_returns_clarify(self):
        result = _parse_negotiation_response("not valid json at all")
        assert result["action"] == "clarify"
        assert result["message"] == "not valid json at all"

    def test_empty_response_returns_clarify(self):
        result = _parse_negotiation_response("")
        assert result["action"] == "clarify"
        assert result["message"] == "(No response from model)"


class TestCurrentPlanReviewRequestDetection:
    def test_detects_matching_review_request(self):
        assert _has_current_plan_review_request(
            [
                {
                    "type": "lead_agent_plan",
                    "plan_review": {
                        "kind": "request",
                        "plan_generated_at": SAMPLE_PLAN["generatedAt"],
                    },
                }
            ],
            plan_generated_at=SAMPLE_PLAN["generatedAt"],
        )

    def test_ignores_non_matching_messages(self):
        assert not _has_current_plan_review_request(
            [
                {
                    "type": "lead_agent_chat",
                    "plan_review": {
                        "kind": "request",
                        "plan_generated_at": SAMPLE_PLAN["generatedAt"],
                    },
                }
            ],
            plan_generated_at=SAMPLE_PLAN["generatedAt"],
        )


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
        llm_response = json.dumps(
            {
                "action": "clarify",
                "message": "Could you tell me more about what you need?",
            }
        )

        with patch("mc.infrastructure.providers.factory.create_provider") as mock_create_provider:
            mock_provider = MagicMock()
            mock_provider.chat = AsyncMock(return_value=_FakeLLMResponse(llm_response))
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
        llm_response = json.dumps(
            {
                "action": "update_plan",
                "updated_plan": UPDATED_PLAN,
                "explanation": explanation,
            }
        )

        with patch("mc.infrastructure.providers.factory.create_provider") as mock_create_provider:
            mock_provider = MagicMock()
            mock_provider.chat = AsyncMock(return_value=_FakeLLMResponse(llm_response))
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

        # Lead agent chat message MUST be posted with the explanation,
        # followed by a fresh plan review request for the new version.
        assert bridge.post_lead_agent_message.call_count == 2
        first_call = bridge.post_lead_agent_message.call_args_list[0]
        second_call = bridge.post_lead_agent_message.call_args_list[1]
        assert first_call.args == (
            "task_abc",
            explanation,
            "lead_agent_chat",
        )
        assert second_call.args[0] == "task_abc"
        assert second_call.args[2] == "lead_agent_plan"
        assert second_call.kwargs["plan_review"] == {
            "kind": "request",
            "plan_generated_at": updated_plan_dict["generatedAt"],
        }

    # --- AC10: handler posts clarification without updating plan when action=clarify

    def test_handler_does_not_update_plan_on_clarify(self):
        """When LLM responds with action=clarify, update_execution_plan is NOT called."""
        bridge = _make_bridge()
        llm_response = json.dumps(
            {
                "action": "clarify",
                "message": "Which agent should handle the new step?",
            }
        )

        with patch("mc.infrastructure.providers.factory.create_provider") as mock_create_provider:
            mock_provider = MagicMock()
            mock_provider.chat = AsyncMock(return_value=_FakeLLMResponse(llm_response))
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

        async def _timeout_wait_for(coro, timeout):
            raise asyncio.TimeoutError

        with (
            patch(
                "mc.contexts.planning.negotiation.asyncio.wait_for",
                new=AsyncMock(side_effect=_timeout_wait_for),
            ),
            patch("mc.infrastructure.providers.factory.create_provider") as mock_create_provider,
        ):
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
        llm_response = json.dumps(
            {
                "action": "update_plan",
                # No "updated_plan" key
                "explanation": "I updated the plan",
            }
        )

        with patch("mc.infrastructure.providers.factory.create_provider") as mock_create_provider:
            mock_provider = MagicMock()
            mock_provider.chat = AsyncMock(return_value=_FakeLLMResponse(llm_response))
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

    def test_handler_rejects_partial_updated_plan_payload(self):
        """Malformed updated_plan payloads must not be persisted."""
        bridge = _make_bridge()
        llm_response = json.dumps(
            {
                "action": "update_plan",
                "updated_plan": {
                    "steps": [
                        UPDATED_PLAN["steps"][0],
                        {
                            "tempId": "step_2",
                            "title": "Create concept 3 logo",
                            "description": "Truncated step payload",
                        },
                    ],
                },
                "explanation": "Added the requested logo step.",
            }
        )

        with patch("mc.infrastructure.providers.factory.create_provider") as mock_create_provider:
            mock_provider = MagicMock()
            mock_provider.chat = AsyncMock(return_value=_FakeLLMResponse(llm_response))
            mock_create_provider.return_value = (mock_provider, "test-model")

            self._run(
                handle_plan_negotiation(
                    bridge,
                    task_id="task_partial",
                    user_message="Add the third logo concept.",
                    current_plan=SAMPLE_PLAN,
                )
            )

        bridge.update_execution_plan.assert_not_called()
        bridge.post_lead_agent_message.assert_called_once()
        assert "plan has not been changed" in bridge.post_lead_agent_message.call_args.args[1]


class TestCreateInitialPlanFromMessage:
    """Tests for bootstrapping the first plan from manual-review conversation."""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_creates_initial_plan_for_manual_review_task(self):
        bridge = MagicMock()
        bridge.list_agents = MagicMock(
            return_value=[
                {
                    "name": "nanobot",
                    "display_name": "Nanobot",
                    "role": "generalist",
                    "skills": ["general"],
                    "enabled": True,
                    "is_system": True,
                }
            ]
        )
        bridge.get_board_by_id = MagicMock(return_value=None)
        bridge.update_execution_plan = MagicMock()
        bridge.update_task_status = MagicMock()
        bridge.create_activity = MagicMock()
        bridge.post_lead_agent_message = MagicMock()

        task_data = {
            "id": "task-manual",
            "title": "Merge task",
            "description": "Merge two threads and keep the best ideas.",
            "status": "review",
            "is_manual": True,
            "files": [],
        }
        plan = ExecutionPlan(
            steps=[
                ExecutionPlanStep(
                    temp_id="step_1",
                    title="Outline the merged approach",
                    description="Synthesize the merged task into a clear execution plan.",
                    assigned_agent="nanobot",
                    blocked_by=[],
                    parallel_group=1,
                    order=1,
                )
            ]
        )

        with (
            patch(
                "mc.contexts.planning.negotiation.asyncio.to_thread",
                new=AsyncMock(side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)),
            ),
            patch("mc.contexts.planning.negotiation.TaskPlanner") as planner_cls,
        ):
            planner = planner_cls.return_value
            planner.plan_task = AsyncMock(return_value=plan)

            self._run(
                create_initial_plan_from_message(
                    bridge=bridge,
                    task_id="task-manual",
                    user_message="Please create the first execution plan from this merge.",
                    task_data=task_data,
                )
            )

        planner.plan_task.assert_awaited_once()
        planner_call = planner.plan_task.await_args
        assert planner_call.args[0] == "Merge task"
        assert "Please create the first execution plan" in planner_call.args[1]
        bridge.update_execution_plan.assert_called_once_with("task-manual", plan.to_dict())
        bridge.update_task_status.assert_called_once()
        status_call = bridge.update_task_status.call_args
        assert status_call.args[0] == "task-manual"
        assert status_call.args[1] == "review"
        assert status_call.args[3].startswith("Initial plan ready for review")
        assert status_call.args[4] is True
        bridge.post_lead_agent_message.assert_called_once()
        post_call = bridge.post_lead_agent_message.call_args
        assert post_call.args[0] == "task-manual"
        assert post_call.args[2] == "lead_agent_plan"
        assert post_call.kwargs["plan_review"] == {
            "kind": "request",
            "plan_generated_at": plan.generated_at,
        }


# ---------------------------------------------------------------------------
# Story 7.3: Execution context — in_progress support
# ---------------------------------------------------------------------------

RUNNING_STEPS = [
    {
        "id": "step_db_id_1",
        "title": "Extract data",
        "status": "running",
        "assigned_agent": "financial-agent",
        "temp_id": "step_1",
    },
    {
        "id": "step_db_id_2",
        "title": "Write summary",
        "status": "planned",  # "planned" is the correct Convex step status (not "pending")
        "assigned_agent": "nanobot",
        "temp_id": "step_2",
    },
]


class TestHandlePlanNegotiationExecutionContext:
    """Tests for Story 7.3 — execution context when task is in_progress."""

    def _run(self, coro):
        """Helper to run async coroutines in sync tests."""
        return asyncio.run(coro)

    def _make_bridge_with_steps(self, steps=None, post_fn=None, update_fn=None):
        """Return a mock bridge that returns given steps from get_steps_by_task."""
        bridge = MagicMock()
        bridge.post_lead_agent_message = post_fn or MagicMock()
        bridge.update_execution_plan = update_fn or MagicMock()
        bridge.get_steps_by_task = MagicMock(return_value=steps or [])
        return bridge

    # 6.1: handler fetches step statuses when task is in_progress and includes them in LLM prompt

    def test_in_progress_includes_step_context_in_prompt(self):
        """When task_status=in_progress, the LLM prompt includes step execution state."""
        captured_messages: list = []

        async def _fake_chat(**kwargs):
            captured_messages.extend(kwargs.get("messages", []))
            return _FakeLLMResponse(json.dumps({"action": "clarify", "message": "Understood."}))

        bridge = self._make_bridge_with_steps(steps=RUNNING_STEPS)
        mock_provider = MagicMock()
        mock_provider.chat = _fake_chat

        with patch(
            "mc.infrastructure.providers.factory.create_provider",
            return_value=(mock_provider, "test-model"),
        ):
            self._run(
                handle_plan_negotiation(
                    bridge,
                    task_id="task_inprogress",
                    user_message="Can you remove step 2?",
                    current_plan=SAMPLE_PLAN,
                    task_status="in_progress",
                    current_steps=RUNNING_STEPS,
                )
            )

        # System prompt or user prompt should mention step statuses
        all_prompt_content = " ".join(m.get("content", "") for m in captured_messages)
        assert (
            "running" in all_prompt_content.lower()
            or "locked" in all_prompt_content.lower()
            or "cannot" in all_prompt_content.lower()
        )

    # 6.2: enforcement layer blocks update_plan for locked steps even when LLM ignores prompt

    def test_in_progress_locked_step_enforcement_blocks_update_plan(self):
        """When LLM returns update_plan for a running/locked step, the handler must veto it.

        This tests the Python-side enforcement, NOT just reliance on the LLM obeying
        the system prompt. Even if the LLM returns action=update_plan with a step whose
        title matches a locked (running/completed/assigned) materialized step, the handler
        must block the update and post a clarification message instead.
        """
        bridge = self._make_bridge_with_steps(steps=RUNNING_STEPS)
        # LLM ignores the system prompt and returns update_plan with the running step
        llm_response = json.dumps(
            {
                "action": "update_plan",
                "updated_plan": {
                    "steps": [
                        {
                            "tempId": "step_1",
                            # Same title as RUNNING_STEPS[0] which is "running" status
                            "title": "Extract data",
                            "description": "Modified description",
                            "assignedAgent": "financial-agent",
                            "blockedBy": [],
                            "parallelGroup": 1,
                            "order": 1,
                        }
                    ]
                },
                "explanation": "I changed step 1.",
            }
        )
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=_FakeLLMResponse(llm_response))

        with patch(
            "mc.infrastructure.providers.factory.create_provider",
            return_value=(mock_provider, "test-model"),
        ):
            self._run(
                handle_plan_negotiation(
                    bridge,
                    task_id="task_locked",
                    user_message="Cancel step 1",
                    current_plan=SAMPLE_PLAN,
                    task_status="in_progress",
                    current_steps=RUNNING_STEPS,
                )
            )

        # Plan must NOT be updated — the enforcement layer must have blocked it
        bridge.update_execution_plan.assert_not_called()
        # A clarification/rejection message must be posted explaining the constraint
        bridge.post_lead_agent_message.assert_called_once()
        call_args = bridge.post_lead_agent_message.call_args[0]
        assert call_args[2] == "lead_agent_chat"
        # Message must reference the locked step
        assert "Extract data" in call_args[1] or "cannot" in call_args[1].lower()

    def test_in_progress_update_plan_allowed_for_planned_steps(self):
        """When LLM returns update_plan for a planned step only, the update is applied."""
        bridge = self._make_bridge_with_steps(steps=RUNNING_STEPS)
        # RUNNING_STEPS[1] has title "Write summary" and status "planned" — modifiable
        llm_response = json.dumps(
            {
                "action": "update_plan",
                "updated_plan": {
                    "steps": [
                        {
                            "tempId": "step_2",
                            "title": "Write summary",
                            "description": "Updated summary description",
                            "assignedAgent": "nanobot",
                            "blockedBy": [],
                            "parallelGroup": 2,
                            "order": 2,
                        }
                    ]
                },
                "explanation": "I updated the summary step.",
            }
        )
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=_FakeLLMResponse(llm_response))

        with patch(
            "mc.infrastructure.providers.factory.create_provider",
            return_value=(mock_provider, "test-model"),
        ):
            self._run(
                handle_plan_negotiation(
                    bridge,
                    task_id="task_pending_ok",
                    user_message="Update the summary step description",
                    current_plan=SAMPLE_PLAN,
                    task_status="in_progress",
                    current_steps=RUNNING_STEPS,
                )
            )

        # Plan update MUST be applied (only planned step is being changed)
        bridge.update_execution_plan.assert_called_once()
        bridge.post_lead_agent_message.assert_called_once()

    # 6.3: start_plan_negotiation_loop handles in_progress tasks

    def test_loop_continues_for_in_progress_task(self):
        """start_plan_negotiation_loop does NOT stop immediately for in_progress tasks."""
        import asyncio as _asyncio

        # Task is in_progress — loop should NOT stop on first poll
        task_data = {
            "status": "in_progress",
            "awaiting_kickoff": False,
            "execution_plan": SAMPLE_PLAN,
        }

        user_message = {
            "_id": "msg_001",
            "author_type": "user",
            "content": "Please add a step",
        }

        call_count = 0

        async def _fake_queue_get():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [user_message]
            # Stop the loop after first iteration by raising CancelledError
            raise _asyncio.CancelledError

        bridge = MagicMock()
        bridge.query = MagicMock(return_value=task_data)
        bridge.get_steps_by_task = MagicMock(return_value=[])
        bridge.post_lead_agent_message = MagicMock()
        bridge.update_execution_plan = MagicMock()

        mock_queue = MagicMock()
        mock_queue.get = AsyncMock(side_effect=_fake_queue_get)
        bridge.async_subscribe = MagicMock(return_value=mock_queue)

        # The loop should process the user_message without stopping for in_progress
        # We verify by checking that query was called (status check happened) and
        # that the loop didn't stop before the first message was processed.
        with (
            patch(
                "mc.contexts.planning.negotiation.asyncio.to_thread",
                new=AsyncMock(side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)),
            ),
            patch(
                "mc.contexts.planning.negotiation.handle_plan_negotiation",
                new=AsyncMock(return_value=None),
            ) as mock_handle,
        ):
            try:
                _asyncio.run(
                    start_plan_negotiation_loop(bridge, "task_inprogress", poll_interval=0.01)
                )
            except _asyncio.CancelledError:
                pass

        # The loop should have seen the in_progress task and NOT stopped
        # (i.e., it called handle_plan_negotiation for the user message)
        mock_handle.assert_called_once()
        call_args = mock_handle.call_args
        # Verify that task_status="in_progress" was passed as a keyword argument
        assert call_args[1]["task_status"] == "in_progress"

    def test_loop_continues_for_paused_review_task_with_plan(self):
        """Paused review tasks with an execution plan should still route plan chat."""
        import asyncio as _asyncio

        task_data = {
            "status": "review",
            "awaiting_kickoff": False,
            "execution_plan": SAMPLE_PLAN,
        }

        user_message = {
            "_id": "msg_paused",
            "author_type": "user",
            "content": "Please revise the plan before resuming",
        }

        call_count = 0

        async def _fake_queue_get():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [user_message]
            raise _asyncio.CancelledError

        bridge = MagicMock()
        bridge.query = MagicMock(return_value=task_data)
        bridge.get_steps_by_task = MagicMock(return_value=[])
        bridge.post_lead_agent_message = MagicMock()
        bridge.update_execution_plan = MagicMock()

        mock_queue = MagicMock()
        mock_queue.get = AsyncMock(side_effect=_fake_queue_get)
        bridge.async_subscribe = MagicMock(return_value=mock_queue)

        with (
            patch(
                "mc.contexts.planning.negotiation.asyncio.to_thread",
                new=AsyncMock(side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)),
            ),
            patch(
                "mc.contexts.planning.negotiation.handle_plan_negotiation",
                new=AsyncMock(return_value=None),
            ) as mock_handle,
        ):
            try:
                _asyncio.run(start_plan_negotiation_loop(bridge, "task_paused", poll_interval=0.01))
            except _asyncio.CancelledError:
                pass

        mock_handle.assert_called_once()
        call_args = mock_handle.call_args
        assert call_args[1]["task_status"] == "review"

    def test_loop_bootstraps_first_plan_for_manual_review_without_execution_plan(self):
        """Manual review tasks without a plan should route the first user message into planning."""
        import asyncio as _asyncio

        task_data = {
            "status": "review",
            "awaiting_kickoff": False,
            "is_manual": True,
            "title": "Manual review task",
            "description": "Needs an initial plan",
        }

        user_message = {
            "_id": "msg_first_plan",
            "author_type": "user",
            "content": "Create the initial execution plan, then I will review it.",
        }

        async def _fake_queue_get():
            return [user_message]

        bridge = MagicMock()
        bridge.query = MagicMock(side_effect=[task_data, {"status": "done"}])
        bridge.post_lead_agent_message = MagicMock()
        bridge.update_execution_plan = MagicMock()
        mock_queue = MagicMock()
        mock_queue.get = AsyncMock(side_effect=[[user_message], _asyncio.CancelledError()])
        bridge.async_subscribe = MagicMock(return_value=mock_queue)

        with (
            patch(
                "mc.contexts.planning.negotiation.asyncio.to_thread",
                new=AsyncMock(side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)),
            ),
            patch(
                "mc.contexts.planning.negotiation.create_initial_plan_from_message",
                new=AsyncMock(return_value=None),
            ) as mock_initial_plan,
            patch(
                "mc.contexts.planning.negotiation.handle_plan_negotiation",
                new=AsyncMock(return_value=None),
            ) as mock_handle,
        ):
            try:
                _asyncio.run(
                    start_plan_negotiation_loop(
                        bridge,
                        "task_manual_review",
                        poll_interval=0.01,
                    )
                )
            except _asyncio.CancelledError:
                pass

        mock_initial_plan.assert_called_once()
        bootstrap_call = mock_initial_plan.call_args
        assert bootstrap_call.args[1] == "task_manual_review"
        assert bootstrap_call.args[2] == user_message["content"]
        assert bootstrap_call.kwargs["task_data"]["is_manual"] is True
        mock_handle.assert_not_called()

    def test_loop_backfills_missing_plan_review_request_for_existing_review_plan(self):
        """Review tasks with an execution plan but no lead-agent request should self-repair."""
        import asyncio as _asyncio

        task_data = {
            "status": "review",
            "awaiting_kickoff": False,
            "is_manual": True,
            "execution_plan": SAMPLE_PLAN,
        }
        system_message = {
            "_id": "msg_system",
            "author_type": "system",
            "content": "Existing thread history",
        }

        bridge = MagicMock()
        bridge.query = MagicMock(side_effect=[task_data, {"status": "done"}])
        bridge.post_lead_agent_message = MagicMock()
        bridge.update_execution_plan = MagicMock()
        mock_queue = MagicMock()
        mock_queue.get = AsyncMock(side_effect=[[system_message], _asyncio.CancelledError()])
        bridge.async_subscribe = MagicMock(return_value=mock_queue)

        with (
            patch(
                "mc.contexts.planning.negotiation.asyncio.to_thread",
                new=AsyncMock(side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)),
            ),
            patch(
                "mc.contexts.planning.negotiation.handle_plan_negotiation",
                new=AsyncMock(return_value=None),
            ),
        ):
            try:
                _asyncio.run(
                    start_plan_negotiation_loop(
                        bridge,
                        "task_missing_request",
                        poll_interval=0.01,
                    )
                )
            except _asyncio.CancelledError:
                pass

        bridge.post_lead_agent_message.assert_called_once()
        post_call = bridge.post_lead_agent_message.call_args
        assert post_call.args[0] == "task_missing_request"
        assert post_call.args[2] == "lead_agent_plan"
        assert post_call.kwargs["plan_review"] == {
            "kind": "request",
            "plan_generated_at": SAMPLE_PLAN["generatedAt"],
        }

    def test_loop_stops_for_non_negotiable_status(self):
        """start_plan_negotiation_loop stops when task is in a non-negotiable status."""
        import asyncio as _asyncio

        task_data = {
            "status": "done",
            "awaiting_kickoff": False,
            "execution_plan": SAMPLE_PLAN,
        }
        user_message = {"_id": "msg_done", "author_type": "user", "content": "hello"}

        async def _fake_queue_get():
            return [user_message]

        bridge = MagicMock()
        bridge.query = MagicMock(return_value=task_data)
        bridge.get_steps_by_task = MagicMock(return_value=[])

        mock_queue = MagicMock()
        mock_queue.get = AsyncMock(side_effect=_fake_queue_get)
        bridge.async_subscribe = MagicMock(return_value=mock_queue)

        with (
            patch(
                "mc.contexts.planning.negotiation.asyncio.to_thread",
                new=AsyncMock(side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)),
            ),
            patch(
                "mc.contexts.planning.negotiation.handle_plan_negotiation",
                new=AsyncMock(return_value=None),
            ) as mock_handle,
        ):
            _asyncio.run(start_plan_negotiation_loop(bridge, "task_done", poll_interval=0.01))

        # Loop stops immediately without processing messages
        mock_handle.assert_not_called()

    # Verify loop subscribes to messages:listByTask (not listPlanChat)

    def test_loop_subscribes_to_list_by_task(self):
        """start_plan_negotiation_loop subscribes to messages:listByTask."""
        import asyncio as _asyncio

        # Use done status with a non-empty (but non-user) message to trigger the task status check
        task_data = {"status": "done", "awaiting_kickoff": False, "execution_plan": {}}
        system_message = {"_id": "sys_001", "author_type": "system", "content": "task done"}

        async def _fake_queue_get():
            return [system_message]

        bridge = MagicMock()
        bridge.query = MagicMock(return_value=task_data)
        bridge.get_steps_by_task = MagicMock(return_value=[])
        mock_queue = MagicMock()
        mock_queue.get = AsyncMock(side_effect=_fake_queue_get)
        bridge.async_subscribe = MagicMock(return_value=mock_queue)

        with patch(
            "mc.contexts.planning.negotiation.asyncio.to_thread",
            new=AsyncMock(side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)),
        ):
            _asyncio.run(start_plan_negotiation_loop(bridge, "task_sub", poll_interval=0.01))

        bridge.async_subscribe.assert_called_once()
        call_args = bridge.async_subscribe.call_args[0]
        assert call_args[0] == "messages:listByTask"

    def test_loop_skips_plan_review_decision_messages(self):
        """Approval decisions should stay as history and not re-enter negotiation."""
        import asyncio as _asyncio

        task_data = {
            "status": "review",
            "awaiting_kickoff": True,
            "execution_plan": SAMPLE_PLAN,
        }
        approval_message = {
            "_id": "msg_approval",
            "author_type": "user",
            "content": "Approved plan.",
            "plan_review": {
                "kind": "decision",
                "plan_generated_at": SAMPLE_PLAN["generatedAt"],
                "decision": "approved",
            },
        }

        async def _fake_queue_get():
            return [approval_message]

        bridge = MagicMock()
        bridge.query = MagicMock(side_effect=[task_data, task_data, None])
        bridge.get_steps_by_task = MagicMock(return_value=[])
        mock_queue = MagicMock()
        mock_queue.get = AsyncMock(side_effect=[[approval_message], _asyncio.CancelledError()])
        bridge.async_subscribe = MagicMock(return_value=mock_queue)

        with (
            patch(
                "mc.contexts.planning.negotiation.asyncio.to_thread",
                new=AsyncMock(side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)),
            ),
            patch(
                "mc.contexts.planning.negotiation.handle_plan_negotiation",
                new=AsyncMock(return_value=None),
            ) as mock_handle,
        ):
            try:
                _asyncio.run(start_plan_negotiation_loop(bridge, "task_review", poll_interval=0.01))
            except _asyncio.CancelledError:
                pass

        mock_handle.assert_not_called()
