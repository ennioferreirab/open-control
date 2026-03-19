"""Claude Code runner strategy — executes tasks via the CC CLI backend.

Extracts the core Claude Code execution logic from
mc.executor.TaskExecutor._execute_cc_task into a strategy that the
ExecutionEngine can invoke uniformly.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from types import SimpleNamespace
from typing import Any

from mc.application.execution.background_tasks import create_background_task
from mc.application.execution.request import (
    ErrorCategory,
    ExecutionRequest,
    ExecutionResult,
)
from mc.types import NANOBOT_AGENT_NAME

logger = logging.getLogger(__name__)


def _collect_provider_error_types() -> tuple[type[Exception], ...]:
    """Collect provider-specific exception types for targeted catching."""
    from mc.infrastructure.providers.factory import ProviderError

    types: list[type[Exception]] = [ProviderError]
    try:
        from nanobot.providers.anthropic_oauth import AnthropicOAuthExpired

        types.append(AnthropicOAuthExpired)
    except ImportError:
        pass
    return tuple(types)


_PROVIDER_ERRORS = _collect_provider_error_types()


class _CCStrategyAdapter:
    """Lightweight adapter that reuses CC helper methods outside TaskExecutor."""

    def __init__(
        self,
        *,
        bridge: Any,
        cron_service: Any | None = None,
        ask_user_registry: Any | None = None,
    ) -> None:
        from mc.contexts.execution.cc_executor import CCExecutorMixin

        class _Adapter(CCExecutorMixin):
            def __init__(self) -> None:
                self._bridge = bridge
                self._cron_service = cron_service
                self._ask_user_registry = ask_user_registry
                self._agent_gateway = SimpleNamespace()
                self._on_task_completed = None

        self._delegate = _Adapter()

    async def sync_agent(self, agent_name: str, agent_data: Any) -> dict[str, Any] | None:
        return await self._delegate._sync_cc_convex_agent(agent_name, agent_data)

    async def resolve_board(
        self,
        task_data: dict[str, Any] | None,
        agent_name: str,
        title: str,
    ) -> tuple[str | None, str]:
        return await self._delegate._resolve_cc_board(task_data, agent_name, title)

    async def lookup_session(self, agent_name: str, task_id: str) -> str | None:
        return await self._delegate._lookup_cc_session(agent_name, task_id)

    async def post_activity(self, task_id: str, agent_name: str, text: str) -> None:
        await self._delegate._post_cc_activity(task_id, agent_name, text)


class ClaudeCodeRunnerStrategy:
    """Runs agent work through the Claude Code CLI.

    Mirrors the execution path in mc.executor.TaskExecutor._execute_cc_task()
    but returns a structured ExecutionResult instead of directly mutating
    task state.
    """

    def __init__(
        self,
        *,
        bridge: Any | None = None,
        cron_service: Any | None = None,
        ask_user_registry: Any | None = None,
    ) -> None:
        self._bridge = bridge
        self._cron_service = cron_service
        self._ask_user_registry = ask_user_registry

    def _build_agent_data(self, request: ExecutionRequest) -> Any:
        from mc.types import AgentData, extract_cc_model_name, is_cc_model

        if request.agent is not None:
            agent_data = replace(request.agent)
        else:
            model_name = request.model or request.agent_model or ""
            if model_name and is_cc_model(model_name):
                model_name = extract_cc_model_name(model_name)
            agent_data = AgentData(
                name=request.agent_name,
                display_name=request.agent_name,
                role="agent",
                model=model_name or None,
                backend="claude-code",
            )

        agent_data.backend = "claude-code"
        if request.agent_prompt:
            agent_data.prompt = request.agent_prompt
        if request.agent_skills is not None:
            agent_data.skills = request.agent_skills
        if request.model:
            agent_data.model = request.model
        elif request.agent_model:
            agent_data.model = request.agent_model

        logger.info(
            "[cc-strategy] Agent '%s' built: skills=%s, model=%s",
            agent_data.name,
            agent_data.skills,
            agent_data.model,
        )
        return agent_data

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute a task via the Claude Code CLI backend.

        Orchestrates workspace preparation, IPC server startup, CC provider
        execution, and returns structured results. Any phase failure is
        returned as an error result rather than raised.
        """
        try:
            return await self._run_cc(request)
        except _PROVIDER_ERRORS as exc:
            logger.error(
                "[cc-strategy] Provider error for task '%s': %s",
                request.title,
                exc,
            )
            return ExecutionResult(
                success=False,
                error_category=ErrorCategory.PROVIDER,
                error_message=str(exc),
                error_exception=exc,
            )
        except Exception as exc:
            logger.error(
                "[cc-strategy] Runner error for task '%s': %s",
                request.title,
                exc,
            )
            return ExecutionResult(
                success=False,
                error_category=ErrorCategory.RUNNER,
                error_message=f"{type(exc).__name__}: {exc}",
                error_exception=exc,
            )

    async def _run_cc(self, request: ExecutionRequest) -> ExecutionResult:
        """Core CC execution — raises on failure for the outer handler."""
        from claude_code.ipc_server import MCSocketServer
        from claude_code.provider import ClaudeCodeProvider
        from claude_code.workspace import CCWorkspaceManager

        from mc.infrastructure.orientation import load_orientation

        adapter = _CCStrategyAdapter(
            bridge=self._bridge,
            cron_service=self._cron_service,
            ask_user_registry=self._ask_user_registry,
        )
        agent_data = self._build_agent_data(request)
        # NOTE: The context_builder already synced prompt, model, variables, and
        # skills from Convex.  The old executor had a redundant _sync_cc_convex_agent
        # call here that could silently override skills with stale Convex data.
        # Removed to keep a single source of truth (context_builder).

        if request.reasoning_level:
            effort_map = {
                "low": "low",
                "medium": "medium",
                "high": "high",
                "max": "high",
            }
            effort = effort_map.get(request.reasoning_level, "high")
            if agent_data.claude_code_opts is None:
                from claude_code.types import ClaudeCodeOpts

                agent_data.claude_code_opts = ClaudeCodeOpts()
            agent_data.claude_code_opts.effort_level = effort

        board_name = request.board_name
        memory_mode = "clean"
        if self._bridge is not None:
            resolved_board_name, memory_mode = await adapter.resolve_board(
                request.task_data,
                request.agent_name,
                request.title,
            )
            board_name = resolved_board_name or board_name

        if not board_name and request.agent_name != NANOBOT_AGENT_NAME:
            raise RuntimeError(
                f"Task '{request.title}' has no board — non-nanobot agent "
                f"'{request.agent_name}' requires a board-scoped workspace."
            )

        # Prepare workspace
        ws_mgr = CCWorkspaceManager()

        orientation = load_orientation(request.agent_name, bridge=self._bridge)
        ws_ctx = ws_mgr.prepare(
            request.agent_name,
            agent_data,
            request.task_id,
            orientation=orientation,
            task_prompt=request.title,
            board_name=board_name,
            memory_mode=memory_mode,
        )

        from mc.contexts.conversation.ask_user.handler import AskUserHandler

        ask_handler = AskUserHandler()
        ipc_server = MCSocketServer(
            self._bridge,
            None,
            cron_service=self._cron_service,
        )
        ipc_server.set_ask_user_handler(ask_handler)
        if self._ask_user_registry is not None:
            self._ask_user_registry.register(request.task_id, ask_handler)

        # Execute via CC provider
        from nanobot.config.loader import load_config

        _cfg = load_config()
        provider = ClaudeCodeProvider(
            cli_path=_cfg.claude_code.cli_path,
            defaults=_cfg.claude_code,
        )

        prompt = request.title
        if request.description:
            prompt = f"{request.title}\n\n{request.description}"

        session_id: str | None = None
        if request.is_task and self._bridge is not None:
            session_id = await adapter.lookup_session(
                request.agent_name,
                request.task_id,
            )

        def on_stream(msg: dict[str, Any]) -> None:
            if msg.get("type") != "text":
                return
            if self._bridge is None:
                return
            create_background_task(
                adapter.post_activity(
                    request.task_id,
                    request.agent_name,
                    msg["text"],
                )
            )

        try:
            await ipc_server.start(ws_ctx.socket_path)
            result_obj = await provider.execute_task(
                prompt=prompt,
                agent_config=agent_data,
                task_id=request.task_id,
                workspace_ctx=ws_ctx,
                session_id=session_id,
                on_stream=on_stream if request.is_task else None,
            )
        finally:
            if self._ask_user_registry is not None:
                self._ask_user_registry.unregister(request.task_id)
            await ipc_server.stop()

        if result_obj.is_error:
            return ExecutionResult(
                success=False,
                error_category=ErrorCategory.RUNNER,
                error_message=f"Claude Code error: {result_obj.output[:1000]}",
                cost_usd=result_obj.cost_usd,
                session_id=result_obj.session_id,
                memory_workspace=ws_ctx.cwd,
            )

        return ExecutionResult(
            success=True,
            output=result_obj.output,
            cost_usd=result_obj.cost_usd,
            session_id=result_obj.session_id,
            memory_workspace=ws_ctx.cwd,
        )
