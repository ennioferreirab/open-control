"""Shared Claude Code tool policy for Mission Control sessions."""

from __future__ import annotations

MC_NATIVE_TOOL_CONFLICTS: tuple[str, ...] = (
    "AskUserQuestion",
    "CronCreate",
    "CronDelete",
    "CronList",
)


def merge_mc_disallowed_tools(configured: list[str] | None) -> list[str]:
    """Merge MC-native conflicts into the explicit disallowed tool list."""

    merged: list[str] = []
    seen: set[str] = set()
    for tool in [*(configured or []), *MC_NATIVE_TOOL_CONFLICTS]:
        normalized = str(tool).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        merged.append(normalized)
    return merged
