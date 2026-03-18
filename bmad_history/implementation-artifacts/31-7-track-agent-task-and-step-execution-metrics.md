# Story 31.7: Track Agent Task and Step Execution Metrics

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want agent execution counters to update at canonical completion points,
so that routing and operator visibility can rely on durable task and step
history.

## Overall Objective

Update task-completion and step-completion paths to increment the new agent
metric fields added earlier, while keeping direct-delegate task counts and
workflow step counts separate.

## Acceptance Criteria

1. Direct-delegate task completion increments `tasksExecuted` for the executing
   agent.
2. Workflow step completion increments `stepsExecuted` for the step executor.
3. `lastTaskExecutedAt` and `lastStepExecutedAt` update alongside their
   counters.
4. Metric updates occur in canonical lifecycle completion paths rather than
   ad-hoc UI-triggered patches.
5. Focused tests prove both task and step metrics update correctly.

## Files To Change

- `dashboard/convex/lib/taskLifecycle.ts`
- `dashboard/convex/lib/taskLifecycle.test.ts`
- `dashboard/convex/steps.ts`
- `dashboard/convex/steps.test.ts`
- `dashboard/convex/agents.ts`

## Tasks / Subtasks

- [ ] Task 1: Update task completion metrics
  - [ ] 1.1 Find the canonical direct-task completion point
  - [ ] 1.2 Increment `tasksExecuted`
  - [ ] 1.3 Update `lastTaskExecutedAt`

- [ ] Task 2: Update step completion metrics
  - [ ] 2.1 Find the canonical workflow step completion point
  - [ ] 2.2 Increment `stepsExecuted`
  - [ ] 2.3 Update `lastStepExecutedAt`

- [ ] Task 3: Add focused regression tests
  - [ ] 3.1 Extend `taskLifecycle.test.ts`
  - [ ] 3.2 Extend `steps.test.ts`
  - [ ] 3.3 Prove direct-task and workflow-step metrics do not get conflated

## Dev Notes

- Do not collapse task and step counters into a single stored field in this
  story.
- Keep metric updates attached to lifecycle truth, not UI interactions.

## References

- [Source: `docs/plans/2026-03-17-lead-agent-direct-delegation-design.md`]
- [Source: `docs/plans/2026-03-17-lead-agent-direct-delegation-implementation-plan.md`]
