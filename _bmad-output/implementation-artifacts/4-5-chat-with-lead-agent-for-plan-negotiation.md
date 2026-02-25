# Story 4.5: Chat with Lead Agent for Plan Negotiation

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to chat with the Lead Agent in the pre-kickoff modal to request plan changes,
So that I can negotiate the execution strategy conversationally.

## Acceptance Criteria

1. **Chat panel renders on the right side of PreKickoffModal** -- Given the PreKickoffModal is open with a two-panel layout, When the modal renders, Then the right panel shows a chat interface with: a scrollable message list, a text input area at the bottom, and a send button (FR16).

2. **User messages post to unified thread with correct type** -- Given the PreKickoffModal chat panel is visible, When the user types a message and clicks send (or presses Enter), Then the message is posted to the task's unified thread with `authorType: "user"`, `messageType: "user_message"`, and `type: "lead_agent_chat"` (FR16), And the message appears in the chat panel immediately via Convex reactive query.

3. **Chat panel filters to lead_agent_chat messages only** -- Given the task's unified thread contains multiple message types (step_completion, user_message, system_error, lead_agent_plan, lead_agent_chat), When the chat panel renders, Then it displays ONLY messages where `type === "lead_agent_chat"`, And messages are shown in chronological order (oldest at top, newest at bottom).

4. **Lead Agent responds via bridge subscription** -- Given the user posts a chat message requesting a plan change (e.g., "Add a final step for the general agent to write a summary"), When the Lead Agent receives the message via bridge subscription on the Python side, Then the Lead Agent processes the request and responds with either: an updated `ExecutionPlan` written to the task record (FR17), or a clarifying question or acknowledgment posted as a `lead_agent_chat` message via `bridge.post_lead_agent_message()`.

5. **PlanEditor re-renders when ExecutionPlan updates** -- Given the Lead Agent updates the ExecutionPlan on the task record, When the task record's `executionPlan` field changes, Then the PlanEditor (left panel) re-renders with the updated plan (new steps, changed assignments, etc.) via Convex reactive query, And the chat panel shows the Lead Agent's response explaining the changes.

6. **Multi-turn conversation works chronologically** -- Given the user and Lead Agent exchange multiple messages, When the conversation continues, Then all messages appear chronologically in the chat panel, And the plan editor always reflects the latest version of the plan.

7. **Empty state shows helpful prompt** -- Given the chat panel is open and no `lead_agent_chat` messages exist yet, When the panel renders, Then it shows a placeholder message: "Chat with the Lead Agent to request plan changes" or similar guidance text.

8. **Input is disabled during message submission** -- Given the user clicks send, When the message is being submitted, Then the input and send button are disabled until the mutation completes, And the input clears on success.

9. **Convex mutation for user plan chat exists** -- Given the dashboard needs to post user chat messages during plan negotiation, When a new Convex mutation `messages:postPlanChatMessage` is called, Then it creates a message with `authorType: "user"`, `authorName: "User"`, `messageType: "user_message"`, `type: "lead_agent_chat"`, And it does NOT transition the task status (the task stays in `reviewing_plan`).

10. **Python bridge listens for plan negotiation messages** -- Given the Python backend subscribes to thread messages for a task in `reviewing_plan` status, When a new `lead_agent_chat` message from the user arrives, Then the bridge dispatches it to the Lead Agent's plan negotiation handler, And the handler can call `bridge.post_lead_agent_message(task_id, response, "lead_agent_chat")` and optionally `bridge.update_execution_plan(task_id, updated_plan)`.

## Tasks / Subtasks

- [x] **Task 1: Create `messages:postPlanChatMessage` Convex mutation** (AC: 2, 9)
  - [x] 1.1 Add a new mutation `postPlanChatMessage` to `dashboard/convex/messages.ts` with args: `taskId: v.id("tasks")`, `content: v.string()`.
  - [x] 1.2 The mutation handler creates a message with: `authorName: "User"`, `authorType: "user"`, `messageType: "user_message"`, `type: "lead_agent_chat"`, `timestamp: new Date().toISOString()`.
  - [x] 1.3 The mutation MUST validate that the task exists and is in `reviewing_plan` status. If not, throw `ConvexError("Task must be in reviewing_plan status to chat with Lead Agent")`.
  - [x] 1.4 The mutation MUST NOT change the task status -- the task stays in `reviewing_plan`. This is different from `sendThreadMessage` which transitions to `assigned`.
  - [x] 1.5 Insert a corresponding `activities` event with `eventType: "thread_message_sent"` and description `"User sent plan negotiation message"`.

- [x] **Task 2: Create `messages:listPlanChat` Convex query** (AC: 3)
  - [x] 2.1 Add a new query `listPlanChat` to `dashboard/convex/messages.ts` with args: `taskId: v.id("tasks")`.
  - [x] 2.2 The query fetches all messages for the task using the `by_taskId` index, then filters to only return messages where `type === "lead_agent_chat"`.
  - [x] 2.3 Return messages in chronological order (the default Convex order by `_creationTime` is ascending, which is correct for chat -- oldest at top, newest at bottom).

- [x] **Task 3: Create `PlanChatPanel` React component** (AC: 1, 3, 6, 7, 8)
  - [x] 3.1 Create `dashboard/components/PlanChatPanel.tsx` with `"use client"` directive.
  - [x] 3.2 Define `PlanChatPanelProps` interface: `{ taskId: Id<"tasks"> }`.
  - [x] 3.3 Use `useQuery(api.messages.listPlanChat, { taskId })` to subscribe to `lead_agent_chat` messages reactively. This auto-updates when new messages arrive.
  - [x] 3.4 Render a vertical layout with:
    - Top: scrollable message list using `ScrollArea` from ShadCN UI, with `ref` for auto-scroll to bottom.
    - Bottom: input area with `Textarea` (min-height 60px, max-height 120px, resize-none) and a `Button` with `SendHorizontal` icon.
  - [x] 3.5 Each message renders using a simplified inline layout (not the full `ThreadMessage` component, to keep the chat lightweight):
    - User messages: right-aligned, blue-50 background, "You" as author.
    - Lead Agent messages: left-aligned, indigo-50 background, "Lead Agent" as author.
    - Both show timestamp in `text-xs text-muted-foreground`.
    - Lead Agent messages render content through `MarkdownRenderer` (the Lead Agent may respond with formatted plan descriptions).
  - [x] 3.6 Implement auto-scroll: when a new message arrives and the user is at the bottom (or near bottom, within 100px), auto-scroll to the newest message. If the user has scrolled up, do not auto-scroll (they are reading history).
  - [x] 3.7 Implement empty state: when no messages exist, show centered placeholder text: "Chat with the Lead Agent to negotiate plan changes. Try: 'Add a summary step at the end' or 'Reassign step 2 to the dev agent'." in `text-sm text-muted-foreground`.
  - [x] 3.8 Implement message submission:
    - On click Send or Enter (without Shift), call `useMutation(api.messages.postPlanChatMessage)` with `{ taskId, content: trimmedContent }`.
    - Disable input and button during submission (`isSubmitting` state).
    - Clear input on success.
    - Show error text in `text-xs text-red-500` if mutation fails.
  - [x] 3.9 Handle Enter key: Enter submits, Shift+Enter inserts a newline (same pattern as `ThreadInput.tsx`).

- [x] **Task 4: Create `PreKickoffModal` component shell** (AC: 1, 5)
  - [x] 4.1 Create `dashboard/components/PreKickoffModal.tsx` with `"use client"` directive.
  - [x] 4.2 Define `PreKickoffModalProps` interface: `{ taskId: Id<"tasks">; open: boolean; onClose: () => void }`.
  - [x] 4.3 Use ShadCN `Dialog` component as the modal shell. Set `modal={true}` for backdrop click handling. Use `DialogContent` with `className="max-w-6xl w-[95vw] h-[85vh] flex flex-col p-0"` for a large, near-full-screen layout.
  - [x] 4.4 Modal header (inside `DialogHeader`): show task title on the left, "Kick-off" button on the right (disabled for this story -- Story 4.6 enables it). Include a close (X) button.
  - [x] 4.5 Modal body: two-panel layout using CSS grid or flexbox:
    - Left panel (60% width): `PlanEditor` component (from story 4.2, integrated concurrently), receiving `executionPlan` from the task record. This panel re-renders automatically when the Lead Agent updates the plan.
    - Right panel (40% width): `PlanChatPanel` component, receiving `taskId`.
    - Panels separated by a vertical border (`border-r`).
  - [x] 4.6 Load task data with `useQuery(api.tasks.getById, { taskId })`. Pass `task.executionPlan` to plan editor and `task._id` to `PlanChatPanel`.
  - [x] 4.7 The modal closes on Escape or clicking the close button. On close, the task remains in `reviewing_plan` status (no status change mutation).

- [x] **Task 5: Integrate PreKickoffModal into the dashboard** (AC: 1)
  - [x] 5.1 Identify the appropriate parent component where task cards are rendered. Add state for tracking which task's PreKickoffModal is open: `const [reviewingTaskId, setReviewingTaskId] = useState<Id<"tasks"> | null>(null)`.
  - [x] 5.2 Add logic to detect tasks in `reviewing_plan` status. When a task enters `reviewing_plan`, auto-open the PreKickoffModal for that task. This can be implemented via a `useEffect` that watches the task list for status changes.
  - [x] 5.3 Render `<PreKickoffModal taskId={reviewingTaskId} open={!!reviewingTaskId} onClose={() => setReviewingTaskId(null)} />` in the parent component.
  - [x] 5.4 Add a "Review Plan" button to the task card (in `TaskCard.tsx` or `StepCard.tsx`) for tasks in `reviewing_plan` status, so the user can reopen the modal after closing it.

- [x] **Task 6: Implement Python-side plan negotiation handler** (AC: 4, 10)
  - [x] 6.1 Create a plan negotiation handler function in `nanobot/mc/plan_negotiator.py`: `async def handle_plan_negotiation(bridge: ConvexBridge, task_id: str, user_message: str, current_plan: dict) -> None`.
  - [x] 6.2 The handler:
    - Constructs an LLM prompt with the current plan (JSON) and user's message.
    - Calls the LLM via `provider_factory.create_provider()` with 30s timeout.
    - Parses the LLM JSON response: if `action=update_plan`, calls `bridge.update_execution_plan()` AND `bridge.post_lead_agent_message()` with the explanation.
    - If `action=clarify` or acknowledgment, calls only `bridge.post_lead_agent_message()`.
  - [x] 6.3 Added `start_plan_negotiation_loop()` that uses `bridge.async_subscribe("messages:listPlanChat", ...)` to detect new user messages on reviewing_plan tasks, stops when task leaves reviewing_plan status.
  - [x] 6.4 Uses `bridge.post_lead_agent_message(task_id, content, "lead_agent_chat")` for Lead Agent responses.
  - [x] 6.5 Uses `bridge.update_execution_plan(task_id, plan.to_dict())` to write updated plans, normalizing via `ExecutionPlan.from_dict()` first.

- [x] **Task 7: Add `reviewing_plan` to Python TaskStatus enum** (AC: 4, 10)
  - [x] 7.1 Added `REVIEWING_PLAN = "reviewing_plan"` to `nanobot/mc/types.py` `TaskStatus` enum.
  - [x] 7.2 Added `reviewing_plan -> planning` and `reviewing_plan -> inbox` transitions to `nanobot/mc/state_machine.py`.

- [x] **Task 8: Write Vitest tests for PlanChatPanel** (AC: 1, 2, 3, 6, 7, 8)
  - [x] 8.1 Created `dashboard/components/PlanChatPanel.test.tsx` with 10 tests.
  - [x] 8.2 Test: "renders empty state when no messages exist" -- passes.
  - [x] 8.3 Test: "renders user message with blue background and 'You' author" -- passes.
  - [x] 8.4 Test: "renders Lead Agent message with indigo background" -- passes.
  - [x] 8.5 Test: "send button is disabled when input is empty" -- passes.
  - [x] 8.6 Test: "send button is disabled during submission" -- passes.
  - [x] 8.7 Test: "input clears after successful send" -- passes.

- [x] **Task 9: Write Vitest tests for PreKickoffModal** (AC: 1, 5)
  - [x] 9.1 Updated `dashboard/components/PreKickoffModal.test.tsx` with 6 tests.
  - [x] 9.2 Test: "renders two-panel layout with plan and chat" -- passes.
  - [x] 9.3 Test: "renders task title in header" -- passes.
  - [x] 9.4 Test: "renders disabled Kick-off button" -- passes.

- [x] **Task 10: Write pytest tests for plan negotiation handler** (AC: 4, 10)
  - [x] 10.1 Created `nanobot/mc/test_plan_negotiator.py` with 9 tests.
  - [x] 10.2 Test: "handler posts lead_agent_chat response via bridge" -- passes.
  - [x] 10.3 Test: "handler updates execution plan when LLM returns modified plan" -- passes.
  - [x] 10.4 Test: "handler posts clarification without updating plan" -- passes.

## Dev Notes

### Existing Infrastructure That This Story Uses

**Bridge methods already available (no changes needed):**
- `bridge.post_lead_agent_message(task_id, content, msg_type)` -- Posts Lead Agent messages with `type: "lead_agent_chat"` or `"lead_agent_plan"`. Defined in `nanobot/mc/bridge.py` lines 379-405.
- `bridge.update_execution_plan(task_id, plan)` -- Updates the `executionPlan` field on a task document. Defined in `nanobot/mc/bridge.py` lines 407-422.
- `bridge.get_task_messages(task_id)` -- Fetches all thread messages for a task. Defined in `nanobot/mc/bridge.py` lines 271-274.
- `bridge.async_subscribe(function_name, args, poll_interval)` -- Async polling subscription that returns an `asyncio.Queue`. Defined in `nanobot/mc/bridge.py` lines 640-696.

**Convex mutations already available (no changes needed):**
- `messages:postLeadAgentMessage` -- Posts Lead Agent plan or chat messages. Defined in `dashboard/convex/messages.ts` lines 153-185. Accepts `type: "lead_agent_plan" | "lead_agent_chat"`.
- `messages:listByTask` -- Fetches all messages for a task. Defined in `dashboard/convex/messages.ts` lines 26-34.

**TypeScript constants already available:**
- `STRUCTURED_MESSAGE_TYPE.LEAD_AGENT_CHAT = "lead_agent_chat"` -- Defined in `dashboard/lib/constants.ts` line 87.
- `STRUCTURED_MESSAGE_TYPE.LEAD_AGENT_PLAN = "lead_agent_plan"` -- Defined in `dashboard/lib/constants.ts` line 86.

**Python types already available:**
- `ThreadMessageType.LEAD_AGENT_CHAT = "lead_agent_chat"` -- Defined in `nanobot/mc/types.py` line 130.
- `ThreadMessageType.LEAD_AGENT_PLAN = "lead_agent_plan"` -- Defined in `nanobot/mc/types.py` line 129.
- `ExecutionPlan` and `ExecutionPlanStep` dataclasses -- Defined in `nanobot/mc/types.py` lines 145-256. Include `to_dict()` and `from_dict()` methods.

**Task status `reviewing_plan` already in Convex:**
- The `tasks.ts` transition map includes `planning -> reviewing_plan` (line 8).
- The `updateExecutionPlan` mutation in `tasks.ts` allows updates when task status is in `["planning", "reviewing_plan", "ready", ...]` (line 347-351).

### ThreadMessage Type Rendering Already Supported

The `ThreadMessage.tsx` component (lines 44-62) already handles `lead_agent_chat` messages:
- `STRUCTURED_MESSAGE_TYPE.LEAD_AGENT_CHAT` renders with `bg-indigo-50` background and "Chat" label.
- The existing `ThreadMessage` component is for the full task thread view. The `PlanChatPanel` uses a simplified inline rendering for the modal chat -- no need to reuse `ThreadMessage` inside the modal, but the styling should be consistent (indigo-50 for Lead Agent, blue-50 for user).

### PreKickoffModal Layout Architecture

```
+--------------------------------------------------------------------+
| [X]  Task: "Compile February financial report..."    [Kick-off]    |
+--------------------------------------------------------------------+
| LEFT PANEL (60%)               | RIGHT PANEL (40%)                 |
| ┌────────────────────────────┐ | ┌────────────────────────────────┐|
| │  ExecutionPlanTab          │ | │  PlanChatPanel (scrollable)    │|
| │  ┌──────────────────────┐  │ | │                                │|
| │  │ Step 1: Extract data │  │ | │  [Lead Agent] I've created a   │|
| │  │ financial-agent      │  │ | │  plan with 4 steps...          │|
| │  └──────────────────────┘  │ | │                                │|
| │  ┌──────────────────────┐  │ | │  [You] Add a final step for    │|
| │  │ Step 2: Reconcile    │  │ | │  the general agent to write    │|
| │  │ financial-agent      │  │ | │  a summary                     │|
| │  └──────────────────────┘  │ | │                                │|
| │  ┌──────────────────────┐  │ | │  [Lead Agent] Done! I added    │|
| │  │ Step 3: Generate PDF │  │ | │  Step 5: "Write summary"       │|
| │  │ general-agent        │  │ | │  assigned to general-agent.    │|
| │  └──────────────────────┘  │ | │                                │|
| │  ┌──────────────────────┐  │ | ├────────────────────────────────┤|
| │  │ Step 4: Email report │  │ | │  [  Type a message...    ] [>] │|
| │  │ secretary-agent      │  │ | └────────────────────────────────┘|
| └────────────────────────────┘ |                                    |
+--------------------------------+------------------------------------+
```

### Convex Reactive Query Pattern for Real-Time Chat

The chat panel uses `useQuery(api.messages.listPlanChat, { taskId })` which creates a Convex subscription. When any mutation inserts a new message with `type: "lead_agent_chat"` for this task, Convex automatically re-runs the query and pushes the new result to the client. The React component re-renders with the updated message list. No polling, no WebSocket management needed in application code.

Similarly, the `ExecutionPlanTab` on the left panel receives its data from `useQuery(api.tasks.getById, { taskId })`. When the Lead Agent calls `bridge.update_execution_plan()`, the task record updates in Convex, the reactive query re-runs, and the plan visualization updates automatically.

### User Message Posting Flow

```
User types message in PlanChatPanel
  -> calls postPlanChatMessage Convex mutation
    -> inserts message: { authorType: "user", type: "lead_agent_chat", ... }
    -> inserts activity: { eventType: "thread_message_sent" }
  -> Convex pushes update to listPlanChat subscription
  -> PlanChatPanel re-renders with new message
```

### Lead Agent Response Flow

```
Python bridge polls messages:listPlanChat for task in reviewing_plan
  -> detects new user message
  -> dispatches to plan_negotiation handler
  -> handler calls LLM with current plan + user request
  -> LLM returns response (modified plan or clarification)
  -> If plan changed:
      bridge.update_execution_plan(task_id, new_plan)
      bridge.post_lead_agent_message(task_id, explanation, "lead_agent_chat")
  -> If clarification only:
      bridge.post_lead_agent_message(task_id, response, "lead_agent_chat")
  -> Convex pushes updates to both listPlanChat and getById subscriptions
  -> Dashboard updates chat panel + plan visualization simultaneously
```

### Why postPlanChatMessage Is Separate from sendThreadMessage

The existing `sendThreadMessage` mutation (messages.ts lines 192-261) is designed for the general thread interaction flow and does the following side effects:
1. Transitions the task to `assigned` status
2. Clears the `executionPlan` field
3. Sets the `assignedAgent`

None of these side effects are appropriate for plan negotiation chat:
- The task must stay in `reviewing_plan` status during negotiation.
- The `executionPlan` must NOT be cleared -- it is the subject of negotiation.
- No agent assignment change occurs.

Therefore, a dedicated `postPlanChatMessage` mutation is needed that only inserts the message and activity event, without any task status changes.

### Dependency on Story 4.1 (Pre-Kickoff Modal Shell)

This story depends on Epic 4 Story 4.1 in the new epics structure (Build Pre-Kickoff Modal Shell), which establishes:
- The `reviewing_plan` task status and transitions in `tasks.ts`
- The `supervisionMode` field on tasks
- The auto-opening behavior for supervised tasks

However, the `reviewing_plan` status already exists in the Convex transition map (tasks.ts line 8). This story creates the `PreKickoffModal` component as part of the implementation, since it does not yet exist in the codebase.

### Common LLM Developer Mistakes to Avoid

1. **DO NOT reuse `sendThreadMessage` for plan chat** -- That mutation transitions the task to `assigned` and clears the execution plan. Use the new `postPlanChatMessage` mutation instead.

2. **DO NOT render ALL thread messages in the chat panel** -- Filter to `type === "lead_agent_chat"` only. The general thread view in `TaskDetailSheet` shows all message types; the chat panel is scoped to plan negotiation.

3. **DO NOT import the Convex SDK directly in Python** -- All Convex interaction must go through `ConvexBridge`. The bridge methods `post_lead_agent_message` and `update_execution_plan` already exist.

4. **DO NOT block the Python gateway event loop** -- Use `asyncio.to_thread()` for synchronous bridge calls in async context. Use `bridge.async_subscribe()` for polling-based subscription.

5. **DO NOT forget the activity event** -- Every message insertion must also insert a `thread_message_sent` activity event. This is an architectural invariant.

6. **DO NOT make the PlanChatPanel too heavy** -- Use a simplified inline message rendering, not the full `ThreadMessage` component. The chat panel is inside a modal and should be lightweight.

7. **DO NOT change task status on chat message send** -- The task stays in `reviewing_plan` throughout the negotiation. Only the kick-off action (Story 4.6) changes the status.

8. **DO NOT use `v.any()` for the new mutation args** -- Use proper Convex validators (`v.string()`, `v.id()`) for type safety.

### What This Story Does NOT Include

- **Kick-off button functionality** -- Story 4.6 enables the kick-off button
- **Agent reassignment UI** -- Story 4.2 in the new Epic 4 structure
- **Step reordering and dependency editing** -- Story 4.3 in the new Epic 4 structure
- **Document attachment to steps** -- Story 4.4 in the new Epic 4 structure
- **Auto-opening the modal when task enters reviewing_plan** -- Story 4.1 covers auto-open behavior; this story provides a manual "Review Plan" button as a simpler trigger
- **LLM prompt engineering for plan modification** -- The handler calls the LLM, but the prompt design is iterative and may be refined post-MVP

### Project Structure Notes

**Files to create:**
- `dashboard/components/PlanChatPanel.tsx` -- Chat panel for plan negotiation (right side of modal)
- `dashboard/components/PlanChatPanel.test.tsx` -- Vitest tests for PlanChatPanel
- `dashboard/components/PreKickoffModal.tsx` -- Two-panel modal shell for plan review
- `dashboard/components/PreKickoffModal.test.tsx` -- Vitest tests for PreKickoffModal
- `nanobot/mc/plan_negotiator.py` (or handler function in `orchestrator.py`) -- Python-side plan negotiation handler
- `nanobot/mc/test_plan_negotiator.py` -- pytest tests for plan negotiation handler

**Files to modify:**
- `dashboard/convex/messages.ts` -- Add `postPlanChatMessage` mutation and `listPlanChat` query
- `nanobot/mc/types.py` -- Add `REVIEWING_PLAN` to `TaskStatus` enum if missing
- `nanobot/mc/state_machine.py` -- Add `reviewing_plan` transitions if missing
- `nanobot/mc/gateway.py` -- Integrate plan negotiation subscription for `reviewing_plan` tasks

**Files NOT to modify:**
- `dashboard/convex/schema.ts` -- No schema changes; `lead_agent_chat` type already exists
- `dashboard/lib/constants.ts` -- No constant changes; `STRUCTURED_MESSAGE_TYPE.LEAD_AGENT_CHAT` already exists
- `nanobot/mc/bridge.py` -- No bridge changes; `post_lead_agent_message` and `update_execution_plan` already exist
- `dashboard/components/ThreadMessage.tsx` -- Chat panel uses its own rendering; ThreadMessage is for the general thread view

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 4.5`] -- Story definition with BDD acceptance criteria (lines 1033-1061)
- [Source: `_bmad-output/planning-artifacts/prd.md#FR16`] -- User can chat with Lead Agent in pre-kickoff modal
- [Source: `_bmad-output/planning-artifacts/prd.md#FR17`] -- Lead Agent can dynamically modify the plan in response to user chat
- [Source: `_bmad-output/planning-artifacts/architecture.md#Pre-Kickoff Modal`] -- Two-panel layout: plan editor (left) + Lead Agent chat (right)
- [Source: `_bmad-output/planning-artifacts/architecture.md#API & Communication Patterns`] -- Convex as single communication hub; ThreadMessage types
- [Source: `_bmad-output/planning-artifacts/architecture.md#Frontend Architecture`] -- Pre-kickoff modal is a full-screen modal overlay, not a route
- [Source: `dashboard/convex/messages.ts#postLeadAgentMessage`] -- Existing mutation for Lead Agent messages (lines 153-185)
- [Source: `dashboard/convex/messages.ts#sendThreadMessage`] -- Existing thread message mutation (NOT to be used for plan chat) (lines 192-261)
- [Source: `dashboard/convex/tasks.ts#VALID_TRANSITIONS`] -- Task state machine including `planning -> reviewing_plan` (line 8)
- [Source: `dashboard/convex/tasks.ts#updateExecutionPlan`] -- Mutation to update execution plan on task record (lines 345+)
- [Source: `nanobot/mc/bridge.py#post_lead_agent_message`] -- Python bridge method for posting Lead Agent messages (lines 379-405)
- [Source: `nanobot/mc/bridge.py#update_execution_plan`] -- Python bridge method for updating execution plan (lines 407-422)
- [Source: `nanobot/mc/bridge.py#async_subscribe`] -- Async polling subscription for Python-side reactivity (lines 640-696)
- [Source: `nanobot/mc/types.py#ThreadMessageType`] -- Python enum with `LEAD_AGENT_CHAT` (line 130)
- [Source: `nanobot/mc/types.py#ExecutionPlan`] -- Execution plan dataclass with `to_dict()` and `from_dict()` (lines 166-256)
- [Source: `dashboard/components/ThreadMessage.tsx#getMessageStyles`] -- Styling for `lead_agent_chat` messages (lines 54-55)
- [Source: `dashboard/components/ExecutionPlanTab.tsx`] -- Read-only plan visualization component (532 lines)
- [Source: `dashboard/components/ThreadInput.tsx`] -- Existing thread input component (pattern reference for Enter key handling)
- [Source: `dashboard/lib/constants.ts#STRUCTURED_MESSAGE_TYPE`] -- TypeScript constants for message types (lines 82-88)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Implemented `postPlanChatMessage` Convex mutation in `dashboard/convex/messages.ts` with proper status validation (reviewing_plan only), no task status transition, and activity event insertion.
- Implemented `listPlanChat` Convex query filtering to `type === "lead_agent_chat"` messages only, in chronological order.
- Created `PlanChatPanel.tsx` React component with Convex reactive subscription, simplified inline message rendering (user=blue-50, lead-agent=indigo-50), auto-scroll within 100px threshold, empty state, Enter-to-send, Shift+Enter for newlines, error display, and MarkdownRenderer for Lead Agent responses.
- Updated `PreKickoffModal.tsx` to replace the disabled chat placeholder with the live `PlanChatPanel` component. The modal integrates with `PlanEditor` (from story 4.2 concurrent implementation) in the left panel.
- Task 5 (DashboardLayout integration with auto-open and "Review Plan" button) was already implemented by concurrent story 4.1. Verified and confirmed functional.
- Added `REVIEWING_PLAN = "reviewing_plan"` to Python `TaskStatus` enum in `nanobot/mc/types.py`.
- Added `reviewing_plan -> planning` and `reviewing_plan -> inbox` transitions to `nanobot/mc/state_machine.py`.
- Created `nanobot/mc/plan_negotiator.py` with `handle_plan_negotiation()` (LLM-based plan modification handler) and `start_plan_negotiation_loop()` (async polling subscription). Handler uses structured JSON response protocol: `action=update_plan` triggers plan update + explanation; `action=clarify` sends chat-only response.
- All tests pass: 16 Vitest tests (PlanChatPanel: 10, PreKickoffModal: 6), 9 pytest tests (plan_negotiator).

### File List

- `dashboard/convex/messages.ts` (modified) — Added `postPlanChatMessage` mutation and `listPlanChat` query
- `dashboard/components/PlanChatPanel.tsx` (created) — Chat panel component for plan negotiation
- `dashboard/components/PlanChatPanel.test.tsx` (created) — 10 Vitest tests for PlanChatPanel
- `dashboard/components/PreKickoffModal.tsx` (modified) — Integrated PlanChatPanel into right panel
- `dashboard/components/PreKickoffModal.test.tsx` (modified) — Updated 6 tests for new modal structure
- `nanobot/mc/types.py` (modified) — Added `REVIEWING_PLAN = "reviewing_plan"` to TaskStatus enum
- `nanobot/mc/state_machine.py` (modified) — Added reviewing_plan transitions to VALID_TRANSITIONS
- `nanobot/mc/plan_negotiator.py` (created) — Python plan negotiation handler and subscription loop
- `nanobot/mc/test_plan_negotiator.py` (created) — 9 pytest tests for plan negotiation handler

## Senior Developer Review (AI)

**Reviewer:** Ennio (via Claude Opus 4.6)
**Date:** 2026-02-25

### Review Summary

**Issues Found:** 3 High, 2 Medium, 1 Low
**All issues auto-fixed.**

### Findings

#### HIGH Issues (Fixed)

1. **[H1] Python state machine `reviewing_plan` transitions out of parity with Convex** (`nanobot/mc/state_machine.py`)
   - Original code had `reviewing_plan -> [planning, inbox]` but Convex has `reviewing_plan -> ["planning", "ready"]`. The `inbox` target was fabricated (not in Convex). The `ready` target was missing (not yet in Python enum).
   - Also missing `PLANNING` transitions entirely: Convex has `planning -> ["failed", "reviewing_plan", "ready"]`.
   - **Fix:** Corrected VALID_TRANSITIONS to mirror Convex exactly (minus `ready` which Story 4.6 will add). Added `PLANNING -> [FAILED, REVIEWING_PLAN]` and `REVIEWING_PLAN -> [PLANNING]`. Added corresponding TRANSITION_EVENT_MAP entries.

2. **[H2] Internal exception details leaked to user via chat messages** (`nanobot/mc/plan_negotiator.py` lines 183, 260)
   - `f"I encountered an error processing your request: {exc}"` exposes raw Python exception objects (tracebacks, class names, internal paths) to the end user via the chat panel.
   - Similarly, plan parse errors exposed `{parse_exc}` details.
   - **Fix:** Replaced with generic user-friendly error messages. Internal details remain in server logs via `logger.error()`.

3. **[H3] `postPlanChatMessage` Convex mutation has no server-side content validation** (`dashboard/convex/messages.ts` line 197)
   - Empty strings or whitespace-only messages would be accepted and stored. Client-side trim check in `PlanChatPanel` can be bypassed by direct API calls or malicious clients.
   - **Fix:** Added `content.trim()` validation at the top of the mutation handler. Throws `ConvexError("Message content cannot be empty")` for empty/whitespace content. Uses trimmed content for storage.

#### MEDIUM Issues (Fixed)

4. **[M1] Deprecated `asyncio.get_event_loop()` in test_plan_negotiator.py** (line 118)
   - `asyncio.get_event_loop()` is deprecated since Python 3.10 and emits `DeprecationWarning` on Python 3.13.
   - **Fix:** Replaced with `asyncio.run()` which is the recommended approach. Deprecation warning eliminated.

5. **[M2] Fire-and-forget `asyncio.create_task` in `start_plan_negotiation_loop` swallows exceptions** (`nanobot/mc/plan_negotiator.py` line 361)
   - `asyncio.create_task(handle_plan_negotiation(...))` without a done callback means any unexpected exceptions in the background task would produce only a "Task exception was never retrieved" warning, making debugging very difficult.
   - **Fix:** Added `_log_task_exception` callback via `task.add_done_callback()` that logs exceptions properly via the module logger.

#### LOW Issues (Fixed)

6. **[L1] Misleading comment in state_machine.py** (line 20)
   - Comment said "reviewing_plan -> ready (kick-off approved)" but code had `[planning, inbox]`. Neither matched.
   - **Fix:** Updated comments to accurately describe the transitions and note that `ready` will be added in Story 4.6.

### Change Log

| Date | Author | Entry |
|------|--------|-------|
| 2026-02-25 | Reviewer (AI) | Fixed 6 issues: state machine Convex parity (H1), error detail leaking (H2), missing server-side content validation (H3), deprecated asyncio usage (M1), fire-and-forget task exception handling (M2), misleading comments (L1). All tests pass. Status -> done. |
