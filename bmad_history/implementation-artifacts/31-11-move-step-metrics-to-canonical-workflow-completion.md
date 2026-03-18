# Story 31.11: Move Step Metrics to Canonical Workflow Completion

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want workflow step metrics to update from canonical completion transitions,
so that agent history reflects real execution instead of UI-only moves.

## Overall Objective

Attach `stepsExecuted` and `lastStepExecutedAt` to the actual workflow step
completion path used by Mission Control and prevent double-counting across
manual and automated flows.

## Acceptance Criteria

1. Workflow step completion increments `stepsExecuted` and
   `lastStepExecutedAt` from the canonical transition path used by MC runtime.
2. Manual completion flows do not double-count a step already counted by the
   canonical transition layer.
3. `steps:updateStatus` and `steps:transition` stay behaviorally aligned for
   metric updates.
4. Direct-task counters and workflow-step counters remain separate.
5. Focused tests cover automated completion, manual completion, and idempotent
   replays.

## Files To Change

- `dashboard/convex/steps.ts`
- `dashboard/convex/steps.test.ts`
- `dashboard/convex/agents.ts`
- `dashboard/convex/lib/stepTransitions.ts`
- `mc/bridge/repositories/steps.py`

## Tasks / Subtasks

- [ ] Task 1: Move metric updates to lifecycle truth
  - [ ] 1.1 Identify the canonical step-completion helper
  - [ ] 1.2 Increment step metrics there
  - [ ] 1.3 Remove UI-only coupling from manual move paths

- [ ] Task 2: Protect against double counting
  - [ ] 2.1 Keep idempotent transition semantics intact
  - [ ] 2.2 Ensure retries or duplicate completions do not inflate metrics
  - [ ] 2.3 Preserve current task metric behavior

- [ ] Task 3: Add regression coverage
  - [ ] 3.1 Prove runtime-driven completion increments step metrics
  - [ ] 3.2 Prove manual completion does not double count
  - [ ] 3.3 Prove step and task metrics remain separate

## Dev Notes

- The fix should follow lifecycle truth, not whichever UI mutation happens to
  be called today.
- Prefer a single canonical metric hook rather than duplicating increments in
  multiple mutations.

## References

- [Source: review findings on March 17, 2026]
- [Source: `31-7-track-agent-task-and-step-execution-metrics.md`]

