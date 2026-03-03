"""
YAML Agent Validator for Mission Control.

Validates agent YAML configuration files against the expected schema using
pydantic v2. Returns AgentData dataclasses on success or actionable error
messages on failure.

This module is pure validation — no Convex interaction, no file watching,
no agent creation.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, ValidationError, field_validator, model_validator

from mc.types import AgentData

logger = logging.getLogger(__name__)

_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# Maps pydantic error types to human-readable fix suggestions.
_FIX_SUGGESTIONS: dict[str, str] = {
    "missing": "add '{field}: <value>' to your YAML config.",
    "string_type": "provide a string value for '{field}'.",
    "list_type": (
        "use YAML list syntax for '{field}':\n"
        "  {field}:\n"
        "    - item1\n"
        "    - item2"
    ),
}

_EXPECTED_TYPES: dict[str, str] = {
    "missing": "non-empty string",
    "string_type": "string",
    "list_type": "list of strings (e.g., ['coding', 'research'])",
}


class AgentConfig(BaseModel):
    """Pydantic model for agent YAML configuration."""

    name: str
    role: str
    prompt: str
    skills: list[str] = []
    model: Optional[str] = None
    display_name: Optional[str] = None
    soul: Optional[str] = None
    is_system: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError(
                "Agent name cannot be empty. "
                "Fix: provide a unique name like 'my-agent'"
            )
        v = v.strip()
        if not _NAME_PATTERN.match(v):
            raise ValueError(
                f"'{v}' contains invalid characters. "
                "Expected: lowercase alphanumeric + hyphens. "
                f"Fix: use '{_to_slug(v)}' instead of '{v}'."
            )
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError(
                "Agent role cannot be empty. "
                "Fix: provide a role like 'Senior Developer'"
            )
        return v.strip()

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError(
                "Agent prompt cannot be empty. "
                "Fix: provide a system prompt like 'You are a coding assistant.'"
            )
        return v.strip()

    @model_validator(mode="after")
    def set_display_name(self) -> AgentConfig:
        if not self.display_name:
            self.display_name = (
                self.name.replace("-", " ").replace("_", " ").title()
            )
        return self


def _to_slug(value: str) -> str:
    """Convert an arbitrary string to a valid agent name slug."""
    slug = value.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "my-agent"


def format_validation_errors(error: ValidationError) -> list[str]:
    """Transform pydantic ValidationError into human-readable messages.

    Each message follows the pattern:
        Field '<field>': <message>. Expected <expected>. Fix: <suggestion>
    """
    messages: list[str] = []
    for err in error.errors():
        field_name = ".".join(str(loc) for loc in err["loc"])
        err_type = err["type"]
        raw_msg = err["msg"]

        # For custom ValueError messages raised in field_validators,
        # pydantic wraps them under type "value_error".
        if err_type == "value_error":
            messages.append(f"Field '{field_name}': {raw_msg}")
            continue

        expected = _EXPECTED_TYPES.get(err_type, "valid value")
        suggestion = _FIX_SUGGESTIONS.get(err_type, "check the field value.")
        suggestion = suggestion.format(field=field_name)

        messages.append(
            f"Field '{field_name}': {raw_msg}. "
            f"Expected: {expected}. "
            f"Fix: {suggestion}"
        )

    return messages


def validate_agent_file(path: Path) -> AgentData | list[str]:
    """Load and validate a single agent YAML file.

    Returns:
        AgentData on success, or a list of error strings on failure.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [f"File not found: {path}"]
    except PermissionError:
        return [f"Permission denied: {path}"]
    except OSError as exc:
        return [f"Cannot read file {path}: {exc}"]

    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        return [f"YAML parse error in {path}: {exc}"]

    if not isinstance(data, dict):
        return [
            f"Invalid YAML structure in {path}: expected a mapping (key: value pairs), "
            f"got {type(data).__name__}."
        ]

    try:
        config = AgentConfig(**data)
    except ValidationError as exc:
        return format_validation_errors(exc)

    # If soul not set in YAML, read SOUL.md from agent directory
    if not config.soul:
        soul_path = path.parent / "SOUL.md"
        if soul_path.is_file():
            try:
                config.soul = soul_path.read_text(encoding="utf-8")
            except OSError:
                pass

    return _config_to_agent_data(config)


def validate_agents_dir(
    dir_path: Path,
) -> tuple[list[AgentData], dict[str, list[str]]]:
    """Validate all agent YAML files in a directory.

    Returns:
        A tuple of (valid_agents, errors) where errors is a dict keyed by
        filename mapping to lists of error strings.
    """
    valid_agents: list[AgentData] = []
    errors: dict[str, list[str]] = {}

    if not dir_path.is_dir():
        logger.error("Agents directory does not exist: %s", dir_path)
        return valid_agents, errors

    yaml_files = sorted(
        p for p in dir_path.iterdir()
        if p.is_file() and p.suffix in (".yaml", ".yml")
    )

    for file_path in yaml_files:
        result = validate_agent_file(file_path)
        if isinstance(result, list):
            errors[file_path.name] = result
            for msg in result:
                logger.error("Invalid agent config %s: %s", file_path.name, msg)
        else:
            valid_agents.append(result)

    return valid_agents, errors


def _config_to_agent_data(config: AgentConfig) -> AgentData:
    """Convert a validated AgentConfig pydantic model to an AgentData dataclass."""
    return AgentData(
        name=config.name,
        display_name=config.display_name or config.name,
        role=config.role,
        prompt=config.prompt,
        soul=config.soul,
        skills=config.skills,
        model=config.model,
        is_system=config.is_system or False,
    )
