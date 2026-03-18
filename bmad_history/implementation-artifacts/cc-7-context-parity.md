# CC-7: Context Parity — CC Backend Must Match Nanobot Agent Context

## Problem

The CC backend (`CCWorkspaceManager._generate_claude_md()`) generates a minimal CLAUDE.md with only agent identity, system prompt, project conventions, MCP tools guide, and soul. The nanobot agent's `ContextBuilder.build_system_prompt()` assembles a rich context with bootstrap files, memory, skills summary, and runtime metadata. This means CC agents are contextually blind compared to nanobot agents running the same tasks.

## Acceptance Criteria

### AC1: Bootstrap Files Injected into CLAUDE.md

`_generate_claude_md()` must read and inject the same bootstrap files the nanobot ContextBuilder loads:

- **SOUL.md** — already handled via `config.soul` (no change needed)
- **AGENTS.md** — agent roster, scheduled reminders, heartbeat instructions
- **USER.md** — user profile, preferences, communication style
- **TOOLS.md** — tool usage notes and safety limits
- **IDENTITY.md** — extended agent identity (if present)

Search order for each file (same as ContextBuilder):
1. `{workspace}/{filename}` (agent-specific)
2. `{root}/workspace/{filename}` (global, `~/.nanobot/workspace/`)

If a file doesn't exist at either location, skip it silently.

### AC2: Memory Context Injected into CLAUDE.md

Read `{workspace}/memory/MEMORY.md` (or `{memory_workspace}/MEMORY.md` if board-scoped) and inject as a `## Memory` section in CLAUDE.md.

The `memory/` directory is already created by `prepare()` (line 90) but its content is never read. This must change.

### AC3: Skills Summary Generated in CLAUDE.md

Generate an XML skills summary equivalent to `SkillsLoader.build_skills_summary()` and inject it into CLAUDE.md with instructions on how to read skill files.

Two approaches (choose one):
- **Option A**: Import and use `SkillsLoader` directly from `nanobot.agent.skills`
- **Option B**: Generate a simpler Markdown-based summary by iterating the symlinked skills in `.claude/skills/`

Option A is preferred for consistency. The summary must include:
- Skill name
- Description (from SKILL.md frontmatter)
- Location path
- Availability status

Add instruction text: "To use a skill, read its SKILL.md file. Skills with available='false' need dependencies installed first."

### AC4: Runtime Context Metadata

Include runtime metadata in CLAUDE.md (or in the prompt passed to `execute_task`):
- Current timestamp + timezone
- Platform (macOS/Linux + architecture)
- Python version

### AC5: Agent Workspace Guidance

Include workspace path information matching the nanobot identity section:
```
## Workspace
Your workspace is at: {workspace_path}
- Long-term memory: {workspace_path}/memory/MEMORY.md
- Custom skills: .claude/skills/{skill-name}/SKILL.md
```

### AC6: Tests

- Test that bootstrap files are read from workspace and injected into CLAUDE.md
- Test fallback to global workspace when agent-specific file is missing
- Test that MEMORY.md content appears in generated CLAUDE.md
- Test that skills summary is generated for mapped skills
- Test that runtime metadata is present

## Technical Design

### Changes to `mc/cc_workspace.py`

#### `_generate_claude_md()` — Expand to include full context

Current (lines 117-147):
```python
def _generate_claude_md(self, workspace: Path, config: AgentData) -> None:
    lines = []
    lines.append("# Agent Identity\n")
    # ... identity, prompt, conventions, MCP guide, soul
```

New structure:
```python
def _generate_claude_md(self, workspace: Path, config: AgentData) -> None:
    lines = []

    # 1. Agent identity + workspace guidance (AC5)
    lines.append("# Agent Identity\n")
    lines.append(f"**Name**: {config.name}")
    lines.append(f"**Role**: {config.role}")
    if config.display_name:
        lines.append(f"**Display name**: {config.display_name}")
    lines.append("")
    lines.append(self._workspace_guidance(workspace))

    # 2. Runtime context (AC4)
    lines.append(self._runtime_context())

    # 3. System prompt (existing)
    if config.prompt:
        lines.append("## System Prompt\n")
        lines.append(config.prompt.strip())
        lines.append("")

    # 4. Bootstrap files (AC1)
    bootstrap = self._load_bootstrap_files(workspace)
    if bootstrap:
        lines.append(bootstrap)

    # 5. Memory context (AC2)
    memory = self._load_memory(workspace)
    if memory:
        lines.append("## Memory\n")
        lines.append(memory)
        lines.append("")

    # 6. Project conventions (existing)
    lines.append(_DEFAULT_CONVENTIONS)

    # 7. MCP tools guide (existing)
    lines.append(_MCP_TOOLS_GUIDE)

    # 8. Skills summary (AC3) — after _map_skills() has created symlinks
    skills_summary = self._build_skills_summary(workspace, config.skills)
    if skills_summary:
        lines.append("## Skills\n")
        lines.append("To use a skill, read its SKILL.md file. Skills with available=\"false\" need dependencies installed first.\n")
        lines.append(skills_summary)
        lines.append("")

    # 9. Soul (existing, keep last for personality override)
    if config.soul:
        lines.append("## Soul\n")
        lines.append(config.soul.strip())
        lines.append("")

    content = "\n".join(lines)
    (workspace / "CLAUDE.md").write_text(content, encoding="utf-8")
```

#### New private methods

```python
_BOOTSTRAP_FILES = ["AGENTS.md", "USER.md", "TOOLS.md", "IDENTITY.md"]
# SOUL.md excluded — already handled via config.soul

def _load_bootstrap_files(self, workspace: Path) -> str:
    """Load bootstrap .md files from workspace (agent-specific) or global."""
    parts = []
    for filename in self._BOOTSTRAP_FILES:
        content = self._read_file_with_fallback(workspace, filename)
        if content:
            parts.append(f"## {filename}\n\n{content}")
    return "\n\n".join(parts) if parts else ""

def _read_file_with_fallback(self, workspace: Path, filename: str) -> str | None:
    """Read file from workspace, falling back to global workspace."""
    agent_file = workspace / filename
    if agent_file.exists():
        return agent_file.read_text(encoding="utf-8").strip()
    global_file = self._root / "workspace" / filename
    if global_file.exists():
        return global_file.read_text(encoding="utf-8").strip()
    return None

def _load_memory(self, workspace: Path) -> str | None:
    """Read MEMORY.md from workspace/memory/."""
    memory_file = workspace / "memory" / "MEMORY.md"
    if memory_file.exists():
        content = memory_file.read_text(encoding="utf-8").strip()
        return content if content else None
    return None

def _runtime_context(self) -> str:
    """Build runtime metadata section."""
    import platform
    from datetime import datetime
    import time
    system = platform.system()
    runtime = f"{'macOS' if system == 'Darwin' else system} {platform.machine()}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
    tz = time.strftime("%Z") or "UTC"
    return f"## Runtime\n\n{runtime}, Python {platform.python_version()}\nCurrent Time: {now} ({tz})\n"

def _workspace_guidance(self, workspace: Path) -> str:
    """Build workspace path guidance section."""
    ws = str(workspace.expanduser().resolve())
    return f"""## Workspace

Your workspace is at: {ws}
- Long-term memory: {ws}/memory/MEMORY.md
- Custom skills: .claude/skills/{{skill-name}}/SKILL.md
"""

def _build_skills_summary(self, workspace: Path, skill_names: list[str]) -> str:
    """Build skills summary from mapped skill symlinks."""
    try:
        from nanobot.agent.skills import SkillsLoader
        loader = SkillsLoader(workspace, global_skills_dir=self._root / "workspace" / "skills")
        return loader.build_skills_summary(allowed_names=skill_names)
    except ImportError:
        # Fallback: simple listing from symlinks
        skills_dir = workspace / ".claude" / "skills"
        if not skills_dir.exists():
            return ""
        entries = []
        for entry in sorted(skills_dir.iterdir()):
            if entry.is_dir() or entry.is_symlink():
                skill_md = entry / "SKILL.md"
                location = str(skill_md) if skill_md.exists() else str(entry)
                entries.append(f"- **{entry.name}**: {location}")
        return "\n".join(entries) if entries else ""
```

#### Call order fix in `prepare()`

Currently `_generate_claude_md()` is called BEFORE `_map_skills()` (line 93-94). For AC3 (skills summary), skills must be mapped first so the summary can reference them. Swap the order:

```python
# In prepare():
self._map_skills(workspace, agent_config.skills)          # First: create symlinks
self._generate_claude_md(workspace, agent_config)          # Then: generate CLAUDE.md with skills summary
```

### Changes to `mc/cc_workspace.py` — `prepare()` signature

Add optional `memory_workspace` parameter for board-scoped memory:

```python
def prepare(self, agent_name: str, agent_config: AgentData, task_id: str,
            memory_workspace: Path | None = None) -> WorkspaceContext:
```

When `memory_workspace` is provided, `_load_memory()` should check it instead of `workspace/memory/`.

### Test file: `tests/mc/test_cc_workspace_context.py` (new)

Focused tests for the new context parity features. Existing `tests/mc/test_cc_workspace.py` tests remain untouched.

## Files Changed

| File | Change |
|------|--------|
| `mc/cc_workspace.py` | Expand `_generate_claude_md()`, add 5 new private methods, swap call order in `prepare()` |
| `tests/mc/test_cc_workspace_context.py` | New test file for AC1-AC6 |

## Dependencies

- None. This story can be implemented independently.
- Should be completed BEFORE CC-8 (vendor extraction) so the enriched version is what gets extracted.

## Out of Scope

- Memory consolidation (post-task MEMORY.md update) — separate story
- Global orientation injection — separate story (requires bridge/executor integration)
- Thread context injection — already handled by executor/step_dispatcher prompt building
- HEARTBEAT.md — not relevant for CC task execution (heartbeat is a polling service)
