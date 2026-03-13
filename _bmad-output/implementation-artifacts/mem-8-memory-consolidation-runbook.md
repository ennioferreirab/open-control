# Story MEM.8: Memory Consolidation Operational Runbook

Status: ready-for-dev

## Story

As an **operator and maintainer**,
I want a short operational runbook for memory cohesion checks,
so that I can declare the system coeso or não coeso using repeatable evidence instead of intuition.

## Acceptance Criteria

### AC1: There is a short runbook with binary operational outcomes

**Given** someone needs to inspect memory cohesion
**When** they use the runbook
**Then** it tells them how to decide “coeso” or “não coeso”
**And** it does so without requiring oral context from the author.

### AC2: The runbook covers the minimum agent matrix

**Given** the operational checks are executed
**When** the matrix is followed
**Then** it includes at least:
- the shared `nanobot`,
- one `cc/...` agent,
- one `clean` board case,
- one `with_history` board case,
- one board-scoped artifact reuse case.

### AC3: Storage, index, session, and artifact checks are included

**Given** the runbook is used for diagnosis
**When** the operator follows it
**Then** it includes commands or checks for:
- `MEMORY.md`,
- `HISTORY.md`,
- `memory-index.sqlite`,
- SQLite sidecars,
- session JSONL state,
- board-scoped `artifacts/`.

### AC4: Trigger observability is part of the inspection

**Given** a consolidation event was executed or skipped
**When** the operator inspects the runbook output
**Then** they can see how to read:
- the trigger that fired,
- the boundary reason,
- the resolved workspaces,
- whether the action consolidated or skipped,
- which files were touched.

### AC5: The validation harness supports the runbook

**Given** the runbook references validation flows
**When** those flows are used
**Then** the validation harness supports the documented mode and interpretation.

## Tasks / Subtasks

- [ ] Task 1: Define the operational checklist surface (AC: 1, 2, 3, 4)
  - [ ] 1.1 Enumerate the minimum inspection matrix and expected pass/fail signals.
  - [ ] 1.2 Document the exact files, logs, and runtime signals to inspect.

- [ ] Task 2: Write the runbook document (AC: 1, 2, 3, 4)
  - [ ] 2.1 Create [`docs/memory-consolidation-runbook.md`](/Users/ennio/Documents/nanobot-ennio/docs/memory-consolidation-runbook.md).
  - [ ] 2.2 Keep the document short, executable, and binary in outcome.

- [ ] Task 3: Align harness references (AC: 5)
  - [ ] 3.1 Update [`scripts/run_agent_validation.py`](/Users/ennio/Documents/nanobot-ennio/scripts/run_agent_validation.py) or its docs only as needed so the runbook matches real commands and modes.
  - [ ] 3.2 Add or extend tests in [`tests/test_run_agent_validation.py`](/Users/ennio/Documents/nanobot-ennio/tests/test_run_agent_validation.py) for documented mode expectations.

- [ ] Task 4: Verify the runbook can be followed cold (AC: 1, 2, 3, 4, 5)
  - [ ] 4.1 Run the focused validation tests.
  - [ ] 4.2 Confirm the written runbook is sufficient without hidden context.

## Dev Notes

- The runbook is the operational closing loop for the whole remediation set.
- Keep it concrete: commands, expected files, expected signals, pass/fail criteria.
- Do not turn it into a long architecture essay.

### Project Structure Notes

- Operational guidance belongs under `docs/`.
- Validation command parity must stay aligned with the harness story.

### References

- [Source: docs/plans/2026-03-11-memory-consolidation-backlog.md#Story-P2.1]
- [Source: docs/plans/2026-03-11-memory-consolidation-remediation-plan.md#Task-7-Verificação-operacional-com-amostragem-real-de-agentes]
- [Source: /Users/ennio/Documents/nanobot-ennio/scripts/run_agent_validation.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/tests/test_run_agent_validation.py]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
