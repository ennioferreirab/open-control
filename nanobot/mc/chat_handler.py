"""
Chat Handler -- processes direct chat messages between users and agents.

Polls Convex for pending chat messages and routes them through the agent
runtime. Sessions persist across messages (no end_task_session call).

Story 10.2 -- Task 5.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nanobot.mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 2


class ChatHandler:
    """Polls for pending chat messages and dispatches them to agents."""

    def __init__(self, bridge: ConvexBridge) -> None:
        self._bridge = bridge

    async def run(self) -> None:
        """Polling loop: fetch pending chats every POLL_INTERVAL_SECONDS."""
        logger.info("[chat] ChatHandler started")
        while True:
            try:
                pending = await asyncio.to_thread(
                    self._bridge.get_pending_chat_messages
                )
                for msg in pending or []:
                    asyncio.create_task(self._process_chat_message(msg))
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("[chat] Error polling pending chats")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def _process_chat_message(self, msg: dict[str, Any]) -> None:
        """Process a single pending chat message.

        1. Mark as processing
        2. Load agent config, create provider + AgentLoop
        3. Call process_direct with session key mc-chat:{agent_name}
        4. Send the response as an agent message
        5. Mark original as done
        """
        chat_id = msg.get("id")
        agent_name = msg.get("agent_name", "")
        content = msg.get("content", "")

        if not chat_id or not agent_name:
            logger.warning("[chat] Skipping invalid chat message: %s", msg)
            return

        logger.info("[chat] Processing chat from user to @%s", agent_name)

        try:
            # Mark as processing
            await asyncio.to_thread(
                self._bridge.mark_chat_processing, chat_id
            )

            # Lazy imports to avoid heavy nanobot.agent dependency at module level
            import importlib.util

            _loop_path = Path(__file__).parent.parent / "agent" / "loop.py"
            spec = importlib.util.spec_from_file_location(
                "_nanobot_agent_loop", str(_loop_path)
            )
            loop_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(loop_mod)  # type: ignore[union-attr]
            AgentLoop = loop_mod.AgentLoop

            _bus_path = Path(__file__).parent.parent / "bus" / "queue.py"
            bus_spec = importlib.util.spec_from_file_location(
                "_nanobot_bus", str(_bus_path)
            )
            bus_mod = importlib.util.module_from_spec(bus_spec)
            bus_spec.loader.exec_module(bus_mod)  # type: ignore[union-attr]
            MessageBus = bus_mod.MessageBus

            from nanobot.mc.provider_factory import create_provider
            from nanobot.mc.gateway import AGENTS_DIR
            from nanobot.mc.yaml_validator import validate_agent_file

            # Load agent config
            config_file = AGENTS_DIR / agent_name / "config.yaml"
            agent_prompt = None
            agent_model = None
            agent_skills = None
            if config_file.exists():
                result = validate_agent_file(config_file)
                if not isinstance(result, list):
                    agent_prompt = result.prompt
                    agent_model = result.model
                    agent_skills = result.skills

            # Resolve tier references
            from nanobot.mc.types import is_tier_reference

            if agent_model and is_tier_reference(agent_model):
                from nanobot.mc.tier_resolver import TierResolver

                resolver = TierResolver(self._bridge)
                agent_model = resolver.resolve_model(agent_model)

            # Create provider
            provider, resolved_model = create_provider(agent_model)

            workspace = AGENTS_DIR / agent_name
            workspace.mkdir(parents=True, exist_ok=True)

            global_skills_dir = Path.home() / ".nanobot" / "workspace" / "skills"

            # Build message with optional system prompt
            message = content
            if agent_prompt:
                message = (
                    f"[System instructions]\n{agent_prompt}\n\n"
                    f"[Chat message]\n{content}"
                )

            session_key = f"mc-chat:{agent_name}"

            bus = MessageBus()
            agent_loop = AgentLoop(
                bus=bus,
                provider=provider,
                workspace=workspace,
                model=resolved_model,
                allowed_skills=agent_skills,
                global_skills_dir=global_skills_dir,
            )

            result = await agent_loop.process_direct(
                content=message,
                session_key=session_key,
                channel="mc",
                chat_id=agent_name,
            )
            # Do NOT call end_task_session -- chat sessions persist

            # Send agent response
            await asyncio.to_thread(
                self._bridge.send_chat_response,
                agent_name,
                result,
            )

            # Mark original message as done
            await asyncio.to_thread(
                self._bridge.mark_chat_done, chat_id
            )

            logger.info("[chat] Response sent for @%s", agent_name)

        except Exception as exc:
            logger.exception(
                "[chat] Error processing chat for @%s: %s", agent_name, exc
            )
            # Mark original as done to avoid re-processing
            try:
                await asyncio.to_thread(
                    self._bridge.mark_chat_done, chat_id
                )
            except Exception:
                logger.exception("[chat] Failed to mark chat done after error")

            # Send error response
            try:
                await asyncio.to_thread(
                    self._bridge.send_chat_response,
                    agent_name,
                    f"Error: {type(exc).__name__}: {exc}",
                )
            except Exception:
                logger.exception("[chat] Failed to send error response")
