"""Helpers for propagating configured secrets to subprocess environments."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nanobot.config.schema import Config, ProviderConfig
    from nanobot.providers.registry import ProviderSpec

_SECRETS_PATH = Path.home() / ".nanobot" / "secrets.json"


def _load_secrets_file() -> dict[str, str]:
    """Load all key-value pairs from ``~/.nanobot/secrets.json``.

    Generic mechanism — any env var can be added and it will be injected
    into every agent environment automatically.

    Example ``~/.nanobot/secrets.json``::

        {"APIFY_API_TOKEN": "apify_api_...", "SOME_OTHER_KEY": "value"}
    """
    if not _SECRETS_PATH.exists():
        return {}
    try:
        data = json.loads(_SECRETS_PATH.read_text())
        if not isinstance(data, dict):
            return {}
        return {k: str(v) for k, v in data.items() if v}
    except (json.JSONDecodeError, OSError):
        return {}


def _known_secret_env_names() -> set[str]:
    """Return all env var names that may carry configured secrets."""
    from nanobot.providers.registry import PROVIDERS

    names = {"BRAVE_API_KEY"}
    for spec in PROVIDERS:
        if spec.env_key:
            names.add(spec.env_key)
        for env_name, _ in spec.env_extras:
            names.add(env_name)
    # Also include any names defined in config.json secrets
    names.update(_load_secrets_file().keys())
    return names


def _populate_provider_secret_env(
    target: dict[str, str],
    spec: ProviderSpec,
    provider_cfg: ProviderConfig | dict | None,
) -> None:
    """Add provider secrets if they are not already present."""
    if provider_cfg is None:
        return

    api_key = getattr(provider_cfg, "api_key", "")
    if not api_key:
        return

    if spec.env_key and spec.env_key not in target:
        target[spec.env_key] = api_key

    effective_base = getattr(provider_cfg, "api_base", None) or spec.default_api_base
    for env_name, template in spec.env_extras:
        if env_name in target:
            continue
        value = template.replace("{api_key}", api_key).replace("{api_base}", effective_base)
        target[env_name] = value


def resolve_secret_env(config: Config | None = None) -> dict[str, str]:
    """Resolve secret env vars from the current env and nanobot config."""
    from nanobot.config.loader import load_config
    from nanobot.providers.registry import PROVIDERS, find_by_name

    cfg = config or load_config()
    resolved: dict[str, str] = {}

    for env_name in _known_secret_env_names():
        value = os.environ.get(env_name)
        if value:
            resolved[env_name] = value

    active_provider_name = cfg.get_provider_name()
    if active_provider_name:
        active_spec = find_by_name(active_provider_name)
        active_cfg = getattr(cfg.providers, active_provider_name, None)
        if active_spec is not None and active_cfg is not None:
            _populate_provider_secret_env(resolved, active_spec, active_cfg)

    for spec in PROVIDERS:
        provider_cfg = getattr(cfg.providers, spec.name, None)
        if provider_cfg is None:
            continue
        _populate_provider_secret_env(resolved, spec, provider_cfg)

    if "BRAVE_API_KEY" not in resolved and cfg.tools.web.search.api_key:
        resolved["BRAVE_API_KEY"] = cfg.tools.web.search.api_key

    # Load generic secrets from config.json — fills anything not yet resolved
    for key, value in _load_secrets_file().items():
        if key not in resolved:
            resolved[key] = value

    return resolved


def build_subprocess_env(
    extra_env: dict[str, str] | None = None,
    config: Config | None = None,
) -> dict[str, str]:
    """Return a full subprocess environment with resolved secrets injected."""
    env = os.environ.copy()
    env.update(resolve_secret_env(config))
    if extra_env:
        env.update(extra_env)
    return env
