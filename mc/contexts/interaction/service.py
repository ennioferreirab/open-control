from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from mc.contexts.interaction.types import BridgeLike, InteractionContext


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _omit_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def _is_same_status_error(exc: Exception, status: str) -> bool:
    msg = str(exc)
    return (
        f"{status} -> {status}" in msg
        or f"from '{status}' to '{status}'" in msg
        or f'from "{status}" to "{status}"' in msg
    )


class InteractionService:
    """Durable interaction facade backed by Convex mutations and queries."""

    def __init__(self, bridge: BridgeLike) -> None:
        self._bridge = bridge

    def ensure_session(
        self,
        *,
        context: InteractionContext,
        state: str = "running",
        progress_message: str | None = None,
        progress_percentage: int | None = None,
    ) -> None:
        self._bridge.mutation(
            "executionSessions:upsert",
            _omit_none(
                {
                    "session_id": context.session_id,
                    "task_id": context.task_id,
                    "step_id": context.step_id,
                    "agent_name": context.agent_name,
                    "provider": context.provider,
                    "state": state,
                    "updated_at": _utcnow(),
                    "last_progress_message": progress_message,
                    "last_progress_percentage": progress_percentage,
                }
            ),
        )

    def set_state(
        self,
        *,
        context: InteractionContext,
        state: str,
        reason: str | None = None,
    ) -> None:
        self._bridge.mutation(
            "executionSessions:setState",
            _omit_none(
                {
                    "session_id": context.session_id,
                    "task_id": context.task_id,
                    "step_id": context.step_id,
                    "agent_name": context.agent_name,
                    "provider": context.provider,
                    "state": state,
                    "updated_at": _utcnow(),
                    "reason": reason,
                }
            ),
        )

    def report_progress(
        self,
        *,
        context: InteractionContext,
        message: str,
        percentage: int | None = None,
    ) -> None:
        now = _utcnow()
        self._bridge.mutation(
            "executionSessions:upsert",
            _omit_none(
                {
                    "session_id": context.session_id,
                    "task_id": context.task_id,
                    "step_id": context.step_id,
                    "agent_name": context.agent_name,
                    "provider": context.provider,
                    "state": "running",
                    "updated_at": now,
                    "last_progress_message": message,
                    "last_progress_percentage": percentage,
                }
            ),
        )
        self._bridge.mutation(
            "executionInteractions:append",
            _omit_none(
                {
                    "session_id": context.session_id,
                    "task_id": context.task_id,
                    "step_id": context.step_id,
                    "kind": "progress_reported",
                    "payload": {
                        "message": message,
                        "percentage": percentage,
                    },
                    "created_at": now,
                    "agent_name": context.agent_name,
                    "provider": context.provider,
                }
            ),
        )

    def post_message(
        self,
        *,
        context: InteractionContext,
        content: str,
        channel: str | None = None,
        chat_id: str | None = None,
        media: list[str] | None = None,
    ) -> None:
        now = _utcnow()
        self._bridge.mutation(
            "messages:create",
            _omit_none(
                {
                    "task_id": context.task_id,
                    "step_id": context.step_id,
                    "author_name": context.agent_name,
                    "author_type": "agent",
                    "content": content,
                    "message_type": "work",
                    "type": "comment",
                    "timestamp": now,
                    "file_attachments": (
                        [
                            {
                                "name": path.split("/")[-1],
                                "type": "application/octet-stream",
                                "size": 0,
                            }
                            for path in media
                        ]
                        if media
                        else None
                    ),
                }
            ),
        )
        self._bridge.mutation(
            "executionInteractions:append",
            _omit_none(
                {
                    "session_id": context.session_id,
                    "task_id": context.task_id,
                    "step_id": context.step_id,
                    "kind": "message_posted",
                    "payload": {
                        "content": content,
                        "channel": channel,
                        "chat_id": chat_id,
                        "media": media or [],
                    },
                    "created_at": now,
                    "agent_name": context.agent_name,
                    "provider": context.provider,
                }
            ),
        )

    def record_final_result(
        self,
        *,
        context: InteractionContext,
        content: str,
        source: str,
    ) -> None:
        now = _utcnow()
        self._bridge.mutation(
            "executionSessions:upsert",
            _omit_none(
                {
                    "session_id": context.session_id,
                    "task_id": context.task_id,
                    "step_id": context.step_id,
                    "agent_name": context.agent_name,
                    "provider": context.provider,
                    "state": "completed",
                    "updated_at": now,
                    "final_result": content,
                    "final_result_source": source,
                    "completed_at": now,
                }
            ),
        )
        self._bridge.mutation(
            "executionInteractions:append",
            _omit_none(
                {
                    "session_id": context.session_id,
                    "task_id": context.task_id,
                    "step_id": context.step_id,
                    "kind": "final_result_recorded",
                    "payload": {"content": content, "source": source},
                    "created_at": now,
                    "agent_name": context.agent_name,
                    "provider": context.provider,
                }
            ),
        )

    def ask_user(
        self,
        *,
        context: InteractionContext,
        question: str | None = None,
        options: list[str] | None = None,
        questions: list[dict[str, Any]] | None = None,
    ) -> str:
        now = _utcnow()
        question_id = str(uuid.uuid4())
        self._bridge.mutation(
            "executionQuestions:create",
            _omit_none(
                {
                    "question_id": question_id,
                    "session_id": context.session_id,
                    "task_id": context.task_id,
                    "step_id": context.step_id,
                    "agent_name": context.agent_name,
                    "provider": context.provider,
                    "question": question,
                    "options": options,
                    "questions": questions,
                    "created_at": now,
                }
            ),
        )
        prompt = _build_prompt(
            context.agent_name, question=question, options=options, questions=questions
        )
        self._bridge.mutation(
            "messages:create",
            _omit_none(
                {
                    "task_id": context.task_id,
                    "step_id": context.step_id,
                    "author_name": context.agent_name,
                    "author_type": "agent",
                    "content": prompt,
                    "message_type": "work",
                    "timestamp": now,
                }
            ),
        )
        try:
            self._bridge.mutation(
                "tasks:updateStatus",
                {
                    "task_id": context.task_id,
                    "status": "review",
                    "agent_name": context.agent_name,
                    "awaiting_kickoff": False,
                },
            )
        except Exception as exc:
            if not _is_same_status_error(exc, "review"):
                raise
        if context.step_id:
            try:
                self._bridge.mutation(
                    "steps:updateStatus",
                    {
                        "step_id": context.step_id,
                        "status": "review",
                    },
                )
            except Exception as exc:
                if not _is_same_status_error(exc, "review"):
                    raise
        return self.wait_for_answer(question_id=question_id, context=context)

    def wait_for_answer(
        self,
        *,
        question_id: str,
        context: InteractionContext,
        poll_interval_seconds: float = 1.0,
    ) -> str:
        while True:
            question = self._bridge.query(
                "executionQuestions:getByQuestionId",
                {"question_id": question_id},
            )
            if question and question.get("status") == "answered":
                answer = str(question.get("answer") or "")
                self._bridge.mutation(
                    "executionSessions:setState",
                    {
                        "session_id": context.session_id,
                        "task_id": context.task_id,
                        "step_id": context.step_id,
                        "agent_name": context.agent_name,
                        "provider": context.provider,
                        "state": "running",
                        "updated_at": _utcnow(),
                        "reason": "user_answer_received",
                    },
                )
                try:
                    self._bridge.mutation(
                        "tasks:updateStatus",
                        {
                            "task_id": context.task_id,
                            "status": "in_progress",
                            "agent_name": context.agent_name,
                            "awaiting_kickoff": False,
                        },
                    )
                except Exception as exc:
                    if not _is_same_status_error(exc, "in_progress"):
                        raise
                if context.step_id:
                    try:
                        self._bridge.mutation(
                            "steps:updateStatus",
                            {
                                "step_id": context.step_id,
                                "status": "running",
                            },
                        )
                    except Exception as exc:
                        if not _is_same_status_error(exc, "running"):
                            raise
                return answer
            time.sleep(poll_interval_seconds)

    def has_pending_question(self, *, task_id: str) -> bool:
        return bool(
            self._bridge.query(
                "executionQuestions:hasPendingForTask",
                {"task_id": task_id},
            )
        )


def has_pending_execution_question(bridge: BridgeLike, task_id: str) -> bool:
    try:
        return bool(
            bridge.query(
                "executionQuestions:hasPendingForTask",
                {"task_id": task_id},
            )
        )
    except Exception:
        return False


def _build_prompt(
    agent_name: str,
    *,
    question: str | None,
    options: list[str] | None,
    questions: list[dict[str, Any]] | None,
) -> str:
    if questions:
        blocks = [f"**{agent_name} is asking:**\n", "### Questionnaire"]
        blocks.append(
            "Reply with one message. You may answer using the option labels/numbers or free text."
        )
        for index, item in enumerate(questions[:3], start=1):
            header = str(item.get("header") or f"Question {index}").strip()
            identifier = str(item.get("id") or f"question_{index}").strip()
            prompt = str(item.get("question") or "").strip()
            blocks.append(f"\n**{index}. {header}** (`{identifier}`)\n{prompt}")
            option_lines: list[str] = []
            for opt_index, option in enumerate((item.get("options") or [])[:3], start=1):
                label = str(option.get("label") or "").strip()
                description = str(option.get("description") or "").strip()
                if description:
                    option_lines.append(f"  {opt_index}. {label} — {description}")
                else:
                    option_lines.append(f"  {opt_index}. {label}")
            option_lines.append("  4. Other — reply with your own text.")
            blocks.append("Options:\n" + "\n".join(option_lines))
        return "\n".join(blocks)

    if not question or not question.strip():
        raise ValueError("ask_user requires either 'question' or 'questions'")

    content_parts = [f"**{agent_name} is asking:**\n\n{question.strip()}"]
    if options:
        opts_str = "\n".join(f"  {i + 1}. {option}" for i, option in enumerate(options[:3]))
        content_parts.append(f"\nOptions:\n{opts_str}\n  4. Other — reply with your own text.")
    return "\n".join(content_parts)
