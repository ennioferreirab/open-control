# Story 33.7: Fix Python Pyright Type Errors

Status: ready-for-dev

## Story

As a developer,
I want pyright type checking to pass on the Python codebase,
so that type mismatches are caught before runtime.

## Acceptance Criteria

1. `uv run pyright mc/` reports zero errors
2. No `# type: ignore` without a documented reason
3. No behavioral changes — only type annotation fixes

## Tasks / Subtasks

### Task 1: Fix `mc/bridge/facade_mixins.py` (105 errors) — STRUCTURAL

**Root cause**: `BridgeRepositoryFacadeMixin` references attributes (`_ensure_repos`, `_tasks`, `_steps`, `_messages`, `_agents`, `_boards`, `_chats`, `_specs`, `_subscriptions`, `_mutation_with_retry`, `_log_state_transition`) that only exist on the host class `ConvexBridge`. Pyright cannot know the mixin is always composed with `ConvexBridge`.

**Fix**: Declare stub attributes on the mixin class under `TYPE_CHECKING`:

```python
from __future__ import annotations
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from mc.bridge.repositories.tasks import TaskRepository
    from mc.bridge.repositories.steps import StepRepository
    from mc.bridge.repositories.messages import MessageRepository
    from mc.bridge.repositories.agents import AgentRepository
    from mc.bridge.repositories.boards import BoardRepository
    from mc.bridge.repositories.chats import ChatRepository
    from mc.bridge.repositories.specs import SpecsRepository
    from mc.bridge.subscription_manager import SubscriptionManager

class BridgeRepositoryFacadeMixin:
    # Declared for type checking — provided by ConvexBridge at runtime
    _tasks: TaskRepository
    _steps: StepRepository
    _messages: MessageRepository
    _agents: AgentRepository
    _boards: BoardRepository
    _chats: ChatRepository
    _specs: SpecsRepository
    _subscriptions: SubscriptionManager

    def _ensure_repos(self) -> None: ...
    def _mutation_with_retry(self, function_name: str, args: dict[str, Any] | None = None) -> Any: ...
    def _log_state_transition(self, entity_type: str, description: str) -> None: ...
```

Also delete duplicate `list_active_registry_view` at line 275-277 (if not already done in 33.6).

### Task 2: Fix `mc/bridge/__init__.py` (10 errors)

| Line | Error | Fix |
|------|-------|-----|
| 73-80 (8 errors) | `_BridgeClientAdapter` not assignable to `BridgeClient` | Create a `BridgeClientProtocol` with `query`, `mutation`, `subscribe`, `close`, `raw_client`. Type all repository constructors against this protocol instead of concrete `BridgeClient`. |
| 136 | `raise last_exception` where could be `None` | Add `assert last_exception is not None` before `raise` |
| 162 | `ConvexClient` has no attribute `close` | Use `getattr(self._client, "close", None)` pattern |

### Task 3: Fix `mc/bridge/client.py` (1 error) and `mc/bridge/retry.py` (1 error)

| File | Line | Fix |
|------|------|-----|
| `client.py:92` | `ConvexClient.close()` not in stubs | `close_fn = getattr(self._client, "close", None); if close_fn: close_fn()` |
| `retry.py:89` | `raise last_exception` could be `None` | `assert last_exception is not None` before `raise` |

### Task 4: Fix `mc/contexts/interactive/adapters/codex_app_server.py` (7 errors)

All are `reportOptionalMemberAccess` on `.get()` calls where pyright doesn't narrow ternary expressions.

**Fix pattern**: Extract variable before ternary:
```python
# BEFORE (pyright can't narrow)
turn = params.get("turn") if isinstance(params.get("turn"), dict) else {}

# AFTER
raw_turn = params.get("turn")
turn: dict[str, Any] = raw_turn if isinstance(raw_turn, dict) else {}
```

Apply to lines: 70, 71, 87, 88, 93, 95, 104.

### Task 5: Fix `mc/runtime/workers/inbox.py` (6 errors)

All are `Any | None` passed where `str` expected for `task_id`.

**Fix**: Add early guard in `process_task` around line 94:
```python
task_id = task_data.get("id")
if not isinstance(task_id, str):
    logger.warning("[inbox] Task missing 'id' field, skipping")
    return
```
This narrows `task_id` to `str` for the rest of the method. Fixes lines 162, 181, 208, 231, 245, 266.

### Task 6: Fix `mc/contexts/provider_cli/providers/nanobot.py` (5 errors) and `claude_code.py` (2 errors)

**Root cause**: subprocess output `chunk` is `bytes | str`. String operations fail because pyright sees potential `bytes`.

**Fix for nanobot.py** — force decode at line ~106:
```python
raw: str = chunk if isinstance(chunk, str) else chunk.decode("utf-8", errors="replace")
```
Fixes lines 115, 117, 119, 120, 127.

**Fix for claude_code.py** — same pattern at line ~70:
```python
text: str = chunk if isinstance(chunk, str) else chunk.decode("utf-8", errors="replace")
```
Fixes lines 78, 86.

### Task 7: Fix `mc/cli/agents.py` (5 errors)

| Line | Error | Fix |
|------|-------|-----|
| 299 | `parsed["name"]` where `parsed` could be `None` | `assert parsed is not None` |
| 311 | Same | Same |
| 316 | `feedback.strip()` where `feedback` could be `None` | `assert isinstance(feedback, str)` |
| 510 | `yaml.safe_load(yaml_text)` where `yaml_text` is `str \| None` | `assert yaml_text is not None` |
| 528 | `AgentPlan(..., yaml_text=yaml_text)` same | Same guard |

### Task 8: Fix `mc/application/execution/post_processing.py` (3 errors)

| Line | Error | Fix |
|------|-------|-----|
| 120 | `session_loop` is `None` in nested closure | `assert result.session_loop is not None` inside `_consolidate` |
| 213 | `memory_workspace` is `Path \| None` | `if result.memory_workspace is None: return` |
| 329 | Same | Same guard |

### Task 9: Fix remaining 18 files (1-3 errors each)

| File | Line | Error | Fix |
|------|------|-------|-----|
| `mc/contexts/interactive/types.py` | 56, 66, 75 | Protocol empty body return type | Add `# pyright: ignore[empty-body]` to each Protocol method |
| `mc/runtime/interactive_transport.py` | 60 | `set[str] = {}` creates dict | `self._pending_terminations: set[str] = set()` |
| `mc/runtime/interactive_transport.py` | 260 | `wait_for` arg type | `await asyncio.wait_for(wait_closed(), timeout=1)  # pyright: ignore[arg-type]` |
| `mc/runtime/nanobot_interactive_session.py` | 37, 38, 39 | `_Environ[str]` vs `dict[str, str]` | Change `_require_env` param to `Mapping[str, str]` |
| `mc/memory/index.py` | 180 (x2) | `lastrowid` is `int \| None` | `assert cur.lastrowid is not None` |
| `mc/memory/service.py` | 35 | `bridge` is `object` | Change param type to `ConvexBridge \| None` |
| `mc/contexts/execution/agent_runner.py` | 245 | Wrong return type | Change `-> tuple[str, str, AgentLoop]` to `-> tuple[AgentRunResult, str, AgentLoop]` |
| `mc/contexts/execution/cc_executor.py` | 292 | Mixin missing `_handle_provider_error` | Declare as stub method on mixin (same pattern as Task 1) |
| `mc/contexts/execution/executor.py` | 592 | `SimpleNamespace` vs `CCTaskResult` | Use `CCTaskResult(...)` directly |
| `mc/contexts/execution/step_dispatcher.py` | 494 | `str \| None` vs `str` | `task_description=execution_description or ""` |
| `mc/contexts/interactive/supervisor.py` | 84 | `session_id` is `str \| None` | `merged_event.session_id or ""` |
| `mc/contexts/planning/negotiation.py` | 686 | `Any` from bridge query | `messages = cast(list[dict[str, Any]], messages)` |
| `mc/contexts/planning/planner.py` | 330 | `self._bridge` is `object` | Type as `ConvexBridge \| None` |
| `mc/infrastructure/agent_bootstrap.py` | 623 | `spec` is `ModuleSpec \| None` | `if spec is None: raise ImportError(...)` |
| `mc/cli/process_manager.py` | 373 | `except TimeoutError` unreachable (subclass of OSError) | Reorder: `except TimeoutError` before `except OSError` |
| `mc/application/execution/strategies/provider_cli.py` | 279 | `dict` invariance | Change param to `Mapping[str, str \| None]` |
| `mc/application/execution/thread_journal_service.py` | 171 | `list[str \| None]` vs `list[str]` | Walrus operator: `[mid for msg in batch if (mid := self._message_id(msg)) is not None]` |

### Task 10: Verify

- `uv run pyright mc/` — zero errors
