# Contributing to Open Control

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Node.js 18+ (for dashboard)
- Git

## Development Setup

```bash
git clone https://github.com/<owner>/open-control.git
cd open-control
uv sync
```

> Runtime compatibility note: some local commands still use the legacy
> `nanobot` CLI name until the public alias migration is complete. When the
> package is installed, prefer `open-control mc ...` in user-facing docs and
> examples.

## Running Tests

```bash
# Python files you changed
uv run ruff format --check path/to/file.py
uv run ruff check path/to/file.py

# Python guardrails
uv run pytest tests/mc/test_architecture.py tests/mc/test_module_reorganization.py tests/mc/infrastructure/test_boundary.py

# Dashboard files you changed
cd dashboard
npm run format:file:check -- path/to/file.tsx
npm run lint:file -- path/to/file.tsx
npm run test:architecture
cd ..
```

## Local Formatting

```bash
# Python files you changed
uv run ruff format path/to/file.py

# Dashboard files you changed
cd dashboard && npm run format:file -- path/to/file.tsx
```

## Code Style

This project uses [ruff](https://docs.astral.sh/ruff/) for Python linting and formatting, and ESLint + Prettier for the dashboard:

```bash
uv run ruff check path/to/file.py
uv run ruff format path/to/file.py
cd dashboard && npm run lint:file -- path/to/file.tsx && npm run format:file:check -- path/to/file.tsx
```

Key conventions:

- Line length: 100 characters
- Type hints required on all public functions
- snake_case for functions/variables, PascalCase for classes
- React/TypeScript UI modules should consume hooks or view-models instead of importing `convex/react` directly

## Architecture Rules

Follow [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) when placing new code:

- `mc/runtime/` composes flows and lifecycle wiring
- `mc/contexts/` owns business behavior
- `mc/domain/` owns pure rules and shared invariants
- `mc/bridge/` owns Convex-facing access
- `mc/infrastructure/` owns framework, environment, and filesystem concerns

Do not add new public modules back into the `mc/` root. Use canonical package entrypoints where available.

## TDD and Verification

Use TDD for every feature and bug fix:

1. Write or update the failing test first.
2. Run it and verify the failure is for the expected reason.
3. Implement the minimum change needed to make it pass.
4. Run the relevant baseline checks again before opening a PR.
5. Always keep the architecture guardrail suites green.

## Pull Request Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes with tests first (TDD)
4. Run the relevant changed-file baseline commands for Python and/or dashboard
5. Ensure GitHub Actions is green before requesting review
6. Commit with clear messages
7. Push and open a Pull Request

## Adding Features

### New Agent Type

1. Create agent YAML in the agents directory
2. Register via `open-control mc agents sync` when the public alias is available, or
   `nanobot agents sync` as the current compatibility command
3. Add tests in `tests/mc/`

### New Hook Handler

1. Create handler class extending `BaseHandler` in `mc/hooks/handlers/`
2. Handlers are auto-discovered -- no registration needed
3. Add tests in `tests/mc/hooks/handlers/`

## Reporting Issues

Please include:

- Python version (`python --version`)
- OS and version
- Steps to reproduce
- Expected vs actual behavior
- Error messages / tracebacks
