"""Shared authoring engine and draft-graph contract for LLM-first authoring.

Canonical phases: discovery, proposal, refinement, approval.
Both agent and squad authoring flows use this module.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

CANONICAL_PHASES: frozenset[str] = frozenset({"discovery", "proposal", "refinement", "approval"})

AUTHORING_SYSTEM_PROMPT_AGENT = """\
You are an expert agent architect helping a user design an AI agent.
Guide the user through a structured authoring session with phases:
1. discovery - understand goals and requirements
2. proposal - propose an initial agent design
3. refinement - refine based on feedback
4. approval - confirm the final design

Always respond with a JSON object containing:
- assistant_message: string (your conversational reply to the user)
- phase: one of "discovery", "proposal", "refinement", "approval"
- draft_graph_patch: object with agent design fields (e.g. agents array)
- unresolved_questions: list of strings (outstanding questions)
- preview: object with summary preview data
- readiness: float 0.0-1.0 (how ready the design is)

Respond only with valid JSON.
"""

AUTHORING_SYSTEM_PROMPT_SQUAD = """\
You are an expert squad architect helping a user design a multi-agent squad.
Guide the user through a structured authoring session with phases:
1. discovery - understand goals and requirements
2. proposal - propose an initial squad design
3. refinement - refine based on feedback
4. approval - confirm the final design

Always respond with a JSON object containing:
- assistant_message: string (your conversational reply to the user)
- phase: one of "discovery", "proposal", "refinement", "approval"
- draft_graph_patch: object with keys:
    - squad: object with outcome and other squad-level fields
    - agents: list of agent objects with key and role
    - workflows: list of workflow objects with key and steps
- unresolved_questions: list of strings (outstanding questions)
- preview: object with summary preview data
- readiness: float 0.0-1.0 (how ready the design is)

Do NOT use flat string fields like team_design or workflow_design.
Always use the structured graph patch format.
Respond only with valid JSON.
"""


class AuthoringMode(str, Enum):
    """Authoring session mode."""

    AGENT = "agent"
    SQUAD = "squad"


@dataclass
class AuthoringResponse:
    """Structured response from the authoring engine.

    Validates that phase is one of the canonical phases.
    """

    assistant_message: str
    phase: str
    draft_graph_patch: dict[str, Any]
    unresolved_questions: list[str]
    preview: dict[str, Any]
    readiness: float
    mode: AuthoringMode
    _extra: dict[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if self.phase not in CANONICAL_PHASES:
            raise ValueError(
                f"Invalid phase {self.phase!r}. Must be one of {sorted(CANONICAL_PHASES)}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict suitable for JSON output."""
        return {
            "assistant_message": self.assistant_message,
            "phase": self.phase,
            "draft_graph_patch": self.draft_graph_patch,
            "unresolved_questions": self.unresolved_questions,
            "preview": self.preview,
            "readiness": self.readiness,
            "mode": self.mode.value,
        }


def _parse_llm_json(raw: str) -> dict[str, Any] | None:
    """Attempt to parse LLM output as JSON.

    Returns None on failure.
    """
    if not raw or not raw.strip():
        return None
    text = raw.strip()
    # Strip markdown code blocks if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last fence lines
        lines = [line for line in lines[1:] if line.strip() != "```"]
        text = "\n".join(lines)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        logger.debug("Failed to parse LLM response as JSON: %.200s", raw)
    return None


def _make_fallback_response(
    mode: AuthoringMode,
    current_phase: str,
) -> AuthoringResponse:
    """Return a safe fallback response when LLM output cannot be parsed."""
    safe_phase = current_phase if current_phase in CANONICAL_PHASES else "discovery"
    message = (
        "I'm having trouble generating a response right now. "
        "Could you tell me more about what you'd like to create?"
    )
    return AuthoringResponse(
        assistant_message=message,
        phase=safe_phase,
        draft_graph_patch={},
        unresolved_questions=[],
        preview={},
        readiness=0.0,
        mode=mode,
    )


def _build_response_from_payload(
    payload: dict[str, Any],
    mode: AuthoringMode,
    current_phase: str,
) -> AuthoringResponse:
    """Build an AuthoringResponse from a parsed LLM payload dict."""
    phase = payload.get("phase", current_phase)
    if phase not in CANONICAL_PHASES:
        phase = current_phase if current_phase in CANONICAL_PHASES else "discovery"

    return AuthoringResponse(
        assistant_message=str(payload.get("assistant_message", "")),
        phase=phase,
        draft_graph_patch=payload.get("draft_graph_patch") or {},
        unresolved_questions=list(payload.get("unresolved_questions") or []),
        preview=payload.get("preview") or {},
        readiness=float(payload.get("readiness", 0.0)),
        mode=mode,
    )


async def build_agent_authoring_response(
    provider: Any,
    messages: list[dict[str, str]],
    current_phase: str,
) -> AuthoringResponse:
    """Call the LLM and return a structured agent authoring response.

    Args:
        provider: LLM provider with a .chat() coroutine.
        messages: Conversation history (user/assistant turns).
        current_phase: The current canonical phase for context.

    Returns:
        AuthoringResponse with mode=AGENT.
    """
    llm_messages = [
        {"role": "system", "content": AUTHORING_SYSTEM_PROMPT_AGENT},
        *messages,
    ]
    try:
        response = await provider.chat(
            messages=llm_messages,
            temperature=0.7,
            max_tokens=2048,
        )
        raw = response.content if hasattr(response, "content") else str(response)
        payload = _parse_llm_json(raw)
        if payload is None:
            return _make_fallback_response(AuthoringMode.AGENT, current_phase)
        return _build_response_from_payload(payload, AuthoringMode.AGENT, current_phase)
    except Exception:
        logger.exception("Error calling LLM for agent authoring")
        return _make_fallback_response(AuthoringMode.AGENT, current_phase)


async def build_squad_authoring_response(
    provider: Any,
    messages: list[dict[str, str]],
    current_phase: str,
    active_agents: list[dict[str, Any]] | None = None,
) -> AuthoringResponse:
    """Call the LLM and return a structured squad authoring response.

    Args:
        provider: LLM provider with a .chat() coroutine.
        messages: Conversation history (user/assistant turns).
        current_phase: The current canonical phase for context.
        active_agents: Optional list of active registered agents for reuse candidates.

    Returns:
        AuthoringResponse with mode=SQUAD and graph patch (squad/agents/workflows).
    """
    system_prompt = AUTHORING_SYSTEM_PROMPT_SQUAD
    if active_agents:
        agent_list = "\n".join(
            f"- name: {a.get('name', '')}, displayName: {a.get('displayName', '')}, "
            f"role: {a.get('role', '')}"
            + (f", prompt: {a.get('prompt', '')}" if a.get("prompt") else "")
            for a in active_agents
        )
        system_prompt = (
            system_prompt
            + f"\n\nThe following agents are already registered and available for reuse:\n"
            f"{agent_list}\n\n"
            "When designing the squad, consider whether any of these existing agents can "
            "fill the required roles instead of creating new ones. If an existing agent is "
            "a good fit, include 'reuseCandidateAgentName' in that agent's entry in the "
            "draft_graph_patch.agents array with the value set to the existing agent's name."
        )

    llm_messages = [
        {"role": "system", "content": system_prompt},
        *messages,
    ]
    try:
        response = await provider.chat(
            messages=llm_messages,
            temperature=0.7,
            max_tokens=2048,
        )
        raw = response.content if hasattr(response, "content") else str(response)
        payload = _parse_llm_json(raw)
        if payload is None:
            return _make_fallback_response(AuthoringMode.SQUAD, current_phase)
        result = _build_response_from_payload(payload, AuthoringMode.SQUAD, current_phase)
        # Ensure squad responses never contain legacy flat keys
        patch = result.draft_graph_patch
        patch.pop("team_design", None)
        patch.pop("workflow_design", None)
        return result
    except Exception:
        logger.exception("Error calling LLM for squad authoring")
        return _make_fallback_response(AuthoringMode.SQUAD, current_phase)
