"""ProviderCliRunnerStrategy — executes tasks via the generic provider CLI session core.

This strategy is provider-agnostic: it delegates to any ProviderCLIParser
implementation (e.g. ClaudeCodeCLIParser, CodexCLIParser).  The parser
encapsulates all provider-specific logic; the strategy only orchestrates the
execution lifecycle.

Story 28.2 wires Claude Code as the first provider.
Story 28.18 adds LiveStreamProjector and supervision_sink wiring.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mc.application.execution.request import (
    ErrorCategory,
    ExecutionRequest,
    ExecutionResult,
)
from mc.contexts.provider_cli.registry import ProviderSessionRegistry
from mc.contexts.provider_cli.types import ParsedCliEvent, SessionStatus

if TYPE_CHECKING:
    from mc.runtime.provider_cli.live_stream import LiveStreamProjector

logger = logging.getLogger(__name__)

DEFAULT_STREAM_IDLE_TIMEOUT_SECONDS = 300.0
DEFAULT_EXIT_TIMEOUT_SECONDS = 30.0
DEFAULT_STARTUP_TIMEOUT_SECONDS = 30.0


class ProviderCliRunnerStrategy:
    """Run agent work through the provider CLI session core.

    Provider-agnostic: any ProviderCLIParser implementation can be injected.
    The strategy owns the execution lifecycle:
      1. Launch the provider CLI process via the parser's start_session.
      2. Register the session in ProviderSessionRegistry.
      3. Stream and parse output via the parser.
      4. Wait for process exit and return ExecutionResult.

    Provider-specific concerns (JSON format, session ID discovery, resume
    semantics) are entirely inside the parser.

    Optional wiring (Story 28-18):
      - projector: LiveStreamProjector — projects each ParsedCliEvent into an
        ordered, timestamped stream so downstream subscribers can observe activity.
      - supervision_sink: callable — receives a normalized dict payload for each
        projected event, enabling the gateway to route events into the supervision
        pipeline (e.g. InteractiveExecutionSupervisor.handle_event).
    """

    def __init__(
        self,
        *,
        parser: Any,
        registry: ProviderSessionRegistry,
        supervisor: Any,
        command: list[str],
        cwd: str,
        projector: LiveStreamProjector | None = None,
        supervision_sink: Callable[[dict[str, Any]], None] | None = None,
        control_plane: Any | None = None,
        bridge: Any | None = None,
        startup_timeout_seconds: float = DEFAULT_STARTUP_TIMEOUT_SECONDS,
        stream_idle_timeout_seconds: float = DEFAULT_STREAM_IDLE_TIMEOUT_SECONDS,
        exit_timeout_seconds: float = DEFAULT_EXIT_TIMEOUT_SECONDS,
    ) -> None:
        self._parser = parser
        self._registry = registry
        self._supervisor = supervisor
        self._command = command
        self._cwd = cwd
        self._projector = projector
        self._control_plane = control_plane
        self._supervision_sink = supervision_sink
        self._bridge = bridge
        self._startup_timeout_seconds = startup_timeout_seconds
        self._stream_idle_timeout_seconds = stream_idle_timeout_seconds
        self._exit_timeout_seconds = exit_timeout_seconds

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute a task via the provider CLI backend.

        Returns ExecutionResult.  Never raises for expected failures.
        """
        try:
            return await self._run(request)
        except Exception as exc:
            logger.error(
                "[provider-cli-strategy] Runner error for task '%s': %s",
                request.title,
                exc,
            )
            return ExecutionResult(
                success=False,
                error_category=ErrorCategory.RUNNER,
                error_message=f"{type(exc).__name__}: {exc}",
                error_exception=exc,
            )

    def _build_command(self, request: ExecutionRequest) -> list[str]:
        """Build the full command for the provider CLI process.

        Inserts ``-p <request.prompt>`` immediately after the binary (position 1)
        when the request carries a non-empty prompt, then appends the remaining
        base-command flags and any agent-specific runtime flags.

        The base command list stored in ``self._command`` is never mutated —
        a new list is always returned.

        Claude CLI contract:
            claude -p "prompt text" --verbose --output-format stream-json ...
        """
        binary = self._command[0]
        rest_of_base = list(self._command[1:])

        command: list[str] = [binary]

        # The prompt must appear immediately after the binary so that the Claude
        # CLI interprets it as the positional print-mode argument.
        if request.prompt:
            command.extend(["-p", request.prompt])

        command.extend(rest_of_base)

        # Agent-specific runtime flags (model, permissions, tools, MCP config)
        agent = request.agent
        if agent is not None:
            # MCP config — derived from memory workspace if available
            mcp_config = self._resolve_mcp_config_path(request)
            if mcp_config is not None:
                command.extend(["--mcp-config", str(mcp_config)])

            # Model — strip cc/ prefix if present
            model = request.model or (agent.model if agent.model else None)
            if model:
                if model.startswith("cc/"):
                    model = model[3:]
                command.extend(["--model", model])

            # Permission mode and tool lists from claude_code_opts
            cc_opts = agent.claude_code_opts
            if cc_opts is not None:
                if cc_opts.permission_mode:
                    command.extend(["--permission-mode", cc_opts.permission_mode])

                if cc_opts.allowed_tools:
                    for tool in cc_opts.allowed_tools:
                        command.extend(["--allowedTools", tool])
                # Always allow the nanobot MCP tool namespace
                command.extend(["--allowedTools", "mcp__mc__*"])

                if cc_opts.disallowed_tools:
                    for tool in cc_opts.disallowed_tools:
                        command.extend(["--disallowedTools", tool])

                if cc_opts.effort_level:
                    command.extend(["--effort", cc_opts.effort_level])

        return command

    def _resolve_mcp_config_path(self, request: ExecutionRequest) -> Path | None:
        """Resolve the most specific .mcp.json for this execution request.

        `memory_workspace` may already point at the agent workspace root
        (`.../agents/{agent}`) or at its `memory/` child. Prefer the board-scoped
        workspace when present, then fall back to the global agent workspace.
        """
        candidates: list[Path] = []

        memory_workspace = request.memory_workspace
        if memory_workspace is not None:
            workspace = memory_workspace
            candidates.append(workspace)
            if workspace.name == "memory":
                candidates.append(workspace.parent)
            else:
                candidates.append(workspace / "memory")

        agent_name = request.agent_name or (request.agent.name if request.agent else "")
        if agent_name:
            from mc.infrastructure.config import AGENTS_DIR

            candidates.append(AGENTS_DIR / agent_name)

        seen: set[Path] = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            mcp_config = candidate / ".mcp.json"
            if mcp_config.exists():
                self._ensure_convex_env_in_mcp_config(mcp_config)
                return mcp_config
        return None

    def _ensure_convex_env_in_mcp_config(self, mcp_config: Path) -> None:
        """Patch the resolved MCP config so bridge subprocesses can use Convex directly."""
        self._patch_mcp_config_env(
            mcp_config,
            {
                "CONVEX_URL": os.environ.get("CONVEX_URL"),
                "CONVEX_ADMIN_KEY": os.environ.get("CONVEX_ADMIN_KEY"),
            },
        )

    def _patch_mcp_config_env(
        self,
        mcp_config: Path,
        env_overrides: Mapping[str, str | None],
    ) -> None:
        """Patch env vars into the resolved MCP config, omitting ``None`` values."""
        filtered_overrides = {
            key: value for key, value in env_overrides.items() if value is not None and value != ""
        }
        if not filtered_overrides:
            return
        try:
            raw = json.loads(mcp_config.read_text(encoding="utf-8"))
        except Exception:
            logger.debug(
                "[provider-cli-strategy] Failed to read MCP config %s for env patch",
                mcp_config,
                exc_info=True,
            )
            return
        servers = raw.get("mcpServers")
        if not isinstance(servers, dict):
            return
        changed = False
        for server in servers.values():
            if not isinstance(server, dict):
                continue
            env = server.setdefault("env", {})
            if not isinstance(env, dict):
                continue
            for key, value in filtered_overrides.items():
                if env.get(key) != value:
                    env[key] = value
                    changed = True
        if changed:
            mcp_config.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    def _materialize_session_mcp_config(
        self,
        *,
        command: list[str],
        runtime_env: dict[str, str],
        mc_session_id: str,
    ) -> Path | None:
        try:
            config_index = command.index("--mcp-config")
        except ValueError:
            return None
        if config_index + 1 >= len(command):
            return None

        shared_config = Path(command[config_index + 1])
        if not shared_config.exists():
            return None

        runtime_dir = shared_config.parent / ".mc-runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        session_hash = hashlib.sha1(mc_session_id.encode("utf-8")).hexdigest()[:10]
        session_config = runtime_dir / f"{session_hash}.mcp.json"
        shutil.copyfile(shared_config, session_config)
        self._patch_mcp_config_env(session_config, runtime_env)
        command[config_index + 1] = str(session_config)
        return session_config

    def _resolve_overflow_dir(self, session_id: str) -> Path | None:
        """Return the overflow directory for large content, or None."""
        try:
            # Extract task_id from session_id (format: {task_id}-{entity_id})
            task_id = session_id.split("-")[0] if "-" in session_id else session_id
            tasks_dir = Path.home() / ".nanobot" / "tasks"
            return tasks_dir / task_id / "output" / "_overflow"
        except Exception:
            return None

    def _cleanup(self, mc_session_id: str) -> None:
        """Remove the session record from the registry after execution completes."""
        if self._control_plane is not None:
            self._control_plane.unregister_parser(mc_session_id)
        self._registry.remove(mc_session_id)

    async def _stop_and_cleanup(self, handle: Any) -> None:
        """Best-effort process stop followed by registry/control-plane cleanup."""
        try:
            await self._parser.stop(handle)
        except Exception:
            logger.warning(
                "[provider-cli-strategy] Failed to stop session '%s' during cleanup",
                handle.mc_session_id,
                exc_info=True,
            )
        self._cleanup(handle.mc_session_id)

    async def _read_stream_chunk(
        self,
        stream_iter: Any,
    ) -> bytes:
        try:
            return await asyncio.wait_for(
                anext(stream_iter),
                timeout=self._stream_idle_timeout_seconds,
            )
        except StopAsyncIteration:
            raise
        except TimeoutError as exc:
            raise RuntimeError(
                "Provider CLI stream output timed out after "
                f"{self._stream_idle_timeout_seconds} seconds"
            ) from exc

    async def _wait_for_exit(self, handle: Any) -> int | None:
        try:
            return await asyncio.wait_for(
                self._supervisor.wait_for_exit(handle),
                timeout=self._exit_timeout_seconds,
            )
        except TimeoutError as exc:
            raise RuntimeError(
                f"Provider CLI process exit timed out after {self._exit_timeout_seconds} seconds"
            ) from exc

    async def _start_session(
        self,
        *,
        mc_session_id: str,
        command: list[str],
        env: dict[str, str] | None = None,
    ) -> Any:
        logger.info(
            "[provider-cli-strategy] Starting provider session '%s' (provider=%s)",
            mc_session_id,
            self._parser.provider_name,
        )
        try:
            handle = await asyncio.wait_for(
                self._parser.start_session(
                    mc_session_id=mc_session_id,
                    command=command,
                    cwd=self._cwd,
                    env=env,
                ),
                timeout=self._startup_timeout_seconds,
            )
        except TimeoutError as exc:
            raise RuntimeError(
                f"Provider CLI start session timed out after {self._startup_timeout_seconds} seconds"
            ) from exc
        logger.info(
            "[provider-cli-strategy] Provider session '%s' started (pid=%s)",
            mc_session_id,
            getattr(handle, "pid", None),
        )
        return handle

    def _persist_session_to_convex(
        self,
        mc_session_id: str,
        *,
        agent_name: str,
        provider: str,
        task_id: str | None,
        step_id: str | None,
        bootstrap_prompt: str | None,
        provider_session_id: str | None = None,
        status: str = "ready",
        ended_at: str | None = None,
        final_result: str | None = None,
        last_error: str | None = None,
    ) -> None:
        """Persist a new provider-cli session record to interactiveSessions in Convex.

        Project provider-cli runtime state into the interactiveSessions surface model.

        The Convex schema does not expose the internal provider-cli lifecycle
        states (running, stopped, crashed). Instead, active sessions map to
        ``ready``, normal termination maps to ``ended``, and failures map to
        ``error``.
        """
        if self._bridge is None:
            return
        timestamp = datetime.now(UTC).isoformat()
        metadata: dict[str, Any] = {
            "session_id": mc_session_id,
            "agent_name": agent_name,
            "provider": provider,
            "scope_kind": "task",
            "scope_id": task_id,
            "surface": "provider-cli",
            "tmux_session": mc_session_id,
            "status": status,
            "capabilities": [],
            "updated_at": timestamp,
            "task_id": task_id,
        }
        if step_id is not None:
            metadata["step_id"] = step_id
        if bootstrap_prompt is not None:
            metadata["bootstrap_prompt"] = bootstrap_prompt
        if provider_session_id is not None:
            metadata["provider_session_id"] = provider_session_id
        if ended_at is not None:
            metadata["ended_at"] = ended_at
        if final_result is not None:
            metadata["final_result"] = final_result
            metadata["final_result_source"] = "provider-cli"
            metadata["final_result_at"] = timestamp
        if last_error is not None:
            metadata["last_error"] = last_error
        self._bridge.mutation("interactiveSessions:upsert", metadata)

    def _patch_provider_cli_metadata(
        self,
        mc_session_id: str,
        **fields: Any,
    ) -> None:
        """Patch provider-cli specific fields on an existing interactiveSessions record.

        Called when providerSessionId is discovered (AC #2) and on cleanup (AC #4).
        No-op when bridge is None or when no fields are provided.
        """
        if self._bridge is None:
            return
        if not fields:
            return
        payload: dict[str, Any] = {"session_id": mc_session_id}
        payload.update(fields)
        self._bridge.mutation("interactiveSessions:patchProviderCliMetadata", payload)

    def _append_activity_log(
        self,
        *,
        session_id: str,
        event: ParsedCliEvent,
        timestamp: str,
        step_id: str | None,
        agent_name: str,
        provider: str,
    ) -> None:
        """Persist provider-cli activity events for dashboard Live surfaces."""
        if self._bridge is None:
            return

        payload: dict[str, Any] = {
            "session_id": session_id,
            "kind": event.kind,
            "ts": timestamp,
            "agent_name": agent_name,
            "provider": provider,
        }
        if step_id is not None:
            payload["step_id"] = step_id

        if event.kind == "tool_use":
            metadata = event.metadata or {}
            payload["tool_name"] = metadata.get("tool_name") or event.text or "tool_use"
            tool_input = metadata.get("tool_input")
            if tool_input is not None:
                if isinstance(tool_input, str):
                    payload["tool_input"] = tool_input
                else:
                    payload["tool_input"] = json.dumps(
                        tool_input, ensure_ascii=True, sort_keys=True
                    )
            payload["summary"] = payload["tool_name"]
        elif event.kind == "error":
            payload["error"] = event.text or "Provider CLI error"
        else:
            if event.text:
                payload["summary"] = event.text

        # Canonical Live metadata (Story 2.1)
        metadata = event.metadata or {}
        source_type = metadata.get("source_type")
        if source_type is not None:
            payload["source_type"] = source_type
        source_subtype = metadata.get("source_subtype")
        if source_subtype is not None:
            payload["source_subtype"] = source_subtype

        # Group key: only set when the parser provides an explicit turn boundary.
        # Do NOT fall back to provider_session_id — that is identical for all events
        # in a session and would collapse everything into one group.
        turn_id = metadata.get("turn_id")
        if turn_id is not None:
            payload["group_key"] = turn_id

        # Raw content preservation — apply Convex overflow protection
        from mc.bridge.overflow import safe_string_for_convex

        overflow_dir = self._resolve_overflow_dir(session_id)
        if event.text is not None:
            payload["raw_text"] = safe_string_for_convex(
                event.text,
                field_name="raw_text",
                task_id=session_id,
                overflow_dir=overflow_dir,
            )
        raw_json_data = metadata.get("tool_input") or metadata.get("raw_json")
        if raw_json_data is not None:
            raw_str = (
                raw_json_data
                if isinstance(raw_json_data, str)
                else json.dumps(raw_json_data, ensure_ascii=True)
            )
            payload["raw_json"] = safe_string_for_convex(
                raw_str,
                field_name="raw_json",
                task_id=session_id,
                overflow_dir=overflow_dir,
            )

        self._bridge.mutation("sessionActivityLog:append", payload)

    async def _run(self, request: ExecutionRequest) -> ExecutionResult:
        """Core execution — raises on failure for the outer handler."""
        mc_session_id = f"{request.task_id}-{request.entity_id}"

        # 1. Build the full command, injecting the bootstrap prompt
        command = self._build_command(request)
        runtime_env = self._build_runtime_env(request=request, mc_session_id=mc_session_id)
        self._materialize_session_mcp_config(
            command=command,
            runtime_env=runtime_env,
            mc_session_id=mc_session_id,
        )

        # 2. Launch the provider CLI process
        handle = await self._start_session(
            mc_session_id=mc_session_id,
            command=command,
            env=runtime_env,
        )

        # 3. Register the session with bootstrap prompt metadata
        bootstrap_prompt = (request.prompt or "")[:500] or None
        record = self._registry.create(
            mc_session_id=handle.mc_session_id,
            provider=self._parser.provider_name,
            pid=handle.pid,
            pgid=handle.pgid,
            mode="provider-native",
            supports_resume=True,
            supports_interrupt=True,
            supports_stop=True,
            bootstrap_prompt=bootstrap_prompt,
        )

        # 3b. Persist session metadata to Convex (Story 28-29, AC #1)
        try:
            self._persist_session_to_convex(
                handle.mc_session_id,
                agent_name=request.agent_name,
                provider=self._parser.provider_name,
                task_id=request.task_id,
                step_id=request.step_id,
                bootstrap_prompt=bootstrap_prompt,
            )
        except Exception:
            try:
                await self._parser.stop(handle)
            except Exception:
                logger.warning(
                    "[provider-cli-strategy] Failed to stop session '%s' after Convex startup "
                    "persistence error",
                    handle.mc_session_id,
                    exc_info=True,
                )
            self._cleanup(handle.mc_session_id)
            raise

        # 4. Transition to RUNNING
        self._registry.update_status(handle.mc_session_id, SessionStatus.RUNNING)

        # 4b. Register parser/handle in control plane for intervention routing
        if self._control_plane is not None:
            self._control_plane.register_parser(
                handle.mc_session_id, parser=self._parser, handle=handle
            )

        # 5. Stream and parse output
        collected_events: list[ParsedCliEvent] = []
        try:
            stream_iter = self._supervisor.stream_output(handle).__aiter__()
            while True:
                try:
                    chunk = await self._read_stream_chunk(stream_iter)
                except StopAsyncIteration:
                    break
                if not chunk:
                    continue
                events = self._parser.parse_output(chunk)
                for event in events:
                    collected_events.append(event)
                    projected_timestamp = datetime.now(UTC).isoformat()
                    # Update registry with discovered session ID
                    if event.kind == "session_id" and event.provider_session_id:
                        self._registry.update_provider_session_id(
                            handle.mc_session_id, event.provider_session_id
                        )
                        record.provider_session_id = event.provider_session_id
                        # Persist provider_session_id to Convex (Story 28-29, AC #2)
                        self._patch_provider_cli_metadata(
                            handle.mc_session_id,
                            provider_session_id=event.provider_session_id,
                        )
                    # Project the event through the live stream projector (Story 28-18)
                    if self._projector is not None:
                        projected = self._projector.project(event, session_id=mc_session_id)
                        projected_timestamp = projected.timestamp
                        # Deliver normalized payload to supervision sink if wired
                        if self._supervision_sink is not None:
                            self._supervision_sink(
                                {
                                    "session_id": mc_session_id,
                                    "provider": self._parser.provider_name,
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
                    self._append_activity_log(
                        session_id=mc_session_id,
                        event=event,
                        timestamp=projected_timestamp,
                        step_id=request.step_id,
                        agent_name=request.agent_name,
                        provider=self._parser.provider_name,
                    )
        except Exception:
            await self._stop_and_cleanup(handle)
            raise

        # 6. Wait for exit
        try:
            exit_code = await self._wait_for_exit(handle)
        except Exception:
            await self._stop_and_cleanup(handle)
            raise

        # 7. Evaluate result
        error_events = [e for e in collected_events if e.kind == "error"]
        result_events = [e for e in collected_events if e.kind == "result"]
        text_events = [e for e in collected_events if e.kind == "text"]

        # Discover session ID
        session_id = record.provider_session_id
        if session_id is None:
            sid_events = [e for e in collected_events if e.kind == "session_id"]
            session_id = sid_events[0].provider_session_id if sid_events else None

        # Determine output text:
        #   1. canonical: last result event text
        #   2. fallback: concatenation of all text events (when no result event)
        output_text = ""
        if result_events:
            output_text = result_events[-1].text or ""
        elif text_events:
            output_text = "".join(e.text or "" for e in text_events)
        elif error_events:
            output_text = error_events[0].text or ""

        # Determine success
        current_status = record.status
        has_error = bool(error_events) or (exit_code is not None and exit_code != 0)

        if current_status == SessionStatus.STOPPED:
            error_msg = "Session stopped by operator."
            record.update_metadata(last_error=error_msg)
            self._persist_session_to_convex(
                handle.mc_session_id,
                agent_name=request.agent_name,
                provider=self._parser.provider_name,
                task_id=request.task_id,
                step_id=request.step_id,
                bootstrap_prompt=bootstrap_prompt,
                provider_session_id=session_id,
                status="error",
                ended_at=datetime.now(UTC).isoformat(),
                last_error=error_msg,
            )
            self._cleanup(handle.mc_session_id)
            return ExecutionResult(
                success=False,
                error_category=ErrorCategory.RUNNER,
                error_message=error_msg,
                session_id=session_id,
            )

        if has_error:
            if error_events:
                error_msg = error_events[0].text
            elif text_events:
                # Prefer captured text output over a generic exit-code message so
                # that diagnostic messages printed by the CLI (e.g. "Not logged in")
                # are surfaced directly to the caller.
                error_msg = "".join(e.text or "" for e in text_events)
            else:
                error_msg = f"Process exited with code {exit_code}"
            if current_status != SessionStatus.CRASHED:
                self._registry.update_status(handle.mc_session_id, SessionStatus.CRASHED)
            record.update_metadata(last_error=error_msg)
            self._persist_session_to_convex(
                handle.mc_session_id,
                agent_name=request.agent_name,
                provider=self._parser.provider_name,
                task_id=request.task_id,
                step_id=request.step_id,
                bootstrap_prompt=bootstrap_prompt,
                provider_session_id=session_id,
                status="error",
                ended_at=datetime.now(UTC).isoformat(),
                last_error=error_msg,
            )
            self._cleanup(handle.mc_session_id)
            return ExecutionResult(
                success=False,
                error_category=ErrorCategory.RUNNER,
                error_message=error_msg,
                session_id=session_id,
            )

        self._registry.update_status(handle.mc_session_id, SessionStatus.COMPLETED)
        record.update_metadata(final_result=output_text[:500] if output_text else None)
        self._persist_session_to_convex(
            handle.mc_session_id,
            agent_name=request.agent_name,
            provider=self._parser.provider_name,
            task_id=request.task_id,
            step_id=request.step_id,
            bootstrap_prompt=bootstrap_prompt,
            provider_session_id=session_id,
            status="ended",
            ended_at=datetime.now(UTC).isoformat(),
            final_result=output_text[:500] if output_text else None,
        )
        self._cleanup(handle.mc_session_id)
        return ExecutionResult(
            success=True,
            output=output_text,
            session_id=session_id,
        )

    def _build_runtime_env(
        self,
        *,
        request: ExecutionRequest,
        mc_session_id: str,
    ) -> dict[str, str]:
        env: dict[str, str] = {
            "AGENT_NAME": request.agent_name,
            "TASK_ID": request.task_id,
            "MC_INTERACTIVE_SESSION_ID": mc_session_id,
        }
        if request.step_id:
            env["STEP_ID"] = request.step_id
        convex_url = os.environ.get("CONVEX_URL")
        convex_admin_key = os.environ.get("CONVEX_ADMIN_KEY")
        if convex_url:
            env["CONVEX_URL"] = convex_url
        if convex_admin_key:
            env["CONVEX_ADMIN_KEY"] = convex_admin_key
        return env
