# Nanobot - Mission Control

## Vendor Boundary

`vendor/nanobot/` is a git subtree of [HKUDS/nanobot](https://github.com/HKUDS/nanobot). **Do NOT edit files inside `vendor/nanobot/` without explicit user permission.** We absorb upstream evolution over time — the closer we stay to the original project, the easier syncs are. This directory must be excluded from project-wide code conventions and linting rules.

`vendor/claude-code/` is our own code and **must follow** the same code conventions as the rest of the project.

## Language

All code (variables, functions, classes, comments, commit messages, docstrings) must be written in English.

## Stack Lifecycle

Use `make start` / `make down` to manage the stack. Use `make validate` for pre-commit checks (no Convex needed). Use `make takeover` from a worktree to steal the Convex instance. See [`building_the_project.md`](agent_docs/building_the_project.md) for full details.

**Convex singleton:** only one local backend can run (port 3210). `make start` kills any existing instance before starting. Never run `npx convex dev --local` directly.

## Development Method

All features follow the **BMAD method**. Use `/bmad-help` to see next steps. The phases are:

1. **Analysis** (optional) — Brainstorm, research, product brief
2. **Planning** (required) — PRD → UX design
3. **Solutioning** (required) — Architecture → Epics & Stories → Implementation Readiness check
4. **Implementation** (per story cycle) — Sprint Plan → Create Story → Validate Story → Dev Story → Code Review → next story

- Artifacts go to `_bmad-output/` (planning and implementation)
- BMAD engine lives in `_bmad/` — do not edit
- Legacy artifacts from prior cycles are in `bmad_history/` (read-only reference)

## Worktree Lifecycle

All new features must be implemented in isolated git worktrees. After the branch is merged back into main, the worktree **must be deleted** immediately. Do not leave stale worktrees around.

```bash
# After merge
git worktree remove .claude/worktrees/<name>
# Or if already deleted on disk
git worktree prune
```

## Agent Docs

Before starting work, scan the list below and **read whichever docs are relevant** to the task at hand. You do not need to read all of them — pick the ones that apply.

`agent_docs/` is the **canonical index** of project documentation for agents. **Only permanent reference docs belong here.** Do NOT add ephemeral files (audit reports, one-off analyses, migration checklists, plan artifacts) to this directory or to the table below.

`agent_docs/` contains:

| File | Scope | Description |
|------|-------|-------------|
| [`building_the_project.md`](agent_docs/building_the_project.md) | All layers | Prerequisites, setup, startup sequence, ports, baseline checks, npm scripts |
| [`service_architecture.md`](agent_docs/service_architecture.md) | All layers | Runtime services, processes, communication protocols, IPC, env vars, and task execution lifecycle |
| [`service_communication_patterns.md`](agent_docs/service_communication_patterns.md) | All layers | IPC socket protocol, Convex bridge, MCP bridge, polling loops, dashboard comm, inter-agent patterns, hooks |
| [`database_schema.md`](agent_docs/database_schema.md) | `dashboard/convex/` | All 26 Convex tables with fields, types, indexes, and relationships |
| [`code_conventions/python.md`](agent_docs/code_conventions/python.md) | `mc/`, `tests/mc/` | Python tooling, naming, type hints, ruff rules |
| [`code_conventions/convex.md`](agent_docs/code_conventions/convex.md) | `dashboard/convex/` | Convex function patterns, lib modules, testing |
| [`code_conventions/typescript.md`](agent_docs/code_conventions/typescript.md) | `dashboard/` (excl. `convex/`) | React/Next.js patterns, feature modules, hooks |
| [`code_conventions/cross_service_naming.md`](agent_docs/code_conventions/cross_service_naming.md) | All layers | Shared naming contract: key conversion, status values, entity types |
| [`running_tests.md`](agent_docs/running_tests.md) | All layers | When to test, what to skip, testing pipeline, commands, quality checklist |
