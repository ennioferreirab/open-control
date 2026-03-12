# Story 23.4: Trim Backend Runtime Compat Seams Left from Convergence

Status: done

## Story

As a **backend maintainer**,
I want the remaining runtime compatibility seams reduced where they no longer buy us anything,
so that the backend keeps moving toward smaller owners without reintroducing transitional facades.

## Acceptance Criteria

### AC1: Gateway Keeps Only Necessary Runtime Ownership

**Given** `mc/runtime/gateway.py` still carries compatibility and composition residue
**When** this story completes
**Then** gateway retains only runtime entrypoint and coordination responsibilities
**And** unnecessary compatibility exports or embedded helper logic are removed or delegated.

### AC2: Orchestrator Stops Carrying Transitional Delegation Wrappers

**Given** some orchestrator helper methods still exist only to preserve a transitional API shape
**When** this story completes
**Then** wrappers that no longer provide real value are removed
**And** worker ownership remains explicit.

### AC3: Current Main Improvements Are Preserved

**Given** the convergence worktree also contains backend regressions in some areas
**When** this story completes
**Then** the cleanup is taken selectively from the useful runtime simplifications only
**And** the current smaller `mc/cli/*` structure, test coverage, and root architecture remain intact.

### AC4: Backend Architecture Tests Stay Honest

**Given** backend cleanup can silently reintroduce cross-module coupling
**When** this story completes
**Then** backend architecture/reorganization tests reflect the new runtime seams
**And** focused runtime/orchestrator tests cover the touched paths.

### AC5: Story Exit Gate Is Green

**Given** this story changes backend runtime flow
**When** the story closes
**Then** focused backend suites and backend architecture tests pass
**And** `/code-review` is run
**And** verification evidence is recorded.

## Tasks / Subtasks

- [ ] **Task 1: Audit runtime compatibility residue** (AC: #1, #2, #3)
  - [ ] 1.1 Identify gateway logic that is still present only for transitional API reasons
  - [ ] 1.2 Identify orchestrator wrappers that only mirror worker owners
  - [ ] 1.3 Explicitly exclude backend regressions from the convergence worktree, especially around `mc/cli/*`

- [ ] **Task 2: Trim the runtime seams selectively** (AC: #1, #2, #3)
  - [ ] 2.1 Remove or delegate unnecessary gateway compatibility seams
  - [ ] 2.2 Remove orchestrator delegation wrappers that no longer carry real ownership
  - [ ] 2.3 Keep runtime helper modules and canonical worker ownership explicit

- [ ] **Task 3: Tighten tests and guardrails** (AC: #4, #5)
  - [ ] 3.1 Update focused gateway/orchestrator tests as needed
  - [ ] 3.2 Run backend architecture and module reorganization guardrails
  - [ ] 3.3 Run `/code-review`

- [ ] **Task 4: Run the story exit gate** (AC: #5)
  - [ ] 4.1 Run focused backend runtime/orchestrator tests
  - [ ] 4.2 Run `uv run pytest tests/mc/test_architecture.py tests/mc/test_module_reorganization.py`
  - [ ] 4.3 Record verification evidence and residual risks

## Dev Notes

### Architecture Patterns

- Keep `mc/runtime/*` as composition and loop ownership only.
- Remove compatibility only when tests prove the public seam is no longer needed.
- Do not reintroduce monolithic module shapes while cleaning compatibility residue.

### Project Structure Notes

- Primary targets:
  - `/Users/ennio/Documents/nanobot-ennio/mc/runtime/gateway.py`
  - `/Users/ennio/Documents/nanobot-ennio/mc/runtime/orchestrator.py`
- Preserve the current split owners under:
  - `mc/runtime/*`
  - `mc/contexts/execution/*`
  - `mc/cli/*`

### References

- [Source: /Users/ennio/Documents/nanobot-ennio/mc/runtime/gateway.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/mc/runtime/orchestrator.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/tests/mc/test_architecture.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/tests/mc/test_module_reorganization.py]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
