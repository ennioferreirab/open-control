"""Tool for synchronous agent-to-agent conversation (Story 10.3)."""

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any, TYPE_CHECKING

from nanobot.agent.tools.base import Tool

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)


class AskAgentTool(Tool):
    """Ask another agent a question synchronously and wait for their response."""

    def __init__(self) -> None:
        self._caller_agent: str | None = None
        self._task_id: str | None = None
        self._depth: int = 0
        self._bridge: "ConvexBridge | None" = None

    def set_context(
        self,
        caller_agent: str,
        task_id: str | None,
        depth: int,
        bridge: "ConvexBridge | None",
    ) -> None:
        """Set the MC execution context for this tool instance."""
        self._caller_agent = caller_agent
        self._task_id = task_id
        self._depth = depth
        self._bridge = bridge

    @property
    def name(self) -> str:
        return "ask_agent"

    @property
    def description(self) -> str:
        return (
            "Ask another agent a question synchronously and wait for their response. "
            "Use for clarification, brainstorming, or getting a specialist opinion "
            "during task execution. The target agent responds based on their "
            "specialization. Do NOT use this for delegating full tasks — use "
            "delegate_task instead."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target_agent": {
                    "type": "string",
                    "description": "Name of the agent to ask (e.g., 'secretary', 'researcher')",
                },
                "question": {
                    "type": "string",
                    "description": "The question to ask the target agent",
                },
            },
            "required": ["target_agent", "question"],
        }

    async def execute(self, target_agent: str, question: str, **kwargs: Any) -> str:
        """Execute the ask_agent tool: ask another agent synchronously."""
        # Validate caller context
        if not self._caller_agent:
            return "Error: ask_agent can only be used during MC task execution (no caller context set)."

        # AC5: Lead agent protection
        from mc.types import LEAD_AGENT_NAME, is_lead_agent

        if is_lead_agent(target_agent) or target_agent == "lead-agent":
            return (
                "Cannot ask the Lead Agent. The Lead Agent is a pure orchestrator "
                "and cannot be targeted by ask_agent."
            )

        # AC3: Depth limit
        if self._depth >= 2:
            return (
                "Inter-agent conversation depth limit reached (max 2). "
                "Cannot nest ask_agent calls beyond this depth."
            )

        # Load target agent config
        from mc.infrastructure.config import AGENTS_DIR
        from mc.yaml_validator import validate_agent_file

        config_file = AGENTS_DIR / target_agent / "config.yaml"
        if not config_file.exists():
            available = self._list_available_agents(AGENTS_DIR)
            return (
                f"Agent '{target_agent}' not found. "
                f"Available agents: {available}."
            )

        result = validate_agent_file(config_file)
        if isinstance(result, list):
            available = self._list_available_agents(AGENTS_DIR)
            return (
                f"Agent '{target_agent}' config is invalid: {'; '.join(result)}. "
                f"Available agents: {available}."
            )

        agent_prompt = result.prompt
        agent_model = result.model
        agent_skills = result.skills

        # Resolve tier reference to actual model ID (e.g. tier:standard-medium → claude-sonnet-4-6)
        from mc.types import is_tier_reference
        if agent_model and is_tier_reference(agent_model):
            if self._bridge:
                try:
                    from mc.tier_resolver import TierResolver
                    agent_model = TierResolver(self._bridge).resolve_model(agent_model)
                except Exception as exc:
                    return f"Failed to resolve model tier '{agent_model}' for '{target_agent}': {exc}"
            else:
                return (
                    f"Agent '{target_agent}' uses tier model '{agent_model}' "
                    f"which cannot be resolved without an MC connection."
                )

        # Create provider
        try:
            from mc.provider_factory import create_provider

            provider, resolved_model = create_provider(agent_model)
        except Exception as exc:
            response = f"Failed to create provider for {target_agent}: {exc}"
            await self._log_to_thread(question, target_agent, response)
            return response

        # Build focused prompt
        focused_prompt = (
            f"You are being asked by {self._caller_agent} for clarification "
            f"during task execution. Answer concisely and specifically.\n\n"
            f"Question: {question}"
        )
        if agent_prompt:
            focused_prompt = (
                f"[System instructions]\n{agent_prompt}\n\n"
                f"[Inter-agent query]\n{focused_prompt}"
            )

        # Create isolated session key
        session_key = f"mc:ask:{self._caller_agent}:{target_agent}:{uuid.uuid4().hex[:8]}"

        # Lazy import to avoid circular imports
        from nanobot.agent.loop import AgentLoop
        from nanobot.bus.queue import MessageBus

        workspace = AGENTS_DIR / target_agent
        workspace.mkdir(parents=True, exist_ok=True)

        bus = MessageBus()
        child_loop = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=workspace,
            model=resolved_model,
            allowed_skills=agent_skills,
        )

        # Set depth on child loop's ask_agent tool (AC3: prevent infinite recursion)
        if child_ask_tool := child_loop.tools.get("ask_agent"):
            if isinstance(child_ask_tool, AskAgentTool):
                child_ask_tool.set_context(
                    caller_agent=target_agent,
                    task_id=self._task_id,
                    depth=self._depth + 1,
                    bridge=self._bridge,
                )

        # Execute with timeout (AC4)
        try:
            response = await asyncio.wait_for(
                child_loop.process_direct(
                    content=focused_prompt,
                    session_key=session_key,
                    channel="mc",
                    chat_id=target_agent,
                ),
                timeout=120,
            )
        except asyncio.TimeoutError:
            response = (
                f"ask_agent timed out after 120 seconds. "
                f"Target agent '{target_agent}' did not respond in time."
            )
            await self._log_to_thread(question, target_agent, response)
            return response
        except Exception as exc:
            logger.exception("ask_agent failed for target '%s'", target_agent)
            response = f"ask_agent failed: {exc}"
            await self._log_to_thread(question, target_agent, response)
            return response

        # AC6: Log to task thread
        await self._log_to_thread(question, target_agent, response)

        return response

    async def _log_to_thread(
        self, question: str, target_agent: str, response: str
    ) -> None:
        """Log the inter-agent conversation to the task thread (AC6)."""
        if not self._bridge or not self._task_id:
            return

        content = (
            f"Inter-agent conversation: {self._caller_agent} asked {target_agent}\n"
            f"Question: {question}\n"
            f"Response: {response[:500]}"
        )
        try:
            await asyncio.to_thread(
                self._bridge.send_message,
                self._task_id,
                "System",
                "system",
                content,
                "system_event",
            )
        except Exception:
            logger.warning("Failed to log inter-agent conversation to thread")

    @staticmethod
    def _list_available_agents(agents_dir: Path) -> str:
        """List available agent names from the agents directory."""
        if not agents_dir.is_dir():
            return "(none)"
        names = sorted(
            d.name
            for d in agents_dir.iterdir()
            if d.is_dir() and (d / "config.yaml").exists()
        )
        return ", ".join(names) if names else "(none)"
