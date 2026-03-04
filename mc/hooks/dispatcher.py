#!/usr/bin/env python3
"""Central hook dispatcher for Claude Code events."""
from __future__ import annotations

import json
import sys


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    event_name = payload.get("hook_event_name", "")
    if not event_name:
        sys.exit(0)

    matcher_value = payload.get("tool_name", "")
    session_id = payload.get("session_id", "unknown")

    # Import here to avoid import overhead when payload is invalid
    from .context import HookContext
    from .discovery import discover_handlers

    ctx = HookContext.load(session_id)

    results: list[str] = []
    for handler_cls in discover_handlers():
        if handler_cls.matches(event_name, matcher_value):
            try:
                handler = handler_cls(ctx, payload)
                result = handler.handle()
                if result:
                    results.append(result)
            except Exception as exc:
                print(f"Handler {handler_cls.__name__} error: {exc}", file=sys.stderr)

    ctx.save()

    if results:
        combined = "; ".join(results)
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": event_name,
                    "additionalContext": combined,
                }
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
