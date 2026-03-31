"""Claude Code provider CLI parser."""

from __future__ import annotations

import json
import signal
from typing import Any

from mc.contexts.provider_cli.types import (
    ParsedCliEvent,
    ProviderProcessHandle,
    ProviderSessionSnapshot,
)

RAW_JSON_VALUE_MAX = 16_000


def _truncate_large_values(obj: Any, max_len: int = RAW_JSON_VALUE_MAX) -> Any:
    """Recursively truncate string values exceeding max_len in a dict/list.

    Keeps the JSON structure valid — only individual string values are cut.
    """
    if isinstance(obj, dict):
        return {k: _truncate_large_values(v, max_len) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_truncate_large_values(item, max_len) for item in obj]
    if isinstance(obj, str) and len(obj) > max_len:
        return obj[:max_len] + f"... [truncated, {len(obj)} chars total]"
    return obj


class ClaudeCodeCLIParser:
    """Implements the ProviderCLIParser protocol for Claude Code CLI sessions.

    This parser processes Claude Code's ``--output-format stream-json`` JSONL
    output and provides provider-native resume, interrupt, and stop through the
    shared provider CLI contract.

    It does NOT depend on any PTY, xterm, websocket, or IPC socket
    infrastructure. Output is captured directly from the process supervisor's
    stdout/stderr stream.
    """

    provider_name: str = "claude-code"

    def __init__(self, *, supervisor: Any | None = None) -> None:
        self._supervisor = supervisor
        self._discovered_session_id: str | None = None
        self._line_buffer: str = ""

    @property
    def discovered_session_id(self) -> str | None:
        """The Claude session ID discovered from output, or None."""
        return self._discovered_session_id

    # ------------------------------------------------------------------
    # ProviderCLIParser protocol
    # ------------------------------------------------------------------

    async def start_session(
        self,
        mc_session_id: str,
        command: list[str],
        cwd: str,
        env: dict[str, str] | None = None,
    ) -> ProviderProcessHandle:
        """Launch the Claude Code CLI process and return a process handle."""
        supervisor = self._get_supervisor()
        return await supervisor.launch(
            mc_session_id=mc_session_id,
            provider=self.provider_name,
            command=command,
            cwd=cwd,
            env=env,
            stdin_mode="devnull",
        )

    def parse_output(self, chunk: bytes) -> list[ParsedCliEvent]:
        """Parse raw output from Claude Code into structured events.

        Claude Code emits JSONL when run with ``--output-format stream-json``.
        Each line is a complete JSON object terminated by ``\\n``.

        TCP chunks (typically 8 KB) can split a single JSONL line across
        multiple ``parse_output`` calls. The line buffer accumulates partial
        content until a newline arrives, then parses the complete line.
        """
        if not chunk:
            return []

        text: str = chunk.decode("utf-8", errors="replace") if isinstance(chunk, bytes) else chunk
        # Prepend any buffered content from the previous chunk
        if self._line_buffer:
            text = self._line_buffer + text
            self._line_buffer = ""

        events: list[ParsedCliEvent] = []

        # If the text does not end with a newline, the last segment is a
        # partial JSONL line split by a TCP chunk boundary.
        if not text.endswith("\n"):
            last_nl = text.rfind("\n")
            if last_nl == -1:
                # No newline at all — buffer everything for next chunk
                self._line_buffer = text
                return events
            # Buffer the trailing partial, process complete lines above it
            self._line_buffer = text[last_nl + 1 :]
            text = text[: last_nl + 1]

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("{"):
                try:
                    data = json.loads(stripped)
                    events.extend(self._parse_json_message(data))
                    continue
                except json.JSONDecodeError:
                    pass

            events.append(ParsedCliEvent(kind="text", text=stripped))

        return events

    async def discover_session(self, handle: ProviderProcessHandle) -> ProviderSessionSnapshot:
        """Return a snapshot for the given handle using any discovered session ID."""
        return ProviderSessionSnapshot(
            mc_session_id=handle.mc_session_id,
            provider_session_id=self._discovered_session_id,
            mode="provider-native",
            supports_resume=True,
            supports_interrupt=True,
            supports_stop=True,
        )

    async def inspect_process_tree(self, handle: ProviderProcessHandle) -> dict[str, Any]:
        """Delegate process tree inspection to the supervisor."""
        return await self._get_supervisor().inspect_process_tree(handle)

    async def interrupt(self, handle: ProviderProcessHandle) -> None:
        """Send SIGINT to the Claude Code process group."""
        await self._get_supervisor().send_signal(handle, signal.SIGINT)

    def resume(
        self,
        *,
        mc_session_id: str,
        provider_session_id: str,
        command_prefix: list[str],
        cwd: str,
        env: dict[str, str] | None = None,
    ) -> list[str]:
        """Build a resume command using Claude Code's ``--resume`` flag.

        Returns the command list that should be passed to ``start_session`` to
        launch a new process resuming the given provider session.
        """
        return [*command_prefix, "--resume", provider_session_id]

    async def stop(self, handle: ProviderProcessHandle) -> None:
        """Send SIGTERM to the Claude Code process via the supervisor."""
        await self._get_supervisor().terminate(handle)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_supervisor(self) -> Any:
        """Return the injected supervisor or lazily create a real one."""
        if self._supervisor is None:
            from mc.runtime.provider_cli.process_supervisor import (
                ProviderProcessSupervisor,
            )

            self._supervisor = ProviderProcessSupervisor()
        return self._supervisor

    def _parse_json_message(self, data: dict[str, Any]) -> list[ParsedCliEvent]:
        """Dispatch JSON message parsing based on the ``type`` field."""
        msg_type = data.get("type", "")
        events: list[ParsedCliEvent] = []

        if msg_type == "system":
            events.extend(self._parse_system_message(data))
        elif msg_type == "assistant":
            events.extend(self._parse_assistant_message(data))
        elif msg_type == "user":
            events.extend(self._parse_user_message(data))
        elif msg_type == "result":
            events.extend(self._parse_result_message(data))
        else:
            events.append(
                ParsedCliEvent(
                    kind="text",
                    text=json.dumps(_truncate_large_values(data)),
                    metadata={"raw_type": msg_type, "source_type": msg_type},
                )
            )

        return events

    def _parse_system_message(self, data: dict[str, Any]) -> list[ParsedCliEvent]:
        """Handle ``system`` messages, including the initial session ID."""
        subtype = data.get("subtype", "")
        events: list[ParsedCliEvent] = []

        if subtype == "init":
            session_id = data.get("session_id")
            if session_id:
                self._discovered_session_id = session_id
                events.append(
                    ParsedCliEvent(
                        kind="session_id",
                        text=session_id,
                        provider_session_id=session_id,
                        metadata={
                            "subtype": subtype,
                            "source_type": "system",
                            "source_subtype": subtype,
                        },
                    )
                )
        elif subtype in ("hook_started", "hook_response"):
            hook_name = data.get("hook_name", subtype)
            summary = f"{hook_name}"
            events.append(
                ParsedCliEvent(
                    kind="system_event",
                    text=summary,
                    provider_session_id=self._discovered_session_id,
                    metadata={
                        "subtype": subtype,
                        "source_type": "system",
                        "source_subtype": subtype,
                        "hook_name": hook_name,
                        "raw_json": json.dumps(_truncate_large_values(data)),
                    },
                )
            )
        else:
            # Other system subtypes (e.g. future ones) — emit as system event
            summary = subtype or "system"
            events.append(
                ParsedCliEvent(
                    kind="system_event",
                    text=summary,
                    provider_session_id=self._discovered_session_id,
                    metadata={
                        "subtype": subtype,
                        "source_type": "system",
                        "source_subtype": subtype,
                    },
                )
            )

        return events

    def _parse_assistant_message(self, data: dict[str, Any]) -> list[ParsedCliEvent]:
        """Handle ``assistant`` messages, extracting text and tool use."""
        message = data.get("message", {})
        content = message.get("content", [])
        events: list[ParsedCliEvent] = []

        for block in content:
            block_type = block.get("type", "")
            if block_type == "text":
                text = block.get("text", "")
                if text:
                    events.append(
                        ParsedCliEvent(
                            kind="text",
                            text=text,
                            provider_session_id=self._discovered_session_id,
                            metadata={"source_type": "assistant", "source_subtype": "text"},
                        )
                    )
            elif block_type == "tool_use":
                tool_name = block.get("name", "unknown_tool")
                tool_input = block.get("input", {})
                ask_user_event = self._parse_ask_user_tool_use(
                    tool_name=tool_name,
                    tool_input=tool_input,
                    tool_id=block.get("id"),
                )
                if ask_user_event is not None:
                    events.append(ask_user_event)
                    continue
                events.append(
                    ParsedCliEvent(
                        kind="tool_use",
                        text=tool_name,
                        provider_session_id=self._discovered_session_id,
                        metadata={
                            "tool_id": block.get("id"),
                            "tool_name": tool_name,
                            "tool_input": tool_input,
                            "source_type": "tool_use",
                            "source_subtype": tool_name,
                        },
                    )
                )

        return events

    def _parse_user_message(self, data: dict[str, Any]) -> list[ParsedCliEvent]:
        """Extract tool_result blocks from echoed user messages."""
        message = data.get("message", {})
        content = message.get("content", [])
        events: list[ParsedCliEvent] = []

        for block in content:
            if block.get("type") != "tool_result":
                continue
            tool_use_id = block.get("tool_use_id")
            result_content = block.get("content", "")
            if isinstance(result_content, list):
                # Multi-part content — extract text parts
                result_content = "\n".join(
                    p.get("text", "") for p in result_content if p.get("type") == "text"
                )
            if not result_content:
                continue
            # Truncate large outputs to avoid bloating the activity log
            max_len = 4000
            truncated = len(result_content) > max_len
            display = result_content[:max_len] + ("... (truncated)" if truncated else "")
            events.append(
                ParsedCliEvent(
                    kind="tool_result",
                    text=display,
                    provider_session_id=self._discovered_session_id,
                    metadata={
                        "tool_use_id": tool_use_id,
                        "source_type": "tool_result",
                        "source_subtype": "tool_result",
                    },
                )
            )

        return events

    def _parse_result_message(self, data: dict[str, Any]) -> list[ParsedCliEvent]:
        """Handle ``result`` messages."""
        subtype = data.get("subtype", "")
        result_text = data.get("result", "")
        is_error = subtype not in {"success", ""}

        if is_error:
            return [
                ParsedCliEvent(
                    kind="error",
                    text=result_text or subtype,
                    provider_session_id=self._discovered_session_id,
                    metadata={
                        "subtype": subtype,
                        "source_type": "result",
                        "source_subtype": "error",
                    },
                )
            ]

        return [
            ParsedCliEvent(
                kind="result",
                text=result_text,
                provider_session_id=self._discovered_session_id,
                metadata={"subtype": subtype, "source_type": "result", "source_subtype": "success"},
            )
        ]

    def _parse_ask_user_tool_use(
        self,
        *,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_id: str | None,
    ) -> ParsedCliEvent | None:
        normalized = tool_name.strip().lower()
        if normalized not in {
            "mcp__mc__ask_user",
            "askuserquestion",
        }:
            return None

        summary = str(tool_input.get("question") or "Agent requested user input").strip()
        return ParsedCliEvent(
            kind="ask_user_requested",
            text=summary,
            provider_session_id=self._discovered_session_id,
            metadata={
                "tool_id": tool_id,
                "tool_name": tool_name,
                "tool_input": tool_input,
                "source_type": "tool_use",
                "source_subtype": "ask_user",
            },
        )
