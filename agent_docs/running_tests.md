# Running & Writing Tests

This document defines **when to test**, **what to test**, and the **testing pipeline**. For framework-specific patterns (pytest, vitest, mocking), see the code conventions docs.

> **Rule of thumb**: a test earns its place by catching a real regression. If it can't break when behavior breaks, it's noise.

---

## Decision: Should I Write a Test?

```text
                  ┌─────────────────────────┐
                  │  Is the code a pure      │
                  │  function / state machine │
                  │  / business rule?         │
                  └────────┬────────────────┘
                           │
                     yes ──┤── no
                           │       │
                    ┌──────▼──┐   ┌▼──────────────────────┐
                    │ TEST IT  │   │ Does it orchestrate   │
                    │ (unit)   │   │ multiple services or  │
                    └──────────┘   │ cross a boundary?     │
                                   └────────┬──────────────┘
                                            │
                                      yes ──┤── no
                                            │       │
                                     ┌──────▼──┐   ┌▼─────────────────────┐
                                     │ TEST IT  │   │ Is it glue code /   │
                                     │ (integ.) │   │ delegation / wiring? │
                                     └──────────┘   └────────┬────────────┘
                                                             │
                                                       yes ──┤── no
                                                             │       │
                                                      ┌──────▼─────┐ │
                                                      │ SKIP TEST  │ │
                                                      │ (glue)     │ │
                                                      └────────────┘ │
                                                                     ▼
                                                              evaluate
                                                              case by case
```

### Always Test

| Category | Why | Example |
|----------|-----|---------|
| **Pure functions** | Deterministic, fast, high ROI | `_human_size()`, `parse_mention()`, `buildFilter()` |
| **State machines / transitions** | Bugs here cascade — wrong state = wrong behavior everywhere | `stepTransitions`, `task lifecycle`, `workflowContract` |
| **Business rules** | Encode domain knowledge that isn't obvious from reading code | Review criteria, agent selection logic, permission checks |
| **Boundary contracts** | Catch drift between services before it hits production | Python↔Convex naming, IPC message shapes, API response parsing |
| **Regression bugs** | Once bitten, twice shy — a test locks the fix in place | Any bug that escaped to production or was hard to debug |

### Never Test

| Category | Why | Example |
|----------|-----|---------|
| **Glue / delegation** | Tests just mirror the implementation — break when you refactor, not when behavior breaks | A function that calls `bridge.send(x)` and returns the result |
| **Framework wiring** | You're testing the framework, not your code | "Does Next.js route to this page?", "Does pytest discover this file?" |
| **Trivial getters/setters** | Zero logic = zero risk | `@property def name(self): return self._name` |
| **1:1 mock mirrors** | If the test is identical to the implementation but with mocks, it proves nothing | Mocking every dependency of a function then asserting it called them in order |
| **UI layout details** | Brittle — breaks on every CSS change, catches nothing meaningful | "Button is 32px tall", "margin is 8px" |

### Case-by-Case

| Situation | Test if... | Skip if... |
|-----------|-----------|------------|
| API endpoint handler | Has validation, transformation, or error-handling logic | Just delegates to a service |
| React component | Has conditional rendering, user interaction logic | Is purely presentational (props → JSX) |
| Worker/cron job | Has retry logic, error recovery, state transitions | Just invokes a service method |
| Config / env parsing | Has fallbacks, defaults, or validation | Just reads and passes through |

---

## Testing Pipeline

When implementing a feature or fix, follow this sequence:

### 1. Identify Testable Units

Before writing code, ask: **"Where is the logic?"** The logic is what needs tests. Wiring does not.

```text
Feature: "Auto-title tasks based on description"

Logic (test these):
  - Title generation algorithm (pure function)
  - "Should auto-title?" decision (business rule)
  - State transition: untitled → titled (state machine)

Wiring (skip these):
  - Convex mutation that calls the title generator
  - Worker that triggers on new tasks
  - Dashboard component that displays the title
```

### 2. Write Tests First (for logic)

For pure functions and business rules, TDD is the fastest path:

```python
# Write this BEFORE implementing generate_title()
def test_generates_title_from_first_sentence():
    assert generate_title("Fix the login bug. Users can't sign in.") == "Fix the login bug"

def test_truncates_long_titles():
    assert len(generate_title("A" * 200)) <= 80

def test_returns_fallback_for_empty_description():
    assert generate_title("") == "Untitled task"
```

### 3. Write Integration Tests (for boundaries)

After the units work, test how they connect:

```python
async def test_auto_title_skips_tasks_with_manual_title():
    """Integration: the worker respects the business rule."""
    task = make_task(title="My custom title", description="Something else")
    result = await process_new_task(task)
    assert result.title == "My custom title"  # not overwritten
```

### 4. Skip Tests for Glue

The Convex mutation that saves the title? The React hook that fetches it? Don't test these. If the units and integration tests pass, the glue works.

---

## Running Tests

### Commands

| Scope | Command |
|-------|---------|
| All Python | `uv run pytest` |
| Specific Python file | `uv run pytest tests/mc/test_executor.py` |
| Specific Python test | `uv run pytest tests/mc/test_executor.py::TestHumanSize::test_bytes_below_mb` |
| All TypeScript | `cd dashboard && npm run test` |
| Specific TS file | `cd dashboard && npx vitest run path/to/file.test.ts` |
| Architecture only | `cd dashboard && npm run test:architecture` |
| E2E | `cd dashboard && npm run test:e2e` |

### When to Run

| Moment | What to run |
|--------|-------------|
| During development | Only the tests you're touching |
| Before committing | All tests in the affected layer (Python OR TypeScript) |
| Before merging | Full suite: `uv run pytest && cd dashboard && npm run test` |
| Architecture tests | Always — these gate the PR |

---

## Test Quality Checklist

Before submitting a test, verify:

- [ ] **Does it test behavior, not implementation?** Could the implementation change without breaking the test?
- [ ] **Does it have a clear failure message?** When it fails, can you understand what broke without reading the test code?
- [ ] **Is it independent?** Can it run in any order, in isolation?
- [ ] **Is it fast?** Unit tests should run in milliseconds. If it needs sleep/polling, it's probably an integration test.
- [ ] **Does it cover a real scenario?** Not a made-up edge case that can't happen in practice.
- [ ] **Would you notice if it was deleted?** If no — delete it.

---

## Anti-Patterns (banned)

These patterns were found and removed during the 2026-03-17 audit. **Do not reintroduce them.**

### 1. Mock Mirror
Mocks every dependency, then asserts `.assert_called_once_with(...)`. The test is a copy of the implementation with extra steps. If the implementation changes, the test breaks — but not because behavior broke.

```python
# BAD — proves nothing
def test_handle_mention_dispatches_to_handler(self):
    with patch("mc.services.conversation.handle_all_mentions") as mock:
        svc.handle_message(msg)
        mock.assert_called_once_with(bridge, task_id, content)
```

**Fix:** test the *outcome* of the dispatch, not that it was dispatched.

### 2. Constructor / Attribute Check
Tests that `self._bridge is bridge` after construction. If the constructor is broken, every other test in the file will fail anyway.

```python
# BAD — trivial, zero value
def test_init(self):
    assert watcher._bridge is bridge
    assert watcher._registry is registry
```

**Fix:** delete. Constructor bugs surface through behavioral tests.

### 3. Purely Presentational Component Test
Renders a component and asserts a CSS class or that props appear in the DOM. Breaks on every style change, catches no logic bugs.

```typescript
// BAD — breaks when you change the color, catches nothing
it("renders agent message with white background", () => {
  render(<ThreadMessage authorType="agent" />);
  expect(container.firstChild).toHaveClass("bg-white");
});
```

**Fix:** only test components that have conditional rendering, user interaction, or data transformation logic.

### 4. Duplicate Across Files
The same intent classification test appears in `test_conversation.py` AND `test_conversation_gateway_integration.py`. When both pass, you learn nothing extra. When one fails, you fix it twice.

**Fix:** test each behavior in exactly one file. Integration test files should only test what's unique to the integration (wiring, handoff, cross-service contract).

### 5. Source Code Grep as Test
Reads a `.ts` or `.py` file and uses regex/string search to verify code patterns. This is an architecture test, not a unit test — and it belongs in `tests/mc/test_architecture.py` or `tests/architecture.test.ts`.

```python
# BAD — breaks on any refactor, tests nothing behavioral
def test_soft_delete_rejects_system_agent(self):
    source = Path("dashboard/convex/agents.ts").read_text()
    assert "isSystem" in source
```

**Fix:** move to architecture tests, or delete if the architecture tests already cover it.

### 6. `Array.isArray` as Only Assertion
A query test that only checks the return is an array, not what's in it.

```typescript
// BAD — Array.isArray is always true for any list query
it("returns all specs", async () => {
  const result = await handler(ctx, {});
  expect(Array.isArray(result)).toBe(true);
});
```

**Fix:** assert on the content — length, specific fields, filter behavior.

### 7. Tautological String Check
Constructs a string and asserts it equals the same construction.

```python
# BAD — proves Python string concatenation works
def test_session_key_format_with_board(self):
    key = f"{agent}:{board}"
    assert key == f"{agent}:{board}"
```

**Fix:** test the *consumer* of the key, not the key format itself.
