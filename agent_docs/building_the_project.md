# Building & Running the Project

## Prerequisites

| Tool | Required for | Install |
|------|-------------|---------|
| Docker Desktop | Running the stack | docker.com |
| Python 3.11+ + `uv` | `make check` (local lint/tests) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js 18+ | `make check` (local lint/tests) | nodejs.org |

Docker is the only requirement for running the full stack. Python and Node are only needed for local lint/typecheck/test (`make check`).

## Initial Setup

```bash
make install    # Local Python + Node deps (for make check)
make start      # Build image + start stack (first run ~2min, then ~5s)
```

## Makefile Targets

| Target | What it does | Needs Docker? |
|--------|-------------|---------------|
| `make start` | Start attached — logs stream to terminal, Ctrl+C to stop | Yes |
| `make up` | Start detached — runs in background | Yes |
| `make down` | Stop everything | Yes |
| `make test` | Run all unit tests (Python + TypeScript) | No |
| `make check` | Lint + typecheck + unit tests | No |
| `make docker-test` | Spin up isolated Docker test instance (auto-detects ports) | Yes |
| `make docker-test-down` | Stop Docker test instance | Yes |
| `make lint` | Ruff + ESLint | No |
| `make typecheck` | Pyright + tsc | No |
| `make format` | Format all code (Ruff + Prettier) | No |

Sub-targets: `test-py`, `test-ts`, `lint-py`, `lint-ts`, `typecheck-py`, `typecheck-ts`, `format-py`, `format-ts`.

Other useful commands (run directly):

```bash
docker compose logs -f          # Tail logs (if detached)
docker compose restart mc       # Restart after Python changes (~3s)
docker compose ps               # Check stack status
docker compose exec mc bash     # Shell into container
docker compose down -v          # Stop + wipe Convex data (fresh start)
```

## Stack Architecture

The system runs **four cooperating processes** inside a Docker container, managed by `ProcessManager` (`mc/cli/process_manager.py`). See [`service_architecture.md`](service_architecture.md) for full details.

```bash
make start
# Docker Compose builds image (if needed) and starts container.
# Inside container, processes start in order:
#   1. Convex local backend  (:3210)
#   2. Next.js frontend      (:3000)
#   3. MC Gateway             (event loop, IPC socket, all workers)
#   4. Nanobot Gateway        (channels: Telegram, Slack, etc.)
```

### Ports

| Process | Host Port | Protocol |
|---------|-----------|----------|
| Next.js frontend | `localhost:3000` | HTTP |
| Convex local backend | `localhost:3210` | WebSocket |
| Convex site | `localhost:3211` | HTTP |
| Interactive runtime | `localhost:8765` | WebSocket |
| Nanobot gateway | `localhost:18790` | HTTP |

### Hot Reload

| Layer | Auto-reload? | Mechanism |
|-------|-------------|-----------|
| Next.js (dashboard/) | Yes | Webpack HMR via polling |
| Convex functions (dashboard/convex/) | Yes | `convex dev --local` file watcher |
| Python (mc/) | No | `docker compose restart mc` (~3s) |

Source code is bind-mounted from the host. Edit files normally — changes are reflected in the container.

## Docker Development Details

### First Run

First `make start` builds the Docker image (~2min) and installs Node dependencies into a named volume (~30s). Subsequent starts take ~5s.

### Dependency Changes

When `pyproject.toml` or `dashboard/package.json` changes:

```bash
# Python deps changed
docker compose exec mc uv sync --frozen

# Node deps changed
docker compose exec mc bash -c "cd /app/dashboard && npm ci"

# Or just restart — the dev entrypoint re-syncs Python deps automatically
docker compose restart mc
```

### Convex Schema Reset

If a breaking schema change causes errors, wipe the Convex volume and restart:

```bash
docker compose down -v    # -v removes named volumes (Convex data + node_modules)
make start                # Fresh start with template database
```

### Worktree Workflow

Each worktree can use `make docker-test` for isolated instances (own Convex, own ports):

```bash
make check              # lint, types, unit tests (no Docker needed)
make docker-test        # auto-detects ports, starts isolated stack
make docker-test-down   # stops this worktree's instance
```

## Environment Variables

The dev entrypoint generates `.env.local` files automatically. No manual env setup needed.

For custom overrides, set env vars in `docker-compose.override.yml` or pass them via shell:

```bash
MC_LOG_LEVEL=DEBUG make start
```

See [`service_communication_patterns.md`](service_communication_patterns.md) for all env vars and IPC details.

## Baseline Checks

Run `make check` before committing. This runs lint + typecheck + unit tests locally without Docker.

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
