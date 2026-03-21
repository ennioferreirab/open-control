# Building & Running the Project

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11+ | — |
| Node.js | 18+ | — |
| `uv` | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Git | — | — |

## Initial Setup

```bash
uv sync                          # Python deps (includes vendor/ editable installs)
cd dashboard && npm install      # Node deps
```

## Makefile Targets

The `Makefile` at the project root is the primary interface for all operations.

| Target | What it does | Needs Convex? |
|--------|-------------|---------------|
| `make start` | Start attached — logs stream to terminal, Ctrl+C to stop | Starts it |
| `make up` | Start detached — runs in background, logs → `/tmp/mc.log` | Starts it |
| `make down` | Stop everything | — |
| `make status` | Show system health (agents, tasks) | Yes |
| `make test` | Run all unit tests (Python + TypeScript) | No |
| `make check` | Lint + typecheck + unit tests | No |
| `make takeover` | Stop any running stack, start from current tree (attached) | Restarts it |
| `make docker-build` | Build Docker image | No |
| `make docker-test` | Spin up isolated Docker test instance (auto-detects ports) | Own Convex |
| `make docker-test-down` | Stop Docker test instance | — |
| `make lint` | Ruff + ESLint | No |
| `make typecheck` | Pyright + tsc | No |
| `make format` | Format all code (Ruff + Prettier) | No |

Sub-targets: `test-py`, `test-ts`, `lint-py`, `lint-ts`, `typecheck-py`, `typecheck-ts`, `format-py`, `format-ts`.

## Stack Architecture

The system is **four cooperating processes** managed by `ProcessManager` (`mc/cli/process_manager.py`). See [`service_architecture.md`](service_architecture.md) for full details.

```bash
make start
# Starts in order:
#   1. Convex local backend  (:3210, kills existing if port occupied)
#   2. Next.js frontend      (:3000)
#   3. MC Gateway             (event loop, IPC socket, all workers)
#   4. Nanobot Gateway        (channels: Telegram, Slack, etc.)
```

### Ports & Sockets

| Process | Address | Protocol |
|---------|---------|----------|
| Convex local backend | `localhost:3210` | WebSocket |
| Next.js frontend | `localhost:3000` | HTTP |
| Interactive runtime | `localhost:8765` | WebSocket |
| Agent IPC | `/tmp/mc-agent.sock` | Unix socket |

## Convex Local Backend — Singleton Constraint

Only **one** Convex local backend can run at a time (port 3210 is exclusive). The `ProcessManager` handles this automatically — it kills any process on `:3210` before starting Convex. But you must understand the implications for worktrees.

### Why This Matters

The Convex local backend holds the **schema and functions** deployed to it. When you switch between main tree and a worktree, the deployed schema may differ. Running `make start` deploys the current tree's schema. Running it from a different tree overwrites the previous deployment.

### Worktree Workflow — Docker (preferred)

Docker test instances are fully isolated — each worktree gets its own Convex, its own ports, no conflicts with the main stack or other worktrees.

```text
┌─────────────────────────────────────────────────────────────┐
│ Docker worktree flow (no conflicts)                          │
│                                                              │
│  1. make check          ← lint, types, unit tests         │
│     (no Convex needed)                                       │
│                                                              │
│  2. make docker-test       ← auto-detects ports, starts      │
│     (prints dashboard URL for human testing)                 │
│                                                              │
│  3. make docker-test-down  ← stops this worktree's instance  │
│     (main stack is untouched)                                │
└─────────────────────────────────────────────────────────────┘
```

**Requires:** Docker image built at least once (`make docker-build`). The image is shared across worktrees — only needs rebuilding when deps or Convex schema change.

### Worktree Workflow — Native (legacy, conflicts)

Without Docker, Convex local is a singleton. Only one stack can run at a time.

```text
┌─────────────────────────────────────────────────────────────┐
│ Native worktree flow (kills other stacks)                    │
│                                                              │
│  1. make check          ← lint, types, unit tests         │
│     (worktree-safe, no Convex needed)                        │
│                                                              │
│  2. If you need the dashboard to validate visually:          │
│     make takeover           ← stops main, starts worktree    │
│     (validates in browser at localhost:3000)                  │
│                                                              │
│  3. When done:                                               │
│     make down               ← stop worktree stack            │
│     (go to main tree, make start to restore)                 │
└─────────────────────────────────────────────────────────────┘
```

**Key rules:**
- `make check` is always safe — runs without Convex
- `make takeover` from a worktree will kill the main tree's stack
- After merging a worktree branch, always `make start` from main to redeploy the schema
- Never run `npx convex dev --local` directly — use `make start` or `make takeover`
- **Prefer `make docker-test`** when Docker is available — avoids all conflicts

## Environment Variables

Primary config lives in `dashboard/.env.local` (auto-created by `convex dev`):

```bash
CONVEX_DEPLOYMENT=anonymous:anonymous-dashboard
NEXT_PUBLIC_CONVEX_URL=http://127.0.0.1:3210
```

The gateway reads `NEXT_PUBLIC_CONVEX_URL` (or falls back to parsing `dashboard/.env.local`). See [`service_communication_patterns.md`](service_communication_patterns.md) for all env vars and IPC details.

## Baseline Checks

Run `make check` before committing. This runs lint + typecheck + unit tests without needing Convex.

For test strategy and when to write tests, see [`running_tests.md`](running_tests.md).

### Architecture Guardrails (must pass before merge)

```bash
uv run pytest tests/mc/test_architecture.py
cd dashboard && npm run test:architecture
```

These are included in `make test`.

## Package Management

| Layer | Manager | Config | Add dependency |
|-------|---------|--------|----------------|
| Python | `uv` (never `pip`) | `pyproject.toml` | `uv add <pkg>` |
| Node | `npm` | `dashboard/package.json` | `cd dashboard && npm install <pkg>` |

Python vendor packages (`vendor/nanobot/`, `vendor/claude-code/`) are installed as editable via `[tool.uv.sources]` in `pyproject.toml`.
