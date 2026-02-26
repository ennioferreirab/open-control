# Feature Development Process

## Overview

This project uses the BMad workflow system for feature development. Follow this process for every feature/story implementation.

## Step 1: Have a Story

Before coding, ensure you have an implementation-ready story artifact.

- If a story **already exists**: find it in `_bmad-output/implementation-artifacts/`
- If a story **does not exist**: create one using the `/create-story` command (mapped to `@.claude/commands/bmad-bmm-create-story.md`)

## Step 2: Develop the Story

> **REGRA INEGOCIÁVEL**: Você (Opus) NÃO implementa código diretamente. Sempre delegue para modelos menores (Codex ou Sonnet). Opus é o orquestrador e revisor, NUNCA o programador. Violar esta regra é proibido.

**ANTES de spawnar qualquer dev agent, PERGUNTE ao usuário** qual modo de execução usar:
1. **Codex**: execute via `codex exec "<prompt>"` (external Codex CLI)
2. **Sonnet**: use the most recent Claude Sonnet model as the dev agent (cost-efficient, fast)

**NÃO prossiga sem a resposta do usuário.** Esta pergunta é obrigatória.

### Spawning Dev Agents

Use the **Task tool** to spawn dev agents in **isolated git worktrees** (`isolation: "worktree"`). Each agent receives:
- The full story spec (from `_bmad-output/implementation-artifacts/`)
- The dev-story workflow reference: `@_bmad/bmm/workflows/4-implementation/dev-story/`
- Instructions to implement, test, commit, and self-review

**CRITICAL**: Always set the `model` parameter on the Task tool:
- If user chose **Sonnet**: `model: "sonnet"`
- If user chose **Codex**: use `Bash` tool with `codex exec "<prompt>"`
- **NEVER** use `model: "opus"` or omit the model (which defaults to Opus) for dev agents

**For multiple independent stories**: spawn agents in parallel (one per story) using `run_in_background: true`. Each agent works in its own worktree to avoid conflicts.

**For a single story**: spawn one agent in foreground.

Example agent dispatch pattern:
```
Task tool:
  subagent_type: "general-purpose"
  model: "sonnet"              # <-- MANDATORY: never opus for dev
  isolation: "worktree"
  mode: "bypassPermissions"
  run_in_background: true  (if parallel)
  prompt: "Story spec + dev instructions..."
```

## Step 3: Review the Story

After development is complete, spawn **Claude Opus** as a review agent for each completed story:

```
@_bmad/bmm/workflows/4-implementation/code-review/
```

### Spawning Review Agents

Use the **Task tool** with `subagent_type: "superpowers:code-reviewer"` to spawn review agents. Each reviewer:
- Receives the full story spec (acceptance criteria)
- Reads the actual implementation code (do NOT trust the dev agent's report)
- Verifies spec compliance line by line
- Reports PASS or issues with file:line references

**For multiple stories**: spawn review agents in parallel as each dev agent completes (`run_in_background: true`).

The review agent must use **Opus** for thorough, adversarial review quality. (This is the ONLY step where Opus executes directly.)

## Step 4: Fix Review Findings

Address any HIGH/CRITICAL findings from the review before merging.

## Step 5: Merge Worktrees

After all stories pass review, merge each worktree branch back into the main branch. Resolve any conflicts from parallel development (especially in shared files like `schema.ts`, `executor.py`).

## Python Environment

- Always use `uv run python` instead of `python3` (system python3 is macOS stock 3.9)
- Use `uv` as the package manager (not pip)
- Run tests with `uv run pytest`

## Project Structure

- `dashboard/` — Next.js + Convex frontend (TypeScript)
- `nanobot/mc/` — Mission Control Python backend (bridge, gateway, types)
- `nanobot/agent/` — Agent runtime (heavy deps: loguru, etc.)
- `tests/mc/` — Python tests for MC module
- Test runners: pytest (Python), vitest (TypeScript/dashboard)
- `nanobot/agent/__init__.py` imports AgentLoop (heavy deps) — avoid importing `nanobot.agent` package in MC module; use `importlib.util` for direct file imports if needed
