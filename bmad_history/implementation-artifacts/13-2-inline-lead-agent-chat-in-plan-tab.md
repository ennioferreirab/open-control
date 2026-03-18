# Story 13.2: Inline Lead-Agent Chat in Execution Plan Tab

Status: ready-for-dev

## Story

As a **user**,
I want to chat with the Lead Agent directly inside the Execution Plan tab,
so that I can ask it to expand, refine, or reorganize the plan without switching to the thread view.

## Acceptance Criteria

### AC1: Collapsible Chat Sidebar

**Given** a task has an execution plan
**When** the Execution Plan tab is displayed
**Then** a chat toggle button (message icon) is visible in the plan tab header
**And** clicking it opens a chat sidebar panel on the right side of the plan tab
**And** the flow graph shrinks to accommodate the sidebar (responsive split layout)
**And** clicking the toggle again collapses the sidebar back

### AC2: Chat Message Display

**Given** the chat sidebar is open
**Then** it displays messages from the task thread filtered to:
- `type === "lead_agent_chat"` (lead-agent responses)
- `type === "lead_agent_plan"` (plan update announcements)
- `type === "user_message"` (user messages sent from this chat or the thread)
**And** messages are shown in chronological order with author labels
**And** lead-agent messages render markdown
**And** the panel auto-scrolls to the latest message
**And** messages update in real-time (Convex subscription)

### AC3: Chat Input

**Given** the chat sidebar is open
**Then** a text input area is shown at the bottom of the sidebar
**And** the placeholder reads "Ask the Lead Agent to modify the plan..."
**And** pressing Enter (without Shift) sends the message
**And** Shift+Enter inserts a newline
**And** a send button is visible to the right of the input

### AC4: Message Sending

**Given** the user types a message and sends it
**When** the message is submitted
**Then** the `messages.postUserPlanMessage` mutation is called (same as existing ThreadInput plan-chat mode)
**And** the message appears immediately in the chat sidebar
**And** the plan_negotiator on the MC backend processes it and the lead-agent responds
**And** if the lead-agent updates the plan, the flow graph re-renders with the changes in real-time

### AC5: Available in Review, In-Progress, and Done

**Given** a task has an execution plan
**When** the task status is "review" (awaitingKickoff), "in_progress", or "done"
**Then** the chat toggle button is visible and functional
**And** in "done" status, the lead-agent can propose new steps to add

### AC6: Done Status — Lead Agent Plan Negotiation

**Given** a task with status "done" and an execution plan
**When** the user sends a message via the chat sidebar (e.g., "add a step to write documentation")
**Then** the plan_negotiator processes the message with the current plan
**And** if the lead-agent returns `action: "update_plan"`, the executionPlan JSON is updated with new steps
**And** the new steps appear in the flow graph with status "planned"
**And** the steps are NOT auto-executed (the user must click Resume from Story 13-3)

### AC7: Backend — Extend plan_negotiator for Done Status

**Given** a task with status "done" and an execution plan
**When** a new user_message appears in the thread
**Then** the plan_negotiator loop processes it (currently stops at in_progress)
**And** `_is_negotiable_status()` returns True for "done" tasks with an execution plan
**And** the LLM system prompt includes a note that this is a completed task and new steps should be proposed for continuation

## Tasks / Subtasks

- [ ] Task 1: Create PlanChatSidebar component (AC: 1, 2, 3)
  - [ ] 1.1: Create `dashboard/components/PlanChatSidebar.tsx` with props: `taskId: Id<"tasks">`, `isOpen: boolean`, `onClose: () => void`
  - [ ] 1.2: Subscribe to `messages.listByTask` (same query used by ThreadView), filter to types: `lead_agent_chat`, `lead_agent_plan`, `user_message`
  - [ ] 1.3: Render messages in a scrollable container. Show author name (styled: "Lead Agent" in accent color, "You" for user). Render content with markdown support (use existing markdown renderer or simple `prose` styling).
  - [ ] 1.4: Auto-scroll to bottom on new messages (useEffect on message count change)
  - [ ] 1.5: Chat input at bottom: Textarea with min-height, send button. Enter to send, Shift+Enter for newline.
  - [ ] 1.6: On send: call `postUserPlanMessage` mutation with `{taskId, content}`, clear input
  - [ ] 1.7: Style: `w-[360px]` sidebar, `border-l`, `bg-background`, `flex flex-col h-full`. Header with "Plan Chat" title + close button.

- [ ] Task 2: Integrate sidebar into ExecutionPlanTab (AC: 1, 5)
  - [ ] 2.1: Add state `showChat: boolean` to ExecutionPlanTab
  - [ ] 2.2: Add chat toggle button (MessageSquare icon from lucide-react) in the header bar
  - [ ] 2.3: Wrap the existing content in a flex row: `<div className="flex flex-1 min-h-0">` containing the flow graph (flex-1) and conditionally the PlanChatSidebar
  - [ ] 2.4: The flow graph container should use `flex-1` so it shrinks when sidebar opens
  - [ ] 2.5: Show the chat toggle only when the task has an execution plan AND status is review/in_progress/done
  - [ ] 2.6: Pass `taskId` to PlanChatSidebar (requires ExecutionPlanTab to receive taskId prop — already available)

- [ ] Task 3: Extend plan_negotiator for "done" status (AC: 6, 7)
  - [ ] 3.1: In `mc/plan_negotiator.py`, update `_is_negotiable_status()` to return True when `status == "done"` AND the task has an execution_plan with steps
  - [ ] 3.2: In `handle_plan_negotiation()`, add a `task_status == "done"` branch that augments the system prompt with: "This task has been completed. The user wants to extend it with additional steps. Propose new steps that continue from the existing completed work. Do NOT modify completed steps."
  - [ ] 3.3: When task_status is "done" and action is "update_plan", the new plan should preserve all existing steps (enforce: all completed step titles must remain) and only add new ones
  - [ ] 3.4: In `start_plan_negotiation_loop()`, the loop already re-checks `_is_negotiable_status()` each iteration — no change needed there, but the orchestrator must start a loop for "done" tasks (see Task 4)

- [ ] Task 4: Start negotiation loop for done tasks (AC: 7)
  - [ ] 4.1: In `mc/orchestrator.py` (or wherever negotiation loops are started), detect when a "done" task gets a new user_message and start a negotiation loop if one isn't already running
  - [ ] 4.2: Alternative simpler approach: extend the existing MentionWatcher to also handle plan-chat messages for "done" tasks by forwarding them to `handle_plan_negotiation` directly (avoids a new loop)
  - [ ] 4.3: Ensure the negotiation loop stops when the task transitions from "done" to "in_progress" (via Resume from Story 13-3)

- [ ] Task 5: Write tests (AC: all)
  - [ ] 5.1: Component test for PlanChatSidebar: renders messages, filters by type, sends messages
  - [ ] 5.2: Integration test: opening sidebar in ExecutionPlanTab shows chat, flow graph resizes
  - [ ] 5.3: Unit test for `_is_negotiable_status()`: returns True for done tasks with plan
  - [ ] 5.4: Unit test for `handle_plan_negotiation` with task_status="done": preserves completed steps, adds new ones
  - [ ] 5.5: Test that "done" task negotiation does NOT auto-materialize new steps

## Dev Notes

### Existing Infrastructure to Reuse

- `messages.postUserPlanMessage` mutation — already handles posting without status transition, works for review/in_progress, extend validation to also allow "done"
- `messages.listByTask` query — already fetches all thread messages, just filter client-side
- `plan_negotiator.py` — already has full LLM negotiation flow, just extend status checks
- ThreadMessage rendering patterns from `dashboard/components/ThreadMessage.tsx`

### Key Files

- `dashboard/components/PlanChatSidebar.tsx` — new component
- `dashboard/components/ExecutionPlanTab.tsx` — add toggle + sidebar integration
- `dashboard/convex/messages.ts` — extend `postUserPlanMessage` to allow "done" status
- `mc/plan_negotiator.py` — extend `_is_negotiable_status()` + done-status prompt
- `mc/orchestrator.py` — start negotiation loop for done tasks

### Architecture Decisions

- The sidebar reuses the same Convex subscription as ThreadView (messages.listByTask) with client-side filtering. This avoids creating a new query and keeps the data layer simple.
- The chat input uses `postUserPlanMessage` (not `sendThreadMessage`) to avoid triggering task status transitions.
- For "done" tasks, the plan_negotiator updates only the executionPlan JSON — it does NOT call PlanMaterializer. Materialization happens only when the user clicks Resume (Story 13-3).

### References

- [Source: mc/plan_negotiator.py] — existing negotiation handler, _is_negotiable_status
- [Source: dashboard/convex/messages.ts#postUserPlanMessage] — plan chat mutation
- [Source: dashboard/components/ExecutionPlanTab.tsx] — current layout
- [Source: dashboard/components/ThreadInput.tsx#isPlanChatMode] — existing plan-chat integration reference
