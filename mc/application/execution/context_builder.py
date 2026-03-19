"""Unified context builder -- orchestrates the full context assembly pipeline.

This is the single entry point for building execution context for both
tasks and steps. It replaces the duplicated context building logic in
executor.py and step_dispatcher.py.

Pipeline stages:
1. Load agent config from YAML
2. Sync from Convex (source of truth for prompt, model, skills, variables)
3. Resolve tiers
4. Fetch fresh task data + build file manifest
5. Build thread context
6. Build tag attributes context
7. Inject orientation
8. Resolve board workspace
9. Assemble final prompt

This module does NOT change the runner -- it only prepares context.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mc.application.execution.file_enricher import (
    build_file_context,
    build_file_manifest,
    build_merged_source_context,
    load_merged_source_payloads,
    resolve_task_dirs,
)
from mc.application.execution.request import EntityType, ExecutionRequest
from mc.application.execution.roster_builder import (
    build_agent_roster,
    inject_orientation,
    load_agent_config,
    load_agent_data,
    resolve_tier,
    sync_agent_from_convex,
)
from mc.application.execution.thread_context_builder import build_thread_context
from mc.application.execution.thread_journal_service import ThreadJournalService
from mc.types import (
    NANOBOT_AGENT_NAME,
    extract_cc_model_name,
    is_cc_model,
    is_lead_agent,
)

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)


def _is_review_feedback_message(message: dict[str, Any]) -> bool:
    content = str(message.get("content") or "").strip()
    author_name = str(message.get("author_name") or "").lower()
    message_type = str(message.get("message_type") or message.get("type") or "").lower()
    return bool(
        content
        and (
            message_type == "review_feedback"
            or content.lower().startswith("rejected:")
            or "reviewer" in author_name
        )
    )


def build_review_feedback_context(messages: list[dict[str, Any]], step_id: str) -> str:
    """Build an explicit rerun block for the latest rejected attempt and reviewer feedback."""
    latest_attempt_output: str | None = None
    latest_review_feedback: str | None = None

    for message in reversed(messages):
        if latest_attempt_output is None and (
            message.get("step_id") == step_id and message.get("type") == "step_completion"
        ):
            latest_attempt_output = str(message.get("content") or "").strip() or None

        if latest_review_feedback is None and _is_review_feedback_message(message):
            latest_review_feedback = str(message.get("content") or "").strip() or None

        if latest_attempt_output and latest_review_feedback:
            break

    if not latest_attempt_output and not latest_review_feedback:
        return ""

    lines = ["[Previous Review Feedback]"]
    if latest_attempt_output:
        lines.extend(
            [
                "Latest rejected attempt output:",
                latest_attempt_output,
            ]
        )
    if latest_review_feedback:
        if latest_attempt_output:
            lines.append("")
        lines.extend(
            [
                "Latest reviewer feedback:",
                latest_review_feedback,
            ]
        )

    return "\n".join(lines)


def build_review_output_contract_context(
    step: dict[str, Any],
    all_task_steps: list[dict[str, Any]] | None = None,
) -> str:
    """Build the explicit JSON-only output contract for workflow review steps."""
    if str(step.get("workflow_step_type") or "").lower() != "review":
        return ""

    review_spec_id = step.get("review_spec_id") or step.get("reviewSpecId")
    on_reject_step_id = step.get("on_reject_step_id") or step.get("onRejectStepId")

    # Build step catalog for the reviewer (preceding steps only)
    current_step_id = str(step.get("id") or "")
    preceding_steps: list[dict[str, Any]] = []
    if all_task_steps:
        for s in all_task_steps:
            sid = str(s.get("id", ""))
            if sid and sid != current_step_id:
                preceding_steps.append(s)

    # Build recommendedReturnStep guidance with step key:title format
    if on_reject_step_id and preceding_steps:
        # Find the matching step to show key:title
        for s in preceding_steps:
            if s.get("workflow_step_id") == on_reject_step_id:
                recommended_return = (
                    f'"{on_reject_step_id}:{s.get("title", on_reject_step_id)}" | null'
                )
                break
        else:
            recommended_return = f'"{on_reject_step_id}" | null'
    elif on_reject_step_id:
        recommended_return = f'"{on_reject_step_id}" | null'
    else:
        recommended_return = "null"

    lines = [
        "[Review Output Contract — STRICT]",
        "This is a workflow review step.",
        "Evaluate the deliverable against the review criteria available in the task context.",
        "",
        "CRITICAL OUTPUT RULE:",
        "Your ENTIRE final response must be a single raw JSON object — nothing else.",
        "No explanation, no commentary, no markdown fences, no text before or after the JSON.",
        "Do not write files. Do not use tools. Just output the JSON.",
        "",
    ]

    # List available steps for rejection routing
    if preceding_steps:
        lines.append("Available steps for rejection routing (use step_key:Title format):")
        for s in preceding_steps:
            key = s.get("workflow_step_id", "?")
            title = s.get("title", key)
            status = s.get("status", "?")
            lines.append(f"  - {key}:{title} (status: {status})")
        lines.append("")

    if review_spec_id:
        lines.append(f"reviewSpecId: {review_spec_id}")
    lines.extend(
        [
            "Required JSON shape:",
            "{",
            '  "verdict": "approved" | "rejected",',
            '  "issues": ["..."],',
            '  "strengths": ["..."],',
            '  "scores": { "criterion": number },',
            '  "vetoesTriggered": ["..."],',
            f'  "recommendedReturnStep": {recommended_return}',
            "}",
            "",
            "If the work passes, set verdict to approved and recommendedReturnStep to null.",
            'If rejected, set recommendedReturnStep using "step_key:Step Title" format from the list above.',
            "",
            "REMINDER: Output ONLY the JSON object. Any text outside the JSON will cause a system error.",
        ]
    )
    return "\n".join(lines)


def build_tag_attributes_context(
    tags: list[str],
    attr_values: list[dict[str, Any]],
    attr_catalog: list[dict[str, Any]],
) -> str:
    """Build a context section describing tag attribute values for the agent.

    Args:
        tags: List of tag name strings assigned to the task.
        attr_values: List of tagAttributeValue records (snake_case keys from bridge).
        attr_catalog: List of tagAttribute records (snake_case keys from bridge).

    Returns:
        A formatted string section like:
        [Task Tag Attributes]
        client-tag: priority=high, deadline=2026-03-01
        ...
        Returns empty string if no tags have non-empty attribute values.
    """
    if not tags or not attr_values or not attr_catalog:
        return ""

    # Build attribute id -> name lookup
    attr_name_map: dict[str, str] = {}
    for attr in attr_catalog:
        attr_id = attr.get("id") or attr.get("_id") or ""
        attr_name = attr.get("name", "")
        if attr_id and attr_name:
            attr_name_map[attr_id] = attr_name

    # Group values by tag name
    tag_attrs: dict[str, list[str]] = {}
    for val in attr_values:
        tag_name = val.get("tag_name", "")
        value = val.get("value", "")
        attr_id = val.get("attribute_id") or val.get("_attribute_id") or ""

        if not tag_name or not value or tag_name not in tags:
            continue

        attr_name = attr_name_map.get(attr_id, "")
        if not attr_name:
            continue

        if tag_name not in tag_attrs:
            tag_attrs[tag_name] = []
        tag_attrs[tag_name].append(f"{attr_name}={value}")

    if not tag_attrs:
        return ""

    lines = ["[Task Tag Attributes]"]
    for tag_name in tags:
        if tag_name in tag_attrs:
            pairs = ", ".join(tag_attrs[tag_name])
            lines.append(f"{tag_name}: {pairs}")

    return "\n".join(lines)


class ContextBuilder:
    """Orchestrates the full context assembly pipeline.

    Builds an ExecutionRequest by running all enrichment stages in order.
    Both TaskExecutor and StepDispatcher delegate to this class.
    """

    def __init__(self, bridge: ConvexBridge) -> None:
        self._bridge = bridge
        self._tier_resolver: Any | None = None

    def _get_tier_resolver(self) -> Any:
        """Lazily create and return a TierResolver instance."""
        if self._tier_resolver is None:
            from mc.infrastructure.providers.tier_resolver import TierResolver

            self._tier_resolver = TierResolver(self._bridge)
        return self._tier_resolver

    async def build_task_context(
        self,
        task_id: str,
        title: str,
        description: str | None,
        agent_name: str,
        trust_level: str = "autonomous",
        task_data: dict[str, Any] | None = None,
    ) -> ExecutionRequest:
        """Build execution context for a task.

        Runs the full pipeline: agent config, file manifest, thread context,
        tag attributes, orientation, board workspace.

        Args:
            task_id: Convex task ID.
            title: Task title.
            description: Task description.
            agent_name: Assigned agent name.
            trust_level: Trust level for the task.
            task_data: Raw task data dict from Convex.

        Returns:
            Populated ExecutionRequest ready for execution.
        """
        req = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id=task_id,
            task_id=task_id,
            title=title,
            description=description,
            agent_name=agent_name,
            trust_level=trust_level,
            task_data=task_data or {},
        )

        # 1. Load agent config from YAML
        agent_prompt, agent_model, agent_skills = load_agent_config(agent_name)
        logger.info(
            "[context] YAML config for '%s': prompt_len=%d, model=%s, skills=%s",
            agent_name,
            len(agent_prompt) if agent_prompt else 0,
            agent_model,
            agent_skills,
        )

        # 2. Sync from Convex (source of truth)
        convex_agent = await self._fetch_convex_agent(agent_name)
        agent_prompt, agent_model, agent_skills = sync_agent_from_convex(
            agent_name,
            agent_prompt,
            agent_model,
            agent_skills,
            convex_agent,
        )

        # 3. Resolve tiers
        reasoning_level: str | None = None
        try:
            agent_model, reasoning_level = resolve_tier(agent_model, self._get_tier_resolver())
        except ValueError as exc:
            logger.error("[context] Tier resolution failed for '%s': %s", agent_name, exc)
            raise

        # 4. Check for CC model
        if agent_model and is_cc_model(agent_model):
            req.is_cc = True
            req.model = extract_cc_model_name(agent_model)
        else:
            req.model = agent_model

        # 5. Fetch fresh task data + build file manifest
        files_dir, output_dir = resolve_task_dirs(task_id)
        req.files_dir = files_dir
        req.output_dir = output_dir

        fresh_task: dict[str, Any] | None = None
        try:
            fresh_task = await asyncio.to_thread(
                self._bridge.query, "tasks:getById", {"task_id": task_id}
            )
            raw_files = (fresh_task or {}).get("files") or []
        except Exception:
            logger.warning(
                "[context] Failed to fetch fresh task for '%s', using snapshot",
                title,
            )
            raw_files = (task_data or {}).get("files") or []

        req.files = raw_files
        req.file_manifest = build_file_manifest(raw_files)

        board_source = fresh_task if isinstance(fresh_task, dict) else (task_data or {})
        board_id = board_source.get("board_id")
        if board_id:
            board_name, memory_workspace, memory_mode = await self._resolve_board(
                board_id, agent_name
            )
            req.board_name = board_name
            req.memory_workspace = memory_workspace
            req.memory_mode = memory_mode
        elif agent_name != NANOBOT_AGENT_NAME:
            raise RuntimeError(
                f"Task '{title}' has no board_id — non-nanobot agent '{agent_name}' "
                "requires a board-scoped workspace. Assign a board to the task."
            )

        memory_dir = str(req.memory_workspace / "memory") if req.memory_workspace else None
        artifacts_dir = None
        if req.board_name:
            from mc.artifacts import resolve_board_artifacts_workspace

            artifacts_dir = str(resolve_board_artifacts_workspace(req.board_name))

        # Build file context and append to description
        file_context = build_file_context(
            req.file_manifest,
            files_dir,
            output_dir,
            memory_dir=memory_dir,
            artifacts_dir=artifacts_dir,
        )
        req.description = (req.description or "") + f"\n\n{file_context}"

        # 6. Inject merged source context before the live thread when task C
        # inherits A/B histories.
        try:
            merged_source_payloads = await load_merged_source_payloads(
                self._bridge,
                fresh_task if isinstance(fresh_task, dict) else task_data,
            )
            merged_source_context = build_merged_source_context(merged_source_payloads)
            if merged_source_context:
                req.description = (req.description or "") + f"\n\n{merged_source_context}"
        except Exception:
            logger.warning("[context] Merged source context failed for '%s'", title, exc_info=True)

        # 7. Build thread context
        try:
            thread_messages = await asyncio.to_thread(self._bridge.get_task_messages, task_id)
            req.thread_messages = thread_messages
            journal_service = ThreadJournalService(bridge=self._bridge)
            journal_snapshot = journal_service.sync_task_thread(
                task_id=task_id,
                task_title=title,
                task_data=fresh_task if isinstance(fresh_task, dict) else (task_data or {}),
                messages=thread_messages,
            )
            req.thread_journal_path = journal_snapshot.journal_path
            req.compacted_thread_summary = journal_snapshot.state.compacted_summary
            thread_context = build_thread_context(
                thread_messages,
                compacted_summary=journal_snapshot.state.compacted_summary,
                thread_journal_path=journal_snapshot.journal_path,
                recent_window_messages=journal_snapshot.state.recent_window_messages,
            )
            if thread_context:
                req.thread_context = thread_context
                req.description = (req.description or "") + f"\n{thread_context}"
                logger.info(
                    "[context] Thread context injected for task '%s' (%d messages)",
                    title,
                    len(thread_messages),
                )
            journal_service.schedule_background_compaction(
                task_id=task_id,
                task_title=title,
                task_data=fresh_task if isinstance(fresh_task, dict) else (task_data or {}),
                messages=thread_messages,
            )
        except Exception:
            logger.warning(
                "[context] Thread context failed for '%s'",
                title,
                exc_info=True,
            )

        # 8. Build tag attributes context
        try:
            task_tags = (task_data or {}).get("tags") or []
            if task_tags:
                req.tags = task_tags
                tag_attrs_context = await self._build_tag_attrs(task_id, task_tags)
                if tag_attrs_context:
                    req.tag_attributes = tag_attrs_context
                    req.description = (req.description or "") + f"\n\n{tag_attrs_context}"
                    logger.info(
                        "[context] Tag attributes injected for task '%s'",
                        title,
                    )
        except Exception:
            logger.warning(
                "[context] Tag attributes failed for '%s'",
                title,
                exc_info=True,
            )

        # 9. Inject orientation
        agent_prompt = inject_orientation(agent_name, agent_prompt, bridge=self._bridge)

        # System agents (nanobot) use SOUL.md -- skip prompt injection
        if agent_name == NANOBOT_AGENT_NAME:
            agent_prompt = None

        # Inject agent roster for lead-agent context
        if is_lead_agent(agent_name):
            roster = build_agent_roster()
            if roster:
                req.description = (req.description or "") + f"\n\n{roster}"

        # Populate final fields
        req.agent_prompt = agent_prompt
        req.agent_model = agent_model
        req.agent_skills = agent_skills
        req.reasoning_level = reasoning_level

        # Load full AgentData if needed (for CC routing)
        if req.is_cc:
            req.agent = load_agent_data(agent_name)

        # Assemble the canonical prompt for the CLI bootstrap.
        # agent_prompt carries the system persona/instructions; description carries the
        # enriched operational context. prompt = both combined so the agent starts with
        # full context and role awareness.
        description_or_title = req.description or req.title
        if agent_prompt:
            req.prompt = f"{agent_prompt}\n\n---\n\n{description_or_title}"
        else:
            req.prompt = description_or_title

        return req

    async def build_step_context(
        self,
        task_id: str,
        step: dict[str, Any],
    ) -> ExecutionRequest:
        """Build execution context for a step.

        Runs the pipeline with step-specific enrichments: predecessor
        context, step-level file routing, step execution description.

        Args:
            task_id: Parent task ID.
            step: Step data dict from Convex.

        Returns:
            Populated ExecutionRequest ready for execution.
        """
        step_id = step.get("id", "")
        step_title = (step.get("title") or "Untitled Step").strip()
        step_description = step.get("description") or ""
        agent_name = (step.get("assigned_agent") or NANOBOT_AGENT_NAME).strip()

        if is_lead_agent(agent_name):
            logger.warning(
                "[context] Step '%s' assigned to lead-agent; rerouting to '%s'",
                step_title,
                NANOBOT_AGENT_NAME,
            )
            agent_name = NANOBOT_AGENT_NAME

        req = ExecutionRequest(
            entity_type=EntityType.STEP,
            entity_id=step_id,
            task_id=task_id,
            step_id=step_id,
            step_title=step_title,
            step_description=step_description,
            agent_name=agent_name,
            blocked_by=[str(pid) for pid in (step.get("blocked_by") or []) if pid],
        )
        req.predecessor_step_ids = req.blocked_by

        # 1. Load agent config from YAML
        agent_prompt, agent_model, agent_skills = load_agent_config(agent_name)
        logger.info(
            "[context] YAML config for step agent '%s': prompt_len=%d, model=%s",
            agent_name,
            len(agent_prompt) if agent_prompt else 0,
            agent_model,
        )

        # 2. Sync from Convex
        convex_agent = await self._fetch_convex_agent(agent_name)
        agent_prompt, agent_model, agent_skills = sync_agent_from_convex(
            agent_name,
            agent_prompt,
            agent_model,
            agent_skills,
            convex_agent,
        )

        # 3. Resolve tiers
        reasoning_level: str | None = None
        try:
            agent_model, reasoning_level = resolve_tier(agent_model, self._get_tier_resolver())
        except ValueError:
            raise

        # 4. Check for CC model
        if agent_model and is_cc_model(agent_model):
            req.is_cc = True
            req.model = extract_cc_model_name(agent_model)
        else:
            req.model = agent_model

        # 5. Inject orientation
        agent_prompt = inject_orientation(agent_name, agent_prompt, bridge=self._bridge)
        if agent_name == NANOBOT_AGENT_NAME:
            agent_prompt = None

        # 6. Fetch task data + build file context
        task_data = await asyncio.to_thread(
            self._bridge.query, "tasks:getById", {"task_id": task_id}
        )
        task_data = task_data if isinstance(task_data, dict) else {}
        req.task_data = task_data
        task_title = task_data.get("title", "Untitled Task")
        req.title = task_title

        board_id = task_data.get("board_id")
        if board_id:
            board_name, memory_workspace, memory_mode = await self._resolve_board(
                board_id, agent_name
            )
            req.board_name = board_name
            req.memory_workspace = memory_workspace
            req.memory_mode = memory_mode
        elif agent_name != NANOBOT_AGENT_NAME:
            raise RuntimeError(
                f"Task '{task_title}' has no board_id — non-nanobot agent '{agent_name}' "
                "requires a board-scoped workspace. Assign a board to the task."
            )

        raw_files = task_data.get("files") or []
        req.files = raw_files
        files_dir, output_dir = resolve_task_dirs(task_id)
        req.files_dir = files_dir
        req.output_dir = output_dir
        req.file_manifest = build_file_manifest(raw_files)
        memory_dir = str(req.memory_workspace / "memory") if req.memory_workspace else None
        artifacts_dir = None
        if req.board_name:
            from mc.artifacts import resolve_board_artifacts_workspace

            artifacts_dir = str(resolve_board_artifacts_workspace(req.board_name))

        # Build step-specific file context (execution description)
        file_context = build_file_context(
            req.file_manifest,
            files_dir,
            output_dir,
            memory_dir=memory_dir,
            artifacts_dir=artifacts_dir,
            is_step=True,
            step_title=step_title,
            step_description=step_description,
            task_title=task_title,
            raw_files=raw_files,
        )

        # 7. Build thread context with predecessor awareness
        thread_messages = await asyncio.to_thread(self._bridge.get_task_messages, task_id)
        req.thread_messages = thread_messages
        journal_service = ThreadJournalService(bridge=self._bridge)
        journal_snapshot = journal_service.sync_task_thread(
            task_id=task_id,
            task_title=task_title,
            task_data=task_data,
            messages=thread_messages,
        )
        req.thread_journal_path = journal_snapshot.journal_path
        req.compacted_thread_summary = journal_snapshot.state.compacted_summary
        thread_context = build_thread_context(
            thread_messages,
            predecessor_step_ids=req.predecessor_step_ids,
            compacted_summary=journal_snapshot.state.compacted_summary,
            thread_journal_path=journal_snapshot.journal_path,
            recent_window_messages=journal_snapshot.state.recent_window_messages,
        )
        req.thread_context = thread_context
        journal_service.schedule_background_compaction(
            task_id=task_id,
            task_title=task_title,
            task_data=task_data,
            messages=thread_messages,
        )

        review_feedback_context = build_review_feedback_context(thread_messages, step_id)
        all_task_steps = await asyncio.to_thread(self._bridge.get_steps_by_task, task_id)
        review_output_contract_context = build_review_output_contract_context(
            step, all_task_steps=all_task_steps
        )

        # Assemble the execution description
        execution_description = file_context
        if review_feedback_context:
            execution_description += f"\n\n{review_feedback_context}"
        if review_output_contract_context:
            execution_description += f"\n\n{review_output_contract_context}"
        if thread_context:
            execution_description += f"\n{thread_context}"
        req.description = execution_description

        # Populate final fields
        req.agent_prompt = agent_prompt
        req.agent_model = agent_model
        req.agent_skills = agent_skills
        req.reasoning_level = reasoning_level

        # Load full AgentData if needed (for CC routing)
        if req.is_cc:
            req.agent = load_agent_data(agent_name)

        # Assemble the canonical prompt for the CLI bootstrap.
        # agent_prompt carries the system persona/instructions; description carries the
        # enriched operational context (file paths, thread history, etc.).
        # prompt = both combined so the agent starts with full context and role awareness.
        description_or_title = req.description or f"{req.step_title}: {req.step_description}"
        if agent_prompt:
            req.prompt = f"{agent_prompt}\n\n---\n\n{description_or_title}"
        else:
            req.prompt = description_or_title

        return req

    async def _fetch_convex_agent(self, agent_name: str) -> dict[str, Any] | None:
        """Fetch agent data from Convex (best-effort)."""
        try:
            return await asyncio.to_thread(self._bridge.get_agent_by_name, agent_name)
        except Exception:
            logger.warning(
                "[context] Could not fetch Convex agent for '%s', using YAML",
                agent_name,
                exc_info=True,
            )
            return None

    async def _build_tag_attrs(self, task_id: str, task_tags: list[str]) -> str:
        """Build tag attributes context string."""
        tag_attr_values = await asyncio.to_thread(
            self._bridge.query,
            "tagAttributeValues:getByTask",
            {"task_id": task_id},
        )
        tag_attr_catalog = await asyncio.to_thread(
            self._bridge.query,
            "tagAttributes:list",
            {},
        )
        return build_tag_attributes_context(
            task_tags,
            tag_attr_values if isinstance(tag_attr_values, list) else [],
            tag_attr_catalog if isinstance(tag_attr_catalog, list) else [],
        )

    async def _resolve_board(
        self, board_id: str, agent_name: str
    ) -> tuple[str | None, Path | None, str | None]:
        """Resolve board-scoped workspace for an agent."""
        try:
            board = await asyncio.to_thread(self._bridge.get_board_by_id, board_id)
            if board:
                board_name = board.get("name")
                if board_name:
                    from mc.infrastructure.boards import (
                        get_agent_memory_mode,
                        resolve_memory_workspace,
                    )

                    mode = get_agent_memory_mode(board, agent_name)
                    resolved = resolve_memory_workspace(
                        agent_name,
                        board_name=board_name,
                        mode=mode,
                    )
                    logger.info(
                        "[context] Board workspace for '%s' on '%s' (mode=%s, scope=%s)",
                        agent_name,
                        board_name,
                        mode,
                        resolved.effective_memory_scope,
                    )
                    return board_name, resolved.workspace, mode
        except Exception:
            logger.warning(
                "[context] Failed to resolve board workspace for '%s'",
                agent_name,
                exc_info=True,
            )
        return None, None, None
