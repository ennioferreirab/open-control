# Python Code Conventions

Applies to `mc/`, `tests/mc/`, and `vendor/*/`. Does **NOT** apply to `vendor/nanobot/`.

> **Cross-service naming**: see [`cross_service_naming.md`](cross_service_naming.md) for the shared naming contract between Python, Convex, and TypeScript.

## Tooling

| Tool | Command | Config |
|------|---------|--------|
| Formatter | `uv run ruff format` | `pyproject.toml` |
| Linter | `uv run ruff check` | `pyproject.toml` |
| Type checker | `uv run pyright` | `pyproject.toml [tool.pyright]` |
| Test runner | `uv run pytest` | `pyproject.toml` |
| Package manager | `uv` (never `pip`) | — |
| Python runtime | `uv run python` (never bare `python3`) | — |

### Pre-commit checks

```bash
uv run ruff format --check mc/ tests/mc/
uv run ruff check mc/ tests/mc/
uv run pyright mc/
```

## Ruff Rules

Enabled rule sets:

| Rule | Purpose |
|------|---------|
| `E` | pycodestyle errors |
| `F` | pyflakes |
| `I` | isort (import sorting) |
| `N` | pep8-naming |
| `W` | pycodestyle warnings |
| `UP` | pyupgrade — enforces modern syntax (`X \| None` over `Optional[X]`, etc.) |
| `B` | flake8-bugbear — catches mutable defaults, unreachable code, common bugs |
| `RUF` | Ruff-specific — unused `noqa`, mutable class vars, etc. |

Per-file ignores for tests:

```toml
[tool.ruff.lint.per-file-ignores]
"tests/**" = ["N803", "N806"]  # PascalCase mock names are idiomatic
```

Line length: **100** characters. Target: **Python 3.11+**.

## Type Checking (Pyright)

Pyright runs in **basic** mode. Configuration in `pyproject.toml`:

```toml
[tool.pyright]
pythonVersion = "3.11"
typeCheckingMode = "basic"
exclude = ["vendor/nanobot", "**/__pycache__"]
reportMissingImports = true
reportMissingTypeStubs = false
```

**Goals:**
- Catch actual type mismatches (wrong arg types, missing attributes, incompatible returns).
- Validate that `| None` is handled before use (narrowing).
- Flag unreachable code paths.

**Do NOT suppress pyright errors with `# type: ignore` unless the error is a false positive.** If pyright complains, fix the type. If fixing is not feasible, add `# pyright: ignore[ruleCode]` with a comment explaining why.

## Language & Style

- **All code in English** — variables, functions, classes, comments, docstrings, commit messages.
- **Line length**: 100 characters max.
- **Quotes**: double quotes (enforced by ruff formatter).
- **Trailing commas**: yes, in multi-line structures.

## Naming

| Element | Convention | Example |
|---------|-----------|---------|
| Functions, variables | `snake_case` | `get_active_agents` |
| Classes | `PascalCase` | `TaskExecutor` |
| Constants | `UPPER_SNAKE_CASE` | `LLM_TIMEOUT_SECONDS` |
| Private/internal | `_` prefix | `_parse_plan_response` |
| Exceptions | `PascalCase` + `Error` suffix | `LeadAgentExecutionError` |
| Modules, packages | `snake_case` | `task_lifecycle.py` |
| Protocols | `PascalCase`, descriptive | `MessageSender`, `TaskStore` |

## Imports

```python
from __future__ import annotations  # REQUIRED in every .py file (except __init__.py)

import stdlib_module                  # 1. stdlib
from stdlib import thing

import third_party                    # 2. third-party

from mc.domain import rule            # 3. project (absolute only, never relative)
from mc.bridge.client import Client

if TYPE_CHECKING:                     # 4. type-only imports (circular-dep safe)
    from mc.types import TaskData
```

- **Always absolute imports** — no relative imports (`from .foo` is not allowed).
- **`TYPE_CHECKING` blocks** for imports used only in annotations.
- **Import sorting** enforced by ruff `I` rules.
- **Lazy imports** in `__init__.py` via `_EXPORTS` + `__getattr__` for heavy packages.

## Type Hints

- **Required** on all public function signatures (args + return type).
- **Modern union syntax**: `str | None`, never `Optional[str]` or `Union[str, None]`.
- **`from __future__ import annotations`** in every module to enable deferred evaluation.
- **`-> None`** explicit on void functions.
- **Minimize `Any`**: prefer `TypedDict`, dataclasses, or protocol classes. `Any` is acceptable only at true boundary layers (e.g., Convex bridge receiving untyped dicts). Every `-> Any` return should have a comment explaining why it cannot be typed.
- **No `Union[]` or `Optional[]`**: use `X | Y` and `X | None`.

### Protocols for dependency inversion

Use `Protocol` classes to define interfaces at layer boundaries. This enables testing without mocks and enforces clean architecture:

```python
from typing import Protocol

class TaskStore(Protocol):
    async def get(self, task_id: str) -> TaskData | None: ...
    async def update_status(self, task_id: str, status: str) -> None: ...
```

Prefer protocols over abstract base classes (ABC) — they support structural subtyping.

### TypedDict for unstructured data

When receiving dicts from external sources (Convex, APIs), define `TypedDict` instead of using `dict[str, Any]`:

```python
class ConvexTaskDoc(TypedDict):
    _id: str
    title: str
    status: str
    assignedAgent: str | None
```

### Dataclasses for internal data

Use `@dataclass` for value objects and data transfer between layers:

```python
@dataclass(frozen=True)
class ExecutionResult:
    status: str
    output: str
    duration_ms: int
```

- Prefer `frozen=True` for immutable value objects.
- Use `field(default_factory=list)` for mutable defaults (never `= []`).
- Use `__post_init__` for validation, not business logic.

## Docstrings

Google style:

```python
def execute_task(task_id: str, *, force: bool = False) -> TaskResult:
    """Execute a task by ID.

    Transitions the task to running state, dispatches to the assigned agent,
    and returns the execution result.

    Args:
        task_id: The unique task identifier.
        force: Skip pre-condition checks if True.

    Returns:
        The execution result including output and final status.

    Raises:
        TaskNotFoundError: If no task exists with the given ID.
    """
```

- **Module docstrings**: required. One-liner describing purpose.
- **Class docstrings**: required on public classes.
- **Function docstrings**: required on public functions. One-liner is fine for simple helpers.
- **No docstrings needed** on private `_` prefixed helpers unless logic is non-obvious.

## Error Handling

- **Custom exceptions** inherit from `RuntimeError` or `Exception` with `Error` suffix.
- **Logging**: every module creates `logger = logging.getLogger(__name__)`.
- **Log format**: include a `[module]` prefix in messages (e.g., `[executor] Task failed`).
- **Use `logger.exception()`** inside `except` blocks for full tracebacks.
- **Use `logger.warning(..., exc_info=True)`** for non-critical failures.
- **Never catch `Exception` silently** — always log or re-raise.
- **Fail fast**: validate inputs at function entry, raise early, keep the happy path unindented.

```python
# CORRECT — fail fast
async def assign_agent(task_id: str, agent_id: str) -> None:
    task = await self.store.get(task_id)
    if task is None:
        raise TaskNotFoundError(task_id)

    agent = await self.registry.get(agent_id)
    if agent is None:
        raise AgentNotFoundError(agent_id)

    await self.store.assign(task, agent)

# WRONG — deeply nested
async def assign_agent(task_id: str, agent_id: str) -> None:
    task = await self.store.get(task_id)
    if task is not None:
        agent = await self.registry.get(agent_id)
        if agent is not None:
            await self.store.assign(task, agent)
```

## Async Patterns

This project is heavily async. Follow these rules:

- **All I/O functions must be `async`** — database calls, HTTP requests, file operations.
- **Never call `asyncio.run()` inside async code** — use `await` directly.
- **Use `asyncio.gather()`** for concurrent independent operations:
  ```python
  task, agent = await asyncio.gather(
      store.get_task(task_id),
      registry.get_agent(agent_id),
  )
  ```
- **Use `asyncio.TaskGroup`** (Python 3.11+) when you need structured concurrency with error propagation.
- **Timeouts**: always set timeouts on external calls. Use `asyncio.timeout()`:
  ```python
  async with asyncio.timeout(30):
      result = await provider.execute(prompt)
  ```
- **Never use `time.sleep()`** in async code — use `await asyncio.sleep()`.

## Module Structure

- **Max 500 lines per module** (soft limit). If a module exceeds this, consider splitting.
- **Layered architecture** — respect boundaries:
  - `mc/domain/` — pure rules, no I/O, no framework imports
  - `mc/contexts/` — business flows, orchestrate domain + infrastructure
  - `mc/infrastructure/` — environment/framework concerns, adapters
  - `mc/bridge/` — Convex-facing access, data translation
  - `mc/runtime/` — composition roots, dependency wiring
  - `mc/application/` — execution pipeline, entry points
- **Dependency rule**: layers only depend inward. `domain/` depends on nothing. `contexts/` depends on `domain/`. `infrastructure/` depends on `domain/`. `bridge/` and `runtime/` can depend on everything.
- **`__init__.py`**: use lazy `_EXPORTS` + `__getattr__` pattern for context packages. Simple packages can use direct imports.
- **`__all__`**: define in `__init__.py` to declare public API.
- **No re-export facades** for backward compatibility. If a symbol moved, update all callers.

## Testing

- **Test runner**: `uv run pytest`
- **Test files**: co-located with source (`mc/foo/bar.py` → `tests/mc/foo/test_bar.py`).
- **Mock naming**: PascalCase mocks are fine (`MockClient`, `MockLoop`) — suppressed via per-file-ignores.
- **Fixtures**: prefer `pytest` fixtures over manual setup/teardown.
- **Async tests**: use `pytest-asyncio` with `asyncio_mode = "auto"` (configured in `pyproject.toml`).
- **Test isolation**: each test must be independent. No shared mutable state between tests.
- **Arrange-Act-Assert**: structure test bodies clearly.

```python
async def test_task_transitions_to_running() -> None:
    # Arrange
    store = InMemoryTaskStore()
    task = await store.create(title="Test task")

    # Act
    result = await store.transition(task.id, to="running")

    # Assert
    assert result.status == "running"
    assert result.started_at is not None
```

- **Name tests descriptively**: `test_<what>_<condition>_<expected>` or `test_<behavior>`.
- **Never test implementation details** — test behavior and outcomes.
- **Architecture tests**: `tests/mc/test_architecture.py` enforces module boundaries — these must always pass.
