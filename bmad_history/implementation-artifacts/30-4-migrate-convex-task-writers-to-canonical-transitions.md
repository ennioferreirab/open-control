# Story 30.4: Migrate Convex Task Writers to Canonical Transitions

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want every Convex-side task lifecycle write to use the canonical task
transition kernel,
so that the dashboard and backend cannot keep mutating task state through
parallel ad-hoc paths.

## Overall Objective

Replace direct lifecycle patches in Convex mutations and helper modules with
calls to the task transition kernel introduced in Story 30.3.

## Acceptance Criteria

1. `taskStatus.ts`, `taskReview.ts`, `taskPlanning.ts`, `messages.ts`, and
   `interactiveSessions.ts` no longer patch `task.status` directly.
2. Every Convex-side lifecycle transition provides `expectedStateVersion`,
   `reason`, and `idempotencyKey` to the canonical task transition path.
3. Status-changing flows in `sendThreadMessage`, `postUserPlanMessage`,
   `approveAndKickOff`, pause/resume, retry, and interactive takeover/resume all
   use the same task transition contract.
4. There is a focused regression test for each migrated path proving it uses the
   canonical transition path and handles same-state or stale-state results
   explicitly.

## Files To Change

- `dashboard/convex/lib/taskStatus.ts:8-134`
- `dashboard/convex/lib/taskReview.ts:16-337`
- `dashboard/convex/lib/taskPlanning.ts:76-207`
- `dashboard/convex/messages.ts:286-364`
- `dashboard/convex/messages.ts:525-602`
- `dashboard/convex/interactiveSessions.ts:274-352`
- `dashboard/convex/tasks.ts`

## Tasks / Subtasks

- [ ] Task 1: Migrate task-status helper modules
  - [ ] 1.1 Replace direct patches in `taskStatus.ts`
  - [ ] 1.2 Replace direct patches in `taskReview.ts`
  - [ ] 1.3 Replace direct patches in `taskPlanning.ts`

- [ ] Task 2: Migrate thread-triggered lifecycle changes
  - [ ] 2.1 Update `postUserPlanMessage` reopening logic in `messages.ts`
  - [ ] 2.2 Update `sendThreadMessage` assignment logic in `messages.ts`
  - [ ] 2.3 Preserve message insertion order and thread behavior while moving
        status changes to the kernel

- [ ] Task 3: Migrate interactive-session lifecycle changes
  - [ ] 3.1 Update `requestHumanTakeover`
  - [ ] 3.2 Update `resumeAgentControl`
  - [ ] 3.3 Keep task and step transitions coordinated but routed through their
        canonical kernels

- [ ] Task 4: Add regression tests
  - [ ] 4.1 Extend `dashboard/convex/tasks.test.ts`
  - [ ] 4.2 Extend `dashboard/convex/messages.test.ts`
  - [ ] 4.3 Extend `dashboard/convex/interactiveSessions.test.ts`

## Dev Notes

- Archive, restore, and merge flows may still need follow-up stories if they
  remain legitimate exceptions; document any temporary exception explicitly.
- This story must not reintroduce direct `ctx.db.patch(taskId, { status: ... })`
  elsewhere while refactoring.

## References

- [Source: `docs/plans/2026-03-16-task-lifecycle-hardening-plan.md`]
- [Source: `dashboard/convex/lib/taskTransitions.ts` from Story 30.3]
