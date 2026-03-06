"""Claude Code runner strategy — executes tasks via the CC CLI backend.

Extracts the core Claude Code execution logic from
mc.executor.TaskExecutor._execute_cc_task into a strategy that the
ExecutionEngine can invoke uniformly.
"""

from __future__ import annotations

import logging

from mc.application.execution.request import (
    ErrorCategory,
    ExecutionRequest,
    ExecutionResult,
)

logger = logging.getLogger(__name__)


def _collect_provider_error_types() -> tuple[type[Exception], ...]:
    """Collect provider-specific exception types for targeted catching."""
    from mc.provider_factory import ProviderError

    types: list[type[Exception]] = [ProviderError]
    try:
        from nanobot.providers.anthropic_oauth import AnthropicOAuthExpired

        types.append(AnthropicOAuthExpired)
    except ImportError:
        pass
    return tuple(types)


_PROVIDER_ERRORS = _collect_provider_error_types()


class ClaudeCodeRunnerStrategy:
    """Runs agent work through the Claude Code CLI.

    Mirrors the execution path in mc.executor.TaskExecutor._execute_cc_task()
    but returns a structured ExecutionResult instead of directly mutating
    task state.
    """

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
            )

    async def _run_cc(self, request: ExecutionRequest) -> ExecutionResult:
        """Core CC execution — raises on failure for the outer handler."""
        from mc.types import AgentData, extract_cc_model_name, is_cc_model

        # Resolve the CC model name from the request model
        agent_model = request.agent_model or ""
        if is_cc_model(agent_model):
            cc_model_name = extract_cc_model_name(agent_model)
        else:
            cc_model_name = agent_model

        agent_data = AgentData(
            name=request.agent_name,
            display_name=request.agent_name,
            role="agent",
            model=cc_model_name,
            backend="claude-code",
        )

        # Prepare workspace
        from claude_code.provider import ClaudeCodeProvider
        from claude_code.workspace import CCWorkspaceManager

        ws_mgr = CCWorkspaceManager()
        from mc.orientation import load_orientation

        orientation = load_orientation(request.agent_name)
        ws_ctx = ws_mgr.prepare(
            request.agent_name,
            agent_data,
            request.task_id,
            orientation=orientation,
            task_prompt=request.title,
            board_name=request.board_name,
        )

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

        result_obj = await provider.execute_task(
            prompt=prompt,
            agent_config=agent_data,
            task_id=request.task_id,
            workspace_ctx=ws_ctx,
            session_id=None,
        )

        if result_obj.is_error:
            return ExecutionResult(
                success=False,
                error_category=ErrorCategory.RUNNER,
                error_message=f"Claude Code error: {result_obj.output[:1000]}",
            )

        return ExecutionResult(
            success=True,
            output=result_obj.output,
            cost_usd=result_obj.cost_usd,
            session_id=result_obj.session_id,
        )
