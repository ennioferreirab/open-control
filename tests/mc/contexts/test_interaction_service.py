from __future__ import annotations

from typing import Any

from mc.contexts.interaction.service import InteractionService
from mc.contexts.interaction.types import InteractionContext


class FakeBridge:
    def __init__(self) -> None:
        self.mutations: list[tuple[str, dict[str, Any] | None]] = []
        self.queries: list[tuple[str, dict[str, Any] | None]] = []
        self._question_polls = 0

    def mutation(self, function_name: str, args: dict[str, Any] | None = None) -> Any:
        self.mutations.append((function_name, args))
        return None

    def query(self, function_name: str, args: dict[str, Any] | None = None) -> Any:
        self.queries.append((function_name, args))
        if function_name == "executionQuestions:hasPendingForTask":
            return True
        if function_name == "executionQuestions:getByQuestionId":
            self._question_polls += 1
            if self._question_polls == 1:
                return {"question_id": args["question_id"], "status": "pending"}
            return {
                "question_id": args["question_id"],
                "status": "answered",
                "answer": "Blue",
            }
        return None


class IdempotentStatusBridge(FakeBridge):
    def mutation(self, function_name: str, args: dict[str, Any] | None = None) -> Any:
        if function_name == "tasks:updateStatus" and args and args.get("status") == "review":
            raise Exception("Cannot transition from 'review' to 'review'")
        if function_name == "steps:updateStatus" and args and args.get("status") == "waiting_human":
            raise Exception("Cannot transition waiting_human -> waiting_human")
        if function_name == "tasks:updateStatus" and args and args.get("status") == "in_progress":
            raise Exception("Cannot transition from 'in_progress' to 'in_progress'")
        if function_name == "steps:updateStatus" and args and args.get("status") == "running":
            raise Exception("Cannot transition running -> running")
        return super().mutation(function_name, args)


def _context() -> InteractionContext:
    return InteractionContext(
        session_id="session-1",
        task_id="task-1",
        step_id="step-1",
        agent_name="offer-strategist",
        provider="claude-code",
    )


def _task_level_context() -> InteractionContext:
    return InteractionContext(
        session_id="session-1",
        task_id="task-1",
        step_id=None,
        agent_name="offer-strategist",
        provider="claude-code",
    )


def test_report_progress_dual_writes_session_and_event() -> None:
    bridge = FakeBridge()
    service = InteractionService(bridge)

    service.report_progress(context=_context(), message="Halfway", percentage=50)

    assert bridge.mutations[0][0] == "executionSessions:upsert"
    assert bridge.mutations[0][1]["last_progress_message"] == "Halfway"
    assert bridge.mutations[1][0] == "executionInteractions:append"
    assert bridge.mutations[1][1]["kind"] == "progress_reported"


def test_record_final_result_writes_completed_session_and_event() -> None:
    bridge = FakeBridge()
    service = InteractionService(bridge)

    service.record_final_result(context=_context(), content="Done", source="mc-mcp")

    assert bridge.mutations[0][0] == "executionSessions:upsert"
    assert bridge.mutations[0][1]["state"] == "completed"
    assert bridge.mutations[1][0] == "executionInteractions:append"
    assert bridge.mutations[1][1]["kind"] == "final_result_recorded"


def test_ask_user_creates_question_posts_message_and_waits(monkeypatch) -> None:
    bridge = FakeBridge()
    service = InteractionService(bridge)
    monkeypatch.setattr(
        "mc.contexts.interaction.service.time.sleep", lambda *_args, **_kwargs: None
    )

    answer = service.ask_user(context=_context(), question="What color?", options=["Blue", "Green"])

    assert answer == "Blue"
    assert bridge.mutations[0][0] == "executionQuestions:create"
    assert bridge.mutations[1][0] == "messages:create"
    assert bridge.mutations[2][0] == "tasks:updateStatus"
    assert bridge.mutations[2][1]["awaiting_kickoff"] is False
    assert bridge.mutations[2][1]["review_phase"] == "execution_pause"
    assert bridge.mutations[3][0] == "steps:updateStatus"
    assert bridge.mutations[3][1]["status"] == "waiting_human"
    assert bridge.mutations[-2][0] == "tasks:updateStatus"
    assert bridge.mutations[-2][1]["awaiting_kickoff"] is False
    assert "review_phase" not in bridge.mutations[-2][1]
    assert bridge.mutations[-1][0] == "steps:updateStatus"
    assert bridge.mutations[-1][1]["status"] == "running"


def test_has_pending_question_queries_convex() -> None:
    bridge = FakeBridge()
    service = InteractionService(bridge)

    assert service.has_pending_question(task_id="task-1") is True
    assert bridge.queries[-1][0] == "executionQuestions:hasPendingForTask"


def test_ask_user_omits_null_step_id_from_convex_payload(monkeypatch) -> None:
    bridge = FakeBridge()
    service = InteractionService(bridge)
    monkeypatch.setattr(
        "mc.contexts.interaction.service.time.sleep", lambda *_args, **_kwargs: None
    )

    answer = service.ask_user(context=_task_level_context(), question="What color?")

    assert answer == "Blue"
    create_payload = bridge.mutations[0][1]
    assert create_payload is not None
    assert "step_id" not in create_payload


def test_ask_user_tolerates_same_status_review_and_resume_transitions(monkeypatch) -> None:
    bridge = IdempotentStatusBridge()
    service = InteractionService(bridge)
    monkeypatch.setattr(
        "mc.contexts.interaction.service.time.sleep", lambda *_args, **_kwargs: None
    )

    answer = service.ask_user(context=_context(), question="What color?")

    assert answer == "Blue"
    assert bridge.mutations[0][0] == "executionQuestions:create"
