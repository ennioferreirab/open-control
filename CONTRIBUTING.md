# Contributing to nanobot-mcontrol

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Node.js 18+ (for dashboard)
- Git

## Development Setup

```bash
git clone https://github.com/<owner>/nanobot-mcontrol.git
cd nanobot-mcontrol
uv sync
```

## Running Tests

```bash
# Python tests
uv run pytest tests/mc/ -v

# Dashboard tests
cd dashboard && npm test
```

## Code Style

This project uses [ruff](https://docs.astral.sh/ruff/) for linting:

```bash
uv run ruff check mc/
uv run ruff format mc/
```

Key conventions:
- Line length: 100 characters
- Type hints required on all public functions
- snake_case for functions/variables, PascalCase for classes

## Pull Request Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes with tests
4. Run the test suite: `uv run pytest tests/mc/ -v`
5. Run the linter: `uv run ruff check mc/`
6. Commit with clear messages
7. Push and open a Pull Request

## Adding Features

### New Agent Type
1. Create agent YAML in the agents directory
2. Register via `nanobot agents sync`
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
