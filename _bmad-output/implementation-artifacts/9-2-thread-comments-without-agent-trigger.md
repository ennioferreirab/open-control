# Story 9.2: Thread Comments Without Agent Trigger

Status: ready-for-dev

## Story

As a **user**,
I want to post comments in a task's thread that do not trigger agent assignment or status changes,
so that I can add context notes for humans and agents to read later.

## Acceptance Criteria

### AC1: Comment Message Type in Schema
**Given** the messages table schema in Convex
**When** the schema is updated
**Then** `"comment"` is added to both the `messageType` union and the `type` union on the messages table
**And** the `STRUCTURED_MESSAGE_TYPE` constant in `dashboard/lib/constants.ts` includes a `COMMENT` entry

### AC2: postComment Mutation
**Given** a task exists and is in any status except `"deleted"`
**When** `messages.postComment` is called with `{ taskId, content, authorName? }`
**Then** a message is created with `authorType: "user"`, `messageType: "comment"`, `type: "comment"`
**And** the task's `status` is NOT changed
**And** the task's `assignedAgent` is NOT changed
**And** the task's `executionPlan` is NOT cleared
**And** an activity event of type `"thread_message_sent"` is created with description `"User posted a comment"`
**And** if `authorName` is not provided, it defaults to `"User"`

### AC3: Comment Blocked in Deleted Status
**Given** a task has status `"deleted"`
**When** the user attempts to post a comment
**Then** a `ConvexError` is thrown: `"Cannot post comments on deleted tasks"`
**And** no message is created

### AC4: Toggle Between Message and Comment Modes in ThreadInput
**Given** the ThreadInput component is rendered for a non-manual, non-deleted task in a status that allows thread messages (not `in_progress`, not `review+awaitingKickoff`)
**When** the user sees the input area
**Then** a toggle pill with two options is visible: "Message Agent" (default) and "Comment"
**And** when "Message Agent" is selected, the existing agent selector and `sendThreadMessage` behavior is used
**And** when "Comment" is selected, the agent selector is hidden, the placeholder reads "Add a comment...", and submission calls `postComment`

### AC5: Comment Mode in In-Progress / Plan-Chat States
**Given** the task is in `in_progress` or `review+awaitingKickoff` (plan-chat mode)
**When** the ThreadInput renders
**Then** a toggle pill is shown: "Plan Chat" (default) and "Comment"
**And** "Plan Chat" preserves existing behavior (calls `postUserPlanMessage`)
**And** "Comment" mode hides the plan-chat helper text, shows "Add a comment..." placeholder, and calls `postComment`

### AC6: Visual Differentiation for Comments in Thread
**Given** a message in the thread has `type === "comment"`
**When** it is rendered by `ThreadMessage`
**Then** the message has a `bg-slate-50` background
**And** a `MessageCircle` icon is shown next to the author name
**And** a "Comment" label is displayed in `text-slate-500`
**And** the content renders as plain text (same as user messages, not Markdown)

### AC7: Backend Python Thread Context Formatting
**Given** the thread context builder processes messages for agent injection
**When** a message with `type === "comment"` is encountered
**Then** it is formatted as `"{author} [Comment]: {content}"`
**And** comments are included in the thread window like any other message (not filtered out)

## Tasks / Subtasks

- [ ] Task 1: Add `"comment"` to message schema unions (AC: #1)
  - [ ] 1.1: In `dashboard/convex/schema.ts`, add `v.literal("comment")` to the `messageType` union on the messages table (line 105-112). Add it after `"user_message"`:
    ```ts
    messageType: v.union(
      v.literal("work"),
      v.literal("review_feedback"),
      v.literal("approval"),
      v.literal("denial"),
      v.literal("system_event"),
      v.literal("user_message"),
      v.literal("comment"),
    ),
    ```
  - [ ] 1.2: Add `v.literal("comment")` to the `type` optional union (lines 113-119). Add after `"lead_agent_chat"`:
    ```ts
    type: v.optional(v.union(
      v.literal("step_completion"),
      v.literal("user_message"),
      v.literal("system_error"),
      v.literal("lead_agent_plan"),
      v.literal("lead_agent_chat"),
      v.literal("comment"),
    )),
    ```

- [ ] Task 2: Update message validators in `dashboard/convex/messages.ts` (AC: #1)
  - [ ] 2.1: Update the `threadMessageTypeValidator` (lines 6-12) to include `"comment"`:
    ```ts
    const threadMessageTypeValidator = v.optional(v.union(
      v.literal("step_completion"),
      v.literal("user_message"),
      v.literal("system_error"),
      v.literal("lead_agent_plan"),
      v.literal("lead_agent_chat"),
      v.literal("comment"),
    ));
    ```
  - [ ] 2.2: Update the `messageType` arg in the `create` mutation (lines 46-53) to include `"comment"`:
    ```ts
    messageType: v.union(
      v.literal("work"),
      v.literal("review_feedback"),
      v.literal("approval"),
      v.literal("denial"),
      v.literal("system_event"),
      v.literal("user_message"),
      v.literal("comment"),
    ),
    ```

- [ ] Task 3: Create `postComment` mutation in `dashboard/convex/messages.ts` (AC: #2, #3)
  - [ ] 3.1: Add the mutation after `postUserPlanMessage` (after line 238):
    ```ts
    /**
     * Post a comment to a task's thread.
     * Does NOT transition status, assign agent, or clear executionPlan.
     * Permitted in any status except "deleted".
     */
    export const postComment = mutation({
      args: {
        taskId: v.id("tasks"),
        content: v.string(),
        authorName: v.optional(v.string()),
      },
      handler: async (ctx, args) => {
        const task = await ctx.db.get(args.taskId);
        if (!task) {
          throw new ConvexError("Task not found");
        }
        if (task.status === "deleted") {
          throw new ConvexError("Cannot post comments on deleted tasks");
        }

        const timestamp = new Date().toISOString();
        const author = args.authorName?.trim() || "User";

        const messageId = await ctx.db.insert("messages", {
          taskId: args.taskId,
          authorName: author,
          authorType: "user",
          content: args.content,
          messageType: "comment",
          type: "comment",
          timestamp,
        });

        await ctx.db.insert("activities", {
          taskId: args.taskId,
          eventType: "thread_message_sent",
          description: "User posted a comment",
          timestamp,
        });

        return messageId;
      },
    });
    ```

- [ ] Task 4: Update `dashboard/lib/constants.ts` (AC: #1)
  - [ ] 4.1: Add `COMMENT: "comment"` to the `STRUCTURED_MESSAGE_TYPE` object (line 83-89):
    ```ts
    export const STRUCTURED_MESSAGE_TYPE = {
      STEP_COMPLETION: "step_completion",
      USER_MESSAGE: "user_message",
      SYSTEM_ERROR: "system_error",
      LEAD_AGENT_PLAN: "lead_agent_plan",
      LEAD_AGENT_CHAT: "lead_agent_chat",
      COMMENT: "comment",
    } as const;
    ```
  - [ ] 4.2: Add `COMMENT: "comment"` to the `MESSAGE_TYPE` object (line 74-80):
    ```ts
    export const MESSAGE_TYPE = {
      WORK: "work",
      REVIEW_FEEDBACK: "review_feedback",
      APPROVAL: "approval",
      DENIAL: "denial",
      SYSTEM_EVENT: "system_event",
      COMMENT: "comment",
    } as const;
    ```

- [ ] Task 5: Update `ThreadInput.tsx` to support Comment mode toggle (AC: #4, #5)
  - [ ] 5.1: Import `MessageCircle` from `lucide-react` and `useMutation` for `postComment`:
    ```ts
    const postComment = useMutation(api.messages.postComment);
    ```
  - [ ] 5.2: Add state for the input mode: `const [inputMode, setInputMode] = useState<"agent" | "comment">("agent");`
  - [ ] 5.3: Update `canSend` to allow sending in comment mode without an agent selected:
    ```ts
    const canSend = content.trim().length > 0 && !isSubmitting &&
      (inputMode === "comment" || isPlanChatMode || !!selectedAgent);
    ```
    But when in plan-chat mode, `inputMode` controls between "plan" and "comment", so the logic is:
    ```ts
    const effectiveMode = inputMode; // "agent" or "comment"
    const canSend = content.trim().length > 0 && !isSubmitting &&
      (effectiveMode === "comment" || isPlanChatMode && effectiveMode === "agent" || !!selectedAgent);
    ```
  - [ ] 5.4: Update `handleSend` to branch on `inputMode`:
    ```ts
    if (inputMode === "comment") {
      await postComment({ taskId: task._id, content: trimmed });
    } else if (isPlanChatMode) {
      await postPlanMessage({ taskId: task._id, content: trimmed });
    } else {
      await sendMessage({ taskId: task._id, content: trimmed, agentName: selectedAgent });
    }
    ```
  - [ ] 5.5: Create a reusable toggle pill component (inline or extracted) to render the mode selector. Place it above the textarea in both the standard and plan-chat rendering paths:
    ```tsx
    <div className="flex gap-1 rounded-full bg-muted p-0.5 w-fit">
      <button
        className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
          inputMode === "agent"
            ? "bg-background text-foreground shadow-sm"
            : "text-muted-foreground hover:text-foreground"
        }`}
        onClick={() => setInputMode("agent")}
      >
        {isPlanChatMode ? "Plan Chat" : "Message Agent"}
      </button>
      <button
        className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
          inputMode === "comment"
            ? "bg-background text-foreground shadow-sm"
            : "text-muted-foreground hover:text-foreground"
        }`}
        onClick={() => setInputMode("comment")}
      >
        <MessageCircle className="h-3 w-3 inline mr-1" />
        Comment
      </button>
    </div>
    ```
  - [ ] 5.6: When `inputMode === "comment"`:
    - Hide the agent `<Select>` (in standard mode) or the plan-chat helper text (in plan-chat mode)
    - Set textarea placeholder to `"Add a comment..."`
  - [ ] 5.7: When `inputMode === "agent"`, preserve existing behavior exactly as-is.
  - [ ] 5.8: Refactor the render to unify the plan-chat and standard paths since they now share the toggle pill and comment branch. The key difference: in plan-chat mode the "agent" option label is "Plan Chat" and calls `postPlanMessage`; in standard mode it's "Message Agent" and calls `sendThreadMessage`.

- [ ] Task 6: Update `ThreadMessage.tsx` for comment visual differentiation (AC: #6)
  - [ ] 6.1: Import `MessageCircle` from `lucide-react`
  - [ ] 6.2: Import `STRUCTURED_MESSAGE_TYPE` is already imported (line 8)
  - [ ] 6.3: Add a case in `getMessageStyles` for the `COMMENT` type (inside the `if (message.type)` block, after the `USER_MESSAGE` case):
    ```ts
    case STRUCTURED_MESSAGE_TYPE.COMMENT:
      return { bg: "bg-slate-50", label: "Comment", labelColor: "text-slate-500" };
    ```
  - [ ] 6.4: In the `ThreadMessage` component body, add a `isComment` flag:
    ```ts
    const isComment = message.type === STRUCTURED_MESSAGE_TYPE.COMMENT;
    ```
  - [ ] 6.5: In the header section (lines 92-107), add the MessageCircle icon when `isComment`:
    ```tsx
    {isComment && (
      <MessageCircle className="h-3.5 w-3.5 text-slate-500 shrink-0" />
    )}
    ```
    Place this after the `styles.label` span and before the `isSystemError` AlertTriangle icon.
  - [ ] 6.6: Comments should render as plain text (like user messages), not Markdown. The existing rendering logic at line 123-134 already handles this: when `message.authorType === "user"`, it renders as a `<p>` tag. Since `postComment` sets `authorType: "user"`, this is handled automatically.

- [ ] Task 7: Update Python `thread_context.py` for comment formatting (AC: #7)
  - [ ] 7.1: In `nanobot/mc/thread_context.py`, update the `_format_message` method (lines 175-192). Add a case for `type === "comment"` after the `step_completion` case:
    ```python
    def _format_message(self, message: dict[str, Any]) -> str:
        """Render a single message including artifacts if present."""
        author = message.get("author_name", "Unknown")
        author_type = message.get("author_type", "system")
        ts = message.get("timestamp", "")
        content = message.get("content", "")
        msg_type = message.get("type")

        if msg_type == "step_completion":
            line = f"{author} [{author_type}] ({ts}) [Step Completion]: {content}"
            artifacts = message.get("artifacts") or []
            if artifacts:
                artifact_str = self._format_artifacts(artifacts)
                if artifact_str:
                    line += "\n" + artifact_str
            return line
        elif msg_type == "comment":
            return f"{author} [Comment]: {content}"
        else:
            return f"{author} [{author_type}] ({ts}): {content}"
    ```
  - [ ] 7.2: Comments are NOT filtered out of the thread window. They appear in the 20-message truncation window like any other message, giving agents context about human notes.

- [ ] Task 8: Add tests (AC: #2, #3, #6, #7)
  - [ ] 8.1: Add Convex-level test or vitest test for `postComment`:
    - Verify message is created with correct fields
    - Verify task status is NOT changed after posting
    - Verify `ConvexError` thrown for deleted tasks
  - [ ] 8.2: Add Python test for `_format_message` with `type="comment"`:
    ```python
    def test_format_comment_message():
        builder = ThreadContextBuilder()
        msg = {"author_name": "Alice", "type": "comment", "content": "This needs review", "timestamp": "2026-01-01T00:00:00Z"}
        result = builder._format_message(msg)
        assert result == 'Alice [Comment]: This needs review'
    ```

## Dev Notes

### Architecture Patterns

- **No status transitions**: The core requirement is that `postComment` is a "safe" write operation. Unlike `sendThreadMessage` (which transitions to `assigned`, sets `assignedAgent`, and clears `executionPlan`), `postComment` only inserts a message row and an activity row. This makes it safe to use in ANY task status.
- **Dual-type fields**: The message uses both `messageType: "comment"` (legacy field for backward compatibility with existing queries) and `type: "comment"` (new structured type for rendering logic in `ThreadMessage`). This mirrors the pattern established in `postStepCompletion` (messages.ts line 95-96).
- **Activity event reuse**: Uses the existing `"thread_message_sent"` activity event type. No new event type needed.
- **Toggle pill pattern**: The toggle pill is a segmented control (not a dropdown) because there are only 2 options. It replaces the need for a separate "Comment" button or mode switch. The pill sits above the textarea, keeping the layout clean.

### Common Mistakes to Avoid

- Do NOT add `"comment"` to the `BLOCKED_STATUSES` array in `ThreadInput.tsx` (line 26). Comments should be postable in ANY status except deleted (which has its own render path).
- Do NOT transition task status in `postComment`. The entire point is that comments are inert.
- Do NOT filter comments out of the thread context in Python. Agents should see human comments as context.
- When updating the `messageType` union in `schema.ts`, also update the `create` mutation's `messageType` arg in `messages.ts` -- they must stay in sync.
- The `threadMessageTypeValidator` in `messages.ts` must also be updated -- it's used by the `create` mutation and other mutations that accept the `type` field.

### Project Structure Notes

- Modified files (frontend): `dashboard/convex/schema.ts`, `dashboard/convex/messages.ts`, `dashboard/lib/constants.ts`, `dashboard/components/ThreadInput.tsx`, `dashboard/components/ThreadMessage.tsx`
- Modified files (backend): `nanobot/mc/thread_context.py`
- No new files except tests

### References

- [Source: dashboard/convex/schema.ts:95-131] -- messages table definition (add "comment" to unions)
- [Source: dashboard/convex/messages.ts:6-12] -- threadMessageTypeValidator (add "comment")
- [Source: dashboard/convex/messages.ts:36-73] -- create mutation messageType arg (add "comment")
- [Source: dashboard/convex/messages.ts:196-238] -- postUserPlanMessage pattern (model for postComment, similar "no status change" semantics)
- [Source: dashboard/convex/messages.ts:245-314] -- sendThreadMessage (the mutation that DOES transition status -- postComment must NOT do this)
- [Source: dashboard/components/ThreadInput.tsx:28-227] -- full ThreadInput component (add toggle pill, comment mode)
- [Source: dashboard/components/ThreadMessage.tsx:44-62] -- getMessageStyles function (add COMMENT case)
- [Source: dashboard/lib/constants.ts:74-89] -- MESSAGE_TYPE and STRUCTURED_MESSAGE_TYPE (add COMMENT)
- [Source: nanobot/mc/thread_context.py:175-192] -- _format_message method (add comment case)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
