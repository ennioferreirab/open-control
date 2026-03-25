# Open Control

## WHAT — Project & Structure

An AI agent orchestration platform. Python backend (`mc/`) manages agent lifecycles, task execution, and inter-agent communication. TypeScript dashboard (`dashboard/`) provides the UI via Next.js + Convex (local backend, port 3210).

```
mc/                  Python backend — runtime, workers, orchestrator, bridge to Convex
  runtime/           Gateway, orchestrator, workers (inbox, execution)
  contexts/          Domain logic — conversation, execution, routing, planning, agents
  bridge/            Python↔Convex communication layer (HTTP client, key conversion, repos)
  cli/               CLI entry point (`uv run open-control mc start`; `nanobot` alias also works)
dashboard/           Next.js app + Convex backend
  convex/            Convex functions (queries, mutations, actions) and schema
  convex/lib/        Pure logic extracted from Convex functions — testable units
  features/          Feature modules (tasks, thread, agents) with components/hooks
  hooks/             Shared React hooks
  components/        Shared UI components (shadcn/ui)
shared/              Cross-language contracts (workflow spec JSON)
tests/mc/            Python test suite (pytest)
vendor/nanobot/      Git subtree — upstream HKUDS/nanobot. DO NOT EDIT without permission
vendor/claude-code/  Our code — follows project conventions
agent_docs/          Binding contracts for agents — see "Agent Docs" section below
_bmad/               BMAD engine — do not edit
_bmad-output/        BMAD artifacts (planning, implementation, project context)
```

**Tech stack:** Python 3.12 (uv), TypeScript (Next.js 15, React 19), Convex (local backend), shadcn/ui, Tailwind CSS, Vitest, Pytest, Playwright (e2e).

## WHY — What Each Layer Does

- **`mc/runtime/`** — Starts the process tree: gateway receives messages, orchestrator routes tasks through a state machine, workers execute steps via LLM providers
- **`mc/bridge/`** — The only way Python talks to Convex. Handles key conversion (snake_case↔camelCase), repositories for each Convex table, retry/idempotency
- **`mc/contexts/`** — Domain boundaries: conversation handling, execution strategies, agent routing, planning. Each context owns its logic and exposes a service
- **`dashboard/convex/`** — Source of truth for all persistent state. Schema defines tasks, steps, messages, agents, threads, boards. `lib/` modules hold pure logic extracted for testability
- **`dashboard/features/`** — UI organized by domain: tasks (kanban, detail sheet), thread (messages, input), agents (management)
- **`shared/workflow/`** — `workflow_spec.json` defines the contract between Python and TypeScript for task/step state machines

## HOW — Working on the Project

### Language

All code, comments, commit messages, and docstrings in **English**.

### Commands

| Action | Command |
|--------|---------|
| Start stack | `make start` |
| Start detached | `make up` |
| Stop stack | `make down` |
| Restart (Python changes) | `docker compose restart mc` |
| Pre-commit validation | `make check` |
| Isolated test instance | `make test-up PORT=3100` |
| Stop test instance | `make test-down` |
| Python tests | `uv run pytest` |
| TypeScript tests | `cd dashboard && npm run test` |
| Single TS test file | `cd dashboard && npx vitest run path/to/file.test.ts` |
| Lint + typecheck | `make lint && make typecheck` |

The stack runs via Docker Compose. Source code is bind-mounted for hot reload (Next.js and Convex auto-reload; Python requires `docker compose restart mc`). Self-hosted Convex inside the container — no port conflicts, no singleton issues.

**Global solutions rule:** Every fix must apply to ALL services (mc, mc-test, future instances). Never solve a problem for one service only. If `mc-test` has a volume mount, env var, or entrypoint fix, the main `mc` service (via `docker-compose.override.yml`) must have it too, and vice versa. Think holistically — test, frontend, backend, database.

### Development Method — BMAD

All features follow the **BMAD method** (v6.0.1). Use `/bmad-help` to see next steps.

| Track | When to use | Entry point |
|-------|-------------|-------------|
| **Full BMAD** | New product area, complex multi-system feature, >5 stories, requires PRD + Architecture | Phase 1 or 2 |
| **Quick Flow** | Bug fixes, small features, clear scope (1–15 stories) | `/bmad-bmm-quick-spec` → `/bmad-bmm-quick-dev` |

**Full BMAD implementation cycle** (follow this order strictly):

1. Create an implementation plan
2. Create stories → `/@_bmad/bmm/workflows/4-implementation/create-story`
3. Create a wave plan grouping stories for parallel execution
4. **Delegate story execution to Sonnet subagents** — NEVER implement stories in the orchestrating session. Always spawn Sonnet (Claude) or GPT-5.4 Medium (Codex) agents via `dev-story`. Each agent receives the story file and implements independently.
5. Dev agent executes → `/@_bmad/bmm/workflows/4-implementation/dev-story`
6. **Code review with Opus** → `/@_bmad/bmm/workflows/4-implementation/code-review` — Always use Opus for code review. Reviews must find 3–10 issues.
7. Run full test suite (`make check`)
8. Integration test — simulate real service interaction using backend functions
9. `make docker-test` to spin up an isolated test instance (auto-detects free ports, prints dashboard URL)
10. Share the dashboard URL with the human for manual testing. Stop with `make docker-test-down` when done.

**MANDATORY AGENT DELEGATION:** The orchestrating agent (Opus) creates stories and reviews code. Implementation is ALWAYS delegated to Sonnet/GPT subagents. This is non-negotiable — it ensures separation of concerns and prevents context pollution.

**Workflow rules:**
- **Step-file discipline.** Load one step at a time, follow exactly, never skip ahead.
- **Role boundaries.** Dev agents must not modify architecture decisions. Conflict → halt and escalate.
- **Validation gates are mandatory.** PRD validation, Implementation Readiness, Code Review (must find 3–10 issues).
- **Stories must be self-contained.** A fresh agent must implement a story without prior conversation history.

**Artifacts:** `_bmad-output/planning-artifacts/` (PRD, architecture), `_bmad-output/implementation-artifacts/` (stories, sprint status), `_bmad-output/project-context.md` (LLM-optimized rules for workflows).

### Feature Implementation — Always Use Worktrees

**All feature work — BMAD or not — MUST be implemented in an isolated git worktree.** Never implement features directly on `main`. This applies to:
- BMAD stories (full or quick flow)
- Ad-hoc features, optimizations, refactors
- Any change that spans multiple files or requires a plan

**Workflow:**
1. Create a worktree branch (e.g. `git worktree add .claude/worktrees/<feature-name> -b feat/<feature-name>`)
2. Implement in the worktree
3. Validate (`make check`)
4. Merge to `main` when approved
5. **Delete immediately** after merge: `git worktree remove .claude/worktrees/<feature-name>`

### Testing

[`running_tests.md`](agent_docs/running_tests.md) is **mandatory reading** before writing or modifying any test. It defines what to test, what to skip, banned anti-patterns, and the quality checklist. Follow it strictly.

**Subagent efficiency:** when dispatching subagents to write tests, provide all context upfront — target file, example test to follow, specific scenarios, output path. Do not let subagents explore the codebase to discover patterns.

### Bug Fixes — TDD Mandatory

When fixing a bug in already-implemented functionality, always follow the red-green TDD cycle:

1. **Investigate** — understand the root cause before writing any code
2. **Write a failing test** — create a test that reproduces the bug. Run it and confirm it **fails** (red)
3. **Implement the fix** — write the minimal code to address the root cause
4. **Verify the test passes** — run the same test and confirm it **passes** (green)

Never skip the red phase. A fix without a test that first proves the failure is not verified.

### Error Handling

Never add silent fallbacks that mask failures. Fail explicitly with clear errors. Only add fallbacks if explicitly requested.

### Docker Volumes — NEVER Delete

**NEVER run `docker volume rm` on any project volume.** Convex data, agent memory, task history, and squad definitions live in Docker volumes. Deleting a volume destroys all persistent state with no recovery. If Convex fails to start, investigate the root cause (port conflicts, stale locks, resource limits) — do NOT delete the volume as a shortcut.

### Vendor Boundary

`vendor/nanobot/` is an upstream git subtree. **Do NOT edit** without explicit permission. `vendor/claude-code/` is our code — follows project conventions.

## Agent Docs — Contracts

These are **binding contracts**. Before touching any layer, **read the relevant docs** below. Do not guess — read the contract first.

`agent_docs/` contains only permanent reference docs. Do NOT add ephemeral files here.

### Structural contracts (require human approval to change)

**Keep contracts in sync.** If a code change alters behavior governed by a structural contract, update the doc in the same PR/commit.

| File | When to read | Description |
|------|-------------|-------------|
| [`service_architecture.md`](agent_docs/service_architecture.md) | Adding/modifying workers, services, processes, or changing runtime lifecycle | Every runtime service, process lifecycle, IPC protocols, env vars, task execution state machine |
| [`service_communication_patterns.md`](agent_docs/service_communication_patterns.md) | Changing how services talk to each other — IPC, bridge, polling, webhooks | Protocol specs for IPC sockets, Convex bridge, MCP bridge, dashboard↔backend, inter-agent messaging |
| [`database_schema.md`](agent_docs/database_schema.md) | Adding/modifying Convex tables, fields, indexes, or writing queries/mutations | All Convex tables with field types, indexes, relationships, valid enum values |
| [`cross_service_naming.md`](agent_docs/code_conventions/cross_service_naming.md) | Using status values, entity types, or field names crossing Python↔TypeScript | Key conversion rules, status enums, entity type names shared across services |

### Reference docs (read before working in scope)

| File | When to read | Description |
|------|-------------|-------------|
| [`building_the_project.md`](agent_docs/building_the_project.md) | Setting up, running the stack, debugging startup, port layout | Prerequisites, `make` commands, startup sequence, port assignments, health checks |
| [`code_conventions/python.md`](agent_docs/code_conventions/python.md) | Writing/modifying Python in `mc/` or `tests/mc/` | Ruff config, naming, type hints, import ordering |
| [`code_conventions/convex.md`](agent_docs/code_conventions/convex.md) | Writing/modifying Convex functions in `dashboard/convex/` | Function patterns, lib module structure, Convex testing |
| [`code_conventions/typescript.md`](agent_docs/code_conventions/typescript.md) | Writing/modifying React/Next.js in `dashboard/` (excl. `convex/`) | Component structure, feature modules, hook patterns |
| [`running_tests.md`](agent_docs/running_tests.md) | Before writing, modifying, or running any test — **mandatory** | Decision tree (test vs skip), commands, banned anti-patterns, quality checklist |
| [`scaling_decisions.md`](agent_docs/scaling_decisions.md) | Hitting platform limits (Convex 1MB, storage, throughput) or changing data flow for large content | Architectural decisions that work now but need revisiting at scale — current limits, files involved, future direction |
| [`harness_engineering.md`](agent_docs/harness_engineering.md) | Modifying agents, skills, memory, threads, workspaces, or squads | Platform internals — skill registration (CC dual registration), memory consolidation, workspace layout, thread journals, squad routing |
