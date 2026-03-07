# Story 20.4: Semantic Hook APIs and Test Decoupling

Status: review

## Story

As a **maintainer**,
I want feature hooks to provide semantic APIs instead of raw Convex pass-throughs,
so that component tests mock hooks instead of Convex internals, completing the Wave 5 decoupling.

## Acceptance Criteria

### AC1: Feature Hooks Provide Semantic APIs

**Given** the 6 feature hooks currently return raw `useMutation()`/`useQuery()` results
**When** the refactoring is complete
**Then** each hook returns a semantic API:
- `useTaskInputData` returns `{ createTask(args): Promise, predefinedTags, ... }` not raw mutation references
- `useAgentConfigSheetData` returns `{ updateConfig(args): Promise, ... }`
- `useTagsPanelData` returns `{ createTag(args): Promise, removeTag(id): Promise, ... }`
- `useSearchBarFilters` returns typed filter data
- `useStepCardActions` returns `{ deleteStep(id): Promise, acceptHumanStep(id): Promise, ... }`
- `useAgentSidebarItemState` returns typed state
**And** Convex is an implementation detail hidden inside the hook

### AC2: Component Tests Mock Hooks

**Given** component tests currently mock `convex/react` with deep Convex setup
**When** the test migration is complete
**Then** component tests mock the feature hook:
```typescript
vi.mock("@/hooks/useTaskInputData", () => ({
  useTaskInputData: () => ({ createTask: vi.fn(), predefinedTags: [] })
}));
```
**And** no component test imports or mocks `convex/react` directly
**And** no component test references Convex API paths

### AC3: Hook Tests Cover Convex Integration

**Given** hooks now hide Convex details
**When** hook tests are written
**Then** each feature hook has a dedicated test file
**And** hook tests verify the Convex integration (which queries/mutations are called)
**And** this is the only place Convex mocks appear

### AC4: Architecture Guardrail

**Given** the decoupling is complete
**When** a guardrail test is added
**Then** component test files (*.test.tsx) in `dashboard/components/` cannot import from `convex/react`
**And** the guardrail runs in the test suite

### AC5: Target Components

**Given** the 6 target components
**When** the refactoring is complete
**Then** all 6 are fully decoupled:
1. TaskInput
2. AgentConfigSheet
3. TagsPanel
4. SearchBar
5. StepCard
6. AgentSidebarItem

## Tasks / Subtasks

- [x] **Task 1: Refactor useTaskInputData to semantic API** (AC: #1)
  - [x] 1.1 Read `dashboard/hooks/useTaskInputData.ts` (67 lines)
  - [x] 1.2 Wrap useMutation returns in async functions
  - [x] 1.3 Define explicit return type interface
  - [x] 1.4 Create `dashboard/hooks/__tests__/useTaskInputData.test.ts`

- [x] **Task 2: Refactor useAgentConfigSheetData** (AC: #1)
  - [x] 2.1 Read hook (47 lines), wrap mutations, define return type
  - [x] 2.2 Create hook test file

- [x] **Task 3: Refactor useTagsPanelData** (AC: #1)
  - [x] 3.1 Read hook (25 lines), wrap 7 mutations/queries
  - [x] 3.2 Create hook test file

- [x] **Task 4: Refactor useSearchBarFilters** (AC: #1)
  - [x] 4.1 Read hook (36 lines), type the return value
  - [x] 4.2 Create hook test file

- [x] **Task 5: Refactor useStepCardActions** (AC: #1)
  - [x] 5.1 Read hook (13 lines), wrap 3 mutations
  - [x] 5.2 Create hook test file

- [x] **Task 6: Refactor useAgentSidebarItemState** (AC: #1)
  - [x] 6.1 Read hook (19 lines), type the return value
  - [x] 6.2 Create hook test file

- [x] **Task 7: Migrate component tests** (AC: #2)
  - [x] 7.1 Rewrite TaskInput.test.tsx to mock useTaskInputData
  - [x] 7.2 Rewrite AgentConfigSheet.test.tsx to mock useAgentConfigSheetData
  - [x] 7.3 Rewrite TagsPanel.test.tsx to mock useTagsPanelData
  - [x] 7.4 Rewrite SearchBar.test.tsx to mock useSearchBarFilters
  - [x] 7.5 Rewrite StepCard.test.tsx to mock useStepCardActions
  - [x] 7.6 Rewrite AgentSidebarItem.test.tsx to mock useAgentSidebarItemState

- [x] **Task 8: Add architecture guardrail** (AC: #4)
  - [x] 8.1 Add test to `dashboard/tests/architecture.test.ts`: component tests cannot import convex/react
  - [x] 8.2 Verify the guardrail catches violations

- [x] **Task 9: Final verification** (AC: #5)
  - [x] 9.1 Run full dashboard test suite
  - [x] 9.2 Verify all 6 components pass
  - [x] 9.3 Verify all 6 hook tests pass

## Dev Notes

### Architecture Patterns

**Semantic API pattern:** A hook returns domain-meaningful functions and data, not framework primitives.

```typescript
// BEFORE (pass-through)
export function useStepCardActions() {
  const deleteStep = useMutation(api.steps.remove);
  return { deleteStep };
}

// AFTER (semantic)
export function useStepCardActions() {
  const _deleteStep = useMutation(api.steps.remove);
  return {
    deleteStep: async (stepId: Id<"steps">) => { await _deleteStep({ stepId }); },
  };
}
```

**Test pattern:** Component tests mock the hook, hook tests mock Convex.

```typescript
// Component test -- mocks hook
vi.mock("@/hooks/useStepCardActions", () => ({
  useStepCardActions: () => ({ deleteStep: vi.fn() })
}));

// Hook test -- mocks Convex
vi.mock("convex/react", () => ({ useMutation: vi.fn() }));
```

**Key Files to Read First:**
- All 6 hooks in `dashboard/hooks/`
- All 6 component test files
- `dashboard/tests/architecture.test.ts` -- existing guardrails

### Project Structure Notes

**Files to MODIFY:**
- `dashboard/hooks/useTaskInputData.ts`
- `dashboard/hooks/useAgentConfigSheetData.ts`
- `dashboard/hooks/useTagsPanelData.ts`
- `dashboard/hooks/useSearchBarFilters.ts`
- `dashboard/hooks/useStepCardActions.ts`
- `dashboard/hooks/useAgentSidebarItemState.ts`
- All 6 component test files
- `dashboard/tests/architecture.test.ts`

**Files to CREATE:**
- `dashboard/hooks/__tests__/useTaskInputData.test.ts`
- `dashboard/hooks/__tests__/useAgentConfigSheetData.test.ts`
- `dashboard/hooks/__tests__/useTagsPanelData.test.ts`
- `dashboard/hooks/__tests__/useSearchBarFilters.test.ts`
- `dashboard/hooks/__tests__/useStepCardActions.test.ts`
- `dashboard/hooks/__tests__/useAgentSidebarItemState.test.ts`

### References

- [Source: dashboard/hooks/] -- current feature hooks
- [Source: dashboard/tests/architecture.test.ts] -- existing guardrails
- [Source: docs/ARCHITECTURE.md] -- dashboard architecture section

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
None -- all tests passed on first attempt.

### Completion Notes List
- All 6 hooks refactored to semantic APIs with explicit TypeScript interfaces
- All 6 hook test files created and passing (28 total hook tests)
- All 8 component test files migrated to mock hooks instead of convex/react (118 component tests)
- Architecture guardrail added (8 new guardrail tests covering all target component test files)
- Also migrated tests/components/TaskInput.layout.test.tsx and TaskInput.tags.test.tsx (out of scope but they test target components)
- Full dashboard suite: 971 passed, 1 pre-existing failure (ExecutionPlanTab.test.tsx plan-editor)

### File List
**Modified (6 hooks):**
- dashboard/hooks/useTaskInputData.ts
- dashboard/hooks/useAgentConfigSheetData.ts
- dashboard/hooks/useTagsPanelData.ts
- dashboard/hooks/useSearchBarFilters.ts
- dashboard/hooks/useStepCardActions.ts
- dashboard/hooks/useAgentSidebarItemState.ts

**Modified (8 component test files):**
- dashboard/components/TaskInput.test.tsx
- dashboard/components/AgentConfigSheet.test.tsx
- dashboard/components/SearchBar.test.tsx
- dashboard/components/StepCard.test.tsx
- dashboard/components/AgentSidebarItem.test.tsx
- dashboard/tests/components/TagsPanel.test.tsx
- dashboard/tests/components/TaskInput.layout.test.tsx
- dashboard/tests/components/TaskInput.tags.test.tsx

**Modified (1 architecture test):**
- dashboard/tests/architecture.test.ts

**Created (6 hook test files):**
- dashboard/hooks/__tests__/useTaskInputData.test.ts
- dashboard/hooks/__tests__/useAgentConfigSheetData.test.ts
- dashboard/hooks/__tests__/useTagsPanelData.test.ts
- dashboard/hooks/__tests__/useSearchBarFilters.test.ts
- dashboard/hooks/__tests__/useStepCardActions.test.ts
- dashboard/hooks/__tests__/useAgentSidebarItemState.test.ts

**Modified (story/sprint tracking):**
- _bmad-output/implementation-artifacts/20-4-semantic-hook-apis-and-test-decoupling.md
- _bmad-output/implementation-artifacts/sprint-status.yaml

## Change Log
- Refactored 6 feature hooks to provide semantic APIs with explicit TypeScript interfaces (CreateTaskArgs, UpdateConfigArgs, etc.)
- Wrapped all useMutation returns in async functions so Convex is an implementation detail
- Added explicit return type interfaces (TaskInputData, AgentConfigSheetData, TagsPanelData, SearchBarFiltersData, StepCardActionsData, AgentSidebarItemStateData)
- Created 6 hook test files in dashboard/hooks/__tests__/ testing Convex integration
- Migrated 8 component test files to mock hooks instead of convex/react
- Added architecture guardrail: component tests cannot import/mock convex/react directly
