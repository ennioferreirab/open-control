#  Open Mission Control

## Vendor Boundary

`vendor/nanobot/` is a git subtree of [HKUDS/nanobot](https://github.com/HKUDS/nanobot). **Do NOT edit files inside `vendor/nanobot/` without explicit user permission.** We absorb upstream evolution over time — the closer we stay to the original project, the easier syncs are. This directory must be excluded from project-wide code conventions and linting rules.

`vendor/claude-code/` is our own code and **must follow** the same code conventions as the rest of the project.

## Language

All code (variables, functions, classes, comments, commit messages, docstrings) must be written in English.

## Stack Lifecycle

Use `make start` / `make down` to manage the stack. Use `make validate` for pre-commit checks (no Convex needed). Use `make takeover` from a worktree to steal the Convex instance. See [`building_the_project.md`](agent_docs/building_the_project.md) for full details.

**Convex singleton:** only one local backend can run (port 3210). `make start` kills any existing instance before starting. Never run `npx convex dev --local` directly.

## Development Method — BMAD

All features follow the **BMAD method** (v6.0.1). Use `/bmad-help` to see next steps.

### Choosing Your Track

| Track | When to use | Entry point |
|-------|-------------|-------------|
| **Full BMAD** | New product area, complex multi-system feature, >5 stories anticipated, requires PRD + Architecture + UX | Phase 1 or 2 |
| **Quick Flow** | Bug fixes, small features, clear scope (1–15 stories), brownfield changes that "fit on one page of notes" | `/bmad-bmm-quick-spec` → `/bmad-bmm-quick-dev` |

**Rule of thumb:** if you'd feel uncomfortable skipping a PRD and architecture doc, use Full BMAD.

### Full BMAD Phases


**Implementation** (per stories cycle) — Create a plan -> /@_bmad/bmm/workflows/4-implementation/create-story -> Create a wave plan → -> Delegate to sonnet (if you are Claude) or GPT-5.4 Medium (if you are Codex) -> devs execute -> /@_bmad/bmm/workflows/4-implementation/dev-story → /@_bmad/bmm/workflows/4-implementation/code-review → Run test suite -> Test the feature using code simulating real interaction with other services using backend functions -> Make takeover any 300x port -> Share the PORT to human test the feature

### Workflow Execution Rules

- **Step-file discipline.** BMAD workflows use micro-file architecture — load one step at a time, follow it exactly, never skip or load ahead. Update `stepsCompleted` in output frontmatter after each step.
- **Role boundaries.** Each agent has a defined scope. Do NOT let dev agents modify architecture decisions or skip validation gates. If an architecture-requirement conflict is discovered during implementation, **halt and escalate** — do not improvise.
- **Validation gates are mandatory.** PRD validation (13 steps), Implementation Readiness check, and Code Review (must find 3–10 issues) are non-optional quality gates. For validation workflows, use a different LLM if available.
- **Stories must be self-contained.** A fresh agent must be able to implement a story without reading prior conversation history. All context (file paths, ACs, API specs) must be inlined in the story file.

### Artifacts

- **Planning:** `_bmad-output/planning-artifacts/` — PRD, architecture, epics, UX design
- **Implementation:** `_bmad-output/implementation-artifacts/` — story files, `sprint-status.yaml`
- **Project context:** `_bmad-output/project-context.md` — LLM-optimized rules loaded by all implementation workflows (generate via `/bmad-bmm-generate-project-context`)
- **BMAD engine:** `_bmad/` — **do not edit**
- **Legacy artifacts:** `bmad_history/` — read-only reference from prior cycles

## Worktree Lifecycle

All new features must be implemented in isolated git worktrees. After the branch is merged back into main, the worktree **must be deleted** immediately. Do not leave stale worktrees around.

```bash
# After merge
git worktree remove .claude/worktrees/<name>
# Or if already deleted on disk
git worktree prune
```

## Testing

[`running_tests.md`](agent_docs/running_tests.md) is **mandatory reading** before writing or modifying any test. It defines what to test, what to skip, anti-patterns to avoid, and the quality checklist. **Follow it strictly** — do not write tests that fall into the "Never Test" or "Anti-Patterns (banned)" categories.

**Subagent efficiency:** when dispatching subagents to write tests, provide all context upfront in the prompt — target file, example test file to follow, specific scenarios to test, and output path. Do not let subagents explore the codebase to discover patterns on their own.

## Error Handling

Never add silent fallbacks that mask failures. If a system call (LLM, API, etc.) fails, **fail explicitly** with a clear error. Only add fallback mechanisms if explicitly requested. Silent degradation is an anti-pattern.

## Agent Docs — Contracts

These documents are **binding contracts**. Before touching any layer of the system, you **MUST read** the relevant docs from the table below. They define how services communicate, how data is shaped, and how code is written. Do not guess — read the contract first.

`agent_docs/` is the **canonical index** of project documentation for agents. **Only permanent reference docs belong here.** Do NOT add ephemeral files (audit reports, one-off analyses, migration checklists, plan artifacts) to this directory or to the table below.

### Structural contracts (require human approval to change)

The following docs define the project's structural foundations. **Any modification to these files is a structural change.** You MUST use `AskUser` to get explicit human approval before editing them. Do NOT modify them silently, even as part of a larger refactor.

**Keep contracts in sync.** If a code change alters behavior governed by a structural contract (new table, renamed field, changed protocol, new status value, etc.), you MUST update the corresponding doc in the same PR/commit. A contract that disagrees with the code is a bug.

| File | When to read | Description |
|------|-------------|-------------|
| [`service_architecture.md`](agent_docs/service_architecture.md) | Adding/modifying workers, services, processes, or changing how the runtime starts and stops | Defines every runtime service, process lifecycle, IPC protocols, env vars, and the task execution state machine |
| [`service_communication_patterns.md`](agent_docs/service_communication_patterns.md) | Changing how services talk to each other — IPC messages, Convex bridge calls, polling, webhooks | Protocol specs for IPC sockets, Convex bridge, MCP bridge, dashboard↔backend comm, inter-agent messaging, hooks |
| [`database_schema.md`](agent_docs/database_schema.md) | Adding/modifying Convex tables, fields, indexes, or writing queries/mutations | All Convex tables with field types, indexes, relationships, and valid enum values |
| [`cross_service_naming.md`](agent_docs/code_conventions/cross_service_naming.md) | Using status values, entity types, or field names that cross Python↔TypeScript boundary | The single source of truth for key conversion rules, status enums, and entity type names shared across services |

### Reference docs (read before working in scope)

| File | When to read | Description |
|------|-------------|-------------|
| [`building_the_project.md`](agent_docs/building_the_project.md) | Setting up the project, running the stack, debugging startup, or understanding the port layout | Prerequisites, `make` commands, startup sequence, port assignments, baseline health checks |
| [`code_conventions/python.md`](agent_docs/code_conventions/python.md) | Writing or modifying any Python code in `mc/` or `tests/mc/` | Ruff config, naming conventions, type hint rules, import ordering, docstring style |
| [`code_conventions/convex.md`](agent_docs/code_conventions/convex.md) | Writing or modifying Convex functions in `dashboard/convex/` | Function patterns (queries/mutations/actions), lib module structure, Convex-specific testing patterns |
| [`code_conventions/typescript.md`](agent_docs/code_conventions/typescript.md) | Writing or modifying React/Next.js code in `dashboard/` (excl. `convex/`) | Component structure, feature module layout, hook patterns, import conventions |
| [`running_tests.md`](agent_docs/running_tests.md) | Before writing, modifying, or running any test — **mandatory** | Decision tree for what to test vs skip, test commands, anti-patterns (banned), quality checklist |
