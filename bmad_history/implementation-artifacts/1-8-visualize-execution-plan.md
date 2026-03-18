# Story 1.8: Visualize Execution Plan

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to see the execution plan showing steps, dependencies, parallel groups, and assigned agents,
So that I understand the full structure of how my goal will be accomplished before and during execution.

## Acceptance Criteria

1. **Plan renders with all step details** — Given a task has an `executionPlan` on its record (before or after kick-off), when the user opens the task detail and navigates to the Execution Plan tab, then the `ExecutionPlanTab` displays all steps from the plan with: step title, assigned agent, parallel group indicator, and dependency relationships.

2. **Dependency visualization** — Given steps have dependency relationships (blockedBy), when the execution plan renders, then visual indicators (lines, arrows, or indentation) show which steps depend on which. Parallel steps (same parallelGroup) are visually grouped side by side or in a parallel lane.

3. **Status color coding after kick-off** — Given steps are in various statuses (after kick-off), when the plan visualization renders, then each step shows its current status with the appropriate color coding (consistent with Kanban status badges). Completed steps are visually distinct from pending/running steps.

4. **Loading state for planning tasks** — Given the user opens the execution plan for a task still in "planning" status, when the plan has not yet been generated, then a muted placeholder displays: "Generating execution plan..." with a loading indicator.

5. **Performance** — Given the task's `executionPlan` field is populated, when the ExecutionPlanTab renders, then it renders within 2 seconds (leveraging Convex reactive queries for real-time data).

## Tasks / Subtasks

- [x] **Task 1: Refactor ExecutionPlanTab for architecture-aligned data model** (AC: 1, 5)
  - [x] 1.1 Update `ExecutionPlanStep` interface to support both pre-kickoff plan data (`executionPlan` on task) and post-kickoff live step data (from `steps` table)
  - [x] 1.2 Add `title` field support (architecture uses `title` + `description`; existing code only uses `description`)
  - [x] 1.3 Update `parallelGroup` type from `string | undefined` to `number | string | undefined` (architecture specifies `number`)
  - [x] 1.4 Update `dependsOn` field name to also accept `blockedBy` (architecture uses `blockedBy`; existing code uses `dependsOn`)

- [x] **Task 2: Add "Generating execution plan..." loading state** (AC: 4)
  - [x] 2.1 Accept task status as a prop (or a `isPlanning` boolean)
  - [x] 2.2 When task status is "planning" and `executionPlan` is null/undefined, render: muted text "Generating execution plan..." with a `Loader2` spinner icon
  - [x] 2.3 Update existing test to cover the new loading state

- [x] **Task 3: Enhance parallel group visualization** (AC: 1, 2)
  - [x] 3.1 Group consecutive steps with the same `parallelGroup` into a visual container (bordered box or lane)
  - [x] 3.2 Inside the parallel group container, render steps side-by-side (flex row) rather than stacked vertically
  - [x] 3.3 Display parallel group label badge at the top of the container (keep existing "Parallel" badge, enhance with group number)

- [x] **Task 4: Enhance dependency visualization** (AC: 2)
  - [x] 4.1 Replace simple `border-l-2` indentation with a proper dependency connector: vertical line from parent step to dependent step with a small arrow or dot at the connection point
  - [x] 4.2 For steps with `blockedBy`/`dependsOn`, render a small "depends on: Step N" label showing which steps they wait on
  - [x] 4.3 Ensure dependency lines connect across parallel group boundaries (a step in group 2 depending on steps in group 1)

- [x] **Task 5: Implement status color coding aligned with Kanban badges** (AC: 3)
  - [x] 5.1 Add a `StepStatusBadge` sub-component that uses `STATUS_COLORS` from `@/lib/constants` (or step-specific equivalents) for consistent coloring
  - [x] 5.2 Map step status values to visual treatments: `planned` = gray/muted, `assigned` = cyan, `blocked` = amber with lock icon, `running` = blue with spinner, `completed` = green with checkmark, `crashed` = red with X icon
  - [x] 5.3 Completed steps get reduced opacity (0.7) to visually recede; running steps get full opacity and subtle pulse
  - [x] 5.4 Preserve backward compatibility with existing status values (`pending`, `in_progress`, `failed`) used in current tests

- [x] **Task 6: Wire up live step data from Convex `steps` table (post-kickoff)** (AC: 1, 3, 5)
  - [x] 6.1 In `TaskDetailSheet.tsx`, add a `useQuery` call to fetch steps by taskId from `steps.getByTask` (when `steps` table exists — Story 1.1 dependency)
  - [x] 6.2 Pass live step data to `ExecutionPlanTab` as an optional `liveSteps` prop
  - [x] 6.3 When `liveSteps` are available, merge them with `executionPlan` snapshot — live step status takes precedence over snapshot status
  - [x] 6.4 When `liveSteps` are NOT available (pre-kickoff or `steps` table doesn't exist yet), fall back to `executionPlan` data only

- [x] **Task 7: Update tests** (AC: 1, 2, 3, 4)
  - [x] 7.1 Add test for loading state ("Generating execution plan..." when planning)
  - [x] 7.2 Add test for parallel group visual container rendering
  - [x] 7.3 Add test for status color mapping (step statuses: planned, assigned, running, completed, crashed, blocked)
  - [x] 7.4 Add test for dependency label rendering ("depends on: Step N")
  - [x] 7.5 Ensure all existing tests continue to pass (backward compatibility)

## Dev Notes

### CRITICAL: What Already Exists (Do NOT Reinvent)

The `ExecutionPlanTab` component at `dashboard/components/ExecutionPlanTab.tsx` **already implements a working baseline.** The developer MUST read and understand it before making changes. Here is what it currently does:

**Existing features (KEEP and ENHANCE):**

| Feature | Current Implementation | What to Enhance |
|---|---|---|
| Step list rendering | Flat vertical list with step number, description, agent, status icon | Add `title` field support, improve layout for parallel groups |
| Status icons | `StepStatusIcon` sub-component: `completed` = green CheckCircle2, `in_progress` = blue spinning Loader2, `failed` = red XCircle, default = gray Circle | Add `planned`, `assigned`, `blocked`, `crashed`, `running` status mappings; add color-coded Badge alongside icon |
| Progress counter | "N/M steps completed" at top | Keep as-is |
| Parallel group indicator | "Parallel" Badge appears when consecutive steps share a `parallelGroup` value | Enhance: render parallel steps side-by-side in a visual lane/container |
| Dependency indication | Steps with `dependsOn.length > 0` get `ml-4 border-l-2 border-border pl-3` indentation | Enhance: add dependency connector lines, "depends on: Step N" labels |
| Assigned agent display | Agent name in muted text below description | Keep as-is |
| Empty/null handling | Shows "Direct execution -- no multi-step plan" when plan is null/empty | Keep; ADD "Generating execution plan..." state for planning tasks |

**Existing interface (must maintain backward compatibility):**

```typescript
interface ExecutionPlanStep {
  stepId: string;
  description: string;
  assignedAgent?: string;
  dependsOn: string[];
  parallelGroup?: string;
  status: string;
}

interface ExecutionPlanTabProps {
  executionPlan: { steps: ExecutionPlanStep[]; createdAt: string } | null | undefined;
}
```

**Existing test file** at `dashboard/components/ExecutionPlanTab.test.tsx` has 10 tests covering:
- null/undefined/empty plan handling
- Step description rendering
- Progress counter
- Status icon CSS classes (completed, in_progress, failed, pending)
- Parallel group label
- Assigned agent name
- Dependency indentation (border-l-2)

ALL existing tests MUST continue to pass after changes.

### Architecture-Aligned Data Model (Target State)

The architecture defines an `ExecutionPlan` type on the task record (pre-kickoff):

```typescript
type ExecutionPlan = {
  steps: Array<{
    tempId: string           // Temporary ID for pre-kickoff editing
    title: string            // Step title (NEW — existing code uses description only)
    description: string
    assignedAgent: string
    blockedBy: string[]      // Architecture uses "blockedBy" (existing code uses "dependsOn")
    parallelGroup: number    // Architecture specifies number (existing code uses string)
    order: number
    attachedFiles?: string[] // Optional file attachments per step
  }>
  generatedAt: string        // ISO 8601
  generatedBy: "lead-agent"
}
```

After kick-off (Story 1.6), each plan step is materialized into a real record in the `steps` Convex table:

```typescript
// Steps table schema (from Story 1.1)
steps: defineTable({
  taskId: v.id("tasks"),
  title: v.string(),
  description: v.string(),
  assignedAgent: v.string(),
  status: v.string(),        // "planned" | "assigned" | "running" | "completed" | "crashed" | "blocked"
  blockedBy: v.optional(v.array(v.id("steps"))),
  parallelGroup: v.number(),
  order: v.number(),
  createdAt: v.string(),
  startedAt: v.optional(v.string()),
  completedAt: v.optional(v.string()),
  errorMessage: v.optional(v.string()),
}).index("by_taskId", ["taskId"])
```

**The `executionPlan` on the task record is preserved as a snapshot of the original plan.** After kick-off, live status comes from the `steps` table, not the snapshot.

### Data Flow: Pre-Kickoff vs. Post-Kickoff

```
PRE-KICKOFF (task.status = "planning" or "reviewing_plan"):
  ExecutionPlanTab receives: task.executionPlan
  Data source: executionPlan field on task record
  Step statuses: all "planned" (static snapshot)
  Use case: user sees the plan before agents start executing

POST-KICKOFF (task.status = "running" or "completed" or "failed"):
  ExecutionPlanTab receives: task.executionPlan (snapshot) + liveSteps (from steps table)
  Data source: Convex reactive query on steps table (real-time updates)
  Step statuses: live values from steps table (assigned, running, completed, crashed, blocked)
  Use case: user watches execution progress in real-time
```

### Updated Props Interface (Target)

```typescript
interface ExecutionPlanStep {
  stepId: string;
  title?: string;              // NEW: from architecture (optional for backward compat)
  description: string;
  assignedAgent?: string;
  dependsOn: string[];         // KEEP: existing field name
  blockedBy?: string[];        // NEW: architecture field name (alias)
  parallelGroup?: string | number;  // WIDENED: accept both string and number
  status: string;
  order?: number;              // NEW: for sorting
  errorMessage?: string;       // NEW: for crashed steps
}

interface ExecutionPlanTabProps {
  executionPlan: { steps: ExecutionPlanStep[]; createdAt: string } | null | undefined;
  liveSteps?: Array<{          // NEW: real-time step data from Convex steps table
    _id: string;
    title: string;
    description: string;
    assignedAgent: string;
    status: string;
    blockedBy?: string[];
    parallelGroup: number;
    order: number;
    errorMessage?: string;
    startedAt?: string;
    completedAt?: string;
  }>;
  isPlanning?: boolean;        // NEW: true when task is in "planning" status
}
```

### Step Status to Visual Treatment Mapping

The component must handle BOTH existing status values (from current tests) and architecture status values (from steps table):

| Step Status | Icon | Color | Opacity | Badge Text | Notes |
|---|---|---|---|---|---|
| `planned` | Circle (outline) | gray/muted-foreground | 0.7 | "Planned" | Pre-kickoff default |
| `pending` | Circle (outline) | gray/muted-foreground | 0.7 | "Pending" | EXISTING — backward compat alias for "planned" |
| `assigned` | Circle (filled dot) | cyan-500 | 1.0 | "Assigned" | Ready for dispatch |
| `blocked` | Lock icon | amber-500 | 0.7 | "Blocked" | Waiting on dependencies |
| `running` | Loader2 (spinning) | blue-500 | 1.0 | "Running" | Agent is executing |
| `in_progress` | Loader2 (spinning) | blue-500 | 1.0 | "In Progress" | EXISTING — backward compat alias for "running" |
| `completed` | CheckCircle2 | green-500 | 0.6 | "Done" | Finished successfully |
| `crashed` | XCircle | red-500 | 1.0 | "Crashed" | Error — show errorMessage if available |
| `failed` | XCircle | red-500 | 1.0 | "Failed" | EXISTING — backward compat alias for "crashed" |

**Color consistency with Kanban:** Use the same Tailwind color families as `STATUS_COLORS` in `dashboard/lib/constants.ts`:
- blue for in-progress/running
- green for done/completed
- red for crashed/failed
- amber for blocked/retrying
- cyan for assigned
- violet for planned/pending (or gray/muted)

### Parallel Group Visualization Pattern

**Current:** Consecutive steps with the same `parallelGroup` get a "Parallel" Badge label at the first step. Steps are rendered vertically.

**Target:** Steps in the same parallel group are rendered inside a visual container with a side-by-side layout.

```
[Parallel Group 1]
+--------------------------------------------------+
| "Parallel"  (badge)                              |
| +---------------------+  +---------------------+ |
| | Step 1: Research    |  | Step 2: Analyze     | |
| | Agent: researcher   |  | Agent: analyst      | |
| | Status: running     |  | Status: assigned    | |
| +---------------------+  +---------------------+ |
+--------------------------------------------------+
       |
       | (dependency line — "depends on: Steps 1, 2")
       v
+---------------------+
| Step 3: Synthesize  |
| Agent: writer       |
| Status: blocked     |
+---------------------+
```

**Implementation approach:**
1. Group steps by `parallelGroup` value
2. For groups with 2+ steps, render a container `div` with `flex flex-row flex-wrap gap-3` and a border/background
3. For groups with exactly 1 step (sequential), render normally without a container
4. Between groups, render dependency connectors (vertical line with arrow)

### Dependency Visualization Pattern

**Current:** Steps with `dependsOn.length > 0` get `ml-4 border-l-2 border-border pl-3` — a left indent with a border.

**Target:** More explicit dependency visualization:

1. **Between parallel groups:** A vertical connector line from the bottom of group N to the top of group N+1 (when group N+1 depends on group N). Use a thin border-left line with a small downward arrow or chevron.

2. **Dependency labels:** Each step with dependencies shows a small muted label: "depends on: Step 1, Step 2" (using step titles or numbers). This makes the dependency explicit without requiring the user to trace visual lines.

3. **Keep the indentation pattern** for simple cases (single step depending on a single step) — it is already clear and tested.

**CSS approach (no external dependency library needed):**

```tsx
{/* Between parallel groups — dependency connector */}
<div className="flex flex-col items-center py-1">
  <div className="w-px h-4 bg-border" />
  <ChevronDown className="h-3 w-3 text-muted-foreground" />
</div>
```

### Loading State for "Planning" Tasks

When `isPlanning` is true and `executionPlan` is null/undefined:

```tsx
<div className="flex flex-col items-center justify-center py-12 gap-3">
  <Loader2 className="h-6 w-6 text-muted-foreground animate-spin" />
  <p className="text-sm text-muted-foreground">
    Generating execution plan...
  </p>
</div>
```

This takes priority over the "Direct execution" message. The logic order is:
1. If `isPlanning && !executionPlan` -> show "Generating execution plan..."
2. If `!executionPlan || executionPlan.steps.length === 0` -> show "Direct execution"
3. Otherwise -> render the plan

### TaskDetailSheet Integration Changes

In `dashboard/components/TaskDetailSheet.tsx` (line 253-255), the ExecutionPlanTab is currently rendered as:

```tsx
<TabsContent value="plan" className="flex-1 min-h-0 m-0 px-6 py-4">
  <ExecutionPlanTab executionPlan={(task as any).executionPlan ?? null} />
</TabsContent>
```

**Changes needed:**

1. Add `isPlanning` prop: pass `task.status === "planning"` (or `task.status === "inbox"` as the current equivalent — see note below about status mapping)
2. Add `liveSteps` prop: when the `steps` table and `steps.getByTask` query exist (Story 1.1 dependency), add a `useQuery` call and pass the results
3. Remove the `as any` cast once the `executionPlan` field typing is tightened

**IMPORTANT STATUS NOTE:** The current task statuses are the EXISTING values (`inbox`, `assigned`, `in_progress`, etc.), NOT the architecture values (`planning`, `reviewing_plan`, `running`, etc.). Story 1.1 notes that status migration is a SEPARATE concern. For now, map:
- `isPlanning` = `task.status === "inbox"` (existing equivalent of "planning")
- Post-kickoff = `task.status === "in_progress"` (existing equivalent of "running")

When status values are migrated in a future story, update the mapping.

### Live Steps Query (Story 1.1 Dependency)

The `steps` table and `steps.getByTask` query DO NOT EXIST YET. They are created in Story 1.1. This story should:

1. **Implement the component enhancements (Tasks 1-5, 7) WITHOUT the live steps integration.** These work purely from the `executionPlan` snapshot prop.
2. **Task 6 (live steps wiring) can be deferred** until Story 1.1 is complete, OR implemented with a graceful guard:

```tsx
// In TaskDetailSheet.tsx — safe to add even before steps table exists
const liveSteps = useQuery(
  api.steps?.getByTask,                    // Will be undefined if steps.ts doesn't exist yet
  taskId ? { taskId } : "skip",
) ?? undefined;
```

If `api.steps` is not yet available (module doesn't exist), the query simply won't execute. The component falls back to `executionPlan` snapshot data.

**Recommended approach:** Add the `liveSteps` prop to the interface now, but only wire it up in TaskDetailSheet after Story 1.1 lands. This keeps the component ready for live data without a hard dependency.

### Merging Live Steps with Execution Plan Snapshot

When both `executionPlan` and `liveSteps` are available (post-kickoff):

```typescript
function mergeStepsWithLiveData(
  planSteps: ExecutionPlanStep[],
  liveSteps: LiveStep[]
): ExecutionPlanStep[] {
  // Create a map of live steps by their order (or title match)
  // Live step status takes precedence over snapshot status
  return planSteps.map((planStep, index) => {
    const liveStep = liveSteps.find(
      (ls) => ls.order === index + 1 || ls.title === planStep.title
    );
    if (liveStep) {
      return {
        ...planStep,
        status: liveStep.status,
        errorMessage: liveStep.errorMessage,
        // Preserve plan structure (dependencies, groups) from snapshot
      };
    }
    return planStep;
  });
}
```

### File Inventory

| File | Action | Description |
|---|---|---|
| `dashboard/components/ExecutionPlanTab.tsx` | **MODIFY** | Primary component — all visual enhancements |
| `dashboard/components/ExecutionPlanTab.test.tsx` | **MODIFY** | Add new tests, preserve existing ones |
| `dashboard/components/TaskDetailSheet.tsx` | **MODIFY** | Pass `isPlanning` prop; wire `liveSteps` when available |
| `dashboard/lib/constants.ts` | **READ ONLY** | Reference for `STATUS_COLORS` — do NOT modify |

### Dependencies on Other Stories

| Story | Dependency Type | What It Provides | Impact on This Story |
|---|---|---|---|
| **1.1: Extend Convex Schema** | Hard (for Task 6 only) | `steps` table, `steps.getByTask` query | Without it, live step data is unavailable — component falls back to `executionPlan` snapshot |
| **1.6: Materialize Steps** | Soft | `steps` records created on kick-off | Without it, there are no live steps to display — but the `executionPlan` snapshot still works |
| None | — | Tasks 1-5, 7 are **independent** | Can be implemented immediately with no blocking dependencies |

### Testing Strategy

**Unit tests (Vitest + React Testing Library):**

1. **Loading state:** Render with `isPlanning={true}` and `executionPlan={null}` -> assert "Generating execution plan..." text and spinner presence
2. **Parallel group container:** Render with 2+ steps in same parallelGroup -> assert container element with flex-row layout exists
3. **Status badge colors:** Render steps with each status value -> assert correct CSS classes:
   - `planned`/`pending` -> `text-muted-foreground`
   - `assigned` -> `text-cyan-500`
   - `blocked` -> `text-amber-500`
   - `running`/`in_progress` -> `text-blue-500` + `animate-spin`
   - `completed` -> `text-green-500`
   - `crashed`/`failed` -> `text-red-500`
4. **Dependency labels:** Render step with `dependsOn: ["s1"]` -> assert "depends on" label text is present
5. **Backward compatibility:** ALL 10 existing tests pass unchanged
6. **Title + description:** Render step with both `title` and `description` -> both are displayed
7. **Live steps merge:** (when applicable) Render with both `executionPlan` and `liveSteps` -> live status overrides snapshot status

**Manual testing checklist:**
- Open task detail sheet, click "Execution Plan" tab
- Verify plan renders with steps, agents, groups, dependencies
- Watch a running task — verify status icons update in real-time
- Open a task in "planning" (inbox) status — verify loading indicator
- Verify parallel steps render side-by-side, not stacked

### Implementation Order

1. **Task 2** (loading state) — simplest, standalone change
2. **Task 1** (interface updates) — expand types for backward + forward compat
3. **Task 5** (status colors) — visual enhancement, self-contained
4. **Task 3** (parallel groups) — layout restructure
5. **Task 4** (dependency visualization) — builds on group layout
6. **Task 7** (tests) — write tests after each task, final pass at end
7. **Task 6** (live steps wiring) — LAST, depends on Story 1.1

### References

- [Source: dashboard/components/ExecutionPlanTab.tsx] — Existing component to enhance
- [Source: dashboard/components/ExecutionPlanTab.test.tsx] — Existing test suite (10 tests)
- [Source: dashboard/components/TaskDetailSheet.tsx:253-255] — Where ExecutionPlanTab is rendered
- [Source: dashboard/lib/constants.ts:87-131] — STATUS_COLORS mapping for Kanban badges
- [Source: dashboard/convex/schema.ts:41] — executionPlan field (v.optional(v.any()))
- [Source: dashboard/convex/tasks.ts:163-167,299-314] — getById query, updateExecutionPlan mutation
- [Source: _bmad-output/planning-artifacts/architecture.md#Data Model] — ExecutionPlan type, steps table schema, step status values
- [Source: _bmad-output/planning-artifacts/architecture.md#Plan Materialization Pattern] — Pre-kickoff snapshot preserved, steps materialized on kick-off
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#TaskDetailSheet] — "Vertical step list with status icons, step dependencies shown as connecting lines"
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Novel Patterns] — "Lead Agent's dependency table rendered as a visual flow on task detail -- live-updating as steps complete"
- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.8] — Full BDD acceptance criteria
- [Source: _bmad-output/implementation-artifacts/1-1-extend-convex-schema-for-task-step-hierarchy.md] — Steps table schema, dependency unblocking algorithm

## Dev Agent Record

### Agent Model Used

- GPT-5 Codex (Codex Desktop)

### Debug Log References

- `npm test -- ExecutionPlanTab.test.tsx`
- `npm test -- TaskDetailSheet.test.tsx`
- `npm test`
- `npx eslint components/ExecutionPlanTab.tsx components/ExecutionPlanTab.test.tsx components/TaskDetailSheet.tsx`
- `npm run lint` (fails due unrelated pre-existing errors in files outside this story's scope)
- `npm test -- ExecutionPlanTab.test.tsx` (post-review fixes)
- `npm test -- TaskDetailSheet.test.tsx` (post-review regression)
- `npx eslint components/ExecutionPlanTab.tsx components/ExecutionPlanTab.test.tsx` (post-review targeted lint)

### Completion Notes List

- Added `isPlanning` loading state with spinner and "Generating execution plan..." placeholder.
- Refactored execution plan step typing to support `title`, `blockedBy`, widened `parallelGroup`, `order`, and `errorMessage` with backward compatibility.
- Added live step merge logic so `steps` table statuses override snapshot statuses when available.
- Implemented status icon and badge mapping for `planned/pending/assigned/blocked/running/in_progress/completed/crashed/failed` with Kanban-aligned color families.
- Enhanced rendering with parallel group lanes (side-by-side cards) and group badges.
- Enhanced dependency visualization with explicit "depends on" labels, retained indentation for simple cases, and added cross-group connector arrows.
- Expanded unit tests to cover planning loading state, parallel lane rendering, dependency labels, status mappings, title+description rendering, and live-status precedence.
- Full dashboard test suite passed (233 tests); repo-wide lint remains red because of unrelated pre-existing errors outside modified story files.
- Code-review fix: hardened execution plan status handling so pre-kickoff plan steps without `status` no longer crash the tab and default to `planned`.
- Code-review fix: live `blockedBy` step IDs are now mapped back to plan step identities/order to keep dependency labels and cross-group connectors human-readable.
- Code-review fix: expanded test coverage for missing `status` and live `blockedBy` mapping paths.
- Code-review fix: File List expanded to match current dashboard git reality in this dirty workspace for traceability.

### File List

- dashboard/components/ExecutionPlanTab.tsx
- dashboard/components/ExecutionPlanTab.test.tsx
- dashboard/components/TaskDetailSheet.tsx
- dashboard/components/TaskInput.tsx *(pre-existing unrelated workspace change)*
- dashboard/components/TaskInput.test.tsx *(pre-existing unrelated workspace change)*
- dashboard/convex/schema.ts *(pre-existing unrelated workspace change)*
- dashboard/convex/tasks.ts *(pre-existing unrelated workspace change)*
- dashboard/convex/activities.ts *(pre-existing unrelated workspace change)*
- dashboard/convex/agents.ts *(pre-existing unrelated workspace change)*
- dashboard/convex/_generated/api.d.ts *(pre-existing unrelated workspace change)*
- dashboard/lib/constants.ts *(pre-existing unrelated workspace change)*

## Change Log

- 2026-02-25: Implemented Story 1.8 execution plan visualization enhancements and test updates; story moved to review.
- 2026-02-25: Applied code-review fixes for missing-status safety and live dependency mapping; story moved to done.

## Senior Developer Review (AI)

### Outcome

Approve

### Review Date

2026-02-25

### Findings Resolved

- [x] [HIGH] Guarded missing step status in `ExecutionPlanTab` to prevent runtime crashes on architecture-shaped pre-kickoff plans.
- [x] [HIGH] Fixed live dependency mapping so `blockedBy` Convex step IDs resolve back to plan step identities for labels/connectors.
- [x] [MEDIUM] Added targeted tests for missing `status` and live `blockedBy` mapping paths.
- [x] [MEDIUM] Reconciled story File List with current dashboard git changes and documented unrelated pre-existing workspace modifications.

### Verification

- `npm test -- ExecutionPlanTab.test.tsx` passed (20/20).
- `npm test -- TaskDetailSheet.test.tsx` passed (17/17).
- `npx eslint components/ExecutionPlanTab.tsx components/ExecutionPlanTab.test.tsx` passed.
