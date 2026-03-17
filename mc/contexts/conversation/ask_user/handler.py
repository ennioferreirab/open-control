"""Unified ask-user handler for all backends."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import TYPE_CHECKING

from mc.contexts.interactive.metrics import increment_interactive_metric
from mc.types import ActivityEventType

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)


def _transition_succeeded(result: object) -> bool:
    return isinstance(result, dict) and result.get("kind") in {"applied", "noop"}


async def _transition_task(
    bridge: "ConvexBridge",
    task_id: str,
    to_status: str,
    *,
    reason: str,
    awaiting_kickoff: bool | None = None,
    review_phase: str | None = None,
) -> object:
    snapshot = await asyncio.to_thread(bridge.get_task, task_id)
    if not isinstance(snapshot, dict):
        logger.warning(
            "ask_user: unable to load task snapshot for %s before %s", task_id, to_status
        )
        return None
    return await asyncio.to_thread(
        bridge.transition_task_from_snapshot,
        snapshot,
        to_status,
        reason=reason,
        awaiting_kickoff=awaiting_kickoff,
        review_phase=review_phase,
    )


class AskUserHandler:
    """Unified ask_user handler for all agent backends."""

    def __init__(self) -> None:
        self._pending_ask: dict[str, asyncio.Future[str]] = {}
        self._task_to_request: dict[str, str] = {}
        self._request_to_step: dict[str, str] = {}

    def has_pending_ask(self, task_id: str) -> bool:
        request_id = self._task_to_request.get(task_id)
        return request_id is not None and request_id in self._pending_ask

    def deliver_user_reply(self, task_id: str, answer: str) -> None:
        request_id = self._task_to_request.get(task_id)
        if request_id:
            future = self._pending_ask.get(request_id)
            if future and not future.done():
                future.set_result(answer)

    async def ask(
        self,
        *,
        question: str | None = None,
        options: list[str] | None = None,
        questions: list[dict] | None = None,
        agent_name: str,
        task_id: str,
        bridge: "ConvexBridge",
    ) -> str:
        """Post question to thread, wait for a reply, and restore task state."""
        content = self._build_prompt(
            agent_name, question=question, options=options, questions=questions
        )

        try:
            await asyncio.to_thread(
                bridge.send_message,
                task_id,
                agent_name,
                "agent",
                content,
                "work",
            )
        except Exception as exc:
            logger.warning("ask_user: failed to post question to thread: %s", exc)

        request_id = str(uuid.uuid4())
        future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        self._pending_ask[request_id] = future
        self._task_to_request[task_id] = request_id
        step_id = await asyncio.to_thread(self._resolve_active_step_id, bridge, task_id)
        if step_id is not None:
            self._request_to_step[request_id] = step_id

        try:
            result = await _transition_task(
                bridge,
                task_id,
                "review",
                reason=f"{agent_name} is waiting for user reply (ask_user)",
                awaiting_kickoff=False,
                review_phase="execution_pause",
            )
            if step_id is not None and _transition_succeeded(result):
                await asyncio.to_thread(bridge.update_step_status, step_id, "waiting_human")
            if _transition_succeeded(result):
                await asyncio.to_thread(
                    bridge.create_activity,
                    ActivityEventType.REVIEW_REQUESTED,
                    f"Interactive session paused for review for @{agent_name}.",
                    task_id,
                    agent_name,
                )
                increment_interactive_metric("interactive_ask_user_pause_total")
        except Exception as exc:
            logger.warning("ask_user: failed to set task to review: %s", exc)

        try:
            answer = await future
        finally:
            self._pending_ask.pop(request_id, None)
            self._task_to_request.pop(task_id, None)
            step_id = self._request_to_step.pop(request_id, None)

        try:
            result = await _transition_task(
                bridge,
                task_id,
                "in_progress",
                reason=f"{agent_name} received user reply, resuming",
            )
            if step_id is not None and _transition_succeeded(result):
                await asyncio.to_thread(bridge.update_step_status, step_id, "running")
            if _transition_succeeded(result):
                await asyncio.to_thread(
                    bridge.create_activity,
                    ActivityEventType.STEP_STARTED,
                    f"Interactive session resumed after user reply for @{agent_name}.",
                    task_id,
                    agent_name,
                )
                increment_interactive_metric("interactive_ask_user_resume_total")
        except Exception as exc:
            logger.warning("ask_user: failed to restore task to in_progress: %s", exc)

        return answer

    def _resolve_active_step_id(self, bridge: "ConvexBridge", task_id: str) -> str | None:
        try:
            steps = bridge.get_steps_by_task(task_id)
        except Exception as exc:
            logger.warning("ask_user: failed to resolve active step for %s: %s", task_id, exc)
            return None

        if not isinstance(steps, list):
            return None

        for candidate_status in ("waiting_human", "review", "running", "assigned"):
            for step in steps:
                if step.get("status") != candidate_status:
                    continue
                step_id = step.get("id") or step.get("_id")
                if isinstance(step_id, str) and step_id.strip():
                    return step_id
        return None

    def _build_prompt(
        self,
        agent_name: str,
        *,
        question: str | None,
        options: list[str] | None,
        questions: list[dict] | None,
    ) -> str:
        if questions:
            return self._build_questionnaire_prompt(agent_name, questions)
        if not question or not question.strip():
            raise ValueError("ask_user requires either 'question' or 'questions'")
        return self._build_single_prompt(agent_name, question=question, options=options)

    def _build_single_prompt(
        self,
        agent_name: str,
        *,
        question: str,
        options: list[str] | None,
    ) -> str:
        content_parts = [f"**{agent_name} is asking:**\n\n{question.strip()}"]
        if options:
            opts_str = "\n".join(f"  {i + 1}. {option}" for i, option in enumerate(options[:3]))
            content_parts.append(f"\nOptions:\n{opts_str}\n  4. Other — reply with your own text.")
        return "\n".join(content_parts)

    def _build_questionnaire_prompt(self, agent_name: str, questions: list[dict]) -> str:
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
