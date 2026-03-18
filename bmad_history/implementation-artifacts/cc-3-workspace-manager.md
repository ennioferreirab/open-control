# Story CC-3: Claude Code Workspace Manager

Status: ready-for-dev

## Story

As **Mission Control**,
I want to prepare a complete workspace for Claude Code agents before spawning them,
so that they have the correct CLAUDE.md, skills, and MCP configuration for their role.

## Acceptance Criteria

### AC1: CLAUDE.md Generation from Agent Config

**Given** an agent with `backend: claude-code` and a `prompt` field in config.yaml
**When** the workspace manager prepares the workspace
**Then** it generates a `CLAUDE.md` file in the agent's workspace directory with:
  - The agent's prompt/personality from config.yaml
  - Project conventions (configurable, from a shared template)
  - Instructions to use `mcp__nanobot__ask_user` instead of `AskUserQuestion`
  - Instructions to use `mcp__nanobot__report_progress` for status updates
  - Instructions to use `mcp__nanobot__send_message` for user-facing output
**And** if a CLAUDE.md already exists in the workspace, it is regenerated (not appended)

### AC2: Skills Mapping via Symlinks

**Given** an agent config with `skills: [github, code-quality]`
**When** the workspace manager prepares the workspace
**Then** it creates `.claude/skills/` directory in the workspace
**And** for each skill, creates a symlink from:
  `workspace/.claude/skills/{skill_name}/` → `{skills_source}/{skill_name}/`
**Where** skills_source follows the nanobot priority: workspace skills → global skills → builtin skills
**And** each symlinked skill directory contains a `SKILL.md` file
**When** a skill is not found in any source
**Then** it is logged as a warning but does not block workspace preparation

### AC3: MCP Config Generation

**Given** an agent being prepared for Claude Code execution
**When** the workspace manager generates the `.mcp.json` file
**Then** the file is written to the agent's workspace root with this structure:
```json
{
  "mcpServers": {
    "nanobot": {
      "command": "uv",
      "args": ["run", "python", "-m", "mc.mcp_bridge"],
      "env": {
        "MC_SOCKET_PATH": "/tmp/mc-{agent_name}.sock",
        "AGENT_NAME": "{agent_name}",
        "TASK_ID": "{task_id}"
      }
    }
  }
}
```
**And** `MC_SOCKET_PATH` uses the agent's name to avoid collisions between concurrent agents
**And** `TASK_ID` is set to the current task being executed

### AC4: Workspace Directory Structure

**Given** an agent workspace at `~/.nanobot/agents/{name}/`
**When** preparation completes
**Then** the directory structure is:
```
~/.nanobot/agents/{name}/
├── config.yaml           # existing, not modified
├── CLAUDE.md             # generated (AC1)
├── .mcp.json             # generated (AC3)
├── .claude/
│   └── skills/           # generated (AC2)
│       ├── github/  → symlink
│       └── code-quality/ → symlink
├── memory/               # existing or created
│   ├── MEMORY.md
│   └── HISTORY.md
└── sessions/             # existing or created
```

### AC5: Idempotent Preparation

**Given** the workspace manager is called multiple times for the same agent
**When** CLAUDE.md, .mcp.json, and skill symlinks already exist
**Then** they are regenerated (overwritten) without errors
**And** broken symlinks (pointing to removed skills) are cleaned up
**And** the memory/ and sessions/ directories are never touched (preserving agent state)

### AC6: WorkspaceContext Return Value

**Given** the workspace manager finishes preparation
**When** the caller receives the result
**Then** it gets a `WorkspaceContext` dataclass with:
  - `cwd: Path` — the agent's workspace directory
  - `mcp_config: Path` — path to generated `.mcp.json`
  - `claude_md: Path` — path to generated `CLAUDE.md`
  - `socket_path: str` — the Unix socket path for MCP IPC

## Tasks / Subtasks

- [ ] **Task 1: Create WorkspaceContext dataclass** (AC: #6)
  - [ ] 1.1 In `mc/types.py`, add:
    ```python
    @dataclass
    class WorkspaceContext:
        cwd: Path
        mcp_config: Path
        claude_md: Path
        socket_path: str
    ```

- [ ] **Task 2: Create cc_workspace module** (AC: #1, #2, #3, #4, #5)
  - [ ] 2.1 Create `mc/cc_workspace.py` with class `CCWorkspaceManager`:
    ```python
    class CCWorkspaceManager:
        def __init__(self, workspace_root: Path | None = None):
            self._root = workspace_root or Path.home() / ".nanobot"

        def prepare(
            self, agent_name: str, agent_config: AgentData, task_id: str
        ) -> WorkspaceContext:
            workspace = self._root / "agents" / agent_name
            self._generate_claude_md(workspace, agent_config)
            self._map_skills(workspace, agent_config.skills)
            socket_path = f"/tmp/mc-{agent_name}.sock"
            self._generate_mcp_json(workspace, agent_name, task_id, socket_path)
            return WorkspaceContext(
                cwd=workspace,
                mcp_config=workspace / ".mcp.json",
                claude_md=workspace / "CLAUDE.md",
                socket_path=socket_path,
            )
    ```

- [ ] **Task 3: Implement CLAUDE.md generation** (AC: #1)
  - [ ] 3.1 Create `_generate_claude_md(self, workspace: Path, config: AgentData)`:
    - Build markdown with sections: Identity, MCP Tools Guide, Project Conventions
    - Identity section: agent name, role, prompt from config
    - MCP Tools Guide:
      ```markdown
      ## Available MCP Tools

      You have access to nanobot tools via MCP. Use these instead of built-in equivalents:

      - `mcp__nanobot__ask_user` — Ask the user a question. ALWAYS use this instead of AskUserQuestion.
      - `mcp__nanobot__send_message` — Send a message to the user's chat channel.
      - `mcp__nanobot__delegate_task` — Create a new task for another agent to handle.
      - `mcp__nanobot__ask_agent` — Ask another agent a question synchronously.
      - `mcp__nanobot__report_progress` — Report task progress (visible in dashboard).

      IMPORTANT: The AskUserQuestion tool does NOT work in this environment.
      Always use mcp__nanobot__ask_user instead.
      ```
    - Write to `workspace / "CLAUDE.md"`

- [ ] **Task 4: Implement skills mapping** (AC: #2)
  - [ ] 4.1 Create `_map_skills(self, workspace: Path, skills: list[str])`:
    - Create `workspace / ".claude" / "skills"` directory
    - Clean up existing broken symlinks in skills dir
    - For each skill name, search in order:
      1. `workspace / "skills" / skill_name` (workspace-local)
      2. `self._root / "workspace" / "skills" / skill_name` (global)
      3. Builtin skills in `vendor/nanobot/nanobot/skills/ / skill_name`
    - Create symlink: `workspace / ".claude" / "skills" / skill_name` → found path
    - Log warning if skill not found in any location

- [ ] **Task 5: Implement MCP config generation** (AC: #3)
  - [ ] 5.1 Create `_generate_mcp_json(self, workspace, agent_name, task_id, socket_path)`:
    - Build the JSON structure per AC3
    - Write to `workspace / ".mcp.json"`

- [ ] **Task 6: Tests** (AC: all)
  - [ ] 6.1 Create `tests/mc/test_cc_workspace.py`:
    - Test CLAUDE.md generation contains agent prompt and MCP tools guide
    - Test skills symlink creation with mock skill directories
    - Test .mcp.json structure matches expected format
    - Test idempotent preparation (run twice, no errors)
    - Test broken symlink cleanup
    - Test WorkspaceContext has correct paths
  - [ ] 6.2 Run: `uv run pytest tests/mc/test_cc_workspace.py -v`

## Dev Notes

### Architecture & Design Decisions

**CLAUDE.md is generated, not handwritten**: Each time the workspace is prepared, CLAUDE.md is regenerated from the agent config. This ensures the CC agent always has up-to-date instructions matching its YAML config. The user's customizations go in config.yaml, not CLAUDE.md.

**Symlinks over copies**: Skills are symlinked, not copied. This means changes to skills are immediately visible to CC agents without re-preparation. It also avoids disk waste for large skill directories.

**Socket path in /tmp**: Unix sockets are created in `/tmp` to avoid path length issues (macOS has ~104 char limit). The agent name is used to avoid collisions.

### Code to Reuse

- `vendor/nanobot/nanobot/agent/skills.py` — `SkillsLoader` class, skill discovery logic
- `mc/gateway.py` — `AGENTS_DIR` constant for workspace root
- `mc/yaml_validator.py` — `validate_agent_file()` for loading agent config

### Common Mistakes to Avoid

- Do NOT modify existing files in the workspace (memory/, sessions/, config.yaml)
- Do NOT create circular symlinks
- Socket paths on macOS have a 104-character limit — keep them short
- `.claude/` directory may not exist — create it
- Use `uv run python` not `python3`. Use `uv run pytest` for tests.

### Project Structure Notes

- **NEW**: `mc/cc_workspace.py` — Workspace preparation logic
- **MODIFIED**: `mc/types.py` — Add `WorkspaceContext` dataclass
- **NEW**: `tests/mc/test_cc_workspace.py`

### References

- `vendor/nanobot/nanobot/agent/skills.py` — SkillsLoader class
- `mc/gateway.py` — AGENTS_DIR constant
- `mc/types.py` — AgentData, ClaudeCodeOpts dataclasses (from CC-1)
- Claude Code skills format: https://code.claude.com/docs/en/skills

## Review Follow-ups (AI)

### Review Date: 2026-03-04 | Reviewer: Claude Opus (adversarial)

**Result: CONDITIONAL PASS** -- 2 CRITICAL, 3 HIGH, 3 MEDIUM, 1 LOW findings. Must fix CRITICALs before merge.

#### CRITICAL
- [ ] [AI-Review][CRITICAL] Path traversal via `agent_name` -- no validation that resolved path stays within workspace root. `../../etc/passwd` as agent_name creates dirs outside root. [mc/cc_workspace.py:58]
- [ ] [AI-Review][CRITICAL] Path traversal via `skill_name` -- untrusted skill names used directly in path construction for both search and symlink creation. [mc/cc_workspace.py:126-145]

#### HIGH
- [ ] [AI-Review][HIGH] AC1 partially unmet: "Project conventions (configurable, from a shared template)" section missing from CLAUDE.md generation. [mc/cc_workspace.py:80-107]
- [ ] [AI-Review][HIGH] No test verifying AC5's guarantee that files in memory/ and sessions/ survive re-preparation. [tests/mc/test_cc_workspace.py]
- [ ] [AI-Review][HIGH] Socket path length not validated against macOS 104-char limit despite Dev Notes warning about this exact issue. [mc/cc_workspace.py:66]

#### MEDIUM
- [ ] [AI-Review][MEDIUM] No test coverage for vendor/builtin skills (third search priority); `_VENDOR_SKILLS_DIR` not injectable for testing. [tests/mc/test_cc_workspace.py]
- [ ] [AI-Review][MEDIUM] Unused import `ClaudeCodeOpts` in test file. [tests/mc/test_cc_workspace.py:13]
- [ ] [AI-Review][MEDIUM] `_VENDOR_SKILLS_DIR` duplicates path logic from upstream `BUILTIN_SKILLS_DIR` in vendor/nanobot/nanobot/agent/skills.py:12 -- should reuse canonical source. [mc/cc_workspace.py:21]

#### LOW
- [ ] [AI-Review][LOW] `test_claude_md_no_soul_section_when_absent` does not assert absence of "## Soul" header -- only checks file exists and contains agent name. [tests/mc/test_cc_workspace.py:129-138]

## Dev Agent Record

### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
