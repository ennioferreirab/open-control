from __future__ import annotations

import io
import json
import sys
from typing import Any

import pytest
from claude_code import hook_bridge


def _set_hook_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MC_SOCKET_PATH", "/tmp/mc-test.sock")
    monkeypatch.setenv("MC_INTERACTIVE_SESSION_ID", "interactive_session:claude")
    monkeypatch.setenv("TASK_ID", "task-123")
    monkeypatch.setenv("AGENT_NAME", "marketing-copy")


async def test_main_returns_zero_when_ipc_connection_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _set_hook_env(monkeypatch)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(json.dumps({"hook_event_name": "UserPromptSubmit"})),
    )

    async def _fail_request(self: Any, method: str, params: dict[str, Any]) -> dict[str, Any]:
        raise ConnectionError("socket unavailable")

    monkeypatch.setattr(hook_bridge.MCSocketClient, "request", _fail_request)

    exit_code = await hook_bridge._main()

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "failed to emit supervision event" in captured.err
    assert "socket unavailable" in captured.err


async def test_main_returns_zero_when_supervision_event_is_rejected(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _set_hook_env(monkeypatch)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(json.dumps({"hook_event_name": "Stop"})),
    )

    async def _error_result(self: Any, method: str, params: dict[str, Any]) -> dict[str, Any]:
        return {"error": "supervisor unavailable"}

    monkeypatch.setattr(hook_bridge.MCSocketClient, "request", _error_result)

    exit_code = await hook_bridge._main()

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "supervision event rejected" in captured.err
    assert "supervisor unavailable" in captured.err


async def test_main_forwards_hook_payload_to_supervision_bridge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_hook_env(monkeypatch)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(json.dumps({"hook_event_name": "Stop", "stop_hook_active": True})),
    )
    calls: list[tuple[str, dict[str, Any]]] = []

    async def _record_request(self: Any, method: str, params: dict[str, Any]) -> dict[str, Any]:
        calls.append((method, params))
        return {"status": "ok"}

    monkeypatch.setattr(hook_bridge.MCSocketClient, "request", _record_request)

    exit_code = await hook_bridge._main()

    assert exit_code == 0
    assert calls == [
        (
            "emit_supervision_event",
            {
                "provider": "claude-code",
                "raw_event": {
                    "hook_event_name": "Stop",
                    "eventName": "Stop",
                    "stop_hook_active": True,
                    "session_id": "interactive_session:claude",
                    "task_id": "task-123",
                    "agent_name": "marketing-copy",
                },
            },
        )
    ]
