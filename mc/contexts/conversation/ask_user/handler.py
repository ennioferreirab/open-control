"""Unified ask-user handler for all backends."""

import asyncio
import logging
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)


class AskUserHandler:
    """Unified ask_user handler for all agent backends."""

    def __init__(self) -> None:
        self._pending_ask: dict[str, asyncio.Future[str]] = {}
        self._task_to_request: dict[str, str] = {}

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
        question: str,
        options: list[str] | None,
        agent_name: str,
        task_id: str,
        bridge: "ConvexBridge",
    ) -> str:
        """Post question to thread, wait for a reply, and restore task state."""
        content_parts = [f"**{agent_name} is asking:**\n\n{question}"]
        if options:
            opts_str = "\n".join(f"  {i + 1}. {option}" for i, option in enumerate(options))
            content_parts.append(f"\nOptions:\n{opts_str}")
        content = "\n".join(content_parts)

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

        try:
            await asyncio.to_thread(
                bridge.update_task_status,
                task_id,
                "review",
                description=f"{agent_name} is waiting for user reply (ask_user)",
            )
        except Exception as exc:
            logger.warning("ask_user: failed to set task to review: %s", exc)

        try:
            answer = await future
        finally:
            self._pending_ask.pop(request_id, None)
            self._task_to_request.pop(task_id, None)

        try:
            await asyncio.to_thread(
                bridge.update_task_status,
                task_id,
                "in_progress",
                description=f"{agent_name} received user reply, resuming",
            )
        except Exception as exc:
            logger.warning("ask_user: failed to restore task to in_progress: %s", exc)

        return answer
