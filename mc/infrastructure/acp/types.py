"""Value types for the ACP transport layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AcpTurnResult:
    """Result of one prompt turn through the ACP adapter.

    Attributes:
        text: Assembled agent response text (all AgentMessageChunk pieces concatenated).
        stop_reason: The stop_reason string from PromptResponse (e.g. "end_turn").
        session_id: The ACP session ID used for the turn.
        usage: Token counts from PromptResponse.usage (empty dict if usage was None).
        cost_usd: Notional cost estimate in USD from the last UsageUpdate, or None.
    """

    text: str
    stop_reason: str
    session_id: str
    usage: dict[str, int]
    cost_usd: float | None
