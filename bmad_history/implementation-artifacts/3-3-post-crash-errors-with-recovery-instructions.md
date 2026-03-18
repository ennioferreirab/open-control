# Story 3.3: Post Crash Errors with Recovery Instructions

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to see exactly what went wrong when an agent crashes with actionable recovery instructions,
So that I can fix the issue and retry.

## Acceptance Criteria

1. **Crash detected — step marked and structured error posted** — Given an agent subprocess crashes during step execution in `_execute_step`, when the exception is caught, then: (a) the step status is set to `"crashed"` in Convex via `bridge.update_step_status` (already happening), (b) a structured error message is posted to the unified thread via the `messages:postSystemError` Convex mutation with `role: "system"`, `type: "system_error"`, `stepId` linked, and human-readable `content` describing the error and a recovery action (FR31), and (c) an activity event is created: `"Agent {agentName} crashed on step: {stepTitle}"`.

2. **LLM provider error — actionable content** — Given the crash exception is identifiable as an LLM provider error (OAuth expiry, rate limit, timeout — detected by checking the exception type/message for provider-specific patterns), when the error message content is constructed, then the content includes the specific provider error and an actionable command such as `"Run: nanobot provider login --provider anthropic"` (NFR7). Provider patterns to detect: `AuthenticationError`, `RateLimitError`, `APITimeoutError`, `APIConnectionError`, `PermissionDeniedError` (from the `anthropic` SDK).

3. **Unknown exception — diagnostic content** — Given the crash exception is NOT a recognized LLM provider error, when the error message content is constructed, then the content includes the exception type and message (e.g., `"RuntimeError: <message>"`) and suggests checking agent logs: `"Check agent logs for details."`.

4. **Crash uses `postSystemError` Convex mutation** — Given a step crashes, when the error message is posted to the thread, then `bridge.post_system_error(task_id, content, step_id)` is called (NOT the current `bridge.send_message` with `MessageType.SYSTEM_EVENT`). This ensures the message lands with `type: "system_error"` and `stepId` linked for future thread rendering (Story 2.7 `ThreadMessage` already renders `system_error` type).

5. **Crash isolation — siblings and parent unaffected** — Given a step crashes, when the crash is fully processed, then: (a) sibling steps in the same parallel group continue running unaffected (already enforced by `asyncio.gather(..., return_exceptions=True)` in `_dispatch_parallel_group`) (FR32, NFR6), (b) only direct dependents of the crashed step remain `"blocked"` (no `checkAndUnblockDependents` call on crash — this is the correct existing behavior), (c) the parent task does NOT transition to `"failed"` or any terminal status — it stays `"running"`.

6. **Activity event — crash-specific description** — Given a step crashes, when the crash activity event is written, then `bridge.create_activity` is called with: `event_type: ActivityEventType.SYSTEM_ERROR`, `description: f"Agent {agent_name} crashed on step: {step_title}"`, `task_id`, `agent_name`. This replaces or supplements the generic dispatch-failure activity in `dispatch_steps`.

7. **Python tests** — New crash-handling behaviors are covered in `tests/mc/test_step_dispatcher.py`: (a) LLM provider error (e.g., `AuthenticationError`) produces content containing the provider name and `"nanobot provider login"`, (b) unknown exception produces content containing the exception type and `"Check agent logs"`, (c) `post_system_error` is called on crash (not `send_message`), (d) `create_activity` is called with `SYSTEM_ERROR` and the crash description on crash.

## Tasks / Subtasks

- [x] **Task 1: Add `post_system_error` bridge method** (AC: 4)
  - [x] 1.1 Add `post_system_error(self, task_id: str, content: str, step_id: str | None = None) -> Any` method to `ConvexBridge` in `nanobot/mc/bridge.py`. The method must call `self._mutation_with_retry("messages:postSystemError", args)` where `args` includes `task_id`, `content`, and optionally `step_id`. Follow the same pattern as `post_step_completion` (lines 313–348 in `bridge.py`).
  - [x] 1.2 Add `_log_state_transition("message", f"System error posted for task {task_id}")` inside `post_system_error`.

- [x] **Task 2: Implement `_build_crash_message` helper in `step_dispatcher.py`** (AC: 2, 3)
  - [x] 2.1 Add a module-level function `_build_crash_message(exc: Exception, agent_name: str, step_title: str) -> str` in `nanobot/mc/step_dispatcher.py`. This function is responsible for constructing the human-readable error content for the thread.
  - [x] 2.2 Detect LLM provider errors by checking `type(exc).__name__` against the set: `{"AuthenticationError", "PermissionDeniedError", "RateLimitError", "APITimeoutError", "APIConnectionError", "APIStatusError"}`. Also check for `"anthropic"` in the exception's module (`type(exc).__module__` or `str(exc)`) to avoid false positives from unrelated libraries with same class names.
  - [x] 2.3 For LLM provider errors, build content:
    ```
    Agent {agent_name} crashed on step "{step_title}" due to an LLM provider error.

    Error: {ExcType}: {exc}

    Recovery: Run `nanobot provider login --provider anthropic` to re-authenticate, then retry this step.
    ```
  - [x] 2.4 For unknown exceptions, build content:
    ```
    Agent {agent_name} crashed on step "{step_title}".

    Error: {ExcType}: {exc}

    Check agent logs for details, then retry this step.
    ```

- [x] **Task 3: Update `_execute_step` crash handler to use `post_system_error`** (AC: 1, 4, 5, 6)
  - [x] 3.1 In the `except Exception as exc` block of `_execute_step` (lines 408–446 in `step_dispatcher.py`), replace the current `bridge.send_message(... MessageType.SYSTEM_EVENT ...)` call with `bridge.post_system_error(task_id, content, step_id)` where `content` comes from `_build_crash_message(exc, agent_name, step_title)`.
  - [x] 3.2 Replace the existing generic crash activity call (or add if absent) with `bridge.create_activity(ActivityEventType.SYSTEM_ERROR, f"Agent {agent_name} crashed on step: {step_title}", task_id, agent_name)`.
  - [x] 3.3 Keep `bridge.update_step_status(step_id, StepStatus.CRASHED, error_message, StepStatus.RUNNING)` call in place (it already sets the `errorMessage` field on the step for the `StepCard` tooltip from Story 3.2). The `error_message` for the step record can remain as `f"{type(exc).__name__}: {exc}"` (short form for the card tooltip) while the thread message uses the richer `_build_crash_message` output.
  - [x] 3.4 Verify that the `re-raise` (`raise`) at the end of the `except` block is preserved — `_dispatch_parallel_group` needs the exception to be propagated so `asyncio.gather(return_exceptions=True)` captures it without crashing siblings (AC 5 crash isolation).

- [x] **Task 4: Write Python tests** (AC: 7)
  - [x] 4.1 In `tests/mc/test_step_dispatcher.py`, add a test: `"crash with AuthenticationError posts provider recovery instructions"` — mock `_run_step_agent` to raise a mock `AuthenticationError` (set `__name__` on the mock class), assert `bridge.post_system_error` was called with content containing `"nanobot provider login"` and `"anthropic"`.
  - [x] 4.2 Add test: `"crash with unknown exception posts diagnostic message"` — mock `_run_step_agent` to raise `RuntimeError("unexpected failure")`, assert `bridge.post_system_error` was called with content containing `"RuntimeError"` and `"Check agent logs"`.
  - [x] 4.3 Add test: `"crash does NOT call send_message"` — same setup as 4.2, assert `bridge.send_message` was NOT called (verifying migration away from the old pattern).
  - [x] 4.4 Add test: `"crash posts SYSTEM_ERROR activity with agent and step name"` — assert `bridge.create_activity` was called with `ActivityEventType.SYSTEM_ERROR` and a description containing the agent name and step title.
  - [x] 4.5 Add unit tests for `_build_crash_message` directly: one for each provider error class name, one for unknown exception — assert the output contains the required strings.

## Dev Notes

### Current Crash Handling Code Path

The entire crash handling logic lives in `_execute_step` in `nanobot/mc/step_dispatcher.py` (lines 408–446). The current flow:

1. **Mark step crashed** (lines 411–424): calls `bridge.update_step_status(step_id, StepStatus.CRASHED, error_message, StepStatus.RUNNING)` — this is correct and must be preserved.
2. **Post crash message to thread** (lines 426–444): calls `bridge.send_message(task_id, "System", AuthorType.SYSTEM, content, MessageType.SYSTEM_EVENT)` — **this is the gap**. The `send_message` bridge method calls `messages:create` (not `messages:postSystemError`), meaning the message is missing the `type: "system_error"` field and the `stepId` link. Story 3.3 replaces this call with `bridge.post_system_error`.
3. **Re-raise** (line 446): `raise` — this is critical for `asyncio.gather(return_exceptions=True)` crash isolation and must be preserved.

Current crash message content (line 433–437):
```python
f'Step "{step_title}" crashed:\n'
f"```\n{error_message}\n```\n"
f"Agent: {agent_name}"
```

This is not structured per the architecture spec (no recovery instructions, no actionable command). Story 3.3 replaces this with `_build_crash_message`.

### Bridge Method to Add: `post_system_error`

The Convex mutation `messages:postSystemError` already exists in `dashboard/convex/messages.ts` (lines 118–147) with this signature:
```typescript
args: {
  taskId: v.id("tasks"),
  content: v.string(),
  stepId: v.optional(v.id("steps")),
}
```

The bridge currently has NO `post_system_error` method. The new method in `nanobot/mc/bridge.py` must follow the same pattern as `post_step_completion` (lines 313–348):

```python
def post_system_error(
    self,
    task_id: str,
    content: str,
    step_id: str | None = None,
) -> Any:
    """Post a system-error message to the unified task thread.

    Calls messages:postSystemError Convex mutation. The message is stored
    with type: "system_error" and linked to the step via stepId.

    Args:
        task_id: Convex task _id.
        content: Human-readable error content with recovery instructions.
        step_id: Optional Convex step _id to link the error to a specific step.
    """
    args: dict[str, Any] = {
        "task_id": task_id,
        "content": content,
    }
    if step_id is not None:
        args["step_id"] = step_id
    result = self._mutation_with_retry("messages:postSystemError", args)
    self._log_state_transition(
        "message",
        f"System error posted for task {task_id}",
    )
    return result
```

### `_build_crash_message` — LLM Provider Error Detection

The Anthropic Python SDK raises these exception types (from `anthropic` package):
- `AuthenticationError` — OAuth expired, invalid API key
- `PermissionDeniedError` — insufficient permissions
- `RateLimitError` — rate limit exceeded
- `APITimeoutError` — request timed out
- `APIConnectionError` — network error
- `APIStatusError` — generic non-2xx response

Detection strategy: check `type(exc).__name__` against the set of known provider error names. To avoid false positives from other libraries, also check if `"anthropic"` appears in `type(exc).__module__`. A robust check:

```python
_LLM_PROVIDER_ERROR_NAMES = frozenset({
    "AuthenticationError",
    "PermissionDeniedError",
    "RateLimitError",
    "APITimeoutError",
    "APIConnectionError",
    "APIStatusError",
})

def _is_llm_provider_error(exc: Exception) -> bool:
    exc_type = type(exc)
    return (
        exc_type.__name__ in _LLM_PROVIDER_ERROR_NAMES
        and "anthropic" in exc_type.__module__
    )
```

This avoids importing `anthropic` directly (not always installed in MC module context — see project memory: `nanobot/agent/__init__.py` imports heavy deps). The check is string-based and safe to call at module level.

### Crash Isolation Guarantee (NFR6, FR32)

The isolation is already fully implemented via `asyncio.gather(*[...], return_exceptions=True)` in `_dispatch_parallel_group` (lines 265–268 of `step_dispatcher.py`). When `_execute_step` raises (via the `raise` at line 446), `gather` captures it as a return value rather than propagating it, so other concurrent `_execute_step` coroutines are unaffected. The loop at lines 270–276 logs each failure individually.

**Story 3.3 must NOT change this mechanism.** The `raise` at the end of the `except` block is load-bearing for isolation — keep it.

The parent task does not transition to `"failed"`: there is no `bridge.update_task_status(... "failed" ...)` call in the crash handler, and the architecture spec is explicit: `"the parent task does NOT transition to 'failed' — it stays 'running' (the user can still retry)"` [Source: _bmad-output/planning-artifacts/epics.md#Story 3.3, line 875].

### `ThreadMessage` Rendering (Story 2.7 compatibility)

The `postSystemError` mutation stores messages with `type: "system_error"`. The `ThreadMessage.tsx` component (completed in Story 2.7) already renders `system_error` type messages with special styling. By switching to `postSystemError`, crash messages will be properly rendered in the Thread tab with the system error visual treatment — no frontend changes required for this story.

### Activity Event Type for Crash

`ActivityEventType.SYSTEM_ERROR` = `"system_error"` already exists in `nanobot/mc/types.py` (line 101). The Convex `activities.eventType` union already accepts `"system_error"` in `dashboard/convex/schema.ts` (line 175). No schema changes needed.

The current crash handler in `_execute_step` does NOT emit any activity event on step crash (only the outer `dispatch_steps` catch emits a dispatch-failure message if the entire dispatch collapses). Story 3.3 adds the missing per-step crash activity event.

### Message Format — Architecture Alignment

From `_bmad-output/planning-artifacts/architecture.md`:
> "Step crashes post structured error messages to the unified thread with actionable recovery instructions." [line 320]
> "Step Crash Isolation Rule: A crashed step ONLY affects its direct dependents (they stay 'blocked'). Sibling steps in the same parallel group continue running. The parent task does NOT fail unless explicitly marked by the user or all steps are crashed." [line 617]

The architecture specifies `role: "system"`, `type: "system_error"` for crash messages [epics.md line 860]. The `postSystemError` mutation enforces both (`authorType: "system"` and `type: "system_error"` — lines 130, 133 of `messages.ts`).

### Running Tests

```bash
uv run pytest tests/mc/test_step_dispatcher.py -v
```

Full regression:
```bash
uv run pytest tests/mc/ -v
```

### Project Structure Notes

- **Files to modify:**
  - `nanobot/mc/bridge.py` — add `post_system_error` method (after `post_step_completion`, ~line 349)
  - `nanobot/mc/step_dispatcher.py` — add `_build_crash_message` helper, add `_LLM_PROVIDER_ERROR_NAMES` constant, update `_execute_step` crash handler to call `post_system_error` and emit crash activity event
  - `tests/mc/test_step_dispatcher.py` — add 5+ tests for new crash behavior

- **No new files** (tests extend existing file)
- **No Convex schema changes** — `messages:postSystemError` already exists, `"system_error"` is already in the activities union
- **No Convex mutation changes** — `messages:postSystemError` already has the correct signature
- **No frontend changes** — `ThreadMessage.tsx` already renders `system_error` type messages
- **No `nanobot/mc/types.py` changes** — `ActivityEventType.SYSTEM_ERROR`, `AuthorType.SYSTEM`, `MessageType.SYSTEM_EVENT`, `ThreadMessageType.SYSTEM_ERROR` are all already defined

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.3] — Acceptance criteria (lines 849–875)
- [Source: _bmad-output/planning-artifacts/architecture.md#Error Handling Pattern] — Step crash posts structured error message with actionable recovery; crash isolation rule (lines 609–617)
- [Source: _bmad-output/planning-artifacts/architecture.md#NFR6] — Crash isolation per step; subprocess boundaries (lines 63, 380, 617, 1026)
- [Source: _bmad-output/planning-artifacts/architecture.md#NFR7] — Graceful LLM provider error recovery with actionable messages (line 63)
- [Source: _bmad-output/planning-artifacts/architecture.md#FR31, FR32] — Step Lifecycle FR29-FR34 coverage (line 856)
- [Source: nanobot/mc/step_dispatcher.py#_execute_step] — Current crash handler (lines 408–446); `asyncio.gather` crash isolation (lines 265–268)
- [Source: nanobot/mc/bridge.py#post_step_completion] — Bridge method pattern to follow (lines 313–348)
- [Source: nanobot/mc/bridge.py#send_message] — Current (incorrect) crash message method being replaced (lines 276–311)
- [Source: nanobot/mc/types.py#ActivityEventType] — `SYSTEM_ERROR = "system_error"` (line 101); `AuthorType`, `MessageType`, `ThreadMessageType` (lines 109–130)
- [Source: dashboard/convex/messages.ts#postSystemError] — Convex mutation with `type: "system_error"` and `stepId` (lines 118–147)
- [Source: dashboard/convex/schema.ts#messages.type] — `"system_error"` is a valid literal in the `type` union (lines 109–115)
- [Source: _bmad-output/implementation-artifacts/3-1-implement-step-status-state-machine.md] — `update_step_status` with `current_status` validation now in place; crash transition is `running → crashed`
- [Source: _bmad-output/implementation-artifacts/3-2-visualize-blocked-and-crashed-steps.md] — `step.errorMessage` already rendered in `StepCard` tooltip; `post_system_error` provides the `stepId` link for thread rendering

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — implementation was straightforward. One pre-existing test failure in `test_gateway.py::TestExecutionLoop::test_pickup_task_reroutes_lead_agent` confirmed to pre-date this story (verified via git stash).

### Completion Notes List

- Added `post_system_error` to `ConvexBridge` following the `post_step_completion` pattern. Method calls `messages:postSystemError` Convex mutation (already existed) with optional `step_id` linking.
- Added `_LLM_PROVIDER_ERROR_NAMES`, `_is_llm_provider_error`, and `_build_crash_message` as module-level helpers in `step_dispatcher.py`. Provider detection is fully string-based (no anthropic import needed).
- Updated `_execute_step` crash handler: replaced `bridge.send_message(... MessageType.SYSTEM_EVENT ...)` with `bridge.post_system_error(task_id, crash_content, step_id)` and added `bridge.create_activity(ActivityEventType.SYSTEM_ERROR, ...)` call. The `raise` at the end is preserved for crash isolation.
- Updated pre-existing `nanobot/mc/test_step_dispatcher.py` crash test assertion to match new behavior (added `post_system_error` to mock bridge, updated `send_message.assert_any_call` to `post_system_error.assert_called`).
- New test file `tests/mc/test_step_dispatcher.py` contains 26 tests: 16 unit tests for `_build_crash_message` (parameterized over all 6 provider error names) and 10 integration tests for `_execute_step` crash handling. All pass.

### File List

- `nanobot/mc/bridge.py` — added `post_system_error` method (after `post_step_completion`)
- `nanobot/mc/step_dispatcher.py` — added `_LLM_PROVIDER_ERROR_NAMES`, `_is_llm_provider_error`, `_build_crash_message`; updated `_execute_step` crash handler
- `nanobot/mc/test_step_dispatcher.py` — updated crash test assertion; added `post_system_error` to mock bridge
- `tests/mc/test_step_dispatcher.py` — new file with 26 tests for crash-handling behaviors

## Review

### Reviewer

claude-sonnet-4-6 (adversarial code-review workflow)

### Findings

**FINDING 1 — HIGH — `_is_llm_provider_error` crashes with `None` module**
- File: `nanobot/mc/step_dispatcher.py`, `_is_llm_provider_error()`
- Issue: `"anthropic" in exc_type.__module__` raises `TypeError: argument of type 'NoneType' is not iterable` when `__module__` is `None`. This can happen with dynamically crafted exception classes (e.g., mock objects or C-extension exceptions where `__module__` is explicitly set to `None`). If any code in the wider agent runtime creates such an exception, the crash handler itself crashes — meaning the step's error is not posted to the thread.
- Fix applied: Changed to `"anthropic" in (exc_type.__module__ or "")`.

**FINDING 2 — MEDIUM — Deprecated `asyncio.get_event_loop()` causes cross-test event loop contamination**
- File: `tests/mc/test_step_dispatcher.py`, `TestExecuteStepCrashHandler._run()`
- Issue: The original implementation used `asyncio.get_event_loop().run_until_complete(coro)` which is deprecated in Python 3.10+ and raises `DeprecationWarning` on Python 3.13. The intermediate fix (`asyncio.run()`) caused a worse problem: `asyncio.run()` closes and removes the running event loop from the policy after completion, so subsequent tests in other modules that use `asyncio.get_event_loop()` raise `RuntimeError: There is no current event loop`. This was causing 10 tests in `nanobot/mc/test_gateway.py::TestAgentGatewayFirstCrash` and `TestAgentGatewaySecondCrash` to fail when the full suite was run together.
- Fix applied: Converted all 5 integration tests in `TestExecuteStepCrashHandler` to `async def` with `@pytest.mark.asyncio`. pytest-asyncio (configured in `asyncio_mode = "auto"`) manages the loop lifecycle correctly — each async test gets its own loop scope without polluting the global event loop policy. Removed the `_run()` helper and the unused `asyncio` import.

**FINDING 3 — LOW — Dead helper method `_make_dispatcher_with_crashing_agent`**
- File: `tests/mc/test_step_dispatcher.py`, `TestExecuteStepCrashHandler._make_dispatcher_with_crashing_agent()`
- Issue: The helper method is defined but never called. All 5 integration tests create their `bridge`/`dispatcher` inline. The dead code adds noise and misleads future readers into thinking there is a shared factory in use.
- Fix applied: Removed the dead method together with the `_run()` wrapper (Finding 2 fix).

### Test Results After Fixes

- `tests/mc/test_step_dispatcher.py`: 26/26 passed (0 warnings)
- Full suite (`tests/mc/` + `nanobot/mc/test_*.py`): 618 passed, 23 failed — identical pre-existing failure count to the baseline before story 3-3 (confirmed via `git stash`). Zero new regressions.

### AC Verification

1. AC1 — PASS: `_execute_step` catches, sets `StepStatus.CRASHED`, calls `post_system_error` with step-linked content, calls `create_activity(SYSTEM_ERROR, ...)`. All three actions wrapped in individual `try/except` to prevent secondary failures from masking the primary exception. `raise` preserved at the end.
2. AC2 — PASS: `_is_llm_provider_error` correctly identifies all 6 Anthropic SDK error class names. For provider errors, content contains `"nanobot provider login --provider anthropic"`. Verified by 12 parameterized unit tests.
3. AC3 — PASS: Unknown exceptions produce `"Error: {type}: {msg}\n\nCheck agent logs for details"`. Verified by 5 unit tests.
4. AC4 — PASS: `bridge.post_system_error(task_id, content, step_id)` is called (not `send_message`). Verified by dedicated `test_crash_does_not_call_send_message` test.
5. AC5 — PASS: `raise` at line 515 is preserved. `asyncio.gather(return_exceptions=True)` in `_dispatch_parallel_group` continues to capture it without cancelling siblings.
6. AC6 — PASS: `create_activity(ActivityEventType.SYSTEM_ERROR, f"Agent {agent_name} crashed on step: {step_title}", task_id, agent_name)` call added. Verified by `test_crash_posts_system_error_activity_with_agent_and_step`.
7. AC7 — PASS: All required test scenarios present: provider error recovery (4.1), unknown exception diagnostic (4.2), no `send_message` on crash (4.3), `SYSTEM_ERROR` activity with agent/step (4.4), `_build_crash_message` unit tests for all provider class names (4.5).
