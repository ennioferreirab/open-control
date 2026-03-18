# Story 3.1: Implement YAML Agent Validator

Status: done

## Story

As a **developer**,
I want a YAML validation module that enforces agent configuration schema with clear, actionable error messages,
So that invalid agent configs are caught early with guidance on how to fix them.

## Acceptance Criteria

1. **Given** a YAML agent configuration file exists in the agents folder, **When** the validator loads and parses the file, **Then** it validates required fields: `name` (string), `role` (string), `prompt` (string)
2. **Given** a YAML file is loaded, **Then** it validates optional fields: `skills` (array of strings), `model` (string), `displayName` (string)
3. **Given** a field fails validation, **Then** the error message includes: field name, expected type/value, and actionable fix suggestion (NFR22)
4. **Given** a YAML file has multiple validation errors, **Then** all errors are collected and returned together (not fail-on-first)
5. **Given** an agent YAML file has an invalid configuration, **When** the system attempts to load it, **Then** the system refuses to start that agent (FR14) and logs the error to stdout with full context
6. **Given** an invalid agent config exists, **Then** other valid agents in the same folder are not affected by the invalid one
7. **Given** a valid agent YAML file is loaded, **When** validation succeeds, **Then** the agent data is returned as an `AgentData` dataclass matching the Convex `agents` table schema
8. **Given** a YAML file does not specify a `displayName`, **Then** the validator generates a display name by title-casing the `name` field (e.g., "dev-agent" -> "Dev Agent")
9. **Given** a YAML file does not specify `skills`, **Then** the validator defaults to an empty list
10. **And** the module is created at `nanobot/mc/yaml_validator.py` using pydantic for schema validation
11. **And** the module does not exceed 500 lines (NFR21)
12. **And** unit tests exist in `nanobot/mc/test_yaml_validator.py` covering valid configs, missing required fields, wrong types, and multi-error collection

## Tasks / Subtasks

- [ ] Task 1: Create the pydantic validation model (AC: #1, #2, #3)
  - [ ] 1.1: Create `nanobot/mc/yaml_validator.py` with pydantic `BaseModel` for agent config
  - [ ] 1.2: Define required fields: `name` (str, non-empty), `role` (str, non-empty), `prompt` (str, non-empty)
  - [ ] 1.3: Define optional fields: `skills` (list[str], default=[]), `model` (str | None, default=None), `display_name` (str | None, default=None)
  - [ ] 1.4: Add pydantic `field_validator` for `name` to enforce lowercase, alphanumeric + hyphens only (valid for filenames/identifiers)
  - [ ] 1.5: Add custom pydantic error messages that include field name, expected type, and fix suggestion

- [ ] Task 2: Implement multi-error collection (AC: #3, #4)
  - [ ] 2.1: Use pydantic's built-in `ValidationError` which collects all errors per model
  - [ ] 2.2: Create a `format_validation_errors(error: ValidationError) -> list[str]` function that transforms pydantic errors into human-readable messages with fix suggestions
  - [ ] 2.3: Each formatted error follows pattern: `"Field '{field}': {message}. Expected {expected}. Fix: {suggestion}"`

- [ ] Task 3: Implement YAML file loading and validation (AC: #1, #5, #6, #7)
  - [ ] 3.1: Create `validate_agent_file(path: Path) -> AgentData | list[str]` function that loads YAML, runs pydantic validation, and returns either a valid `AgentData` or list of error strings
  - [ ] 3.2: Handle YAML parsing errors (malformed YAML) with a clear error message
  - [ ] 3.3: Handle file-not-found and permission errors gracefully
  - [ ] 3.4: On success, convert the validated pydantic model to an `AgentData` dataclass from `types.py`

- [ ] Task 4: Implement display name auto-generation (AC: #8)
  - [ ] 4.1: If `display_name` is not provided in YAML, generate from `name` by replacing hyphens/underscores with spaces and title-casing
  - [ ] 4.2: Implement as a pydantic `model_validator` that runs after field validation

- [ ] Task 5: Implement directory-level batch validation (AC: #6)
  - [ ] 5.1: Create `validate_agents_dir(dir_path: Path) -> tuple[list[AgentData], dict[str, list[str]]]` that scans a directory for `.yaml`/`.yml` files
  - [ ] 5.2: Returns a tuple of (valid agents, errors dict keyed by filename)
  - [ ] 5.3: Log errors for invalid files but continue processing valid ones

- [ ] Task 6: Write unit tests (AC: #12)
  - [ ] 6.1: Create `nanobot/mc/test_yaml_validator.py`
  - [ ] 6.2: Test valid config with all fields -> returns `AgentData`
  - [ ] 6.3: Test valid config with minimal fields (name, role, prompt only) -> returns `AgentData` with defaults
  - [ ] 6.4: Test missing required field `name` -> error includes field name and fix suggestion
  - [ ] 6.5: Test missing required field `role` -> error includes field name and fix suggestion
  - [ ] 6.6: Test missing required field `prompt` -> error includes field name and fix suggestion
  - [ ] 6.7: Test wrong type for `skills` (string instead of list) -> error with expected type
  - [ ] 6.8: Test multiple errors in one file -> all errors returned (not just first)
  - [ ] 6.9: Test malformed YAML -> clear parse error message
  - [ ] 6.10: Test display name auto-generation from name field
  - [ ] 6.11: Test `validate_agents_dir` with mix of valid and invalid files
  - [ ] 6.12: Test empty directory -> returns empty lists

## Dev Notes

### Critical Architecture Requirements

- **pydantic for validation**: Use pydantic v2 (`BaseModel`) for schema validation. pydantic's `ValidationError` natively collects all errors across all fields, satisfying the multi-error requirement (AC #4). Do NOT use cerberus, jsonschema, or manual validation loops.
- **AgentData from types.py**: The validated output MUST be converted to the `AgentData` dataclass defined in `nanobot/mc/types.py`. This is the shared Python type that mirrors the Convex `agents` table schema. The validator bridges YAML -> pydantic model -> AgentData.
- **500-line limit (NFR21)**: The validator module must stay under 500 lines. Keep it focused on validation logic only. No Convex calls, no file watching, no registry sync.
- **Bridge boundary**: This module does NOT interact with Convex. It only validates YAML files and returns Python dataclasses. The registry sync (Story 3.2) handles Convex writes.

### Agent YAML Schema

```yaml
# Required fields
name: dev-agent          # Unique identifier (lowercase, alphanumeric + hyphens)
role: Senior Developer   # Human-readable role description
prompt: "You are a..."   # System prompt for the agent

# Optional fields
skills:                  # List of capability tags for routing
  - code-review
  - debugging
  - testing
model: claude-sonnet-4-6  # LLM model override (system default if omitted)
displayName: Dev Agent   # Dashboard display name (auto-generated from name if omitted)
```

### Agent Configuration Path

Per UX design spec, agent YAML configs live in `~/.nanobot/agents/{name}/config.yaml`. The validator should accept individual file paths or scan a directory.

### Pydantic Model Pattern

```python
from pydantic import BaseModel, field_validator, model_validator

class AgentConfig(BaseModel):
    name: str
    role: str
    prompt: str
    skills: list[str] = []
    model: str | None = None
    display_name: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Agent name cannot be empty. Fix: provide a unique name like 'my-agent'")
        # lowercase, alphanumeric + hyphens
        ...
        return v

    @model_validator(mode="after")
    def set_display_name(self) -> "AgentConfig":
        if not self.display_name:
            self.display_name = self.name.replace("-", " ").replace("_", " ").title()
        return self
```

### Error Message Format (NFR22)

Each validation error MUST include three parts:
1. **Field name**: Which field has the error
2. **Expected type/value**: What was expected
3. **Actionable fix suggestion**: How to fix it

Example errors:
- `"Field 'name': value is required. Expected: non-empty string. Fix: add 'name: my-agent' to your YAML config."`
- `"Field 'skills': invalid type. Expected: list of strings (e.g., ['coding', 'research']). Fix: use YAML list syntax:\n  skills:\n    - coding\n    - research"`
- `"Field 'name': 'My Agent' contains invalid characters. Expected: lowercase alphanumeric + hyphens. Fix: use 'my-agent' instead of 'My Agent'."`

### YAML Key Convention

YAML files use snake_case keys (matching Python convention): `display_name`, not `displayName`. The bridge layer handles conversion to camelCase when writing to Convex.

### Common LLM Developer Mistakes to Avoid

1. **DO NOT use `yaml.safe_load` without error handling** -- Malformed YAML raises `yaml.YAMLError`. Catch it and return a clear error message including the file path.
2. **DO NOT fail on first error** -- pydantic v2's `ValidationError.errors()` returns ALL validation errors. Use this to collect all errors in a single pass.
3. **DO NOT import or call ConvexBridge** -- This module is pure validation. No network calls. No Convex interaction.
4. **DO NOT hardcode the agents directory path** -- Accept `Path` arguments. The caller decides where agents live.
5. **DO NOT skip the `AgentData` conversion** -- The return type must be `AgentData` from `types.py`, not the pydantic model directly. Other modules depend on `AgentData`.
6. **DO NOT use `yaml.dump` for anything** -- This module only reads and validates. Writing YAML is handled by Story 3.4 (CLI agent create).
7. **DO NOT use camelCase in YAML keys** -- YAML config uses snake_case (`display_name`). The bridge handles case conversion for Convex.
8. **DO NOT exceed 500 lines** -- Keep the module focused. If you're approaching the limit, you're doing too much.

### What This Story Does NOT Include

- **No Convex interaction** -- Registry sync to Convex `agents` table is Story 3.2
- **No file watching** -- Hot-reload of YAML changes is not required for MVP (NFR17 says detection on CLI command/refresh)
- **No agent creation** -- Writing new YAML files is Story 3.4
- **No system-wide default model resolution** -- Story 3.2 handles resolving the default model when syncing to Convex
- **No CLI commands** -- Stories 3.4 and 3.5 add CLI integration

### Files Created in This Story

| File | Purpose |
|------|---------|
| `nanobot/mc/yaml_validator.py` | Agent YAML schema validation using pydantic |
| `nanobot/mc/test_yaml_validator.py` | Unit tests for validation scenarios |

### Files Modified in This Story

None. This is a standalone new module.

### Verification Steps

1. Create a valid agent YAML file with all fields -- validator returns `AgentData`
2. Create a YAML file missing `name` -- error message includes field name, expected type, and fix suggestion
3. Create a YAML file with multiple errors (missing `role` + invalid `skills` type) -- all errors returned together
4. Create a malformed YAML file (bad indentation) -- clear parse error
5. Create a directory with 3 files: 2 valid, 1 invalid -- 2 `AgentData` returned + errors for the invalid one
6. Verify module is under 500 lines: `wc -l nanobot/mc/yaml_validator.py`
7. Run tests: `cd /Users/ennio/Documents/nanobot-ennio && python -m pytest nanobot/mc/test_yaml_validator.py -v`

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 3.1`] -- Original story definition with acceptance criteria
- [Source: `_bmad-output/planning-artifacts/architecture.md#Data Architecture`] -- pydantic for Python-side YAML validation
- [Source: `_bmad-output/planning-artifacts/prd.md#Agent Management`] -- FR10-FR14 agent configuration requirements
- [Source: `nanobot/mc/types.py`] -- `AgentData` dataclass definition
- [Source: `dashboard/convex/schema.ts`] -- Convex `agents` table schema (target data shape)
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#Agent Configuration UX`] -- Agent workspace structure

## Dev Agent Record

### Agent Model Used
claude-opus-4-6

### Debug Log References
N/A

### Completion Notes List
- Created pydantic v2 AgentConfig model with field validators for name (lowercase alphanumeric + hyphens), role, and prompt (non-empty checks)
- Implemented model_validator for auto-generating display_name from name field
- format_validation_errors() transforms pydantic ValidationError into human-readable messages with field name, expected type, and fix suggestions
- validate_agent_file() handles YAML parse errors, file I/O errors, and validation errors gracefully
- validate_agents_dir() scans directory for .yaml/.yml files, returns valid AgentData list + errors dict
- All errors collected per file (not fail-on-first) via pydantic's native multi-error collection
- Added optional `prompt` field to AgentData in types.py (local-only, not synced to Convex)
- 19 unit tests covering: valid configs, missing required fields, wrong types, multi-error collection, malformed YAML, directory validation
- Module is 217 lines (well under 500-line NFR21 limit)

### File List
| File | Action |
|------|--------|
| `nanobot/mc/yaml_validator.py` | Created - Agent YAML schema validation using pydantic v2 |
| `nanobot/mc/test_yaml_validator.py` | Created - 19 unit tests for validation scenarios |
| `nanobot/mc/types.py` | Modified - Added optional `prompt` field to AgentData dataclass |
