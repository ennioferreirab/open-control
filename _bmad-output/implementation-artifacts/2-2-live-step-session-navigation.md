# Story 2.2: Live Step and Session Navigation

Status: ready-for-dev

## Story

As an operator,
I want to switch between active and historical Live steps,
so that I can inspect completed Live runs without losing the default active Live context.

## Acceptance Criteria

1. The `Live` tab renders a selector containing all active and historical Live choices for the task.
2. The default selected choice remains the currently active Live session when one exists.
3. Completed and failed step sessions with persisted Live history can be opened from the selector.
4. Task-level sessions remain available for direct agent-assigned tasks without step-scoped Live data.
5. Existing execution-plan affordances that open historical Live output still work and sync with the selector state.

## Tasks / Subtasks

- [ ] Task 1: Extend the hook view-model for navigable Live choices (AC: #1, #2, #3, #4)
  - [ ] 1.1 Add a typed `liveChoices` model in `dashboard/features/interactive/hooks/useTaskInteractiveSession.ts`
  - [ ] 1.2 Preserve the current active-step priority rules for the default choice
  - [ ] 1.3 Include historical ended/error step sessions and task-level sessions in the returned choice list
  - [ ] 1.4 Cover ordering and fallback behavior in `dashboard/features/interactive/hooks/useTaskInteractiveSession.test.ts`

- [ ] Task 2: Wire selector state into `TaskDetailSheet` (AC: #1, #2, #5)
  - [ ] 2.1 Replace the implicit `selectedLiveStepId`-only flow with selector-driven state that can represent step or task-level sessions
  - [ ] 2.2 Render the selector in the `Live` tab header area without removing the current default-open behavior
  - [ ] 2.3 Ensure `handleOpenLive(stepId)` still opens the requested historical step and updates the selector choice

- [ ] Task 3: Add integration coverage in the sheet tests (AC: #1, #3, #4, #5)
  - [ ] 3.1 Extend `dashboard/components/TaskDetailSheet.test.tsx` with selector coverage for active and historical choices
  - [ ] 3.2 Verify direct task-level sessions still show a usable `Live` tab

## Dev Notes

### Why this story exists

The hook already knows how to find active and historical sessions, but the `Live` tab UI does not expose that model directly. This story turns that hidden capability into an explicit operator control.

### Expected Files

| File | Change |
|------|--------|
| `dashboard/features/interactive/hooks/useTaskInteractiveSession.ts` | Return navigable session/step choices |
| `dashboard/features/interactive/hooks/useTaskInteractiveSession.test.ts` | Cover ordering/default selection/history |
| `dashboard/features/tasks/components/TaskDetailSheet.tsx` | Render and control the Live selector |
| `dashboard/components/TaskDetailSheet.test.tsx` | Integration tests for selector behavior |

### Technical Constraints

- Keep `Live` defaulting to the current active session to match the existing mental model.
- Avoid breaking direct-task sessions that have no `stepId`.
- Keep selector logic in hooks/view-models; do not fetch Convex directly from presentational components outside established patterns.

### Testing Guidance

- Follow `agent_docs/running_tests.md`.
- Prefer hook tests for ordering/selection rules and component tests for the actual selector behavior.

### References

- [Source: AGENTS.md]
- [Source: agent_docs/code_conventions/typescript.md]
- [Source: agent_docs/running_tests.md]
- [Source: dashboard/features/interactive/hooks/useTaskInteractiveSession.ts]
- [Source: dashboard/features/tasks/components/TaskDetailSheet.tsx]
- [Source: dashboard/components/TaskDetailSheet.test.tsx]

## Dev Agent Record

### Agent Model Used

TBD

### Debug Log References

### Completion Notes List

### File List
