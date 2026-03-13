"""Codex app-server supervision relay for interactive sessions."""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from mc.contexts.interactive.errors import InteractiveSessionStartupError
from mc.contexts.interactive.supervision_types import InteractiveSupervisionEvent
from mc.contexts.interactive.types import InteractiveSupervisionSink


class CodexAppServerProtocolError(RuntimeError):
    """Raised when Codex app-server returns a structured protocol error."""


@dataclass(frozen=True)
class CodexAppServerSession:
    """Bookkeeping for a Codex app-server supervision sidecar."""

    session_id: str
    stop: Callable[[], Awaitable[None] | None]
    ready: asyncio.Future[None]


class CodexSupervisionRelay:
    """Normalize Codex app-server messages into the shared supervision contract."""

    def __init__(
        self,
        *,
        session_id: str,
        task_id: str,
        step_id: str | None,
        agent_name: str,
        sink: InteractiveSupervisionSink,
    ) -> None:
        self._session_id = session_id
        self._task_id = task_id
        self._step_id = step_id
        self._agent_name = agent_name
        self._sink = sink
        self._final_outputs_by_turn: dict[str, str] = {}

    def process_message(self, message: dict[str, Any]) -> dict[str, object] | None:
        method = _text(message.get("method"))
        if method == "error":
            detail = _text((message.get("params") or {}).get("message")) or "unknown protocol error"
            raise CodexAppServerProtocolError(detail)

        event = self._normalize_message(message)
        if event is None:
            return None
        return self._sink.handle_event(event)

    def _normalize_message(self, message: dict[str, Any]) -> InteractiveSupervisionEvent | None:
        method = _text(message.get("method"))
        params = message.get("params")
        if not isinstance(params, dict) or method is None:
            return None

        if method in {"turn/started", "turn/completed"}:
            turn = params.get("turn") if isinstance(params.get("turn"), dict) else {}
            turn_id = _text(turn.get("id"))
            summary = _text(turn.get("summary"))
            kind = "turn_started" if method == "turn/started" else "turn_completed"
            final_output = None
            if method == "turn/completed" and turn_id is not None:
                final_output = self._final_outputs_by_turn.get(turn_id)
            return self._event(
                kind=kind,
                turn_id=turn_id,
                summary=summary,
                final_output=final_output,
                metadata={"thread_id": _text(params.get("threadId"))},
            )

        if method in {"item/started", "item/completed"}:
            item = params.get("item") if isinstance(params.get("item"), dict) else {}
            kind = "item_started" if method == "item/started" else "item_completed"
            item_type = _text(item.get("type"))
            message_phase = _text(item.get("phase"))
            final_output = None
            if (
                method == "item/completed"
                and item_type == "agentMessage"
                and _text(item.get("text")) is not None
            ):
                item_text = _text(item.get("text"))
                if item_text is not None and message_phase == "final_answer":
                    turn_id = _text(params.get("turnId"))
                    if turn_id is not None:
                        self._final_outputs_by_turn[turn_id] = item_text
                    final_output = item_text
            return self._event(
                kind=kind,
                turn_id=_text(params.get("turnId")),
                item_id=_text(item.get("id")),
                final_output=final_output,
                metadata={
                    "thread_id": _text(params.get("threadId")),
                    "item_type": item_type,
                    "message_phase": message_phase,
                },
            )

        if method in {
            "item/commandExecution/requestApproval",
            "item/fileChange/requestApproval",
            "item/permissions/requestApproval",
            "applyPatchApproval",
            "execCommandApproval",
            "mcpServer/elicitation/request",
        }:
            summary = _text(params.get("reason")) or _text(params.get("prompt"))
            metadata = {
                "thread_id": _text(params.get("threadId"), params.get("conversationId")),
                "request_id": _text(message.get("id")),
                "method": method,
                "command": _text(params.get("command")),
            }
            return self._event(
                kind="approval_requested",
                turn_id=_text(params.get("turnId")),
                item_id=_text(params.get("itemId"), params.get("callId")),
                summary=summary,
                metadata=_drop_none(metadata),
            )

        if method == "item/tool/requestUserInput":
            questions = params.get("questions") if isinstance(params.get("questions"), list) else []
            first_question = questions[0] if questions and isinstance(questions[0], dict) else {}
            return self._event(
                kind="user_input_requested",
                turn_id=_text(params.get("turnId")),
                item_id=_text(params.get("itemId")),
                summary=_text(first_question.get("question")),
                metadata=_drop_none(
                    {
                        "thread_id": _text(params.get("threadId")),
                        "request_id": _text(message.get("id")),
                        "method": method,
                        "questions": questions,
                    }
                ),
            )

        return None

    def _event(
        self,
        *,
        kind: str,
        turn_id: str | None = None,
        item_id: str | None = None,
        summary: str | None = None,
        final_output: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> InteractiveSupervisionEvent:
        return InteractiveSupervisionEvent(
            kind=kind,
            session_id=self._session_id,
            provider="codex",
            task_id=self._task_id,
            step_id=self._step_id,
            turn_id=turn_id,
            item_id=item_id,
            summary=summary,
            final_output=final_output,
            metadata=_drop_none(metadata or {}),
            agent_name=self._agent_name,
        )


async def start_codex_app_server_session(
    *,
    session_id: str,
    task_id: str,
    step_id: str | None,
    agent_name: str,
    cwd: Path,
    sink: InteractiveSupervisionSink,
    cli_path: str = "codex",
    launcher: Callable[..., Awaitable[asyncio.subprocess.Process]] = asyncio.create_subprocess_exec,
) -> CodexAppServerSession:
    """Start a Codex app-server sidecar for structured supervision."""

    try:
        process = await launcher(
            cli_path,
            "app-server",
            "--listen",
            "stdio://",
            cwd=str(cwd),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        raise InteractiveSessionStartupError(f"Codex app-server supervision failed: {exc}") from exc

    ready: asyncio.Future[None] = asyncio.get_running_loop().create_future()
    relay = CodexSupervisionRelay(
        session_id=session_id,
        task_id=task_id,
        step_id=step_id,
        agent_name=agent_name,
        sink=sink,
    )
    reader_task = asyncio.create_task(_read_codex_stream(process, relay))
    stderr_task = asyncio.create_task(_drain_stream(process.stderr))

    await asyncio.sleep(0)
    if process.returncode is not None:
        stderr_text = await _read_stream_text(process.stderr)
        reader_task.cancel()
        stderr_task.cancel()
        raise InteractiveSessionStartupError(
            "Codex app-server supervision failed: "
            + (stderr_text.strip() or f"process exited with code {process.returncode}")
        )

    ready.set_result(None)

    async def _stop() -> None:
        reader_task.cancel()
        stderr_task.cancel()
        if process.stdin is not None:
            with contextlib.suppress(Exception):
                process.stdin.close()
        if process.returncode is None:
            process.terminate()
            with contextlib.suppress(ProcessLookupError):
                await process.wait()

    return CodexAppServerSession(session_id=session_id, stop=_stop, ready=ready)


async def stop_codex_app_server_session(session: CodexAppServerSession) -> None:
    """Stop a previously started Codex app-server sidecar."""

    result = session.stop()
    if inspect.isawaitable(result):
        await result


async def _read_codex_stream(
    process: asyncio.subprocess.Process,
    relay: CodexSupervisionRelay,
) -> None:
    if process.stdout is None:
        return
    parser = _CodexAppServerMessageParser()
    while not process.stdout.at_eof():
        chunk = await process.stdout.read(4096)
        if not chunk:
            break
        for message in parser.feed(chunk):
            relay.process_message(message)


async def _drain_stream(stream: asyncio.StreamReader | None) -> None:
    if stream is None:
        return
    while not stream.at_eof():
        chunk = await stream.read(4096)
        if not chunk:
            break


async def _read_stream_text(stream: asyncio.StreamReader | None) -> str:
    if stream is None:
        return ""
    data = await stream.read()
    return data.decode("utf-8", errors="replace")


class _CodexAppServerMessageParser:
    """Parse either newline-delimited JSON or Content-Length framed messages."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, chunk: bytes) -> list[dict[str, Any]]:
        self._buffer.extend(chunk)
        messages: list[dict[str, Any]] = []
        while True:
            content_length = self._content_length()
            if content_length is not None:
                header_end = self._buffer.find(b"\r\n\r\n")
                if header_end == -1:
                    break
                payload_start = header_end + 4
                if len(self._buffer) < payload_start + content_length:
                    break
                payload = bytes(self._buffer[payload_start : payload_start + content_length])
                del self._buffer[: payload_start + content_length]
                messages.append(json.loads(payload.decode("utf-8")))
                continue

            newline = self._buffer.find(b"\n")
            if newline == -1:
                break
            line = bytes(self._buffer[:newline]).strip()
            del self._buffer[: newline + 1]
            if not line:
                continue
            messages.append(json.loads(line.decode("utf-8")))
        return messages

    def _content_length(self) -> int | None:
        header_end = self._buffer.find(b"\r\n\r\n")
        if header_end == -1:
            return None
        header = self._buffer[:header_end].decode("utf-8", errors="replace")
        for line in header.split("\r\n"):
            if line.lower().startswith("content-length:"):
                value = line.split(":", 1)[1].strip()
                return int(value)
        return None


def _drop_none(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _text(*values: object) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None
