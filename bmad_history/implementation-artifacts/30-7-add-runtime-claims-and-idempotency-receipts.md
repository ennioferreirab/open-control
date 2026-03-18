# Story 30.7: Add Runtime Claims and Idempotency Receipts

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want worker claims and side-effect receipts persisted in Convex,
so that retries, restarts, and concurrent loops do not duplicate lifecycle
effects.

## Overall Objective

Add persistent `runtimeClaims` and `runtimeReceipts` tables plus idempotency-key
support across task transitions, step transitions, messages, and activities.

## Acceptance Criteria

1. Convex has persistent storage for runtime claims with lease expiration.
2. Convex has persistent storage for idempotency receipts keyed by
   `idempotencyKey`.
3. `messages:create`, `messages:postStepCompletion`,
   `messages:postLeadAgentMessage`, task transitions, step transitions, and
   `activities:create` can all reuse an idempotency key safely.
4. Bridge retry logic reuses the same idempotency key on every attempt instead
   of regenerating side effects.
5. Focused tests prove duplicate retries do not create duplicate messages,
   activities, or lifecycle transitions.

## Files To Change

- `dashboard/convex/schema.ts`
- `dashboard/convex/runtimeClaims.ts`
- `dashboard/convex/runtimeReceipts.ts`
- `dashboard/convex/messages.ts:125-203`
- `dashboard/convex/messages.ts:243-273`
- `dashboard/convex/messages.ts:472-602`
- `dashboard/convex/activities.ts`
- `dashboard/convex/tasks.ts`
- `dashboard/convex/steps.ts`
- `mc/bridge/__init__.py:95-134`
- `mc/bridge/repositories/messages.py:34-166`
- `mc/bridge/repositories/tasks.py:26-90`
- `mc/bridge/repositories/steps.py:59-91`

## Tasks / Subtasks

- [ ] Task 1: Add persistent claim and receipt tables
  - [ ] 1.1 Add schema definitions for `runtimeClaims`
  - [ ] 1.2 Add schema definitions for `runtimeReceipts`
  - [ ] 1.3 Add minimal CRUD/claim helpers in Convex

- [ ] Task 2: Add idempotency support to write-heavy Convex mutations
  - [ ] 2.1 Update message mutations
  - [ ] 2.2 Update activity creation
  - [ ] 2.3 Update task and step transition entry points

- [ ] Task 3: Make bridge retry reuse keys
  - [ ] 3.1 Update `mc/bridge/__init__.py`
  - [ ] 3.2 Thread idempotency keys through repository methods
  - [ ] 3.3 Preserve deterministic behavior across retries

- [ ] Task 4: Add focused tests
  - [ ] 4.1 Extend `dashboard/convex/messages.test.ts`
  - [ ] 4.2 Extend `dashboard/convex/tasks.test.ts`
  - [ ] 4.3 Extend `dashboard/convex/steps.test.ts`
  - [ ] 4.4 Extend `tests/mc/bridge/test_retry.py`

## Dev Notes

- Claims and receipts are infrastructure stories, not UI stories.
- This story must not depend on workers already being claim-aware; it only
  establishes the persistent primitives and idempotent write paths.

## References

- [Source: `docs/plans/2026-03-16-task-lifecycle-hardening-plan.md`]
- [Source: `_bmad-output/planning-artifacts/2026-03-16-runtime-state-capture-and-race-report.md`]
