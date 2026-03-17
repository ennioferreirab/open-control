# Nanobot - Mission Control

## Vendor Boundary

`vendor/nanobot/` is a git subtree of [HKUDS/nanobot](https://github.com/HKUDS/nanobot). **Do NOT edit files inside `vendor/nanobot/` without explicit user permission.** We absorb upstream evolution over time — the closer we stay to the original project, the easier syncs are. This directory must be excluded from project-wide code conventions and linting rules.

`vendor/claude-code/` is our own code and **must follow** the same code conventions as the rest of the project.

## Language

All code (variables, functions, classes, comments, commit messages, docstrings) must be written in English.

## Convex Local Backend

This project runs Convex locally (`npx convex dev --local`). Only **one instance** of the local backend is allowed at a time — it binds to port 3210 exclusively. If you see the error `A local backend is still running on port 3210`, do NOT try to start a second instance. Instead, restart the existing one.

**Implications for worktrees:** When working in a git worktree, the Convex schema and functions are deployed to the same local backend as the main tree. Do not run `npx convex dev --local` from a worktree — it will fail. Any Convex function changes in a worktree must be deployed by restarting the single local backend instance from the main tree, or by stopping the existing instance first (`lsof -ti:3210 | xargs kill`) and starting it from the worktree.

**`make start` must account for this:** If a local backend is already running, the start command should restart it rather than attempt to launch a parallel instance.

## Worktree Lifecycle

All new features must be implemented in isolated git worktrees. After the branch is merged back into main, the worktree **must be deleted** immediately. Do not leave stale worktrees around.

```bash
# After merge
git worktree remove .claude/worktrees/<name>
# Or if already deleted on disk
git worktree prune
```

## Code Conventions

Follow the conventions documented in `agent_docs/code_conventions/`:

- [`python.md`](agent_docs/code_conventions/python.md) — `mc/` and `tests/mc/`
- [`convex.md`](agent_docs/code_conventions/convex.md) — `dashboard/convex/`
- [`typescript.md`](agent_docs/code_conventions/typescript.md) — `dashboard/` (excluding `convex/`)
- [`cross_service_naming.md`](agent_docs/code_conventions/cross_service_naming.md) — shared naming contract between all layers
