"""
ClaudeCodeProvider — runs Claude Code CLI as a headless subprocess.

Spawns `claude -p <prompt> --output-format stream-json` and streams NDJSON
messages back to the caller.  Handles cancellation, process cleanup, and
result extraction.
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
from typing import TYPE_CHECKING, AsyncIterator, Callable

from claude_code.types import CCTaskResult, WorkspaceContext
from mc.types import AgentData

if TYPE_CHECKING:
    from nanobot.config.schema import ClaudeCodeConfig

logger = logging.getLogger(__name__)

_STREAM_READER_LIMIT = 1024 * 1024


class ClaudeCodeProvider:
    """Executes prompts via the Claude Code CLI in headless mode.

    Args:
        cli_path: Path (or name on PATH) of the ``claude`` executable.
        defaults: A ``ClaudeCodeConfig`` instance providing global defaults
            for model, budget, turns, and permission mode.  Loaded lazily
            from config to avoid circular imports at import time.
    """

    def __init__(self, cli_path: str = "claude", defaults: ClaudeCodeConfig | None = None) -> None:
        self._cli = cli_path
        # ``defaults`` is a ClaudeCodeConfig from nanobot.config.schema.
        # The TYPE_CHECKING guard above provides the type annotation without
        # importing at module load time (avoiding circular imports).
        self._defaults = defaults

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute_task(
        self,
        prompt: str,
        agent_config: AgentData,
        task_id: str,
        workspace_ctx: WorkspaceContext,
        session_id: str | None = None,
        on_stream: Callable[[dict], None] | None = None,
    ) -> CCTaskResult:
        """Execute a prompt with the Claude Code CLI and return the result.

        Args:
            prompt: The user/task prompt to send.
            agent_config: Agent metadata (model, cc opts, etc.).
            task_id: Identifier for the current task (used for logging).
            workspace_ctx: Workspace paths and socket info.
            session_id: Optional Claude Code session ID to resume.
            on_stream: Optional callback invoked for each streamed
                assistant/tool message.  Receives normalized dicts:
                ``{"type": "text", "text": "..."}`` or
                ``{"type": "tool_use", "name": "..."}``.

        Returns:
            A :class:`CCTaskResult` with the final output and metadata.
        """
        cmd = self._build_command(prompt, agent_config, workspace_ctx, session_id)
        logger.debug("ClaudeCodeProvider: spawning %s (task=%s)", cmd[0], task_id)
        from mc.infrastructure.secrets import build_subprocess_env

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(workspace_ctx.cwd),
            env=build_subprocess_env(),
            limit=_STREAM_READER_LIMIT,
        )

        result = CCTaskResult(
            output="",
            session_id=session_id or "",
            cost_usd=0.0,
            usage={},
            is_error=False,
        )

        try:
            async for msg in self._parse_stream(proc):
                self._handle_message(msg, result, on_stream)
        except asyncio.CancelledError:
            logger.warning("ClaudeCodeProvider: task %s cancelled — killing process", task_id)
            await self._kill_process(proc)
            raise

        returncode = await proc.wait()
        if proc.stderr is None:
            raise RuntimeError("subprocess stderr not available")
        stderr_bytes = await proc.stderr.read()
        stderr_output = stderr_bytes.decode(errors="replace")[:2000]

        if returncode != 0 and not result.output:
            logger.warning(
                "ClaudeCodeProvider: process exited %d (task=%s). stderr: %s",
                returncode,
                task_id,
                stderr_output[:200],
            )
            result.is_error = True
            result.output = stderr_output

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_command(
        self,
        prompt: str,
        agent_config: AgentData,
        workspace_ctx: WorkspaceContext,
        session_id: str | None,
    ) -> list[str]:
        """Build the CLI command list for this execution."""
        cmd = [self._cli, "-p", prompt, "--output-format", "stream-json", "--verbose"]
        cmd.extend(["--mcp-config", str(workspace_ctx.mcp_config)])

        # Model: per-agent overrides global default
        model = agent_config.model
        if not model and self._defaults:
            model = self._defaults.default_model
        if model and model.startswith("cc/"):
            model = model[3:]
        if model:
            from claude_code.types import CC_AVAILABLE_MODELS

            known_bare = {m.removeprefix("cc/") for m in CC_AVAILABLE_MODELS}
            if model not in known_bare:
                logger.warning(
                    "ClaudeCodeProvider: model '%s' not in known models %s — "
                    "proceeding anyway (may fail if model does not exist)",
                    model,
                    sorted(known_bare),
                )
            cmd.extend(["--model", model])

        # Budget and turns: per-agent opts > global defaults
        cc = agent_config.claude_code_opts
        budget = (cc and cc.max_budget_usd) or (
            self._defaults and self._defaults.default_max_budget_usd
        )
        turns = (cc and cc.max_turns) or (self._defaults and self._defaults.default_max_turns)
        if budget is not None:
            cmd.extend(["--max-budget-usd", str(budget)])
        if turns is not None:
            cmd.extend(["--max-turns", str(turns)])

        # Permission mode
        perm = (
            (cc and cc.permission_mode)
            or (self._defaults and self._defaults.default_permission_mode)
            or "acceptEdits"
        )
        cmd.extend(["--permission-mode", perm])

        # Allowed tools — one flag per tool
        if cc and cc.allowed_tools:
            for tool in cc.allowed_tools:
                cmd.extend(["--allowedTools", tool])
        # Always allow the nanobot MCP tool namespace
        cmd.extend(["--allowedTools", "mcp__mc__*"])

        # Disallowed tools
        if cc and cc.disallowed_tools:
            for tool in cc.disallowed_tools:
                cmd.extend(["--disallowedTools", tool])

        # Session resume
        if session_id:
            cmd.extend(["--resume", session_id])

        # Effort level
        if cc and cc.effort_level:
            cmd.extend(["--effort", cc.effort_level])

        return cmd

    async def _parse_stream(self, proc: asyncio.subprocess.Process) -> AsyncIterator[dict]:
        """Yield parsed JSON objects from the process stdout (NDJSON format)."""
        if proc.stdout is None:
            raise RuntimeError("subprocess stdout not available")
        async for line in proc.stdout:
            text = line.decode(errors="replace").strip()
            if not text:
                continue
            try:
                yield json.loads(text)
            except json.JSONDecodeError:
                logger.warning("ClaudeCodeProvider: malformed JSON from CLI: %s", text[:200])

    def _handle_message(
        self,
        msg: dict,
        result: CCTaskResult,
        on_stream: Callable[[dict], None] | None,
    ) -> None:
        """Classify a single streamed message and update the result in-place."""
        msg_type = msg.get("type", "")

        # Capture session_id from any message that carries it.
        # Last-wins: the final message's session_id is used for resume,
        # which is correct since the CLI may update it mid-session.
        if msg.get("session_id"):
            result.session_id = msg["session_id"]

        if msg_type == "result":
            # Final result message from the CLI.
            # Try the spec field name first (total_cost_usd), then the
            # cost_usd alias, then the nested cost object, then fall back to 0.
            result.output = msg.get("result", "")
            result.is_error = bool(msg.get("is_error", False))
            if result.is_error:
                err = msg.get("error")
                if isinstance(err, dict):
                    result.error_type = result.error_type or err.get("type", "")
                    result.error_message = result.error_message or err.get("message", "")
                    if not result.output:
                        result.output = f"{result.error_type}: {result.error_message}"
                elif not result.output:
                    result.output = "Unknown error (no details in result message)"
            cost = (
                msg.get("total_cost_usd")
                or msg.get("cost_usd")
                or (msg.get("cost") or {}).get("total_cost_usd")
                or 0.0
            )
            result.cost_usd = float(cost)
            usage_raw = msg.get("usage")
            if isinstance(usage_raw, dict):
                result.usage = usage_raw

        elif msg_type == "assistant":
            # Streaming assistant turn — extract text/tool_use content blocks
            # and deliver them as normalized event dicts to the callback.
            if on_stream is not None:
                content = msg.get("message", {}).get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        block_type = block.get("type")
                        if block_type == "text":
                            on_stream({"type": "text", "text": block.get("text", "")})
                        elif block_type == "tool_use":
                            on_stream({"type": "tool_use", "name": block.get("name", "")})
                elif isinstance(content, str) and content:
                    on_stream({"type": "text", "text": content})

        elif msg_type == "stream_event":
            event = msg.get("event") or {}
            if event.get("type") == "error":
                err = event.get("error") or {}
                result.is_error = True
                result.error_type = err.get("type", "api_error")
                result.error_message = err.get("message", "Unknown stream error")
                if not result.output:
                    result.output = f"{result.error_type}: {result.error_message}"
                logger.warning(
                    "ClaudeCodeProvider: stream error (task): %s — %s",
                    result.error_type,
                    result.error_message,
                )

    async def _kill_process(self, proc: asyncio.subprocess.Process) -> None:
        """Gracefully terminate the subprocess, falling back to SIGKILL."""
        try:
            proc.send_signal(signal.SIGTERM)
            try:
                await asyncio.wait_for(proc.wait(), timeout=10)
            except asyncio.TimeoutError:
                logger.warning("ClaudeCodeProvider: SIGTERM timed out — sending SIGKILL")
                proc.kill()
                await proc.wait()
        except ProcessLookupError:
            pass  # Process already exited
