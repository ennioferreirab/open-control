"""
Crash Handler — monitors agent processes and handles crash recovery with auto-retry.

Extracted from mc.gateway so that executor can depend on it without importing
the gateway composition root.

Implements FR37 (auto-retry once on crash), FR38 (crashed status with error
log), and NFR10 (crash recovery within 30 seconds).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)

# Max auto-retries per task (FR37: single retry)
MAX_AUTO_RETRIES = 1


class AgentGateway:
    """Monitors agent processes and handles crash recovery with auto-retry.

    Implements FR37 (auto-retry once on crash), FR38 (crashed status with error
    log), and NFR10 (crash recovery within 30 seconds).
    """

    def __init__(self, bridge: ConvexBridge) -> None:
        self._bridge = bridge
        self._retry_counts: dict[str, int] = {}

    async def handle_agent_crash(self, agent_name: str, task_id: str, error: Exception) -> None:
        """Handle an agent crash during task execution.

        On first crash: transitions task to "retrying", logs error to thread,
        and re-dispatches. On second crash (or if retry count already >= 1):
        transitions to "crashed" and stops.

        Args:
            agent_name: Name of the crashed agent.
            task_id: Convex task _id the agent was working on.
            error: The exception that caused the crash.
        """
        error_msg = f"{type(error).__name__}: {error}"
        current_retries = self._retry_counts.get(task_id, 0)

        if current_retries < MAX_AUTO_RETRIES:
            await self._retry_task(task_id, agent_name, error_msg, current_retries)
        else:
            await self._crash_task(task_id, agent_name, error_msg)

    async def _retry_task(
        self,
        task_id: str,
        agent_name: str,
        error_msg: str,
        current_retries: int,
    ) -> None:
        """Auto-retry: transition to retrying, log error, re-dispatch."""
        self._retry_counts[task_id] = current_retries + 1
        attempt = current_retries + 1

        logger.info(
            "[gateway] Agent '%s' crashed on task %s. Auto-retrying (attempt %d/%d)",
            agent_name,
            task_id,
            attempt,
            MAX_AUTO_RETRIES,
        )

        # Transition task to "retrying"
        await asyncio.to_thread(
            self._bridge.update_task_status,
            task_id,
            "retrying",
            agent_name,
            f"Agent {agent_name} crashed. Auto-retrying (attempt {attempt}/{MAX_AUTO_RETRIES})",
        )

        # Write error details to task thread
        await asyncio.to_thread(
            self._bridge.send_message,
            task_id,
            "System",
            "system",
            f"Agent crash detected:\n```\n{error_msg}\n```\nAuto-retrying...",
            "system_event",
        )

        # Re-dispatch: transition retrying -> in_progress
        await asyncio.to_thread(
            self._bridge.update_task_status,
            task_id,
            "in_progress",
            agent_name,
            f"Re-dispatching task to {agent_name}",
        )

    async def _crash_task(self, task_id: str, agent_name: str, error_msg: str) -> None:
        """Retry exhausted: transition to crashed, log full error."""
        self._retry_counts.pop(task_id, None)

        logger.error(
            "[gateway] Agent '%s' crashed on task %s. Retry exhausted — marking as crashed.",
            agent_name,
            task_id,
        )

        # Transition task to "crashed"
        await asyncio.to_thread(
            self._bridge.update_task_status,
            task_id,
            "crashed",
            agent_name,
            f"Agent {agent_name} crashed. Retry failed. Task marked as crashed.",
        )

        # Write error details to task thread
        await asyncio.to_thread(
            self._bridge.send_message,
            task_id,
            "System",
            "system",
            (
                f"Retry failed. Agent crash:\n```\n{error_msg}\n```\n"
                "Task marked as crashed. Use 'Retry from Beginning' to try again."
            ),
            "system_event",
        )

    def clear_retry_count(self, task_id: str) -> None:
        """Clear the retry count for a task.

        Called when a task completes successfully or is manually retried
        (transitions to "inbox" via Story 6.4).
        """
        self._retry_counts.pop(task_id, None)

    def get_retry_count(self, task_id: str) -> int:
        """Return current retry count for a task."""
        return self._retry_counts.get(task_id, 0)


CrashRecoveryService = AgentGateway

__all__ = ["MAX_AUTO_RETRIES", "AgentGateway", "CrashRecoveryService"]
