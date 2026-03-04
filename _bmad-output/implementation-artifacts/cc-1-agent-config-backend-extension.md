# Story CC-1: Agent Config Backend Extension

Status: complete

## Story

As an **admin**,
I want to specify `backend: claude-code` in an agent's config.yaml with Claude Code-specific options,
so that Mission Control knows which execution engine to use for each agent.

## Acceptance Criteria

### AC1: Backend Field in Agent Config YAML

**Given** an agent config file at `~/.nanobot/agents/{name}/config.yaml`
**When** the YAML includes `backend: claude-code`
**Then** the validator accepts it as a valid backend value
**And** `backend: nanobot` is also valid (explicit default)
**When** `backend` is omitted
**Then** it defaults to `"nanobot"` (backward compatible)
**When** `backend` is set to an invalid value (e.g., `"openai"`)
**Then** validation returns an error: "Invalid backend 'openai'. Valid options: nanobot, claude-code"

### AC2: Claude Code Options in Agent Config

**Given** an agent config with `backend: claude-code`
**When** the YAML includes a `claude_code` section
**Then** the validator accepts these fields:
```yaml
claude_code:
  max_budget_usd: 5.0         # float, optional, default from global config
  max_turns: 50                # int, optional, default from global config
  permission_mode: acceptEdits # str, optional, default "acceptEdits"
  allowed_tools:               # list[str], optional
    - Read
    - Glob
    - Grep
    - Bash
  disallowed_tools:            # list[str], optional
    - Write
```
**And** all fields are optional with sensible defaults
**When** `backend: nanobot` and `claude_code` section exists
**Then** the `claude_code` section is ignored (no error)

### AC3: Global Claude Code Config

**Given** the nanobot config at `~/.nanobot/config.json`
**When** a `claude_code` section is present
**Then** it provides defaults for all Claude Code agents:
```json
{
  "claude_code": {
    "cli_path": "claude",
    "default_model": "claude-sonnet-4-6",
    "default_max_budget_usd": 5.0,
    "default_max_turns": 50,
    "default_permission_mode": "acceptEdits",
    "auth_method": "oauth"
  }
}
```
**And** `cli_path` defaults to `"claude"` (found via PATH)
**And** `auth_method` accepts `"oauth"` or `"api_key"` (default `"oauth"`)
**When** the `claude_code` section is absent
**Then** defaults are used and no error is raised

### AC4: AgentData Extension

**Given** the `AgentData` dataclass in `mc/types.py`
**When** an agent config is loaded with `backend: claude-code`
**Then** `AgentData.backend` is `"claude-code"`
**And** `AgentData.claude_code_opts` contains the parsed Claude Code options
**When** an agent config has `backend: nanobot` or no backend
**Then** `AgentData.backend` is `"nanobot"`
**And** `AgentData.claude_code_opts` is `None`

### AC5: Gateway Sync Compatibility

**Given** the gateway syncs agent configs to Convex via `sync_agent_registry()`
**When** an agent has `backend: claude-code`
**Then** the backend field is synced to Convex as part of agent metadata
**And** existing nanobot agents are unaffected
**And** the dashboard can display which backend each agent uses

## Tasks / Subtasks

- [x] **Task 1: Add backend field to AgentConfig pydantic model** (AC: #1)
  - [x] 1.1 In `mc/yaml_validator.py`, add to `AgentConfig` class:
    ```python
    backend: Optional[str] = None  # "nanobot" | "claude-code", defaults to "nanobot"
    ```
  - [x] 1.2 Add field validator for `backend`:
    ```python
    @field_validator("backend")
    @classmethod
    def validate_backend(cls, v: str | None) -> str | None:
        if v is None:
            return None
        valid = {"nanobot", "claude-code"}
        if v not in valid:
            raise ValueError(
                f"Invalid backend '{v}'. Valid options: {', '.join(sorted(valid))}"
            )
        return v
    ```
  - [x] 1.3 Add `claude_code` field as optional dict:
    ```python
    claude_code: Optional[dict] = None
    ```

- [x] **Task 2: Create ClaudeCodeOpts dataclass** (AC: #2)
  - [x] 2.1 In `mc/types.py`, add dataclass:
    ```python
    @dataclass
    class ClaudeCodeOpts:
        max_budget_usd: float | None = None
        max_turns: int | None = None
        permission_mode: str = "acceptEdits"
        allowed_tools: list[str] | None = None
        disallowed_tools: list[str] | None = None
    ```
  - [x] 2.2 Add `backend: str = "nanobot"` field to `AgentData` dataclass
  - [x] 2.3 Add `claude_code_opts: ClaudeCodeOpts | None = None` field to `AgentData`

- [x] **Task 3: Update validate_agent_file to parse new fields** (AC: #1, #2, #4)
  - [x] 3.1 In `mc/yaml_validator.py` `validate_agent_file()`, after constructing `AgentData`, populate the new fields:
    ```python
    backend = validated.backend or "nanobot"
    cc_opts = None
    if backend == "claude-code" and validated.claude_code:
        cc_opts = ClaudeCodeOpts(
            max_budget_usd=validated.claude_code.get("max_budget_usd"),
            max_turns=validated.claude_code.get("max_turns"),
            permission_mode=validated.claude_code.get("permission_mode", "acceptEdits"),
            allowed_tools=validated.claude_code.get("allowed_tools"),
            disallowed_tools=validated.claude_code.get("disallowed_tools"),
        )
    ```
  - [x] 3.2 Pass `backend=backend, claude_code_opts=cc_opts` to `AgentData` constructor

- [x] **Task 4: Add ClaudeCodeConfig to global config schema** (AC: #3)
  - [x] 4.1 In `vendor/nanobot/nanobot/config/schema.py`, add a new model:
    ```python
    class ClaudeCodeConfig(Base):
        cli_path: str = "claude"
        default_model: str = "claude-sonnet-4-6"
        default_max_budget_usd: float = 5.0
        default_max_turns: int = 50
        default_permission_mode: str = "acceptEdits"
        auth_method: str = "oauth"  # "oauth" | "api_key"
    ```
  - [x] 4.2 Add `claude_code: ClaudeCodeConfig = ClaudeCodeConfig()` to the top-level `Config` class

- [x] **Task 5: Update gateway sync for backend field** (AC: #5)
  - [x] 5.1 In `mc/gateway.py` `sync_agent_registry()`, include `backend` in the agent data synced to Convex
  - [x] 5.2 Ensure backward compatibility — existing agents without `backend` field default to `"nanobot"`

- [x] **Task 6: Tests** (AC: all)
  - [x] 6.1 In `tests/mc/test_yaml_validator.py`, add tests:
    - Valid `backend: claude-code` with claude_code options
    - Valid `backend: nanobot` (explicit)
    - Missing backend (defaults to nanobot)
    - Invalid backend value
    - `claude_code` section with `backend: nanobot` (ignored, no error)
  - [x] 6.2 In `tests/mc/test_types.py`, add tests for `ClaudeCodeOpts` dataclass
  - [x] 6.3 Run: `uv run pytest tests/mc/test_yaml_validator.py tests/mc/test_types.py -v`

### Review Follow-ups (AI)

- [x] [AI-Review][HIGH] No type validation on claude_code dict values -- garbage strings pass through to ClaudeCodeOpts numeric fields silently [mc/yaml_validator.py:238-245, mc/types.py:306-312]
- [x] [AI-Review][HIGH] ClaudeCodeConfig.auth_method accepts any string; should use Literal["oauth", "api_key"] [vendor/nanobot/nanobot/config/schema.py:329]
- [x] [AI-Review][HIGH] write_agent_config drops backend and claude_code on Convex-to-local round-trip [mc/bridge.py:742-766]
- [x] [AI-Review][MEDIUM] ClaudeCodeConfig accepts negative values for default_max_budget_usd and default_max_turns [vendor/nanobot/nanobot/config/schema.py:324-328]
- [x] [AI-Review][MEDIUM] bridge.sync_agent uses unnecessary hasattr guard for backend; inconsistent with other field patterns [mc/bridge.py:557]
- [x] [AI-Review][MEDIUM] Missing test for claude_code section with backend omitted (should be ignored, defaulting to nanobot) [tests/mc/test_yaml_validator.py]
- [x] [AI-Review][LOW] permission_mode not validated against known Claude Code modes (default/acceptEdits/bypassPermissions) [vendor/nanobot/nanobot/config/schema.py:328, mc/types.py:310]
- [x] [AI-Review][LOW] Story task checkboxes all [ ] despite implementation being complete; Dev Agent Record section empty [cc-1-agent-config-backend-extension.md:88-167]
- [x] [AI-Review][LOW] No tests for ClaudeCodeConfig global schema model (defaults, camelCase aliases) [vendor/nanobot/nanobot/config/schema.py:321-329]

## Dev Notes

### Architecture Patterns

- **Backward compatibility**: The `backend` field defaults to `"nanobot"` when omitted. No existing config files need changes.
- **Validation-only scope**: This story only adds config parsing and validation. No execution logic — that's CC-4 (ClaudeCodeProvider).
- **Global vs per-agent**: Per-agent `claude_code` options override global `claude_code` defaults from `config.json`. The merge happens at execution time (CC-4), not here.

### Code to Reuse

- `mc/yaml_validator.py` — `AgentConfig` pydantic model, `validate_agent_file()` function
- `mc/types.py` — `AgentData` dataclass
- `vendor/nanobot/nanobot/config/schema.py` — `Config`, `Base` pydantic models

### Common Mistakes to Avoid

- Do NOT add execution logic here — this story is strictly config schema + validation
- Do NOT modify the Convex schema — the backend field can be stored in existing agent metadata
- Do NOT make `claude_code` a Pydantic model in yaml_validator — keep it as `Optional[dict]` for flexibility since the YAML format may evolve
- Use `uv run python` not `python3`. Use `uv run pytest` for tests.

### Project Structure Notes

- **MODIFIED**: `mc/yaml_validator.py` — Add `backend` and `claude_code` fields to `AgentConfig`
- **MODIFIED**: `mc/types.py` — Add `ClaudeCodeOpts` dataclass, extend `AgentData`
- **MODIFIED**: `vendor/nanobot/nanobot/config/schema.py` — Add `ClaudeCodeConfig`
- **MODIFIED**: `mc/gateway.py` — Include backend in sync
- **NEW**: Tests in `tests/mc/test_yaml_validator.py` (additions)

### References

- `mc/yaml_validator.py` — AgentConfig class, validate_agent_file function
- `mc/types.py` — AgentData dataclass (line ~80)
- `vendor/nanobot/nanobot/config/schema.py` — Config, Base models
- `mc/gateway.py` — sync_agent_registry function

## Dev Agent Record

### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
