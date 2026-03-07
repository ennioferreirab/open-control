"""
Chat Handler -- processes direct chat messages between users and agents.

Polls Convex for pending chat messages and routes them through
ExecutionEngine.run() for both CC and nanobot backends.
Sessions persist across messages (no end_task_session call).

Story 10.2 -- Task 5.  Migrated to ExecutionEngine in Story 20.1.

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
import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from mc.application.execution.background_tasks import create_background_task
from mc.application.execution.engine import ExecutionEngine
from mc.application.execution.request import (
    EntityType,
    ExecutionRequest,
    ExecutionResult,
    RunnerType,
)
from mc.application.execution.runtime import relocate_invalid_memory_files

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)

ACTIVE_POLL_INTERVAL_SECONDS = 5
SLEEP_POLL_INTERVAL_SECONDS = 60
POLL_INTERVAL_SECONDS = ACTIVE_POLL_INTERVAL_SECONDS
RUNTIME_SETTINGS_KEY = "chat_handler_runtime"


class ChatHandler:
    """Polls for pending chat messages and dispatches them to agents."""

    def __init__(
        self, bridge: ConvexBridge, ask_user_registry: Any | None = None
    ) -> None:
        self._bridge = bridge
        self._ask_user_registry = ask_user_registry
        self._mode: str = "sleep"
        self._in_flight = 0
        self._last_transition_at = self._utc_now()
        self._last_work_found_at: str | None = None
        self._remote_terminal_cache: dict[str, bool] = {}

    async def run(self) -> None:
        """Polling loop with adaptive sleep/active intervals."""
        logger.info("[chat] ChatHandler started")
        await self._persist_runtime(force=True)
        while True:
            try:
                pending = await asyncio.to_thread(
                    self._bridge.get_pending_chat_messages
                )
                useful_pending = await self._filter_useful_pending(
                    pending or []
                )
                for msg in useful_pending:
                    self._dispatch_message(msg)
                if useful_pending:
                    await self._persist_runtime(
                        mode="active",
                        work_found=True,
                    )
                elif self._mode == "active" and self._in_flight == 0:
                    await self._persist_runtime(mode="sleep")
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("[chat] Error polling pending chats")
            await asyncio.sleep(self._current_poll_interval())

    def _current_poll_interval(self) -> int:
        if self._mode == "active":
            return ACTIVE_POLL_INTERVAL_SECONDS
        return SLEEP_POLL_INTERVAL_SECONDS

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    async def _persist_runtime(
        self,
        *,
        mode: str | None = None,
        work_found: bool = False,
        force: bool = False,
    ) -> None:
        next_mode = mode or self._mode
        if not force and next_mode == self._mode:
            return

        now = self._utc_now()
        self._mode = next_mode
        self._last_transition_at = now
        if work_found:
            self._last_work_found_at = now

        payload: dict[str, Any] = {
            "mode": self._mode,
            "pollIntervalSeconds": self._current_poll_interval(),
            "lastTransitionAt": self._last_transition_at,
            "inFlight": self._in_flight,
        }
        if self._last_work_found_at is not None:
            payload["lastWorkFoundAt"] = self._last_work_found_at

        try:
            await asyncio.to_thread(
                self._bridge.mutation,
                "settings:set",
                {
                    "key": RUNTIME_SETTINGS_KEY,
                    "value": json.dumps(payload),
                },
            )
        except Exception:
            logger.exception("[chat] Failed to persist runtime state")

    async def _filter_useful_pending(
        self,
        pending: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        useful: list[dict[str, Any]] = []
        for msg in pending:
            agent_name = msg.get("agent_name", "")
            if not agent_name:
                continue
            if await self._is_remote_terminal_agent(agent_name):
                logger.debug(
                    "[chat] Ignoring pending chat for remote terminal @%s",
                    agent_name,
                )
                continue
            useful.append(msg)
        return useful

    async def _is_remote_terminal_agent(self, agent_name: str) -> bool:
        cached = self._remote_terminal_cache.get(agent_name)
        if cached is not None:
            return cached

        try:
            agent = await asyncio.to_thread(
                self._bridge.get_agent_by_name, agent_name
            )
        except Exception:
            logger.exception(
                "[chat] Failed to resolve agent role for @%s",
                agent_name,
            )
            self._remote_terminal_cache[agent_name] = False
            return False

        is_remote_terminal = bool(
            agent and agent.get("role") == "remote-terminal"
        )
        self._remote_terminal_cache[agent_name] = is_remote_terminal
        return is_remote_terminal

    def _dispatch_message(self, msg: dict[str, Any]) -> None:
        self._in_flight += 1
        create_background_task(self._process_with_tracking(msg))

    async def _process_with_tracking(self, msg: dict[str, Any]) -> None:
        try:
            await self._process_chat_message(msg)
        finally:
            self._in_flight = max(0, self._in_flight - 1)

    async def _process_chat_message(self, msg: dict[str, Any]) -> None:
        """Process a single pending chat message.

        1. Mark as processing
        2. Load agent config, determine runner type
        3. Build ExecutionRequest and route through ExecutionEngine.run()
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

            from mc.infrastructure.config import AGENTS_DIR
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
            from mc.types import is_cc_model, is_tier_reference

            if agent_model and is_tier_reference(agent_model):
                from mc.tier_resolver import TierResolver

                resolver = TierResolver(self._bridge)
                agent_model = resolver.resolve_model(agent_model)

            # Determine runner type and build request
            if agent_model and is_cc_model(agent_model):
                engine_result = await self._run_cc_chat(
                    agent_name=agent_name,
                    agent_model=agent_model,
                    agent_prompt=agent_prompt,
                    agent_skills=agent_skills,
                    agent_display_name=agent_display_name,
                    agent_data_full=agent_data_full,
                    content=content,
                )
            else:
                engine_result = await self._run_nanobot_chat(
                    agent_name=agent_name,
                    agent_model=agent_model,
                    agent_prompt=agent_prompt,
                    agent_skills=agent_skills,
                    content=content,
                )

            if not engine_result.success:
                raise RuntimeError(
                    engine_result.error_message
                    or f"Execution failed for chat with @{agent_name}"
                )

            result_text = engine_result.output

            # Send agent response
            await asyncio.to_thread(
                self._bridge.send_chat_response,
                agent_name,
                result_text,
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

    async def _run_cc_chat(
        self,
        *,
        agent_name: str,
        agent_model: str,
        agent_prompt: str | None,
        agent_skills: list[str] | None,
        agent_display_name: str,
        agent_data_full: Any | None,
        content: str,
    ) -> ExecutionResult:
        """Execute CC chat through ExecutionEngine.

        Handles session persistence: loads previous session from settings,
        persists new session_id from result. Also runs post-execution
        memory relocation and consolidation.
        """
        from mc.types import (
            AgentData,
            ClaudeCodeOpts,
            extract_cc_model_name,
        )

        cc_model_name = extract_cc_model_name(agent_model)

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

        # Enrich from Convex agent data
        try:
            convex_agent_raw = await asyncio.to_thread(
                self._bridge.get_agent_by_name, agent_name
            )
            if convex_agent_raw:
                agent_data_for_cc.display_name = convex_agent_raw.get(
                    "display_name", agent_display_name
                )
                agent_data_for_cc.role = convex_agent_raw.get("role", "agent")
                cc_opts_raw = convex_agent_raw.get("claude_code_opts")
                if cc_opts_raw and isinstance(cc_opts_raw, dict):
                    agent_data_for_cc.claude_code_opts = ClaudeCodeOpts(
                        max_budget_usd=cc_opts_raw.get("max_budget_usd"),
                        max_turns=cc_opts_raw.get("max_turns"),
                        permission_mode=cc_opts_raw.get(
                            "permission_mode", "acceptEdits"
                        ),
                        allowed_tools=cc_opts_raw.get("allowed_tools"),
                        disallowed_tools=cc_opts_raw.get("disallowed_tools"),
                    )
        except Exception:
            logger.warning(
                "[chat] Could not enrich agent data for CC routing"
            )

        task_id = f"chat-{agent_name}"

        # Build prompt with system instructions
        prompt = content
        if agent_prompt:
            prompt = (
                f"[System instructions]\n{agent_prompt}\n\n"
                f"[Chat message]\n{content}"
            )

        # Build ExecutionRequest for CC chat
        request = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id=task_id,
            task_id=task_id,
            title=prompt,
            agent=agent_data_for_cc,
            agent_name=agent_name,
            agent_prompt=agent_prompt,
            agent_model=agent_model,
            agent_skills=agent_skills,
            runner_type=RunnerType.CLAUDE_CODE,
            is_cc=True,
        )

        # Create strategy with bridge context
        from mc.application.execution.strategies.claude_code import (
            ClaudeCodeRunnerStrategy,
        )

        cc_strategy = ClaudeCodeRunnerStrategy(
            bridge=self._bridge,
            ask_user_registry=self._ask_user_registry,
        )

        engine = ExecutionEngine(
            strategies={RunnerType.CLAUDE_CODE: cc_strategy},
        )

        engine_result = await engine.run(request)

        # Post-execution: memory relocation
        if engine_result.memory_workspace:
            try:
                await asyncio.to_thread(
                    relocate_invalid_memory_files,
                    task_id,
                    engine_result.memory_workspace,
                )
            except Exception:
                logger.warning(
                    "[chat] Failed to relocate invalid memory files for @%s",
                    agent_name,
                    exc_info=True,
                )

        # Persist session for CC chat continuity
        settings_key = f"cc_session:{agent_name}:chat"
        if engine_result.session_id:
            try:
                await asyncio.to_thread(
                    self._bridge.mutation,
                    "settings:set",
                    {"key": settings_key, "value": engine_result.session_id},
                )
            except Exception:
                logger.warning(
                    "[chat] Failed to persist CC session for %s", agent_name
                )

        # Fire-and-forget memory consolidation
        _ws_cwd = engine_result.memory_workspace
        if _ws_cwd is not None:
            _task_status = "error" if not engine_result.success else "completed"
            _task_output = engine_result.output or ""

            async def _post_chat_consolidate() -> None:
                try:
                    from claude_code.memory_consolidator import (
                        CCMemoryConsolidator,
                    )

                    from mc.tier_resolver import TierResolver
                    from mc.types import is_tier_reference

                    _model = "tier:standard-low"
                    if is_tier_reference(_model):
                        _model = (
                            TierResolver(self._bridge).resolve_model(_model)
                            or _model
                        )
                    consolidator = CCMemoryConsolidator(_ws_cwd)
                    await consolidator.consolidate(
                        task_title=f"chat with @{agent_name}",
                        task_output=_task_output,
                        task_status=_task_status,
                        task_id=task_id,
                        model=_model,
                    )
                    logger.info(
                        "[chat] CC memory consolidation done for @%s",
                        agent_name,
                    )
                except Exception:
                    logger.warning(
                        "[chat] CC memory consolidation failed for @%s",
                        agent_name,
                        exc_info=True,
                    )

            create_background_task(_post_chat_consolidate())

        return engine_result

    async def _run_nanobot_chat(
        self,
        *,
        agent_name: str,
        agent_model: str | None,
        agent_prompt: str | None,
        agent_skills: list[str] | None,
        content: str,
    ) -> ExecutionResult:
        """Execute nanobot chat through ExecutionEngine.

        Uses a chat-specific session key format so sessions persist
        across messages (no end_task_session call).
        """
        # Build prompt with system instructions
        message = content
        if agent_prompt:
            message = (
                f"[System instructions]\n{agent_prompt}\n\n"
                f"[Chat message]\n{content}"
            )

        task_id = f"chat-{agent_name}"
        session_key = f"mc-chat:{agent_name}"

        request = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id=task_id,
            task_id=task_id,
            title=message,
            description=None,
            agent_name=agent_name,
            agent_prompt=agent_prompt,
            agent_model=agent_model,
            agent_skills=agent_skills,
            runner_type=RunnerType.NANOBOT,
            session_key=session_key,
        )

        from mc.application.execution.strategies.nanobot import (
            NanobotRunnerStrategy,
        )

        nanobot_strategy = NanobotRunnerStrategy()

        engine = ExecutionEngine(
            strategies={RunnerType.NANOBOT: nanobot_strategy},
        )

        return await engine.run(request)
