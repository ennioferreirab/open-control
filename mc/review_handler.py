"""Review lifecycle handler — feedback, approval, and review routing.

Implements FR27 (review transitions), FR28 (review feedback),
FR29 (agent revision), and FR30 (review approval).

Extracted from mc.orchestrator to separate routing from review concerns.
"""

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
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)


class ReviewHandler:
    """Handles review lifecycle: transitions, feedback, revision, and approval."""

    def __init__(
        self,
        bridge: ConvexBridge,
        ask_user_registry: Any | None = None,
    ) -> None:
        self._bridge = bridge
        self._ask_user_registry = ask_user_registry
        self._known_review_task_ids: set[str] = set()

    async def _handle_review_transition(
        self, task_id: str, task: dict[str, Any]
    ) -> None:
        """Handle a task entering review state (FR27)."""
        title = task.get("title", "Untitled")
        logger.info(
            "[orchestrator] _handle_review_transition called for task '%s' (%s) — "
            "awaiting_kickoff=%s, supervision_mode=%s, trust_level=%s",
            title,
            task_id,
            task.get("awaiting_kickoff"),
            task.get("supervision_mode"),
            task.get("trust_level"),
        )

        # Skip tasks awaiting kick-off — those are supervised plan-review tasks
        # managed by the PreKickoffModal + kickoff_watch_loop, not work reviews.
        if task.get("awaiting_kickoff"):
            logger.info(
                "[orchestrator] Task '%s' is awaiting kick-off; skipping review routing.",
                title,
            )
            return

        # Skip tasks with a pending ask_user — the review state was set by the
        # ask_user handler to surface the question in the UI. Do NOT auto-complete.
        if self._ask_user_registry is not None and self._ask_user_registry.has_pending_ask(task_id):
            logger.info(
                "[orchestrator] Task '%s' has a pending ask_user — skipping review routing.",
                title,
            )
            return

        # Skip tasks that were paused mid-execution (Story 7.4):
        # A paused task enters review WITHOUT awaiting_kickoff but WITH materialized steps.
        # Auto-completing such a task to "done" would discard all pending/running steps.
        steps = await asyncio.to_thread(self._bridge.get_steps_by_task, task_id)
        if steps:
            logger.info(
                "[orchestrator] Task '%s' entered review with %d materialized steps — "
                "treating as paused task; skipping auto-completion.",
                title,
                len(steps),
            )
            return

        reviewers: list[str] = task.get("reviewers") or []
        trust_level = task.get("trust_level", TrustLevel.AUTONOMOUS)
        title = task.get("title", "Untitled")

        if not reviewers and trust_level == TrustLevel.AUTONOMOUS:
            logger.info(
                "[orchestrator] Task '%s' is autonomous with no reviewers — "
                "auto-completing to done.",
                title,
            )
            await asyncio.to_thread(
                self._bridge.update_task_status,
                task_id,
                TaskStatus.DONE,
            )
            return

        if reviewers:
            reviewer_names = ", ".join(reviewers)
            logger.info(
                "[orchestrator] Routing review for task '%s' to: %s",
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
            logger.info(
                "[orchestrator] Human approval requested for task '%s'.",
                title,
            )
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
        """Send a task-scoped message on behalf of an agent (FR26)."""
        logger.info(
            "[orchestrator] Agent '%s' sending message on task %s",
            agent_name,
            task_id,
        )
        result = await asyncio.to_thread(
            self._bridge.send_message,
            task_id,
            agent_name,
            AuthorType.AGENT,
            content,
            message_type,
        )
        return result

    async def handle_review_feedback(
        self, task_id: str, reviewer_name: str, feedback: str
    ) -> None:
        """Handle reviewer feedback on a task (FR28)."""
        logger.info(
            "[orchestrator] Reviewer '%s' providing feedback on task %s",
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
        task = await asyncio.to_thread(
            self._bridge.query, "tasks:getById", {"task_id": task_id}
        )
        title = task.get("title", "Untitled") if task else "Untitled"
        await asyncio.to_thread(
            self._bridge.create_activity,
            ActivityEventType.REVIEW_FEEDBACK,
            f"{reviewer_name} provided feedback on '{title}'",
            task_id,
            reviewer_name,
        )

    async def handle_agent_revision(
        self, task_id: str, agent_name: str, content: str
    ) -> None:
        """Handle an agent's revision in response to review feedback (FR29)."""
        logger.info(
            "[orchestrator] Agent '%s' submitting revision on task %s",
            agent_name,
            task_id,
        )
        await asyncio.to_thread(
            self._bridge.send_message,
            task_id,
            agent_name,
            AuthorType.AGENT,
            content,
            MessageType.WORK,
        )

    async def handle_review_approval(
        self, task_id: str, reviewer_name: str
    ) -> None:
        """Handle reviewer approval of a task (FR30)."""
        logger.info(
            "[orchestrator] Reviewer '%s' approving task %s",
            reviewer_name,
            task_id,
        )
        await asyncio.to_thread(
            self._bridge.send_message,
            task_id,
            reviewer_name,
            AuthorType.AGENT,
            f"Approved by {reviewer_name}",
            MessageType.APPROVAL,
        )
        task = await asyncio.to_thread(
            self._bridge.query, "tasks:getById", {"task_id": task_id}
        )
        title = task.get("title", "Untitled") if task else "Untitled"
        trust_level = (
            task.get("trust_level", TrustLevel.AUTONOMOUS)
            if task
            else TrustLevel.AUTONOMOUS
        )

        await asyncio.to_thread(
            self._bridge.create_activity,
            ActivityEventType.REVIEW_APPROVED,
            f"{reviewer_name} approved '{title}'",
            task_id,
            reviewer_name,
        )

        if trust_level == TrustLevel.HUMAN_APPROVED:
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
