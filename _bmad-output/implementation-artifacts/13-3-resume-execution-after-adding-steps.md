# Story 13.3: Resume Execution After Adding Steps

Status: ready-for-dev

## Story

As a **user**,
I want to resume execution of a task after adding new steps to its plan,
so that the system continues the work trail with the newly added steps without starting over.

## Acceptance Criteria

### AC1: Resume Button Visibility

**Given** a task with an execution plan
**When** the task status is "done" AND there are steps with status "planned" (newly added, not yet executed)
**Then** a "Resume" button is visible in the Execution Plan tab header
**And** the button shows a play icon and the text "Resume (N new steps)" where N is the count of planned steps

### AC2: Resume Button — In-Progress with All Steps Finished

**Given** a task with status "in_progress"
**When** all existing steps have status "completed" or "crashed" AND there are new steps with status "planned"
**Then** the "Resume" button is also visible (same behavior as AC1)

### AC3: Resume from Done

**Given** a task with status "done" and new planned steps
**When** the user clicks "Resume"
**Then** the `tasks.resumeFromDone` mutation is called
**And** the task status transitions from "done" to "in_progress"
**And** an activity record is created: "User resumed task with N new steps"
**And** the orchestrator detects the transition and dispatches the new planned steps
**And** steps that have no blockers (or whose blockers are all completed) start executing immediately
**And** steps with unfinished blockers remain in "blocked" status

### AC4: Resume Materializes Unmaterialized Steps

**Given** new steps were added to `executionPlan.steps` via lead-agent chat (Story 13-2) but NOT yet materialized as step records
**When** the user clicks "Resume"
**Then** the mutation detects steps in `executionPlan.steps` that don't have corresponding step records
**And** those steps are created as new step records (using the same logic as `steps.batchCreate`, resolving tempId dependencies)
**And** after materialization, the task transitions to "in_progress"

### AC5: Resume Dispatches Only New Steps

**Given** the task resumes with both completed and new planned steps
**When** the orchestrator picks up the resumed task
**Then** it dispatches ONLY steps with status "planned" or "blocked" (that become unblocked)
**And** already completed steps are NOT re-executed
**And** crashed steps are NOT auto-retried (user must explicitly retry those separately)

### AC6: Convex Mutation — tasks.resumeFromDone

**Given** a call to `tasks.resumeFromDone` with `{taskId}`
**Then** the mutation:
- Validates the task exists
- Validates the task status is "done"
- Validates there is at least one step with status "planned" (rejects if no new work to do)
- Checks for unmaterialized steps in executionPlan.steps — if found, materializes them (creates step records, resolves dependencies)
- Transitions task status from "done" to "in_progress"
- Creates activity: `task_started` with description "User resumed task execution with N new steps"
- Returns the task ID

### AC7: Orchestrator Detects Resumed Task

**Given** a task transitions from "done" to "in_progress"
**When** the orchestrator polls for active tasks
**Then** it detects the task has steps with status "planned" or "blocked"
**And** it calls `StepDispatcher` to dispatch steps whose dependencies are all completed
**And** it starts a new plan_negotiation_loop for the task (so the user can continue chatting with lead-agent during execution)

### AC8: State Machine Extension

**Given** the current state machine defines valid task transitions
**Then** "done" → "in_progress" is added as a valid transition
**And** it is labeled "task_resumed" in the activity log

## Tasks / Subtasks

- [ ] Task 1: Create `tasks.resumeFromDone` Convex mutation (AC: 3, 4, 6)
  - [ ] 1.1: Add the mutation to `dashboard/convex/tasks.ts` with args: `taskId: v.id("tasks")`
  - [ ] 1.2: Validate task exists and status is "done"
  - [ ] 1.3: Query steps for this task, count those with status "planned" — reject with error if zero
  - [ ] 1.4: Check for unmaterialized steps: compare `executionPlan.steps` tempIds against existing step records. For any tempId without a matching step record, create the step (reuse logic from `batchCreate` or inline)
  - [ ] 1.5: Transition task status to "in_progress", clear any completion-related fields
  - [ ] 1.6: Insert activity record: `task_started`, description includes count of new steps

- [ ] Task 2: Extend state machine for done → in_progress (AC: 8)
  - [ ] 2.1: In `dashboard/convex/tasks.ts`, add "in_progress" to the valid transitions from "done" (the `isValidTransition` function or transition map)
  - [ ] 2.2: In `mc/state_machine.py`, add `("done", "in_progress")` to `TASK_TRANSITIONS` with event type `TASK_RESUMED` (or reuse `TASK_STARTED`)
  - [ ] 2.3: Add `TASK_RESUMED` event type to activity types if not already present

- [ ] Task 3: Resume button in ExecutionPlanTab (AC: 1, 2)
  - [ ] 3.1: In `ExecutionPlanTab.tsx`, compute `hasNewPlannedSteps`: check if any step/liveStep has status "planned"
  - [ ] 3.2: Compute `allExistingFinished`: all steps that are NOT "planned" have status "completed" or "crashed"
  - [ ] 3.3: Show "Resume" button when: `hasNewPlannedSteps && (taskStatus === "done" || (taskStatus === "in_progress" && allExistingFinished))`
  - [ ] 3.4: Button shows Play icon + "Resume (N new steps)" text
  - [ ] 3.5: On click: call `tasks.resumeFromDone` mutation, show loading state, handle errors
  - [ ] 3.6: After successful resume, the button disappears (task is now in_progress with dispatching steps)
  - [ ] 3.7: ExecutionPlanTab needs to receive `taskStatus` as a prop (add if not already present)

- [ ] Task 4: Orchestrator picks up resumed tasks (AC: 5, 7)
  - [ ] 4.1: In `mc/orchestrator.py` (or `mc/step_dispatcher.py`), ensure the task polling loop detects tasks that just became "in_progress" with pending "planned" steps
  - [ ] 4.2: The existing `_dispatch_ready_steps()` should already handle this — it queries steps with status "planned" or "blocked" and dispatches ready ones. Verify this works for resumed tasks (it should, since the mechanism is the same as initial kickoff).
  - [ ] 4.3: If the orchestrator uses a set of "known active tasks" to avoid re-processing, ensure resumed tasks are added to this set
  - [ ] 4.4: Start a `plan_negotiation_loop` for the resumed task so lead-agent chat continues during execution

- [ ] Task 5: Write tests (AC: all)
  - [ ] 5.1: Unit test for `tasks.resumeFromDone`: validates done status, rejects if no planned steps, transitions to in_progress
  - [ ] 5.2: Unit test for `tasks.resumeFromDone`: materializes unmaterialized steps from executionPlan
  - [ ] 5.3: Unit test for state machine: done → in_progress is valid
  - [ ] 5.4: Component test for Resume button: visible when conditions met, hidden otherwise
  - [ ] 5.5: Integration test: full flow — add step to done task → click Resume → task becomes in_progress → step dispatched
  - [ ] 5.6: Test that completed steps are NOT re-executed on resume

## Dev Notes

### Existing Infrastructure to Reuse

- `tasks.resumeTask` mutation — already handles review → in_progress. Use as reference but create a separate `resumeFromDone` to keep the validation logic clean (different preconditions).
- `steps.batchCreate` — reuse for materializing unmaterialized steps from executionPlan
- `StepDispatcher._dispatch_ready_steps()` — already queries for planned/blocked steps and dispatches ready ones. Should work for resumed tasks without changes.
- `start_plan_negotiation_loop()` — already handles in_progress tasks with plans

### Key Files

- `dashboard/convex/tasks.ts` — add `resumeFromDone` mutation, extend transition map
- `dashboard/components/ExecutionPlanTab.tsx` — add Resume button
- `mc/state_machine.py` — add done → in_progress transition
- `mc/orchestrator.py` — ensure resumed tasks are picked up
- `mc/step_dispatcher.py` — verify _dispatch_ready_steps works for resumed tasks

### Architecture Decisions

- Separate `resumeFromDone` mutation (not reusing `resumeTask`) because:
  - `resumeTask` requires status "review" (not "done")
  - `resumeFromDone` needs to materialize unmaterialized steps
  - Different validation: resumeFromDone requires planned steps to exist
- Materialization at resume time (not at step-add time) keeps "done" tasks stable until the user explicitly resumes. Adding steps to a done task via chat is exploratory — the user might discard changes.
- The orchestrator's existing polling mechanism should pick up resumed tasks naturally. If it maintains an explicit "active tasks" set, we just need to ensure re-scanning on status change.

### References

- [Source: dashboard/convex/tasks.ts#resumeTask] — existing resume mutation (review → in_progress)
- [Source: dashboard/convex/tasks.ts#approveAndKickOff] — kickoff mutation reference
- [Source: dashboard/convex/steps.ts#batchCreate] — step materialization logic
- [Source: mc/step_dispatcher.py] — step dispatch mechanism
- [Source: mc/state_machine.py] — task transition definitions
- [Source: mc/orchestrator.py] — task polling and dispatch loop
