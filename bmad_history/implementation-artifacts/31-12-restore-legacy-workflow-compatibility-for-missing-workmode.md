# Story 31.12: Restore Legacy Workflow Compatibility for Missing Work Mode

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want legacy workflow tasks without `workMode` to keep workflow behavior,
so that existing tasks do not lose plan review and plan-chat affordances.

## Overall Objective

Introduce a safe compatibility layer and backfill strategy for old workflow
tasks whose documents predate the `workMode` contract.

## Acceptance Criteria

1. Legacy tasks that clearly belong to workflow execution retain workflow-only
   behavior even if `workMode` is absent.
2. Direct-delegate and manual legacy tasks without `workMode` are not
   incorrectly reclassified as workflow.
3. Task detail and conversation intent use the same compatibility rule for
   workflow detection.
4. A one-time backfill or lazy-persist strategy exists to stamp
   `workMode="ai_workflow"` onto qualifying legacy tasks.
5. Focused tests cover workflow legacy tasks, non-workflow legacy tasks, and
   post-backfill behavior.

## Files To Change

- `mc/contexts/conversation/intent.py`
- `tests/mc/contexts/conversation/test_intent.py`
- `dashboard/convex/lib/taskDetailView.ts`
- `dashboard/convex/lib/taskDetailView.test.ts`
- `dashboard/convex/tasks.ts`
- `dashboard/convex/lib/readModels.ts`

## Tasks / Subtasks

- [ ] Task 1: Define a shared legacy-workflow compatibility rule
  - [ ] 1.1 Detect workflow ownership from durable task evidence
  - [ ] 1.2 Reuse the rule in task-detail and conversation intent
  - [ ] 1.3 Keep non-workflow legacy tasks on normal thread behavior

- [ ] Task 2: Add a backfill path
  - [ ] 2.1 Choose a safe write path for qualifying legacy tasks
  - [ ] 2.2 Avoid stamping `ai_workflow` onto ambiguous tasks
  - [ ] 2.3 Keep new-task behavior unchanged

- [ ] Task 3: Add regression coverage
  - [ ] 3.1 Prove legacy workflow tasks still surface workflow affordances
  - [ ] 3.2 Prove legacy non-workflow tasks stay non-workflow
  - [ ] 3.3 Prove backfilled tasks behave like first-class `ai_workflow`

## Dev Notes

- Prefer explicit evidence such as workflow-generated execution-plan metadata
  over heuristic status-only guesses.
- If no production legacy data exists, the backfill path can still be valuable
  as a defensive migration for restored backups and imported tasks.

## References

- [Source: review findings on March 17, 2026]
- [Source: `31-4-scope-planning-and-plan-chat-to-workflow.md`]
- [Source: `31-6-scope-task-detail-plan-review-ui-to-workflow.md`]

