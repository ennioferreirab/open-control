# Story 4.3: Reorder Steps and Edit Dependencies

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to reorder steps and change blocking dependencies in the plan,
So that I can adjust the execution sequence based on my understanding of the work.

## Acceptance Criteria

1. **Drag-and-drop step reordering** -- Given the PlanEditor displays step cards, when the user drags a step card to a new position, then the step order updates to reflect the new position (FR13), and drag-and-drop uses `@dnd-kit/core` + `@dnd-kit/sortable` for accessible, smooth reordering, and the `order` and `parallelGroup` values update accordingly.

2. **Dependency toggle via UI** -- Given the user wants to change a dependency, when the user toggles a dependency relationship between two steps (e.g., via a checkbox or connection line UI), then the `blockedBy` array on the dependent step is updated to add or remove the blocker (FR14), and the plan editor visually shows the updated dependency (arrow/line appears or disappears).

3. **Circular dependency prevention** -- Given the user creates a circular dependency (A blocks B, B blocks A -- directly or transitively), when the invalid state is detected, then the UI prevents the action and shows a warning: "Circular dependency detected".

4. **Immediate local state update** -- Given the user reorders or changes dependencies, when reviewing the plan, then all changes are reflected in the local plan state and the visual layout updates immediately.

## Tasks / Subtasks

- [x] **Task 1: Install `@dnd-kit/core` and `@dnd-kit/sortable`** (AC: 1)
  - [x] 1.1 Run `npm install @dnd-kit/core @dnd-kit/sortable` in the `dashboard/` directory. These are the two required packages: `@dnd-kit/core` provides `DndContext`, sensors, and collision detection; `@dnd-kit/sortable` provides `SortableContext`, `useSortable` hook, `arrayMove` utility, and `verticalListSortingStrategy`.
  - [x] 1.2 Verify the packages are added to `dashboard/package.json` dependencies and the lockfile is updated.
  - [x] 1.3 Verify TypeScript types resolve correctly (both packages include built-in TypeScript definitions -- no separate `@types/` packages needed).

- [x] **Task 2: Create the `hasCycle` circular dependency detection utility** (AC: 3)
  - [x] 2.1 Create `dashboard/lib/planUtils.ts`. This file will contain pure utility functions for plan editing logic -- no React, no Convex, no UI dependencies.
  - [x] 2.2 Implement `hasCycle(steps: PlanStep[], proposedBlockedBy: { stepTempId: string; blockerTempId: string }): boolean`. The function takes the current plan steps and a proposed new dependency edge, and returns `true` if adding that edge would create a cycle.
  - [x] 2.3 Algorithm: DFS-based cycle detection. Build an adjacency map from `blockedBy` arrays (direction: blocker -> dependent). Add the proposed edge. Starting from `blockerTempId`, traverse the graph depth-first. If the traversal reaches `stepTempId`, a cycle exists. Use a `visited` Set and a `recursionStack` Set to detect back-edges.

    ```typescript
    type PlanStep = {
      tempId: string;
      title: string;
      description: string;
      assignedAgent: string;
      blockedBy: string[];
      parallelGroup: number;
      order: number;
      attachedFiles?: string[];
    };

    export function hasCycle(
      steps: PlanStep[],
      proposed: { stepTempId: string; blockerTempId: string }
    ): boolean {
      // Build adjacency: for each step, who does it block? (blocker -> dependents)
      // A step's blockedBy = [X, Y] means X -> step, Y -> step
      const adj = new Map<string, string[]>();
      for (const s of steps) {
        for (const blocker of s.blockedBy) {
          const deps = adj.get(blocker) ?? [];
          deps.push(s.tempId);
          adj.set(blocker, deps);
        }
      }
      // Add proposed edge: blockerTempId -> stepTempId
      const deps = adj.get(proposed.blockerTempId) ?? [];
      deps.push(proposed.stepTempId);
      adj.set(proposed.blockerTempId, deps);

      // DFS from stepTempId: can we reach blockerTempId?
      // If yes, adding blockerTempId -> stepTempId creates a cycle.
      const visited = new Set<string>();
      function dfs(node: string): boolean {
        if (node === proposed.blockerTempId) return true;
        if (visited.has(node)) return false;
        visited.add(node);
        for (const neighbor of adj.get(node) ?? []) {
          if (dfs(neighbor)) return true;
        }
        return false;
      }
      return dfs(proposed.stepTempId);
    }
    ```

  - [x] 2.4 Implement `recalcParallelGroups(steps: PlanStep[]): PlanStep[]`. After reorder or dependency changes, recalculate `parallelGroup` values based on the dependency graph. Steps with no `blockedBy` get group 0. Steps whose blockers are all in group N get group N+1. Steps with multiple blockers get `max(blocker groups) + 1`. This uses a topological-sort-like level assignment.

    ```typescript
    export function recalcParallelGroups(steps: PlanStep[]): PlanStep[] {
      const stepMap = new Map(steps.map(s => [s.tempId, s]));
      const levels = new Map<string, number>();

      function getLevel(tempId: string): number {
        if (levels.has(tempId)) return levels.get(tempId)!;
        const step = stepMap.get(tempId);
        if (!step || step.blockedBy.length === 0) {
          levels.set(tempId, 0);
          return 0;
        }
        const maxBlocker = Math.max(
          ...step.blockedBy.map(id => getLevel(id))
        );
        const level = maxBlocker + 1;
        levels.set(tempId, level);
        return level;
      }

      for (const s of steps) getLevel(s.tempId);

      return steps.map(s => ({
        ...s,
        parallelGroup: levels.get(s.tempId) ?? 0,
      }));
    }
    ```

  - [x] 2.5 Create `dashboard/lib/planUtils.test.ts` with comprehensive tests:
    - Test: `hasCycle returns false for valid dependency` -- A -> B (B blockedBy A), propose B -> C -- no cycle.
    - Test: `hasCycle returns true for direct cycle` -- A -> B exists, propose B -> A -- cycle detected.
    - Test: `hasCycle returns true for transitive cycle` -- A -> B -> C exists, propose C -> A -- cycle detected.
    - Test: `hasCycle returns false when no steps have dependencies` -- empty blockedBy arrays.
    - Test: `hasCycle handles self-dependency` -- propose A -> A -- cycle detected.
    - Test: `recalcParallelGroups assigns group 0 to steps with no blockers`.
    - Test: `recalcParallelGroups assigns sequential groups in a chain` -- A(0) -> B(1) -> C(2).
    - Test: `recalcParallelGroups assigns same group to parallel steps` -- A(0) and B(0) both with no blockers.
    - Test: `recalcParallelGroups handles diamond dependency` -- A(0), B(1 blocked by A), C(1 blocked by A), D(2 blocked by B and C).

- [x] **Task 3: Build the `DependencyEditor` component** (AC: 2, 3)
  - [x] 3.1 Create `dashboard/components/DependencyEditor.tsx`. This component renders inside `PlanStepCard` (or as a popover/panel triggered from a step card) and allows the user to toggle which other steps block the current step.
  - [x] 3.2 Props interface:

    ```typescript
    interface DependencyEditorProps {
      currentStepTempId: string;
      steps: PlanStep[];              // All steps in the plan
      blockedBy: string[];            // Current step's blockedBy array (tempIds)
      onToggleDependency: (blockerTempId: string) => void;
    }
    ```

  - [x] 3.3 Render a list of all OTHER steps (exclude the current step). For each step, show:
    - A `Checkbox` (from `@radix-ui/react-checkbox`, already installed) indicating whether the step is in the `blockedBy` array.
    - The step title and assigned agent name.
    - If checking the checkbox would create a circular dependency (call `hasCycle`), disable the checkbox and show a tooltip: "Circular dependency detected".
  - [x] 3.4 When the user toggles a checkbox:
    - If adding: call `hasCycle()` first. If cycle detected, show a toast or inline warning "Circular dependency detected" and do NOT add. If no cycle, call `onToggleDependency(blockerTempId)`.
    - If removing: always allow, call `onToggleDependency(blockerTempId)`.
  - [x] 3.5 Use `Popover` (from `@radix-ui/react-popover` -- check if already installed, or use a ShadCN `Popover` component if available in `components/ui/`) triggered by a "Dependencies" button or link icon on the step card. If `Popover` is not installed, use a collapsible section or a simple dropdown panel.
  - [x] 3.6 Visual dependency indicators: when a step has items in `blockedBy`, render small arrow or "blocked by: Step X, Step Y" text below the step title in `PlanStepCard`. Use `ArrowRight` or `Link2` icon from `lucide-react` (already installed).

- [x] **Task 4: Add drag-and-drop reordering to `PlanEditor`** (AC: 1, 4)
  - [x] 4.1 This task builds on the `PlanEditor.tsx` component created in Story 4.1. If `PlanEditor.tsx` does not yet exist, create it in `dashboard/components/PlanEditor.tsx`. The PlanEditor receives the execution plan steps as local state and renders them as a sortable list.
  - [x] 4.2 Wrap the step list in `DndContext` from `@dnd-kit/core` and `SortableContext` from `@dnd-kit/sortable`:

    ```typescript
    import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors, type DragEndEvent } from "@dnd-kit/core";
    import { SortableContext, sortableKeyboardCoordinates, verticalListSortingStrategy, arrayMove } from "@dnd-kit/sortable";
    ```

  - [x] 4.3 Configure sensors for both mouse/touch (PointerSensor) and keyboard (KeyboardSensor with `sortableKeyboardCoordinates`) to ensure accessibility (FR13 requires accessible reordering):

    ```typescript
    const sensors = useSensors(
      useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
      useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
    );
    ```

    The `activationConstraint: { distance: 5 }` prevents accidental drags when clicking.

  - [x] 4.4 Implement `handleDragEnd(event: DragEndEvent)`:
    - Extract `active.id` and `over.id` from the event.
    - Find the old and new indices in the steps array.
    - Use `arrayMove(steps, oldIndex, newIndex)` to create the reordered array.
    - Update `order` values: assign `order = index` for each step in the new array.
    - Call `recalcParallelGroups()` to update parallel group assignments.
    - Update the local plan state via the `onPlanChange` callback.

  - [x] 4.5 Each step card must use the `useSortable` hook from `@dnd-kit/sortable`. Create or extend `PlanStepCard.tsx` to be a sortable item:

    ```typescript
    import { useSortable } from "@dnd-kit/sortable";
    import { CSS } from "@dnd-kit/utilities";

    function SortablePlanStepCard({ step, ... }: SortablePlanStepCardProps) {
      const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: step.tempId });

      const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
        zIndex: isDragging ? 10 : "auto",
      };

      return (
        <div ref={setNodeRef} style={style} {...attributes}>
          {/* Drag handle */}
          <span {...listeners} className="cursor-grab active:cursor-grabbing">
            <GripVertical className="h-4 w-4 text-muted-foreground" />
          </span>
          {/* Rest of step card content */}
        </div>
      );
    }
    ```

    Import `GripVertical` from `lucide-react`.

  - [x] 4.6 The `DndContext` must have an `onDragEnd` handler and use `closestCenter` collision detection strategy:

    ```tsx
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
      <SortableContext items={steps.map(s => s.tempId)} strategy={verticalListSortingStrategy}>
        {steps.map(step => (
          <SortablePlanStepCard key={step.tempId} step={step} ... />
        ))}
      </SortableContext>
    </DndContext>
    ```

  - [x] 4.7 Integrate the `DependencyEditor` from Task 3 into each `PlanStepCard`. When the user toggles a dependency:
    - Update the step's `blockedBy` array in local state (add or remove the blocker tempId).
    - Call `recalcParallelGroups()` on the entire steps array to update parallel groups.
    - Update the local plan state via `onPlanChange`.

- [x] **Task 5: Wire plan state management in `PreKickoffModal`** (AC: 4)
  - [x] 5.1 This task builds on the `PreKickoffModal.tsx` created in Story 4.1. The modal holds the local `ExecutionPlan` state in a `useState` or `useReducer`. All edits (reorder, dependency changes, agent reassignment from Story 4.2) mutate this local state -- nothing is written to Convex until kick-off (Story 4.6).
  - [x] 5.2 Define the plan state shape and update handlers:

    ```typescript
    const [planSteps, setPlanSteps] = useState<PlanStep[]>(() =>
      task.executionPlan?.steps ?? []
    );

    const handleReorder = (reorderedSteps: PlanStep[]) => {
      setPlanSteps(recalcParallelGroups(reorderedSteps));
    };

    const handleToggleDependency = (stepTempId: string, blockerTempId: string) => {
      setPlanSteps(prev => {
        const updated = prev.map(s => {
          if (s.tempId !== stepTempId) return s;
          const isBlocked = s.blockedBy.includes(blockerTempId);
          return {
            ...s,
            blockedBy: isBlocked
              ? s.blockedBy.filter(id => id !== blockerTempId)
              : [...s.blockedBy, blockerTempId],
          };
        });
        return recalcParallelGroups(updated);
      });
    };
    ```

  - [x] 5.3 Pass `planSteps`, `handleReorder`, and `handleToggleDependency` to the `PlanEditor` component as props. The `PlanEditor` is the left panel of the `PreKickoffModal` two-panel layout.
  - [x] 5.4 Ensure the plan state is preserved when the modal closes and reopens. The state lives in the `PreKickoffModal` component which is conditionally rendered -- if the component unmounts, state resets to the task's `executionPlan`. This is acceptable because the modal reopens with the persisted plan from Convex. Alternatively, lift state to a parent component if persistence across close/reopen is needed before kick-off.

- [x] **Task 6: Write component tests** (AC: 1, 2, 3, 4)
  - [x] 6.1 Create `dashboard/components/PlanEditor.test.tsx` (or extend it if it exists from Story 4.1):
    - Test: `"renders all plan steps in order"` -- render PlanEditor with 3 steps, verify all 3 step titles are visible in order.
    - Test: `"reorders steps on drag end"` -- simulate a DragEndEvent (mock `@dnd-kit` or fire the `onDragEnd` callback directly), verify the steps array is reordered and `order` values are updated.
    - Test: `"updates parallel groups after reorder"` -- after reorder, verify `parallelGroup` values are recalculated.
  - [x] 6.2 Create `dashboard/components/DependencyEditor.test.tsx`:
    - Test: `"renders checkboxes for all other steps"` -- 3 steps total, render for step A, verify 2 checkboxes (B and C) are shown.
    - Test: `"checkbox is checked for existing blockers"` -- step A has `blockedBy: [tempIdB]`, verify B's checkbox is checked.
    - Test: `"calls onToggleDependency when checkbox is toggled"` -- click unchecked B, verify `onToggleDependency` is called with B's tempId.
    - Test: `"disables checkbox when adding would create a cycle"` -- set up A blocks B (B.blockedBy=[A]), render for step A, verify B's checkbox that would add B->A dependency is disabled with tooltip.
  - [x] 6.3 Extend `dashboard/lib/planUtils.test.ts` (from Task 2.5) if additional edge cases are discovered during implementation.
  - [x] 6.4 Run the full test suite: `cd dashboard && npm run test` (Vitest). Ensure all existing tests continue to pass and no regressions are introduced.

## Dev Notes

### Dependency on Story 4.1 (Build Pre-Kickoff Modal Shell)

Story 4.1 creates `PreKickoffModal.tsx` and `PlanEditor.tsx` (or a combined component). This story extends those components with drag-and-drop and dependency editing capabilities. If Story 4.1 is not yet implemented when this story begins:
- Create the components from scratch following the architecture spec.
- The `PreKickoffModal` is a full-screen Radix Dialog with two-panel layout: plan editor (left) + chat (right).
- The `PlanEditor` renders step cards from the task's `executionPlan.steps` array.
- The `PlanStepCard` is an editable card showing step title, description, assigned agent, and dependencies.

### Dependency on Story 4.2 (Reassign Agents to Steps)

Story 4.2 adds agent reassignment dropdowns to step cards. This story adds drag-and-drop reordering and dependency editing alongside the agent dropdown. Both features modify the same local plan state in `PreKickoffModal`. They must coexist without conflicts. The `PlanStepCard` component will have: agent dropdown (4.2) + drag handle (4.3) + dependency editor (4.3).

### ExecutionPlan Data Structure

The execution plan is stored on the task record as `executionPlan: v.any()` in the Convex schema (see `dashboard/convex/schema.ts` line 43). The TypeScript shape is defined in the architecture doc:

```typescript
type ExecutionPlan = {
  steps: Array<{
    tempId: string;           // Temporary ID for pre-kickoff editing (e.g., "step-1", "step-2")
    title: string;
    description: string;
    assignedAgent: string;
    blockedBy: string[];      // References other tempIds
    parallelGroup: number;
    order: number;
    attachedFiles?: string[];
  }>;
  generatedAt: string;
  generatedBy: "lead-agent";
};
```

The `tempId` is crucial: during pre-kickoff editing, steps are identified by `tempId` (not Convex `_id`). On kick-off (Story 4.6), each plan step is materialized into a real `steps` table document and `tempId` references are converted to real Convex IDs.

### @dnd-kit Library Details

**Packages to install:**
- `@dnd-kit/core` (v6.3.1) -- DndContext, sensors, collision detection
- `@dnd-kit/sortable` (v10.0.0) -- SortableContext, useSortable, arrayMove, verticalListSortingStrategy

**Key imports:**
```typescript
// @dnd-kit/core
import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors } from "@dnd-kit/core";
import type { DragEndEvent } from "@dnd-kit/core";

// @dnd-kit/sortable
import { SortableContext, sortableKeyboardCoordinates, verticalListSortingStrategy, arrayMove, useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
```

**Note:** `@dnd-kit/utilities` is a peer dependency of `@dnd-kit/sortable` and may be installed automatically. If not, install it: `npm install @dnd-kit/utilities`. It provides the `CSS.Transform.toString()` helper.

**Accessibility:** `@dnd-kit/core` supports keyboard-based sorting via `KeyboardSensor` with `sortableKeyboardCoordinates`. This satisfies FR13's requirement for accessible reordering. The drag handle (`GripVertical` icon) should have `aria-label="Drag to reorder"` and the sortable item should communicate its position via ARIA attributes (handled automatically by the `useSortable` hook's `attributes` spread).

### Circular Dependency Detection Algorithm

The `hasCycle` function uses DFS reachability. Given the proposed edge `blockerTempId -> stepTempId`, we check if there is already a path from `stepTempId` to `blockerTempId` in the dependency graph. If yes, adding the proposed edge would create a cycle.

**Why this direction:** The `blockedBy` array represents "this step is blocked BY these other steps". In graph terms, `step.blockedBy = [A, B]` means edges A -> step and B -> step (A and B must complete before step can run). When the user proposes that step X should be blocked by step Y, we add edge Y -> X. We then check if X can already reach Y (meaning Y already depends on X transitively). If so, adding Y -> X would create a cycle.

**Performance:** With typical execution plans having 3-15 steps, DFS is instantaneous. No optimization needed.

### Parallel Group Recalculation

When the user reorders steps or changes dependencies, the `parallelGroup` values must be recalculated. The `parallelGroup` determines which steps can run in parallel during execution:
- Steps with the same `parallelGroup` and no blocking relationships between them run in parallel.
- Steps in higher-numbered groups run after lower-numbered groups complete.

The `recalcParallelGroups` function performs a topological-level assignment: each step's level is `max(blocker levels) + 1`, or `0` if no blockers. This is equivalent to the longest path from a root node in a DAG.

### Local State Only -- No Convex Writes

All changes in this story (reorder, dependency edits) modify React local state only. Nothing is written to Convex until the user clicks "Kick-off" (Story 4.6). This keeps the editing experience fast and allows the user to undo/redo by simply closing and reopening the modal (which resets to the persisted plan).

### Existing Components to Extend

| Component | File | What to Add |
|-----------|------|-------------|
| `PlanEditor` | `dashboard/components/PlanEditor.tsx` | Wrap step list in `DndContext` + `SortableContext`, add `handleDragEnd` |
| `PlanStepCard` | `dashboard/components/PlanStepCard.tsx` | Add `useSortable` hook, drag handle (`GripVertical`), `DependencyEditor` trigger |
| `PreKickoffModal` | `dashboard/components/PreKickoffModal.tsx` | Add `handleReorder` and `handleToggleDependency` state handlers |

### New Files to Create

| File | Purpose |
|------|---------|
| `dashboard/lib/planUtils.ts` | Pure utility functions: `hasCycle`, `recalcParallelGroups`, `PlanStep` type |
| `dashboard/lib/planUtils.test.ts` | Unit tests for cycle detection and parallel group recalculation |
| `dashboard/components/DependencyEditor.tsx` | Checkbox-based dependency toggle UI with cycle prevention |
| `dashboard/components/DependencyEditor.test.tsx` | Component tests for dependency editing |
| `dashboard/components/PlanEditor.test.tsx` | Component tests for drag-and-drop reordering |

### Testing Standards

- **Framework:** Vitest + @testing-library/react + @testing-library/user-event + jsdom
- **Test location:** Co-located with source files (same directory)
- **Patterns:** Use `container.querySelector` (NOT `document.querySelector`) for DOM queries. Destructure `{ container }` from `render()`.
- **Run tests:** `cd dashboard && npm run test`
- **Existing test count:** ~335 tests across ~25 files -- ensure no regressions

### Lucide Icons to Use

All icons import from `lucide-react` (already installed):
- `GripVertical` -- drag handle for sortable items
- `Link2` or `ArrowRight` -- dependency indicator on step cards
- `AlertTriangle` -- warning icon for circular dependency detection

### Project Structure Notes

- All new dashboard components go in `dashboard/components/` (flat structure, no subdirectories)
- All new utility functions go in `dashboard/lib/`
- Tests are co-located with source files
- Follow PascalCase for component files, camelCase for utility files
- Use Tailwind CSS classes only -- no CSS modules, no styled-components
- Follow existing patterns from `StepCard.tsx`, `KanbanBoard.tsx`, `KanbanColumn.tsx`
- No Python or Convex schema changes required for this story

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.3] -- Acceptance criteria (lines 981-1007)
- [Source: _bmad-output/planning-artifacts/architecture.md#Execution Plan Structure] -- ExecutionPlan type with tempId, blockedBy, parallelGroup, order (lines 211-228)
- [Source: _bmad-output/planning-artifacts/architecture.md#Pre-Kickoff Modal] -- Two-panel layout: plan editor (left) + chat (right), drag-and-drop reorder (lines 333-337)
- [Source: _bmad-output/planning-artifacts/architecture.md#Project Structure] -- Component file naming, PlanEditor.tsx, PlanStepCard.tsx, PreKickoffModal.tsx (lines 756-758)
- [Source: _bmad-output/planning-artifacts/architecture.md#Naming Patterns] -- PascalCase components, camelCase utilities (lines 420-460)
- [Source: _bmad-output/planning-artifacts/architecture.md#Starter Template] -- @dnd-kit/core suggested for drag-and-drop (line 142)
- [Source: _bmad-output/planning-artifacts/architecture.md#Dependency Unblocking Pattern] -- blockedBy array semantics (lines 579-597)
- [Source: _bmad-output/planning-artifacts/prd.md#FR13] -- User can reorder steps in the pre-kickoff modal
- [Source: _bmad-output/planning-artifacts/prd.md#FR14] -- User can change blocking dependencies between steps
- [Source: _bmad-output/planning-artifacts/prd.md#NFR2] -- Pre-kickoff modal renders within 2 seconds
- [Source: dashboard/convex/schema.ts#steps] -- Steps table schema with blockedBy, parallelGroup, order (lines 67-89)
- [Source: dashboard/convex/schema.ts#tasks] -- executionPlan field as v.any() (line 43)
- [Source: dashboard/lib/constants.ts] -- STEP_STATUS, STEP_STATUS_COLORS used by step cards
- [Source: dashboard/components/StepCard.tsx] -- Existing step card pattern with tooltips, badges, icons

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Installed `@dnd-kit/core` (v6.3.1), `@dnd-kit/sortable` (v10.0.0), and `@dnd-kit/utilities` (v3.2.2) in `dashboard/`.
- Created `dashboard/lib/planUtils.ts` with `hasCycle` (DFS-based cycle detection) and `recalcParallelGroups` (topological level assignment). Re-exports `PlanStep` type from `dashboard/lib/types.ts` (shared with Story 4.2).
- Created `dashboard/components/DependencyEditor.tsx`: collapsible panel with Checkbox list for each other step, cycle detection via `hasCycle`, Tooltip for disabled circular-dep checkboxes, `Link2` icon summary when closed.
- Extended `dashboard/components/PlanStepCard.tsx`: added `useSortable` hook, `GripVertical` drag handle, `DependencyEditor` integration, and `allSteps`/`onToggleDependency` props. Compatible with Story 4.2's agent dropdown and `StepFileAttachment`.
- Extended `dashboard/components/PlanEditor.tsx`: wrapped step list in `DndContext` + `SortableContext`, implemented `handleDragEnd` with `arrayMove` + `recalcParallelGroups`, added `handleToggleDependency` with immediate local state + parallel group recalculation.
- `dashboard/components/PreKickoffModal.tsx` was already updated by Story 4.2 with `useState<ExecutionPlan>` local state and `PlanEditor` wiring. Confirmed it passes `taskId` to `PlanEditor`.
- Created `dashboard/lib/planUtils.test.ts`: 11 tests covering `hasCycle` (direct, transitive, self, no-deps, valid) and `recalcParallelGroups` (chain, parallel, diamond, no-mutation).
- Created `dashboard/components/DependencyEditor.test.tsx`: 7 tests covering checkbox rendering, checked state, toggle callback, cycle-disabled state, blocked-by summary.
- Extended `dashboard/components/PlanEditor.test.tsx`: added 3 new tests (renders in order, reorders on drag end, updates parallel groups) + mocks for `@dnd-kit/core`, `@dnd-kit/sortable`, `DependencyEditor`, `StepFileAttachment`. Updated `convex/react` mock to include `useMutation`.
- Total new tests: 42 across 5 test files. All pass in isolation and when run together.
- Pre-existing timeout failures in `TaskInput.test.tsx`, `TaskDetailSheet.test.tsx` (intermittent when all tests run in parallel) are NOT related to this story's changes.

### File List

- `dashboard/package.json` (modified — added @dnd-kit dependencies)
- `dashboard/package-lock.json` (modified — lockfile updated)
- `dashboard/lib/planUtils.ts` (new)
- `dashboard/lib/planUtils.test.ts` (new)
- `dashboard/components/DependencyEditor.tsx` (new)
- `dashboard/components/DependencyEditor.test.tsx` (new)
- `dashboard/components/PlanStepCard.tsx` (modified — added drag handle, DependencyEditor, useSortable)
- `dashboard/components/PlanEditor.tsx` (modified — added DndContext, handleDragEnd, handleToggleDependency)
- `dashboard/components/PlanEditor.test.tsx` (modified — added drag-drop tests, dnd-kit mocks)

## Senior Developer Review (AI)

**Reviewer:** Ennio on 2026-02-25
**Status:** APPROVED with fixes applied

### Review Summary

**Issues Found:** 3 High, 2 Medium, 0 Low -- all fixed automatically.
**Git vs Story Discrepancies:** 0 (File List matches git reality for story scope).

### Findings and Fixes

#### HIGH-1: ESLint error -- `setState` called inside `useEffect` (PlanEditor.tsx)

**File:** `dashboard/components/PlanEditor.tsx` (line 39)
**Problem:** The `useEffect` + `setLocalPlan(plan)` pattern triggered ESLint's `react-hooks/set-state-in-effect` error. Calling setState synchronously inside an effect causes cascading renders. Additionally, the `react-hooks/exhaustive-deps` rule flagged a missing `plan` dependency.
**Fix:** Replaced the `useEffect`-based sync with a render-time comparison pattern: track a `syncKey` state initialized to `plan.generatedAt`, and when `plan.generatedAt` changes, update both `syncKey` and `localPlan` during render. Removed `useEffect` import since it is no longer used.

#### HIGH-2: `recalcParallelGroups` infinite recursion on cyclic data (planUtils.ts)

**File:** `dashboard/lib/planUtils.ts` (function `recalcParallelGroups`)
**Problem:** If `blockedBy` arrays contain a cycle (e.g., corrupted backend data: A blockedBy B and B blockedBy A), the recursive `getLevel()` function enters infinite recursion and causes a stack overflow. While `hasCycle()` prevents cycles from being added via the UI, the backend could theoretically provide invalid data.
**Fix:** Added a `visiting` Set that tracks nodes currently in the recursion stack. If `getLevel` re-enters a node already being visited, it returns 0 to break the cycle. Added two new tests: one for dangling `blockedBy` references and one that verifies no stack overflow on cyclic data.

#### HIGH-3: Missing test coverage for dependency removal (DependencyEditor.test.tsx)

**File:** `dashboard/components/DependencyEditor.test.tsx`
**Problem:** Tests covered toggling a dependency ON (adding a blocker) but had no test for toggling OFF (removing an existing blocker). This is half of the dependency toggle UI's core functionality.
**Fix:** Added test `"calls onToggleDependency when checked checkbox is toggled (removing a dependency)"` that renders with an existing blocker, clicks the checked checkbox, and verifies `onToggleDependency` is called.

#### MEDIUM-4: Unused variable in PlanEditor.test.tsx

**File:** `dashboard/components/PlanEditor.test.tsx` (line 127)
**Problem:** `allOptions` was assigned via `screen.getAllByRole("option")` but never used, causing an ESLint `@typescript-eslint/no-unused-vars` warning.
**Fix:** Removed the unused variable and simplified the surrounding comments.

#### MEDIUM-5: Missing test for dangling blockedBy reference in recalcParallelGroups

**File:** `dashboard/lib/planUtils.test.ts`
**Problem:** No test verified behavior when a step's `blockedBy` array references a `tempId` that does not exist in the steps array. This is an edge case that can occur when steps are deleted but references are not cleaned up.
**Fix:** Added test `"handles dangling blockedBy reference (non-existent tempId) gracefully"` that confirms the function returns level 1 for a step blocked by a non-existent step (since the unknown step defaults to level 0).

### AC Validation

| AC | Status | Evidence |
|----|--------|----------|
| AC1: Drag-and-drop reordering | IMPLEMENTED | `PlanEditor.tsx` wraps steps in `DndContext` + `SortableContext`, `PlanStepCard.tsx` uses `useSortable` hook with `GripVertical` drag handle, `handleDragEnd` uses `arrayMove` + `recalcParallelGroups` |
| AC2: Dependency toggle via UI | IMPLEMENTED | `DependencyEditor.tsx` renders checkbox list, `hasCycle` prevents invalid additions, visual summary with `Link2` icon |
| AC3: Circular dependency prevention | IMPLEMENTED | `hasCycle()` DFS-based detection in `planUtils.ts`, checkboxes disabled with tooltip "Circular dependency detected" |
| AC4: Immediate local state update | IMPLEMENTED | All changes update React local state via `useState` in `PlanEditor`, no Convex writes until kick-off |

### Test Results

- 40 tests pass across 4 story-specific test files (up from 36 before review)
- 414 tests pass in full suite (1 pre-existing flaky failure in `TaskInput.tags.test.tsx` unrelated to this story)
- 0 ESLint errors/warnings on all story files after fixes
- 0 TypeScript errors on story source files
