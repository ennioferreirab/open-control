"""Provider-event normalization into the shared interactive supervision contract."""

from __future__ import annotations

from typing import Any, Final

from mc.contexts.interactive.supervision_types import (
    INTERACTIVE_SUPERVISION_EVENT_KINDS,
    InteractiveSupervisionEvent,
)

_CLAUDE_EVENT_KIND_MAP: Final[dict[str, str]] = {
    "sessionstart": "session_started",
    "instructionsloaded": "session_ready",
    "userpromptsubmit": "turn_started",
    "pretooluse": "item_started",
    "posttooluse": "item_completed",
    "posttoolusefailure": "session_failed",
    "permissionrequest": "approval_requested",
    "notification": "turn_updated",
    "subagentstart": "item_started",
    "subagentstop": "item_completed",
    "stop": "turn_completed",
}

_CODEX_EVENT_KIND_MAP: Final[dict[str, str]] = {
    "turn/started": "turn_started",
    "turn/completed": "turn_completed",
    "turn/updated": "turn_updated",
    "item/started": "item_started",
    "item/completed": "item_completed",
    "session/started": "session_started",
    "session/ready": "session_ready",
    "session/stopped": "session_stopped",
    "session/failed": "session_failed",
    "approval/requested": "approval_requested",
    "request_user_input": "user_input_requested",
}


def normalize_provider_event(
    *, provider: str, raw_event: dict[str, Any]
) -> InteractiveSupervisionEvent:
    """Map provider-specific event payloads into the shared event contract."""

    kind = _resolve_event_kind(provider=provider, raw_event=raw_event)
    metadata = raw_event.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    return InteractiveSupervisionEvent(
        kind=kind,
        session_id=_string_value(raw_event, "session_id", "sessionId", "session"),
        provider=provider,
        task_id=_string_value(raw_event, "task_id", "taskId"),
        step_id=_string_value(raw_event, "step_id", "stepId"),
        turn_id=_string_value(raw_event, "turn_id", "turnId"),
        item_id=_string_value(raw_event, "item_id", "itemId"),
        status=_string_value(raw_event, "status"),
        summary=_string_value(raw_event, "summary", "message"),
        error=_string_value(raw_event, "error", "errorMessage"),
        metadata=metadata,
        occurred_at=_string_value(raw_event, "occurred_at", "occurredAt", "timestamp"),
        agent_name=_string_value(raw_event, "agent_name", "agentName"),
    )


def _resolve_event_kind(*, provider: str, raw_event: dict[str, Any]) -> str:
    raw_kind = _string_value(raw_event, "kind", "eventName", "event_name", "event", "type")
    if raw_kind is None:
        raise ValueError("Interactive supervision event is missing a kind")

    canonical_candidate = _canonicalize(raw_kind)
    if canonical_candidate in INTERACTIVE_SUPERVISION_EVENT_KINDS:
        return canonical_candidate

    provider_key = provider.strip().lower()
    if provider_key == "claude-code":
        mapped = _CLAUDE_EVENT_KIND_MAP.get(_condense(raw_kind))
        if mapped is not None:
            return mapped
    if provider_key == "codex":
        mapped = _CODEX_EVENT_KIND_MAP.get(raw_kind.strip().lower())
        if mapped is not None:
            return mapped

    raise ValueError(
        f"Unsupported interactive supervision event '{raw_kind}' for provider '{provider}'"
    )


def _string_value(raw_event: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = raw_event.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _canonicalize(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace("/", "_")


def _condense(value: str) -> str:
    return "".join(character for character in value.strip().lower() if character.isalnum())
