# Epic 30: Task Lifecycle Hardening Story Map

Status: ready-for-planning

## Goal

Break the lifecycle hardening plan into implementation-ready BMad stories with
explicit scope, file targets, and sequencing.

## Recommended Delivery Order

Stories `30.1` through `30.7` are the minimum safe cut.

1. `30.1` Make review meaning explicit and remove the manual no-plan review
   bootstrap
2. `30.2` Harden pause, resume, and final approval review behavior
3. `30.3` Introduce canonical task transitions with `stateVersion`
4. `30.4` Move Convex-side task writers to the canonical task transition path
5. `30.5` Move Python-side task writers to the canonical task transition path
6. `30.6` Introduce canonical step transitions and remove parent-task
   reconciliation from `steps.ts`
7. `30.7` Add persistent runtime claims and idempotency receipts
8. `30.8` Make polling workers claim-aware and remove process-local dedupe as a
   correctness mechanism
9. `30.9` Stop mirroring live runtime state into `executionPlan`

## Story Inventory

### Story 30.1: Make Review Phase Explicit and Remove Manual Bootstrap from Review

- Overall objective: replace implicit `review` meaning with explicit
  `reviewPhase`, and stop using `review` for manual tasks that do not yet have a
  real execution plan.
- Primary files:
  - `dashboard/convex/schema.ts`
  - `mc/types.py`
  - `dashboard/convex/lib/readModels.ts`
  - `mc/runtime/workers/planning.py`
  - `mc/contexts/planning/negotiation.py`
  - `mc/contexts/conversation/intent.py`

### Story 30.2: Harden Review Actions and Final Review Routing

- Overall objective: make `pause`, `resume`, and `approve` mutually coherent and
  ensure planned tasks that complete all steps still go through real final
  review routing.
- Primary files:
  - `dashboard/convex/lib/taskStatus.ts`
  - `dashboard/convex/lib/taskReview.ts`
  - `mc/runtime/workers/review.py`
  - `mc/contexts/execution/step_dispatcher.py`
  - `mc/contexts/conversation/ask_user/handler.py`
  - `mc/contexts/interactive/supervisor.py`

### Story 30.3: Add Canonical Task Transition Kernel with CAS

- Overall objective: create a single compare-and-set transition path for
  `task.status`, `reviewPhase`, and `stateVersion`.
- Primary files:
  - `dashboard/convex/schema.ts`
  - `dashboard/convex/lib/taskTransitions.ts`
  - `dashboard/convex/tasks.ts`
  - `dashboard/convex/lib/taskLifecycle.ts`
  - `dashboard/convex/lib/taskMetadata.ts`

### Story 30.4: Migrate Convex Task Writers to Canonical Transitions

- Overall objective: remove direct lifecycle patches from Convex-side task
  helpers and mutations.
- Primary files:
  - `dashboard/convex/lib/taskStatus.ts`
  - `dashboard/convex/lib/taskReview.ts`
  - `dashboard/convex/lib/taskPlanning.ts`
  - `dashboard/convex/messages.ts`
  - `dashboard/convex/interactiveSessions.ts`

### Story 30.5: Migrate Python Task Writers to Canonical Transitions

- Overall objective: make runtime workers and services call the new task
  transition contract instead of plain `tasks:updateStatus`.
- Primary files:
  - `mc/bridge/repositories/tasks.py`
  - `mc/bridge/facade_mixins.py`
  - `mc/runtime/workers/inbox.py`
  - `mc/runtime/workers/planning.py`
  - `mc/runtime/workers/kickoff.py`
  - `mc/contexts/execution/executor.py`
  - `mc/contexts/execution/step_dispatcher.py`

### Story 30.6: Add Canonical Step Transition Kernel and Remove Parent Reconcile

- Overall objective: give `steps` the same CAS transition discipline and stop
  letting child-step code rewrite the parent task lifecycle directly.
- Primary files:
  - `dashboard/convex/schema.ts`
  - `dashboard/convex/lib/stepTransitions.ts`
  - `dashboard/convex/steps.ts`
  - `mc/contexts/interaction/service.py`
  - `mc/contexts/conversation/ask_user/handler.py`
  - `mc/contexts/interactive/supervisor.py`

### Story 30.7: Add Runtime Claims and Idempotency Receipts

- Overall objective: make retries and concurrent workers safe by persisting work
  claims and effect receipts in Convex.
- Primary files:
  - `dashboard/convex/schema.ts`
  - `dashboard/convex/runtimeClaims.ts`
  - `dashboard/convex/runtimeReceipts.ts`
  - `dashboard/convex/messages.ts`
  - `dashboard/convex/activities.ts`
  - `mc/bridge/__init__.py`

### Story 30.8: Make Polling Workers Claim-Aware

- Overall objective: keep polling temporarily, but stop relying on `_known_*`,
  `_seen_*`, and `_processed_*` sets as correctness boundaries.
- Primary files:
  - `mc/runtime/orchestrator.py`
  - `mc/runtime/workers/inbox.py`
  - `mc/runtime/workers/planning.py`
  - `mc/runtime/workers/review.py`
  - `mc/runtime/workers/kickoff.py`
  - `mc/contexts/conversation/mentions/watcher.py`

### Story 30.9: Stop Mirroring Live Runtime State into Execution Plan

- Overall objective: keep `executionPlan` as desired structure only and derive
  live progress from `steps`.
- Primary files:
  - `dashboard/convex/steps.ts`
  - `dashboard/convex/lib/taskLifecycle.ts`
  - `dashboard/features/tasks/components/TaskCard.tsx`
  - `dashboard/features/tasks/components/ExecutionPlanTab.tsx`
  - `dashboard/features/tasks/hooks/useTaskDetailView.ts`

## References

- [Source: `docs/plans/2026-03-16-task-lifecycle-hardening-plan.md`]
- [Source: `_bmad-output/planning-artifacts/2026-03-16-task-convex-rigidity-report.md`]
- [Source: `_bmad-output/planning-artifacts/2026-03-16-runtime-state-capture-and-race-report.md`]
- [Source: `_bmad-output/planning-artifacts/2026-03-16-task-usercase-flow-map.md`]
