"""Task-scoped thread journal reconciliation and rolling compaction."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from mc.application.execution.background_tasks import (
    create_background_task,
    create_deduplicated_background_task,
)
from mc.infrastructure.thread_journal_store import (
    ThreadCompactionState,
    ThreadJournalStore,
)
from mc.types import task_safe_id

Summarizer = Callable[..., str]
logger = logging.getLogger(__name__)


@dataclass
class ThreadJournalSnapshot:
    """Resolved thread-journal state for prompt context assembly."""

    journal_path: str
    state: ThreadCompactionState
    recent_messages: list[dict[str, Any]]
    store: ThreadJournalStore


class ThreadJournalService:
    """Reconcile Convex task messages into a local journal and rolling state."""

    def __init__(
        self,
        *,
        base_tasks_dir: Path | None = None,
        recent_window_messages: int = 15,
        compaction_batch_messages: int = 5,
        compaction_trigger_messages: int | None = None,
        compaction_trigger_chars: int | None = None,
        summary_token_budget: int = 20_000,
        summarizer: Summarizer | None = None,
        bridge: Any | None = None,
    ) -> None:
        self._base_tasks_dir = base_tasks_dir or (Path.home() / ".nanobot" / "tasks")
        self._recent_window_messages = recent_window_messages
        self._compaction_batch_messages = compaction_batch_messages
        self._compaction_trigger_messages = compaction_trigger_messages
        self._compaction_trigger_chars = compaction_trigger_chars
        self._summary_token_budget = summary_token_budget
        self._summarizer = summarizer
        self._bridge = bridge

    def sync_task_thread(
        self,
        *,
        task_id: str,
        task_title: str,
        task_data: dict[str, Any],
        messages: list[dict[str, Any]],
    ) -> ThreadJournalSnapshot:
        """Reconcile the full task thread into the local journal store."""
        store = self._build_store(task_id)
        state = store.read_state()
        store.write_journal_header(
            task_title=task_title,
            task_id=task_id,
            created_at=self._resolve_created_at(messages),
            updated_at=self._resolve_updated_at(messages),
            status=str(task_data.get("status") or ""),
            assigned_agent=str(
                task_data.get("assigned_agent") or task_data.get("assignedAgent") or ""
            ),
            board_name=str(task_data.get("board_name") or task_data.get("boardName") or "") or None,
            workflow_spec=str(
                task_data.get("workflow_spec_id") or task_data.get("workflowSpecId") or ""
            )
            or None,
            plan_generated_by=self._resolve_plan_generated_by(task_data),
            execution_plan_markdown=self._render_execution_plan_markdown(task_data),
        )

        unseen_messages = self._messages_after_id(messages, state.last_journal_message_id)
        for message in unseen_messages:
            store.append_event(
                timestamp=str(message.get("timestamp") or ""),
                author_name=str(
                    message.get("author_name") or message.get("authorName") or "Unknown"
                ),
                author_type=str(
                    message.get("author_type") or message.get("authorType") or "system"
                ),
                event_type=str(
                    message.get("type")
                    or message.get("message_type")
                    or message.get("messageType")
                    or "message"
                ),
                content=str(message.get("content") or ""),
                step_id=self._message_step_id(message),
                artifacts=message.get("artifacts"),
            )

        if messages:
            state.last_journal_message_id = self._message_id(messages[-1])
        state.recent_window_messages = self._recent_window_messages
        state.summary_token_budget = self._summary_token_budget
        eligible_messages = self._eligible_compaction_messages(
            messages=messages,
            last_compacted_message_id=state.last_compacted_message_id,
        )
        state.message_count_since_compaction = len(eligible_messages)
        state.char_count_since_compaction = sum(
            len(str(message.get("content") or "")) for message in eligible_messages
        )
        store.write_state(state)

        return ThreadJournalSnapshot(
            journal_path=str(store.journal_path),
            state=state,
            recent_messages=messages[-self._recent_window_messages :]
            if self._recent_window_messages
            else [],
            store=store,
        )

    def compact_thread(
        self,
        *,
        task_id: str,
        task_title: str,
        task_data: dict[str, Any],
        messages: list[dict[str, Any]],
    ) -> ThreadCompactionState:
        """Compact the next eligible older message batch into the rolling summary."""
        snapshot = self.sync_task_thread(
            task_id=task_id,
            task_title=task_title,
            task_data=task_data,
            messages=messages,
        )
        state = snapshot.store.read_state()
        eligible_messages = self._eligible_compaction_messages(
            messages=messages,
            last_compacted_message_id=state.last_compacted_message_id,
        )
        if not eligible_messages:
            return state
        batch = eligible_messages[: self._compaction_batch_messages]
        if not batch:
            return state
        if self._summarizer is None:
            raise RuntimeError("Thread compaction summarizer is required")

        summary = self._summarizer(
            previous_summary=state.compacted_summary,
            messages=batch,
            max_tokens=state.summary_token_budget,
        )

        batch_ids = [self._message_id(message) for message in batch if self._message_id(message)]
        state.compacted_summary = summary
        state.last_compacted_message_id = self._message_id(batch[-1])
        state.last_compacted_timestamp = str(batch[-1].get("timestamp") or "")
        state.source_message_ids = list(dict.fromkeys([*state.source_message_ids, *batch_ids]))
        state.message_count_since_compaction = 0
        state.char_count_since_compaction = 0
        snapshot.store.write_state(state)
        return state

    def schedule_background_compaction(
        self,
        *,
        task_id: str,
        task_title: str,
        task_data: dict[str, Any],
        messages: list[dict[str, Any]],
    ) -> asyncio.Task[Any]:
        """Schedule deduplicated background compaction for a task when needed."""
        snapshot = self.sync_task_thread(
            task_id=task_id,
            task_title=task_title,
            task_data=task_data,
            messages=messages,
        )
        if not self._should_compact(snapshot.state):
            return create_background_task(self._noop())

        async def _run() -> ThreadCompactionState | None:
            try:
                return self.compact_thread(
                    task_id=task_id,
                    task_title=task_title,
                    task_data=task_data,
                    messages=messages,
                )
            except Exception as exc:
                await self._handle_compaction_failure(
                    task_id=task_id,
                    journal_path=snapshot.journal_path,
                    exc=exc,
                )
                return None

        return create_deduplicated_background_task(
            f"thread-compaction:{task_id}",
            _run(),
        )

    def _build_store(self, task_id: str) -> ThreadJournalStore:
        safe_id = task_safe_id(task_id)
        output_dir = self._base_tasks_dir / safe_id / "output"
        return ThreadJournalStore(
            journal_path=output_dir / "THREAD_JOURNAL.md",
            state_path=output_dir / "THREAD_COMPACTION_STATE.json",
        )

    def _eligible_compaction_messages(
        self,
        *,
        messages: list[dict[str, Any]],
        last_compacted_message_id: str | None,
    ) -> list[dict[str, Any]]:
        if len(messages) <= self._recent_window_messages:
            return []
        older_messages = messages[: -self._recent_window_messages]
        return self._messages_after_id(older_messages, last_compacted_message_id)

    def _should_compact(self, state: ThreadCompactionState) -> bool:
        if self._compaction_trigger_messages is not None:
            if state.message_count_since_compaction >= self._compaction_trigger_messages:
                return True
        if self._compaction_trigger_chars is not None:
            if state.char_count_since_compaction >= self._compaction_trigger_chars:
                return True
        return False

    @staticmethod
    def _messages_after_id(
        messages: list[dict[str, Any]],
        last_message_id: str | None,
    ) -> list[dict[str, Any]]:
        if not last_message_id:
            return list(messages)
        seen = False
        result: list[dict[str, Any]] = []
        for message in messages:
            if seen:
                result.append(message)
            elif ThreadJournalService._message_id(message) == last_message_id:
                seen = True
        return result

    @staticmethod
    def _message_id(message: dict[str, Any]) -> str | None:
        value = message.get("_id") or message.get("id")
        return str(value) if value else None

    @staticmethod
    def _message_step_id(message: dict[str, Any]) -> str | None:
        value = message.get("step_id") or message.get("stepId")
        return str(value) if value else None

    @staticmethod
    def _resolve_created_at(messages: list[dict[str, Any]]) -> str:
        if messages:
            return str(messages[0].get("timestamp") or "")
        return ""

    @staticmethod
    def _resolve_updated_at(messages: list[dict[str, Any]]) -> str:
        if messages:
            return str(messages[-1].get("timestamp") or "")
        return ""

    @staticmethod
    def _resolve_plan_generated_by(task_data: dict[str, Any]) -> str | None:
        execution_plan = task_data.get("execution_plan") or task_data.get("executionPlan") or {}
        if not isinstance(execution_plan, dict):
            return None
        generated_by = execution_plan.get("generated_by") or execution_plan.get("generatedBy")
        return str(generated_by) if generated_by else None

    @staticmethod
    def _render_execution_plan_markdown(task_data: dict[str, Any]) -> str:
        execution_plan = task_data.get("execution_plan") or task_data.get("executionPlan") or {}
        if not isinstance(execution_plan, dict):
            return "(none)"
        steps = execution_plan.get("steps") or []
        if not isinstance(steps, list) or not steps:
            return "(none)"
        lines: list[str] = []
        for index, step in enumerate(steps, start=1):
            title = step.get("title") or step.get("description") or f"Step {index}"
            lines.append(f"{index}. {title}")
        return "\n".join(lines)

    async def _handle_compaction_failure(
        self,
        *,
        task_id: str,
        journal_path: str,
        exc: Exception,
    ) -> None:
        logger.exception(
            "[thread_journal] Compaction failed for task %s (journal=%s): %s",
            task_id,
            journal_path,
            exc,
        )
        if self._bridge is None:
            return
        try:
            await asyncio.to_thread(
                self._bridge.update_task_status,
                task_id,
                "crashed",
                None,
                f"Thread compaction failed: {type(exc).__name__}: {exc}",
            )
        except Exception:
            logger.exception(
                "[thread_journal] Failed to crash task %s after compaction failure",
                task_id,
            )

    @staticmethod
    async def _noop() -> None:
        return None
