# Story 33.4: TypeScript Import and Naming Alignment

Status: ready-for-dev

## Story

As a developer,
I want all TypeScript imports to use `@/` path aliases, component files to follow naming conventions, and shared types to match the cross-service contract,
so that the frontend codebase is consistent and navigation is predictable.

## Acceptance Criteria

1. All relative imports crossing directory boundaries converted to `@/` aliases
2. `convex/react` imports removed from `components/` (excluding `ConvexClientProvider`)
3. `PlanStep` type naming collision resolved and aligned with Python `ExecutionPlanStep`
4. All kebab-case filenames (non-shadcn) renamed to camelCase
5. `ConvexClientProvider` uses named export instead of default export
6. `TrustLevel` constants aligned with cross-service naming contract
7. Missing `"use client"` directives added to hook files that use React hooks
8. Zero new ESLint errors introduced

## Tasks / Subtasks

- [ ] Task 1: Convert relative imports to `@/` aliases in `components/` (AC: #1)
  - [ ] `FeedItem.tsx:3` — `"../convex/_generated/dataModel"` → `"@/convex/_generated/dataModel"`
  - [ ] `DashboardLayout.tsx:4` — same pattern
  - [ ] `TagAttributeEditor.tsx:5,8` — both imports
  - [ ] `CompactFavoriteCard.tsx:4,5` — both imports
  - [ ] `KanbanColumn.tsx:9` — dataModel import
  - [ ] `InlineRejection.tsx:4` — dataModel import
  - [ ] `StepFileAttachment.tsx:5,6` — both imports
  - [ ] `AddStepForm.tsx:23` — dataModel import
  - [ ] `BoardContext.tsx:11` — dataModel import
  - [ ] `EditStepForm.tsx:24` — dataModel import
  - [ ] Test files: `KanbanBoard.test.tsx:4`, `ThreadInput.test.tsx:5`, `KanbanColumn.test.tsx:4`, `ActivityFeed.test.tsx:5`

- [ ] Task 2: Convert relative imports to `@/` aliases in `hooks/` (AC: #1)
  - [ ] `useBoardColumns.ts:2,3` — dataModel + lib import
  - [ ] `useGatewaySleepRuntime.ts:4` — api import
  - [ ] `useThreadComposer.ts:5,6` — api + dataModel
  - [ ] `useChatSyncRuntime.ts:3` — api import
  - [ ] `useSelectableAgents.ts:2,3` — api + dataModel
  - [ ] `useFileUpload.ts:5,6` — api + dataModel
  - [ ] Test: `useBoardColumns.test.ts:4`

- [ ] Task 3: Remove `convex/react` imports from `components/` (AC: #2)
  - [ ] `TagAttributeEditor.tsx:4` — extract mutation to a feature hook or shared hook
  - [ ] `CompactFavoriteCard.tsx:3` — extract mutation to a feature hook
  - [ ] `StepFileAttachment.tsx:4` — extract mutation to a feature hook
  - [ ] `ConvexClientProvider.tsx:4` — KEEP (this is the provider setup, acceptable)

- [ ] Task 4: Resolve `PlanStep` / `ExecutionPlanStep` naming (AC: #3)
  - [ ] `dashboard/lib/types.ts:5` — rename `PlanStep` to `EditablePlanStep` (it's the editable/normalized form)
  - [ ] `dashboard/features/tasks/components/ExecutionPlanTab.tsx:32` — keep existing `ExecutionPlanStep` (it's the raw Convex form)
  - [ ] Update all usages of `PlanStep`:
    - `lib/planUtils.ts` — 13 references
    - `lib/flowLayout.ts` — 2 references
    - `lib/planUtils.test.ts` — 2 references
    - `lib/flowLayout.test.ts` — 3 references
    - `components/FlowStepNode.tsx` — 2 references
    - `features/tasks/components/ExecutionPlanTab.tsx` — 7 references
    - `features/agents/components/SquadWorkflowCanvas.tsx` — 6 references
  - [ ] Add comment documenting the distinction: `EditablePlanStep` (UI-editable) vs `ExecutionPlanStep` (raw from Convex)

- [ ] Task 5: Rename kebab-case files (AC: #4)
  - [ ] `hooks/use-mobile.tsx` → `hooks/useIsMobile.ts` (also change `.tsx` to `.ts`, no JSX)
  - [ ] `features/settings/polling-fields.ts` → `features/settings/pollingFields.ts`
  - [ ] `lib/cron-parser.ts` → `lib/cronParser.ts`
  - [ ] `lib/cron-parser.test.ts` → `lib/cronParser.test.ts`
  - [ ] Update all import references to the renamed files
  - [ ] Note: `components/ui/*.tsx` kebab-case files are shadcn convention — leave them

- [ ] Task 6: Fix default export (AC: #5)
  - [ ] `ConvexClientProvider.tsx:8` — change `export default function` to `export function`
  - [ ] Update the import in the consuming file (likely `app/layout.tsx`)

- [ ] Task 7: Align TrustLevel constants (AC: #6)
  - [ ] `lib/constants.ts:31` — `TRUST_LEVEL.HUMAN_APPROVED` should be reviewed
  - [ ] Cross-reference with Convex schema trust level values
  - [ ] If Convex uses `human_approved`, update `cross_service_naming.md` to match reality
  - [ ] If Convex uses `supervised`/`manual`, update `lib/constants.ts` to match

- [ ] Task 8: Add missing `"use client"` directives (AC: #7)
  - [ ] `hooks/use-mobile.tsx` (will become `useIsMobile.ts` after rename)
  - [ ] `hooks/useSelectableAgents.ts`
  - [ ] `hooks/useBoardFilters.ts`
  - [ ] `hooks/useChatSyncRuntime.ts`
  - [ ] `hooks/useGatewaySleepRuntime.ts`
  - [ ] `hooks/useBoardColumns.ts`
  - [ ] `features/agents/hooks/useNanobotProvider.ts`

- [ ] Task 9: Verify (AC: #8)
  - [ ] `cd dashboard && npx next lint`
  - [ ] `cd dashboard && npx tsc --noEmit`

## Dev Notes

- Task 3 (removing convex/react from components) requires creating new hooks. The mutations are simple one-liners — either add them to existing feature hooks or create minimal shared hooks in `hooks/`.
- Task 4 (PlanStep naming) has a collision. The current `PlanStep` in `lib/types.ts` is actually an editable/normalized plan step (with `x`, `y` coordinates for canvas), while `ExecutionPlanStep` in `ExecutionPlanTab.tsx` is the raw Convex step shape. Rename `PlanStep` to `EditablePlanStep` to disambiguate without breaking the existing `ExecutionPlanStep`.
- Task 7 (TrustLevel) needs investigation — the canonical values may have drifted from the original naming contract.

### References

- [Source: agent_docs/code_conventions/typescript.md#Imports] — @/ alias convention
- [Source: agent_docs/code_conventions/typescript.md#Component Patterns] — named exports, hook pattern
- [Source: agent_docs/code_conventions/typescript.md#File Naming] — camelCase convention
- [Source: agent_docs/code_conventions/cross_service_naming.md#TrustLevel] — canonical trust levels
- [Source: dashboard/lib/types.ts:5] — PlanStep definition
- [Source: dashboard/features/tasks/components/ExecutionPlanTab.tsx:32] — ExecutionPlanStep definition
