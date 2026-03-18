# Story 30.8: Make Polling Workers Claim-Aware

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want polling workers and watchers to claim work in Convex before acting,
so that process-local dedupe sets stop being correctness boundaries.

## Overall Objective

Keep polling temporarily, but change workers and watchers to acquire persistent
claims before performing side effects, with in-memory dedupe retained only as an
optional optimization.

## Acceptance Criteria

1. Inbox, planning, review, kickoff, executor, plan-negotiation, mention, and
   ask-user watcher flows claim work before producing side effects.
2. `_known_*`, `_seen_*`, and `_processed_*` sets are no longer required for
   correctness.
3. Worker restarts or parallel runtimes do not duplicate covered lifecycle side
   effects in focused tests.
4. Timeout checking and review escalation are also claim-aware or explicitly
   documented as remaining follow-up work.

## Files To Change

- `mc/runtime/orchestrator.py:168-256`
- `mc/runtime/workers/inbox.py:23-39`
- `mc/runtime/workers/planning.py:49-63`
- `mc/runtime/workers/review.py:35-46`
- `mc/runtime/workers/kickoff.py:46-79`
- `mc/contexts/execution/executor.py:156-270`
- `mc/contexts/planning/supervisor.py:45-147`
- `mc/contexts/conversation/mentions/watcher.py:66-187`
- `mc/contexts/conversation/ask_user/watcher.py:32-135`
- `mc/runtime/timeout_checker.py:58-108`

## Tasks / Subtasks

- [ ] Task 1: Add claim acquisition to task workers
  - [ ] 1.1 Inbox worker
  - [ ] 1.2 Planning worker
  - [ ] 1.3 Review worker
  - [ ] 1.4 Kickoff worker
  - [ ] 1.5 Assigned-task executor

- [ ] Task 2: Add claim acquisition to message and plan watchers
  - [ ] 2.1 Mention watcher
  - [ ] 2.2 Ask-user watcher
  - [ ] 2.3 Plan-negotiation supervisor/loops

- [ ] Task 3: Demote local dedupe to optimization only
  - [ ] 3.1 Remove correctness assumptions around `_known_*`
  - [ ] 3.2 Remove correctness assumptions around `_seen_*`
  - [ ] 3.3 Remove correctness assumptions around `_processed_signatures`

- [ ] Task 4: Add focused tests
  - [ ] 4.1 Extend `tests/mc/runtime/test_inbox_worker_ai_workflow.py`
  - [ ] 4.2 Extend `tests/mc/runtime/test_planning_worker_ai_workflow.py`
  - [ ] 4.3 Extend `tests/mc/services/test_conversation_gateway_integration.py`
  - [ ] 4.4 Add restart/duplicate-processing regression tests where coverage is
        currently missing

## Dev Notes

- This story depends on Story 30.7. Do not start it before persistent claims
  exist.
- If a worker keeps an in-memory set after this story, that set must only be a
  best-effort optimization and never the final dedupe barrier.

## References

- [Source: `docs/plans/2026-03-16-task-lifecycle-hardening-plan.md`]
- [Source: `dashboard/convex/runtimeClaims.ts` from Story 30.7]
