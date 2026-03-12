# Story 22.1: Remove Backend Legacy Compatibility Packages

Status: ready-for-dev

## Story

As a **backend maintainer**,
I want the remaining backend compatibility packages removed from the root repository,
so that `mc.contexts/*`, `mc.runtime.workers`, and other canonical layers become the only supported ownership model.

## Acceptance Criteria

### AC1: Legacy Backend Compatibility Packages Deleted

**Given** the root repository still contains compatibility packages and facades
**When** this story completes
**Then** compatibility-only packages under `mc/ask_user`, `mc/mentions`, `mc/services`, and `mc/workers` are deleted
**And** no production imports remain from those packages.

### AC2: Canonical Backend Imports Become Mandatory

**Given** the documented architecture already defines canonical owners
**When** this story completes
**Then** backend call sites import from `mc.contexts/*`, `mc.runtime.workers`, `mc.bridge`, and other canonical packages only
**And** reexport-based fallback imports are removed.

### AC3: Backend Guardrails Match the Real Target

**Given** current backend architecture tests still tolerate transition-era roots
**When** this story completes
**Then** backend architecture tests fail if deleted compatibility packages are reintroduced
**And** module-reorganization tests assert canonical ownership without legacy aliases.

### AC4: Runtime and Conversation Behavior Remains Stable

**Given** these packages currently sit on execution, conversation, and worker paths
**When** this story completes
**Then** ask-user, mention handling, orchestrator workers, and conversation services preserve behavior
**And** no user-visible workflow regressions are introduced.

### AC5: Story Exit Gate Is Green

**Given** this story changes core backend imports and ownership
**When** the story closes
**Then** focused backend tests and the backend architecture guardrails pass
**And** `/code-review` is run
**And** a backend smoke verification is recorded before merge.

## Tasks / Subtasks

- [ ] **Task 1: Inventory and lock the legacy removals in tests** (AC: #1, #2, #3)
  - [ ] 1.1 Identify all production imports from `mc/ask_user`, `mc/mentions`, `mc/services`, and `mc/workers`
  - [ ] 1.2 Update architecture tests to treat those packages as removed roots
  - [ ] 1.3 Update module-reorganization tests to stop asserting compatibility behavior

- [ ] **Task 2: Remove conversation compatibility roots** (AC: #1, #2, #4)
  - [ ] 2.1 Rewrite imports to `mc.contexts.conversation.ask_user.*`
  - [ ] 2.2 Rewrite imports to `mc.contexts.conversation.mentions.*`
  - [ ] 2.3 Delete the legacy `mc/ask_user` and `mc/mentions` packages

- [ ] **Task 3: Remove runtime/service compatibility roots** (AC: #1, #2, #4)
  - [ ] 3.1 Rewrite imports to `mc.runtime.workers`
  - [ ] 3.2 Rewrite imports from `mc.services.*` to canonical context owners
  - [ ] 3.3 Delete the legacy `mc/services` and `mc/workers` packages

- [ ] **Task 4: Run the backend exit gate** (AC: #3, #4, #5)
  - [ ] 4.1 Run focused tests for conversation, orchestrator, gateway, and worker flows
  - [ ] 4.2 Run `uv run pytest tests/mc/test_architecture.py tests/mc/test_module_reorganization.py -q`
  - [ ] 4.3 Run `/code-review`
  - [ ] 4.4 Record the verification summary and remaining follow-ups if any

## Dev Notes

### Architecture Patterns

- This story is not a naming cleanup. It is the removal of double ownership in the backend.
- `mc.contexts/*` owns behavior. `mc.runtime` composes. `mc.bridge` owns backend Convex access.
- Do not replace deleted roots with new compatibility wrappers under different names.

### Project Structure Notes

- Root packages that exist only for compatibility should be deleted, not deprecated indefinitely.
- Update tests first so the removal target is explicit and regressions are caught immediately.

### References

- [Source: /Users/ennio/Documents/nanobot-ennio/docs/ARCHITECTURE.md]
- [Source: /Users/ennio/Documents/nanobot-ennio/tests/mc/test_architecture.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/tests/mc/test_module_reorganization.py]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
