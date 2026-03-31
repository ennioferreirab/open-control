"""ExecutionEngine — single entry point for all task/step execution.

Story 16.2 — Centralizes strategy selection, error categorization, and
post-execution steps (memory consolidation, artifact sync, session
cleanup). Callers build an ExecutionRequest and receive an ExecutionResult
without knowing which backend ran.
"""

from __future__ import annotations

import logging
from typing import Any

from mc.application.execution.request import (
    ErrorCategory,
    ExecutionRequest,
    ExecutionResult,
    RunnerType,
)
from mc.application.execution.strategies.base import RunnerStrategy
from mc.application.execution.strategies.claude_code import ClaudeCodeRunnerStrategy
from mc.application.execution.strategies.human import HumanRunnerStrategy
from mc.application.execution.strategies.interactive import InteractiveTuiRunnerStrategy
from mc.application.execution.strategies.provider_cli import ProviderCliRunnerStrategy

logger = logging.getLogger(__name__)


def categorize_error(exc: Exception) -> ErrorCategory:
    """Normalize an exception into an ErrorCategory.

    Centralizes error classification so all callers get consistent
    categorization regardless of which runner raised.
    """
    exc_type = type(exc).__name__
    exc_module = type(exc).__module__ or ""

    # Tier resolution errors
    if isinstance(exc, ValueError) and "tier" in str(exc).lower():
        return ErrorCategory.TIER

    # Provider / OAuth errors
    try:
        from mc.infrastructure.providers.factory import ProviderError

        if isinstance(exc, ProviderError):
            return ErrorCategory.PROVIDER
    except ImportError:
        pass

    try:
        from nanobot.providers.anthropic_oauth import AnthropicOAuthExpired

        if isinstance(exc, AnthropicOAuthExpired):
            return ErrorCategory.PROVIDER
    except ImportError:
        pass

    if "oauth" in exc_type.lower() or "provider" in exc_type.lower():
        return ErrorCategory.PROVIDER

    # Workflow errors (state machine, validation)
    if "workflow" in exc_module.lower() or "state_machine" in exc_module.lower():
        return ErrorCategory.WORKFLOW

    # Default: runner error
    return ErrorCategory.RUNNER


class ExecutionEngine:
    """Single entry point for executing tasks and steps.

    Selects the appropriate RunnerStrategy based on the request's
    runner_type, runs it, and performs centralized post-execution
    steps (memory consolidation, artifact sync, session cleanup).
    """

    def __init__(
        self,
        *,
        strategies: dict[RunnerType, RunnerStrategy] | None = None,
        post_execution_hooks: list[Any] | None = None,
    ) -> None:
        """Initialize with optional strategy overrides (useful for testing).

        Args:
            strategies: Map of RunnerType to strategy instance. Defaults
                are created if not provided.
            post_execution_hooks: Optional list of callables that receive
                (request, result) after execution. Each is called in order.
        """
        if strategies is not None:
            self._strategies: dict[RunnerType, RunnerStrategy] = strategies
        else:
            from mc.contexts.provider_cli.providers.claude_code import ClaudeCodeCLIParser
            from mc.contexts.provider_cli.registry import ProviderSessionRegistry
            from mc.runtime.provider_cli.process_supervisor import ProviderProcessSupervisor

            _provider_registry = ProviderSessionRegistry()
            _provider_supervisor = ProviderProcessSupervisor()
            _provider_parser = ClaudeCodeCLIParser(supervisor=_provider_supervisor)

            self._strategies = {
                RunnerType.CLAUDE_CODE: ClaudeCodeRunnerStrategy(),
                RunnerType.HUMAN: HumanRunnerStrategy(),
                RunnerType.INTERACTIVE_TUI: InteractiveTuiRunnerStrategy(
                    bridge=None,
                    session_coordinator=None,
                ),
                RunnerType.PROVIDER_CLI: ProviderCliRunnerStrategy(
                    parser=_provider_parser,
                    registry=_provider_registry,
                    supervisor=_provider_supervisor,
                    command=["claude", "--verbose", "--output-format", "stream-json"],
                    cwd=".",
                ),
            }
        self._post_execution_hooks = (
            post_execution_hooks if post_execution_hooks is not None else []
        )

    def get_strategy(self, runner_type: RunnerType) -> RunnerStrategy:
        """Return the strategy for the given runner type.

        Raises KeyError if no strategy is registered for the type.
        """
        if runner_type not in self._strategies:
            raise KeyError(f"No strategy registered for runner type: {runner_type!r}")
        return self._strategies[runner_type]

    async def run(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute a task or step through the appropriate strategy.

        This is the single entry point. It:
        1. Selects the strategy based on request.runner_type
        2. Delegates execution to the strategy
        3. Categorizes any unexpected errors
        4. Runs post-execution hooks (memory consolidation, artifact sync)
        5. Returns a normalized ExecutionResult
        """
        logger.info(
            "[engine] Running task '%s' (runner=%s, agent=%s, step=%s)",
            request.title,
            request.runner_type.value,
            request.agent_name,
            request.step_id,
        )

        # 1. Select strategy
        try:
            strategy = self.get_strategy(request.runner_type)
        except KeyError as exc:
            logger.error("[engine] %s", exc)
            return ExecutionResult(
                success=False,
                error_category=ErrorCategory.WORKFLOW,
                error_message=str(exc),
            )

        # 2. Execute
        try:
            result = await strategy.execute(request)
        except Exception as exc:
            logger.error(
                "[engine] Unexpected error from strategy %s: %s",
                request.runner_type.value,
                exc,
                exc_info=True,
            )
            category = categorize_error(exc)
            result = ExecutionResult(
                success=False,
                error_category=category,
                error_message=f"{type(exc).__name__}: {exc}",
                error_exception=exc,
            )

        # 3. Run post-execution hooks
        await self._run_post_execution(request, result)

        logger.info(
            "[engine] Task '%s' finished (success=%s, category=%s)",
            request.title,
            result.success,
            result.error_category,
        )

        return result

    async def _run_post_execution(self, request: ExecutionRequest, result: ExecutionResult) -> None:
        """Run centralized post-execution steps.

        Post-execution runs for BOTH task and step execution, and for
        both success and failure cases. Individual hooks handle their
        own error isolation.

        Hooks are callables with signature:
            async def hook(request: ExecutionRequest, result: ExecutionResult) -> None
        """
        for hook in self._post_execution_hooks:
            try:
                await hook(request, result)
            except Exception:
                logger.warning(
                    "[engine] Post-execution hook %s failed for task '%s'",
                    getattr(hook, "__name__", repr(hook)),
                    request.title,
                    exc_info=True,
                )
