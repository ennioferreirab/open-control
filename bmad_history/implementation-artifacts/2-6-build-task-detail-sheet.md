# Story 2.6: Build Task Detail Sheet

Status: done

## Story

As a **user**,
I want to click on a task card and see its full details in a slide-out panel,
So that I can read the complete task story — description, status, agent, and threaded messages — without leaving the board.

## Acceptance Criteria

1. **Given** the Kanban board is displayed with task cards, **When** the user clicks a TaskCard, **Then** a ShadCN Sheet slides out from the right (480px wide) displaying the task detail view
2. **Given** the TaskDetailSheet is open, **Then** the Sheet header shows: task title (`text-lg`, `font-semibold`), status Badge, assigned agent name with avatar
3. **Given** the TaskDetailSheet is open, **When** the user views the Thread tab (default active tab), **Then** threaded messages from the `messages` table are displayed chronologically (newest at bottom)
4. **Given** messages exist for the task, **Then** each ThreadMessage shows: author avatar (24px), author name, timestamp, message content
5. **Given** messages exist, **Then** message variants are visually distinct: agent messages (white bg), user messages (blue-50 bg), system events (gray-50 bg, italic)
6. **Given** the TaskDetailSheet is open, **When** the underlying task is updated in Convex (status change, new message), **Then** the sheet content refreshes in place without closing
7. **Given** the TaskDetailSheet is open, **When** the user presses Escape or clicks outside the sheet, **Then** the sheet closes and focus returns to the triggering TaskCard
8. **Given** a task has no messages, **When** the Thread tab is viewed, **Then** muted text displays: "No messages yet. Agent activity will appear here."
9. **And** `TaskDetailSheet.tsx` and `ThreadMessage.tsx` components are created
10. **And** Convex `messages.ts` contains a `listByTask` query (filtered by taskId, ordered by timestamp)
11. **And** the Sheet provides `role="dialog"` and proper focus trap (inherited from ShadCN/Radix)
12. **And** Vitest test exists for `TaskDetailSheet.tsx`

## Tasks / Subtasks

- [x] Task 1: Create the Convex `messages.ts` file (AC: #10)
  - [x] 1.1: Create `dashboard/convex/messages.ts`
  - [x] 1.2: Implement `listByTask` query: accepts `taskId` (id of tasks), returns messages filtered by taskId, ordered by timestamp ascending (oldest first, newest at bottom)
  - [x] 1.3: Implement `create` mutation: accepts `taskId`, `authorName`, `authorType`, `content`, `messageType`, `timestamp`

- [x] Task 2: Create the ThreadMessage component (AC: #4, #5)
  - [x] 2.1: Create `dashboard/components/ThreadMessage.tsx`
  - [x] 2.2: Accept props: `message` object (matching Convex message document shape)
  - [x] 2.3: Render author avatar (24px ShadCN `Avatar` with initials), author name, timestamp, message content
  - [x] 2.4: Implement visual variants based on `authorType`:
    - Agent messages: white background (`bg-white`)
    - User messages: blue-50 background (`bg-blue-50`)
    - System events: gray-50 background (`bg-gray-50`), italic text
  - [x] 2.5: Implement visual variants based on `messageType`:
    - Review feedback: amber-50 background (`bg-amber-50`) — overrides author-based styling
    - Approval: green-50 background with checkmark icon
    - Denial: red-50 background with X icon

- [x] Task 3: Create the TaskDetailSheet component (AC: #1, #2, #3, #6, #7, #8, #9, #11)
  - [x] 3.1: Create `dashboard/components/TaskDetailSheet.tsx` with `"use client"` directive
  - [x] 3.2: Accept props: `taskId` (string or null — null means sheet is closed), `onClose` callback
  - [x] 3.3: Use ShadCN `Sheet` component with `side="right"` and width 480px
  - [x] 3.4: In the sheet header: display task title (`text-lg font-semibold`), status Badge (using status color mapping from Story 2.3), assigned agent name
  - [x] 3.5: Use `useQuery(api.tasks.getById, { taskId })` to reactively fetch the task data
  - [x] 3.6: Use ShadCN `Tabs` with tabs: "Thread" (default active), "Execution Plan", "Config"
  - [x] 3.7: Thread tab: use `useQuery(api.messages.listByTask, { taskId })` to reactively fetch messages
  - [x] 3.8: Render messages as `ThreadMessage` components in chronological order (oldest first)
  - [x] 3.9: Show "No messages yet. Agent activity will appear here." when no messages exist
  - [x] 3.10: Execution Plan tab: placeholder text "Execution plan details will appear here." (implemented in Story 4.3)
  - [x] 3.11: Config tab: display task configuration (trust level, reviewers, timeouts) in read-only format
  - [x] 3.12: Sheet opens via `open` prop controlled by parent state
  - [x] 3.13: Sheet closes via `onOpenChange` callback, Escape key, or click outside (ShadCN Sheet handles this)

- [x] Task 4: Add `getById` query to Convex tasks (AC: #6)
  - [x] 4.1: Add `getById` query to `dashboard/convex/tasks.ts`: accepts `taskId` (id of tasks), returns the single task document

- [x] Task 5: Wire TaskDetailSheet to TaskCard clicks (AC: #1, #7)
  - [x] 5.1: Add state management for selected task in `KanbanBoard.tsx` or `DashboardLayout.tsx`: `const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null)`
  - [x] 5.2: Pass `onClick` handler to `TaskCard` that sets `selectedTaskId`
  - [x] 5.3: Render `TaskDetailSheet` with `taskId={selectedTaskId}` and `onClose={() => setSelectedTaskId(null)}`
  - [x] 5.4: Ensure focus returns to the triggering card when sheet closes

- [x] Task 6: Write unit tests (AC: #12)
  - [x] 6.1: Create `dashboard/components/TaskDetailSheet.test.tsx`
  - [x] 6.2: Test sheet renders with task title and status badge
  - [x] 6.3: Test Thread tab shows messages
  - [x] 6.4: Test empty thread shows placeholder text
  - [x] 6.5: Test message variants render with correct background colors

## Dev Notes

### Critical Architecture Requirements

- **Convex reactive queries in the sheet**: Both the task data and messages are fetched via `useQuery`. When the task status changes or a new message arrives, the sheet updates in real-time WITHOUT closing. This is Convex's reactive behavior — the sheet stays open and its content refreshes.
- **ShadCN Sheet = Radix Dialog**: The ShadCN `Sheet` component is built on Radix UI's Dialog primitive. It provides: `role="dialog"`, focus trap (Tab cycles within the sheet), Escape to close, click-outside to close, and screen reader announcements. These are inherited automatically.
- **Message thread order**: Messages are displayed chronologically — oldest at the top, newest at the bottom. This matches the chat convention. The user reads top-to-bottom to follow the conversation.
- **Task ID as sheet control**: The sheet is controlled by a `taskId` state. When `taskId` is not null, the sheet is open for that task. When null, the sheet is closed. This pattern avoids passing entire task objects through props.

### ShadCN Sheet Usage Pattern

```tsx
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";

<Sheet open={!!taskId} onOpenChange={(open) => !open && onClose()}>
  <SheetContent side="right" className="w-[480px] sm:w-[480px]">
    <SheetHeader>
      <SheetTitle>{task.title}</SheetTitle>
      <SheetDescription>
        <Badge>{task.status}</Badge>
        {task.assignedAgent && <span>{task.assignedAgent}</span>}
      </SheetDescription>
    </SheetHeader>
    {/* Tabs content */}
  </SheetContent>
</Sheet>
```

### ShadCN Tabs Usage Pattern

```tsx
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

<Tabs defaultValue="thread" className="mt-4">
  <TabsList>
    <TabsTrigger value="thread">Thread</TabsTrigger>
    <TabsTrigger value="plan">Execution Plan</TabsTrigger>
    <TabsTrigger value="config">Config</TabsTrigger>
  </TabsList>
  <TabsContent value="thread">
    {/* ThreadMessage list */}
  </TabsContent>
  <TabsContent value="plan">
    <p className="text-sm text-slate-400">
      Execution plan details will appear here.
    </p>
  </TabsContent>
  <TabsContent value="config">
    {/* Task config display */}
  </TabsContent>
</Tabs>
```

### ThreadMessage Component Pattern

```tsx
// dashboard/components/ThreadMessage.tsx
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Doc } from "../convex/_generated/dataModel";

interface ThreadMessageProps {
  message: Doc<"messages">;
}

function getInitials(name: string): string {
  return name.slice(0, 2).toUpperCase();
}

function getMessageBg(message: Doc<"messages">): string {
  // Message type takes priority for review-related styling
  if (message.messageType === "review_feedback") return "bg-amber-50";
  if (message.messageType === "approval") return "bg-green-50";
  if (message.messageType === "denial") return "bg-red-50";

  // Then author type
  if (message.authorType === "user") return "bg-blue-50";
  if (message.authorType === "system") return "bg-gray-50";
  return "bg-white";
}

export function ThreadMessage({ message }: ThreadMessageProps) {
  const bg = getMessageBg(message);
  const isSystem = message.authorType === "system";

  return (
    <div className={`flex gap-2 p-2 rounded-md ${bg}`}>
      <Avatar className="h-6 w-6 shrink-0">
        <AvatarFallback className="text-xs">
          {getInitials(message.authorName)}
        </AvatarFallback>
      </Avatar>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-slate-700">
            {message.authorName}
          </span>
          <span className="text-xs text-slate-400">
            {new Date(message.timestamp).toLocaleTimeString()}
          </span>
        </div>
        <p className={`text-sm text-slate-600 mt-0.5 ${isSystem ? "italic" : ""}`}>
          {message.content}
        </p>
      </div>
    </div>
  );
}
```

### Convex queries needed

```typescript
// dashboard/convex/tasks.ts — add getById query
export const getById = query({
  args: { taskId: v.id("tasks") },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.taskId);
  },
});

// dashboard/convex/messages.ts
export const listByTask = query({
  args: { taskId: v.id("tasks") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("messages")
      .withIndex("by_taskId", (q) => q.eq("taskId", args.taskId))
      .collect();
  },
});
```

### State Management for Sheet Open/Close

The selected task state lives in the component that renders both the KanbanBoard and the TaskDetailSheet. This is typically `DashboardLayout.tsx` or a new wrapper component:

```tsx
// In DashboardLayout.tsx or a KanbanWrapper component
const [selectedTaskId, setSelectedTaskId] = useState<Id<"tasks"> | null>(null);

return (
  <>
    <KanbanBoard onTaskClick={(taskId) => setSelectedTaskId(taskId)} />
    <TaskDetailSheet
      taskId={selectedTaskId}
      onClose={() => setSelectedTaskId(null)}
    />
  </>
);
```

The `Id<"tasks">` type comes from Convex's generated types and provides type safety for document IDs.

### Common LLM Developer Mistakes to Avoid

1. **DO NOT render the Sheet as a separate route** — The TaskDetailSheet is an overlay on the existing dashboard, NOT a separate page. It uses ShadCN `Sheet` which renders as a dialog overlay.

2. **DO NOT pass the entire task object to TaskDetailSheet** — Pass only the `taskId`. The sheet fetches the task data itself via `useQuery`. This ensures the sheet always shows the latest data (reactive updates).

3. **DO NOT close the sheet when the task updates** — The sheet must stay open and refresh its content when the underlying task changes. Convex reactive queries handle this automatically — the `useQuery` result updates in place.

4. **DO NOT forget the `side="right"` prop on SheetContent** — The sheet slides from the right side. Without this prop, it may slide from a different direction.

5. **DO NOT hardcode the sheet width in CSS** — Use the `className="w-[480px]"` on `SheetContent`. The 480px width is specified in the UX design.

6. **DO NOT render messages in reverse order** — Messages are chronological: oldest at top, newest at bottom. Use ascending timestamp order from the Convex query.

7. **DO NOT override ShadCN Sheet's focus trap** — The Sheet component inherits Radix Dialog's focus trap behavior. Do not add custom focus management that conflicts with it.

8. **DO NOT create separate Sheet instances per task** — There is ONE TaskDetailSheet component. It receives the current `taskId` as a prop. When the user clicks a different card, the sheet updates its content (doesn't close and reopen).

9. **DO NOT forget to handle the loading state** — When `taskId` changes, `useQuery` briefly returns `undefined` while fetching the new task's data. Show a subtle loading state or the previous task's data until the new data arrives.

10. **DO NOT implement the Execution Plan tab content** — This story creates the tab with placeholder text. The actual execution plan visualization is Story 4.3.

11. **DO NOT add approve/deny buttons to the sheet header** — HITL actions are added in Epic 6. This story focuses on the read-only detail view.

### What This Story Does NOT Include

- **No Execution Plan tab content** — Placeholder text only. Built in Story 4.3.
- **No HITL approve/deny buttons** — Added in Story 6.1 and 6.2.
- **No user message input** — Users cannot send messages from the sheet in this story. User messaging through the sheet could be added later.
- **No message sending** — The `messages.create` mutation is created but not called from the dashboard in this story. Messages are sent by agents via the bridge.
- **No retry button** — The "Retry from Beginning" button for crashed tasks is Story 6.4.
- **No Config tab interactive controls** — The Config tab shows read-only task configuration. Editing is not supported.

### Files Created in This Story

| File | Purpose |
|------|---------|
| `dashboard/convex/messages.ts` | `listByTask` query + `create` mutation for messages table |
| `dashboard/components/TaskDetailSheet.tsx` | 480px slide-out Sheet with Tabs (Thread, Plan, Config) |
| `dashboard/components/ThreadMessage.tsx` | Single message with author avatar, name, timestamp, content |
| `dashboard/components/TaskDetailSheet.test.tsx` | Unit tests for sheet rendering and message display |

### Files Modified in This Story

| File | Changes |
|------|---------|
| `dashboard/convex/tasks.ts` | Add `getById` query |
| `dashboard/components/KanbanBoard.tsx` | Add `onTaskClick` prop handling |
| `dashboard/components/TaskCard.tsx` | Wire `onClick` to parent handler |
| `dashboard/components/DashboardLayout.tsx` | Add selected task state + TaskDetailSheet rendering |

### Verification Steps

1. Click a task card on the Kanban board — Sheet slides out from the right (480px wide)
2. Sheet header shows task title, status badge, and assigned agent (if any)
3. Thread tab is active by default — shows "No messages yet" for tasks without messages
4. Manually insert a message in Convex dashboard for the task — message appears in the thread in real-time
5. Different message types show correct backgrounds: agent (white), user (blue-50), system (gray-50)
6. Click Execution Plan tab — shows placeholder text
7. Click Config tab — shows task configuration (trust level, etc.)
8. Press Escape — sheet closes
9. Click outside sheet — sheet closes
10. Update task status while sheet is open — sheet content updates without closing
11. `cd dashboard && npx vitest run` — Tests pass

### References

- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#Component Strategy`] — TaskDetailSheet spec: 480px, right slide-out, Tabs (Thread/Plan/Config)
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#Component Strategy`] — ThreadMessage spec: avatar (24px), author name, timestamp, content, visual variants
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#UX Consistency Patterns`] — Anti-disruption: sheet content refreshes without closing
- [Source: `_bmad-output/planning-artifacts/architecture.md#Data Architecture`] — Messages table: task-scoped, threaded conversation
- [Source: `_bmad-output/planning-artifacts/architecture.md#Frontend Architecture`] — Routing: task detail is Sheet overlay, not a route
- [Source: `_bmad-output/planning-artifacts/epics.md#Story 2.6`] — Original story definition with acceptance criteria
- [Source: `dashboard/convex/schema.ts`] — Messages table schema with by_taskId index

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References
- DashboardLayout test failure: mock `useQuery` returning `[]` for all queries caused `TaskDetailSheet` to treat an array as a valid task object. Fixed by adding `isTaskLoaded` guard that checks for `"status" in task`.

### Completion Notes List
- Task 1: Created `dashboard/convex/messages.ts` with `listByTask` query (by_taskId index) and `create` mutation
- Task 2: Created `dashboard/components/ThreadMessage.tsx` with visual variants for authorType (agent=white, user=blue-50, system=gray-50+italic) and messageType (review_feedback=amber-50, approval=green-50+checkmark, denial=red-50+X icon)
- Task 3: Created `dashboard/components/TaskDetailSheet.tsx` — 480px right Sheet with 3 tabs (Thread, Execution Plan placeholder, Config read-only), reactive Convex queries, loading state
- Task 4: Added `getById` query to `dashboard/convex/tasks.ts`
- Task 5: Wired TaskDetailSheet to TaskCard clicks via KanbanBoard -> KanbanColumn -> TaskCard `onClick` prop chain, with `selectedTaskId` state in DashboardLayout
- Task 6: Created `dashboard/components/TaskDetailSheet.test.tsx` — 12 tests covering sheet rendering, message display, empty states, and all message variant backgrounds

### File List
**Created:**
- `dashboard/convex/messages.ts`
- `dashboard/components/ThreadMessage.tsx`
- `dashboard/components/TaskDetailSheet.tsx`
- `dashboard/components/TaskDetailSheet.test.tsx`

**Modified:**
- `dashboard/convex/tasks.ts` — added `getById` query
- `dashboard/components/KanbanBoard.tsx` — added `onTaskClick` prop
- `dashboard/components/KanbanColumn.tsx` — added `onTaskClick` prop, wired to TaskCard
- `dashboard/components/DashboardLayout.tsx` — added `selectedTaskId` state, renders TaskDetailSheet
