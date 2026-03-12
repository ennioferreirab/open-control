"""Inbox worker — handles new task processing, auto-title, and initial routing."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from mc.contexts.planning.title_generation import generate_title_via_low_agent

if TYPE_CHECKING:
    from mc.infrastructure.runtime_context import RuntimeContext

logger = logging.getLogger(__name__)


class InboxWorker:
    """Processes inbox tasks: auto-title generation and routing to planning/assigned."""

    def __init__(self, ctx: RuntimeContext) -> None:
        self._ctx = ctx
        self._bridge = ctx.bridge
        self._known_inbox_ids: set[str] = set()

    async def process_batch(self, tasks: list[dict[str, Any]]) -> None:
        """Process a batch of inbox tasks from a subscription update."""
        current_ids = {task.get("id") for task in tasks if task.get("id")}
        self._known_inbox_ids &= current_ids

        for task_data in tasks:
            task_id = task_data.get("id")
            if not task_id or task_id in self._known_inbox_ids:
                continue
            if task_data.get("is_manual"):
                self._known_inbox_ids.add(task_id)
                continue
            self._known_inbox_ids.add(task_id)
            try:
                await self.process_task(task_data)
            except Exception:
                logger.warning(
                    "[inbox] Error processing inbox task %s",
                    task_id,
                    exc_info=True,
                )

    async def process_task(self, task_data: dict[str, Any]) -> None:
        """Handle an inbox task: generate auto-title then transition to planning or assigned."""
        task_id = task_data.get("id")
        if task_data.get("is_manual"):
            logger.info("[inbox] Skipping manual inbox task %s", task_id)
            return

        title = task_data.get("title", "")
        description = task_data.get("description")
        assigned_agent = task_data.get("assigned_agent")
        auto_title = task_data.get("auto_title")

        logger.info(
            "[inbox] Processing inbox task %s: auto_title=%r, has_description=%s, keys=%s",
            task_id,
            auto_title,
            bool(description),
            list(task_data.keys()),
        )

        if auto_title and description:
            generated_title = await generate_title_via_low_agent(
                self._bridge, description
            )
            if generated_title:
                title = generated_title
                await asyncio.to_thread(
                    self._bridge.mutation,
                    "tasks:updateTitle",
                    {"task_id": task_id, "title": title},
                )
                logger.info(
                    "[inbox] Auto-generated title for task %s: '%s'",
                    task_id,
                    title,
                )
            else:
                logger.warning(
                    "[inbox] Auto-title generation returned None for task %s; keeping placeholder title",
                    task_id,
                )
                try:
                    await asyncio.to_thread(
                        self._bridge.create_activity,
                        "system_error",
                        "Auto-title generation failed -- check gateway logs for details",
                        task_id,
                    )
                except Exception:
                    pass
        elif auto_title and not description:
            logger.warning(
                "[inbox] auto_title=True but no description for task %s",
                task_id,
            )

        next_status = "assigned" if assigned_agent else "planning"
        await asyncio.to_thread(
            self._bridge.update_task_status,
            task_id,
            next_status,
        )
        logger.info(
            "[inbox] Inbox task %s ('%s') -> %s",
            task_id,
            title,
            next_status,
        )
