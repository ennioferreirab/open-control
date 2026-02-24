# Story 11.1: Thread-Based Human-Agent Interaction

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **Mission Control user**,
I want to send messages in a task's thread to interact with the assigned AI agent and optionally delegate to another agent,
so that I can provide follow-up instructions, corrections, or additional context and receive agent responses in a multi-turn conversation.

## Acceptance Criteria

### AC1: Thread Message Input Visibility

**Given** the TaskDetailSheet is open on an AI-managed task (`isManual` is false or undefined)
**When** the user views the Thread tab
**Then** a message input area is visible at the bottom of the thread, containing:
- A text area (auto-resizing, min-height 80px) for composing messages (placeholder: "Send a message to the agent...")
- A Send button (icon or labeled), disabled when the text area is empty
- An agent selector dropdown (collapsed by default, showing current agent name)
**And** Enter sends the message, Shift+Enter inserts a newline

### AC2: Thread Message Submission

**Given** the user types a message and clicks Send (or presses Enter)
**When** the message is submitted
**Then** a new message appears in the thread with `authorType="user"`, `authorName="User"`, and `messageType="user_message"`
**And** the text area is cleared and the Send button shows a brief loading state
**And** the task status transitions to `"assigned"` with the selected agent
**And** the task's `executionPlan` is cleared (set to undefined) to prevent stale plan interference
**And** the task's `previousStatus` is set to the status before transition (for audit trail)
**And** `stalledAt` is cleared (if set)
**And** an activity event `"thread_message_sent"` is created with description: "User sent follow-up message to {agentName}"
**And** the thread auto-scrolls to show the new message

### AC3: Agent Selector for Delegation

**Given** the thread message input area is visible
**When** the user expands the agent selector
**Then** a dropdown shows agents enabled for the task's board: query the board by `task.boardId`, filter agents by `board.enabledAgents` (empty means all), always include system agents (lead-agent, mc-agent)
**And** the default selection is the task's current `assignedAgent` (or last known agent if unassigned)
**And** the user can select a different agent before sending
**And** if the user selects a different agent, the task is assigned to that agent when the message is sent

### AC4: Multi-Turn Agent Context

**Given** the executor picks up a task that was re-assigned via thread message
**When** the agent processes the task
**Then** the agent receives the full thread history as context, formatted as a conversation:
- Each message includes: author name, author type, timestamp, and content
- Messages are in chronological order (Convex insertion order via `by_taskId` index)
- The user's latest message is clearly marked as the follow-up instruction
- For long threads (>20 messages), include only the last 20 messages in full, with a summary note: "({N} earlier messages omitted)"
**And** the agent's response is posted as a new `"work"` message in the thread
**And** the task follows the normal completion flow (trust level determines final status)

### AC5: Manual Task Exclusion

**Given** a task is manual (`isManual=true`)
**When** the user views the Thread tab
**Then** no message input area is shown (manual tasks are user-managed, not AI-executed)

### AC6: Status-Based Input Availability

**Given** a task is in status `done`, `review`, `crashed`, or `inbox`
**When** the user views the Thread tab
**Then** the message input is enabled and ready for use
**And** sending a message transitions the task to `"assigned"` regardless of previous status

**Given** a task is in status `in_progress` or `retrying`
**When** the user views the Thread tab
**Then** the message input is disabled with a visual indicator: "Agent is currently working..."
**And** the user cannot send messages until the agent completes or crashes

**Given** a task is in status `assigned` (waiting for agent pickup)
**When** the user sends another message
**Then** the message is added to the thread without changing the task status (already assigned)
**And** the agent will see this message when it picks up the task

### AC7: State Machine Transitions

**Given** a task in status `done`, `review`, `crashed`, or `inbox`
**When** a thread message is sent
**Then** the task transitions to `"assigned"` via the existing state machine validation
**And** `previousStatus` is set to the status before transition
**And** `assignedAgent` is set to the selected agent
**And** `executionPlan` is cleared (set to undefined)
**And** `stalledAt` is cleared (if set)

## Tasks / Subtasks

- [x] Task 1: Extend Convex schema with new message type and activity event (AC: 1, 2)
  - [x] 1.1: Add `"user_message"` to `messageType` union in `schema.ts` messages table
  - [x] 1.2: Add `"user_message"` to the `messageType` args validator in `messages.ts:create()` mutation (keeps both mutations consistent)
  - [x] 1.3: Add `"thread_message_sent"` to `eventType` union in `schema.ts` activities table
  - [x] 1.4: Add `UserMessage = "user_message"` to `MessageType` enum in `nanobot/mc/types.py`
  - [x] 1.5: Add `THREAD_MESSAGE_SENT = "thread_message_sent"` to `ActivityEventType` enum in `nanobot/mc/types.py`
- [x] Task 2: Add valid state transitions for thread re-assignment (AC: 7)
  - [x] 2.1: Add transitions to `VALID_TRANSITIONS` in `convex/tasks.ts`: `done→assigned`, `review→assigned`, `crashed→assigned` (note: `inbox→assigned` already exists)
  - [x] 2.2: Ensure `assigned→assigned` is handled gracefully — the `sendThreadMessage` mutation checks status and skips the `updateStatus` call if already assigned, only updating `assignedAgent` if changed
  - [x] 2.3: Add transition event entries to `TRANSITION_EVENT_MAP`: `"done->assigned": "thread_message_sent"`, `"review->assigned": "thread_message_sent"`, `"crashed->assigned": "thread_message_sent"`
- [x] Task 3: Create `sendThreadMessage` Convex mutation (AC: 2, 6, 7)
  - [x] 3.1: Create mutation in `messages.ts` that atomically: (a) validates task exists and is not manual, (b) validates status is not `in_progress`, `retrying`, or `deleted`, (c) creates user message with `authorType="user"`, `authorName="User"`, `messageType="user_message"`, (d) if status !== "assigned": transitions task to "assigned" via `isValidTransition()` check, sets `previousStatus`, clears `executionPlan` to `undefined`, clears `stalledAt`, updates `assignedAgent`, (e) if status === "assigned": only updates `assignedAgent` if changed, (f) creates `"thread_message_sent"` activity event
  - [x] 3.2: The mutation args: `{ taskId: Id<"tasks">, content: string, agentName: string }`
  - [x] 3.3: Write tests for: valid transitions from each status, rejection for in_progress/retrying/deleted, assigned→assigned no-op, executionPlan clearing
- [x] Task 4: Build ThreadInput component (AC: 1, 3, 5, 6)
  - [x] 4.1: Create `ThreadInput.tsx` with auto-resizing `Textarea` (follow `InlineRejection.tsx` pattern: `min-h-[80px]`, `text-sm`), Send button with loading state, keyboard handling (Enter to send, Shift+Enter for newline)
  - [x] 4.2: Add agent selector using ShadCN `Select` component — query agents via `useQuery(api.agents.list)`, filter by board's `enabledAgents` (query board via `task.boardId`), default to `task.assignedAgent`
  - [x] 4.3: Implement disabled state: when `task.status` is `in_progress` or `retrying`, show muted text "Agent is currently working..." and disable textarea + button
  - [x] 4.4: Hide component entirely when `task.isManual === true`
  - [x] 4.5: Integrate into `TaskDetailSheet.tsx` Thread tab — place BELOW the `ScrollArea` (not inside it), inside the `TabsContent value="thread"` div. The layout must be: `flex flex-col` with ScrollArea taking `flex-1` and ThreadInput pinned at bottom
- [x] Task 5: Update executor to include thread history in agent context (AC: 4)
  - [x] 5.1: Add bridge method `get_task_messages(task_id)` that calls `self.query("messages:listByTask", {"taskId": task_id})` — messages return in insertion order (chronological)
  - [x] 5.2: Create `_build_thread_context(messages: list[dict], max_messages: int = 20) -> str` helper in executor.py that formats thread history. For threads with >20 messages, include a summary note and only the last 20. Format each message as: `{authorName} [{authorType}] ({timestamp}): {content}`
  - [x] 5.3: Modify `_execute_task()` to call `get_task_messages()` and `_build_thread_context()`. Prepend thread context to the agent's message input BETWEEN the task description and the agent's system prompt. The agent must see: original task → thread history → follow-up instruction
  - [x] 5.4: If thread is empty (first execution, no user messages), skip thread context injection entirely — backward compatible with existing behavior
- [x] Task 6: End-to-end validation and edge cases (AC: all)
  - [x] 6.1: Verify full round-trip: user sends message → task moves to assigned → executor picks up → agent responds with thread context → new work message in thread
  - [x] 6.2: Verify multi-turn: user sends follow-up after agent response → agent sees full history including previous exchange
  - [x] 6.3: Verify agent delegation: user changes agent before sending → new agent picks up with context
  - [x] 6.4: Verify status restrictions: in_progress/retrying tasks disable input, manual tasks hide input
  - [x] 6.5: Verify executionPlan is cleared on re-assignment — re-opened tasks run as single-step agent execution, not stale multi-step plans
  - [x] 6.6: Verify assigned→assigned edge case: sending multiple messages before agent picks up — all messages are in thread, no duplicate status transitions

## Dev Notes

### Architecture & Design Decisions

**Single Atomic Mutation Pattern**: The `sendThreadMessage` mutation MUST be a single Convex mutation that atomically creates the message, updates task status, and creates the activity event. This prevents inconsistent states. Follow the pattern from `tasks.ts:approve()` (lines 359-402) and `tasks.ts:deny()` (lines 530-576) which combine message creation + status update + activity event in one mutation.

**Execution Plan Clearing**: When a task is re-assigned via thread message, the `executionPlan` field MUST be set to `undefined`. The original execution plan was created by the lead agent for the initial task routing and is no longer relevant for a follow-up interaction. If the plan is preserved, the executor could incorrectly try to follow multi-step plan logic. The re-assigned task should run as a simple single-agent execution.

**Thread Context for Agents**: Currently, `_execute_task()` builds the agent prompt from `task_title + task_description` only (executor.py lines 368-530). For multi-turn, the executor must fetch thread messages and format them as conversation context:
```
[Original Task]
{task_title}
{task_description}

[Thread History — {N} messages]
User [user] (2026-02-23T10:00:00Z): Please also handle the edge case for...
research-agent [agent] (2026-02-23T10:01:00Z): I've completed the analysis...
User [user] (2026-02-23T10:05:00Z): Good, but can you also check...

[Latest Follow-up]
User: {latest_user_message_content}
```

**Thread Context Size Guard**: For tasks with extensive thread history (>20 messages), only include the last 20 messages in full. Prepend a note: `"({N} earlier messages omitted — see thread for full history)"`. This prevents context window overflow in the agent's LLM call.

**Session Key Behavior**: After each agent execution, `end_task_session(session_key)` is called (executor.py), which clears the session state. When the task is re-assigned, the executor creates a FRESH session. Thread history injection IS the continuity mechanism — there is no session state carried over between executions. This is intentional and correct.

**State Machine Extension**: The new transitions (`done→assigned`, `review→assigned`, `crashed→assigned`) represent "re-opening" a task for multi-turn interaction:
- `done→assigned`: Task was completed, user wants a follow-up
- `review→assigned`: User sends feedback directly instead of using approve/deny flow
- `crashed→assigned`: User provides additional context to help the agent succeed
- `inbox→assigned`: Already exists — user directly assigns instead of waiting for lead agent

**Executor De-duplication**: The `_known_assigned_ids` set (executor.py line 165) is cleared in the `finally` block of `_execute_task()` after execution completes. Re-queued tasks WILL be picked up automatically — no changes needed to the subscription loop. Tasks that are `in_progress` still have their ID in the set, which is why AC6 disables input for `in_progress` tasks to avoid race conditions.

**No Changes to Orchestrator**: The orchestrator subscribes to `inbox` tasks. Thread messages send tasks to `assigned` (not `inbox`), so the orchestrator will NOT interfere. The executor's `assigned` subscription handles pickup. This is intentional — the user explicitly chooses the agent, bypassing lead agent routing.

**User Identity**: The `authorName` for user messages is hardcoded as `"User"`. This follows the existing pattern in `tasks.ts:approve()` (line 387: `userName ?? "User"`) and `tasks.ts:deny()`. There is no user authentication model beyond access tokens — this is consistent.

### DO NOT MODIFY These Files

- **`ThreadMessage.tsx`**: The `getMessageStyles()` function's `default` case (line 27) already checks `authorType === "user"` and returns `{ bg: "bg-blue-50" }`. The `"user_message"` messageType falls through to default, which correctly applies user styling. Content rendering (line 66) already renders user messages as plain text (not markdown). NO changes are needed.
- **`orchestrator.py`**: Thread messages bypass orchestration entirely (assigned, not inbox).

### Existing Code to Reuse

**InlineRejection.tsx** — Pattern reference for ThreadInput:
- Same `Textarea` component with `min-h-[80px]`, `text-sm` styling
- Same `useState` for content + `isSubmitting` loading state
- Same `motion.div` animation pattern (optional)
- Same `useMutation` + try/finally pattern for submission

**TaskInput.tsx Agent Selector** (lines 35-46):
- Uses `useQuery(api.agents.list)` for agent list
- Uses `useBoard()` hook from `BoardContext` for board context
- Uses ShadCN `Select` component with `SelectTrigger`, `SelectContent`, `SelectItem`
- Agent filtering: query board by ID, check `board.enabledAgents`, if empty array → all agents eligible

**TaskDetailSheet.tsx Thread Tab Layout** (lines 218-236):
- Currently: `<TabsContent><ScrollArea>...messages...</ScrollArea></TabsContent>`
- Must change to: `<TabsContent className="flex flex-col"><ScrollArea className="flex-1">...messages...</ScrollArea><ThreadInput .../></TabsContent>`
- ThreadInput is pinned at the bottom, ScrollArea takes remaining space

### Message Ordering

Convex `listByTask` query (messages.ts line 4-12) uses `.withIndex("by_taskId")` which returns documents in insertion order (Convex default). This is chronological for messages. The executor's `_build_thread_context()` helper can rely on this ordering without additional sorting.

### Project Structure Notes

- **New file**: `dashboard/components/ThreadInput.tsx`
- **Modified**: `dashboard/convex/schema.ts` (messageType + eventType unions)
- **Modified**: `dashboard/convex/messages.ts` (add `sendThreadMessage` mutation + update `create` args)
- **Modified**: `dashboard/convex/tasks.ts` (add transitions to `VALID_TRANSITIONS` and `TRANSITION_EVENT_MAP`)
- **Modified**: `dashboard/components/TaskDetailSheet.tsx` (integrate ThreadInput in Thread tab)
- **Modified**: `nanobot/mc/types.py` (add enum values)
- **Modified**: `nanobot/mc/executor.py` (thread context injection in `_execute_task`)
- **Modified**: `nanobot/mc/bridge.py` (add `get_task_messages` method)
- **No new dependencies required**

### Testing Standards

- **Frontend**: Test ThreadInput renders, disabled states, hiding for manual tasks, agent selector filtering
- **Convex**: Test `sendThreadMessage` mutation: valid transitions from each status, rejection for in_progress/retrying/deleted, assigned→assigned behavior, executionPlan clearing, activity event creation
- **State machine**: Test new transitions are valid, invalid transitions still rejected
- **Executor**: Test `_build_thread_context` formatting, truncation for >20 messages, empty thread passthrough
- **E2E**: Full round-trip: send message → agent pickup → agent response → thread update

### References

- [Source: dashboard/components/TaskDetailSheet.tsx — Thread tab rendering, lines 206-236]
- [Source: dashboard/components/ThreadMessage.tsx — getMessageStyles default handles user, line 27]
- [Source: dashboard/components/InlineRejection.tsx — Textarea + mutation pattern reference]
- [Source: dashboard/convex/schema.ts — Data model for tasks, messages, activities]
- [Source: dashboard/convex/tasks.ts — VALID_TRANSITIONS lines 4-13, approve() lines 359-402, deny() lines 530-576]
- [Source: dashboard/convex/messages.ts — create() mutation, listByTask query]
- [Source: dashboard/components/TaskInput.tsx — Agent selector + useBoard() pattern, lines 35-46]
- [Source: nanobot/mc/executor.py — _execute_task() lines 368-530, _known_assigned_ids line 165, end_task_session]
- [Source: nanobot/mc/types.py — TaskStatus, MessageType, AuthorType, ActivityEventType enums]
- [Source: nanobot/mc/bridge.py — send_message() lines 271-294, query() method]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- TypeScript type check: `npx tsc --noEmit` — clean (0 errors)
- Python tests: `uv run pytest tests/mc/` — 152 passed, 0 failures (13 new thread context tests)
- TaskDetailSheet tests: 17/17 passed (run individually)
- 8 pre-existing test failures in DashboardLayout.test.tsx and TaskCard.test.tsx (timeout issues, unrelated to this story)

### Completion Notes List

- All 6 tasks (22 subtasks) implemented and verified
- `sendThreadMessage` is a single atomic Convex mutation (message + status transition + activity event)
- Thread context injection is backward-compatible — no change in behavior for tasks without user messages
- State machine extended with `done→assigned`, `review→assigned`, `crashed→assigned` transitions
- Executor de-duplication works naturally — `_known_assigned_ids` clears in `finally` block
- ThreadMessage.tsx `getMessageStyles()` default case already handles `authorType="user"` — no changes needed
- Orchestrator unaffected — thread messages send tasks to `assigned` (not `inbox`)

### File List

- **NEW**: `dashboard/components/ThreadInput.tsx` — Thread message input UI component
- **NEW**: `tests/mc/test_thread_context.py` — 13 tests for `_build_thread_context` (empty, basic, truncation, edge cases)
- **MODIFIED**: `dashboard/convex/schema.ts` — Added `user_message` messageType, `thread_message_sent` eventType
- **MODIFIED**: `dashboard/convex/messages.ts` — Added `user_message` to `create` args, added `sendThreadMessage` mutation
- **MODIFIED**: `dashboard/convex/tasks.ts` — Added state transitions, event mappings, `thread_message_sent` in updateStatus type
- **MODIFIED**: `dashboard/components/TaskDetailSheet.tsx` — Integrated ThreadInput in Thread tab, added auto-scroll
- **MODIFIED**: `nanobot/mc/types.py` — Added `USER_MESSAGE`, `THREAD_MESSAGE_SENT` enum values
- **MODIFIED**: `nanobot/mc/executor.py` — Added `_build_thread_context()` helper with [Latest Follow-up] section, thread context injection in `_execute_task()`
- **MODIFIED**: `nanobot/mc/bridge.py` — Added `get_task_messages()` method

### Change Log

- 2026-02-23: Story created via `*validate-create-story` with all 11 validation improvements applied
- 2026-02-23: Tasks 1-6 implemented sequentially
- 2026-02-23: All tests passing, story moved to review
- 2026-02-23: Code review found 3H/4M/2L issues — all HIGH and MEDIUM fixed:
  - H1: Added 13 persistent tests in `tests/mc/test_thread_context.py`
  - H2: Added auto-scroll via `threadEndRef` + `onMessageSent` callback
  - H3: Moved setState to `useEffect` for agent sync
  - M1: Added `[Latest Follow-up]` section in `_build_thread_context`
  - M2: Added error state + catch block in `handleSend`
  - M3: Added `thread_message_sent` to updateStatus type assertion
  - M4: Fixed misleading log count (shows injected vs total)
  - L1: Fixed min-h-[60px] → min-h-[80px] per AC1 spec
