# Story 7.2: Human as First-Class Plan Actor

Status: done

## Story

As a **user**,
I want to assign plan steps to myself (human) just like I would assign them to an agent,
So that I can include manual tasks in the execution flow that block dependent steps until I complete them.

## Context

In the execution plan canvas (Story 7.1), "Human" is a selectable assignee alongside agents. When a human-assigned step is dispatched during execution, instead of spawning an agent subprocess, the step transitions to a **waiting** state that halts dependent steps and surfaces an **"Accept"** button in the Execution Plan canvas. The human clicks "Accept" to complete the step and unblock dependents.

**Key design decisions confirmed with user:**
- Human is `assignedAgent: "human"` in the plan (a special sentinel value, not a DB record)
- Step assigned to "human" → when dispatched, transitions to a special waiting state (not "running")
- The step block shows an **"Accept" button** for the user to click to complete it
- On Accept: step transitions to `completed`, dependent steps are unblocked
- Human steps are treated as first-class actors in the plan — they block dependent steps until accepted

## Acceptance Criteria

1. **Human option in agent dropdown** -- Given the canvas is in edit mode (Story 7.1), when the user opens the agent dropdown on a step, then "Human" appears as the first option with a user icon, and selecting it sets `assignedAgent: "human"` on the step.

2. **Human step visual distinction in canvas** -- Given a step has `assignedAgent: "human"` in the plan, when the canvas renders the step block, then the step displays a `User` icon and "Human" label instead of an agent name/avatar, both in edit and read-only mode.

3. **Dispatcher skips agent subprocess for human steps** -- Given a human-assigned step is dispatched by the Python orchestrator, when the dispatcher processes it, then instead of spawning an agent subprocess, it transitions the step to a new `waiting_human` status and does NOT send it to any agent.

4. **Human step shows "Accept" button in canvas** -- Given a step is in `waiting_human` status, when the user views the Execution Plan tab, then the step block shows an **"Accept"** button (green, with a checkmark icon), the step status badge shows "Awaiting Human", and dependent steps show a "Blocked" indicator.

5. **Accept button completes the step** -- Given the user clicks "Accept" on a human-assigned step in `waiting_human` status, when the mutation completes, then the step transitions to `completed`, dependent steps that were blocked only by this step transition to `pending`/`assigned` and are dispatched by the orchestrator, and an activity event is created: "Human completed step: {step title}".

6. **Human steps block dependents** -- Given step B has `blockedBy: [step A (human)]` and step A is in `waiting_human`, when the dispatcher checks step B, then step B remains in `blocked` status and is NOT dispatched until step A is accepted.

7. **Human step does not block non-dependent steps** -- Given step C has no dependency on step A (human), when step A is in `waiting_human`, then step C continues to execute normally without waiting for step A.

8. **`waiting_human` added to step status schema** -- Given the step status union in `schema.ts`, when this story is implemented, then `v.literal("waiting_human")` is added to the `steps.status` union, and `WAITING_HUMAN = "waiting_human"` is added to the Python `StepStatus` enum in `types.py`.

9. **Convex mutation for human step acceptance** -- Given the dashboard needs to mark a human step as completed, when the user clicks "Accept", then a `steps:acceptHumanStep` Convex mutation is called that: (a) validates the step is in `waiting_human` status, (b) transitions step to `completed`, (c) creates an activity event, (d) triggers dependent step unblocking (same mechanism as regular step completion).

## Tasks / Subtasks

- [x] **Task 1: Add `waiting_human` to Convex schema and Python types** (AC: 8)
  - [x] 1.1 In `dashboard/convex/schema.ts`, add `v.literal("waiting_human")` to the `steps.status` union (after `"blocked"`).
  - [x] 1.2 In `nanobot/mc/types.py`, add `WAITING_HUMAN = "waiting_human"` to `StepStatus` enum.
  - [x] 1.3 In `nanobot/mc/step_state_machine.py` (or equivalent), add valid transitions: `waiting_human -> completed`, `waiting_human -> crashed`.
  - [x] 1.4 In `nanobot/mc/step_dispatcher.py`, add "waiting_human" to the set of terminal states (steps in this state should not be re-dispatched).

- [x] **Task 2: Python dispatcher handles human steps** (AC: 3, 6)
  - [x] 2.1 In `nanobot/mc/step_dispatcher.py`, in the step dispatch logic (where `assigned_agent` is read), check if `assigned_agent == "human"`.
  - [x] 2.2 If `assigned_agent == "human"`: call `bridge.update_step_status(step_id, StepStatus.WAITING_HUMAN, ...)` instead of spawning a subprocess.
  - [x] 2.3 Create an activity event: `"Human action required for step: {step_title}"`.
  - [x] 2.4 Ensure the auto-unblock mechanism (`step_completion` handler) does NOT treat `waiting_human` as a completion — only `completed` unblocks dependents.
  - [x] 2.5 The existing dependency check in the dispatcher already uses step status to decide if a step can run. Verify `waiting_human` is treated as a non-completed blocking state (not "done").

- [x] **Task 3: Create `steps:acceptHumanStep` Convex mutation** (AC: 5, 9)
  - [x] 3.1 In `dashboard/convex/steps.ts` (or create it if it doesn't exist), add mutation `acceptHumanStep`:
    - Args: `stepId: v.id("steps")`
    - Validates step is in `waiting_human` status; throws `ConvexError` otherwise
    - Transitions step to `completed`
    - Creates activity event: `"Human completed step: {step.title}"`
    - Returns the `taskId` for the caller to trigger dependent unblocking check
  - [x] 3.2 The mutation does NOT directly unblock dependents — the Python orchestrator's existing `auto_unblock_dependent_steps` mechanism handles this by watching for `completed` steps (same as agent step completion).

- [x] **Task 4: Add "Accept" button to ExecutionPlanTab step card (read-only mode)** (AC: 4, 5)
  - [x] 4.1 In `ExecutionPlanTab.tsx`, when rendering a step card with `status === "waiting_human"`:
    - Show status badge: "Awaiting Human" with a `Clock` or `User` icon in amber color.
    - Show "Accept" button (green, `CheckCircle` icon from lucide-react).
  - [x] 4.2 On "Accept" click: call `useMutation(api.steps.acceptHumanStep)` with the step ID.
  - [x] 4.3 While the mutation is in flight: disable the button, show spinner.
  - [x] 4.4 On error: show a toast with the error message.

- [x] **Task 5: Add human step visual distinction in PlanStepCard (edit mode)** (AC: 1, 2)
  - [x] 5.1 In `PlanStepCard.tsx`, when `step.assignedAgent === "human"`, render a `User` icon and "Human" label in the agent area (instead of an agent avatar/name).
  - [x] 5.2 In the agent dropdown, ensure "Human" is the first option with a `User` icon, value `"human"`. (Dependency on Task 4 of Story 7.1 — can be done together.)

- [x] **Task 6: Write tests** (AC: 1-9)
  - [x] 6.1 **Python test:** `test_step_dispatcher.py` — test that a step with `assigned_agent == "human"` transitions to `waiting_human` instead of spawning subprocess.
  - [x] 6.2 **Python test:** `test_step_dispatcher.py` — test that `waiting_human` step does NOT unblock dependents (only `completed` does).
  - [x] 6.3 **Convex test:** `steps.test.ts` — test `acceptHumanStep` mutation: happy path (waiting_human → completed + activity), error path (wrong status throws ConvexError).
  - [x] 6.4 **Dashboard test:** `ExecutionPlanTab.test.tsx` — test that `waiting_human` step shows "Accept" button, clicking it calls `acceptHumanStep`.

## Dev Notes

### Step Status Flow for Human Steps

```
plan (assignedAgent: "human")
  -> dispatch:  waiting_human  [Accept button shown to user]
  -> user clicks Accept
  -> completed  [dependents unblocked by auto-unblock mechanism]
```

Contrast with agent steps:
```
plan (assignedAgent: "general-agent")
  -> dispatch:  assigned -> running -> completed
```

### Why `waiting_human` instead of `review`

The existing `review` status on *tasks* is used for:
1. Pre-kickoff (with `awaitingKickoff: true`)
2. Pause/Resume (Story 7.4)

Using `waiting_human` as a **step** status keeps concerns separated:
- Task-level `review` = user reviewing/editing the plan or paused execution
- Step-level `waiting_human` = a specific step waiting for human action

### Bridge Method for Step Status Update

Use the existing pattern for step status updates in the bridge:
```python
bridge.update_step_status(step_id, StepStatus.WAITING_HUMAN, task_id, "Human action required")
```
If this method doesn't exist with this exact signature, check `nanobot/mc/bridge.py` for the existing step status update method and adapt.

### Auto-Unblock Pattern (DO NOT Reinvent)

The existing `auto_unblock_dependent_steps` in `nanobot/mc/step_dispatcher.py` already watches for steps that transition to `completed` and unblocks their dependents. This story does NOT change that mechanism — it only ensures:
1. `waiting_human` is NOT treated as `completed`
2. When the user clicks Accept and the step transitions to `completed`, the existing auto-unblock fires normally

The `steps:acceptHumanStep` Convex mutation only needs to transition the step to `completed` — the Python orchestrator's existing subscription loop will detect this and unblock dependents.

### Common LLM Developer Mistakes to Avoid

1. **DO NOT add "human" to the `agents` table** — "Human" is a sentinel value (`"human"`) in `assignedAgent`, not a DB record. Querying `api.agents.list` will never return "human".

2. **DO NOT make the dispatcher crash when it sees `assigned_agent == "human"`** — it must gracefully handle this case and transition the step to `waiting_human`.

3. **DO NOT show "Accept" in the PlanEditor (edit mode)** — Accept is only shown in the read-only execution view (`ExecutionPlanTab` when the task is `in_progress`). In edit mode (pre-kickoff), a "human" step just shows the Human label, no Accept button.

4. **DO NOT use `review` for the step status of human steps** — use `waiting_human`. The `review` status is for tasks, not steps.

5. **DO NOT block the entire task** when a human step is waiting — only steps with a dependency on the human step are blocked. Other parallel branches execute normally (AC: 7).

### What This Story Does NOT Include

- Lead Agent thread negotiation (Story 7.3)
- Task Pause/Resume (Story 7.4)

### Files to Modify

- `dashboard/convex/schema.ts` — add `waiting_human` to steps status union
- `dashboard/convex/steps.ts` — add `acceptHumanStep` mutation
- `dashboard/components/ExecutionPlanTab.tsx` — render Accept button for `waiting_human` steps
- `dashboard/components/PlanStepCard.tsx` — human visual (covered in Story 7.1 Task 5)
- `nanobot/mc/types.py` — add `WAITING_HUMAN` to `StepStatus` enum
- `nanobot/mc/step_dispatcher.py` — handle `assigned_agent == "human"` case
- `nanobot/mc/step_state_machine.py` (or equivalent) — add `waiting_human` transitions

### References

- [Source: `dashboard/convex/schema.ts#steps`] — Current step status union
- [Source: `nanobot/mc/step_dispatcher.py`] — Step dispatch and auto-unblock logic
- [Source: `nanobot/mc/types.py#StepStatus`] — Python step status enum
- [Source: `dashboard/components/ExecutionPlanTab.tsx`] — Read-only execution view to extend
- [Story 7.1] — Canvas edit mode and Human option in dropdown

## File List

### Modified Files
- `dashboard/convex/schema.ts` — Added `v.literal("waiting_human")` to `steps.status` union
- `dashboard/convex/steps.ts` — Added `"waiting_human"` to `STEP_STATUSES` and `STEP_TRANSITIONS`; added `acceptHumanStep` mutation; **[review fix]** added `logStepStatusChange` call and inline `findBlockedStepsReadyToUnblock` + unblock loop to ensure dependent steps are assigned on Accept
- `dashboard/components/ExecutionPlanTab.tsx` — Added `waiting_human` status display ("Awaiting Human" badge, amber User icon, green Accept button with spinner, per-step error display)
- `nanobot/mc/types.py` — Added `WAITING_HUMAN = "waiting_human"` to `StepStatus` enum
- `nanobot/mc/state_machine.py` — Added complete step-level state machine (`STEP_VALID_TRANSITIONS`, `STEP_TRANSITION_EVENT_MAP`, `is_valid_step_transition`, `validate_step_transition`, `get_step_event_type`); added `waiting_human` transitions
- `nanobot/mc/bridge.py` — Added `post_system_error` method (referenced by pre-existing test file)
- `nanobot/mc/step_dispatcher.py` — Added human step dispatch path (transitions to `waiting_human`, creates activity, returns without spawning agent); added `_LLM_PROVIDER_ERROR_NAMES`, `_is_llm_provider_error`, `_build_crash_message` (referenced by pre-existing test file); updated crash handler to use `post_system_error`

### Test Files Modified
- `dashboard/components/ExecutionPlanTab.test.tsx` — Added 6 Story 7.2 tests; fixed shared `mockMutationFn` pattern
- `dashboard/convex/steps.test.ts` — Added `waiting_human` to status/transition tests; added `acceptHumanStep` test suite (6 tests); added `findBlockedStepsReadyToUnblock` waiting_human test; **[review fix]** updated `makeCtx` to include `query` mock; updated "does not unblock dependents" test to "unblocks dependent steps directly" asserting the correct behavior; updated activity assertion to use `find()` instead of length check
- `tests/mc/test_step_dispatcher.py` — Added `TestHumanStepDispatch` class (5 tests); fixed pre-existing broken imports by implementing missing symbols
- `tests/mc/test_step_state_machine.py` — Added `waiting_human` valid/invalid transition tests and event type tests; updated parity test

## Change Log

### dashboard/convex/schema.ts
- Added `v.literal("waiting_human")` to the `steps.status` validator union (after `"blocked"`)

### dashboard/convex/steps.ts
- Added `"waiting_human"` to `STEP_STATUSES` const array
- Added `"waiting_human"` to `STEP_TRANSITIONS.assigned` allowed transitions
- Added `STEP_TRANSITIONS["waiting_human"] = ["completed", "crashed"]`
- Added `acceptHumanStep` mutation: validates `waiting_human` status, patches to `completed`, calls `logStepStatusChange`, inserts `step_completed` activity event, unblocks dependent steps inline (queries all task steps, runs `findBlockedStepsReadyToUnblock`, patches each to `assigned`, logs and inserts `step_unblocked` activities), returns `taskId`

### dashboard/components/ExecutionPlanTab.tsx
- Imported `useState`, `CheckCircle`, `User` (lucide-react), `useMutation` (convex/react), `api`, `Id`
- Added `"waiting_human"` to `StepStatusMeta.icon` discriminated union type
- Added `waiting_human` case to `getStatusMeta()`: amber badge "Awaiting Human", User icon
- Added `User` icon rendering branch in `StepStatusIcon` for `waiting_human`
- Extended `StepCard` props with `onAccept?`, `acceptError?`, `isAccepting?`
- Added Accept button block in `StepCard` (green, CheckCircle icon, Loader2 spinner when in-flight, error message below)
- Added `acceptHumanStepMutation`, `acceptingStepId`, `acceptErrors` state to `ExecutionPlanTab`
- Added `handleAccept(stepId)` async handler
- Hidden `"human"` sentinel from agent name display in read-only step card

### nanobot/mc/types.py
- Added `WAITING_HUMAN = "waiting_human"` to `StepStatus` StrEnum

### nanobot/mc/state_machine.py
- Updated module docstring to reference Story 7.2
- Added `StepStatus` to imports from `nanobot.mc.types`
- Added `STEP_VALID_TRANSITIONS` dict (7 states including `waiting_human`)
- Added `STEP_TRANSITION_EVENT_MAP` dict (9 mappings including `waiting_human` transitions)
- Added `is_valid_step_transition(current_status, new_status) -> bool`
- Added `validate_step_transition(current_status, new_status) -> None`
- Added `get_step_event_type(current_status, new_status) -> str`

### nanobot/mc/bridge.py
- Added `post_system_error(task_id, content, step_id=None)` method: posts a system-type message with structured args

### nanobot/mc/step_dispatcher.py
- Added `_LLM_PROVIDER_ERROR_NAMES` frozenset of known LLM provider exception class names
- Added `_LLM_PROVIDER_MODULES` frozenset of known LLM provider module prefixes
- Added `_is_llm_provider_error(exc) -> bool` helper
- Added `_build_crash_message(exc, agent_name, step_title) -> str` helper
- Added human step early-exit in `_execute_step()`: detects `agent_name == "human"`, calls `update_step_status(WAITING_HUMAN)`, creates `STEP_DISPATCHED` activity event, returns `[]`
- Updated crash handler to use `post_system_error` + `_build_crash_message` + `create_activity(SYSTEM_ERROR)`

## Dev Agent Record

### Implementation Notes

**Pre-existing broken test infrastructure (fixed as part of this story):**

The test suite for the MC module had two files that imported symbols which did not exist in the codebase:

1. `tests/mc/test_step_dispatcher.py` imported `_LLM_PROVIDER_ERROR_NAMES`, `_build_crash_message`, `_is_llm_provider_error` from `step_dispatcher.py` and `post_system_error` from `bridge.py` — none were implemented. These were remnants of a previously "done" story (Epic 3 crash handling) that were listed as done but never committed. Implemented all four symbols as part of this story.

2. `tests/mc/test_step_state_machine.py` imported step-level state machine functions from `state_machine.py` that only had the task-level state machine. The full step-level state machine (`STEP_VALID_TRANSITIONS`, `STEP_TRANSITION_EVENT_MAP`, and three functions) was missing. Implemented as part of this story.

**Human step dispatch flow (AC 3, 6, 7):**

The `_execute_step()` method in `step_dispatcher.py` checks `agent_name == "human"` before the subprocess spawn logic. On match it calls `update_step_status(WAITING_HUMAN)` (no subprocess) and returns an empty list. The existing dispatch loop only processes `assigned` steps, so `waiting_human` steps are never re-dispatched. The `all_completed` guard in the orchestrator loop only passes when every step is `completed`, so tasks with pending human steps stay `in_progress`.

**`waiting_human` does not unblock dependents (AC 6):**

`findBlockedStepsReadyToUnblock` in `steps.ts` already only unblocks when ALL blockers have status `"completed"`. No special-casing was needed — `waiting_human` is simply not `completed`, so blocked dependents remain blocked until the user clicks Accept.

**Accept button only in execution view, not edit mode (AC 4, Dev Note 3):**

The Accept button is rendered inside `ExecutionPlanTab.tsx`'s `StepCard`, which is the read-only execution view. `PlanStepCard.tsx` (edit mode) already had the Human visual distinction from Story 7.1 and was not changed.

**Test mock fix for Accept button click test:**

The Vitest test for Accept button click required a shared `mockMutationFn` variable declared before the `vi.mock("convex/react")` factory. This ensures the same function reference is captured by the module mock closure and accessible in test assertions. The click event was wrapped in `act(async () => { ... })` with a microtask flush to allow the async mutation handler to settle.

### Completion Notes

All 9 Acceptance Criteria are fully implemented and tested:
- AC 1, 2: Human visual in PlanStepCard was already done in Story 7.1; read-only display in ExecutionPlanTab updated to hide "human" sentinel and show User icon with "Awaiting Human" badge
- AC 3: `step_dispatcher.py` detects `agent_name == "human"` and transitions to `waiting_human` without spawning subprocess
- AC 4: `ExecutionPlanTab.tsx` renders amber "Awaiting Human" badge and green Accept button for `waiting_human` steps
- AC 5: `acceptHumanStep` mutation transitions to `completed` and creates activity event; orchestrator's existing auto-unblock fires on `completed`
- AC 6: `findBlockedStepsReadyToUnblock` only unblocks on `completed`; `waiting_human` correctly keeps dependents blocked
- AC 7: Non-dependent steps are unaffected by a `waiting_human` step (verified by existing dispatch loop logic and tests)
- AC 8: `waiting_human` added to `schema.ts` union and `StepStatus` Python enum
- AC 9: `acceptHumanStep` mutation implemented with validation, transition, activity event, and `taskId` return

**Test results at completion:**
- `ExecutionPlanTab.test.tsx`: 31 tests passed (25 existing + 6 new)
- `dashboard/convex/steps.test.ts`: 26 tests passed (added waiting_human + acceptHumanStep tests)
- `tests/mc/test_step_dispatcher.py`: 41 tests passed (was broken, now fixed + 5 new human step tests)
- `tests/mc/test_step_state_machine.py`: 48 tests passed (was broken, now fixed + waiting_human tests)
