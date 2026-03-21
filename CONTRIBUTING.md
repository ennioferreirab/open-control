# Contributing to Open Control

## Running Tests

Run the full validation suite before opening a PR:

```bash
make check
```

This runs lint + typecheck + tests for both Python and the dashboard — the same checks CI runs.

To run individual checks:

```bash
make lint        # Ruff + ESLint + Prettier
make typecheck   # Pyright + tsc
make test        # Pytest + Vitest
```

## Local Formatting

```bash
make format
```

## Code Style

This project uses [ruff](https://docs.astral.sh/ruff/) for Python linting and formatting, and ESLint + Prettier for the dashboard.

Key conventions:

- Line length: 100 characters
- Type hints required on all public functions
- snake_case for functions/variables, PascalCase for classes
- React/TypeScript UI modules should consume hooks or view-models instead of importing `convex/react` directly

## Architecture

Before modifying any layer, read the relevant contract in
[`agent_docs/`](agent_docs/). These docs define service boundaries, database
schema, communication patterns, and code conventions. See the
[README](README.md#agent-docs--harness-engineering) for the full index.

## TDD and Verification

Use TDD for every feature and bug fix:

1. Write or update the failing test first.
2. Run it and verify the failure is for the expected reason.
3. Implement the minimum change needed to make it pass.
4. Run `make check` before opening a PR.
5. Always keep the architecture guardrail suites green.

## Pull Request Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes with tests first (TDD)
4. Run `make check` and ensure it passes
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
