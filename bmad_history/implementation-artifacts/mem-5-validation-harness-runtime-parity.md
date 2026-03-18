# Story MEM.5: Validation Harness Runtime Parity

Status: ready-for-dev

## Story

As a **platform maintainer**,
I want the validation harness to reflect the real runtime behavior without polluting production workspaces,
so that validation results are trustworthy and do not create false negatives or unsafe side effects.

## Acceptance Criteria

### AC1: Validation mode uses the same post-execution hooks by default

**Given** `run_agent_validation.py` executes an agent scenario
**When** the harness builds its execution engine
**Then** it uses the same post-execution hook pipeline as the production runtime
**Or** it explicitly declares a named alternate mode that is covered by tests.

### AC2: Default validation is isolated from real workspaces

**Given** the validation harness runs in its default mode
**When** it prepares agent workspaces
**Then** it uses a temporary isolated workspace
**And** it does not mutate the user’s real `~/.nanobot` state.

### AC3: Real workspace access is explicit audit mode

**Given** an operator intentionally wants to validate against the real workspace
**When** the harness is run in audit mode
**Then** that mode is explicit in the command surface and in the report output
**And** it is not the default.

### AC4: Reports identify execution mode and meaning

**Given** a validation report is produced
**When** someone reads the result
**Then** the report identifies:
- whether production hooks were used,
- whether the workspace was isolated or real,
- whether missing history is a real failure or expected in the chosen mode.

### AC5: No silent false negatives remain

**Given** a scenario where production would consolidate
**When** the harness executes the equivalent flow
**Then** the result cannot silently report “no consolidation” unless the mode explicitly says that behavior is expected.

## Tasks / Subtasks

- [ ] Task 1: Freeze harness divergence in tests (AC: 1, 2, 3, 4, 5)
  - [ ] 1.1 Extend [`tests/test_run_agent_validation.py`](/Users/ennio/Documents/nanobot-ennio/tests/test_run_agent_validation.py) for isolated vs audit mode behavior.
  - [ ] 1.2 Add regression coverage proving whether production hooks are used.

- [ ] Task 2: Align engine construction with runtime (AC: 1, 5)
  - [ ] 2.1 Update [`scripts/run_agent_validation.py`](/Users/ennio/Documents/nanobot-ennio/scripts/run_agent_validation.py) to build the same execution pipeline as runtime code.
  - [ ] 2.2 Update [`mc/application/execution/engine.py`](/Users/ennio/Documents/nanobot-ennio/mc/application/execution/engine.py) only as needed to make hook configuration explicit and reusable.

- [ ] Task 3: Add isolated and audit mode semantics (AC: 2, 3, 4)
  - [ ] 3.1 Make isolated workspace mode the default.
  - [ ] 3.2 Make real-workspace execution an explicit audit mode.
  - [ ] 3.3 Ensure reports surface mode and interpretation clearly.

- [ ] Task 4: Verify trustworthiness (AC: 5)
  - [ ] 4.1 Run the focused validation test suite.
  - [ ] 4.2 Confirm expected consolidation behavior is visible in results.

## Dev Notes

- This story is about correctness and operator trust, not about adding new validation scenarios.
- Avoid mutating real agent memory during ordinary CI or local validation runs.
- Prefer reusing runtime factory code over duplicating engine construction logic in the script.

### Project Structure Notes

- Runtime wiring belongs in `mc/application/execution/`.
- The script should orchestrate modes and reporting, not reinvent execution semantics.

### References

- [Source: docs/plans/2026-03-11-memory-consolidation-backlog.md#Story-P1.2]
- [Source: docs/plans/2026-03-11-memory-consolidation-remediation-plan.md#AC6-Validation-Harness-Parity]
- [Source: /Users/ennio/Documents/nanobot-ennio/scripts/run_agent_validation.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/mc/application/execution/engine.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/mc/application/execution/post_processing.py]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
