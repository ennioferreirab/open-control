"""
Chat Handler -- processes direct chat messages between users and agents.

Polls Convex for pending chat messages and routes them through the agent
runtime. Sessions persist across messages (no end_task_session call).

Story 10.2 -- Task 5.

TODO (CC-6 H2): Thread replies to tasks assigned to claude-code (backend="claude-code")
agents are currently not routed to TaskExecutor.handle_cc_thread_reply(). The
MentionWatcher in mention_watcher.py handles @mention messages across tasks, but
plain (non-mention) user replies to a done/crashed CC task thread are not forwarded
to the CC provider for session resumption.

To integrate: in MentionWatcher._poll_all_tasks() (or a new dedicated poller), detect
user messages on tasks whose assigned agent has backend="claude-code", and call
TaskExecutor.handle_cc_thread_reply(task_id, agent_name, content, agent_data) instead
of (or in addition to) the @mention flow. The TaskExecutor method already implements
the full resume + session update + response posting logic (CC-6 AC3).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 2

# Strong references to fire-and-forget consolidation tasks (prevents GC before completion).
_chat_background_tasks: set[asyncio.Task[None]] = set()


class ChatHandler:
    """Polls for pending chat messages and dispatches them to agents."""

    def __init__(self, bridge: ConvexBridge, ask_user_registry: Any | None = None) -> None:
        self._bridge = bridge
        self._ask_user_registry = ask_user_registry

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

            _loop_path = Path(__file__).parent.parent / "vendor" / "nanobot" / "nanobot" / "agent" / "loop.py"
            spec = importlib.util.spec_from_file_location(
                "_nanobot_agent_loop", str(_loop_path)
            )
            loop_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(loop_mod)  # type: ignore[union-attr]
            AgentLoop = loop_mod.AgentLoop

            _bus_path = Path(__file__).parent.parent / "vendor" / "nanobot" / "nanobot" / "bus" / "queue.py"
            bus_spec = importlib.util.spec_from_file_location(
                "_nanobot_bus", str(_bus_path)
            )
            bus_mod = importlib.util.module_from_spec(bus_spec)
            bus_spec.loader.exec_module(bus_mod)  # type: ignore[union-attr]
            MessageBus = bus_mod.MessageBus

            from mc.provider_factory import create_provider
            from mc.gateway import AGENTS_DIR
            from mc.yaml_validator import validate_agent_file

            # Load agent config
            config_file = AGENTS_DIR / agent_name / "config.yaml"
            agent_prompt = None
            agent_model = None
            agent_skills = None
            agent_display_name = agent_name
            agent_data_full = None
            if config_file.exists():
                result = validate_agent_file(config_file)
                if not isinstance(result, list):
                    agent_data_full = result
                    agent_prompt = result.prompt
                    agent_model = result.model
                    agent_skills = result.skills
                    agent_display_name = result.display_name or agent_name

            # Resolve tier references
            from mc.types import is_tier_reference, is_cc_model, extract_cc_model_name

            if agent_model and is_tier_reference(agent_model):
                from mc.tier_resolver import TierResolver

                resolver = TierResolver(self._bridge)
                agent_model = resolver.resolve_model(agent_model)

            # Route to Claude Code backend when model starts with cc/
            if agent_model and is_cc_model(agent_model):
                cc_model_name = extract_cc_model_name(agent_model)
                from mc.types import AgentData
                if agent_data_full:
                    agent_data_for_cc = agent_data_full
                    agent_data_for_cc.model = cc_model_name
                    agent_data_for_cc.backend = "claude-code"
                else:
                    agent_data_for_cc = AgentData(
                        name=agent_name,
                        display_name=agent_display_name,
                        role="agent",
                        model=cc_model_name,
                        backend="claude-code",
                    )
                # Enrich from Convex agent data (for claude_code_opts not in config.yaml)
                try:
                    convex_agent_raw = await asyncio.to_thread(
                        self._bridge.get_agent_by_name, agent_name
                    )
                    if convex_agent_raw:
                        agent_data_for_cc.display_name = convex_agent_raw.get("display_name", agent_display_name)
                        agent_data_for_cc.role = convex_agent_raw.get("role", "agent")
                        cc_opts_raw = convex_agent_raw.get("claude_code_opts")
                        if cc_opts_raw and isinstance(cc_opts_raw, dict):
                            from mc.types import ClaudeCodeOpts
                            agent_data_for_cc.claude_code_opts = ClaudeCodeOpts(
                                max_budget_usd=cc_opts_raw.get("max_budget_usd"),
                                max_turns=cc_opts_raw.get("max_turns"),
                                permission_mode=cc_opts_raw.get("permission_mode", "acceptEdits"),
                                allowed_tools=cc_opts_raw.get("allowed_tools"),
                                disallowed_tools=cc_opts_raw.get("disallowed_tools"),
                            )
                except Exception:
                    logger.warning("[chat] Could not enrich agent data for CC routing")

                task_id = f"chat-{agent_name}"

                from claude_code.workspace import CCWorkspaceManager
                from claude_code.provider import ClaudeCodeProvider
                from claude_code.ipc_server import MCSocketServer

                try:
                    ws_mgr = CCWorkspaceManager()
                    from mc.orientation import load_orientation
                    orientation = load_orientation(agent_name)
                    ws_ctx = ws_mgr.prepare(agent_name, agent_data_for_cc, task_id, orientation=orientation,
                                            task_prompt=content)
                except Exception as exc:
                    raise RuntimeError(f"CC workspace preparation failed: {exc}")

                from mc.ask_user_handler import AskUserHandler

                ask_handler = AskUserHandler()
                ipc_server = MCSocketServer(self._bridge, None)
                ipc_server.set_ask_user_handler(ask_handler)
                if self._ask_user_registry is not None:
                    self._ask_user_registry.register(task_id, ask_handler)
                try:
                    await ipc_server.start(ws_ctx.socket_path)
                except Exception as exc:
                    raise RuntimeError(f"MCP IPC server failed: {exc}")

                # Load persisted session for chat continuity
                session_id: str | None = None
                settings_key = f"cc_session:{agent_name}:chat"
                try:
                    stored = await asyncio.to_thread(
                        self._bridge.query,
                        "settings:get",
                        {"key": settings_key},
                    )
                    if stored and isinstance(stored, str):
                        session_id = stored
                        logger.info("[chat] Resuming CC session %s for %s", session_id, agent_name)
                except Exception:
                    logger.debug("[chat] No stored CC session for %s chat", agent_name)

                # Sentinel captures execute_task() result for consolidation in finally.
                # Assigned before the is_error raise so both success and error paths see it.
                _cc_result_obj = None
                _cc_ws_cwd_chat = ws_ctx.cwd

                try:
                    from nanobot.config.loader import load_config
                    _cfg = load_config()
                    provider = ClaudeCodeProvider(
                        cli_path=_cfg.claude_code.cli_path,
                        defaults=_cfg.claude_code,
                    )

                    # Build prompt with system instructions
                    prompt = content
                    if agent_prompt:
                        prompt = (
                            f"[System instructions]\n{agent_prompt}\n\n"
                            f"[Chat message]\n{content}"
                        )

                    result_obj = await provider.execute_task(
                        prompt=prompt,
                        agent_config=agent_data_for_cc,
                        task_id=task_id,
                        workspace_ctx=ws_ctx,
                        session_id=session_id,
                    )

                    # Capture before the is_error raise so the finally can consolidate
                    # both successful and error CC chat results (mirrors executor behaviour).
                    _cc_result_obj = result_obj

                    if result_obj.is_error:
                        raise RuntimeError(f"Claude Code error: {result_obj.output[:1000]}")

                    result = result_obj.output

                    # Persist session for next chat message
                    try:
                        await asyncio.to_thread(
                            self._bridge.mutation,
                            "settings:set",
                            {"key": settings_key, "value": result_obj.session_id},
                        )
                    except Exception:
                        logger.warning("[chat] Failed to persist CC session for %s", agent_name)

                finally:
                    if self._ask_user_registry is not None:
                        self._ask_user_registry.unregister(task_id)
                    await ipc_server.stop()

                    # Fire-and-forget memory consolidation for CC chat (both success and error).
                    # Runs here (finally) so error results are also consolidated.
                    # _cc_result_obj is None only if execute_task() itself threw, in which case
                    # there is nothing useful to consolidate.
                    if _cc_result_obj is not None:
                        _cc_task_status_chat = "error" if _cc_result_obj.is_error else "completed"
                        _cc_task_output_chat = _cc_result_obj.output or ""

                        async def _post_chat_consolidate():
                            try:
                                from claude_code.memory_consolidator import CCMemoryConsolidator
                                from mc.types import is_tier_reference
                                from mc.tier_resolver import TierResolver
                                _model = "tier:standard-low"
                                if is_tier_reference(_model):
                                    _model = TierResolver(self._bridge).resolve_model(_model) or _model
                                consolidator = CCMemoryConsolidator(_cc_ws_cwd_chat)
                                await consolidator.consolidate(
                                    task_title=f"chat with @{agent_name}",
                                    task_output=_cc_task_output_chat,
                                    task_status=_cc_task_status_chat,
                                    task_id=task_id,
                                    model=_model,
                                )
                                logger.info("[chat] CC memory consolidation done for @%s", agent_name)
                            except Exception:
                                logger.warning(
                                    "[chat] CC memory consolidation failed for @%s", agent_name, exc_info=True
                                )

                        _ct = asyncio.create_task(_post_chat_consolidate())
                        _chat_background_tasks.add(_ct)
                        _ct.add_done_callback(_chat_background_tasks.discard)

                # Send response and mark done
                await asyncio.to_thread(
                    self._bridge.send_chat_response,
                    agent_name,
                    result,
                    agent_display_name,
                )
                await asyncio.to_thread(
                    self._bridge.mark_chat_done, chat_id
                )
                logger.info("[chat] CC response sent for @%s", agent_name)
                return

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
                agent_display_name,
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
