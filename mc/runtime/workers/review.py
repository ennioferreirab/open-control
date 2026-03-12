"""Review worker — handles review routing, completion detection, and post-review transitions."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from mc.types import (
    ActivityEventType,
    AuthorType,
    MessageType,
    TaskStatus,
    TrustLevel,
)

if TYPE_CHECKING:
    from mc.infrastructure.runtime_context import RuntimeContext

logger = logging.getLogger(__name__)


class ReviewWorker:
    """Handles review lifecycle: transitions, feedback, revision, and approval."""

    def __init__(
        self,
        ctx: RuntimeContext,
        ask_user_registry: Any | None = None,
    ) -> None:
        self._ctx = ctx
        self._bridge = ctx.bridge
        self._ask_user_registry = ask_user_registry
        self._known_review_task_ids: set[str] = set()

    async def process_batch(self, tasks: list[dict[str, Any]]) -> None:
        current_ids = {task.get("id") for task in tasks if task.get("id")}
        self._known_review_task_ids &= current_ids

        for task_data in tasks:
            task_id = task_data.get("id")
            if not task_id or task_id in self._known_review_task_ids:
                continue
            self._known_review_task_ids.add(task_id)
            await self.handle_review_transition(task_id, task_data)

    async def handle_review_transition(self, task_id: str, task: dict[str, Any]) -> None:
        title = task.get("title", "Untitled")
        logger.info(
            "[review] _handle_review_transition called for task '%s' (%s) -- awaiting_kickoff=%s, supervision_mode=%s, trust_level=%s",
            title,
            task_id,
            task.get("awaiting_kickoff"),
            task.get("supervision_mode"),
            task.get("trust_level"),
        )

        if task.get("awaiting_kickoff"):
            logger.info(
                "[review] Task '%s' is awaiting kick-off; skipping review routing.",
                title,
            )
            return

        if self._ask_user_registry is not None and self._ask_user_registry.has_pending_ask(task_id):
            logger.info(
                "[review] Task '%s' has a pending ask_user -- skipping review routing.",
                title,
            )
            return

        steps = await asyncio.to_thread(self._bridge.get_steps_by_task, task_id)
        if steps:
            logger.info(
                "[review] Task '%s' entered review with %d materialized steps -- treating as paused task; skipping auto-completion.",
                title,
                len(steps),
            )
            return

        reviewers: list[str] = task.get("reviewers") or []
        trust_level = task.get("trust_level", TrustLevel.AUTONOMOUS)

        if not reviewers and trust_level == TrustLevel.AUTONOMOUS:
            logger.info(
                "[review] Task '%s' is autonomous with no reviewers -- awaiting explicit approval in review.",
                title,
            )
            return

        if reviewers:
            reviewer_names = ", ".join(reviewers)
            logger.info(
                "[review] Routing review for task '%s' to: %s",
                title,
                reviewer_names,
            )
            await asyncio.to_thread(
                self._bridge.send_message,
                task_id,
                "system",
                AuthorType.SYSTEM,
                f"Review requested. Awaiting review from: {reviewer_names}",
                MessageType.SYSTEM_EVENT,
            )
            await asyncio.to_thread(
                self._bridge.create_activity,
                ActivityEventType.REVIEW_REQUESTED,
                f"Review requested from {reviewer_names} for '{title}'",
                task_id,
            )

        if trust_level == TrustLevel.HUMAN_APPROVED and not reviewers:
            logger.info("[review] Human approval requested for task '%s'.", title)
            await asyncio.to_thread(
                self._bridge.create_activity,
                ActivityEventType.HITL_REQUESTED,
                f"Human approval requested for '{title}'",
                task_id,
            )

    async def send_agent_message(
        self,
        task_id: str,
        agent_name: str,
        content: str,
        message_type: str = MessageType.WORK,
    ) -> Any:
        logger.info("[review] Agent '%s' sending message on task %s", agent_name, task_id)
        return await asyncio.to_thread(
            self._bridge.send_message,
            task_id,
            agent_name,
            AuthorType.AGENT,
            content,
            message_type,
        )

    async def handle_review_feedback(self, task_id: str, reviewer_name: str, feedback: str) -> None:
        logger.info(
            "[review] Reviewer '%s' providing feedback on task %s",
            reviewer_name,
            task_id,
        )
        await asyncio.to_thread(
            self._bridge.send_message,
            task_id,
            reviewer_name,
            AuthorType.AGENT,
            feedback,
            MessageType.REVIEW_FEEDBACK,
        )
        task = await asyncio.to_thread(self._bridge.query, "tasks:getById", {"task_id": task_id})
        title = task.get("title", "Untitled") if task else "Untitled"
        await asyncio.to_thread(
            self._bridge.create_activity,
            ActivityEventType.REVIEW_FEEDBACK,
            f"{reviewer_name} provided feedback on '{title}'",
            task_id,
            reviewer_name,
        )

    async def handle_agent_revision(self, task_id: str, agent_name: str, content: str) -> None:
        logger.info("[review] Agent '%s' submitting revision on task %s", agent_name, task_id)
        await asyncio.to_thread(
            self._bridge.send_message,
            task_id,
            agent_name,
            AuthorType.AGENT,
            content,
            MessageType.WORK,
        )

    async def handle_review_approval(self, task_id: str, reviewer_name: str) -> None:
        logger.info("[review] Reviewer '%s' approving task %s", reviewer_name, task_id)
        await asyncio.to_thread(
            self._bridge.send_message,
            task_id,
            reviewer_name,
            AuthorType.AGENT,
            f"Approved by {reviewer_name}",
            MessageType.APPROVAL,
        )
        task = await asyncio.to_thread(self._bridge.query, "tasks:getById", {"task_id": task_id})
        title = task.get("title", "Untitled") if task else "Untitled"
        trust_level = task.get("trust_level", TrustLevel.AUTONOMOUS) if task else TrustLevel.AUTONOMOUS

        await asyncio.to_thread(
            self._bridge.create_activity,
            ActivityEventType.REVIEW_APPROVED,
            f"{reviewer_name} approved '{title}'",
            task_id,
            reviewer_name,
        )

        if trust_level == TrustLevel.AUTONOMOUS:
            await asyncio.to_thread(
                self._bridge.update_task_status,
                task_id,
                TaskStatus.DONE,
                reviewer_name,
            )
        elif trust_level == TrustLevel.HUMAN_APPROVED:
            await asyncio.to_thread(
                self._bridge.send_message,
                task_id,
                "system",
                AuthorType.SYSTEM,
                "Agent review passed. Awaiting human approval.",
                MessageType.SYSTEM_EVENT,
            )
            await asyncio.to_thread(
                self._bridge.create_activity,
                ActivityEventType.HITL_REQUESTED,
                f"Human approval requested for '{title}'",
                task_id,
            )
