# Story 14.1: Human Steps — Full Lifecycle & Review Hardening

Status: dev-complete

## Story

As a **user managing manual/inbox tasks**,
I want human-assigned steps to have a complete lifecycle (dispatch → accept → work → complete),
with proper kanban visibility, drag-drop support, and thread interaction,
so that human steps don't disappear, get stuck, or block the entire execution plan.

## Context

Story 7.2 introduced `waiting_human` step status and the `acceptHumanStep` mutation, but the lifecycle was incomplete:
- Accepting a human step immediately completed it (skipping the "in progress" phase).
- Steps in `waiting_human` disappeared from the kanban (missing column mapping).
- Human steps couldn't be dragged between kanban columns.
- Thread messages were fully blocked for manual tasks.
- The lead-agent planner couldn't assign "human" to steps.
- Add Step form didn't offer "Human" as an agent option.
- Inbox manual tasks with no plan couldn't add steps (null plan bug).

This story fixes all of the above and hardens the implementation based on an adversarial code review.

## Acceptance Criteria

### AC1: Human Step Lifecycle

**Given** a step assigned to "human" is dispatched
**When** the step enters `waiting_human` status
**Then** it appears in the Review column on the kanban board
**And** the step card shows an "Accept" button

**When** the user clicks "Accept"
**Then** the step transitions to `running` (not `completed`)
**And** the step moves to the In Progress column
**And** the step card shows a "Mark Done" button

**When** the user clicks "Mark Done"
**Then** the step transitions to `completed`
**And** any blocked dependent steps are unblocked and assigned

### AC2: Human Step Kanban Drag-Drop

**Given** a human step is in `running` or `assigned` status
**Then** the step card is draggable via native HTML5 drag
**And** dropping on a valid kanban column triggers `manualMoveStep`
**And** invalid transitions are rejected with a console error (not silent)

**Given** a human step is in `waiting_human` status
**Then** the step card is NOT draggable (must use Accept button)

### AC3: Human Agent in Forms & Planner

**Given** the AddStepForm or EditStepForm is open
**Then** a "Human" option with User icon is available in the agent dropdown
**And** the lead-agent planner can assign "human" to steps requiring manual action
**And** the step dispatcher transitions human steps to `waiting_human` instead of spawning an agent

### AC4: Thread Messages for Manual Tasks

**Given** a manual (inbox) task
**When** the user opens the thread
**Then** the thread input is visible (not hidden)
**And** messages can be sent without triggering agent status transitions
**And** `postUserPlanMessage` allows `inbox` status for manual tasks

### AC5: Inbox Manual Task Plan Management

**Given** an inbox manual task with no execution plan
**When** the user clicks "Add Step"
**Then** a new plan is created from scratch (null plan handled gracefully)
**And** steps can be added, edited, and deleted inline
**And** "Save Plan" persists the plan to Convex
**And** "Start" transitions the task to `in_progress`

### AC6: State Machine Parity

**Given** the step state machine in Python and Convex
**Then** `waiting_human` allows transitions to `[running, completed, crashed]`
**And** the Python task state machine matches Convex (including `inbox → planning`)
**And** event type mappings exist for all new transitions

### AC7: Security & Robustness (Review Hardening)

- `manualMoveStep` restricts transitions to human-safe subset only (no `blocked`, no arbitrary states)
- `sendThreadMessage` blocks `in_progress` status for non-manual tasks (restored guard)
- `deleteStep` allows deletion of `assigned` human steps (not just planned/blocked)
- `startInboxTask` validates existing plan field shapes before proceeding
- `StepCard` shows error feedback when accept/complete mutations fail
- `KanbanColumn` logs step drop errors to console instead of silently swallowing
- `TaskDetailSheet` uses separate error state for "Mark Done" action
- `step_dispatcher.py` doesn't re-raise after crash fallback (prevents double error handling)

## Technical Design

### New Mutations

| Mutation | File | Purpose |
|----------|------|---------|
| `manualMoveStep` | `dashboard/convex/steps.ts` | Move human steps between states with restricted transition set |
| `saveExecutionPlan` | `dashboard/convex/tasks.ts` | Persist execution plan on inbox/review tasks |
| `startInboxTask` | `dashboard/convex/tasks.ts` | Transition inbox → in_progress with plan validation |

### Modified Mutations

| Mutation | Change |
|----------|--------|
| `acceptHumanStep` | Transitions to `running` (was `completed`), sets `startedAt`, no dependent unblocking |
| `sendThreadMessage` | Removed `isManual` guard; conditional status transition; `in_progress` blocked for non-manual only |
| `postUserPlanMessage` | Removed `isManual` guard; allows `inbox` for manual tasks |
| `deleteStep` | Allows `assigned` human steps to be deleted |

### State Machine Changes

| From | To | Added In |
|------|-----|----------|
| `waiting_human` | `running` | Step transitions (both Python and Convex) |
| `inbox` | `in_progress` | Task transitions (both Python and Convex) |
| `inbox` | `planning` | Python task transitions (was missing, Convex already had it) |

### Frontend Components

| Component | Change |
|-----------|--------|
| `StepCard` | Accept/Mark Done buttons, drag support, error feedback |
| `TaskCard` | Drag moved to outer div wrapper (motion.js conflict fix) |
| `KanbanBoard` | `waiting_human → review` column mapping |
| `KanbanColumn` | Step drop handler with `application/step-id` data transfer |
| `FlowStepNode` | Accept + Mark Done buttons for human steps |
| `ExecutionPlanTab` | Null plan handling, delete step, node click-to-edit |
| `AddStepForm` | Human agent option in dropdown |
| `EditStepForm` | Human agent option + delete button |
| `StepDetailPanel` | Uses `HUMAN_AGENT_NAME` constant |
| `TaskDetailSheet` | Save Plan, Start, Mark Done buttons for inbox tasks |
| `ThreadInput` | Removed `isManual` early return |

### Python Backend

| File | Change |
|------|--------|
| `mc/types.py` | `HUMAN_AGENT_NAME = "human"` constant |
| `mc/planner.py` | System prompt allows "human" assignment; validator accepts it |
| `mc/plan_parser.py` | Agent roster includes virtual "human" entry |
| `mc/step_dispatcher.py` | Human steps → `waiting_human` instead of agent spawn |
| `mc/state_machine.py` | `waiting_human → running` transition + event mapping; `inbox → planning` |

### Constants

| File | Change |
|------|--------|
| `dashboard/lib/constants.ts` | `WAITING_HUMAN` in `STEP_STATUS`, `STEP_STATUS_COLORS`, `HUMAN_AGENT_NAME` |

## Files Changed (22 files)

- `dashboard/components/AddStepForm.tsx`
- `dashboard/components/EditStepForm.tsx`
- `dashboard/components/ExecutionPlanTab.tsx`
- `dashboard/components/FlowStepNode.tsx`
- `dashboard/components/KanbanBoard.tsx`
- `dashboard/components/KanbanColumn.tsx`
- `dashboard/components/StepCard.tsx`
- `dashboard/components/StepDetailPanel.tsx`
- `dashboard/components/TaskCard.tsx`
- `dashboard/components/TaskDetailSheet.tsx`
- `dashboard/components/ThreadInput.tsx`
- `dashboard/convex/messages.ts`
- `dashboard/convex/steps.ts`
- `dashboard/convex/steps.test.ts`
- `dashboard/convex/tasks.ts`
- `dashboard/lib/constants.ts`
- `mc/plan_parser.py`
- `mc/planner.py`
- `mc/state_machine.py`
- `mc/step_dispatcher.py`
- `mc/types.py`
- `tests/mc/test_step_state_machine.py`

## Test Coverage

- **Python:** 49 tests pass (`tests/mc/test_step_state_machine.py` + `tests/mc/`)
- **TypeScript:** 26 tests pass (`dashboard/convex/steps.test.ts`)
- **Type check:** `npx tsc --noEmit` clean
