# Story 4.3: Build Execution Plan Visualization

Status: done

## Story

As a **user**,
I want to see the Lead Agent's execution plan on the task detail panel,
So that I understand how work is being organized and track step-by-step progress.

## Acceptance Criteria

1. **Given** a task has an execution plan (the `executionPlan` JSON field is populated), **When** the user clicks the task card to open TaskDetailSheet, **Then** the "Execution Plan" tab is available and displays the plan
2. **Given** the Execution Plan tab is active, **Then** steps are displayed as a vertical list with: step number, description, assigned agent name, and status icon (pending: gray circle, in_progress: blue spinner, completed: green checkmark, failed: red X)
3. **Given** steps have dependencies, **Then** connecting lines or indentation visually indicate which steps depend on others
4. **Given** steps are in a parallel group, **Then** they are grouped visually (e.g., side-by-side or with a "Parallel" label)
5. **Given** execution plan steps are completing, **When** a step status changes in Convex, **Then** the visualization updates in real-time (status icon changes, completed steps show green checkmark)
6. **Given** a task has no execution plan (single-step or directly assigned), **When** the user opens TaskDetailSheet, **Then** the Execution Plan tab shows: "Direct execution -- no multi-step plan"
7. **Given** the user views a task card with an execution plan on the Kanban board, **Then** the card shows a small plan indicator icon and progress (e.g., "2/4 steps") via click-to-expand (FR7)
8. **And** the Execution Plan tab content is implemented in `dashboard/components/ExecutionPlanTab.tsx`
9. **And** Vitest tests exist for the ExecutionPlanTab component

## Tasks / Subtasks

- [ ] Task 1: Create the ExecutionPlanTab component (AC: #1, #2, #3, #4, #6, #8)
  - [ ] 1.1: Create `dashboard/components/ExecutionPlanTab.tsx` with `"use client"` directive
  - [ ] 1.2: Accept prop `executionPlan: { steps: Array<{ stepId: string; description: string; assignedAgent?: string; dependsOn: string[]; parallelGroup?: string; status: string }>, createdAt: string } | null`
  - [ ] 1.3: If `executionPlan` is null or empty, render: "Direct execution -- no multi-step plan" in `text-sm text-slate-400`
  - [ ] 1.4: Render steps as a vertical list using `div` elements with `space-y-3` gap
  - [ ] 1.5: Each step shows: step number (1-based, `text-xs text-slate-400 font-mono`), status icon (16px), description (`text-sm`), assigned agent name (`text-xs text-slate-500`)
  - [ ] 1.6: Status icons: pending = gray circle outline (`text-slate-300`), in_progress = blue spinning icon (`text-blue-500 animate-spin`), completed = green checkmark (`text-green-500`), failed = red X (`text-red-500`)
  - [ ] 1.7: For steps with dependencies, show a subtle connecting line on the left (a `border-l-2 border-slate-200` with indentation)
  - [ ] 1.8: For parallel groups, show a "Parallel" badge (`text-xs bg-blue-50 text-blue-600 rounded-full px-2`) above the grouped steps

- [ ] Task 2: Create status icon components (AC: #2)
  - [ ] 2.1: Create `StepStatusIcon` sub-component (or inline) that renders the correct icon based on step status
  - [ ] 2.2: Use Lucide icons (already included with ShadCN): `Circle` (pending), `Loader2` with `animate-spin` (in_progress), `CheckCircle2` (completed), `XCircle` (failed)

- [ ] Task 3: Integrate ExecutionPlanTab into TaskDetailSheet (AC: #1, #5)
  - [ ] 3.1: Update `dashboard/components/TaskDetailSheet.tsx` to import and render `ExecutionPlanTab` in the "Execution Plan" `TabsContent`
  - [ ] 3.2: Pass `task.executionPlan` from the task document to the component
  - [ ] 3.3: The plan updates in real-time because `TaskDetailSheet` already uses `useQuery(api.tasks.getById)` which is reactive

- [ ] Task 4: Add plan indicator to TaskCard (AC: #7)
  - [ ] 4.1: Update `dashboard/components/TaskCard.tsx` to check if `task.executionPlan` exists
  - [ ] 4.2: If plan exists, show a small icon and progress text (e.g., "2/4 steps") in `text-xs text-slate-400`
  - [ ] 4.3: Use the `ListChecks` Lucide icon (or similar) next to the progress text
  - [ ] 4.4: Calculate progress by counting completed steps vs total steps

- [ ] Task 5: Write Vitest tests (AC: #9)
  - [ ] 5.1: Create `dashboard/components/ExecutionPlanTab.test.tsx`
  - [ ] 5.2: Test null plan shows "Direct execution" message
  - [ ] 5.3: Test plan with 3 steps renders all step descriptions
  - [ ] 5.4: Test status icons match step status values
  - [ ] 5.5: Test parallel group label renders for grouped steps
  - [ ] 5.6: Test completed steps show green checkmark

## Dev Notes

### Critical Architecture Requirements

- **Execution plan data comes from the task document**: The `executionPlan` field on the task is a JSON object stored via `v.any()` in the Convex schema (added in Story 4.2). The component reads this directly from the task query result.
- **Real-time updates are automatic**: Since `TaskDetailSheet` uses `useQuery(api.tasks.getById)`, any update to the task's `executionPlan` field triggers a re-render. No additional subscription needed.
- **This is a read-only visualization**: The dashboard does NOT modify execution plans. Plans are created and updated by the Python orchestrator via the bridge.

### ExecutionPlan JSON Shape (from Convex)

The plan is stored in camelCase (Convex convention):

```typescript
interface ExecutionPlanStep {
  stepId: string;
  description: string;
  assignedAgent?: string;
  dependsOn: string[];
  parallelGroup?: string;
  status: "pending" | "in_progress" | "completed" | "failed";
}

interface ExecutionPlan {
  steps: ExecutionPlanStep[];
  createdAt: string;
}
```

### Component Pattern

```tsx
"use client";

import { CheckCircle2, Circle, Loader2, XCircle, ListChecks } from "lucide-react";
import { Badge } from "@/components/ui/badge";

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

function StepStatusIcon({ status }: { status: string }) {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    case "in_progress":
      return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
    case "failed":
      return <XCircle className="h-4 w-4 text-red-500" />;
    default:
      return <Circle className="h-4 w-4 text-slate-300" />;
  }
}

export function ExecutionPlanTab({ executionPlan }: ExecutionPlanTabProps) {
  if (!executionPlan || !executionPlan.steps || executionPlan.steps.length === 0) {
    return (
      <p className="text-sm text-slate-400 text-center py-8">
        Direct execution &mdash; no multi-step plan
      </p>
    );
  }

  const { steps } = executionPlan;
  const completedCount = steps.filter((s) => s.status === "completed").length;

  // Group steps by parallel group for visual grouping
  let currentGroup: string | null = null;

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs text-slate-500">
          {completedCount}/{steps.length} steps completed
        </span>
      </div>

      {steps.map((step, index) => {
        const showGroupLabel =
          step.parallelGroup && step.parallelGroup !== currentGroup;
        if (step.parallelGroup) currentGroup = step.parallelGroup;
        else currentGroup = null;

        return (
          <div key={step.stepId}>
            {showGroupLabel && (
              <Badge variant="secondary" className="text-xs bg-blue-50 text-blue-600 mb-2">
                Parallel
              </Badge>
            )}
            <div className="flex items-start gap-3 py-2">
              <span className="text-xs text-slate-400 font-mono w-5 pt-0.5">
                {index + 1}
              </span>
              <StepStatusIcon status={step.status} />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-slate-800">{step.description}</p>
                {step.assignedAgent && (
                  <p className="text-xs text-slate-500 mt-0.5">
                    {step.assignedAgent}
                  </p>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
```

### TaskCard Plan Indicator Pattern

```tsx
// Inside TaskCard, after the tags section:
{task.executionPlan && task.executionPlan.steps && (
  <div className="flex items-center gap-1 mt-1.5">
    <ListChecks className="h-3 w-3 text-slate-400" />
    <span className="text-xs text-slate-400">
      {task.executionPlan.steps.filter((s: any) => s.status === "completed").length}
      /{task.executionPlan.steps.length} steps
    </span>
  </div>
)}
```

### Common LLM Developer Mistakes to Avoid

1. **DO NOT create a separate Convex query for execution plans** — The plan is part of the task document. `useQuery(api.tasks.getById)` already returns it.

2. **DO NOT add interactive editing to the plan** — This is a read-only visualization. The dashboard does not modify plans.

3. **DO NOT use complex SVG or canvas for plan rendering** — A simple vertical list with status icons and indentation is sufficient for MVP. Fancy flow diagrams are post-MVP.

4. **DO NOT forget the `"use client"` directive** — The component uses hooks and must be a client component.

5. **DO NOT assume executionPlan will always have the expected shape** — Use optional chaining and null checks since `v.any()` provides no schema guarantees.

6. **DO NOT import Framer Motion for plan animations** — Simple CSS transitions for status icon changes are sufficient. The `animate-spin` class handles the spinner.

### What This Story Does NOT Include

- **Interactive plan editing** — Users cannot modify execution plans from the dashboard
- **Drag-and-drop reordering** — Steps cannot be reordered visually
- **Complex flow diagram rendering** — No SVG-based dependency graphs for MVP
- **Plan creation UI** — Plans are created by the Python orchestrator, not the dashboard

### Files Created in This Story

| File | Purpose |
|------|---------|
| `dashboard/components/ExecutionPlanTab.tsx` | Execution plan step list with status icons |
| `dashboard/components/ExecutionPlanTab.test.tsx` | Vitest tests for plan visualization |

### Files Modified in This Story

| File | Changes |
|------|---------|
| `dashboard/components/TaskDetailSheet.tsx` | Replace placeholder with `ExecutionPlanTab` in the Execution Plan tab |
| `dashboard/components/TaskCard.tsx` | Add plan indicator (icon + step progress) when executionPlan exists |

### Verification Steps

1. Open TaskDetailSheet for a task with an execution plan — verify steps render with correct status icons
2. Open TaskDetailSheet for a task without a plan — verify "Direct execution" message
3. Verify real-time update: change a step status in Convex — icon updates without page refresh
4. Verify parallel group label appears for grouped steps
5. Verify TaskCard shows plan progress indicator (e.g., "2/4 steps")
6. Run `cd dashboard && npx vitest run` — tests pass

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 4.3`] — Original story definition
- [Source: `_bmad-output/planning-artifacts/prd.md#FR7`] — View execution plan via click-to-expand
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#Component Strategy`] — TaskDetailSheet Execution Plan tab spec
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#User Journey Flows`] — Journey 2 execution plan details
- [Source: `dashboard/components/TaskDetailSheet.tsx`] — Existing sheet with placeholder for plan tab
- [Source: `dashboard/components/TaskCard.tsx`] — Existing card to add plan indicator

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
- TypeScript compilation: clean (0 errors)
- Vitest: 12/12 tests passing

### Completion Notes List
- Created ExecutionPlanTab component with StepStatusIcon sub-component
- Integrated into TaskDetailSheet's "Execution Plan" tab replacing placeholder
- Added plan progress indicator (ListChecks icon + "X/Y steps") to TaskCard
- Used `(task as any).executionPlan` for accessing v.any() field not in typed schema
- Dependency visualization via left border indentation on steps with dependsOn
- Parallel group label rendered as Badge when parallelGroup changes

### File List
- `dashboard/components/ExecutionPlanTab.tsx` (created) - Execution plan step list with status icons
- `dashboard/components/ExecutionPlanTab.test.tsx` (created) - 12 Vitest tests
- `dashboard/components/TaskDetailSheet.tsx` (modified) - Import + render ExecutionPlanTab in plan tab
- `dashboard/components/TaskCard.tsx` (modified) - Plan progress indicator with ListChecks icon
