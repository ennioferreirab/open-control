# Story 1.7: Render Step Cards on Kanban Board

Status: done

## Dependencies

**BLOCKER: Story 1.1 (Extend Convex Schema for Task/Step Hierarchy) MUST be completed first.** Story 1.1 creates the `steps` table in Convex with the `by_taskId` index, step status values, and the `steps.ts` Convex function file with `getByTask` query. This story assumes the `steps` table and its query functions exist. If Story 1.1 has not been completed, stop and complete it first.

**BLOCKER: Story 1.6 (Materialize Plans into Step Records) SHOULD be completed first** for end-to-end testing. Story 1.6 implements the plan materializer that creates step records in Convex from ExecutionPlan objects. Without materialized steps, there is no data to render. However, this story can be developed and tested with manually inserted step records via Convex dashboard if Story 1.6 is not yet ready.

**Depends on from Story 1.1:**
- `steps` table in `dashboard/convex/schema.ts` with fields: `taskId`, `title`, `description`, `assignedAgent`, `status`, `blockedBy`, `parallelGroup`, `order`, `createdAt`, `startedAt`, `completedAt`, `errorMessage`
- `dashboard/convex/steps.ts` with at least `getByTask` query (returns all steps for a given taskId)
- `by_taskId` index on `steps` table

## Story

As a **user**,
I want to see steps as individual cards on the Kanban board grouped by parent task,
So that I can track the progress of each unit of work across my agents.

## Acceptance Criteria

1. **Steps render as cards in correct columns** -- Given a task has been kicked off and step records exist in Convex, when the Kanban board renders, then each step appears as an individual `StepCard` in the column matching its status (`assigned` -> "Assigned", `running` -> "In Progress", `completed` -> "Done"). Steps belonging to the same task are visually grouped with a `TaskGroupHeader` showing the parent task title.

2. **StepCard displays required information** -- Given a StepCard renders on the board, when the card is displayed, then it shows: step title, assigned agent name/avatar, status badge (color + text label per UX spec), and parent task name as a subtle label. The card follows the ShadCN Card component pattern with Tailwind styling consistent with the existing design system.

3. **Real-time status transitions with animation** -- Given a step's status changes in Convex (e.g., "assigned" -> "running"), when the Convex reactive query fires, then the StepCard moves to the new column with a smooth Motion transition (`layoutId`). The status badge updates in real-time within 1 second (NFR3).

4. **Multiple task groups in columns** -- Given multiple tasks have been kicked off, when the Kanban board renders, then steps from different tasks are separated by their respective TaskGroupHeaders within each column.

5. **Tasks without steps render as regular TaskCards** -- Given a task with no steps (still in "planning" status or old-style task), when the Kanban board renders, then the task appears as a regular task card (not step cards) until steps are materialized.

## Tasks / Subtasks

- [x] **Task 1: Add step status color constants to `lib/constants.ts`** (AC: 2)
  - [x] 1.1 Add `STEP_STATUS_COLORS` mapping for step-specific status values (`planned`, `assigned`, `running`, `completed`, `crashed`, `blocked`)
  - [x] 1.2 Add `StepStatus` TypeScript type

- [x] **Task 2: Create `StepCard.tsx` component** (AC: 2, 3)
  - [x] 2.1 Create `dashboard/components/StepCard.tsx` with props: step document, parent task title, onClick handler
  - [x] 2.2 Implement card layout: title, agent avatar/initials, status badge, parent task label
  - [x] 2.3 Wrap in `motion.div` with `layoutId={step._id}` for animated column transitions
  - [x] 2.4 Add `useReducedMotion` hook to respect `prefers-reduced-motion`
  - [x] 2.5 Add blocked indicator (lock icon + "Blocked" badge) for steps with `status === "blocked"`
  - [x] 2.6 Add crashed indicator (red badge) for steps with `status === "crashed"`

- [x] **Task 3: Create `TaskGroupHeader.tsx` component** (AC: 1, 4)
  - [x] 3.1 Create `dashboard/components/TaskGroupHeader.tsx` with props: task title, step count, onClick handler
  - [x] 3.2 Implement subtle header with task title, step count badge, and optional click to open task detail

- [x] **Task 4: Create `steps.listAll` Convex query (or use existing)** (AC: 1, 3)
  - [x] 4.1 If Story 1.1 only created `getByTask` (per-task query), add a `listAll` query to `dashboard/convex/steps.ts` that returns all non-deleted steps
  - [x] 4.2 Alternatively, add `listByBoard` query that joins steps to tasks filtered by board

- [x] **Task 5: Modify `KanbanBoard.tsx` to query and render steps** (AC: 1, 3, 4, 5)
  - [x] 5.1 Add `useQuery(api.steps.listAll)` (or equivalent) to fetch all steps alongside tasks
  - [x] 5.2 Identify which tasks have materialized steps (steps exist for that taskId)
  - [x] 5.3 For tasks WITH steps: exclude the parent task from the tasks list (it should not render as a TaskCard)
  - [x] 5.4 For tasks WITHOUT steps: keep them in the tasks list as regular TaskCards (backward compatible)
  - [x] 5.5 Build combined column data: regular TaskCards + step-grouped StepCards per column
  - [x] 5.6 Pass step and task data down to KanbanColumn

- [x] **Task 6: Modify `KanbanColumn.tsx` to render mixed content** (AC: 1, 4, 5)
  - [x] 6.1 Update KanbanColumn props to accept both tasks and step groups
  - [x] 6.2 Render TaskGroupHeader + StepCards for step groups
  - [x] 6.3 Render regular TaskCards for tasks without steps
  - [x] 6.4 Update column item count badge to include steps

- [x] **Task 7: Add step click handler** (AC: 2)
  - [x] 7.1 Wire StepCard click to open the parent task's TaskDetailSheet (reuse existing `onTaskClick`)

- [x] **Task 8: Write tests** (AC: 1, 2, 3, 4, 5)
  - [x] 8.1 StepCard.test.tsx: renders title, agent, status badge, parent task label
  - [x] 8.2 StepCard.test.tsx: renders blocked indicator when status is "blocked"
  - [x] 8.3 StepCard.test.tsx: renders crashed indicator when status is "crashed"
  - [x] 8.4 TaskGroupHeader.test.tsx: renders task title and step count
  - [x] 8.5 KanbanBoard integration: tasks with steps show StepCards, tasks without steps show TaskCards

## Dev Notes

### Step Status to Kanban Column Mapping

The step status values from the architecture do NOT map 1:1 to the existing Kanban column statuses. Here is the exact mapping:

| Step Status | Kanban Column | Column Status Value | Rationale |
|---|---|---|---|
| `planned` | _(not shown)_ | N/A | Pre-materialization state; steps in "planned" are still in the ExecutionPlan, not yet materialized |
| `assigned` | **Assigned** | `assigned` | Step created, waiting for dispatch. Maps to "Assigned" column. |
| `blocked` | **Assigned** | `assigned` | Blocked steps are waiting — they live in the Assigned column with a visual "blocked" indicator (lock icon). They cannot move to In Progress until unblocked. |
| `running` | **In Progress** | `in_progress` | Agent is actively executing the step. |
| `completed` | **Done** | `done` | Step finished successfully. |
| `crashed` | **In Progress** | `in_progress` | Crashed steps stay in the In Progress column (like crashed tasks do today) with a red "Crashed" badge. This is consistent with existing TaskCard behavior where `crashed` and `retrying` tasks appear in the In Progress column. |

**IMPORTANT:** Steps do NOT appear in "Inbox" or "Review" columns. Those columns are for tasks only (task-level workflow). Steps live in Assigned, In Progress, and Done only.

### Step Status Color Scheme

Add these to `dashboard/lib/constants.ts`:

```typescript
// Step status values
export const STEP_STATUS = {
  PLANNED: "planned",
  ASSIGNED: "assigned",
  RUNNING: "running",
  COMPLETED: "completed",
  CRASHED: "crashed",
  BLOCKED: "blocked",
} as const;

export type StepStatus = (typeof STEP_STATUS)[keyof typeof STEP_STATUS];

// Step status color mapping (follows same pattern as STATUS_COLORS)
export const STEP_STATUS_COLORS: Record<
  StepStatus,
  { border: string; bg: string; text: string }
> = {
  planned: {
    border: "border-l-slate-400",
    bg: "bg-slate-100 dark:bg-slate-900",
    text: "text-slate-600 dark:text-slate-400",
  },
  assigned: {
    border: "border-l-cyan-500",
    bg: "bg-cyan-100 dark:bg-cyan-950",
    text: "text-cyan-700 dark:text-cyan-300",
  },
  running: {
    border: "border-l-blue-500",
    bg: "bg-blue-100 dark:bg-blue-950",
    text: "text-blue-700 dark:text-blue-300",
  },
  completed: {
    border: "border-l-green-500",
    bg: "bg-green-100 dark:bg-green-950",
    text: "text-green-700 dark:text-green-300",
  },
  crashed: {
    border: "border-l-red-500",
    bg: "bg-red-100 dark:bg-red-950",
    text: "text-red-700 dark:text-red-300",
  },
  blocked: {
    border: "border-l-amber-500",
    bg: "bg-amber-100 dark:bg-amber-950",
    text: "text-amber-700 dark:text-amber-300",
  },
};
```

These colors align with the UX spec's status palette:
- **Assigned** (cyan-500) -- matches the existing "Assigned" column accent
- **Running** (blue-500) -- matches the existing "In Progress" active indicator
- **Completed** (green-500) -- matches the existing "Done" column accent
- **Crashed** (red-500) -- matches the existing error indicator
- **Blocked** (amber-500) -- amber signals "attention needed" per UX spec
- **Planned** (slate-400) -- muted; this status is rarely visible on the board

### New Component: `StepCard.tsx`

**Location:** `dashboard/components/StepCard.tsx`

**Props interface:**
```typescript
interface StepCardProps {
  step: Doc<"steps">;
  parentTaskTitle: string;
  onClick?: () => void;
}
```

**Implementation pattern -- follow existing TaskCard.tsx closely:**

```typescript
"use client";

import * as motion from "motion/react-client";
import { useReducedMotion } from "motion/react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, Lock } from "lucide-react";
import { Doc } from "../convex/_generated/dataModel";
import { STEP_STATUS_COLORS, type StepStatus } from "@/lib/constants";

interface StepCardProps {
  step: Doc<"steps">;
  parentTaskTitle: string;
  onClick?: () => void;
}

export function StepCard({ step, parentTaskTitle, onClick }: StepCardProps) {
  const shouldReduceMotion = useReducedMotion();
  const colors = STEP_STATUS_COLORS[step.status as StepStatus] ?? STEP_STATUS_COLORS.assigned;

  const assignedAgentInitials = step.assignedAgent
    ? step.assignedAgent
        .split(/[\s-_]+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((word) => word[0]?.toUpperCase() ?? "")
        .join("")
    : "?";

  return (
    <motion.div
      layoutId={step._id}
      layout
      transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.3 }}
    >
      <Card
        className={[
          "cursor-pointer rounded-[10px] border-l-[3px] p-3 transition-shadow hover:shadow-md",
          colors.border,
        ].join(" ")}
        onClick={onClick}
        role="article"
        aria-label={`Step: ${step.title} - ${step.status} - assigned to ${step.assignedAgent}`}
      >
        {/* Parent task label */}
        <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground/70 truncate">
          {parentTaskTitle}
        </p>

        {/* Step title */}
        <div className="mb-1.5 flex items-start justify-between gap-2">
          <h3 className="min-w-0 text-sm font-semibold text-foreground line-clamp-2">
            {step.title}
          </h3>
          <div className="mt-0.5 flex shrink-0 items-center gap-1">
            {step.status === "blocked" && (
              <Lock className="h-3.5 w-3.5 text-amber-500" />
            )}
            {step.status === "crashed" && (
              <AlertTriangle className="h-3.5 w-3.5 text-red-500" />
            )}
          </div>
        </div>

        {/* Description preview (optional) */}
        {step.description && (
          <p className="mb-2 text-xs text-muted-foreground line-clamp-2">
            {step.description}
          </p>
        )}

        {/* Footer: agent + status badge */}
        <div className="mt-2 flex items-center gap-2">
          <span className="inline-flex min-w-0 items-center gap-1 text-xs text-muted-foreground">
            <span className="flex h-4 w-4 items-center justify-center rounded-[5px] bg-muted text-[9px] font-semibold text-foreground">
              {assignedAgentInitials}
            </span>
            <span className="truncate">{step.assignedAgent ?? "Unassigned"}</span>
          </span>
          <Badge
            variant="secondary"
            className={`h-5 rounded-full px-2 text-[10px] font-medium ${colors.bg} ${colors.text}`}
          >
            {step.status}
          </Badge>
          {step.status === "crashed" && (
            <Badge className="h-5 rounded-full bg-red-500 px-2 text-[10px] text-white">
              Crashed
            </Badge>
          )}
          {step.status === "blocked" && (
            <Badge
              variant="outline"
              className="h-5 rounded-full border-amber-300 bg-amber-50 px-2 text-[10px] font-medium text-amber-600"
            >
              <Lock className="mr-1 h-3 w-3" />
              Blocked
            </Badge>
          )}
        </div>
      </Card>
    </motion.div>
  );
}
```

**Key design decisions matching TaskCard:**
- Same `rounded-[10px]`, `border-l-[3px]`, `p-3` / `p-3.5` card styling
- Same `text-sm font-semibold` title, `text-xs` metadata
- Same agent initials pattern (split on `\s-_`, take first 2 chars)
- Same `motion.div` wrapper with `layoutId` and `layout` props
- Same `useReducedMotion` pattern for accessibility
- **Smaller padding** (`p-3` vs `p-3.5`) to visually differentiate step cards from task cards -- steps are lightweight work units, not full tasks
- **Parent task label** at top in `text-[10px] uppercase tracking-wide` -- subtle but always visible
- **No HITL buttons** -- steps do not have approve/deny workflow (that is at the task level)
- **No tags row** -- steps do not have tags (tags are at the task level)
- **No progress bar** -- steps are atomic units; progress is shown at the task level
- **No trash/delete button** -- steps cannot be individually deleted from the board

### New Component: `TaskGroupHeader.tsx`

**Location:** `dashboard/components/TaskGroupHeader.tsx`

```typescript
"use client";

import { Badge } from "@/components/ui/badge";
import { Id } from "../convex/_generated/dataModel";

interface TaskGroupHeaderProps {
  taskTitle: string;
  taskId: Id<"tasks">;
  stepCount: number;
  onClick?: () => void;
}

export function TaskGroupHeader({
  taskTitle,
  taskId,
  stepCount,
  onClick,
}: TaskGroupHeaderProps) {
  return (
    <div
      className="flex items-center gap-2 rounded-md bg-muted/60 px-2.5 py-1.5 cursor-pointer hover:bg-muted/80 transition-colors"
      onClick={onClick}
      role="heading"
      aria-level={3}
      aria-label={`Task: ${taskTitle} (${stepCount} steps)`}
    >
      <h3 className="min-w-0 flex-1 truncate text-xs font-semibold text-muted-foreground">
        {taskTitle}
      </h3>
      <Badge variant="secondary" className="h-4 px-1.5 text-[9px]">
        {stepCount}
      </Badge>
    </div>
  );
}
```

**Design rationale:**
- Subtle header -- `bg-muted/60` background, `text-xs`, `text-muted-foreground`. Does not compete with StepCards for visual attention.
- Clickable -- opens the parent task's TaskDetailSheet.
- Step count badge -- quick glance at how many steps are in this group within this column.

### Convex Query: Fetching All Steps for the Board

Story 1.1 creates `steps.getByTask` (per-task query). For the Kanban board, we need ALL steps across ALL tasks. Add this to `dashboard/convex/steps.ts`:

```typescript
export const listAll = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db.query("steps").collect();
  },
});
```

**Board-scoped variant** (if board filtering is needed, to match the existing task board scoping):

```typescript
export const listByTaskIds = query({
  args: { taskIds: v.array(v.id("tasks")) },
  handler: async (ctx, args) => {
    const taskIdSet = new Set(args.taskIds);
    const allSteps = await ctx.db.query("steps").collect();
    return allSteps.filter((s) => taskIdSet.has(s.taskId));
  },
});
```

**Recommended approach:** Use `listAll` for simplicity. The board-scoped filtering can be done client-side by matching `step.taskId` to the already-fetched tasks. This avoids an additional query and keeps the reactive update path simple. Convex reactive queries automatically re-fire when any step changes.

### KanbanBoard.tsx Modifications

This is the most complex change. The board must now render a mix of regular TaskCards (for tasks without steps) and StepCard groups (for tasks with steps).

**Changes to `dashboard/components/KanbanBoard.tsx`:**

```typescript
// === NEW IMPORTS ===
import { StepCard } from "./StepCard";
import { TaskGroupHeader } from "./TaskGroupHeader";
import { Doc } from "../convex/_generated/dataModel";

// === INSIDE KanbanBoard FUNCTION ===

// 1. Fetch all steps
const allSteps = useQuery(api.steps.listAll) ?? [];

// 2. Group steps by taskId
const stepsByTaskId = new Map<string, Doc<"steps">[]>();
for (const step of allSteps) {
  const key = step.taskId;
  if (!stepsByTaskId.has(key)) {
    stepsByTaskId.set(key, []);
  }
  stepsByTaskId.get(key)!.push(step);
}

// 3. Identify tasks that have materialized steps
const tasksWithSteps = new Set(stepsByTaskId.keys());

// 4. Build task title lookup (for TaskGroupHeader and StepCard parent label)
const taskTitleMap = new Map<string, string>();
for (const task of tasks) {
  taskTitleMap.set(task._id, task.title);
}

// 5. Filter: tasks WITHOUT steps stay as regular TaskCards
const regularTasks = tasks.filter((t) => !tasksWithSteps.has(t._id));
```

**Column data structure update:**

The current `tasksByStatus` builds column data from tasks only. The new version must build a unified structure:

```typescript
// Type for column items
type ColumnItem =
  | { type: "task"; task: Doc<"tasks"> }
  | { type: "step-group"; taskId: string; taskTitle: string; steps: Doc<"steps">[] };

// Step status -> column mapping function
function stepStatusToColumnStatus(stepStatus: string): string | null {
  switch (stepStatus) {
    case "assigned":
    case "blocked":
      return "assigned";
    case "running":
    case "crashed":
      return "in_progress";
    case "completed":
      return "done";
    default:
      return null; // "planned" steps are not shown
  }
}

// Build column data
const tasksByStatus = COLUMNS.map((col) => {
  // Regular tasks for this column (existing logic)
  const columnTasks = regularTasks
    .filter((t) => {
      if (col.status === "in_progress") {
        return t.status === "in_progress" || t.status === "retrying" || t.status === "crashed";
      }
      return t.status === col.status;
    })
    .sort((a, b) => b._creationTime - a._creationTime);

  // Step groups for this column
  const columnStepGroups: { taskId: string; taskTitle: string; steps: Doc<"steps">[] }[] = [];

  for (const [taskId, taskSteps] of stepsByTaskId.entries()) {
    const stepsInColumn = taskSteps.filter(
      (s) => stepStatusToColumnStatus(s.status) === col.status
    );
    if (stepsInColumn.length > 0) {
      columnStepGroups.push({
        taskId,
        taskTitle: taskTitleMap.get(taskId) ?? "Unknown Task",
        steps: stepsInColumn.sort((a, b) => a.order - b.order),
      });
    }
  }

  return {
    ...col,
    tasks: columnTasks,
    stepGroups: columnStepGroups,
    totalCount: columnTasks.length + columnStepGroups.reduce((sum, g) => sum + g.steps.length, 0),
  };
});
```

### KanbanColumn.tsx Modifications

**Updated props interface:**

```typescript
interface KanbanColumnProps {
  title: string;
  status: string;
  tasks: Doc<"tasks">[];
  stepGroups: {
    taskId: string;
    taskTitle: string;
    steps: Doc<"steps">[];
  }[];
  totalCount: number;
  accentColor: string;
  onTaskClick?: (taskId: Id<"tasks">) => void;
  hitlCount?: number;
  onClear?: () => void;
  clearDisabled?: boolean;
  onViewAll?: () => void;
  tagColorMap?: Record<string, string>;
}
```

**Updated render logic (inside the scrollable area):**

```tsx
<div className="flex flex-col gap-2">
  {/* Step groups first (active work is more important) */}
  {stepGroups.map((group) => (
    <div key={group.taskId} className="flex flex-col gap-1.5">
      <TaskGroupHeader
        taskTitle={group.taskTitle}
        taskId={group.taskId as Id<"tasks">}
        stepCount={group.steps.length}
        onClick={onTaskClick ? () => onTaskClick(group.taskId as Id<"tasks">) : undefined}
      />
      {group.steps.map((step) => (
        <StepCard
          key={step._id}
          step={step}
          parentTaskTitle={group.taskTitle}
          onClick={onTaskClick ? () => onTaskClick(step.taskId) : undefined}
        />
      ))}
    </div>
  ))}

  {/* Regular task cards (tasks without steps) */}
  {tasks.map((task) => (
    <TaskCard
      key={task._id}
      task={task}
      onClick={onTaskClick ? () => onTaskClick(task._id) : undefined}
      tagColorMap={tagColorMap}
    />
  ))}
</div>
```

**Column badge count:** Replace `tasks.length` with `totalCount` in the header Badge.

### Motion / Animation Patterns

The existing codebase uses `motion/react` (not `framer-motion` -- the package is `motion` v12.34.3):

```typescript
// Client-side motion components (for DOM elements rendered by client components):
import * as motion from "motion/react-client";

// Layout animation hooks:
import { useReducedMotion, LayoutGroup } from "motion/react";
```

**Critical pattern from existing code:**
- `KanbanBoard.tsx` wraps everything in `<LayoutGroup>` (line 81)
- `TaskCard.tsx` uses `motion.div` with `layoutId={task._id}` (line 62)
- `StepCard` MUST follow the same pattern: `layoutId={step._id}` inside the existing `<LayoutGroup>`
- The `layoutId` must be globally unique. Since step IDs are Convex document IDs (different table from tasks), there is no collision risk.

**Reduced motion support:**
```typescript
const shouldReduceMotion = useReducedMotion();
// ...
transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.3 }}
```

This is the exact pattern used in `TaskCard.tsx` at line 64. Copy it verbatim.

### Backward Compatibility: Tasks Without Steps

**The critical invariant:** Existing tasks (created before the step system exists, or tasks still in `inbox`/`assigned`/`in_progress` without any step records) MUST continue to render as regular `TaskCard` components exactly as they do today.

The logic is simple:
1. Fetch all steps via `useQuery(api.steps.listAll)`
2. Group steps by `taskId`
3. For each task: if `stepsByTaskId.has(task._id)`, the task has steps -> render as StepCard group
4. Otherwise -> render as regular TaskCard

**Edge case: task status vs step statuses.** When a task has steps, the task itself has its own status (e.g., `in_progress` or `running`). The task-level status is NOT used for column placement -- only the individual step statuses determine which column each step appears in. The parent task itself is hidden from the board (replaced by its steps).

**Edge case: task with steps where ALL steps are "planned".** If all steps are in "planned" status (pre-materialization snapshot), none will appear on the board. This is correct -- planned steps are in the ExecutionPlan preview, not yet actionable. The task itself will still appear as a regular TaskCard until steps are materialized to "assigned"/"blocked" status.

### Exact Files to Modify

| File | What Changes | Lines of Interest |
|---|---|---|
| `dashboard/lib/constants.ts` | ADD `STEP_STATUS`, `StepStatus` type, `STEP_STATUS_COLORS` | After line 131 (after existing `STATUS_COLORS`) |
| `dashboard/components/StepCard.tsx` | **NEW FILE** -- Step card component for Kanban | N/A (new) |
| `dashboard/components/TaskGroupHeader.tsx` | **NEW FILE** -- Task group header for step grouping | N/A (new) |
| `dashboard/convex/steps.ts` | ADD `listAll` query (if not already present from Story 1.1) | Append to file |
| `dashboard/components/KanbanBoard.tsx` | MODIFY -- add step query, compute step groups, pass to columns | Lines 30-37 (queries), 62-76 (column building) |
| `dashboard/components/KanbanColumn.tsx` | MODIFY -- accept stepGroups prop, render mixed content | Lines 13-24 (props), 143-158 (render area) |

### What NOT to Change

- **`dashboard/convex/schema.ts`** -- Do NOT modify. Schema changes are Story 1.1.
- **`dashboard/components/TaskCard.tsx`** -- Do NOT modify. TaskCard continues to work for tasks without steps. No changes needed.
- **`dashboard/components/TaskDetailSheet.tsx`** -- Do NOT modify. Step list in task detail is a future story. Clicking a StepCard opens the parent task's existing TaskDetailSheet.
- **`dashboard/convex/tasks.ts`** -- Do NOT modify. Task queries remain unchanged.

### ShadCN Components Used

| Component | Usage | Already Installed? |
|---|---|---|
| `Card` | StepCard outer container | Yes (`dashboard/components/ui/card.tsx`) |
| `Badge` | Status badge, step count in TaskGroupHeader | Yes (`dashboard/components/ui/badge.tsx`) |
| `Avatar` | Not used directly -- agent initials use a styled `<span>` (same as TaskCard pattern) | N/A |

No new ShadCN components need to be installed.

### Lucide Icons Used

| Icon | Usage | Already Imported Elsewhere? |
|---|---|---|
| `Lock` | Blocked step indicator | No -- import from `lucide-react` |
| `AlertTriangle` | Crashed step indicator | Yes (TaskCard.tsx) |

### Convex Reactive Query Pattern

The existing board uses this pattern for tasks:
```typescript
const allTasksResult = useQuery(api.tasks.list);
```

Steps follow the exact same pattern:
```typescript
const allSteps = useQuery(api.steps.listAll) ?? [];
```

Convex reactive queries automatically re-fire whenever any document in the queried table changes. When a step status changes (e.g., `assigned` -> `running`), the query re-fires, the component re-renders, and the StepCard moves to the new column via Motion `layoutId` animation. No manual subscription management needed.

**Performance consideration:** `listAll` fetches ALL steps. For MVP with a small number of tasks/steps (single user, localhost), this is fine. If performance becomes an issue later, switch to `listByTaskIds` with the visible task IDs.

### Board-Scoped Steps

The existing KanbanBoard supports board-scoped task queries:
```typescript
const boardTasksResult = useQuery(
  api.tasks.listByBoard,
  activeBoardId ? { boardId: activeBoardId, includeNoBoardId: isDefaultBoard } : "skip"
);
const tasks = activeBoardId ? boardTasksResult : allTasksResult;
```

For steps, filter client-side using the already-fetched tasks:
```typescript
const allSteps = useQuery(api.steps.listAll) ?? [];

// Only include steps whose parent task is in the current board's task list
const visibleTaskIds = new Set((tasks ?? []).map((t) => t._id));
const boardSteps = allSteps.filter((s) => visibleTaskIds.has(s.taskId));
```

This avoids creating a board-scoped Convex query for steps and leverages the already-filtered task list.

### Testing Strategy

**StepCard.test.tsx:**
```typescript
// Test patterns (follow existing TaskCard.test.tsx conventions):
// 1. Renders step title
// 2. Renders assigned agent initials
// 3. Renders status badge with correct color
// 4. Renders parent task label
// 5. Renders blocked indicator when status is "blocked"
// 6. Renders crashed indicator when status is "crashed"
// 7. Calls onClick when card is clicked
// 8. Has correct aria-label
```

**TaskGroupHeader.test.tsx:**
```typescript
// 1. Renders task title
// 2. Renders step count badge
// 3. Calls onClick when header is clicked
// 4. Has correct aria attributes
```

**KanbanBoard integration (if feasible with existing test setup):**
```typescript
// 1. Tasks without steps render as TaskCards
// 2. Tasks with steps render as StepCard groups with TaskGroupHeader
// 3. Parent task of step group is NOT shown as a TaskCard
```

**Test runner:** vitest (run from `dashboard/` directory: `npx vitest`)

**Mocking Convex queries in tests:**
The existing tests mock `useQuery` and `useMutation`. For StepCard tests, mock the step document as a plain object:
```typescript
const mockStep = {
  _id: "step1" as Id<"steps">,
  _creationTime: Date.now(),
  taskId: "task1" as Id<"tasks">,
  title: "Analyze financial data",
  description: "Review Q4 reports",
  assignedAgent: "financial-agent",
  status: "running",
  blockedBy: [],
  parallelGroup: 1,
  order: 1,
  createdAt: new Date().toISOString(),
};
```

### Visual Hierarchy in Columns

When a column has both step groups and regular tasks, the rendering order should be:

1. **Step groups first** (grouped by parent task, each with a TaskGroupHeader)
2. **Regular TaskCards after** (tasks without steps)

This puts active orchestrated work at the top of each column, with standalone tasks below. Within step groups, steps are sorted by their `order` field (plan order). Regular tasks are sorted by `_creationTime` descending (newest first), matching existing behavior.

### Edge Cases

1. **Empty steps query:** If `useQuery(api.steps.listAll)` returns `undefined` (loading) or `[]` (no steps), the board renders exactly as it does today -- all tasks as TaskCards. Zero-step state is the current default.

2. **Step with unknown taskId:** If a step's `taskId` references a task not in the current board/view, the step is filtered out by the `visibleTaskIds` check. No orphan steps rendered.

3. **All steps completed:** When all steps for a task are "completed", they all appear in the Done column under their TaskGroupHeader. The Done column's "Clear All" button clears tasks -- it does NOT affect steps. Step cleanup is a separate concern.

4. **Step changes status during render:** Convex handles this via reactive queries. The next render cycle picks up the change. Motion `layoutId` handles the animation automatically.

5. **Concurrent steps from multiple tasks in same column:** Multiple TaskGroupHeaders appear in the column, each followed by their respective StepCards. Groups are separated by the header's background styling (`bg-muted/60`).

### References

- [Source: dashboard/components/KanbanBoard.tsx] -- Existing Kanban board with task queries and column building (lines 1-116)
- [Source: dashboard/components/KanbanColumn.tsx] -- Existing column with TaskCard rendering (lines 1-161)
- [Source: dashboard/components/TaskCard.tsx] -- Existing task card with Motion animation, status colors, agent initials (lines 1-273)
- [Source: dashboard/lib/constants.ts] -- STATUS_COLORS, TaskStatus type, existing color scheme (lines 87-146)
- [Source: dashboard/convex/schema.ts] -- Tasks table (lines 18-59), steps table added by Story 1.1
- [Source: dashboard/convex/tasks.ts] -- Task queries: list, listByBoard, getById (lines 163-200)
- [Source: dashboard/components/ui/card.tsx] -- ShadCN Card primitive
- [Source: dashboard/components/ui/badge.tsx] -- ShadCN Badge primitive
- [Source: _bmad-output/planning-artifacts/architecture.md#Step Rendering on Kanban] -- "Steps are flat cards in Kanban columns. Task grouping header separates steps by parent task within each column. Step cards show: step title, assigned agent avatar, status badge, blocked indicator, file indicator, parent task label"
- [Source: _bmad-output/planning-artifacts/architecture.md#Data Architecture] -- Steps table: taskId, title, description, assignedAgent, status, blockedBy, parallelGroup, order
- [Source: _bmad-output/planning-artifacts/architecture.md#Step Status Values] -- "planned" | "assigned" | "running" | "completed" | "crashed" | "blocked"
- [Source: _bmad-output/planning-artifacts/architecture.md#Frontend Architecture] -- Motion layoutId for GPU-accelerated card transitions, prefers-reduced-motion respect
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#TaskCard] -- Card-Rich styling: p-3.5, rounded-[10px], border-left 3px, status-color accents, text-sm font-semibold title, text-xs metadata
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Status Palette] -- Blue (active), green (done), amber (review/attention), red (error), slate (idle), violet (inbox)
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Animation Patterns] -- Card movement: smooth Framer Motion transition (300ms), layoutId, prefers-reduced-motion check
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Accessibility] -- role="article", aria-label, status not color-only (always color + text label)
- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.7] -- Full BDD acceptance criteria
- [Source: _bmad-output/implementation-artifacts/1-1-extend-convex-schema-for-task-step-hierarchy.md] -- Dependency: steps table, steps.ts queries

## Dev Agent Record

### Agent Model Used

GPT-5 Codex (Codex CLI)

### Debug Log References

- `npm test -- components/StepCard.test.tsx components/TaskGroupHeader.test.tsx components/KanbanBoard.test.tsx` (initial RED run): failed as expected before implementation (`StepCard`/`TaskGroupHeader` missing, Kanban mixed rendering test failing).
- `npm test -- components/StepCard.test.tsx components/TaskGroupHeader.test.tsx components/KanbanBoard.test.tsx` (post-implementation): pass (15 tests).
- `npm test`: pass (23 files, 259 tests).
- `npm run lint`: fails due existing unrelated lint baseline issues in multiple files outside Story 1.7 scope.
- `npx eslint components/KanbanBoard.tsx components/KanbanColumn.tsx components/StepCard.tsx components/TaskGroupHeader.tsx components/KanbanBoard.test.tsx components/StepCard.test.tsx components/TaskGroupHeader.test.tsx convex/steps.ts lib/constants.ts`: pass.
- `npm test -- components/StepCard.test.tsx components/TaskGroupHeader.test.tsx components/KanbanBoard.test.tsx convex/steps.test.ts`: pass (33 tests) after senior review fixes.
- `npx eslint components/StepCard.tsx components/TaskGroupHeader.tsx components/KanbanBoard.tsx convex/steps.ts components/StepCard.test.tsx components/TaskGroupHeader.test.tsx components/KanbanBoard.test.tsx`: pass.

### Completion Notes List

- Implemented `STEP_STATUS`, `StepStatus`, and `STEP_STATUS_COLORS` in `dashboard/lib/constants.ts` to provide step-specific status typing and styling.
- Added `StepCard` component with required content (title, parent task label, assigned agent initials/name, status badge), blocked/crashed indicators, and Motion `layoutId` transition with reduced-motion support.
- Added `TaskGroupHeader` component with task title, step count badge, and click-through support for opening the parent task detail.
- Added Convex `steps.listAll` query to support real-time board-wide step rendering.
- Updated `KanbanBoard` to fetch steps, map step statuses to Kanban columns, group steps by parent task per column, hide parent TaskCards when renderable steps exist, keep tasks without steps as regular TaskCards, and compute mixed item counts.
- Updated `KanbanColumn` to render mixed content (step groups first, regular TaskCards after) and use total item count badge (tasks + steps).
- Added coverage for new behaviors:
  - `StepCard.test.tsx`
  - `TaskGroupHeader.test.tsx`
  - `KanbanBoard.test.tsx` integration scenario for task/step mixed rendering.
- Senior review follow-up fixes applied:
  - Added `steps.listByBoard` query so subtask 4.2 is implemented in code.
  - Added keyboard accessibility for interactive `StepCard` and `TaskGroupHeader` (Enter/Space activation + focus styles).
  - Removed step-loading UI flicker by respecting Convex loading state for steps (`undefined` gate before render).
  - Strengthened tests for status-color assertions and `blocked`/`crashed` column mapping behavior.

### File List

- dashboard/lib/constants.ts
- dashboard/components/StepCard.tsx
- dashboard/components/TaskGroupHeader.tsx
- dashboard/convex/steps.ts
- dashboard/components/KanbanBoard.tsx
- dashboard/components/KanbanColumn.tsx
- dashboard/components/StepCard.test.tsx
- dashboard/components/TaskGroupHeader.test.tsx
- dashboard/components/KanbanBoard.test.tsx

### Change Log

- 2026-02-25: Implemented Story 1.7 Kanban step rendering (step cards, task grouping headers, mixed task/step column rendering, step query, and tests).
- 2026-02-25: Senior code review fixes applied (listByBoard query, accessibility keyboard semantics, loading-state handling, stronger tests); story marked done.

## Senior Developer Review (AI)

### Reviewer

GPT-5 Codex

### Date

2026-02-25

### Outcome

Approve

### Findings Reviewed

- [x] [HIGH] Task 4.2 marked complete but no `steps.listByBoard` query existed.
- [x] [MEDIUM] `StepCard` clickable behavior lacked keyboard activation support.
- [x] [MEDIUM] `TaskGroupHeader` used non-interactive heading role for clickable behavior.
- [x] [MEDIUM] `KanbanBoard` treated loading steps as empty array, causing temporary task-card rendering flicker.
- [x] [MEDIUM] `StepCard` tests did not assert status color classes.
- [x] [LOW] Mapping coverage for `blocked` and `crashed` step statuses in Kanban tests was weak.

### Notes

- All HIGH and MEDIUM findings were fixed in code and verified by targeted tests/lint.
- LOW finding was also addressed by expanding Kanban mapping assertions.
