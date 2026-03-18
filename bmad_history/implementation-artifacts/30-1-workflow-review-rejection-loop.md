# Story 30.1: Workflow Review Rejection Loop

Status: ready-for-dev

## Story

As a **user running AI workflow missions**,
I want workflow `review` steps to execute as reviewer-agent steps driven by the workflow's `reviewSpec`,
so that rejection routes deterministically back to the correct step, rework preserves thread context, and review runs again without human intervention.

## Context

The current workflow runtime already preserves these metadata fields on materialized steps:

- `workflowStepType`
- `reviewSpecId`
- `onRejectStepId`

But the runtime still has major gaps:

- `review` steps are not treated as a distinct execution contract.
- there is no structured verdict parsing for reviewer output.
- there is no automatic rejection routing to `onRejectStepId`.
- the rejected step is not re-run in a controlled loop with the same thread history.
- provider CLI approval/intervention events can still get conflated with workflow review semantics.
- human/checkpoint gates can still diverge from the normal step lifecycle and get stuck.

This story closes that loop while preserving the existing task/step runtime model.

## Acceptance Criteria

### AC1: Review Step Is Agent-Owned, Not Human-Gated

**Given** a workflow step has `workflowStepType == "review"`
**And** it has an explicit reviewer agent on the step itself
**When** the dispatcher reaches that step
**Then** the step runs as a normal agent execution step
**And** it does NOT enter `waiting_human`
**And** its execution contract is driven by `reviewSpecId`, not by hardcoded agent-name checks.

### AC2: Workflow Review Contract Is Validated Up Front

**Given** a workflow `review` step is compiled or prepared for execution
**When** it is missing required review metadata
**Then** the workflow is rejected before runtime execution begins.

Required review-step fields for this story:

- `agentId`
- `reviewSpecId`
- `onReject`

### AC3: Reviewer Returns Structured Verdict

**Given** a workflow `review` step runs
**When** the reviewer agent completes
**Then** the runtime parses a structured review result containing at least:

- `verdict`
- `issues`
- `strengths`
- `scores`
- `vetoesTriggered`
- `recommendedReturnStep`

**And** `verdict` must be one of:

- `approved`
- `rejected`

### AC4: Approved Review Completes Normally

**Given** a workflow `review` step returns `verdict = approved`
**When** the runtime handles the result
**Then** the review step transitions to `completed`
**And** downstream dependent steps are unblocked through the normal step lifecycle.

### AC5: Rejected Review Reroutes Deterministically

**Given** a workflow `review` step returns `verdict = rejected`
**When** the runtime handles the result
**Then** the runtime routes rework to the step identified by `onRejectStepId`
**And** the current review step transitions to `blocked`
**And** the rejected target step transitions back to `assigned`
**And** the rejected target keeps its existing runtime identity (same step record, not a replacement step).

### AC6: Re-Review Loop Repeats on the Same Review Step

**Given** a workflow `review` step has rejected a target step
**When** the target step completes again
**Then** the blocked review step becomes dispatchable again
**And** the same review step runs a new review pass
**And** no duplicate review step record is created for the new cycle.

### AC7: Rejected Step Re-Execution Preserves Context

**Given** a step was rejected by a workflow reviewer
**When** that step is re-executed
**Then** the execution uses the same task thread history
**And** the previous rejected output remains in the thread
**And** the reviewer feedback remains in the thread
**And** the next execution prompt explicitly includes the latest review feedback / rejected-attempt context
**And** the new execution appends new completion output to the same thread instead of replacing old output.

### AC8: Human Gates Stay Separate

**Given** workflow steps of type `human` or `checkpoint`
**When** they are dispatched
**Then** they use the explicit human-gate lifecycle
**And** only those step types may enter `waiting_human`
**And** they do not share reviewer verdict parsing logic.

### AC9: Provider Approval Events Do Not Masquerade as Workflow Review

**Given** an interactive/provider session emits an approval/intervention event
**When** the runtime projects that event
**Then** it is treated as live-session supervision state
**And** it does NOT change workflow `review` step semantics into a human review gate.

## Tasks / Subtasks

- [ ] **Task 1: Add failing tests for workflow review loop semantics** (AC: 1, 3, 4, 5, 6, 7, 8, 9)
  - [ ] 1.1 Add dispatcher/runtime tests for review-step approval and rejection paths
  - [ ] 1.2 Add Convex tests for gate/manual lifecycle separation
  - [ ] 1.3 Add context-builder tests for rejection feedback preservation
  - [ ] 1.4 Add parser tests for structured reviewer output

- [ ] **Task 2: Validate review-step contracts during compilation/materialization** (AC: 2)
  - [ ] 2.1 Reject `review` steps without `agentId`
  - [ ] 2.2 Reject `review` steps without `reviewSpecId`
  - [ ] 2.3 Reject `review` steps without `onReject`
  - [ ] 2.4 Preserve `reviewSpecId` / `onRejectStepId` through materialization

- [ ] **Task 3: Implement structured review-result parsing in runtime** (AC: 1, 3, 4)
  - [ ] 3.1 Add a review-result parser in the domain layer
  - [ ] 3.2 Inject review-specific prompt context for `review` steps
  - [ ] 3.3 Branch runtime behavior by parsed `verdict`

- [ ] **Task 4: Implement rejection reroute + repeat-review lifecycle** (AC: 5, 6)
  - [ ] 4.1 Block the review step on rejection
  - [ ] 4.2 Reassign the `onRejectStepId` target step
  - [ ] 4.3 Keep the same step record for rework
  - [ ] 4.4 Unblock and rerun the same review step after the target completes again

- [ ] **Task 5: Harden human/checkpoint and provider supervision boundaries** (AC: 8, 9)
  - [ ] 5.1 Ensure only `human` / `checkpoint` use `waiting_human`
  - [ ] 5.2 Fix non-human workflow gates so they cannot get stuck after accept
  - [ ] 5.3 Separate provider approval/intervention events from workflow review semantics

- [ ] **Task 6: Verify the full loop end-to-end** (AC: 1-9)
  - [ ] 6.1 Run targeted Python and dashboard tests
  - [ ] 6.2 Run lint/format/architecture checks for touched areas
  - [ ] 6.3 Boot the full MC stack and validate reviewer approve/reject cycles manually

## Technical Design

### Approved Execution Model

- `agent` step: normal agent step
- `human` step: human gate
- `checkpoint` step: human gate
- `review` step: reviewer-agent step with structured result contract
- `system` step: unchanged / out of scope unless needed for parity

### Rejection Loop

When a review rejects:

1. parse structured reviewer output
2. persist feedback to the thread
3. transition review step to `blocked`
4. transition `onRejectStepId` target to `assigned`
5. re-run target step on the same task thread
6. when target completes again, unblock and rerun the same review step

### Context Preservation

Re-runs must append to the same task thread.

The implementation must preserve:

- prior `step_completion` output
- reviewer feedback
- predecessor context
- new execution output from the re-run

The prompt should explicitly surface the latest rejection feedback instead of relying only on generic thread truncation.

## Dev Notes

### Existing Behavior to Reuse

- workflow compiler already maps `onReject` to `onRejectStepId`
- materializer already preserves workflow step metadata
- step execution already rebuilds context from the task thread on each run
- `post_step_completion` already appends structured step completion to the thread

### Behavior That Must Change

- `review` step handling in dispatcher
- gate handling for workflow human/checkpoint steps
- review-result parsing and routing
- prompt enrichment for rejected-step re-runs
- interactive/provider approval event projection that currently blurs review semantics

### Files Likely Involved

- `dashboard/convex/lib/workflowExecutionCompiler.ts`
- `dashboard/convex/steps.ts`
- `dashboard/convex/lib/stepLifecycle.ts`
- `dashboard/features/tasks/components/StepCard.tsx`
- `mc/application/execution/context_builder.py`
- `mc/contexts/execution/step_dispatcher.py`
- `mc/contexts/interactive/supervisor.py`
- `mc/contexts/provider_cli/providers/codex.py`

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log
