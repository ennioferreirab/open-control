# Story 33.8: Fix TypeScript ESLint and Type Errors

Status: ready-for-dev

## Story

As a developer,
I want all TypeScript lint and type errors resolved,
so that the frontend codebase has verified type safety and lint compliance.

## Acceptance Criteria

1. `cd dashboard && npx eslint .` — zero errors (warnings acceptable)
2. `cd dashboard && npx tsc --noEmit` — zero errors
3. No `eslint-disable` without a documented reason

## Tasks / Subtasks

### Task 1: Create shared test helpers (fixes 55+ errors at once)

Create `dashboard/tests/helpers/mockConvex.ts`:

```typescript
import type { Id } from "@/convex/_generated/dataModel";
import type { ReactMutation, FunctionReference } from "convex/react";

/** Cast a string to a branded Convex Id for test mocks */
export function testId<T extends string>(value: string): Id<T> {
  return value as unknown as Id<T>;
}

/** Create a mock ReactMutation that includes withOptimisticUpdate */
export function mockReactMutation<T>(
  impl: (...args: unknown[]) => T,
): ReactMutation<FunctionReference<"mutation">> {
  const fn = vi.fn(impl) as unknown as ReactMutation<FunctionReference<"mutation">>;
  (fn as Record<string, unknown>).withOptimisticUpdate = vi.fn().mockReturnValue(fn);
  return fn;
}
```

### Task 2: Fix `"stringId" as any` → `testId()` across test files (55+ eslint errors)

Replace ALL `"task1" as any` / `"step-1" as any` patterns with `testId<"tasks">("task1")` etc.

| File | Lines | Pattern |
|------|-------|---------|
| `hooks/useTaskDetailActions.test.ts` | 88, 103, 119, 131, 143, 152, 164, 174, 186, 202, 217, 228, 239, 250, 261, 277 | `"task1" as any` → `testId<"tasks">("task1")` |
| `hooks/useTaskDetailView.test.ts` | 73, 110, 142, 177, 210, 259, 308 | Same |
| `convex/lib/threadRules.test.ts` | 109, 129, 153, 173, 192, 211, 214 | `"task-1" as any` → `testId<"tasks">("task-1")`, `"step-1" as any` → `testId<"steps">("step-1")` |
| `convex/lib/workflowHelpers.test.ts` | 87, 150, 157 | Same |
| `tests/components/CompactFavoriteCard.test.tsx` | 21 | Same |
| `tests/components/TaskDetailSheet.tags.test.tsx` | 149, 227, 297, 344 | Same |

### Task 3: Fix `useTaskInteractiveSession.test.ts` (30 tsc errors)

Create factory functions at the top of the file:

```typescript
function makeSession(overrides: Partial<Doc<"interactiveSessions">> = {}): Doc<"interactiveSessions"> {
  return {
    _id: testId<"interactiveSessions">("session-doc"),
    _creationTime: 1,
    sessionId: "interactive_session:claude",
    agentName: "claude-pair",
    provider: "claude-code",
    // ... all required fields
    ...overrides,
  } as Doc<"interactiveSessions">;
}
```

Replace `{ ...sessionBase, status: "active" }` → `makeSession({ status: "active" })` throughout.

### Task 4: Fix `withOptimisticUpdate` missing (24 tsc errors)

Use `mockReactMutation` helper from Task 1.

| File | Lines | Fix |
|------|-------|-----|
| `features/agents/hooks/useCreateSquadDraft.test.tsx` | 30, 40, 53, 76, 99, 125, 140, 163, 181, 217 | Replace `vi.fn().mockResolvedValue(...)` with `mockReactMutation(async () => ...)` |
| `features/agents/hooks/useRunSquadMission.test.tsx` | 42, 51, 60, 72, 81, 90, 100, 110, 130, 149, 173 | Same |
| `features/agents/hooks/useUpdatePublishedSquad.test.tsx` | 29, 38, 76 | Same |

### Task 5: Fix `no-explicit-any` in non-test production code (8 errors)

| File | Line | Current | Fix |
|------|------|---------|-----|
| `convex/agents.ts` | 12 | `query: (table: string) => any` | `query: (table: string) => unknown` |
| `convex/agents.ts` | 13 | `patch: (id: any, ...)` | `patch: (id: string, ...)` |
| `hooks/useThreadComposer.ts` | 81 | `const taskAny = task as any` | Access `awaitingKickoff` through `Doc<"tasks">` type directly (field exists on schema) |
| `hooks/useThreadComposer.ts` | 199 | `(textareaRef.current as any)?.__mentionNav` | Define `interface MentionNavElement extends HTMLTextAreaElement { __mentionNav?: { navigateDown(): void; navigateUp(): void; selectCurrent(): void } }` and cast to it |

### Task 6: Fix `no-explicit-any` in test mocks (25+ errors)

| File | Lines | Fix |
|------|-------|-----|
| `tests/components/TaskDetailSheet.tags.test.tsx` | 72, 82, 92, 93, 94, 95, 96, 103, 110, 113, 116, 123, 126, 129, 176, 177, 335, 336 | Replace `any` with proper prop types: `{ children: React.ReactNode }`, `{ children: React.ReactNode; value: string }`, etc. |
| `tests/components/TaskDetailSheet.tags.test.tsx` | 69, 90, 102 | `const React = require("react")` → `import * as React from "react"` |
| `tests/components/AgentMentionAutocomplete.test.tsx` | 69, 77, 97 | Type mock returns properly, replace `as any` |
| `hooks/useBoardView.test.ts` | 102, 113, 124, 139, 149, 161, 171, 189, 212 | Define typed mock object for `getBoardView` return, replace `as any` spread |
| `hooks/useThreadComposer.test.ts` | 47 | `} as any` → `} as Doc<"tasks">` |
| `components/viewers/MarkdownViewer.test.tsx` | 100, 118, 133 | `as any` → `as MarkdownViewerProps` |
| `app/api/agents/[agentName]/config/route.test.ts` | 55 | `req as any` → `req as NextRequest` |

### Task 7: Fix `no-restricted-imports` (3 errors)

| File | Line | Fix |
|------|------|-----|
| `components/ConvexClientProvider.tsx` | 4 | Add `// eslint-disable-next-line no-restricted-imports -- root provider needs direct convex/react access` |
| `tests/components/AgentMentionAutocomplete.test.tsx` | 24 | Add `// eslint-disable-next-line no-restricted-imports -- test mock requires direct import` |
| `tests/components/TaskDetailSheet.tags.test.tsx` | 135 | Same |

### Task 8: Fix remaining tsc errors (11 errors)

| File | Line | Error | Fix |
|------|------|-------|-----|
| `components/DocumentViewerModal.tsx` | 270 | `file.size` is `number \| undefined` | `formatSize(file.size ?? 0)` |
| `components/FlowStepNode.test.tsx` | 16 | Missing props | Add `isConnectable: true, positionAbsoluteX: 0, positionAbsoluteY: 0` |
| `features/agents/components/AgentConfigSheet.test.tsx` | 186, 187, 188, 193, 194 | `child.props` is `unknown` | Cast: `(child as React.ReactElement<{ value: string; children: React.ReactNode }>).props` |
| `features/agents/components/SquadDetailSheet.tsx` | 134 | `dependsOn` undefined vs `string[]` | `dependsOn: step.dependsOn.length ? step.dependsOn : []` |
| `features/agents/components/SquadSidebarSection.test.tsx` | 41, 47, 67, 87 | Missing mock fields | Add `archivedSquads: [], archiveSquad: vi.fn(), unarchiveSquad: vi.fn()` |
| `features/agents/hooks/useSquadDetailData.ts` | 29 | `null` in agent list | `agents?.filter((a): a is Doc<"agents"> => a !== null)` |
| `features/agents/hooks/useUpdatePublishedSquad.ts` | 61 | Returns `string`, expects `Id<"squadSpecs">` | `return await publishMutation(args) as Id<"squadSpecs">` |
| `features/boards/components/BoardSettingsSheet.tsx` | 228 | `boardName` on union type | Narrow: `artifactSource.kind === "board-artifact" ? artifactSource.boardName : ""` |

### Task 9: Fix React/a11y/misc warnings (17 warnings — optional but recommended)

| File | Line | Rule | Fix |
|------|------|------|-----|
| `components/BoardContext.tsx` | 61 | `set-state-in-effect` | Refactor localStorage hydration to use lazy initial state in `useState` |
| `components/PromptEditModal.tsx` | 127 | `set-state-in-effect` | Use `key` prop reset pattern |
| `components/ui/sidebar.tsx` | 645 | `react-hooks/purity` | `const widthRef = useRef(\`\${Math.floor(Math.random() * 40) + 50}%\`)` |
| `features/tasks/hooks/usePlanEditorState.ts` | 28, 36 | `set-state-in-effect` | Compute as derived state |
| `components/FileChip.tsx` | 25 | `jsx-a11y/alt-text` | Add `alt={file.name}` |
| `components/viewers/ImageViewer.tsx` | 103, 113 | `no-img-element` | Use `next/image` or suppress |
| `components/ActivityFeed.test.tsx` | 22 | `no-unused-vars` | Remove unused destructured vars |
| `components/viewers/PdfViewer.test.tsx` | 2 | `no-unused-vars` | Remove `act` import |
| `convex/lib/taskMerge.ts` | 9 | `no-unused-vars` | Remove `MergeCapableTask` type |
| `convex/steps.ts` | 6 | `no-unused-vars` | Remove unused imports `incrementAgentStepMetric`, `AgentMetricDb` |
| `hooks/useBoardFilters.ts` | 4 | `no-unused-vars` | Remove `ParsedAttributeFilter` import |
| `tests/mocks/select-mock.tsx` | 45, 54 | `no-unused-vars`, `jsx-a11y` | Remove `_onChange`, add aria attributes |
| `app/api/tasks/[taskId]/files/route.ts` | 64 | `no-unused-vars` | `} catch {` (drop `err`) |

### Task 10: Verify

- `cd dashboard && npx eslint .` — zero errors
- `cd dashboard && npx tsc --noEmit` — zero errors
