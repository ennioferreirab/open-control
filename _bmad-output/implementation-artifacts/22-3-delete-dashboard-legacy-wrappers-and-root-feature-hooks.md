# Story 22.3: Delete Dashboard Legacy Wrappers and Root Feature Hooks

Status: ready-for-dev

## Story

As a **frontend maintainer**,
I want root wrappers and root feature hooks removed wherever ownership is already clear,
so that `dashboard/features/*` becomes the real workflow architecture instead of a parallel architecture.

## Acceptance Criteria

### AC1: Feature-Owned Root Wrappers Are Deleted

**Given** many root files under `dashboard/components/*` still act as feature aliases
**When** this story completes
**Then** files that are clearly feature-owned are deleted from the root component layer
**And** imports are rewritten to canonical feature paths.

### AC2: Root Hooks Stop Mirroring Feature Ownership

**Given** `dashboard/hooks/*` still contains hooks that are effectively feature-owned
**When** this story completes
**Then** those hooks are moved or deleted in favor of `dashboard/features/*/hooks`
**And** root hooks retain only truly shared, non-feature utilities.

### AC3: Shared Root Surface Is Explicitly Curated

**Given** root `components/*` still serves valid shared roles
**When** this story completes
**Then** the remaining root surface is limited to shell components, shared widgets, `components/ui`, `components/viewers`, and other genuinely cross-feature modules
**And** the architecture documentation and tests reflect that distinction.

### AC4: Dashboard Shell Uses Canonical Entry Points

**Given** `DashboardLayout` is supposed to be a shell
**When** this story completes
**Then** `DashboardLayout` composes feature entry points directly
**And** it no longer pulls workflow owners through root aliases.

### AC5: Story Exit Gate Is Green

**Given** this story rewrites imports across the dashboard shell
**When** the story closes
**Then** lint, typecheck, targeted tests, and architecture tests pass
**And** `/code-review` is run
**And** Playwright smoke validates the shell-level flows touched by the cleanup.

## Tasks / Subtasks

- [ ] **Task 1: Classify root dashboard modules by ownership** (AC: #1, #2, #3)
  - [ ] 1.1 Identify root components that are wrappers or feature-owned aliases
  - [ ] 1.2 Identify root hooks that mirror feature hooks rather than shared utilities
  - [ ] 1.3 Capture the keep/delete split before editing imports

- [ ] **Task 2: Delete root feature wrappers** (AC: #1, #4)
  - [ ] 2.1 Rewrite imports from root component aliases to canonical feature paths
  - [ ] 2.2 Delete root wrapper files that no longer own shared behavior
  - [ ] 2.3 Keep only truly shared shell and widget modules at the root

- [ ] **Task 3: Delete root feature hooks** (AC: #2, #4)
  - [ ] 3.1 Rewrite imports from `dashboard/hooks/*` to canonical feature hooks
  - [ ] 3.2 Delete root hooks that only proxy or duplicate feature-owned behavior
  - [ ] 3.3 Preserve only justified shared hooks at the root

- [ ] **Task 4: Tighten docs and guardrails** (AC: #3, #4, #5)
  - [ ] 4.1 Update dashboard architecture tests to forbid reintroduction of deleted wrappers
  - [ ] 4.2 Update `docs/ARCHITECTURE.md` if the shared-root description changes materially
  - [ ] 4.3 Run `/code-review`

- [ ] **Task 5: Run the dashboard exit gate** (AC: #5)
  - [ ] 5.1 Run `npm run lint`
  - [ ] 5.2 Run `npm run typecheck`
  - [ ] 5.3 Run focused frontend tests and `npm run test:architecture`
  - [ ] 5.4 Run Playwright smoke for board, task sheet, settings, search, and agents flows

## Dev Notes

### Architecture Patterns

- Root `dashboard/components/*` is allowed to exist, but only as a curated shared layer.
- Root `dashboard/hooks/*` is suspicious by default and must justify being cross-feature.
- Delete aliases once imports are rewritten. Do not leave “temporary” wrappers behind.

### Project Structure Notes

- Canonical workflow owners live under `dashboard/features/*`.
- Preserve `components/ui/*` and `components/viewers/*` as shared primitives.

### References

- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/features/README.md]
- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/tests/architecture.test.ts]
- [Source: /Users/ennio/Documents/nanobot-ennio/docs/ARCHITECTURE.md]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
