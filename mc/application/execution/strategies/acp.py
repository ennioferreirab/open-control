"""AcpRunnerStrategy — executes tasks via the Agent Client Protocol SDK.

The ACP SDK owns the subprocess through AcpClient (infrastructure layer).
This strategy consumes the structured on_update push stream and maps each
update to ParsedCliEvent, then feeds the same registry / live-stream /
activity infrastructure the provider-cli path uses.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from mc.application.execution.request import ErrorCategory, ExecutionRequest, ExecutionResult
from mc.contexts.interactive.activity_service import SessionActivityService
from mc.contexts.provider_cli.registry import ProviderSessionRegistry
from mc.contexts.provider_cli.types import ParsedCliEvent, SessionStatus
from mc.infrastructure.acp.client import AcpClient
from mc.infrastructure.acp.harness_registry import get_harness, resolve_model

if TYPE_CHECKING:
    from mc.runtime.provider_cli.live_stream import LiveStreamProjector

logger = logging.getLogger(__name__)


def _acp_update_to_event(update: Any) -> ParsedCliEvent | None:
    """Map one ACP session/update object to a ParsedCliEvent, or None to skip.

    Mapping rules:
    - AgentMessageChunk with non-empty text  → kind="text"
    - ToolCallStart / ToolCallProgress       → kind="tool_use" / "tool_result"
    - UsageUpdate                            → kind="system_event"
    - Everything else (AvailableCommandsUpdate, etc.) → None
    """
    from acp.schema import (
        AgentMessageChunk,
        TextContentBlock,
        ToolCallProgress,
        ToolCallStart,
        UsageUpdate,
    )

    if isinstance(update, AgentMessageChunk):
        content = update.content
        if isinstance(content, TextContentBlock) and content.text:
            return ParsedCliEvent(
                kind="text",
                text=content.text,
                metadata={"source_type": "acp_message_chunk"},
            )
        return None

    if isinstance(update, ToolCallStart):
        return ParsedCliEvent(
            kind="tool_use",
            text=update.title,
            metadata={
                "source_type": "acp_tool_call",
                "tool_name": update.title,
                "tool_call_id": update.tool_call_id,
            },
        )

    if isinstance(update, ToolCallProgress):
        return ParsedCliEvent(
            kind="tool_result",
            text=update.title,
            metadata={
                "source_type": "acp_tool_call_progress",
                "tool_name": update.title,
                "tool_call_id": update.tool_call_id,
            },
        )

    if isinstance(update, UsageUpdate):
        metadata: dict[str, Any] = {"used_tokens": update.used, "context_size": update.size}
        if update.cost is not None:
            metadata["cost_usd"] = update.cost.amount
        return ParsedCliEvent(
            kind="system_event",
            text=None,
            metadata=metadata,
        )

    return None


class AcpRunnerStrategy:
    """Run agent work through the ACP SDK subprocess adapter.

    Shares the same ProviderSessionRegistry, LiveStreamProjector, and
    SessionActivityService infrastructure as ProviderCliRunnerStrategy.
    The AcpClient owns the subprocess; this strategy only orchestrates
    the execution lifecycle and maps the structured update stream to
    ParsedCliEvent.
    """

    def __init__(
        self,
        *,
        registry: ProviderSessionRegistry,
        harness: str = "claude-code",
        cwd: str,
        projector: LiveStreamProjector | None = None,
        supervision_sink: Callable[[dict[str, Any]], None] | None = None,
        control_plane: Any | None = None,
        bridge: Any | None = None,
    ) -> None:
        self._registry = registry
        self._harness = harness
        self._cwd = cwd
        self._projector = projector
        self._supervision_sink = supervision_sink
        self._control_plane = control_plane
        self._activity = SessionActivityService(bridge)

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute a task via the ACP backend. Never raises for expected failures."""
        try:
            return await self._run(request)
        except Exception as exc:
            self._activity.flush()
            logger.error(
                "[acp-strategy] Runner error for task '%s': %s",
                request.title,
                exc,
            )
            return ExecutionResult(
                success=False,
                error_category=ErrorCategory.RUNNER,
                error_message=f"{type(exc).__name__}: {exc}",
                error_exception=exc,
            )

    def _on_update(
        self,
        update: Any,
        mc_session_id: str,
        request: ExecutionRequest,
    ) -> None:
        """Handle one ACP session/update. Called synchronously by AcpClient."""
        event = _acp_update_to_event(update)
        if event is None:
            return

        projected_timestamp = datetime.now(UTC).isoformat()

        if self._projector is not None:
            projected = self._projector.project(event, session_id=mc_session_id)
            projected_timestamp = projected.timestamp
            if self._supervision_sink is not None:
                self._supervision_sink(
                    {
                        "session_id": mc_session_id,
                        "provider": "acp",
                        "task_id": request.task_id,
                        "step_id": request.step_id,
                        "agent_name": request.agent_name,
                        "kind": event.kind,
                        "text": event.text,
                        "provider_session_id": event.provider_session_id,
                        "metadata": event.metadata,
                        "sequence": projected.sequence,
                        "timestamp": projected.timestamp,
                    }
                )

        self._activity.append_parsed_cli_event(
            mc_session_id,
            event_kind=event.kind,
            event_text=event.text,
            event_metadata=event.metadata,
            timestamp=projected_timestamp,
            agent_name=request.agent_name,
            provider="acp",
            step_id=request.step_id,
        )

    def _build_mc_mcp(self, request: ExecutionRequest, mc_session_id: str) -> tuple[Any, list[str]]:
        """Build the mc MCP server config and allowed tools list for an ACP session."""
        import os

        from acp.schema import EnvVariable, McpServerStdio
        from claude_code.workspace import _PROJECT_ROOT

        from mc.infrastructure.secrets import resolve_secret_env

        env_dict: dict[str, str] = {
            **resolve_secret_env(),
            "AGENT_NAME": request.agent_name,
            "TASK_ID": request.task_id,
            "MC_INTERACTIVE_SESSION_ID": mc_session_id,
        }
        if request.step_id:
            env_dict["STEP_ID"] = request.step_id
        convex_url = os.environ.get("CONVEX_URL")
        convex_admin_key = os.environ.get("CONVEX_ADMIN_KEY")
        if convex_url:
            env_dict["CONVEX_URL"] = convex_url
        if convex_admin_key:
            env_dict["CONVEX_ADMIN_KEY"] = convex_admin_key

        server = McpServerStdio(
            name="mc",
            command="uv",
            args=["run", "--project", str(_PROJECT_ROOT), "python", "-m", "mc.runtime.mcp.bridge"],
            env=[EnvVariable(name=k, value=v) for k, v in env_dict.items()],
        )
        allowed = ["mcp__mc__ask_user", "mcp__mc__send_message"]
        return server, allowed

    async def _run(self, request: ExecutionRequest) -> ExecutionResult:
        """Core execution — raises on failure for the outer handler."""
        mc_session_id = f"{request.task_id}-{request.entity_id}"

        agent = getattr(request, "agent", None)
        harness_name = getattr(agent, "backend", None) or self._harness
        spec = get_harness(harness_name)
        command = list(spec.launch_command)
        model = resolve_model(spec, request.model)

        bootstrap_prompt = (request.prompt or "")[:500] or None
        self._registry.create(
            mc_session_id=mc_session_id,
            provider="acp",
            pid=0,
            pgid=None,
            mode="provider-native",
            supports_resume=False,
            supports_interrupt=True,
            supports_stop=True,
            bootstrap_prompt=bootstrap_prompt,
        )

        self._activity.upsert_session(
            mc_session_id,
            agent_name=request.agent_name,
            provider="acp",
            surface="provider-cli",
            task_id=request.task_id,
            step_id=request.step_id,
            bootstrap_prompt=bootstrap_prompt,
        )

        self._registry.update_status(mc_session_id, SessionStatus.RUNNING)

        server, allowed = self._build_mc_mcp(request, mc_session_id)
        async with AcpClient(
            command=command,
            cwd=self._cwd,
            model=model,
            mcp_servers=[server],
            allowed_tools=allowed,
            model_env=spec.model_env,
            session_param_style=spec.session_param_style,
            model_via_session=spec.model_via_session,
            env_overrides=spec.env_overrides,
        ) as client:
            if client.session_id is not None:
                self._registry.update_provider_session_id(mc_session_id, client.session_id)

            turn = await client.prompt(
                request.prompt,
                on_update=lambda u: self._on_update(u, mc_session_id, request),
            )

        self._registry.update_status(mc_session_id, SessionStatus.COMPLETED)
        self._activity.upsert_session(
            mc_session_id,
            agent_name=request.agent_name,
            provider="acp",
            surface="provider-cli",
            task_id=request.task_id,
            step_id=request.step_id,
            status="ended",
            final_result=(turn.text or "")[:500] or None,
        )
        self._registry.remove(mc_session_id)

        is_error = turn.stop_reason not in ("end_turn", "stop")
        return ExecutionResult(
            success=not is_error,
            output=turn.text,
            cost_usd=turn.cost_usd or 0.0,
            session_id=turn.session_id,
        )
