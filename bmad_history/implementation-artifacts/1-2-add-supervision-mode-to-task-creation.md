# Story 1.2: Add Supervision Mode to Task Creation

Status: done

## Dependencies

**BLOCKER: Story 1.1 (Extend Convex Schema for Task/Step Hierarchy) MUST be completed first.** Story 1.1 adds the `supervisionMode` field to the `tasks` table in `dashboard/convex/schema.ts`. This story assumes that field already exists in the schema. Do NOT re-add the schema field. If Story 1.1 has not been completed, stop and complete it first.

Specifically, Story 1.1 adds this to the tasks table definition in `schema.ts`:
```typescript
supervisionMode: v.optional(v.string()), // "autonomous" | "supervised"
```

## Story

As a **user**,
I want to select autonomous or supervised mode when creating a task,
So that I can choose whether to review the execution plan before agents start working.

## Acceptance Criteria

1. **Supervision mode selector visible in expanded options** — Given the TaskInput component on the dashboard, when the user expands the task creation options (clicks the chevron toggle), then a supervision mode selector is visible with two options: "Autonomous" (default) and "Supervised". The selector uses a ShadCN `Select` component consistent with the existing design system.

2. **Task created with selected supervision mode** — Given the user types a task description and selects a supervision mode, when the user submits the task, then the task is created in Convex with the selected `supervisionMode` value ("autonomous" or "supervised") and the task card appears in the Inbox column on the Kanban board.

3. **Default supervision mode is autonomous** — Given the user submits a task without explicitly selecting supervision mode (collapsed panel or default left unchanged), when the task is created, then the `supervisionMode` defaults to "autonomous".

4. **Supervision mode persisted on task record** — Given the task is created with supervision mode set, when the task record is queried from Convex, then the `supervisionMode` field reflects the user's selection.

## Tasks / Subtasks

- [x] **Task 1: Add `supervisionMode` arg to the `tasks.create` mutation** (AC: 2, 3, 4)
  - [x] 1.1 Add `supervisionMode: v.optional(v.string())` to the `args` validator in `tasks.create`
  - [x] 1.2 In the handler, resolve the supervision mode value: use `args.supervisionMode ?? "autonomous"` — for manual tasks, always set `"autonomous"`
  - [x] 1.3 Include `supervisionMode` in the `ctx.db.insert("tasks", {...})` call
  - [x] 1.4 Optionally append supervision mode info to the activity event description (e.g., `(supervised)` when not autonomous)

- [x] **Task 2: Add supervision mode state and UI to TaskInput component** (AC: 1, 3)
  - [x] 2.1 Add `supervisionMode` state variable: `const [supervisionMode, setSupervisionMode] = useState<string>("autonomous");`
  - [x] 2.2 Add a new `Select` component for supervision mode inside the `CollapsibleContent` panel, positioned after the Trust Level selector
  - [x] 2.3 Reset `supervisionMode` to `"autonomous"` on successful submission (alongside the existing resets)
  - [x] 2.4 Reset `supervisionMode` to `"autonomous"` when switching to manual mode

- [x] **Task 3: Wire supervision mode into the submission flow** (AC: 2, 3, 4)
  - [x] 3.1 Update the `args` type definition in `handleSubmit` to include `supervisionMode?: string`
  - [x] 3.2 For non-manual tasks: always include `supervisionMode` in the args (even when "autonomous", so the field is always set)
  - [x] 3.3 For manual tasks: set `supervisionMode: "autonomous"` explicitly (manual tasks are always autonomous)

- [x] **Task 4: Update tests** (AC: 1, 2, 3)
  - [x] 4.1 Add test: "shows supervision mode selector when expanded" — expand panel, verify "Supervision Mode" label and "Autonomous" default are visible
  - [x] 4.2 Add test: "submits with supervisionMode autonomous by default" — create task without changing mode, assert mutation called with `supervisionMode: "autonomous"`
  - [x] 4.3 Add test: "submits with supervisionMode supervised when selected" — expand, change to Supervised, submit, assert mutation called with `supervisionMode: "supervised"`
  - [x] 4.4 Add test: "resets supervision mode after submission" — submit a supervised task, verify mode resets to autonomous
  - [x] 4.5 Update existing submission tests to include `supervisionMode: "autonomous"` in expected args if the implementation always sends it

## Dev Notes

### Exact Files to Modify

| File | What Changes | Lines of Interest |
|------|-------------|-------------------|
| `dashboard/convex/tasks.ts` | Add `supervisionMode` arg to `create` mutation, include in db insert | Lines 77-161 (the `create` mutation) |
| `dashboard/components/TaskInput.tsx` | Add supervision mode state, UI selector, wire to submission | Lines 31-368 (entire component) |
| `dashboard/components/TaskInput.test.tsx` | Add 4-5 new tests for supervision mode behavior | Lines 109+ (after existing expansion tests) |

### What NOT to Change

- **`dashboard/convex/schema.ts`** — Do NOT modify. Story 1.1 adds the `supervisionMode` field. This story only uses it.
- **`dashboard/components/TaskCard.tsx`** — No supervision mode display on cards in this story. That is a future concern.
- **`dashboard/components/KanbanBoard.tsx`** — No changes needed.

### Convex Mutation Changes (tasks.ts)

The `create` mutation at line 77 needs these changes:

**1. Add to args validator (line 78-95):**
```typescript
args: {
  title: v.string(),
  description: v.optional(v.string()),
  tags: v.optional(v.array(v.string())),
  assignedAgent: v.optional(v.string()),
  trustLevel: v.optional(v.string()),
  reviewers: v.optional(v.array(v.string())),
  isManual: v.optional(v.boolean()),
  boardId: v.optional(v.id("boards")),
  cronParentTaskId: v.optional(v.string()),
  supervisionMode: v.optional(v.string()),  // <-- ADD THIS
  files: v.optional(v.array(v.object({...}))),
},
```

**2. Resolve supervision mode in handler (after line 100):**
```typescript
const supervisionMode = isManual
  ? "autonomous"
  : (args.supervisionMode ?? "autonomous");
```

**3. Include in db.insert (line 123-137):**
Add `supervisionMode` to the insert object. It should always be present (not conditionally spread), since the schema field is `v.optional(v.string())` and we always have a value.

**4. Optionally enhance activity description (line 140-148):**
When `supervisionMode === "supervised"`, append `(supervised)` to the activity description, similar to how trust level is appended.

### TaskInput Component Changes

**Existing pattern to follow:**

The component already has this exact pattern for Trust Level (lines 36, 299-317):
1. State: `const [trustLevel, setTrustLevel] = useState<string>("autonomous");`
2. UI: A `Select` component with label, trigger, and items inside `CollapsibleContent`
3. Reset: `setTrustLevel("autonomous")` on successful submission (line 101)
4. Reset on manual toggle: `setTrustLevel("autonomous")` (line 186)
5. Wire to args: conditional inclusion in `handleSubmit`

**Follow the identical pattern for supervision mode.**

The supervision mode `Select` should be placed inside the `CollapsibleContent > div.space-y-3` panel (lines 273-364), after the Trust Level section (after line 317) and before the reviewer section (line 319). This groups all task configuration options logically.

**Supervision mode selector JSX (to add after the Trust Level `Select` section):**

```tsx
<div className="space-y-1">
  <label className="text-xs text-muted-foreground font-medium">Supervision Mode</label>
  <Select
    value={supervisionMode}
    onValueChange={setSupervisionMode}
  >
    <SelectTrigger className="h-9">
      <SelectValue />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="autonomous">Autonomous</SelectItem>
      <SelectItem value="supervised">Supervised</SelectItem>
    </SelectContent>
  </Select>
</div>
```

This mirrors the Trust Level selector styling exactly:
- Same `space-y-1` wrapper
- Same `text-xs text-muted-foreground font-medium` label
- Same `h-9` trigger height
- Same `Select` / `SelectTrigger` / `SelectValue` / `SelectContent` / `SelectItem` pattern

**Submission args wiring:**

In `handleSubmit`, the supervision mode should always be sent for non-manual tasks. For manual tasks, it should be set to "autonomous". Update the args building section (lines 56-82):

```typescript
// After line 69 (boardId assignment):
args.supervisionMode = isManual ? "autonomous" : supervisionMode;
```

Or more cleanly, follow the existing conditional pattern:
```typescript
if (isManual) {
  args.isManual = true;
  args.supervisionMode = "autonomous";
} else {
  args.supervisionMode = supervisionMode;
  // ... existing agent/trust/reviewer logic
}
```

**State reset on submission (line 98-104):** Add:
```typescript
setSupervisionMode("autonomous");
```

**State reset on manual mode toggle (line 183-189):** Add alongside existing resets:
```typescript
setSupervisionMode("autonomous");
```

### ShadCN Component Choice: Select (not Toggle)

The UX spec specifies `Select` for task creation dropdowns (see: UX spec component table). The existing codebase uses `Select` for both Agent selection and Trust Level selection in TaskInput. Using `Select` here maintains visual and behavioral consistency. A toggle (`Switch` or `ToggleGroup`) was considered but rejected because:
1. The existing panel uses `Select` for all configuration options
2. Future supervision modes beyond "autonomous"/"supervised" may be added
3. `Select` has consistent keyboard navigation via Radix

### Default Value Handling

The default is `"autonomous"` and is enforced at three levels:
1. **React state:** `useState<string>("autonomous")` — UI always shows a value
2. **Mutation args:** `args.supervisionMode ?? "autonomous"` — server-side fallback
3. **Schema:** `v.optional(v.string())` — allows missing (for backward compat with existing tasks)

This triple-layer defense ensures no task is ever created without a supervision mode value, while remaining backward-compatible with tasks created before this feature existed.

### Integration with Story 1.1

Story 1.1 adds the `supervisionMode` field to the tasks table schema. This story:
- Does NOT modify `schema.ts`
- USES the field by including it in the `create` mutation args and insert
- READS the field when needed (future stories display it)

If Story 1.1 has not added the field to the schema, the `ctx.db.insert` call will fail with a Convex schema validation error because the field is not defined in the table.

### Test Strategy

All tests are in `dashboard/components/TaskInput.test.tsx`. The existing test file uses:
- `vitest` with `@testing-library/react`
- Mocked `useMutation` returning `mockMutate`
- Mocked `useQuery` returning `mockAgents` for agents and `[]` for taskTags
- `fireEvent` for interactions
- `screen` queries for assertions
- `vi.waitFor` for async assertions after submission

**Important test detail:** The existing tests at lines 61-71 and 87-97 assert exact mutation args. When supervision mode is always included in args, these tests will need updating to include `supervisionMode: "autonomous"` in the expected call. Plan for this — update them as part of Task 4.5.

**Existing test patterns to follow (from lines 225-250):**
```typescript
it("submits with trustLevel and reviewers when configured", () => {
  mockMutate.mockResolvedValue("taskId123");
  render(<TaskInput />);
  // ... expand, change settings, submit
  expect(mockMutate).toHaveBeenCalledWith({
    title: "...",
    tags: undefined,
    trustLevel: "agent_reviewed",
    reviewers: ["coder"],
  });
});
```

Follow this same pattern for supervision mode tests.

### Project Structure Notes

- **Frontend components:** `dashboard/components/` — PascalCase filenames, one component per file
- **Convex mutations:** `dashboard/convex/tasks.ts` — all task mutations in one file
- **UI primitives:** `dashboard/components/ui/select.tsx` — ShadCN Select already installed and used
- **Test files:** Co-located with components as `{Component}.test.tsx`
- **Test runner:** vitest (run with `npx vitest` from `dashboard/` directory)
- **Package manager:** npm (dashboard is a Next.js project)

### References

- [Source: dashboard/convex/schema.ts] — Tasks table definition (lines 18-59), supervisionMode field added by Story 1.1
- [Source: dashboard/convex/tasks.ts#create] — Existing create mutation (lines 77-161) — the mutation to extend
- [Source: dashboard/components/TaskInput.tsx] — Full component (lines 1-368) — Trust Level Select pattern at lines 299-317, state declarations at lines 31-41, submission logic at lines 48-126, manual mode toggle at lines 180-198
- [Source: dashboard/components/TaskInput.test.tsx] — Existing tests (277 lines) — expansion tests at lines 112-129, submission assertion pattern at lines 61-71
- [Source: dashboard/components/TaskCard.tsx] — Task card rendering (reference only, no changes)
- [Source: dashboard/components/DashboardLayout.tsx#line-109] — TaskInput placement in the layout
- [Source: dashboard/components/ui/select.tsx] — ShadCN Select primitive (Radix-based, already imported in TaskInput)
- [Source: _bmad-output/planning-artifacts/architecture.md#Data Model Decisions] — supervisionMode: "autonomous" | "supervised" on task record
- [Source: _bmad-output/planning-artifacts/architecture.md#Component Tree] — TaskInput extend with supervision mode selector
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#TaskInput] — Progressive disclosure panel spec: Agent selector + Review toggle + Reviewer selector + Human approval checkbox; Select component for dropdowns
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Component Strategy] — Select, Switch, Checkbox usage in task creation
- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.2] — Full BDD acceptance criteria
- [Source: _bmad-output/implementation-artifacts/1-1-extend-convex-schema-for-task-step-hierarchy.md] — Dependency: schema changes this story depends on

## Dev Agent Record

### Agent Model Used

GPT-5 (Codex)

### Debug Log References

- `npx vitest run components/TaskInput.test.tsx`
- `npx vitest run`
- `npm run lint` (fails due pre-existing repository lint errors unrelated to this story)
- `npx vitest run convex/tasks.test.ts components/TaskInput.test.tsx`

### Completion Notes List

- Added `supervisionMode` support to `tasks.create` mutation args and persisted field with default resolution (`autonomous` fallback, forced autonomous for manual tasks).
- Updated task activity description to append `(supervised)` when non-manual tasks are created in supervised mode.
- Added `supervisionMode` state and ShadCN `Select` UI to `TaskInput` expanded options, positioned after Trust Level.
- Wired submission payloads to always include `supervisionMode` (`autonomous` for manual tasks, selected value otherwise).
- Reset `supervisionMode` to `autonomous` after successful submit and when toggling into manual mode.
- Added supervision-mode tests and updated existing submission expectations to include `supervisionMode`.
- Validation: `npx vitest run components/TaskInput.test.tsx` and `npx vitest run` both pass.
- Code-review fixes applied: restored default unassigned task status to `inbox`, tightened mutation arg validation for supervision mode literals, and added Convex-side mutation tests for defaulting/persistence behavior.
- Note on repo traceability: this workspace contains pre-existing unrelated modified files outside story scope; review and fixes here were scoped to this story's implementation files.

### File List

- dashboard/convex/tasks.ts
- dashboard/convex/tasks.test.ts
- dashboard/components/TaskInput.tsx
- dashboard/components/TaskInput.test.tsx
- _bmad-output/implementation-artifacts/1-2-add-supervision-mode-to-task-creation.md
- _bmad-output/implementation-artifacts/sprint-status.yaml

## Change Log

- 2026-02-25: Implemented Story 1.2 supervision mode creation flow (backend mutation support, TaskInput UI/state wiring, and test coverage updates).
- 2026-02-25: Code review fixes applied (status visibility fix, strict supervisionMode validation, backend persistence/defaulting tests) and story advanced to done.

## Senior Developer Review (AI)

### Outcome

Approve

### Review Date

2026-02-25

### Findings Resolved

- [x] [HIGH] Unassigned non-manual tasks were created in `planning` and could be hidden from the Kanban flow expected by this story. Fixed by restoring default creation status to `inbox` when no agent is assigned.
- [x] [MEDIUM] `supervisionMode` accepted arbitrary strings in mutation args. Fixed with literal union validation (`autonomous` | `supervised`).
- [x] [MEDIUM] AC4 backend persistence/defaulting lacked direct Convex mutation tests. Fixed by adding `dashboard/convex/tasks.test.ts` with mutation handler assertions.
- [x] [MEDIUM] Git/story traceability discrepancy in this dirty workspace was documented explicitly as out-of-scope pre-existing changes.

### Verification

- `npx vitest run convex/tasks.test.ts components/TaskInput.test.tsx` passed.
- `npx vitest run` passed (`236/236`).
