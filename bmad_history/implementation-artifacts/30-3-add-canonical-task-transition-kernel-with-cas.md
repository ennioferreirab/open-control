# Story 30.3: Add Canonical Task Transition Kernel with CAS

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want every task lifecycle transition to pass through a compare-and-set
transition kernel,
so that stale snapshots and concurrent writers cannot silently overwrite the
task state.

## Overall Objective

Add `stateVersion` to tasks and create a canonical transition helper and
mutation that owns `status`, `reviewPhase`, and lifecycle event logging.

## Acceptance Criteria

1. The `tasks` schema has `stateVersion: number`, initialized for all newly
   created tasks.
2. A new `dashboard/convex/lib/taskTransitions.ts` module validates task
   transitions, increments `stateVersion`, and emits lifecycle side effects.
3. A canonical internal mutation `tasks:transition` accepts at least:
   `taskId`, `fromStatus`, `expectedStateVersion`, `toStatus`, `reviewPhase`,
   `reason`, and `idempotencyKey`.
4. Stale or repeated transitions return explicit conflict or no-op semantics
   instead of silently patching the task anyway.
5. `tasks:updateStatus` becomes a thin compatibility wrapper or is clearly
   deprecated behind the new transition kernel.

## Files To Change

- `dashboard/convex/schema.ts:108-199`
  - Add `stateVersion` to tasks
- `dashboard/convex/lib/taskTransitions.ts`
  - New canonical task transition kernel
- `dashboard/convex/tasks.ts:456-585`
  - Add `tasks:transition` and deprecate raw status mutation entry points
- `dashboard/convex/lib/taskLifecycle.ts:23-225`
  - Reuse or refactor transition validation and event mapping
- `dashboard/convex/lib/taskMetadata.ts:27-80`
  - Initialize `stateVersion` on task creation
- `dashboard/convex/lib/squadMissionLaunch.ts`
  - Initialize `stateVersion` for launched workflow tasks

## Tasks / Subtasks

- [ ] Task 1: Add `stateVersion` to task creation paths
  - [ ] 1.1 Update normal task creation in `taskMetadata.ts`
  - [ ] 1.2 Update mission launch and merge-task creation paths
  - [ ] 1.3 Add schema tests proving the field exists and starts at `1`

- [ ] Task 2: Create the canonical transition kernel
  - [ ] 2.1 Create `dashboard/convex/lib/taskTransitions.ts`
  - [ ] 2.2 Move transition validation into the kernel
  - [ ] 2.3 Make the kernel increment `stateVersion` atomically
  - [ ] 2.4 Make the kernel own lifecycle activity/log generation

- [ ] Task 3: Expose the kernel through `tasks:transition`
  - [ ] 3.1 Add the new internal mutation in `dashboard/convex/tasks.ts`
  - [ ] 3.2 Define explicit conflict/no-op return shapes
  - [ ] 3.3 Route `tasks:updateStatus` through the kernel as a compatibility
        path if it must remain temporarily

- [ ] Task 4: Add focused tests
  - [ ] 4.1 Extend `dashboard/convex/tasks.test.ts`
  - [ ] 4.2 Add CAS conflict coverage
  - [ ] 4.3 Add same-transition idempotent no-op coverage

## Dev Notes

- This story is not the migration of all writers. It only establishes the
  canonical contract.
- Do not leave a second code path that can still patch `tasks.status` and
  bypass `stateVersion`.
- Keep board-level statuses stable; this story changes ownership, not product
  semantics.

## References

- [Source: `docs/plans/2026-03-16-task-lifecycle-hardening-plan.md`]
- [Source: `_bmad-output/planning-artifacts/2026-03-16-task-convex-rigidity-report.md`]
