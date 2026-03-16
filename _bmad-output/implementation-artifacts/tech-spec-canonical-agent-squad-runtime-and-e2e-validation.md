# Story: Canonical Agent Squad Runtime And E2E Validation

Status: ready-for-dev

## Story

As a Mission Control user,
I want squad mission launch and runtime dispatch to resolve directly from
registered agents,
so that squad execution stays coherent with the same global agents used in
creation and editing.

## Problems Found

- `launchSquadMission` currently builds runtime agent refs from
  `squadSpec.agentSpecIds`, not from the canonical `agents` registry.
- workflow execution still depends on the intermediate `agentSpecId ->
  agentName` translation path.
- there is no final backend-only end-to-end proof that a real user flow works
  without mocks after the canonical-agent refactor.

## Solution

Switch mission launch and workflow compilation to canonical agents:

- squad launch resolves `squad.agentIds`
- workflow agent steps resolve `agentId -> agent.name`
- missing registered agents fail fast
- add a backend-only real end-to-end test that simulates a user creating or
  using a squad flow without mocks in the final verification step

## Acceptance Criteria

1. `launchSquadMission` loads agents from `squad.agentIds`.
2. Workflow compilation resolves `agentId` directly to the runtime
   `assignedAgent` or agent reference payload.
3. Launch fails with a clear error when a workflow step references an agent id
   that is not registered.
4. Existing Python runtime coverage for squad workflow dispatch is updated to
   the canonical-agent model.
5. The final verification includes a backend-only, no-mocks, end-to-end test
   that simulates a real user flow and proves the canonical agent path works.

## Tasks / Subtasks

- [ ] Task 1: Update squad mission launch to resolve agents from `agentIds`
- [ ] Task 2: Update workflow execution compilation to use `agentId`
- [ ] Task 3: Update Python runtime tests for canonical-agent squad dispatch
- [ ] Task 4: Add a backend-only no-mocks end-to-end test for the user flow
- [ ] Task 5: Run real verification with Python commands and capture evidence

## Dev Notes

- Keep the validation backend-only for the final proof; no frontend browser
  flow is required.
- Do not rely on mocks for the last end-to-end verification step.
- Prefer a user-level flow that exercises real persistence and runtime
  resolution over isolated helper-unit behavior.
- If an existing “real” test harness exists in Python, extend it instead of
  creating another custom path.

### Project Structure Notes

- Convex mission launch and workflow compilation stay under `dashboard/convex/`
- Python runtime verification stays under `tests/mc/`
- preserve architecture boundaries documented in `docs/ARCHITECTURE.md`

### References

- [Source: docs/plans/2026-03-15-agent-squad-unification-design.md]
- [Source: docs/plans/2026-03-15-agent-squad-unification-implementation-plan.md]
- [Source: dashboard/convex/lib/squadMissionLaunch.ts]
- [Source: dashboard/convex/lib/workflowExecutionCompiler.ts]
- [Source: tests/mc/runtime/test_squad_workflow_dispatch.py]
- [Source: docs/ARCHITECTURE.md]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
