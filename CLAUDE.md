# Feature Development Process

## Overview

This project uses the BMad workflow system for feature development. Follow this process for every feature/story implementation.

## Step 1: Have a Story

Before coding, ensure you have an implementation-ready story artifact.

- If a story already exists: find it in `_bmad-output/implementation-artifacts/`
- If a story does not exist: create one using the `/create-story` command

## Step 2: Develop the Story

**Before spawning any dev agent, ask the user** which execution mode to use:
1. **Codex** (`gpt-5.4`): execute via `codex exec` (external Codex CLI)
2. **Sonnet** (`claude-sonnet-4-6`): use Claude Sonnet as the dev agent (cost-efficient, fast)

Do not proceed without the user's answer.

### Spawning Dev Agents

Use the Task tool to spawn dev agents in isolated git worktrees (`isolation: "worktree"`). Each agent receives:
- The full story spec
- The dev-story workflow reference
- Instructions to implement, test, commit, and self-review

Always set the `model` parameter on the Task tool:
- If user chose Sonnet: `model: "sonnet"`
- If user chose Codex: use Bash tool with `codex exec`
- Never use `model: "opus"` for dev agents

For multiple independent stories: spawn agents in parallel with `run_in_background: true`.

## Step 3: Review the Story

After development, spawn a review agent (Opus) for each completed story. The reviewer:
- Reads the actual implementation code
- Verifies spec compliance line by line
- Reports PASS or issues with file:line references

## Step 4: Fix Review Findings

Address any HIGH/CRITICAL findings before merging.

## Step 5: Merge Worktrees

Merge each worktree branch back into main. Resolve conflicts from parallel development.

## Python Environment

- Always use `uv run python` instead of `python3` (system python3 may be outdated)
- Use `uv` as the package manager (not pip)
- Run tests with `uv run pytest`

## Project Structure

- `mc/` — Mission Control Python backend (multi-agent orchestration)
- `vendor/nanobot/` — git subtree of upstream nanobot (with patches documented in PATCHES.md)
- `vendor/claude-code/` — Claude Code headless backend
- `dashboard/` — Next.js + Convex frontend
- `boot.py` — entry point that wires vendor path + CLI
- `tests/mc/` — Python tests for MC module

### Code Conventions

- Linter: ruff (configured in pyproject.toml)
- Line length: 100 characters
- Type hints: required on all public functions
- Naming: snake_case for functions/variables, PascalCase for classes
- Test runner: pytest (Python), vitest (TypeScript/dashboard)

### Upstream Sync

```bash
git fetch upstream
git subtree pull --prefix=vendor/nanobot upstream main --squash
# Resolve conflicts using PATCHES.md as guide
```
