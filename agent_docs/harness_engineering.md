# Harness Engineering

> **Scope:** Platform internals — how the harness manages agents, skills, memory, threads, workspaces, and squads at runtime. Read this before modifying any of these subsystems.
>
> Related docs: [`service_architecture.md`](service_architecture.md) (runtime processes), [`service_communication_patterns.md`](service_communication_patterns.md) (IPC/bridge), [`database_schema.md`](database_schema.md) (Convex tables).

---

## Agents

### Configuration

Each agent lives in `~/.nanobot/agents/{agent_name}/` with a mandatory `config.yaml`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | `string` | yes | Slug format: `^[a-z0-9]+(-[a-z0-9]+)*$` |
| `display_name` | `string` | no | Auto-generated from `name` if omitted |
| `role` | `string` | yes | Role/job description |
| `prompt` | `string` | yes | System prompt (min 1 char) |
| `model` | `string` | no | LLM model ID or `tier:standard-low` etc. |
| `skills` | `list[str]` | no | Skill names available to this agent (default `[]`) |
| `soul` | `string` | no | Path to or content of SOUL.md personality override |
| `backend` | `string` | no | `"nanobot"` or `"claude-code"` (default `"nanobot"`) |
| `is_system` | `bool` | no | System agents cannot be deleted |
| `interactive_provider` | `string` | no | `"claude-code"`, `"codex"`, or `"mc"` |
| `claude_code` | `dict` | no | CC-specific: `permission_mode`, `max_budget_usd`, `max_turns` |

**SOUL.md** is a personality override loaded last in the agent's CLAUDE.md so it takes precedence over all other context.

### Permission Model

All Claude Code agents default to `bypassPermissions` mode. This grants full
file and tool access without interactive approval prompts.

**Why:** MC agents run autonomously in non-interactive backend sessions. There
is no human to approve permission requests, so restrictive modes cause agents
to block indefinitely or flail with workarounds.

**Future concern:** As the platform moves toward multi-tenant or production
use, revisit this to implement:
- Per-agent permission scoping (allowlists of directories and tools)
- Skill-declared permission requirements in SKILL.md frontmatter
- Sandbox isolation per task execution

### Sync: YAML ↔ Convex

`AgentSyncService.sync_agent_registry()` in `mc/contexts/agents/sync.py`:

1. Validates every `config.yaml` against the `AgentConfig` pydantic model
2. Convex is authoritative — if Convex has a `skills` list, it overrides YAML
3. Write-back: dashboard changes are synced back to local YAML so both stay in sync
4. Model resolution: blank model → resolved default via tier system
5. Deactivation: agents whose YAML is removed get status `"idle"` in Convex

### System Agents

| Name | Purpose |
|------|---------|
| `orchestrator-agent` | Orchestrator — routes tasks, manages workflows |
| `nanobot` | Default general-purpose agent |
| `low-agent` | System low-privilege agent |
| `human` | Placeholder for human participants (HITL) |

---

## Skills

### Definition Format

A skill is a directory containing a `SKILL.md` with YAML frontmatter:

```
skill-name/
  SKILL.md              ← required (frontmatter + body)
  scripts/              ← optional deterministic operations
  references/           ← optional domain knowledge
  assets/               ← optional output templates
  agents/openai.yaml    ← optional, enables Codex provider support
```

**SKILL.md frontmatter:**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | `string` | yes | Skill slug |
| `description` | `string` | yes | Must include trigger scenarios, not just what the skill does |
| `always` | `bool` | no | If `true`, auto-loaded into every agent session |
| `metadata` | `string` | no | JSON string with provider-specific config |
| `license` | `string` | no | License identifier |

Body max: ~500 lines. Use imperative form ("Extract the data", not "This skill extracts").

### Skill Sources (Priority Order)

| Priority | Location | Notes |
|----------|----------|-------|
| 1 | `{agent_workspace}/skills/{name}/` | Agent-specific overrides |
| 2 | `~/.nanobot/workspace/skills/{name}/` | Global workspace (user-created + distributed builtins) |
| 3 | `vendor/nanobot/nanobot/skills/{name}/` | Upstream vendor builtins |

Project-specific builtins in `mc/skills/` are distributed to the global workspace at startup.

### Lifecycle: From Disk to Agent

```text
┌──────────────────────────────────────────────────────────┐
│  1. DISTRIBUTION  (gateway startup)                      │
│  _distribute_builtin_skills() in agent_bootstrap.py      │
│  Copies from mc/skills/ and vendor/nanobot/skills/       │
│  → ~/.nanobot/workspace/skills/                          │
│  (preserves existing — never overwrites user edits)      │
└──────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────┐
│  2. SYNC TO CONVEX  (gateway startup)                    │
│  sync_skills() in agent_bootstrap.py                     │
│  - SkillsLoader discovers all skills from 3 sources      │
│  - Detects supported providers (claude-code, codex,      │
│    nanobot) — presence of agents/openai.yaml → codex     │
│  - Checks requirements (bins via which(), env vars)      │
│  - Upserts to Convex via skills:upsertByName             │
│  - Deactivates skills no longer on disk                  │
└──────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────┐
│  3. WORKSPACE MAPPING  (per agent session)               │
│  _map_skills() in workspace.py                           │
│  For each skill in agent config:                         │
│    a. Find source dir (3 locations, first match wins)    │
│    b. Check availability via SkillsLoader                │
│    c. Copy to .claude/skills/{name}/ (NOT symlinks —     │
│       CC's Glob tool doesn't traverse symlinks)          │
│    d. Register as CC slash command in                    │
│       .claude/commands/{name}.md                         │
│  + Build skills summary in CLAUDE.md section 9           │
│    with path: .claude/skills/<name>/SKILL.md             │
└──────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────┐
│  4. AGENT RUNTIME                                        │
│  CC backend:  /skill-name (Skill tool) or Read SKILL.md  │
│  Nanobot:     SkillsLoader.build_skills_summary()        │
│  Codex:       agents/openai.yaml + content from Convex   │
└──────────────────────────────────────────────────────────┘
```

### CC Backend: Dual Registration

Skills are made available to Claude Code sessions in **two ways**:

1. **File-based** — skill directory copied to `.claude/skills/{name}/`. The CLAUDE.md says "read the SKILL.md file". Works for any agent that can read files.

2. **CC slash command** — a `.claude/commands/{name}.md` is generated with the skill's frontmatter and a pointer to the full SKILL.md. This lets CC's `Skill` tool invoke `/skill-name`.

> **Why dual registration?** CC's `Skill` tool only knows about commands registered in `.claude/commands/`. If a skill is only in `.claude/skills/`, the `Skill` tool returns "Unknown skill". The CC system-reminder (`superpowers:using-superpowers`) instructs agents to always use the `Skill` tool, so without the command registration, agents fail to find workspace skills.
>
> **Incident:** The `post-creator` agent tried `Skill("generate-image")` → got "Unknown skill" → tried `ToolSearch` → found nothing → gave up. Two root causes:
>
> 1. **Missing command registration** — `generate-image` was only in `.claude/skills/` without a `.claude/commands/` entry. Fixed by adding `_register_skill_commands()` in `workspace.py`.
>
> 2. **Provider-CLI strategy did not prepare workspaces** — CC agents routed through `ProviderCliRunnerStrategy` (the default since Story 28.7) launched with `cwd="."` (project root) instead of the agent workspace. The strategy never called `CCWorkspaceManager.prepare()`, so `.claude/skills/`, `.claude/commands/`, and `CLAUDE.md` were never created. Fixed by adding `_prepare_workspace()` in `provider_cli.py`.

### Availability Checking

`SkillsLoader.is_skill_available()` validates requirements before mapping:

```text
requires:
  bins: ["gh", "jq"]        ← checked via shutil.which()
  env: ["GITHUB_TOKEN"]     ← checked via os.environ.get()
```

Unavailable skills are skipped with a warning log. The `requires` field is stored in Convex and shown in the dashboard.

---

## Workspaces

### Directory Structure

```text
~/.nanobot/
  workspace/                          ← global shared workspace
    skills/                           ← distributed skills (all agents)
  agents/{agent_name}/                ← per-agent workspace
    config.yaml                       ← agent configuration
    SOUL.md                           ← optional personality
    memory/                           ← agent memory (global scope)
      MEMORY.md                       ← long-term persistent facts
      HISTORY.md                      ← chronological event log
      memory-index.sqlite             ← hybrid BM25+vector search index
    sessions/                         ← session-scoped files
    skills/                           ← agent-specific skill overrides
    .claude/
      skills/{name}/                  ← mapped skill copies (CC runtime)
      commands/{name}.md              ← CC slash commands for skills
    CLAUDE.md                         ← generated agent identity + context
    .mcp.json                         ← MCP server config
  boards/{board_name}/                ← board-scoped isolation
    {agent_name}/
      memory/                         ← isolated memory per board
    .artifacts/                       ← board artifacts
  tasks/{task_id}/                    ← task execution workspace
    attachments/                      ← task input files
    output/                           ← task output files
    journal/                          ← thread journal (local reconciliation)
```

### Board-Scoped vs Global

| Scope | Memory path | When used |
|-------|-------------|-----------|
| Global | `~/.nanobot/agents/{name}/memory/` | Default — agent accumulates knowledge across all tasks |
| Board-scoped | `~/.nanobot/boards/{board}/{name}/memory/` | When task belongs to a board — isolated memory per board |

Resolution: `resolve_board_workspace()` in `mc/infrastructure/boards.py`.

### Workspace Preparation (CC Backend)

`CCWorkspaceManager.prepare()` in `vendor/claude-code/claude_code/workspace.py`:

1. Validate agent name (path traversal protection)
2. Resolve board workspace if `board_name` provided
3. Create directory structure (`memory/`, `sessions/`)
4. Map skills → `.claude/skills/` + `.claude/commands/`
5. Generate `CLAUDE.md` with sections:
   - Agent identity (name, role, prompt)
   - Global orientation text
   - Memory context (MEMORY.md + recent HISTORY.md)
   - Relevant history (hybrid search against task prompt)
   - MCP tools guide
   - Always-on skills
   - Skills summary with paths
   - Soul (personality override — last, so it wins)
6. Generate `.mcp.json` for MCP bridge subprocess
7. Return `WorkspaceContext` (cwd, socket path, mcp config)

---

## Memory

### Storage

Each agent has a memory directory with three key files:

| File | Purpose | Format |
|------|---------|--------|
| `MEMORY.md` | Long-term persistent facts and knowledge | Markdown — structured facts, decisions, preferences |
| `HISTORY.md` | Chronological event log | `[YYYY-MM-DD HH:MM] event summary` entries |
| `memory-index.sqlite` | Hybrid search index | SQLite with BM25 FTS + optional vector embeddings |

Locks: `.memory.lock` (concurrent access), `.consolidation.lock` (consolidation operations).

### MCP Tools

| Tool | Purpose | Params |
|------|---------|--------|
| `search_memory` | Hybrid BM25+vector search over memory | `query` (string), `top_k` (1–50, default 5) |
| `save_memory` | Write history entry + update MEMORY.md | `history_entry` (2–5 sentences with timestamp), `memory_update` (full MEMORY.md) |

### Consolidation

Triggered automatically when `HISTORY.md` exceeds **160K chars** (~40K tokens).

```text
HISTORY.md > 160K chars
        │
        ▼
consolidate_history_and_memory()
        │
        ├─ Archive old history → HISTORY_ARCHIVE.md
        ├─ LLM extracts key facts → update MEMORY.md
        └─ Target MEMORY.md size: ~12K chars (~3K tokens)
```

Task-level consolidation (`consolidate_task_output()`) runs after task execution — extracts key facts from the task result into both MEMORY.md and HISTORY.md.

### Hybrid Search Index

- **Schema:** `files`, `chunks`, `chunks_fts` (BM25), `chunks_vec` (optional vector)
- **Chunking:** 500 chars per chunk, 50-char overlap
- **Embedding:** configurable via `NANOBOT_MEMORY_EMBEDDING_MODEL` env var or `~/.nanobot/memory_settings.json`
- **Settings:** `history_context_days` (default 5), `memory_context_max_chars` (default 40K)

### Context Loading

`get_memory_context()` returns the combined context injected into CLAUDE.md:
- Long-term facts from MEMORY.md
- Recent history from HISTORY.md (last N days, truncated to max chars)
- Relevant history via hybrid search against the current task prompt

---

## Threads

### Model

Threads are the message stream for a task. All messages are stored in the Convex `messages` table.

| Field | Type | Notes |
|-------|------|-------|
| `task_id` | `Id<"tasks">` | Parent task |
| `author_name` | `string` | Agent slug or `"user"` |
| `author_type` | `"agent" \| "user" \| "system"` | Message origin |
| `content` | `string` | Message body |
| `type` | `string` | `"step_completion"`, `"user_message"`, `"system_error"`, `"orchestrator_agent_chat"` |
| `step_id` | `Id<"steps">` | Optional — step that generated this message |
| `artifacts` | `array` | Modified/created files with diffs |
| `timestamp` | `number` | Epoch milliseconds |

### Thread Context Building

`ThreadContextBuilder.build()` in `mc/application/execution/thread_context.py`:

- Includes last **20 messages** by default
- Predecessor step completions are always included (even if outside the 20-message window)
- Artifacts formatted with diffs (max 2000 chars per diff)
- Step-aware mode: always includes predecessor completion messages

### Thread Journal (Local Reconciliation)

The thread journal reconciles Convex messages into a local markdown journal for rolling context:

| Component | Location | Purpose |
|-----------|----------|---------|
| `ThreadJournalService` | `mc/application/execution/thread_journal_service.py` | Sync Convex → local journal |
| `ThreadJournalStore` | `mc/infrastructure/thread_journal_store.py` | Markdown journal with compaction |
| Journal storage | `~/.nanobot/tasks/{task_id}/journal/` | Local journal files |

**Compaction:** when the journal exceeds a threshold, old messages are summarized via LLM into a compacted summary, keeping only recent messages in full.

---

## Squads

### Configuration

Squads group agents into collaborative teams with shared workflows.

| Convex Table | Purpose |
|-------------|---------|
| `squadSpecs` | Squad definition — agents, workflows, review policy, metadata |
| `boardSquadBindings` | Links boards to squad specs |

Squad spec fields: `squad_name`, `published_by_spec_id`, `squad_metadata`, `agents` array.

### Routing Modes

| Mode | Behavior |
|------|----------|
| `"orchestrator_agent"` | Orchestrator agent decides task assignment and orchestration |
| `"workflow"` | Follows spec-compiled workflow steps — deterministic routing |
| `"human"` | Human-driven (human-in-the-loop) |

### Inter-Agent Communication

| Mechanism | Tool | Description |
|-----------|------|-------------|
| Ask agent | `ask_agent` (MCP) | Query a specific agent from another agent's session |
| Ask user | `ask_user` (MCP) | Escalate to human for input |
| Send message | `send_message` (MCP) | Post a message to the task thread |

Squad graph publication: `publish_squad_graph(graph)` in `mc/bridge/repositories/specs.py`. Graph structure: `{squad: {...}, agents: [...], workflows: [...], reviewPolicy: {...}}`.

### Creation Skills

| Skill | Trigger | API dependencies | Notes |
|-------|---------|-----------------|-------|
| `/create-squad-mc` | User wants a new multi-agent team | `GET /api/specs/squad/context`, `POST /api/specs/squad` | 6 phases: Intent → Capabilities → Skill Resolution → Agent Design → Workflow Design → Publish. Phase 4 (Agent Design) enforces a mandatory Reuse Assessment — existing agents must be evaluated before creating new ones (60%+ fit → reuse, 3+ new agents → explicit user confirmation required). |
| `/create-workflow-mc` | User wants to add a workflow to an existing squad | `GET /api/specs/workflow/context`, `POST /api/specs/workflow` | 4 phases: Intent & Squad Selection → Agent Roster Review → Step Design → Review & Publish. Can invoke `/create-squad-mc` inline when the user needs a new squad before designing the workflow. Publishes via `workflowSpecs:publishStandalone`. |

---

## Key Files Reference

| Subsystem | File | Key Functions |
|-----------|------|---------------|
| Agent config validation | `mc/infrastructure/agents/yaml_validator.py` | `validate_agent_file()`, `AgentConfig` |
| Agent sync | `mc/contexts/agents/sync.py` | `AgentSyncService.sync_agent_registry()` |
| Agent bootstrap | `mc/infrastructure/agent_bootstrap.py` | `sync_skills()`, `_distribute_builtin_skills()` |
| Workspace manager | `vendor/claude-code/claude_code/workspace.py` | `CCWorkspaceManager.prepare()`, `_map_skills()` |
| Memory store | `mc/memory/store.py` | `HybridMemoryStore.search()`, `append_history()` |
| Memory consolidation | `mc/memory/consolidation.py` | `consolidate_task_output()`, `consolidate_history_and_memory()` |
| Memory index | `mc/memory/index.py` | `MemoryIndex.search()`, `sync_file()` |
| Thread context | `mc/application/execution/thread_context.py` | `ThreadContextBuilder.build()` |
| Thread journal | `mc/application/execution/thread_journal_service.py` | `ThreadJournalService.sync_task_thread()` |
| Board workspace | `mc/infrastructure/boards.py` | `resolve_board_workspace()` |
| Agent types | `mc/types.py` | `AgentData` dataclass |
| Convex schema | `dashboard/convex/schema.ts` | `messages`, `agents`, `skills`, `squadSpecs` tables |
| Skills API | `dashboard/app/api/specs/skills/` | `GET /api/specs/skills` — list all skills (`?available=true` filter); `POST` — register/update skill |
| Skills file API | `dashboard/app/api/skills/[skillName]/files/` | REST endpoints for skill file R/W |
