"""Harness registry — immutable table of ACP-compatible agent harnesses.

Each HarnessSpec records how to launch a harness subprocess and how to
translate uniform tier labels (low/medium/high) to the concrete model ID
that harness understands. Adding a new harness is a data entry here, not
new wiring elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field


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
        model_env: Environment variable the adapter reads to pick the model
            (e.g. "ANTHROPIC_MODEL" for claude-agent-acp). None when the
            harness has no env override and selects its model another way
            (e.g. Codex reads ~/.codex/config.toml).
        session_param_style: How session/new conveys MCP and tool scoping.
            "claude_code" wraps them in the adapter's non-standard
            claudeCode.options block; "standard" passes the spec-defined
            mcpServers field only.
        model_via_session: True when the model is applied with an explicit
            session/set_model after session creation rather than an env var
            (Codex has no model env; it accepts session/set_model).
        env_overrides: Adapter subprocess env adjustments. A None value unsets
            the variable. Codex unsets OPENAI_API_KEY / CODEX_API_KEY so the
            ChatGPT subscription credentials in auth.json take effect.
    """

    name: str
    launch_command: tuple[str, ...]
    native_acp: bool
    model_tiers: dict[str, str]
    model_env: str | None = "ANTHROPIC_MODEL"
    session_param_style: str = "claude_code"
    model_via_session: bool = False
    env_overrides: dict[str, str | None] = field(default_factory=dict)
    # Names the env var a harness uses to select its profile/home directory
    # (Hermes: HERMES_HOME). None for harnesses without profile selection.
    profile_env: str | None = None


HARNESSES: dict[str, HarnessSpec] = {
    "claude-code": HarnessSpec(
        name="claude-code",
        launch_command=("npx", "-y", "@agentclientprotocol/claude-agent-acp"),
        native_acp=False,
        # Spike-verified: claude-agent-acp v0.40.0 reads ANTHROPIC_MODEL.
        # "default" is the alias for Opus 4.8 on a MAX account.
        model_tiers={"low": "haiku", "medium": "sonnet", "high": "default"},
    ),
    "codex": HarnessSpec(
        name="codex",
        launch_command=("npx", "-y", "@zed-industries/codex-acp"),
        native_acp=False,
        # codex-acp (codex-rs rust-v0.133.0) has no model env var; it reads
        # ~/.codex/config.toml or accepts session/set_model. Tier slugs from
        # the bundled catalog: high=gpt-5.5, medium=gpt-5.4, low=gpt-5.4-mini.
        model_tiers={"low": "gpt-5.4-mini", "medium": "gpt-5.4", "high": "gpt-5.5"},
        model_env=None,
        session_param_style="standard",
        model_via_session=True,
        # ChatGPT subscription auth (auth_mode=chatgpt in ~/.codex/auth.json)
        # only wins when no API key env is present.
        env_overrides={"OPENAI_API_KEY": None, "CODEX_API_KEY": None},
    ),
    "hermes": HarnessSpec(
        name="hermes",
        launch_command=("uvx", "--from", "hermes-agent[acp]==0.15.2", "hermes-acp"),
        native_acp=True,
        # Model is owned by the Hermes profile (config.yaml), not by OpenControl.
        # No tier mapping, no model env, no per-session set_model.
        model_tiers={},
        model_env=None,
        session_param_style="standard",
        model_via_session=False,
        profile_env="HERMES_HOME",
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


def is_registered_harness(name: str | None) -> bool:
    """Return True if *name* names a harness in the registry."""
    return name in HARNESSES


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
