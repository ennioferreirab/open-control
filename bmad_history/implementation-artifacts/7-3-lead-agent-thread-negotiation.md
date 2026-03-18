# Story 7.3: Lead Agent Plan Negotiation via Main Thread

Status: done

## Story

As a **user**,
I want to send messages in the task thread to ask the Lead Agent to modify the execution plan,
So that I can collaborate on the plan through natural conversation — both before kick-off (during Review) and during execution (for not-yet-started steps).

## Context

Previously (Epic 4 stories 4.5/4.6), the Lead Agent chat happened in a **separate `PlanChatPanel`** inside the `PreKickoffModal`. With the new design (Story 7.1), the modal is removed. The thread IS the conversation.

**Key design decisions confirmed with user:**
- Messages in the task's main thread can be directed at the Lead Agent
- The Lead Agent responds to thread messages during **both** `review` (pre-kickoff) **and** `in_progress` (execution) statuses
- During execution, the Lead Agent can only modify steps that have NOT started (`pending`/`blocked` status)
- The Lead Agent updates the `executionPlan` on the task record; the canvas auto-refreshes via `syncKey` pattern
- The existing `postPlanChatMessage` Convex mutation and `plan_negotiator.py` module are repurposed for this
- The Python subscription loop should listen for user thread messages on tasks in `review` (awaitingKickoff) OR `in_progress` status

## Acceptance Criteria

1. **User thread messages reach Lead Agent during review** -- Given a task is in `review` status with `awaitingKickoff: true`, when the user sends a message in the Thread tab (via the existing `ThreadInput`), then the Python `plan_negotiator.py` receives the message, interprets it, and responds with either an updated plan or a clarification — both appearing in the thread.

2. **User thread messages reach Lead Agent during execution** -- Given a task is in `in_progress` status, when the user sends a message in the thread, then the Lead Agent processes the request and can modify steps that are in `pending` or `blocked` status (not yet started), while preserving steps in `assigned`, `running`, or `completed` status.

3. **Lead Agent response appears in thread** -- Given the Lead Agent processes a user request, when it generates a response, then the response appears in the task thread as a `lead_agent_chat` message, rendered with the Lead Agent's visual style (indigo background, bot icon), visible in the Thread tab.

4. **Plan canvas updates automatically** -- Given the Lead Agent calls `bridge.update_execution_plan()` in response to a thread message, when the Convex task record's `executionPlan` field updates, then the `ExecutionPlanTab` canvas auto-refreshes (via the `syncKey` / `generatedAt` change) without a page reload.

5. **During execution: Lead Agent cannot modify started steps** -- Given the task is `in_progress` and step A is `running`, when the user asks "Cancel step A", then the Lead Agent responds explaining it cannot modify steps already in progress, and the plan is NOT updated for those steps.

6. **Lead Agent subscription covers review + in_progress** -- Given the Python orchestrator is running, when a task is in `review` (awaitingKickoff) or `in_progress` status, then the `plan_negotiation_loop` is actively listening for new user thread messages on that task.

7. **Existing thread messages are NOT all sent to Lead Agent** -- Given the thread contains step completion messages, system errors, and other non-user messages, when the plan negotiator processes the thread, then it only processes messages where `authorType: "user"` (not agent completions or system messages).

8. **The `postPlanChatMessage` Convex mutation is replaced by standard thread posting** -- Given the old `postPlanChatMessage` mutation existed separately, when this story is implemented, then user thread messages posted via the standard `sendThreadMessage` mutation (or existing ThreadInput) are what the Lead Agent listens to — no separate mutation needed for plan chat.

9. **Lead Agent plan modification during execution respects already-dispatched steps** -- Given the Lead Agent generates an updated plan, when steps are already materialized (exist in the `steps` table), then the Lead Agent's response explains which changes it CAN make (pending steps) and which it CANNOT (running/completed), and only updates the `executionPlan` record for the pending steps portion.

## Tasks / Subtasks

- [x] **Task 1: Extend plan_negotiator subscription to cover `in_progress` tasks** (AC: 1, 2, 6)
  - [x] 1.1 Read `nanobot/mc/plan_negotiator.py` fully to understand current implementation.
  - [x] 1.2 The current `start_plan_negotiation_loop()` only handles tasks in `reviewing_plan` (old status). Update it to handle tasks in:
    - `review` with `awaitingKickoff: true` (pre-kickoff)
    - `in_progress` (during execution — for not-yet-started steps)
  - [x] 1.3 The subscription should listen on `messages:listByTask` (all user messages in the task thread), filtering by `authorType: "user"` to avoid reacting to agent messages.
  - [x] 1.4 Track `last_seen_message_id` per task to avoid re-processing old messages when the subscription fires.

- [x] **Task 2: Update plan negotiation handler for execution context** (AC: 2, 5, 9)
  - [x] 2.1 In `handle_plan_negotiation()`, add context about the current execution state:
    - Fetch current steps from `bridge.get_steps_by_task(task_id)`
    - Pass step statuses to the LLM system prompt: which steps are `pending`/`blocked` (modifiable) vs `assigned`/`running`/`completed` (locked)
  - [x] 2.2 Update the LLM system prompt to include: "During execution, you can ONLY modify steps in 'pending' or 'blocked' status. Steps in 'assigned', 'running', or 'completed' status cannot be changed."
  - [x] 2.3 When the LLM returns an `update_plan` action during execution: only apply changes to modifiable steps; leave locked steps untouched.
  - [x] 2.4 When the user requests a change to a locked step: respond with a `clarify` action explaining the constraint.

- [x] **Task 3: Lead Agent response posts to main thread** (AC: 3)
  - [x] 3.1 The existing `bridge.post_lead_agent_message(task_id, content, "lead_agent_chat")` already posts to the main thread. Verify this is what the plan negotiator uses.
  - [x] 3.2 Verify `ThreadMessage.tsx` already renders `lead_agent_chat` messages with the Lead Agent style (indigo background, "Lead Agent" label). If not, add the rendering.
  - [x] 3.3 In `TaskDetailSheet.tsx`, ensure the Thread tab shows ALL message types including `lead_agent_chat` (currently the `listByTask` query returns all messages — verify no filter is hiding them).

- [x] **Task 4: Wire plan negotiation loop into orchestrator gateway** (AC: 6)
  - [x] 4.1 In `nanobot/mc/orchestrator.py` or `nanobot/mc/gateway.py`, start the plan negotiation subscription for tasks as they enter `review` (awaitingKickoff) or `in_progress` status.
  - [x] 4.2 Current pattern: `start_routing_loop()`, `start_review_routing_loop()`, `start_kickoff_watch_loop()` run as separate `asyncio.create_task()` loops.
  - [x] 4.3 Add `start_plan_negotiation_loop()` as a gateway-level task. OR (better) integrate it into the routing loop so that when a task enters `review`/`in_progress`, a per-task negotiation loop is spawned and cancelled when the task leaves that status.
  - [x] 4.4 Prevent duplicate negotiation loops for the same task if the status subscription fires multiple times.

- [x] **Task 5: Remove `postPlanChatMessage` and `listPlanChat` Convex artifacts** (AC: 8)
  - [x] 5.1 In `dashboard/convex/messages.ts`, check if `postPlanChatMessage` and `listPlanChat` are still used anywhere after Story 7.1 (PreKickoffModal removed). If not used, delete them.
  - [x] 5.2 The Python `plan_negotiator.py` was using `messages:listPlanChat` for its subscription. Update it to use `messages:listByTask` (filtering by `authorType: "user"` in Python).
  - [x] 5.3 The `LEAD_AGENT_CHAT` message type constant in `dashboard/lib/constants.ts` should be preserved — it's still used for Lead Agent responses in the main thread.

- [x] **Task 6: Write tests** (AC: 1-9)
  - [x] 6.1 **Python test:** `test_plan_negotiator.py` — test that handler fetches step statuses when task is `in_progress` and includes them in the LLM prompt.
  - [x] 6.2 **Python test:** `test_plan_negotiator.py` — test that a request to modify a `running` step results in a `clarify` action, not `update_plan`.
  - [x] 6.3 **Python test:** `test_plan_negotiator.py` — test that handler processes `in_progress` task messages (not just `review`).
  - [x] 6.4 **Dashboard test:** `ThreadMessage.test.tsx` — test that `lead_agent_chat` messages render with indigo background and "Lead Agent" label.

## Dev Notes

### Relationship to Existing Code

**plan_negotiator.py** (already exists):
- `handle_plan_negotiation(bridge, task_id, user_message, current_plan)` — calls LLM, handles `update_plan` / `clarify`
- `start_plan_negotiation_loop()` — subscription loop that watches for user messages
- Currently scoped to `reviewing_plan` status — needs to extend to `review` (new status name) + `in_progress`

**bridge.post_lead_agent_message(task_id, content, "lead_agent_chat")** — posts Lead Agent response to thread. Already implemented.

**bridge.update_execution_plan(task_id, plan.to_dict())** — writes updated plan to Convex. Already implemented.

**ThreadMessage.tsx** — already handles `lead_agent_chat` type (Epic 4, Story 4.5). Renders in indigo style.

### Thread Message Filtering in Python

The negotiation loop must only react to user messages, not Loop endlessly on its own responses:

```python
# Only process user messages
messages = await bridge.get_task_messages(task_id)
user_messages = [m for m in messages if m.get("author_type") == "user"]

# Track last seen to avoid reprocessing
new_messages = [m for m in user_messages if m["id"] > last_seen_id]
```

### LLM Prompt Additions for Execution Context

Add to the NEGOTIATION_SYSTEM_PROMPT when task is `in_progress`:

```
Current execution state:
- Steps in 'pending' or 'blocked' status: {list} — CAN be modified
- Steps in 'assigned', 'running', or 'completed' status: {list} — LOCKED, cannot be modified

If the user asks to modify a locked step, respond with action=clarify and explain why you cannot.
```

### Plan Update During Execution

When the Lead Agent returns `update_plan` during execution:
1. Fetch current materialized steps from bridge
2. For each updated step in the plan: if the step maps to a materialized step in `pending`/`blocked` → update the materialized step record too (title, description, assignedAgent)
3. If the updated step maps to a `running`/`completed` step → skip that step's changes
4. Always update `task.executionPlan` with the full updated plan (for canvas display)

This may require a new bridge method or Convex mutation to update individual pending steps' metadata.

### Common LLM Developer Mistakes to Avoid

1. **DO NOT create a new subscription system** — the existing `bridge.async_subscribe()` pattern is the right approach. Extend `start_plan_negotiation_loop()` to handle both statuses.

2. **DO NOT react to Lead Agent's own messages** — filter by `authorType == "user"` only. The loop will see its own responses and must not re-process them.

3. **DO NOT block the Python event loop** — use `asyncio.to_thread()` for bridge calls and `asyncio.create_task()` for fire-and-forget.

4. **DO NOT update `executionPlan` AND individual materialized steps atomically** — if updating materialized steps, do it as a separate operation after the plan update. Convex mutations are atomic per mutation, not across mutations.

5. **DO NOT remove `LEAD_AGENT_CHAT` constant or the thread rendering** — Lead Agent responses still use this type, and the thread renders them correctly.

### What This Story Does NOT Include

- Pause/Resume (Story 7.4)
- Human step Accept button (Story 7.2)
- Canvas editing (Story 7.1)

### Files to Modify

- `nanobot/mc/plan_negotiator.py` — extend to `review` + `in_progress`, add execution-state context and enforcement
- `nanobot/mc/gateway.py` — wire updated negotiation loop (plan negotiation manager)
- `nanobot/mc/test_plan_negotiator.py` — Python tests for Story 7.3 additions
- `dashboard/convex/messages.ts` — add `postUserPlanMessage` mutation; `postPlanChatMessage`/`listPlanChat` removed
- `dashboard/components/TaskDetailSheet.tsx` — verify thread shows `lead_agent_chat` messages
- `dashboard/components/ThreadMessage.tsx` — fix Lead Agent messages to render as Markdown (not italic)
- `dashboard/components/ThreadInput.tsx` — add plan-chat mode for `in_progress`/`review+awaitingKickoff` tasks
- `dashboard/components/ThreadMessage.test.tsx` — new test file for `lead_agent_chat` rendering

### References

- [Source: `nanobot/mc/plan_negotiator.py`] — existing negotiation handler
- [Source: `nanobot/mc/bridge.py#post_lead_agent_message`] — Lead Agent thread posting
- [Source: `nanobot/mc/bridge.py#update_execution_plan`] — plan update method
- [Source: `dashboard/convex/messages.ts`] — existing message mutations
- [Source: `dashboard/components/ThreadMessage.tsx`] — `lead_agent_chat` rendering
- [Story 7.1] — canvas syncKey pattern (auto-refresh when plan updates)

## Dev Agent Record

### Code Review Fixes Applied (2026-02-25)

- **[H1] Fixed `MODIFIABLE_STEP_STATUSES`**: Removed non-existent `"pending"` status, kept `"planned"` and `"blocked"` (the actual Convex schema values). Updated `EXECUTION_CONTEXT_PROMPT` text to say "planned or blocked" instead of "pending or blocked". Updated test fixture `RUNNING_STEPS` to use `"planned"` for the un-started step.
- **[H2] Fixed seen-IDs pruning race**: Moved the `seen_message_ids` prune logic to AFTER the per-message processing loop to prevent new user messages in the current batch from being skipped when a prune triggers in the same iteration.
- **[M1] Fixed weak test assertion**: `test_loop_continues_for_in_progress_task` had `assert call_args[1]["task_status"] == "in_progress" or (len(call_args[0]) > 0)` — the right-hand side was always True (positional args always present), making the assertion vacuous. Fixed to `assert call_args[1]["task_status"] == "in_progress"`.
- **[M2] Fixed `LOCKED_STEP_STATUSES`**: Added `"waiting_human"` and `"crashed"` to the locked set. Steps in these states cannot be safely modified mid-execution. The enforcement veto now correctly blocks LLM from modifying these states.
