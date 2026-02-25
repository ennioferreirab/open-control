# Story 3.2: Visualize Blocked and Crashed Steps

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to see at a glance which steps are blocked and which have crashed,
So that I understand the current state of my task without clicking into each step.

## Acceptance Criteria

1. **Blocked step — lock icon and dependency subtitle** — Given a step has `status === "blocked"` with entries in its `blockedBy` array, when the `StepCard` renders on the Kanban board, then a `Lock` icon (from `lucide-react`) is displayed on the card header AND the titles of the blocking steps are shown as a `Tooltip` wrapping the lock icon area (FR30). The tooltip content lists each blocking step title on its own line (or comma-separated if single-line preferred).

2. **Blocked step — muted visual style** — Given a step has `status === "blocked"`, when `StepCard` renders, then the card is visually muted: the entire card wrapper receives `opacity-60` and `grayscale-[0.3]` (or equivalent Tailwind classes that match the existing design token for `--muted`) to signal it cannot proceed. The amber left-border (`border-l-amber-500`) from `STEP_STATUS_COLORS.blocked` is preserved as the color accent — only opacity/saturation is reduced, not the accent color.

3. **Crashed step — destructive badge** — Given a step has `status === "crashed"`, when `StepCard` renders, then a red "Crashed" `Badge` is displayed. The badge must use `bg-red-500 text-white` (destructive color from design system). The card remains visible on the board in the "In Progress" column — it is NOT removed. The `AlertTriangle` icon (lucide-react, already imported) appears adjacent to the title, colored `text-red-500`.

4. **Crashed step — error message on hover** — Given a step has `status === "crashed"` AND has a non-empty `errorMessage` field, when the user hovers over the `AlertTriangle` icon or the "Crashed" badge, then a `Tooltip` shows the `step.errorMessage` content (truncated to 200 characters if longer).

5. **Unblock transition — smooth animation** — Given a step transitions from `status === "blocked"` to `status === "assigned"` (triggered by `checkAndUnblockDependents` in `steps.ts`), when Convex updates the step record and the `KanbanBoard` re-renders, then: the lock icon and muted styling are removed, the card's `opacity` returns to `1`, and the card moves from the "Assigned" column's blocked position to its normal assigned slot with a smooth Framer Motion `layoutId` transition (already wired — `layoutId={step._id}` in `motion.div`). The transition duration is `0.3s` (already the default; `shouldReduceMotion` sets it to `0`).

6. **Accessibility** — All new icon + tooltip pairs must be accessible: the `TooltipTrigger` wraps the icon with a visually descriptive `aria-label` (e.g., `aria-label="Blocked by: Step A, Step B"`). The `StepCard` `aria-label` attribute must include the blocked/crashed status (it already includes `step.status` — no change required).

7. **Tests** — New behaviors are covered in `StepCard.test.tsx`: (a) blocked card has `opacity-60` class on the wrapper, (b) tooltip text contains blocking step titles, (c) crashed card shows `errorMessage` in tooltip when present, (d) crashed card with no `errorMessage` does not render a tooltip on the crashed badge, (e) existing tests still pass.

## Tasks / Subtasks

- [x] **Task 1: Extend `StepCard` props to support blocking step titles** (AC: 1, 2, 4, 6)
  - [x] 1.1 Add optional prop `blockingStepTitles?: string[]` to `StepCardProps` — this receives the resolved titles of all steps in `step.blockedBy` (resolved by the parent component, not via a Convex query inside `StepCard`)
  - [x] 1.2 Wrap the `Lock` icon in a `TooltipProvider` + `Tooltip` + `TooltipTrigger` + `TooltipContent` (import from `@/components/ui/tooltip`). The `TooltipContent` renders `blockingStepTitles` joined with `"\n"` (or as `<div>` lines). If `blockingStepTitles` is empty or undefined, render the lock icon without a tooltip (plain `<span>`).
  - [x] 1.3 Add `aria-label` to the `TooltipTrigger` element: `aria-label={\`Blocked by: ${(blockingStepTitles ?? []).join(", ")}\`}` (falls back to `"Blocked"` if titles are empty)
  - [x] 1.4 Apply muted visual classes to the `motion.div` wrapper when `status === "blocked"`: add `opacity-60` and `grayscale-[0.3]` to the `motion.div` className. These classes must be conditional — other statuses must not receive them.

- [x] **Task 2: Add error message tooltip to crashed step indicator** (AC: 3, 4, 6)
  - [x] 2.1 Wrap the `AlertTriangle` icon (already present in the header) in a `Tooltip` when `step.errorMessage` is present. The `TooltipContent` renders `step.errorMessage.slice(0, 200)` with a `...` suffix if truncated. If `step.errorMessage` is absent or empty, render `AlertTriangle` as-is (no tooltip).
  - [x] 2.2 Wrap the "Crashed" `Badge` (already present in the footer row) in a `Tooltip` when `step.errorMessage` is present, showing the same truncated message. This allows the user to hover either the icon OR the badge to see the error.
  - [x] 2.3 Add `aria-label` to the crashed icon `TooltipTrigger`: `aria-label="Crashed: {errorMessage first 80 chars}"` (or `"Step crashed"` if no message).

- [x] **Task 3: Resolve `blockedBy` IDs to titles in `KanbanBoard`** (AC: 1, 7)
  - [x] 3.1 In `KanbanBoard.tsx`, build a step-ID-to-title lookup map from `allSteps`: `const stepTitleById = new Map(allSteps.map(s => [s._id, s.title] as const))` — this is a pure derivation, no new Convex query needed.
  - [x] 3.2 When building `stepGroups` inside `tasksByStatus`, for each step in the group, compute `blockingStepTitles: (step.blockedBy ?? []).map(id => stepTitleById.get(id) ?? "Unknown step")`.
  - [x] 3.3 Update the `StepCard` element in `KanbanColumn.tsx` to accept and forward `blockingStepTitles`. This requires adding `blockingStepTitles?: string[]` to the step group shape flowing through `KanbanColumn`. Approach: add it to the step object wrapper in `KanbanBoard` (not as a separate prop array), or extend `StepCard` to accept it and pass it from `KanbanColumn`. Prefer adding `blockingStepTitles` to the per-step objects passed into `stepGroups` — change the `stepGroups` type in `KanbanColumnProps` from `{ taskId, taskTitle, steps: Doc<"steps">[] }` to `{ taskId, taskTitle, steps: Array<Doc<"steps"> & { blockingStepTitles: string[] }> }`.

- [x] **Task 4: Write tests for new visual behaviors** (AC: 7)
  - [x] 4.1 In `StepCard.test.tsx`, add test: `"blocked step renders Lock icon with tooltip listing blocking step titles"` — render `StepCard` with `status: "blocked"` and `blockingStepTitles: ["Step A", "Step B"]`, assert tooltip content contains "Step A" and "Step B"
  - [x] 4.2 Add test: `"blocked step wrapper has opacity-60 class"` — assert the `motion.div` (or its DOM equivalent after mock) has `opacity-60` in its className
  - [x] 4.3 Add test: `"crashed step with errorMessage renders tooltip on AlertTriangle"` — render with `status: "crashed"` and `errorMessage: "Something failed"`, assert tooltip text "Something failed" is present (hover or `getByTitle`/`getByLabelText`)
  - [x] 4.4 Add test: `"crashed step without errorMessage does not render tooltip"` — render with `status: "crashed"` and no `errorMessage`, assert no tooltip content rendered
  - [x] 4.5 Add test: `"errorMessage longer than 200 chars is truncated in tooltip"` — render with `errorMessage` of 250 chars, assert tooltip text ends with `"..."`
  - [x] 4.6 Verify all pre-existing `StepCard.test.tsx` tests (6 tests) still pass after prop changes

## Dev Notes

### Current State of the Codebase

**This story is entirely frontend (React/TypeScript).** No Python, no Convex mutations, no schema changes. The `StepCard` component at `dashboard/components/StepCard.tsx` already has partial implementations for both blocked and crashed states, but they are incomplete relative to the acceptance criteria:

**What already exists in `StepCard.tsx` (lines 1–115):**
- `Lock` icon from `lucide-react` is already imported (line 8)
- `AlertTriangle` icon from `lucide-react` is already imported (line 8)
- `Lock` icon renders in the header when `status === "blocked"` (lines 69–71): `<Lock className="h-3.5 w-3.5 text-amber-500" />`
- `AlertTriangle` icon renders in the header when `status === "crashed"` (lines 72–74): `<AlertTriangle className="h-3.5 w-3.5 text-red-500" />`
- "Crashed" badge renders in the footer row (lines 97–101): `<Badge className="h-5 rounded-full bg-red-500 px-2 text-[10px] text-white">Crashed</Badge>`
- "Blocked" badge renders in the footer row (lines 102–110): amber outline badge with a `Lock` icon
- `STEP_STATUS_COLORS` already defines `blocked: { border: "border-l-amber-500", bg: "bg-amber-100", text: "text-amber-600" }` and `crashed: { border: "border-l-red-500", bg: "bg-red-100", text: "text-red-700" }` in `dashboard/lib/constants.ts` (lines 196–210)

**What is MISSING (the gaps this story fills):**
1. No tooltip on the `Lock` icon showing which steps are blocking
2. No muted/opacity styling on blocked cards
3. No tooltip on the `AlertTriangle` / "Crashed" badge showing `errorMessage`
4. `blockingStepTitles` is not passed in — `blockedBy` is an array of step IDs, not titles. Resolution must happen in `KanbanBoard` using a lookup map.

### Exact Component File Locations

| Component | Path | Current Lines |
|-----------|------|---------------|
| `StepCard` | `dashboard/components/StepCard.tsx` | 115 lines |
| `StepCard` tests | `dashboard/components/StepCard.test.tsx` | 119 lines (6 tests) |
| `KanbanBoard` | `dashboard/components/KanbanBoard.tsx` | 187 lines |
| `KanbanColumn` | `dashboard/components/KanbanColumn.tsx` | 194 lines |
| `constants.ts` (STEP_STATUS_COLORS) | `dashboard/lib/constants.ts` | lines 176–211 |
| ShadCN Tooltip | `dashboard/components/ui/tooltip.tsx` | Radix-based, 4 exports |

### Tooltip Import Pattern

The `Tooltip` component set is already available in the project. The correct import (matching `AgentConfigSheet.tsx` which already uses it):

```tsx
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
```

The `TooltipContent` renders with this default class from `dashboard/components/ui/tooltip.tsx`:
```
z-50 overflow-hidden rounded-md bg-primary px-3 py-1.5 text-xs text-primary-foreground animate-in fade-in-0 zoom-in-95 ...
```

**Important:** `TooltipProvider` must wrap any `Tooltip` usage. For `StepCard`, wrap the entire card in a `TooltipProvider` at the top of the return — or wrap only the specific icon areas. The simplest approach is to wrap the `motion.div` in a `<TooltipProvider>` (zero visual impact).

### Muted Styling for Blocked Cards

The UX spec (ux-design-specification.md, line 273) uses `--muted` (Slate-400) for disabled/inactive state. The Tailwind equivalent:

```tsx
// Add to motion.div className when status === "blocked"
className={[
  step.status === "blocked" ? "opacity-60 grayscale-[0.3]" : "",
  // ... rest of classNames
].join(" ")}
```

The `motion.div` currently has `layoutId`, `layout`, and `transition` props but no `className`. Adding `className` here is safe — it applies to the wrapper div that Framer Motion generates.

**Do NOT** use `opacity-70` (the UX spec uses that for "Done" cards — see ux-design-specification.md line 777: "Done (opacity 0.7)"). For blocked, use `opacity-60` to be visually distinct from Done.

### Framer Motion Pattern (Already in Place)

`StepCard.tsx` already uses `motion/react-client` and `useReducedMotion` (lines 3–4, 43–47). The `layoutId={step._id}` on the `motion.div` (line 44) handles the smooth column transition animation when a blocked step becomes assigned. No additional animation code is needed — the transition is automatic when the step's column assignment changes (via `stepStatusToColumnStatus` in `KanbanBoard.tsx` line 28–43, which maps `"blocked" → "assigned"` column).

The `transition` prop respects `shouldReduceMotion`:
```tsx
transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.3 }}
```

### `blockedBy` ID Resolution Strategy

The `steps` schema defines `blockedBy: v.optional(v.array(v.id("steps")))` — these are Convex document IDs, not titles. The `StepCard` receives `step: Doc<"steps">` directly, which includes `blockedBy: Id<"steps">[] | undefined`.

**Resolution approach (Task 3):** In `KanbanBoard.tsx`, all steps are already fetched via `useQuery(api.steps.listAll)` at line 57. Build a lookup map:

```tsx
const stepTitleById = new Map(allSteps.map((s) => [s._id, s.title] as const));
```

Then when building step groups, compute `blockingStepTitles` for each step:

```tsx
const blockingStepTitles = (step.blockedBy ?? []).map(
  (id) => stepTitleById.get(id) ?? "Unknown step"
);
```

This is a pure client-side derivation — zero additional Convex queries, no network overhead.

### Prop Threading: KanbanBoard → KanbanColumn → StepCard

Currently, `KanbanColumn` receives `stepGroups` typed as:
```tsx
stepGroups: {
  taskId: Id<"tasks">;
  taskTitle: string;
  steps: Doc<"steps">[];
}[];
```

The cleanest extension is to augment each step with the resolved titles as a local type — create an inline type or local interface in `KanbanBoard.tsx` and `KanbanColumn.tsx`:

```tsx
// In KanbanBoard.tsx — build augmented steps:
type StepWithBlockingTitles = Doc<"steps"> & { blockingStepTitles: string[] };

// Update stepGroups type in KanbanColumnProps:
stepGroups: {
  taskId: Id<"tasks">;
  taskTitle: string;
  steps: StepWithBlockingTitles[];
}[];
```

Then in `KanbanColumn.tsx`, pass `step.blockingStepTitles` to `StepCard`:
```tsx
<StepCard
  key={step._id}
  step={step}
  parentTaskTitle={group.taskTitle}
  blockingStepTitles={step.blockingStepTitles}
  onClick={onTaskClick ? () => onTaskClick(step.taskId) : undefined}
/>
```

### Test Pattern to Follow

Existing `StepCard.test.tsx` uses:
- `vitest` (`describe`, `it`, `expect`, `vi`, `afterEach`)
- `@testing-library/react` (`render`, `screen`, `fireEvent`, `cleanup`)
- Motion mocked via `vi.mock("motion/react-client", ...)` and `vi.mock("motion/react", ...)` (lines 5–17)
- `baseStep` fixture with `status: "running"` (lines 19–31)

For Tooltip tests, note that Radix UI `Tooltip` requires the trigger to be hovered/focused to show content. In tests, use `@testing-library/user-event` or `fireEvent.mouseEnter` on the trigger element. Alternatively, check that the tooltip content is in the DOM (Radix renders it when open). A simpler approach: assert the `aria-label` value on the tooltip trigger, and assert the text content of the `TooltipContent` when rendered (use `screen.getByText` after simulating hover or check the content is present in the DOM via `data-state="open"` workaround).

**Recommended test approach for tooltips:** Mock the Tooltip components or use `userEvent.hover()` from `@testing-library/user-event` v14 (check if already installed):

```tsx
import userEvent from "@testing-library/user-event";
// ...
const user = userEvent.setup();
await user.hover(screen.getByLabelText("Blocked by: Step A, Step B"));
expect(await screen.findByText("Step A")).toBeInTheDocument();
```

If `@testing-library/user-event` is not installed, check `dashboard/package.json`.

### No Convex / Backend Changes

This story touches ONLY frontend files. No Convex queries, mutations, or schema changes are required. The `blockedBy` field is already populated by `batchCreate` (step materializer) and `checkAndUnblockDependents`. The `errorMessage` field is already set by `updateStatus` on crash (hardened in Story 3.1). Both are already available on `Doc<"steps">`.

### Running Tests

```bash
cd /Users/ennio/Documents/nanobot-ennio/dashboard && npx vitest run components/StepCard.test.tsx
```

To run all dashboard tests (regression check):
```bash
cd /Users/ennio/Documents/nanobot-ennio/dashboard && npx vitest run
```

### Project Structure Notes

- **Files to modify:**
  - `dashboard/components/StepCard.tsx` — add `blockingStepTitles` prop, tooltip on lock icon, opacity on blocked wrapper, tooltip on AlertTriangle/Crashed badge
  - `dashboard/components/KanbanBoard.tsx` — build `stepTitleById` map, compute `blockingStepTitles` per step, update `stepGroups` type
  - `dashboard/components/KanbanColumn.tsx` — update `stepGroups` type to include `blockingStepTitles` per step, forward `blockingStepTitles` to `StepCard`
  - `dashboard/components/StepCard.test.tsx` — add 5 new tests for blocked tooltip, opacity class, crashed error tooltip, truncation
- **No new files** (tests extend existing file)
- **No schema changes**, **no Python changes**, **no Convex mutation changes**
- **No new npm packages** — `lucide-react`, `motion/react-client`, and `@radix-ui/react-tooltip` (via ShadCN) are already installed

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.2] — Acceptance criteria for this story (lines 825–847)
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Component Specs] — `TaskCard` state specs: "Crashed (red border + red badge)", "Done (opacity 0.7)"; badge design tokens (lines 774–781)
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Design Tokens] — `--muted: Slate-400 — disabled, inactive` (line 273); `Error / Crashed: #EF4444 (red-500)` (line 261)
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Animations] — `layoutId` card transition for column changes (line 300, 767)
- [Source: _bmad-output/planning-artifacts/architecture.md#Step Lifecycle FR29-FR34] — `StepCard.tsx (crashed badge, blocked icon)` listed as the frontend component for FR30 (line 856)
- [Source: dashboard/components/StepCard.tsx] — Existing component: already has Lock, AlertTriangle, Crashed badge, Blocked badge (115 lines)
- [Source: dashboard/components/KanbanBoard.tsx#stepStatusToColumnStatus] — `"blocked" → "assigned"` column mapping (lines 28–43); `allSteps` already fetched via `listAll` (line 57)
- [Source: dashboard/components/KanbanColumn.tsx] — `StepCard` rendering loop (lines 169–178); `stepGroups` prop shape (lines 18–24)
- [Source: dashboard/lib/constants.ts#STEP_STATUS_COLORS] — `blocked.border: "border-l-amber-500"`, `crashed.border: "border-l-red-500"` (lines 196–210)
- [Source: dashboard/components/ui/tooltip.tsx] — ShadCN Tooltip exports: `Tooltip`, `TooltipTrigger`, `TooltipContent`, `TooltipProvider`
- [Source: dashboard/components/AgentConfigSheet.tsx] — Existing `TooltipProvider/Tooltip/TooltipTrigger/TooltipContent` usage pattern (lines 376–395)
- [Source: dashboard/convex/schema.ts#steps] — `blockedBy: v.optional(v.array(v.id("steps")))`, `errorMessage: v.optional(v.string())` (lines 80, 86)
- [Source: _bmad-output/implementation-artifacts/3-1-implement-step-status-state-machine.md#File List] — Continuity: steps.ts hardened in 3.1; StepCard.tsx was explicitly noted as the frontend component requiring hardening in Story 3.2

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Radix Tooltip in jsdom renders content in two places: visible element + hidden aria span. Tests use `findAllByText` to handle this and query `[role="tooltip"]` for exact text matching.
- `motion/react-client` mock strips `layoutId`, `layout`, `transition` props before forwarding to DOM div; `className` prop is forwarded correctly, enabling `opacity-60` class assertion.

### Completion Notes List

- All 4 tasks completed with all 12 tests passing (7 pre-existing + 5 new).
- Full regression run: 321 tests across 24 files — all pass.
- `TooltipProvider` wraps the entire card return to allow multiple `Tooltip` instances within one card without nesting providers.
- `StepWithBlockingTitles` type defined locally in both `KanbanBoard.tsx` and `KanbanColumn.tsx` to avoid cross-file type export while keeping the prop threading clean.
- Tooltip on "Crashed" badge (footer) and on `AlertTriangle` (header) both show the same truncated errorMessage, satisfying AC 4.
- Muted styling (`opacity-60 grayscale-[0.3]`) applied to `motion.div` wrapper only when `status === "blocked"`, preserving `border-l-amber-500` accent color on the Card.

### File List

- `dashboard/components/StepCard.tsx`
- `dashboard/components/StepCard.test.tsx`
- `dashboard/components/KanbanBoard.tsx`
- `dashboard/components/KanbanColumn.tsx`

## Code Review Record

### Reviewer Model

claude-sonnet-4-6

### Review Date

2026-02-25

### AC Verification

- AC1 (blocked step — lock icon + tooltip): PASS — `StepCard.tsx` lines 101–119 render `Lock` icon conditionally for `status === "blocked"`. When `hasBlockingTitles` is true, the icon is wrapped in `Tooltip`/`TooltipTrigger`/`TooltipContent` showing each title in a `<div>` per line. When titles are empty, plain `<span>` with `aria-label="Blocked"` renders the icon.
- AC2 (blocked step — muted visual style): PASS — `motion.div` at line 72 receives `className="opacity-60 grayscale-[0.3]"` when `step.status === "blocked"`. The `border-l-amber-500` accent is on the `Card`, not the `motion.div`, so it is preserved.
- AC3 (crashed step — destructive badge): PASS — `Badge` with `bg-red-500 text-white` renders at lines 162–164. `AlertTriangle` is rendered at lines 125/132 with `text-red-500`. The `crashed` status maps to `in_progress` column (KanbanBoard lines 37–39).
- AC4 (crashed step — error message on hover): PASS — Both the `AlertTriangle` icon (lines 122–129) and the "Crashed" badge (lines 159–168) are wrapped in `Tooltip` when `hasErrorMessage` is true, showing `truncatedError` (200-char limit + "...").
- AC5 (unblock transition — smooth animation): PASS — `layoutId={step._id}` preserved at line 73. No animation code changes were needed; transition is automatic.
- AC6 (accessibility): PARTIAL FIX APPLIED — The `AlertTriangle` `TooltipTrigger` span has `aria-label={crashedAriaLabel}` (line 124). The "Crashed" badge `TooltipTrigger` span was missing `aria-label` in the original implementation; fixed in review to `aria-label="Crashed badge: show error details"` (line 161) to distinguish it from the icon trigger and avoid duplicate label errors. The `Lock` icon trigger has `aria-label={blockingAriaLabel}` (line 105). The `StepCard` `aria-label` includes step status (line 90).
- AC7 (tests): PASS — 5 new tests added covering all specified scenarios; all 12 tests (7 pre-existing + 5 new) pass.

### Findings

**Finding 1 — HIGH — Import ordering violation: `type` declaration between import statements in `KanbanBoard.tsx`**
- File: `dashboard/components/KanbanBoard.tsx` line 8 (before fix)
- `type StepWithBlockingTitles` was placed between two import groups (between `import { Doc, Id }` and `import { LayoutGroup }`). While valid TypeScript, this causes some tools (e.g., IDE language servers using `isolatedModules`) to emit TS6196-style warnings because the type appears before subsequent imports complete hoisting analysis.
- Fix: Moved `type StepWithBlockingTitles` to after all imports (now at line 14).
- Status: FIXED

**Finding 2 — HIGH — Import ordering violation: `type` declaration between import statements in `KanbanColumn.tsx`**
- File: `dashboard/components/KanbanColumn.tsx` line 12 (before fix)
- Same pattern as Finding 1 — `type StepWithBlockingTitles` was inserted between `import { Doc, Id }` and `import { Eraser, List }`.
- Fix: Moved `type StepWithBlockingTitles` to after all imports (now at line 15).
- Status: FIXED

**Finding 3 — MEDIUM — Missing `aria-label` on Crashed badge `TooltipTrigger` span (AC6 violation)**
- File: `dashboard/components/StepCard.tsx` line 161 (before fix)
- The `<span>` wrapping the "Crashed" badge inside its `TooltipTrigger` lacked an `aria-label`. AC6 requires all new icon + tooltip pairs to be accessible with a descriptive label.
- Fix: Added `aria-label="Crashed badge: show error details"` to the span. A distinct label (not reusing `crashedAriaLabel`) is required to avoid duplicate-label errors in tests that use `getByLabelText(/^Crashed:/)` for the icon trigger.
- Status: FIXED

### Test Results After Fixes

- `StepCard.test.tsx`: 12/12 tests pass
- Full regression: 321/321 tests pass across 24 files
