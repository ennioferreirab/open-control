"""Tool for asking the human user a question and waiting for their reply.

Delegates to mc.ask_user.handler.AskUserHandler for the unified ask_user flow.
"""

from typing import TYPE_CHECKING, Any

from nanobot.agent.tools.base import Tool

if TYPE_CHECKING:
    from mc.ask_user.handler import AskUserHandler
    from mc.bridge import ConvexBridge


class AskUserTool(Tool):
    """Ask the human user a question and wait for their reply.

    Uses AskUserHandler for the shared ask_user implementation.
    """

    def __init__(self) -> None:
        self._bridge: "ConvexBridge | None" = None
        self._task_id: str | None = None
        self._agent_name: str | None = None
        self._handler: "AskUserHandler | None" = None

    def set_context(
        self,
        agent_name: str,
        task_id: str | None,
        bridge: "ConvexBridge | None",
        handler: "AskUserHandler | None",
    ) -> None:
        """Set the MC execution context."""
        self._agent_name = agent_name
        self._task_id = task_id
        self._bridge = bridge
        self._handler = handler

    def teardown(self) -> None:
        """Clear context after task execution."""
        self._bridge = None
        self._task_id = None
        self._agent_name = None
        self._handler = None

    @property
    def name(self) -> str:
        return "ask_user"

    @property
    def description(self) -> str:
        return (
            "Ask the human user a question and wait for their reply. "
            "The call BLOCKS until the user actually responds — do NOT proceed "
            "until you receive the answer. Use this for clarifications, "
            "questionnaires (one question at a time), or confirmations. "
            "NEVER guess or fabricate user input."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to ask the user.",
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of choices for the user.",
                },
            },
            "required": ["question"],
        }

    async def execute(self, question: str, options: list[str] | None = None, **kwargs: Any) -> str:
        """Post question to thread, wait for user reply, return it."""
        if not self._bridge or not self._task_id:
            return "Error: ask_user requires Mission Control context (bridge + task_id)."
        if not self._handler:
            return "Error: ask_user handler not initialized."

        agent_name = self._agent_name or "agent"
        return await self._handler.ask(
            question=question,
            options=options,
            agent_name=agent_name,
            task_id=self._task_id,
            bridge=self._bridge,
        )
