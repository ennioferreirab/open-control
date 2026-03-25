"""Generate MCP tool definitions from shared entity specs.

Reads JSON specs from ``shared/specs/`` and produces:

- MCP ``Tool`` objects with correct JSON Schema ``inputSchema``
- Field name lists for generic bridge dispatch
- camelCase field names matching the spec (bridge handles snake conversion)

This module is the Python-side reader of the single source of truth.
The specs are the canonical field definitions — changes here propagate
to MCP tools, bridge dispatch, and IPC handlers automatically.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.types import Tool

# ---------------------------------------------------------------------------
# Spec loading
# ---------------------------------------------------------------------------

_SPECS_DIR = Path(__file__).resolve().parents[3] / "shared" / "specs"
_cache: dict[str, dict[str, Any]] = {}
_entity_to_file: dict[str, str] = {}  # entity name → file stem


def _load_spec(entity: str) -> dict[str, Any]:
    """Load and cache a shared entity spec JSON file."""
    if entity in _cache:
        return _cache[entity]

    # Try entity-to-file mapping first (populated by load_all_specs)
    file_stem = _entity_to_file.get(entity, entity)
    path = _SPECS_DIR / f"{file_stem}.json"
    _cache[entity] = json.loads(path.read_text(encoding="utf-8"))
    return _cache[entity]


def load_all_specs() -> dict[str, dict[str, Any]]:
    """Load all entity specs from shared/specs/. Keyed by entity name."""
    specs = {}
    for path in sorted(_SPECS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        entity = data["entity"]
        _cache[entity] = data
        _entity_to_file[entity] = path.stem
        specs[entity] = data
    return specs


# ---------------------------------------------------------------------------
# JSON Schema generation from spec fields
# ---------------------------------------------------------------------------

_TYPE_MAP = {
    "string": {"type": "string"},
    "number": {"type": "number"},
    "boolean": {"type": "boolean"},
    "string[]": {"type": "array", "items": {"type": "string"}},
    "object": {"type": "object"},
    "object[]": {"type": "array"},
}


def _field_to_json_schema(field: dict[str, Any]) -> dict[str, Any]:
    """Convert a single spec field to JSON Schema property."""
    field_type = field["type"]
    schema: dict[str, Any] = {}

    if field_type in _TYPE_MAP:
        schema.update(_TYPE_MAP[field_type])
    elif field_type.endswith("[]"):
        schema["type"] = "array"

    if "enum" in field:
        if schema.get("type") == "array":
            schema["items"] = {"type": "string", "enum": field["enum"]}
        else:
            schema["enum"] = field["enum"]

    if "description" in field:
        schema["description"] = field["description"]

    if "minItems" in field:
        schema["minItems"] = field["minItems"]

    # Nested object properties
    if "properties" in field:
        schema["type"] = "object"
        schema["properties"], nested_required = _fields_to_json_schema(field["properties"])
        if nested_required:
            schema["required"] = nested_required
        schema["additionalProperties"] = False

    if "itemProperties" in field:
        schema["type"] = "array"
        item_schema: dict[str, Any] = {"type": "object"}
        item_schema["properties"], item_required = _fields_to_json_schema(field["itemProperties"])
        if item_required:
            item_schema["required"] = item_required
        item_schema["additionalProperties"] = False
        schema["items"] = item_schema

    return schema


def _fields_to_json_schema(
    fields: dict[str, Any],
    operation: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Convert a fields dict to JSON Schema properties + required list."""
    properties: dict[str, Any] = {}
    required: list[str] = []

    for name, field in fields.items():
        # Filter by operation if specified
        if operation and "operations" in field:
            if operation not in field["operations"]:
                continue

        properties[name] = _field_to_json_schema(field)

        if field.get("required"):
            required.append(name)

    return properties, required


# ---------------------------------------------------------------------------
# MCP Tool generation
# ---------------------------------------------------------------------------


def generate_tool(entity: str, operation: str) -> Tool:
    """Generate an MCP Tool from a shared spec operation."""
    spec = _load_spec(entity)
    op = spec["operations"][operation]
    fields = spec.get("fields", {})

    # Build input schema from fields for this operation
    properties, required = _fields_to_json_schema(fields, operation)

    # Add list params if this is a list operation
    if operation == "list" and "listParams" in spec:
        list_props, _ = _fields_to_json_schema(spec["listParams"])
        properties.update(list_props)

    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        input_schema["required"] = required

    return Tool(
        name=op["mcpTool"],
        description=op["mcpDescription"],
        inputSchema=input_schema,
    )


def generate_all_tools() -> list[Tool]:
    """Generate all MCP tools from all shared specs."""
    tools: list[Tool] = []
    for spec in load_all_specs().values():
        for operation in spec.get("operations", {}):
            op_meta = spec["operations"][operation]
            if "mcpTool" not in op_meta:
                continue
            tools.append(generate_tool(spec["entity"], operation))
    return tools


# ---------------------------------------------------------------------------
# Field name extraction for dispatch
# ---------------------------------------------------------------------------


def get_field_names(entity: str, operation: str | None = None) -> list[str]:
    """Get camelCase field names for an entity, optionally filtered by operation."""
    spec = _load_spec(entity)
    fields = spec.get("fields", {})
    names = []
    for name, field in fields.items():
        if operation and "operations" in field:
            if operation not in field["operations"]:
                continue
        names.append(name)
    return names


def get_operation_meta(entity: str, operation: str) -> dict[str, Any]:
    """Get operation metadata (mutation name, IPC method, etc.)."""
    spec = _load_spec(entity)
    return spec["operations"][operation]
