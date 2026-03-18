# Story 13.1: Decouple @Mention Messages from Status Transition

Status: review

## Story

As a **user**,
I want to @mention an agent in a task thread without the task automatically changing status,
so that I can ask for opinions or start discussions without triggering a full task re-execution.

## Acceptance Criteria

### AC1: New Convex Mutation `postMentionMessage`

**Given** a task in any status except `deleted`
**When** the user sends a message containing `@agentname`
**Then** a new `postMentionMessage` mutation creates the user message in the thread
**And** the task status is NOT changed (remains in its current status)
**And** the `executionPlan` is NOT cleared
**And** the `assignedAgent` is NOT modified
**And** an activity event `thread_message_sent` is created with description "User mentioned @{agentName}"

### AC2: No Status Blockers for Mentions

**Given** a task in status `in_progress`, `review`, `done`, `crashed`, `inbox`, `assigned`, or `retrying`
**When** the user sends a @mention message via `postMentionMessage`
**Then** the message is accepted and inserted into the thread
**And** no `ConvexError` is thrown for any non-deleted status

### AC3: Frontend Uses `postMentionMessage` for @Mentions

**Given** the user types a message containing `@agentname` in the ThreadInput
**When** the user submits the message
**Then** the frontend calls `postMentionMessage` (not `sendThreadMessage`)
**And** the `@agentname` text remains visible in the message content
**And** the task card does NOT move to a different kanban column

### AC4: Explicit Status Transition Remains via `sendThreadMessage`

**Given** the user types a message WITHOUT `@agentname` and selects an agent from the dropdown
**When** the user submits the message
**Then** the frontend calls `sendThreadMessage` as before (transitions to `assigned`)
**And** existing behavior is fully preserved for non-mention messages

### AC5: Plan-Chat Mode Unchanged

**Given** a task in `in_progress` or `review` with `awaitingKickoff`
**When** the user sends a message via the plan-chat textarea
**Then** `postUserPlanMessage` is still used (no change to plan-chat flow)
**And** @mentions in plan-chat are handled by the PlanNegotiator as before

## Tasks / Subtasks

- [x] Task 1: Create `postMentionMessage` mutation in Convex (AC: 1, 2)
  - [x] 1.1: In `dashboard/convex/messages.ts`, add new mutation `postMentionMessage` with args: `taskId: v.id("tasks")`, `content: v.string()`, `mentionedAgent: v.optional(v.string())`. Handler: validate task exists, reject `deleted` status only, insert message with `authorName: "User"`, `authorType: "user"`, `messageType: "user_message"`, `type: "user_message"`. Do NOT patch task status, assignedAgent, or executionPlan.
  - [x] 1.2: Create activity event with `eventType: "thread_message_sent"`, description includes mentioned agent name if provided.
  - [x] 1.3: Return the message ID from the mutation.

- [x] Task 2: Update ThreadInput to route @mention messages (AC: 3, 4)
  - [x] 2.1: In `dashboard/components/ThreadInput.tsx`, in the `handleSend` function, detect if the message content contains a valid `@agentname` pattern (reuse the existing regex `/@(\w[\w-]*)(?:\s|$)/`).
  - [x] 2.2: If @mention detected: call `postMentionMessage({ taskId, content, mentionedAgent })` instead of `sendThreadMessage`. Pass the first mentioned agent name as `mentionedAgent`.
  - [x] 2.3: If no @mention detected: call `sendThreadMessage` as before (preserving existing dropdown-based agent selection and status transition).
  - [x] 2.4: Clear the textarea and reset state after successful submission in both paths.

- [x] Task 3: Validation and edge cases (AC: 1, 2, 5)
  - [x] 3.1: Verify `postMentionMessage` works on all statuses: `inbox`, `assigned`, `in_progress`, `review`, `done`, `crashed`, `retrying`. Write a Convex test or manual verification for each.
  - [x] 3.2: Verify `postMentionMessage` rejects `deleted` tasks with `ConvexError`.
  - [x] 3.3: Verify plan-chat mode continues using `postUserPlanMessage` — the @mention routing only applies to the main thread textarea, not the plan-chat textarea.

## Dev Notes

### Architecture & Design Decisions

**Why a new mutation instead of modifying `sendThreadMessage`?** The existing `sendThreadMessage` has a clear contract: it transitions the task to `assigned` and clears the execution plan. This is the correct behavior for "user sends a follow-up that should restart agent work." Adding a flag like `noStatusChange` would make the contract ambiguous. A separate mutation has a clean, distinct contract: "post a message for @mention handling without affecting task state."

**Frontend routing logic:** The decision of which mutation to call happens in `handleSend` based on content analysis. This is simple and predictable: if the message has `@agentname`, it's a mention (no status change); if it doesn't, it's a follow-up (status change to assigned). The user always has a clear mental model.

**Why not use `postComment`?** Comments use `messageType: "comment"` which the MentionWatcher ignores (it only processes `user_message` type). We need the message to be a proper `user_message` so the MentionWatcher detects and handles the @mention.

### Existing Code to Reuse

**`dashboard/convex/messages.ts`** (lines 292-361):
- `sendThreadMessage` — reference for message creation pattern
- `postComment` (lines 247-285) — reference for status-inert mutation pattern
- `postUserPlanMessage` (lines 198-240) — another status-inert pattern

**`dashboard/components/ThreadInput.tsx`**:
- `handleSend` — the submission handler to modify
- `selectedAgent` state — still used for dropdown-based submissions
- `isPlanChatMode` guard — must not affect plan-chat path

### Common Mistakes to Avoid

1. **Do NOT modify `sendThreadMessage`** — it must keep its existing contract for non-mention messages.
2. **Do NOT change `postComment` to handle mentions** — comments have a different `messageType` that the watcher ignores.
3. **Do NOT remove the dropdown agent selector** — it coexists with @mentions for explicit status-changing submissions.
4. **Do NOT use `postMentionMessage` for plan-chat** — plan-chat always goes through `postUserPlanMessage`.
5. **Do NOT add @mention detection to the Convex mutation** — the backend just stores the message; @mention detection is the MentionWatcher's responsibility.

### Project Structure Notes

- **MODIFIED**: `dashboard/convex/messages.ts` — add `postMentionMessage` mutation
- **MODIFIED**: `dashboard/components/ThreadInput.tsx` — route @mention messages to new mutation
- No Python backend changes in this story
- No new files created

### References

- [Source: dashboard/convex/messages.ts#sendThreadMessage — lines 287-361, current status-transitioning mutation]
- [Source: dashboard/convex/messages.ts#postComment — lines 247-285, status-inert mutation reference]
- [Source: dashboard/convex/messages.ts#postUserPlanMessage — lines 198-240, plan-chat mutation]
- [Source: dashboard/components/ThreadInput.tsx — main thread input component]
- [Source: mc/mentions/watcher.py — MentionWatcher only processes `user_message` authorType]

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
N/A

### Completion Notes List
- Created `postMentionMessage` mutation in `dashboard/convex/messages.ts` that inserts a user_message without modifying task status, assignedAgent, or executionPlan. Only rejects `deleted` tasks. Creates activity event with "User mentioned @{agentName}" description.
- Updated `handleSend` in `dashboard/components/ThreadInput.tsx` to detect @mentions matching known agents and route those messages to `postMentionMessage` instead of `sendThreadMessage`. Plan-chat and in-progress reply paths are unaffected.
- Created 12 unit tests in `dashboard/convex/messages.test.ts` covering: message insertion, activity event creation, no task patch, all 7 allowed statuses, deleted rejection, mentionedAgent description logic, and message ID return.
- Created 8 unit tests in `dashboard/components/ThreadInput.test.tsx` covering: @mention routing to postMentionMessage, non-mention routing to sendThreadMessage, textarea clearing, plan-chat mode bypass, unknown agent fallback, deleted task UI, and manual task rendering.
- All 20 new tests pass. No regressions in existing test suites (pre-existing failures in unrelated components confirmed unchanged).

### File List
- `dashboard/convex/messages.ts` — MODIFIED: added `postMentionMessage` mutation
- `dashboard/components/ThreadInput.tsx` — MODIFIED: added @mention routing in `handleSend`
- `dashboard/convex/messages.test.ts` — NEW: 12 unit tests for postMentionMessage
- `dashboard/components/ThreadInput.test.tsx` — NEW: 8 unit tests for @mention routing
- `_bmad-output/implementation-artifacts/13-1-decouple-mention-from-status-transition.md` — MODIFIED: updated status and dev agent record

### Change Log
- 2026-03-05: Implemented Story 13.1 — Decouple @Mention Messages from Status Transition. Added `postMentionMessage` Convex mutation and frontend routing logic with full test coverage.
