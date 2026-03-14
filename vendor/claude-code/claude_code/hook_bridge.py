"""Bridge Claude hook callbacks into Mission Control supervision over IPC."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

from claude_code.ipc_client import MCSocketClient


def _read_stdin_payload() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    return json.loads(raw)


def _warn_and_continue(message: str) -> int:
    print(f"[mc-hook-bridge] warning: {message}", file=sys.stderr)
    return 0


async def _main() -> int:
    socket_path = os.environ.get("MC_SOCKET_PATH")
    session_id = os.environ.get("MC_INTERACTIVE_SESSION_ID")
    if not socket_path or not session_id:
        return _warn_and_continue(
            "MC hook bridge requires MC_SOCKET_PATH and MC_INTERACTIVE_SESSION_ID"
        )

    try:
        payload = _read_stdin_payload()
    except Exception as exc:
        return _warn_and_continue(f"failed to parse hook payload: {exc}")
    event_name = payload.get("hook_event_name")
    raw_event = dict(payload)
    if event_name:
        raw_event["eventName"] = event_name
    raw_event["session_id"] = session_id
    if os.environ.get("TASK_ID"):
        raw_event["task_id"] = os.environ["TASK_ID"]
    if os.environ.get("AGENT_NAME"):
        raw_event["agent_name"] = os.environ["AGENT_NAME"]

    client = MCSocketClient(socket_path)
    try:
        result = await client.request(
            "emit_supervision_event",
            {
                "provider": "claude-code",
                "raw_event": raw_event,
            },
        )
    except Exception as exc:
        return _warn_and_continue(f"failed to emit supervision event: {exc}")
    if result.get("error"):
        return _warn_and_continue(f"supervision event rejected: {result['error']}")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
