---
title: 'Task Soft Delete and Restore'
slug: 'task-soft-delete-and-restore'
created: '2026-02-23'
status: 'ready-for-dev'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Convex', 'React', 'Next.js', 'TypeScript', 'Framer Motion', 'Tailwind CSS', 'Lucide Icons', 'shadcn/ui']
files_to_modify: ['convex/schema.ts', 'convex/tasks.ts', 'convex/activities.ts', 'lib/constants.ts', 'components/TaskCard.tsx', 'components/KanbanBoard.tsx', 'components/DashboardLayout.tsx', 'components/TrashBinSheet.tsx']
code_patterns: ['Convex mutations with transactional activity logging', 'InlineRejection pattern for confirmations', 'useQuery reactive subscriptions', 'Framer Motion layoutId animations', 'VALID_TRANSITIONS state machine map', 'Sheet side panel pattern (TaskDetailSheet, SettingsPanel)', 'STATUS_COLORS mapping for visual consistency']
test_patterns: []
---

# Tech-Spec: Task Soft Delete and Restore

**Created:** 2026-02-23

## Overview

### Problem Statement

Tasks in the dashboard cannot be removed from the Kanban board or recovered after removal. There is no way to clean up completed, crashed, or unwanted tasks, and no mechanism to bring them back if deleted by mistake.

### Solution

Add a "deleted" status to the task state machine with soft-delete semantics (records `deletedAt` timestamp and preserves previous status). Provide a trash icon on each TaskCard with inline confirmation, a trash bin view to browse deleted tasks, and two restore modes: restore to previous state (n-1, with agent notification) or restore from beginning (inbox).

### Scope

**In Scope:**
- New `"deleted"` status in the task union type and state machine
- Soft delete: `deletedAt` timestamp + `previousStatus` field to remember state before deletion
- Delete icon (trash) on TaskCard with inline confirmation
- Trash bin icon in the dashboard header (next to Settings gear) that opens a Sheet with all deleted tasks
- Two restore modes:
  - **Restore to previous state (n-1):** Task returns to the state before the last completed step; assigned agent is notified to redo that step
  - **Restore from beginning:** Task returns to `inbox` status, `assignedAgent` cleared
- Activity events: `task_deleted`, `task_restored`
- Deleted tasks excluded from Kanban board columns and `countHitlPending`

**Out of Scope:**
- Hard delete / permanent purge
- Bulk delete operations
- CLI delete command

## Context for Development

### Codebase Patterns

- **Transactional activity logging:** Every task state change MUST write an activity event in the same Convex mutation (architectural invariant). See `tasks.ts` — all mutations (`create`, `updateStatus`, `approve`, `deny`, `retry`, `returnToLeadAgent`) insert an activity record.
- **State machine:** `VALID_TRANSITIONS` map + `UNIVERSAL_TARGETS` array in `tasks.ts` (line 7-14). The `isValidTransition()` function validates transitions. `"deleted"` should be added to `UNIVERSAL_TARGETS` (deletable from any state).
- **System messages in thread:** Mutations like `retry` and `returnToLeadAgent` insert a system message into the `messages` table for thread visibility. Delete and restore should follow this pattern.
- **Reactive queries:** All components use `useQuery(api.tasks.list)` for real-time updates. The `list` query currently returns ALL tasks — it must be updated to exclude deleted tasks.
- **Sheet panels:** `TaskDetailSheet` and `SettingsPanel` use the `Sheet` component from shadcn/ui, opening from the right side at 480px width. The trash bin should follow this same pattern.
- **InlineRejection pattern:** Multi-step actions use Framer Motion expand/collapse with `initial={{ height: 0, opacity: 0 }}` / `animate={{ height: "auto", opacity: 1 }}`. Delete confirmation follows this pattern but simpler (no textarea, just confirm/cancel buttons).
- **Header icons:** The `DashboardLayout` header has a Settings gear icon (line 71-77). The trash bin icon goes next to it, following the same `rounded-md p-2 text-muted-foreground hover:bg-accent` pattern.
- **Status colors:** `lib/constants.ts` maps each `TaskStatus` to `{ border, bg, text }` Tailwind classes. Must add a `deleted` entry.
- **Event type union:** The `eventType` field in `activities` table and in mutation type casts both use a union of string literals. Both must be extended with `"task_deleted"` and `"task_restored"`.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `convex/schema.ts:5-31` | Task table schema — add `"deleted"` to status union, add `deletedAt` and `previousStatus` optional fields |
| `convex/schema.ts:68-93` | Activities table — add `"task_deleted"` and `"task_restored"` to eventType union |
| `convex/tasks.ts:7-17` | State machine constants — add `"deleted"` to `UNIVERSAL_TARGETS` |
| `convex/tasks.ts:62-112` | `create` mutation — pattern reference for transactional activity + message logging |
| `convex/tasks.ts:121-126` | `list` query — must filter out `status !== "deleted"` |
| `convex/tasks.ts:184-222` | `retry` mutation — pattern reference for state reset + system message |
| `convex/activities.ts:4-37` | `create` mutation — type cast for eventType must include new types |
| `lib/constants.ts:1-10` | `TASK_STATUS` — add `DELETED: "deleted"` |
| `lib/constants.ts:72-111` | `STATUS_COLORS` — add `deleted` entry |
| `components/TaskCard.tsx:1-145` | Add trash icon button + inline delete confirmation |
| `components/KanbanBoard.tsx:37-49` | `tasksByStatus` filter — must exclude deleted tasks |
| `components/DashboardLayout.tsx:67-78` | Header — add trash bin icon next to Settings |
| `components/InlineRejection.tsx` | Reference pattern for inline UI expansion |
| `components/TaskDetailSheet.tsx` | Reference pattern for Sheet-based detail view |

### Technical Decisions

- **Soft delete over hard delete:** Preserves task history and activity trail; enables restore
- **`previousStatus` field:** Stores the status before deletion so restore can return to correct state
- **`"deleted"` as a status value (not a boolean):** Keeps deletion within the existing state machine, leverages the `by_status` index for efficient queries, and deleted tasks naturally disappear from status-filtered views
- **Trash bin as Sheet panel:** Follows the existing `TaskDetailSheet` / `SettingsPanel` pattern (right-side 480px sheet)
- **n-1 restore map:** Hardcoded mapping because the state machine has branching paths
- **Agent notification via activity event + system message:** The `task_restored` activity event + a system message in the task thread serves as the notification

## Implementation Plan

### Tasks

- [ ] **Task 1: Extend Convex schema with deleted status and soft-delete fields**
  - File: `convex/schema.ts`
  - Action:
    1. Add `v.literal("deleted")` to the `status` union in the `tasks` table (after `"crashed"`)
    2. Add `deletedAt: v.optional(v.string())` field to the `tasks` table
    3. Add `previousStatus: v.optional(v.string())` field to the `tasks` table
    4. Add `v.literal("task_deleted")` and `v.literal("task_restored")` to the `eventType` union in the `activities` table
  - Notes: Schema changes are automatically applied by Convex on deploy. The `previousStatus` is stored as a plain string (not a union) because it only needs to be read back, not validated against the union.

- [ ] **Task 2: Update constants with deleted status and colors**
  - File: `lib/constants.ts`
  - Action:
    1. Add `DELETED: "deleted"` to `TASK_STATUS` object (after `CRASHED`)
    2. Add `TASK_DELETED: "task_deleted"` and `TASK_RESTORED: "task_restored"` to `ACTIVITY_EVENT_TYPE` object
    3. Add `deleted` entry to `STATUS_COLORS` map with gray theme:
       ```
       deleted: {
         border: "border-l-gray-400",
         bg: "bg-gray-100 dark:bg-gray-900",
         text: "text-gray-500 dark:text-gray-400",
       }
       ```
  - Notes: The `TaskStatus` type is auto-derived from `TASK_STATUS`, so it will automatically include `"deleted"`.

- [ ] **Task 3: Add softDelete and restore mutations + update list query**
  - File: `convex/tasks.ts`
  - Action:
    1. Add `"deleted"` to the `UNIVERSAL_TARGETS` array (line 17): `const UNIVERSAL_TARGETS = ["retrying", "crashed", "deleted"];`
    2. Add `RESTORE_TARGET_MAP` constant for n-1 restore logic:
       ```typescript
       const RESTORE_TARGET_MAP: Record<string, string> = {
         inbox: "inbox",
         assigned: "inbox",
         in_progress: "assigned",
         review: "in_progress",
         done: "review",
         crashed: "in_progress",
         retrying: "in_progress",
       };
       ```
    3. Add `softDelete` mutation:
       - Args: `{ taskId: v.id("tasks") }`
       - Fetch task, throw if not found
       - Throw if already deleted: `if (task.status === "deleted") throw new ConvexError("Task is already deleted")`
       - Patch task: `{ status: "deleted", previousStatus: task.status, deletedAt: now, updatedAt: now }`
       - Insert activity: `{ taskId, agentName: task.assignedAgent, eventType: "task_deleted", description: "Task deleted: \"{task.title}\"" }`
       - Insert system message: `{ taskId, authorName: "System", authorType: "system", content: "Task moved to trash", messageType: "system_event" }`
    4. Add `restore` mutation:
       - Args: `{ taskId: v.id("tasks"), mode: v.union(v.literal("previous"), v.literal("beginning")) }`
       - Fetch task, throw if not found
       - Throw if not deleted: `if (task.status !== "deleted") throw new ConvexError("Task is not deleted")`
       - Determine target status:
         - If `mode === "beginning"`: target = `"inbox"`, clear `assignedAgent`
         - If `mode === "previous"`: target = `RESTORE_TARGET_MAP[task.previousStatus ?? "inbox"]`, preserve `assignedAgent`
       - Patch task: `{ status: target, previousStatus: undefined, deletedAt: undefined, stalledAt: undefined, updatedAt: now }`
       - If mode is "beginning", also patch `assignedAgent: undefined`
       - Insert activity: `{ taskId, agentName: task.assignedAgent, eventType: "task_restored", description: "Task restored to {target}: \"{task.title}\"" }`
       - Insert system message with restore context:
         - If mode "previous": `"Task restored. Resuming from {target} — agent {task.assignedAgent} will redo the {task.previousStatus} step."`
         - If mode "beginning": `"Task restored to inbox for re-assignment."`
    5. Add `listDeleted` query:
       - Args: none
       - Return: `ctx.db.query("tasks").withIndex("by_status", q => q.eq("status", "deleted")).collect()`
    6. Update `list` query to exclude deleted tasks:
       - Change from `ctx.db.query("tasks").collect()` to `const all = await ctx.db.query("tasks").collect(); return all.filter(t => t.status !== "deleted");`
    7. Add `"deleted"` to the `listByStatus` args union (add `v.literal("deleted")` to the status union)
    8. Update all `eventType` type cast strings in `updateStatus` mutation (line 317-333) to include `"task_deleted"` and `"task_restored"`
    9. Update `eventType` type cast in `activities.ts` `create` mutation to include the new event types
  - Notes: The `list` query filter ensures KanbanBoard never sees deleted tasks. The `listDeleted` query uses the `by_status` index for efficient retrieval.

- [ ] **Task 4: Add delete button with inline confirmation to TaskCard**
  - File: `components/TaskCard.tsx`
  - Action:
    1. Add imports: `Trash2` from `lucide-react`, `useMutation` already imported
    2. Add `softDeleteMutation = useMutation(api.tasks.softDelete)` in component
    3. Add `showDeleteConfirm` state: `const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)`
    4. Add a `Trash2` icon button in the bottom row (before the status Badge, after the agent name). Style: `className="h-3.5 w-3.5 text-muted-foreground hover:text-red-500 transition-colors cursor-pointer"`. onClick stops propagation and toggles `showDeleteConfirm`.
    5. Add inline delete confirmation below the card content (after `showRejection` block), wrapped in Framer Motion expand/collapse (same pattern as InlineRejection):
       ```tsx
       {showDeleteConfirm && (
         <div onClick={(e) => e.stopPropagation()}>
           <motion.div
             initial={{ height: 0, opacity: 0 }}
             animate={{ height: "auto", opacity: 1 }}
             exit={{ height: 0, opacity: 0 }}
             transition={{ duration: 0.15 }}
             className="overflow-hidden"
           >
             <div className="pt-2 flex items-center gap-2">
               <span className="text-xs text-muted-foreground">Delete this task?</span>
               <Button size="sm" variant="destructive" className="text-xs h-6 px-2"
                 onClick={async (e) => {
                   e.stopPropagation();
                   await softDeleteMutation({ taskId: task._id });
                 }}>
                 Yes
               </Button>
               <Button size="sm" variant="ghost" className="text-xs h-6 px-2"
                 onClick={(e) => {
                   e.stopPropagation();
                   setShowDeleteConfirm(false);
                 }}>
                 No
               </Button>
             </div>
           </motion.div>
         </div>
       )}
       ```
  - Notes: The trash icon is always visible on every card (regardless of status). Clicking shows a simple Yes/No confirmation inline, following the same Framer Motion pattern as InlineRejection but without a textarea.

- [ ] **Task 5: Create TrashBinSheet component**
  - File: `components/TrashBinSheet.tsx` (NEW FILE)
  - Action:
    1. Create a new component following the `TaskDetailSheet` pattern
    2. Props: `{ open: boolean; onClose: () => void }`
    3. Uses `useQuery(api.tasks.listDeleted)` to get deleted tasks
    4. Uses `useMutation(api.tasks.restore)` for restore actions
    5. Renders a `Sheet` (side="right", width 480px) with:
       - Header: "Trash" title with trash icon, count badge
       - ScrollArea with a list of deleted task cards, each showing:
         - Task title
         - `previousStatus` badge (showing what state it was in before deletion)
         - `deletedAt` formatted as relative time or date
         - `assignedAgent` if present
         - Two restore buttons:
           - "Restore" (primary outline) — calls `restore({ taskId, mode: "previous" })` — tooltip: "Restore to {n-1 status}, agent will redo {previousStatus} step"
           - "Restart" (secondary) — calls `restore({ taskId, mode: "beginning" })` — tooltip: "Send back to inbox"
       - Empty state: "Trash is empty" message when no deleted tasks
    6. Import `Undo2` and `RotateCcw` from lucide-react for the restore button icons
    7. Use `STATUS_COLORS` to color the `previousStatus` badge
  - Notes: Real-time reactive — when a task is restored, it disappears from this list and reappears on the Kanban board automatically via Convex reactivity.

- [ ] **Task 6: Add trash bin icon to DashboardLayout header and wire up TrashBinSheet**
  - File: `components/DashboardLayout.tsx`
  - Action:
    1. Add imports: `Trash2` from `lucide-react`, `TrashBinSheet` component, `useQuery` from `convex/react`, `api` from convex
    2. Add state: `const [trashOpen, setTrashOpen] = useState(false)`
    3. Add query for deleted count: `const deletedCount = useQuery(api.tasks.listDeleted)?.length ?? 0`
    4. Add trash bin icon button in the header, before the Settings gear icon. Follow the same styling pattern as the Settings button:
       ```tsx
       <button
         aria-label="Open trash"
         onClick={() => setTrashOpen(true)}
         className="relative rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
       >
         <Trash2 className="h-5 w-5" />
         {deletedCount > 0 && (
           <span className="absolute -top-1 -right-1 bg-gray-500 text-white text-[10px] font-medium rounded-full px-1 min-w-[16px] text-center">
             {deletedCount}
           </span>
         )}
       </button>
       ```
    5. Add `<TrashBinSheet open={trashOpen} onClose={() => setTrashOpen(false)} />` alongside the existing `TaskDetailSheet` and Settings Sheet
  - Notes: The count badge on the trash icon shows how many deleted tasks exist, providing visual feedback. The badge uses gray-500 to match the "deleted" status color theme.

- [ ] **Task 7: Update KanbanBoard to exclude deleted tasks**
  - File: `components/KanbanBoard.tsx`
  - Action:
    1. The `tasks.list` query is being updated in Task 3 to exclude deleted tasks, so no change needed in KanbanBoard's filter logic itself
    2. However, verify that the empty state check (`tasks.length === 0`) still works correctly — if all tasks are deleted, the board should show the empty state
  - Notes: This is a verification task. Since `list` is updated server-side to exclude deleted tasks, the KanbanBoard component requires no code changes. The existing `tasksByStatus` filter won't encounter `"deleted"` status tasks.

### Acceptance Criteria

- [ ] **AC 1:** Given a task in any status (inbox, assigned, in_progress, review, done, crashed, retrying), when the user clicks the trash icon on the TaskCard and confirms "Yes", then the task disappears from the Kanban board, its status becomes "deleted", `deletedAt` and `previousStatus` are recorded, and a `task_deleted` activity event is logged.

- [ ] **AC 2:** Given a task in any status, when the user clicks the trash icon and then clicks "No", then the confirmation dismisses and the task remains unchanged.

- [ ] **AC 3:** Given deleted tasks exist, when the user clicks the trash bin icon in the header, then a Sheet opens showing all deleted tasks with their previous status, deletion date, and assigned agent.

- [ ] **AC 4:** Given a deleted task that was previously `in_progress` with an assigned agent, when the user clicks "Restore" in the trash bin, then the task reappears on the Kanban board with status `assigned` (n-1), the assigned agent is preserved, a `task_restored` activity event is logged, and a system message is added to the thread notifying that the agent should redo the `in_progress` step.

- [ ] **AC 5:** Given a deleted task, when the user clicks "Restart" in the trash bin, then the task reappears on the Kanban board with status `inbox`, `assignedAgent` is cleared, a `task_restored` activity event is logged, and a system message indicates the task was returned to inbox.

- [ ] **AC 6:** Given no deleted tasks exist, when the user looks at the header trash bin icon, then no count badge is shown. When they open the trash bin Sheet, it shows an "empty" state message.

- [ ] **AC 7:** Given a task is deleted and then restored, when the restore completes, then the task disappears from the trash bin view and reappears in the correct Kanban column in real-time (no page refresh needed).

- [ ] **AC 8:** Given the n-1 restore map, when restoring a task that was `inbox` before deletion, then it restores to `inbox` (cannot go lower). When a `done` task is restored, it goes to `review`. When a `crashed` task is restored, it goes to `in_progress`.

## Additional Context

### Dependencies

- No new packages required — uses existing Lucide icons (`Trash2`, `RotateCcw`, `Undo2`), Framer Motion, Tailwind, shadcn/ui Sheet
- Tasks 1-3 (backend) must be completed before Tasks 4-6 (frontend), as the frontend depends on the new mutations and queries
- Task 2 (constants) must be completed before Tasks 4-5, as components import `STATUS_COLORS`

### Testing Strategy

- **Manual testing steps:**
  1. Create a task, advance it through statuses (inbox → assigned → in_progress)
  2. Click trash icon on the card — verify confirmation appears inline
  3. Click "No" — verify confirmation dismisses, task unchanged
  4. Click trash icon again, click "Yes" — verify task disappears from board
  5. Check activity feed — verify `task_deleted` event appears
  6. Click trash bin icon in header — verify Sheet opens with the deleted task
  7. Verify deleted task shows previous status badge and deletion time
  8. Click "Restore" — verify task reappears on board in `assigned` column (n-1 of `in_progress`)
  9. Check thread — verify system message about agent redo
  10. Delete a task again, click "Restart" — verify it goes to inbox, agent cleared
  11. Delete all tasks — verify trash icon shows count, board shows empty state
  12. Restore all — verify trash bin shows empty state

### Notes

- The `RESTORE_TARGET_MAP` is a hardcoded reverse mapping because the state machine has branching paths (e.g., `in_progress` can go to `review` or `done`), making automatic reverse computation ambiguous
- Agent notification on restore relies on the existing activity event + system message pattern — no separate push notification system is needed at this stage
- The `list` query filter is a simple in-memory filter; if the tasks table grows very large, consider adding a compound index or separate query strategy
- `countHitlPending` already filters by `status === "review"`, so deleted tasks are naturally excluded without changes
