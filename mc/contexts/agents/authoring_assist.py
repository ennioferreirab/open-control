"""Structured authoring assist for agent and squad spec creation.

This module drives the deep ``Create Agent`` and ``Create Squad`` wizards.
It returns structured JSON responses — never raw YAML — so the dashboard can
render a live summary panel and advance through phases progressively.

Phases for agent authoring:
    PURPOSE -> OPERATING_CONTEXT -> WORKING_STYLE -> EXECUTION_POLICY ->
    REVIEW_POLICY -> SUMMARY

Phases for squad authoring:
    team_design -> workflow_design -> review_design -> approval
"""

from __future__ import annotations

import dataclasses
import enum
from typing import Any

# ---------------------------------------------------------------------------
# Phase enum
# ---------------------------------------------------------------------------


class AuthoringPhase(str, enum.Enum):
    """Ordered phases for the agent authoring wizard."""

    PURPOSE = "purpose"
    OPERATING_CONTEXT = "operating_context"
    WORKING_STYLE = "working_style"
    EXECUTION_POLICY = "execution_policy"
    REVIEW_POLICY = "review_policy"
    SUMMARY = "summary"


_AGENT_PHASE_ORDER: list[AuthoringPhase] = [
    AuthoringPhase.PURPOSE,
    AuthoringPhase.OPERATING_CONTEXT,
    AuthoringPhase.WORKING_STYLE,
    AuthoringPhase.EXECUTION_POLICY,
    AuthoringPhase.REVIEW_POLICY,
    AuthoringPhase.SUMMARY,
]

_AGENT_PHASE_TO_SPEC_KEY: dict[AuthoringPhase, str] = {
    AuthoringPhase.PURPOSE: "purpose",
    AuthoringPhase.OPERATING_CONTEXT: "operating_context",
    AuthoringPhase.WORKING_STYLE: "working_style",
    AuthoringPhase.EXECUTION_POLICY: "execution_policy",
    AuthoringPhase.REVIEW_POLICY: "review_policy",
}

_SQUAD_PHASE_ORDER: list[str] = [
    "team_design",
    "workflow_design",
    "review_design",
    "approval",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class SpecDraftPatch:
    """A structured patch to apply to the in-progress spec draft."""

    fields: dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"fields": self.fields}


@dataclasses.dataclass
class AuthoringResponse:
    """Structured response from the agent authoring assistant.

    This is the only output contract exposed to the dashboard — YAML is never
    included in this response.
    """

    question: str
    draft_patch: SpecDraftPatch
    phase: AuthoringPhase
    readiness: float
    summary_sections: dict[str, Any]
    recommended_next_phase: AuthoringPhase

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "draft_patch": self.draft_patch.to_dict(),
            "phase": self.phase.value,
            "readiness": self.readiness,
            "summary_sections": self.summary_sections,
            "recommended_next_phase": self.recommended_next_phase.value,
        }


# ---------------------------------------------------------------------------
# Readiness scoring
# ---------------------------------------------------------------------------

_REQUIRED_SPEC_KEYS = list(_AGENT_PHASE_TO_SPEC_KEY.values())


def compute_readiness(spec: dict[str, Any]) -> float:
    """Return a 0.0–1.0 readiness score based on filled spec sections.

    Only non-empty string values count toward readiness.
    """
    if not spec:
        return 0.0
    filled = sum(
        1
        for key in _REQUIRED_SPEC_KEYS
        if key in spec and isinstance(spec[key], str) and spec[key].strip()
    )
    return filled / len(_REQUIRED_SPEC_KEYS)


# ---------------------------------------------------------------------------
# Question generation
# ---------------------------------------------------------------------------

_AGENT_PHASE_QUESTIONS: dict[AuthoringPhase, str] = {
    AuthoringPhase.PURPOSE: (
        "What is the primary purpose of this agent? "
        "Describe what it should accomplish and who it will serve."
    ),
    AuthoringPhase.OPERATING_CONTEXT: (
        "What is the operating context for this agent? "
        "Describe the environment, data sources, and systems it will interact with."
    ),
    AuthoringPhase.WORKING_STYLE: (
        "How should this agent work? "
        "Describe its communication style, level of autonomy, and approach to tasks."
    ),
    AuthoringPhase.EXECUTION_POLICY: (
        "What is the execution policy for this agent? "
        "Should it work autonomously, wait for approval, or follow a hybrid approach?"
    ),
    AuthoringPhase.REVIEW_POLICY: (
        "What review policy should apply to this agent's outputs? "
        "Describe quality checks, approval requirements, and escalation rules."
    ),
    AuthoringPhase.SUMMARY: (
        "Here is a summary of the agent spec so far. "
        "Please review and let me know if anything needs adjustment before we finalize."
    ),
}

_SQUAD_PHASE_QUESTIONS: dict[str, str] = {
    "team_design": (
        "How many agents should be in your squad, and what roles should they have? "
        "Describe the team composition and each agent's specialty."
    ),
    "workflow_design": (
        "How should the squad's workflow be structured? "
        "Describe the steps, handoffs between agents, and completion criteria."
    ),
    "review_design": (
        "How should the squad review its outputs? "
        "Describe the review criteria, weights, and approval policy."
    ),
    "approval": (
        "Here is a summary of your squad design. "
        "Please review and approve to publish the squad spec."
    ),
}


def build_agent_question(phase: AuthoringPhase, spec: dict[str, Any]) -> str:
    """Return the deep question for the given authoring phase.

    For the SUMMARY phase the question contextualizes the current spec.
    """
    if phase == AuthoringPhase.SUMMARY and spec:
        filled_sections = [k for k in _REQUIRED_SPEC_KEYS if spec.get(k, "").strip()]
        section_list = ", ".join(filled_sections) if filled_sections else "none yet"
        return (
            f"Here is a summary of the agent spec covering: {section_list}. "
            "Please review and let me know if anything needs adjustment before we finalize."
        )
    return _AGENT_PHASE_QUESTIONS.get(phase, "What would you like to refine?")


def build_squad_question(phase: str, spec: dict[str, Any]) -> str:
    """Return the deep question for the given squad authoring phase."""
    if phase == "approval" and spec:
        filled = [k for k in ("team_design", "workflow_design", "review_design") if spec.get(k)]
        section_list = ", ".join(filled) if filled else "none yet"
        return (
            f"Here is a summary of your squad design covering: {section_list}. "
            "Please review and approve to publish the squad spec."
        )
    return _SQUAD_PHASE_QUESTIONS.get(phase, "What would you like to refine?")


# ---------------------------------------------------------------------------
# Phase advancement
# ---------------------------------------------------------------------------


def advance_agent_phase(current: AuthoringPhase, spec: dict[str, Any]) -> AuthoringPhase:
    """Advance to the next phase if the current phase's section is filled.

    Returns the current phase unchanged if the section is still empty.
    """
    if current == AuthoringPhase.SUMMARY:
        return AuthoringPhase.SUMMARY

    spec_key = _AGENT_PHASE_TO_SPEC_KEY.get(current)
    if spec_key and not (spec.get(spec_key, "") or "").strip():
        return current

    current_idx = _AGENT_PHASE_ORDER.index(current)
    if current_idx + 1 < len(_AGENT_PHASE_ORDER):
        return _AGENT_PHASE_ORDER[current_idx + 1]
    return current


def advance_squad_phase(current: str, spec: dict[str, Any]) -> str:
    """Advance to the next squad phase if the current section is filled."""
    if current == "approval":
        return "approval"

    if not (spec.get(current, "") or "").strip():
        return current

    current_idx = _SQUAD_PHASE_ORDER.index(current)
    if current_idx + 1 < len(_SQUAD_PHASE_ORDER):
        return _SQUAD_PHASE_ORDER[current_idx + 1]
    return current


# ---------------------------------------------------------------------------
# LLM prompt assembly
# ---------------------------------------------------------------------------

_AGENT_AUTHORING_SYSTEM_PROMPT = """\
You are a structured agent authoring assistant for Mission Control.
Your role is to guide the user through creating a well-defined agent spec
by asking deep, focused questions one phase at a time.

Current authoring phase: {phase}

You must extract the key information from the user's response and summarize
it clearly and concisely. Focus on understanding the agent's:
- Purpose and goals
- Operating context and environment
- Working style and communication approach
- Execution policy (autonomous vs. supervised)
- Review and quality requirements

Do NOT generate YAML. Respond with a clear, natural language summary of what
you understood from the user's input, focusing on the current phase.
"""

_SQUAD_AUTHORING_SYSTEM_PROMPT = """\
You are a structured squad authoring assistant for Mission Control.
Your role is to guide the user through creating a well-defined squad spec
by asking deep, focused questions one phase at a time.

Current authoring phase: {phase}

Squad phases: team_design -> workflow_design -> review_design -> approval

You must extract the key information from the user's response and summarize
it clearly and concisely. Focus on understanding the squad's:
- Team composition (agent roles and specialties)
- Workflow structure (steps, handoffs, exit criteria)
- Review and approval policy
- Overall squad purpose

Do NOT generate YAML. Respond with a clear, natural language summary of what
you understood from the user's input, focusing on the current phase.
"""


# ---------------------------------------------------------------------------
# LLM-backed generation
# ---------------------------------------------------------------------------


async def generate_agent_assist_response(
    provider: Any,
    messages: list[dict[str, str]],
    current_spec: dict[str, Any],
    phase: AuthoringPhase,
    model: str | None = None,
) -> AuthoringResponse:
    """Generate a structured authoring response for the agent wizard.

    Args:
        provider: An LLMProvider instance.
        messages: The conversation history (role/content dicts).
        current_spec: The current in-progress agent spec draft.
        phase: The current authoring phase.
        model: Optional model override.

    Returns:
        An AuthoringResponse with the next question, draft patch, and metadata.
    """
    system_prompt = _AGENT_AUTHORING_SYSTEM_PROMPT.format(phase=phase.value)

    # Build LLM messages: system + conversation history
    llm_messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    llm_messages.extend(messages)

    kwargs: dict[str, Any] = {}
    if model:
        kwargs["model"] = model

    _response = await provider.chat(  # noqa: F841
        messages=llm_messages,
        temperature=0.5,
        max_tokens=1024,
        **kwargs,
    )

    # Extract the user's last message as the phase's draft content
    last_user_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    # Build the draft patch: update the current phase's spec key
    spec_key = _AGENT_PHASE_TO_SPEC_KEY.get(phase)
    patch_fields: dict[str, Any] = {}
    if spec_key and last_user_msg.strip():
        patch_fields[spec_key] = last_user_msg.strip()

    # Merge the patch into the current spec for readiness computation
    merged_spec = {**current_spec, **patch_fields}

    readiness = compute_readiness(merged_spec)
    next_phase = advance_agent_phase(phase, merged_spec)
    next_question = build_agent_question(next_phase, merged_spec)

    # Build summary sections from merged spec
    summary_sections: dict[str, Any] = {
        k: v for k, v in merged_spec.items() if isinstance(v, str) and v.strip()
    }

    return AuthoringResponse(
        question=next_question,
        draft_patch=SpecDraftPatch(fields=patch_fields),
        phase=next_phase,
        readiness=readiness,
        summary_sections=summary_sections,
        recommended_next_phase=next_phase,
    )


async def generate_squad_assist_response(
    provider: Any,
    messages: list[dict[str, str]],
    current_spec: dict[str, Any],
    phase: str,
    model: str | None = None,
) -> dict[str, Any]:
    """Generate a structured authoring response for the squad wizard.

    Returns a plain dict (not a dataclass) to keep the squad contract flexible
    as squad spec fields evolve.
    """
    system_prompt = _SQUAD_AUTHORING_SYSTEM_PROMPT.format(phase=phase)

    llm_messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    llm_messages.extend(messages)

    kwargs: dict[str, Any] = {}
    if model:
        kwargs["model"] = model

    _response = await provider.chat(  # noqa: F841
        messages=llm_messages,
        temperature=0.5,
        max_tokens=1024,
        **kwargs,
    )

    # Extract last user message
    last_user_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    # Build draft patch for squad phase
    patch_fields: dict[str, Any] = {}
    if phase in _SQUAD_PHASE_ORDER and last_user_msg.strip():
        patch_fields[phase] = last_user_msg.strip()

    merged_spec = {**current_spec, **patch_fields}
    next_phase = advance_squad_phase(phase, merged_spec)
    next_question = build_squad_question(next_phase, merged_spec)

    # Compute readiness as fraction of squad phases filled
    squad_keys = [p for p in _SQUAD_PHASE_ORDER if p != "approval"]
    filled = sum(1 for k in squad_keys if (merged_spec.get(k) or "").strip())
    readiness = filled / len(squad_keys) if squad_keys else 0.0

    summary_sections: dict[str, Any] = {
        k: v for k, v in merged_spec.items() if isinstance(v, str) and v.strip()
    }

    return {
        "question": next_question,
        "draft_patch": {"fields": patch_fields},
        "phase": next_phase,
        "readiness": readiness,
        "summary_sections": summary_sections,
        "recommended_next_phase": next_phase,
    }
