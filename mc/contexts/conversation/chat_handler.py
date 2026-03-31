"""
Chat Handler -- processes direct chat messages between users and agents.

Polls Convex for pending chat messages and routes them through
ExecutionEngine.run() for CC and provider-cli backends.
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
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from mc.application.execution.background_tasks import create_background_task
from mc.application.execution.request import (
    EntityType,
    ExecutionRequest,
    ExecutionResult,
    RunnerType,
)
from mc.application.execution.roster_builder import inject_orientation

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge
    from mc.types import AgentData

logger = logging.getLogger(__name__)

ACTIVE_POLL_INTERVAL_SECONDS = 5
SLEEP_POLL_INTERVAL_SECONDS = 60
RUNTIME_SETTINGS_KEY = "chat_handler_runtime"


class ChatHandler:
    """Subscribes to pending chat messages and dispatches them to agents."""

    def __init__(
        self,
        bridge: ConvexBridge,
        ask_user_registry: Any | None = None,
        sleep_controller: Any | None = None,
        *,
        active_poll_interval_seconds: int = ACTIVE_POLL_INTERVAL_SECONDS,
        sleep_poll_interval_seconds: int = SLEEP_POLL_INTERVAL_SECONDS,
    ) -> None:
        self._bridge = bridge
        self._ask_user_registry = ask_user_registry
        self._sleep_controller = sleep_controller
        self._active_poll_interval = active_poll_interval_seconds
        self._sleep_poll_interval = sleep_poll_interval_seconds
        self._mode: str = "sleep"
        self._in_flight = 0
        self._queued_chat_ids: set[str] = set()
        self._last_transition_at = self._utc_now()
        self._last_work_found_at: str | None = None
        self._remote_terminal_cache: dict[str, bool] = {}

    async def run(self) -> None:
        """Subscription loop with adaptive runtime state persistence."""
        logger.info("[chat] ChatHandler started")
        await self._persist_runtime(force=True)
        while True:
            try:
                queue = self._bridge.async_subscribe("chats:listPending", {})
                while True:
                    pending = await queue.get()
                    if pending is None:
                        continue
                    if isinstance(pending, dict) and pending.get("_error") is True:
                        logger.warning(
                            "[chat] Pending chat subscription failed: %s",
                            pending.get("message", "unknown error"),
                        )
                        break
                    if not isinstance(pending, list):
                        logger.warning(
                            "[chat] Ignoring unexpected pending chat payload of type %s",
                            type(pending).__name__,
                        )
                        continue
                    useful_pending = await self._filter_useful_pending(pending)
                    for msg in useful_pending:
                        self._dispatch_message(msg)
                    if useful_pending:
                        if self._sleep_controller is not None:
                            await self._sleep_controller.record_work_found()
                        await self._persist_runtime(
                            mode="active",
                            work_found=True,
                        )
                    elif self._mode == "active" and self._in_flight == 0:
                        if self._sleep_controller is not None:
                            await self._sleep_controller.record_idle()
                            await self._persist_runtime(mode=self._sleep_controller.mode)
                        else:
                            await self._persist_runtime(mode="sleep")
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("[chat] Error handling pending chat subscription")
                await asyncio.sleep(1)

    def _current_poll_interval(self) -> int:
        if self._mode == "active":
            return self._active_poll_interval
        return self._sleep_poll_interval

    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat()

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
            "configuredActiveInterval": self._active_poll_interval,
            "configuredSleepInterval": self._sleep_poll_interval,
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
            agent = await asyncio.to_thread(self._bridge.get_agent_by_name, agent_name)
        except Exception:
            logger.exception(
                "[chat] Failed to resolve agent role for @%s",
                agent_name,
            )
            self._remote_terminal_cache[agent_name] = False
            return False

        is_remote_terminal = bool(agent and agent.get("role") == "remote-terminal")
        self._remote_terminal_cache[agent_name] = is_remote_terminal
        return is_remote_terminal

    def _dispatch_message(self, msg: dict[str, Any]) -> None:
        chat_id = str(msg.get("id") or "")
        if not chat_id or chat_id in self._queued_chat_ids:
            return
        self._queued_chat_ids.add(chat_id)
        self._in_flight += 1
        create_background_task(self._process_with_tracking(msg))

    async def _process_with_tracking(self, msg: dict[str, Any]) -> None:
        chat_id = str(msg.get("id") or "")
        try:
            await self._process_chat_message(msg)
        finally:
            if chat_id:
                self._queued_chat_ids.discard(chat_id)
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
            await asyncio.to_thread(self._bridge.mark_chat_processing, chat_id)

            from mc.infrastructure.agents.yaml_validator import validate_agent_file
            from mc.infrastructure.config import AGENTS_DIR

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

            agent_prompt = inject_orientation(agent_name, agent_prompt, bridge=self._bridge)

            # Resolve tier references
            from mc.types import is_cc_model, is_tier_reference

            channel_board = await self._resolve_channel_board_binding()

            if agent_model and is_tier_reference(agent_model):
                from mc.infrastructure.providers.tier_resolver import TierResolver

                resolver = TierResolver(self._bridge)
                agent_model = resolver.resolve_model(agent_model)

            # All chat — CC and non-CC — goes through the headless provider-cli path.
            engine_result = await self._run_chat(
                agent_name=agent_name,
                agent_model=agent_model,
                agent_prompt=agent_prompt,
                agent_skills=agent_skills,
                agent_display_name=agent_display_name,
                agent_data_full=agent_data_full,
                content=content,
                channel_board=channel_board,
                is_cc=bool(agent_model and is_cc_model(agent_model)),
            )

            if not engine_result.success:
                raise RuntimeError(
                    engine_result.error_message or f"Execution failed for chat with @{agent_name}"
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
            await asyncio.to_thread(self._bridge.mark_chat_done, chat_id)

            logger.info("[chat] Response sent for @%s", agent_name)

        except Exception as exc:
            logger.exception("[chat] Error processing chat for @%s: %s", agent_name, exc)
            # Mark original as done to avoid re-processing
            try:
                await asyncio.to_thread(self._bridge.mark_chat_done, chat_id)
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

    async def _run_chat(
        self,
        *,
        agent_name: str,
        agent_model: str | None,
        agent_prompt: str | None,
        agent_skills: list[str] | None,
        agent_display_name: str,
        agent_data_full: Any | None,
        content: str,
        channel_board: dict[str, Any] | None,
        is_cc: bool,
    ) -> ExecutionResult:
        """Execute chat through the headless provider-cli engine.

        All chat — CC and non-CC models — goes through PROVIDER_CLI
        (``-p`` flag, JSONL output, no TUI).  For CC models, the agent
        data is enriched with Convex metadata (claude_code_opts, etc.)
        and session IDs are persisted for continuity.
        """
        agent_data = self._build_chat_agent_data(
            agent_name=agent_name,
            agent_model=agent_model,
            agent_display_name=agent_display_name,
            agent_data_full=agent_data_full,
            is_cc=is_cc,
        )

        if is_cc:
            await self._enrich_agent_from_convex(agent_data, agent_name, agent_display_name)

        task_id = f"chat-{agent_name}"
        session_key = f"mc-chat:{agent_name}"

        # Build prompt with system instructions
        message = content
        if agent_prompt:
            message = f"[System instructions]\n{agent_prompt}\n\n[Chat message]\n{content}"

        request = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id=task_id,
            task_id=task_id,
            title=message,
            board=channel_board,
            board_name=channel_board.get("name") if isinstance(channel_board, dict) else None,
            agent=agent_data,
            agent_name=agent_name,
            agent_prompt=agent_prompt,
            agent_model=agent_model,
            agent_skills=agent_skills,
            runner_type=RunnerType.PROVIDER_CLI,
            session_key=session_key,
            is_cc=is_cc,
        )

        from mc.application.execution.post_processing import build_execution_engine

        engine = build_execution_engine(bridge=self._bridge)
        engine_result = await engine.run(request)

        # Persist session for CC chat continuity
        if is_cc and engine_result.session_id:
            settings_key = f"cc_session:{agent_name}:chat"
            try:
                await asyncio.to_thread(
                    self._bridge.mutation,
                    "settings:set",
                    {"key": settings_key, "value": engine_result.session_id},
                )
            except Exception:
                logger.warning("[chat] Failed to persist CC session for %s", agent_name)

        return engine_result

    @staticmethod
    def _build_chat_agent_data(
        *,
        agent_name: str,
        agent_model: str | None,
        agent_display_name: str,
        agent_data_full: Any | None,
        is_cc: bool,
    ) -> AgentData:
        """Build AgentData for chat, setting CC-specific fields when needed."""
        from mc.types import AgentData, extract_cc_model_name

        model = extract_cc_model_name(agent_model) if is_cc and agent_model else agent_model

        if agent_data_full:
            agent_data_full.model = model
            if is_cc:
                agent_data_full.backend = "claude-code"
            return agent_data_full

        return AgentData(
            name=agent_name,
            display_name=agent_display_name,
            role="agent",
            model=model,
            backend="claude-code" if is_cc else None,
        )

    async def _enrich_agent_from_convex(
        self,
        agent_data: AgentData,
        agent_name: str,
        agent_display_name: str,
    ) -> None:
        """Enrich AgentData with Convex metadata (claude_code_opts, role, etc.)."""
        from mc.types import ClaudeCodeOpts

        try:
            convex_agent_raw = await asyncio.to_thread(self._bridge.get_agent_by_name, agent_name)
            if convex_agent_raw:
                agent_data.display_name = convex_agent_raw.get("display_name", agent_display_name)
                agent_data.role = convex_agent_raw.get("role", "agent")
                cc_opts_raw = convex_agent_raw.get("claude_code_opts")
                if cc_opts_raw and isinstance(cc_opts_raw, dict):
                    agent_data.claude_code_opts = ClaudeCodeOpts(
                        max_budget_usd=cc_opts_raw.get("max_budget_usd"),
                        max_turns=cc_opts_raw.get("max_turns"),
                        permission_mode=cc_opts_raw.get("permission_mode", "bypassPermissions"),
                        allowed_tools=cc_opts_raw.get("allowed_tools"),
                        disallowed_tools=cc_opts_raw.get("disallowed_tools"),
                    )
        except Exception:
            logger.warning("[chat] Could not enrich agent data from Convex for @%s", agent_name)

    async def _resolve_channel_board_binding(self) -> dict[str, Any] | None:
        """Bind board-scoped official-channel resources to the default board."""
        try:
            board = await asyncio.to_thread(self._bridge.get_default_board)
            if isinstance(board, dict):
                logger.info(
                    "[chat] Bound official-channel request to default board '%s'",
                    board.get("name", "<unknown>"),
                )
                return board
            return None
        except Exception:
            logger.warning(
                "[chat] Failed to resolve default board for official-channel binding",
                exc_info=True,
            )
            return None
