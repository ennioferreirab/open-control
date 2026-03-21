# ─── Open Control ────────────────────────────────────────────────
#
# make start       Start attached — logs stream to terminal (Ctrl+C to stop)
# make up          Start detached — runs in background, logs → /tmp/mc.log
# make down        Stop everything
# make status      Show system health
#
# make test        Unit tests only (no Convex needed, worktree-safe)
# make check       Lint + typecheck + unit tests (worktree-safe)
# make takeover    Stop any running stack, start from current tree
#
# make docker-build      Build the Docker image
# make docker-up         Start the containerized stack
# make docker-down       Stop the containerized stack
# make docker-test       Spin up isolated test instance (auto-detects ports)
# make docker-test-down  Stop the test instance
#
# make install      Install all dependencies (Python + Node)
# make lint         Ruff + ESLint
# make typecheck    Pyright + tsc
# make format       Format all code
# ──────────────────────────────────────────────────────────────────

.PHONY: install start up down status test check takeover lint typecheck format \
        test-py test-ts lint-py lint-ts typecheck-py typecheck-ts format-py format-ts \
        docker-build docker-up docker-down docker-test docker-test-down

MC_CMD := uv run nanobot mc start
PUBLIC_MC_CMD := uv run open-control mc start

# ─── Setup ───────────────────────────────────────────────────────

install:
	uv sync --group dev
	cd dashboard && npm ci

# ─── Stack lifecycle ──────────────────────────────────────────────

start:
	@$(MC_CMD)

up:
	@nohup $(MC_CMD) > /tmp/mc.log 2>&1 & echo "Open Control started in background. Logs: /tmp/mc.log"

down:
	@uv run nanobot mc down

status:
	@uv run nanobot mc status

# Stop any running MC instance, then start from current directory.
# Use this from a worktree to take over the Convex local backend.
# Purges __pycache__ so stale .pyc from deleted modules are not loaded.
takeover: down
	@sleep 2
	@find mc/ -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@$(MC_CMD)

# Public CLI note:
# The preferred branded command is `$(PUBLIC_MC_CMD)`.
# The current Make targets still execute `$(MC_CMD)` for runtime compatibility.

# ─── Testing ──────────────────────────────────────────────────────
# Unit tests are fully mocked — no Convex needed.
# Safe to run from worktrees without touching the running stack.

test: test-py test-ts

test-py:
	uv run pytest

test-ts:
	cd dashboard && npm run test

# ─── Validation (pre-commit / pre-merge) ─────────────────────────
# Runs everything that doesn't need a running stack.

check: lint typecheck test

# ─── Linting ──────────────────────────────────────────────────────

lint: lint-py lint-ts

lint-py:
	uv run ruff format --check mc/ tests/mc/
	uv run ruff check mc/ tests/mc/

lint-ts:
	cd dashboard && npx prettier --check .
	cd dashboard && npm run lint

# ─── Type checking ────────────────────────────────────────────────

typecheck: typecheck-py typecheck-ts

typecheck-py:
	uv run pyright mc/

typecheck-ts:
	cd dashboard && npm run typecheck

# ─── Formatting ───────────────────────────────────────────────────

format: format-py format-ts

format-py:
	uv run ruff format mc/ tests/mc/

format-ts:
	cd dashboard && npm run format

# ─── Docker ──────────────────────────────────────────────────────

docker-build:
	docker build -t mc-test:latest .

docker-up:
	docker compose up -d

docker-down:
	docker compose down

# Spin up an isolated test instance with auto-detected ports.
# Safe to run from any worktree — each gets its own container + Convex.
docker-test:
	@bash scripts/docker-test.sh

docker-test-down:
	@bash scripts/docker-test.sh down
