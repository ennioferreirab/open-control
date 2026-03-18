"""Review worker — handles review routing, completion detection, and post-review transitions."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from mc.bridge.runtime_claims import acquire_runtime_claim, task_snapshot_claim_kind
from mc.contexts.interaction.service import has_pending_execution_question
from mc.domain.workflow.review_result import ReviewResult, parse_review_result
from mc.types import (
    ActivityEventType,
    AuthorType,
    MessageType,
    ReviewPhase,
    TaskStatus,
    TrustLevel,
)

if TYPE_CHECKING:
    from mc.infrastructure.runtime_context import RuntimeContext

logger = logging.getLogger(__name__)


def _build_task_review_contract(task: dict[str, Any], reviewer_name: str) -> str:
    assigned_agent = task.get("assigned_agent") or "the assigned agent"
    title = task.get("title", "Untitled")
    lines = [
        "[Task Review Contract]",
        f"You are reviewing the completed work for task: {title}",
        f"The work under review was produced by: {assigned_agent}",
        f"You are the designated reviewer: {reviewer_name}",
        "Review the task thread, artifacts, and latest deliverable before deciding.",
        "Return ONLY a single JSON object in your final response.",
        "Do not wrap the JSON in markdown fences.",
        "Required JSON shape:",
        "{",
        '  "verdict": "approved" | "rejected",',
        '  "issues": ["..."],',
        '  "strengths": ["..."],',
        '  "scores": { "criterion": number },',
        '  "vetoesTriggered": ["..."],',
        '  "recommendedReturnStep": null',
        "}",
        "If the work passes, set verdict to approved.",
        "If the work fails, set verdict to rejected and include concrete, actionable issues.",
    ]
    return "\n".join(lines)


def _format_review_feedback(reviewer_name: str, review_result: ReviewResult) -> str:
    lines = [f"Rejected: {reviewer_name} requested changes."]
    if review_result.issues:
        lines.append("Issues:")
        lines.extend(f"- {issue}" for issue in review_result.issues)
    if review_result.strengths:
        lines.append("Strengths:")
        lines.extend(f"- {strength}" for strength in review_result.strengths)
    if review_result.vetoes_triggered:
        lines.append("Vetoes triggered:")
        lines.extend(f"- {veto}" for veto in review_result.vetoes_triggered)
    return "\n".join(lines)


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

    def _build_execution_engine(self) -> Any:
        from mc.application.execution.post_processing import build_execution_engine

        return build_execution_engine(
            bridge=self._bridge,
            ask_user_registry=self._ask_user_registry,
            provider_cli_registry=self._ctx.services.get("provider_cli_registry"),
            provider_cli_supervisor=self._ctx.services.get("provider_cli_supervisor"),
            provider_cli_projector=self._ctx.services.get("provider_cli_projector"),
            provider_cli_supervision_sink=self._ctx.services.get("provider_cli_supervision_sink"),
            provider_cli_control_plane=self._ctx.services.get("provider_cli_control_plane"),
        )

    async def _run_reviewer_agent(
        self,
        task_id: str,
        task: dict[str, Any],
        reviewer_name: str,
    ) -> ReviewResult:
        from mc.application.execution.context_builder import ContextBuilder

        ctx_builder = ContextBuilder(self._bridge)
        req = await ctx_builder.build_task_context(
            task_id=task_id,
            title=task.get("title", "Untitled"),
            description=task.get("description"),
            agent_name=reviewer_name,
            trust_level=task.get("trust_level", TrustLevel.AUTONOMOUS),
            task_data=task,
        )
        review_contract = _build_task_review_contract(task, reviewer_name)
        req.description = (
            f"{req.description}\n\n{review_contract}" if req.description else review_contract
        )
        if req.agent_prompt:
            req.prompt = f"{req.agent_prompt}\n\n---\n\n{req.description}"
        else:
            req.prompt = req.description
        req.session_boundary_reason = "task_review"
        logger.debug(
            "[review] Execution request built for reviewer '%s' on task %s (runner_type=%s, model=%s)",
            reviewer_name,
            task_id,
            req.runner_type.value,
            req.model,
        )

        engine = self._build_execution_engine()
        execution_result = await engine.run(req)
        if not execution_result.success:
            raise RuntimeError(execution_result.error_message or "Reviewer execution failed")
        return parse_review_result(execution_result.output)

    async def _record_non_terminal_approval(self, task_id: str, reviewer_name: str) -> None:
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
        await asyncio.to_thread(
            self._bridge.create_activity,
            ActivityEventType.REVIEW_APPROVED,
            f"{reviewer_name} approved '{title}'",
            task_id,
            reviewer_name,
        )

    async def process_batch(self, tasks: list[dict[str, Any]]) -> None:
        current_ids = {task.get("id") for task in tasks if task.get("id")}
        self._known_review_task_ids &= current_ids

        for task_data in tasks:
            task_id = task_data.get("id")
            if not task_id or task_id in self._known_review_task_ids:
                continue
            claimed = await asyncio.to_thread(
                acquire_runtime_claim,
                self._bridge,
                claim_kind=task_snapshot_claim_kind("review", task_data),
                entity_type="task",
                entity_id=task_id,
                metadata={"status": task_data.get("status", "review")},
            )
            if not claimed:
                logger.debug("[review] Claim denied for task %s", task_id)
                continue
            self._known_review_task_ids.add(task_id)
            await self.handle_review_transition(task_id, task_data)

    async def handle_review_transition(self, task_id: str, task: dict[str, Any]) -> None:
        title = task.get("title", "Untitled")
        review_phase = task.get("review_phase") or task.get("reviewPhase")
        logger.info(
            "[review] _handle_review_transition called for task '%s' (%s) -- awaiting_kickoff=%s, review_phase=%s, supervision_mode=%s, trust_level=%s",
            title,
            task_id,
            task.get("awaiting_kickoff"),
            review_phase,
            task.get("supervision_mode"),
            task.get("trust_level"),
        )

        if task.get("awaiting_kickoff") or review_phase == ReviewPhase.PLAN_REVIEW:
            logger.info(
                "[review] Task '%s' is awaiting kick-off; skipping review routing.",
                title,
            )
            return

        if (
            self._ask_user_registry is not None and self._ask_user_registry.has_pending_ask(task_id)
        ) or has_pending_execution_question(self._bridge, task_id):
            logger.info(
                "[review] Task '%s' has a pending ask_user -- skipping review routing.",
                title,
            )
            return

        steps = await asyncio.to_thread(self._bridge.get_steps_by_task, task_id)
        if steps and review_phase != ReviewPhase.FINAL_APPROVAL:
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
            for index, reviewer_name in enumerate(reviewers):
                try:
                    review_result = await self._run_reviewer_agent(task_id, task, reviewer_name)
                except Exception as exc:
                    error_message = (
                        f"Review by {reviewer_name} failed: {exc}. Task remains in review."
                    )
                    logger.exception(
                        "[review] Reviewer '%s' failed while reviewing task %s",
                        reviewer_name,
                        task_id,
                    )
                    await asyncio.to_thread(
                        self._bridge.post_system_error,
                        task_id,
                        error_message,
                    )
                    await asyncio.to_thread(
                        self._bridge.create_activity,
                        ActivityEventType.SYSTEM_ERROR,
                        error_message,
                        task_id,
                        reviewer_name,
                    )
                    return
                if review_result.verdict == "rejected":
                    await self.handle_review_feedback(
                        task_id,
                        reviewer_name,
                        _format_review_feedback(reviewer_name, review_result),
                    )
                    await asyncio.to_thread(
                        self._bridge.transition_task_from_snapshot,
                        task,
                        TaskStatus.ASSIGNED,
                        reason=f"Review rejected by {reviewer_name}; task returned for revision",
                        agent_name=task.get("assigned_agent"),
                    )
                    return
                if index < len(reviewers) - 1:
                    await self._record_non_terminal_approval(task_id, reviewer_name)
            await self.handle_review_approval(task_id, reviewers[-1])
            return

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
        trust_level = (
            task.get("trust_level", TrustLevel.AUTONOMOUS) if task else TrustLevel.AUTONOMOUS
        )

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
