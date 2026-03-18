# Story 23.3: Decouple Board and Thread Shell State from Root Components

Status: done

## Story

As a **frontend maintainer**,
I want board and thread shell state moved behind clearer feature hooks and typed local contracts,
so that root shell components stop coupling directly to data sources and ad hoc UI state conventions.

## Acceptance Criteria

### AC1: BoardProvider Stops Owning Data Fetching Directly

**Given** `BoardContext` currently mixes provider state with direct data access
**When** this story completes
**Then** board data fetching is delegated to feature-owned hooks
**And** `BoardProvider` focuses on selection and terminal/session state composition.

### AC2: Thread Mention Navigation Uses an Explicit Typed Contract

**Given** mention autocomplete still relies on implicit element mutation patterns
**When** this story completes
**Then** thread mention navigation uses a typed local contract
**And** the autocomplete remains behaviorally stable while becoming less fragile.

### AC3: Shell-Level Settings Actions Use Dedicated Hooks

**Given** shell settings actions should not leak workflow data access into layout modules
**When** this story completes
**Then** shell-level settings requests use dedicated hooks or view-model owners
**And** the shell stays consistent with the feature boundary rules from Epic 22.

### AC4: Architecture Tests Cover the New Shell-State Boundaries

**Given** these are subtle coupling reductions rather than visible redesigns
**When** this story completes
**Then** architecture tests and focused component tests lock the new boundaries in place
**And** regressions toward direct root data ownership are caught.

### AC5: Story Exit Gate Is Green

**Given** this story rewires board/thread shell state
**When** the story closes
**Then** `npm run typecheck`, focused tests, `npm run test:architecture`, and Playwright regression pass
**And** `/code-review` is run
**And** verification evidence is recorded.

## Tasks / Subtasks

- [ ] **Task 1: Extract board shell state dependencies** (AC: #1, #3)
  - [ ] 1.1 Introduce or complete feature hooks for board provider/selector data
  - [ ] 1.2 Rewire `BoardContext` to consume those hooks instead of fetching directly
  - [ ] 1.3 Preserve board selection and open-terminal behavior

- [ ] **Task 2: Type the thread mention navigation seam** (AC: #2, #4)
  - [ ] 2.1 Introduce a typed thread mention navigation contract in a feature-local module
  - [ ] 2.2 Rewire mention autocomplete and thread input integration to use it
  - [ ] 2.3 Remove ad hoc `any`-style element mutation patterns from this flow

- [ ] **Task 3: Tighten shell settings action ownership** (AC: #3, #4)
  - [ ] 3.1 Extract shell settings actions into dedicated feature hooks where still missing
  - [ ] 3.2 Keep `DashboardLayout` and related shell files view-oriented
  - [ ] 3.3 Run `/code-review`

- [ ] **Task 4: Run the story exit gate** (AC: #5)
  - [ ] 4.1 Run `npm run typecheck`
  - [ ] 4.2 Run focused board/thread/settings tests and `npm run test:architecture`
  - [ ] 4.3 Run `npm run test:e2e`
  - [ ] 4.4 Record verification evidence and residual risks

## Dev Notes

### Architecture Patterns

- Root providers should compose state, not fetch workflow data directly.
- Typed local contracts are preferable to hidden object mutation on DOM elements.
- Shell settings interactions belong behind feature hooks when they cross into data access.

### Project Structure Notes

- Current shell/provider entry points:
  - `/Users/ennio/Documents/nanobot-ennio/dashboard/components/BoardContext.tsx`
  - `/Users/ennio/Documents/nanobot-ennio/dashboard/components/AgentMentionAutocomplete.tsx`
  - `/Users/ennio/Documents/nanobot-ennio/dashboard/components/DashboardLayout.tsx`
- Target owners should stay within `dashboard/features/boards/*`, `dashboard/features/thread/*`, and `dashboard/features/settings/*`.

### References

- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/components/BoardContext.tsx]
- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/components/AgentMentionAutocomplete.tsx]
- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/tests/architecture.test.ts]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
