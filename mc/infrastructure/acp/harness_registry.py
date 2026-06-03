"""Harness registry — immutable table of ACP-compatible agent harnesses.

Each HarnessSpec records how to launch a harness subprocess and how to
translate uniform tier labels (low/medium/high) to the concrete model ID
that harness understands. Adding a new harness is a data entry here, not
new wiring elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HarnessSpec:
    """Immutable descriptor for one ACP-compatible agent harness.

    Attributes:
        name: Registry key (e.g. "claude-code").
        launch_command: Command + args tuple to spawn the adapter subprocess.
            Use tuple so the frozen dataclass remains hashable.
            Convert to list at call sites: list(spec.launch_command).
        native_acp: True if the harness speaks ACP natively; False means it
            is wrapped by an adapter (e.g. claude-agent-acp).
        model_tiers: Maps uniform tier labels ("low", "medium", "high") to
            the concrete model ID this harness accepts. A label absent from
            this dict is not a valid tier for the harness; callers that pass
            a concrete model ID receive it unchanged (pass-through).
    """

    name: str
    launch_command: tuple[str, ...]
    native_acp: bool
    model_tiers: dict[str, str]


HARNESSES: dict[str, HarnessSpec] = {
    "claude-code": HarnessSpec(
        name="claude-code",
        launch_command=("npx", "-y", "@agentclientprotocol/claude-agent-acp"),
        native_acp=False,
        # Spike-verified: claude-agent-acp v0.40.0 reads ANTHROPIC_MODEL.
        # "default" is the alias for Opus 4.8 on a MAX account.
        model_tiers={"low": "haiku", "medium": "sonnet", "high": "default"},
    ),
}


def get_harness(name: str) -> HarnessSpec:
    """Return the HarnessSpec for *name*.

    Raises:
        ValueError: If *name* is not registered in HARNESSES.
    """
    spec = HARNESSES.get(name)
    if spec is None:
        known = ", ".join(sorted(HARNESSES))
        raise ValueError(f"Unknown harness {name!r}. Known harnesses: {known}")
    return spec


def resolve_model(spec: HarnessSpec, model: str | None) -> str | None:
    """Translate a tier label to this harness's concrete model ID.

    If *model* is a key in *spec.model_tiers*, return the mapped value.
    Otherwise return *model* unchanged — concrete model IDs and None pass
    through without modification.

    Args:
        spec: The harness whose tier table is consulted.
        model: A tier label ("low", "medium", "high"), a concrete model ID,
            or None.

    Returns:
        The concrete model ID for this harness, or None.
    """
    if model is None:
        return None
    return spec.model_tiers.get(model, model)
