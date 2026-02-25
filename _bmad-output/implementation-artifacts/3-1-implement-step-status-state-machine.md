# Story 3.1: Implement Step Status State Machine

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want step status transitions to follow a defined state machine,
So that steps never enter invalid states and the UI can reliably reflect their lifecycle.

## Acceptance Criteria

1. **Convex transition validation enforced** — Given the step lifecycle is defined as `planned → assigned → running → completed | crashed`, and `blocked` as a parallel state, when a step status update is requested via the `steps:updateStatus` Convex mutation, then the mutation validates that the transition is legal (e.g., `assigned → running` is valid, `completed → assigned` is invalid unless retrying via `crashed → assigned`), and illegal transitions are rejected with a `ConvexError` containing a clear human-readable message.

2. **Activity event created on every transition** — Given a step transitions to any new status, when the mutation completes, then a corresponding activity event is written to the `activities` table with: `taskId`, `agentName` (from `step.assignedAgent`), `eventType: "step_status_changed"`, a human-readable `description` naming the previous and next status and the step title, and `timestamp` (ISO 8601) (FR29).

3. **Python state machine mirrors Convex** — Given the `state_machine.py` module in the Python backend currently validates task-level transitions only, when it is extended for step-level states, then `StepStateMachine` (or equivalent functions) validates step transitions identically to the Convex-side `STEP_TRANSITIONS` table, and Python and Convex agree on all valid transitions — no drift between the two systems.

4. **Illegal transition rejected from Python side** — Given the Python bridge calls `update_step_status` with an invalid transition (e.g., `completed → running`), when `validate_step_transition` is called before the bridge mutation, then a `ValueError` is raised with a clear message, and the bridge mutation is NOT called.

5. **Step-to-activity event type mapping** — Given a step transition maps to a semantic event, when the Python state machine emits an event type, then it uses the correct `ActivityEventType` constant: `STEP_STARTED` for `assigned → running`, `STEP_COMPLETED` for `running → completed`, and `STEP_DISPATCHED` for `planned → assigned` or `blocked → assigned`.

## Tasks / Subtasks

- [x] **Task 1: Extend `state_machine.py` with step-level state machine** (AC: 3, 4, 5)
  - [x] 1.1 Add `STEP_VALID_TRANSITIONS: dict[str, list[str]]` mirroring exactly the `STEP_TRANSITIONS` table in `dashboard/convex/steps.ts`: `planned → [assigned, blocked]`, `assigned → [running, completed, crashed, blocked]`, `running → [completed, crashed]`, `completed → []`, `crashed → [assigned]`, `blocked → [assigned, crashed]`
  - [x] 1.2 Add `STEP_TRANSITION_EVENT_MAP: dict[tuple[str, str], str]` mapping transitions to `ActivityEventType` values: `(planned, assigned) → STEP_DISPATCHED`, `(blocked, assigned) → STEP_DISPATCHED`, `(assigned, running) → STEP_STARTED`, `(running, completed) → STEP_COMPLETED`, `(running, crashed) → STEP_COMPLETED` (use `SYSTEM_ERROR` or a new `STEP_CRASHED` if needed — see Dev Notes), `(crashed, assigned) → STEP_DISPATCHED` (retry)
  - [x] 1.3 Add `is_valid_step_transition(current_status: str, new_status: str) -> bool` — analogous to the existing `is_valid_transition` for tasks
  - [x] 1.4 Add `validate_step_transition(current_status: str, new_status: str) -> None` — raises `ValueError` with message `"Cannot transition step from '{current}' to '{new}'"` if invalid
  - [x] 1.5 Add `get_step_event_type(current_status: str, new_status: str) -> str` — returns the `ActivityEventType` string for a given step transition, raises `ValueError` if no mapping exists

- [x] **Task 2: Write Python unit tests for the step state machine** (AC: 3, 4, 5)
  - [x] 2.1 Create `tests/mc/test_step_state_machine.py` with tests covering: all valid transitions return `True` from `is_valid_step_transition`, all invalid transitions return `False`, `validate_step_transition` raises `ValueError` for illegal transitions, `get_step_event_type` returns correct `ActivityEventType` for each mapping, `get_step_event_type` raises `ValueError` for unmapped transitions
  - [x] 2.2 Add a parity test that asserts the Python `STEP_VALID_TRANSITIONS` keys and values match the expected set — to serve as a guard against future drift with the Convex side

- [x] **Task 3: Verify and harden `steps:updateStatus` Convex mutation** (AC: 1, 2)
  - [x] 3.1 Read the current `updateStatus` mutation in `dashboard/convex/steps.ts` — confirm `isValidStepTransition` is already called before patching; if so, document as verified. If not, add the call.
  - [x] 3.2 Verify the `logStepStatusChange` call inside `updateStatus` writes the correct `eventType: "step_status_changed"` and includes `taskId`, `agentName`, `description`, and `timestamp` — the description must name both previous and next status and the step title
  - [x] 3.3 Verify `updateStatus` sets `startedAt` when transitioning to `running` and `completedAt` when transitioning to `completed`; confirm `errorMessage` is set on `crashed` and cleared on all other transitions — add the clearing patch if missing
  - [x] 3.4 Add a dedicated `eventType: "step_crashed"` activity event when `status === "crashed"` (in addition to the generic `step_status_changed` event) — this is required by AC2/FR29 and will be consumed by Story 3.5's activity feed

- [x] **Task 4: Write TypeScript unit tests for `steps.ts` state machine functions** (AC: 1, 2)
  - [x] 4.1 In `dashboard/convex/steps.test.ts` (already exists — extend it), add a `describe("isValidStepTransition — full matrix")` block that exhaustively tests every valid transition listed in `STEP_TRANSITIONS` returns `true`, and a representative set of invalid transitions returns `false`
  - [x] 4.2 Add a test for `updateStatus` handler that verifies: a `ConvexError` is thrown for an invalid transition; the `activities` table receives a `step_status_changed` event on a valid transition; `startedAt` is set when transitioning to `running`; `errorMessage` is cleared when transitioning away from `crashed`

- [x] **Task 5: Integrate step transition validation into the Python bridge** (AC: 4)
  - [x] 5.1 In `nanobot/mc/bridge.py`, in the `update_step_status` method, add a pre-flight call to `validate_step_transition(current_status, new_status)` before `_mutation_with_retry` — this requires knowing the current status; update the bridge method signature to accept `current_status: str` as a required parameter
  - [x] 5.2 Update all callers of `bridge.update_step_status` in `step_dispatcher.py` and `executor.py` to pass the current status when known; where the current status is not tracked locally, document that Convex-side validation is sufficient and Python pre-flight is skipped
  - [x] 5.3 Ensure the `validate_step_transition` import in `bridge.py` uses a direct import from `nanobot.mc.state_machine` (not from `nanobot.agent`) to avoid heavy-dependency import chains

## Dev Notes

### Current State of the Codebase

**This story is primarily about hardening and extending existing partial implementations.** The Convex mutation `steps:updateStatus` already exists and already calls `isValidStepTransition`. The `STEP_TRANSITIONS` table is already defined in `dashboard/convex/steps.ts`. The Python `state_machine.py` module exists but only covers task-level transitions. The gaps are:

1. Python has no step-level state machine — `state_machine.py` is task-only
2. Convex mutation does NOT yet emit a `step_crashed` activity event (only the generic `step_status_changed`)
3. The Python bridge's `update_step_status` method has no pre-flight validation

### Exact Transition Table (Source of Truth)

The Convex `STEP_TRANSITIONS` in `dashboard/convex/steps.ts` (lines 27–34) is the authoritative definition:

```typescript
const STEP_TRANSITIONS: Record<StepStatus, StepStatus[]> = {
  planned: ["assigned", "blocked"],
  assigned: ["running", "completed", "crashed", "blocked"],
  running: ["completed", "crashed"],
  completed: [],
  crashed: ["assigned"],
  blocked: ["assigned", "crashed"],
};
```

The Python `STEP_VALID_TRANSITIONS` dict in `state_machine.py` MUST match this exactly. The parity test in Task 2.2 will enforce this at the CI level.

**Note on `planned` status:** The architecture spec lists step statuses as `"planned" | "assigned" | "running" | "completed" | "crashed" | "blocked"`. However, looking at the current implementation in `steps.ts`, `planned` appears in `STEP_TRANSITIONS` but `resolveInitialStepStatus` only ever produces `assigned` or `blocked` — never `planned`. The `planned` status is a pre-materialization placeholder that currently maps forward to `assigned` or `blocked`. Do not remove `planned` from the transition table — it is architecturally present for future pre-kickoff plan editing (Epic 4).

### Python State Machine — File to Modify

File: `/Users/ennio/Documents/nanobot-ennio/nanobot/mc/state_machine.py`

The current module (67 lines) covers ONLY task transitions. The extension should add step-level functions below the existing task functions without modifying the existing task logic. Suggested structure:

```python
# ── Step State Machine ────────────────────────────────────────────────────────

STEP_VALID_TRANSITIONS: dict[str, list[str]] = {
    StepStatus.PLANNED: [StepStatus.ASSIGNED, StepStatus.BLOCKED],
    StepStatus.ASSIGNED: [StepStatus.RUNNING, StepStatus.COMPLETED, StepStatus.CRASHED, StepStatus.BLOCKED],
    StepStatus.RUNNING: [StepStatus.COMPLETED, StepStatus.CRASHED],
    StepStatus.COMPLETED: [],
    StepStatus.CRASHED: [StepStatus.ASSIGNED],
    StepStatus.BLOCKED: [StepStatus.ASSIGNED, StepStatus.CRASHED],
}

STEP_TRANSITION_EVENT_MAP: dict[tuple[str, str], str] = {
    (StepStatus.PLANNED, StepStatus.ASSIGNED): ActivityEventType.STEP_DISPATCHED,
    (StepStatus.BLOCKED, StepStatus.ASSIGNED): ActivityEventType.STEP_DISPATCHED,
    (StepStatus.ASSIGNED, StepStatus.RUNNING): ActivityEventType.STEP_STARTED,
    (StepStatus.RUNNING, StepStatus.COMPLETED): ActivityEventType.STEP_COMPLETED,
    (StepStatus.CRASHED, StepStatus.ASSIGNED): ActivityEventType.STEP_DISPATCHED,
    # running -> crashed has no clean semantic in current ActivityEventType;
    # use SYSTEM_ERROR as the closest available value (see Dev Notes)
    (StepStatus.RUNNING, StepStatus.CRASHED): ActivityEventType.SYSTEM_ERROR,
    (StepStatus.ASSIGNED, StepStatus.CRASHED): ActivityEventType.SYSTEM_ERROR,
}


def is_valid_step_transition(current_status: str, new_status: str) -> bool:
    """Check if a step state transition is valid."""
    allowed = STEP_VALID_TRANSITIONS.get(current_status, [])
    return new_status in allowed


def validate_step_transition(current_status: str, new_status: str) -> None:
    """Validate a step state transition. Raises ValueError if invalid."""
    if not is_valid_step_transition(current_status, new_status):
        raise ValueError(
            f"Cannot transition step from '{current_status}' to '{new_status}'"
        )


def get_step_event_type(current_status: str, new_status: str) -> str:
    """Get the activity event type for a step transition."""
    event_type = STEP_TRANSITION_EVENT_MAP.get((current_status, new_status))
    if event_type is None:
        raise ValueError(
            f"No event type mapping for step transition '{current_status}' -> '{new_status}'"
        )
    return event_type
```

**Import note:** `StepStatus` and `ActivityEventType` are already imported from `nanobot.mc.types` at the top of `state_machine.py` — add `StepStatus` to the existing import line.

### Activity Event Types — Existing vs. Missing

From `nanobot/mc/types.py` (lines 75–107), these step-related `ActivityEventType` values already exist:

| Constant | String value | Appropriate use |
|----------|-------------|-----------------|
| `STEP_DISPATCHED` | `"step_dispatched"` | `planned → assigned`, `blocked → assigned`, `crashed → assigned` (retry) |
| `STEP_STARTED` | `"step_started"` | `assigned → running` |
| `STEP_COMPLETED` | `"step_completed"` | `running → completed` |
| `SYSTEM_ERROR` | `"system_error"` | `running → crashed`, `assigned → crashed` (no dedicated `STEP_CRASHED` exists) |

There is **no `STEP_CRASHED`** constant in `ActivityEventType`. Do NOT add a new enum value to `ActivityEventType` in this story — that would require a Convex schema change for the `activities` table's `eventType` union. Instead, use `SYSTEM_ERROR` for crash transitions in the Python event map. The Convex side uses the generic `"step_status_changed"` eventType for all step status changes (from `logStepStatusChange`). Task 3.4 adds a dedicated `"step_crashed"` event on the Convex side — but this requires verifying the Convex `activities` schema allows this string value (check `dashboard/convex/schema.ts`).

**Action required in Task 3.4:** Before adding `"step_crashed"` as a Convex eventType, check `dashboard/convex/schema.ts` to see if `eventType` is a union literal or a free string. If it is a union literal, you must add `"step_crashed"` to the union. If it is `v.string()`, you can use it directly.

### Convex `updateStatus` — Current Implementation

File: `/Users/ennio/Documents/nanobot-ennio/dashboard/convex/steps.ts`

The mutation at lines 349–401 already:
- Validates `isValidStepStatus` (line 361)
- Validates `isValidStepTransition` (line 367) — throws `ConvexError` on failure (AC1 is ALREADY DONE)
- Sets `startedAt` on transition to `running` (line 378)
- Sets `completedAt` on transition to `completed` (line 381)
- Sets `errorMessage` on crash (line 384) and clears it on other transitions (line 386)
- Calls `logStepStatusChange` which writes `eventType: "step_status_changed"` (lines 150–168)

**What's missing:** A dedicated `"step_crashed"` activity event (Task 3.4). The generic `step_status_changed` event is sufficient for AC2, but Story 3.5 (activity feed) will need crash-specific events for visual differentiation. Adding it now keeps the architecture clean.

**AC1 verification:** Confirmed — `isValidStepTransition` IS called in `updateStatus`. Task 3.1 is verification/documentation, not implementation.

### Python Bridge — `update_step_status` Method

File: `/Users/ennio/Documents/nanobot-ennio/nanobot/mc/bridge.py` (lines 444–459)

Current signature:
```python
def update_step_status(
    self,
    step_id: str,
    status: str,
    error_message: str | None = None,
) -> Any:
```

For Task 5.1, add `current_status: str | None = None` as an optional parameter (not required — Convex-side validation is the safety net; Python pre-flight is defense-in-depth). Only validate when `current_status` is provided:

```python
def update_step_status(
    self,
    step_id: str,
    status: str,
    error_message: str | None = None,
    current_status: str | None = None,
) -> Any:
    if current_status is not None:
        from nanobot.mc.state_machine import validate_step_transition
        validate_step_transition(current_status, status)
    # ... rest of existing implementation
```

This avoids a breaking change for all existing callers while enabling pre-flight validation where the caller knows the current status.

### Callers of `bridge.update_step_status`

From grep results, callers exist in:
- `nanobot/mc/step_dispatcher.py` — this module tracks step states during dispatch; it CAN pass `current_status`
- `nanobot/mc/executor.py` — the step executor; it transitions steps from `assigned → running` and `running → completed/crashed`; it CAN pass `current_status`

Both files should be updated to pass `current_status` for defense-in-depth. The change is additive (keyword argument with default).

### Testing Patterns to Follow

**Python tests:** Follow the pattern from `tests/mc/test_plan_materializer.py` — use `unittest.mock.MagicMock` for bridge, `pytest` fixtures, descriptive function names like `test_valid_transition_returns_true`. Run with `uv run pytest tests/mc/test_step_state_machine.py -v`.

**TypeScript tests:** Extend `dashboard/convex/steps.test.ts` (already exists, 211 lines). Follow the existing `describe/it/expect` pattern. The `updateStatus` handler test must use the `._handler` accessor pattern (see `describe("batchCreate")` block at lines 115–210 for the exact pattern). Run with `cd dashboard && npx vitest run convex/steps.test.ts`.

### Parity Test Rationale

The parity test (Task 2.2) is the most important test in this story. Without it, Python and Convex state machines will inevitably drift as the codebase evolves. The test should hard-code the expected transition table as a dictionary literal and assert that `STEP_VALID_TRANSITIONS` equals it. This makes any future change to either side explicit and intentional.

```python
def test_step_valid_transitions_match_convex_spec() -> None:
    """Guard against Python/Convex state machine drift."""
    expected = {
        "planned": ["assigned", "blocked"],
        "assigned": ["running", "completed", "crashed", "blocked"],
        "running": ["completed", "crashed"],
        "completed": [],
        "crashed": ["assigned"],
        "blocked": ["assigned", "crashed"],
    }
    # Compare as sets to ignore list ordering
    for state, allowed in expected.items():
        assert set(STEP_VALID_TRANSITIONS[state]) == set(allowed), (
            f"Mismatch for state '{state}': "
            f"expected {set(allowed)}, got {set(STEP_VALID_TRANSITIONS[state])}"
        )
    assert set(STEP_VALID_TRANSITIONS.keys()) == set(expected.keys())
```

### No Frontend Changes Required

This story is entirely backend (Python + Convex mutations + tests). No React components, no Convex queries, no dashboard UI changes. The frontend already handles all step statuses — `StepCard.tsx` renders `crashed`, `blocked`, `running`, etc. visually (that hardening happens in Story 3.2).

### Project Structure Notes

- **Files to modify:**
  - `nanobot/mc/state_machine.py` — add step-level state machine functions
  - `dashboard/convex/steps.ts` — verify/harden `updateStatus` mutation, add `step_crashed` activity event in Task 3.4
  - `dashboard/convex/steps.test.ts` — extend with additional transition matrix tests and `updateStatus` handler tests
  - `nanobot/mc/bridge.py` — add optional `current_status` parameter to `update_step_status`
  - `nanobot/mc/step_dispatcher.py` — pass `current_status` when calling `update_step_status`
  - `nanobot/mc/executor.py` — pass `current_status` when calling `update_step_status`
- **New file:**
  - `tests/mc/test_step_state_machine.py` — Python unit tests for step state machine functions
- **No schema changes** — unless `activities.eventType` must be extended for `"step_crashed"` (verify in Task 3.4)
- **No new Convex functions** — `updateStatus` already exists; this story hardens it

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.1] — Acceptance criteria for step state machine story
- [Source: _bmad-output/planning-artifacts/architecture.md#Step Status Values] — `type StepStatus = "planned" | "assigned" | "running" | "completed" | "crashed" | "blocked"`
- [Source: _bmad-output/planning-artifacts/architecture.md#Convex Mutation Pattern] — `updateStepStatus` pattern with activity event requirement
- [Source: _bmad-output/planning-artifacts/architecture.md#Step Crash Isolation Rule] — crash does not cascade to siblings or parent task
- [Source: _bmad-output/planning-artifacts/architecture.md#Communication Patterns] — "Every mutation that modifies step or task state MUST also write a corresponding activity event"
- [Source: dashboard/convex/steps.ts#STEP_TRANSITIONS] — Authoritative TypeScript transition table (lines 27–34)
- [Source: dashboard/convex/steps.ts#updateStatus] — Existing mutation with transition validation (lines 349–401)
- [Source: dashboard/convex/steps.test.ts] — Existing test file to extend (211 lines)
- [Source: nanobot/mc/state_machine.py] — Task-level state machine to extend with step-level functions (67 lines)
- [Source: nanobot/mc/types.py#StepStatus] — Python `StepStatus` StrEnum (lines 51–58)
- [Source: nanobot/mc/types.py#ActivityEventType] — Python `ActivityEventType` StrEnum — includes `STEP_DISPATCHED`, `STEP_STARTED`, `STEP_COMPLETED`, `SYSTEM_ERROR` (lines 75–107)
- [Source: nanobot/mc/bridge.py#update_step_status] — Python bridge method to extend (lines 444–459)
- [Source: tests/mc/test_plan_materializer.py] — Python test pattern to follow

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Task 5.2: `executor.py` does not call `bridge.update_step_status` — all step status updates go through `step_dispatcher.py`. Verified via grep. The three callers are all inside `_execute_step` in `step_dispatcher.py`.
- Task 3.1: AC1 was pre-satisfied — `isValidStepTransition` was already called in `updateStatus` at line 367, throwing `ConvexError` on illegal transitions. Documented as verified, no code change needed.
- Task 3.2: AC2 was pre-satisfied — `logStepStatusChange` already writes `step_status_changed` with all required fields. Documented as verified, no code change needed.
- Task 3.3: Pre-satisfied — `startedAt`, `completedAt`, `errorMessage` lifecycle fields already handled correctly. Documented as verified, no code change needed.
- Task 3.4: `"step_crashed"` was not in the Convex `activities.eventType` union literal in `schema.ts`. Added it to schema before adding the event in `updateStatus`.
- `test_step_dispatcher.py` mock `_update_step_status` accepted only 3 positional args — updated to also accept `current_status` as 4th parameter to match the new bridge signature.

### Completion Notes List

- **Task 1 complete**: Extended `nanobot/mc/state_machine.py` with `STEP_VALID_TRANSITIONS`, `STEP_TRANSITION_EVENT_MAP`, `is_valid_step_transition`, `validate_step_transition`, and `get_step_event_type`. `StepStatus` added to the import. All 6 states covered. `running→crashed` and `assigned→crashed` map to `SYSTEM_ERROR` (no dedicated `STEP_CRASHED` constant exists without schema change).
- **Task 2 complete**: Created `tests/mc/test_step_state_machine.py` with 37 tests: 11 valid transition checks, 11 invalid transition checks, 4 `validate_step_transition` tests, 7 event type mapping tests, 3 unmapped-transition ValueError tests, and 1 parity test against the Convex spec. All 37 pass.
- **Task 3 complete**: ACs 1–3 were pre-satisfied and verified. Added dedicated `"step_crashed"` activity event (Task 3.4) to `updateStatus` in `steps.ts`, and added `"step_crashed"` literal to `activities.eventType` union in `schema.ts`.
- **Task 4 complete**: Extended `dashboard/convex/steps.test.ts` with `describe("isValidStepTransition — full matrix")` (24 tests) and `describe("updateStatus")` (8 tests) — total TypeScript test count rose from 269 to 315. All pass.
- **Task 5 complete**: Added optional `current_status: str | None = None` parameter to `bridge.update_step_status` with lazy import of `validate_step_transition`. Updated all 3 callers in `step_dispatcher.py` to pass their known current statuses (`ASSIGNED→RUNNING`, `RUNNING→COMPLETED`, `RUNNING→CRASHED`). Import is from `nanobot.mc.state_machine` (not from `nanobot.agent`).

### File List

- `nanobot/mc/state_machine.py` — extended with step-level state machine (STEP_VALID_TRANSITIONS, STEP_TRANSITION_EVENT_MAP, is_valid_step_transition, validate_step_transition, get_step_event_type)
- `tests/mc/test_step_state_machine.py` — new file: 39 Python unit tests for step state machine (2 added by code review)
- `dashboard/convex/steps.ts` — added `step_crashed` activity event in updateStatus; updated ActivityLoggerCtx type
- `dashboard/convex/schema.ts` — added `"step_crashed"` to activities.eventType union literal
- `dashboard/convex/steps.test.ts` — extended with isValidStepTransition full matrix tests and updateStatus handler tests (36 new tests; 1 added by code review)
- `nanobot/mc/bridge.py` — added optional current_status parameter to update_step_status with pre-flight validation
- `nanobot/mc/step_dispatcher.py` — updated 3 callers of update_step_status to pass current_status
- `nanobot/mc/test_step_dispatcher.py` — updated mock _update_step_status to accept current_status parameter

## Change Log

- 2026-02-25: Story 3.1 implemented. Extended Python state_machine.py with step-level state machine mirroring Convex STEP_TRANSITIONS. Added dedicated step_crashed activity event to Convex updateStatus mutation and schema. Added pre-flight validation to bridge.update_step_status via optional current_status parameter. All callers in step_dispatcher.py updated. 37 new Python tests + 35 new TypeScript tests added; all pass with no regressions.
- 2026-02-25: Code review (adversarial). Fixed 5 issues: (1) Strengthened AC2 test assertion from weak OR regex to 3 separate match assertions verifying previous status, next status, AND step title all appear in description. (2) Added TypeScript test verifying completedAt is set on transition to completed. (3) Added 2 Python tests documenting that get_step_event_type raises ValueError for assigned→completed and blocked→crashed (valid but intentionally unmapped transitions). (4) Added documentation comment in STEP_TRANSITION_EVENT_MAP listing all intentionally unmapped transitions. (5) Added no-op test assertion that step record status is unchanged after same-status transition. Final test counts: 39 Python + 47 TypeScript, all pass.
