"""Model listing for agent configuration UIs.

Returns the model identifiers a user can assign to an agent. Anthropic OAuth
models are exposed with the ``cc/`` prefix so they route through the Claude Code
ACP backend.
"""

from __future__ import annotations


def _to_cc_prefix(models: list[str]) -> list[str]:
    """Replace the anthropic-oauth/ prefix with cc/ so models route through Claude Code."""
    result: list[str] = []
    for m in models:
        if m.startswith("anthropic-oauth/") or m.startswith("anthropic_oauth/"):
            result.append("cc/" + m.split("/", 1)[1])
        else:
            result.append(m)
    return result


def list_available_models() -> list[str]:
    """Return model identifiers available for agent assignment.

    Priority: the explicit ``agents.models`` list, else the default model.
    """
    from mc.infrastructure.config import load_config

    config = load_config()
    if config.agents.models:
        return _to_cc_prefix(list(config.agents.models))
    default_model = config.agents.defaults.model
    return _to_cc_prefix([default_model] if default_model else [])
