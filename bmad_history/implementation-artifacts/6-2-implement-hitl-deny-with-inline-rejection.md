# Story 6.2: Implement HITL Deny with Inline Rejection

Status: done

## Story

As a **user**,
I want to deny a task with feedback explaining what needs to change,
So that agents receive actionable context for revision.

## Acceptance Criteria

1. **Given** a task is in "review" state requiring human approval, **When** the user clicks the "Deny" button on the TaskCard or TaskDetailSheet, **Then** an inline textarea expands smoothly below the button (150ms expand animation via Framer Motion)
2. **Given** the inline textarea is expanded, **Then** the textarea receives focus automatically
3. **Given** the user types rejection feedback and clicks "Submit", **When** the denial is processed, **Then** a message is created with messageType "denial", authorType "user", and the feedback text as content
4. **Given** the denial is processed, **Then** the task remains in "review" state and stays actionable (FR33)
5. **Given** the denial succeeds, **Then** a `hitl_denied` activity event is created with description: "User denied '{task title}': {feedback preview}"
6. **Given** the textarea is submitted, **Then** it collapses (150ms) and the new denial message appears in the task thread
7. **Given** the user denies a task, **When** the inline rejection form is visible, **Then** a secondary button "Return to Lead Agent" is available below the textarea
8. **Given** the user clicks "Return to Lead Agent", **Then** the task is re-routed: status resets to "inbox" with full thread history + user comment, so the Lead Agent can re-plan or re-assign
9. **And** the `InlineRejection.tsx` component is created with ShadCN `Textarea` + `Button` + Framer Motion expand animation
10. **And** a Convex mutation `tasks:deny` is created
11. **And** Vitest tests exist for `InlineRejection.tsx`

## Tasks / Subtasks

- [ ] Task 1: Create the `tasks:deny` Convex mutation (AC: #3, #4, #5, #10)
  - [ ] 1.1: Add a `deny` mutation to `dashboard/convex/tasks.ts`
  - [ ] 1.2: Args: `taskId: v.id("tasks")`, `feedback: v.string()`, `userName: v.optional(v.string())`
  - [ ] 1.3: Validate the task exists and is in "review" status
  - [ ] 1.4: Do NOT change the task status — it stays in "review" (FR33)
  - [ ] 1.5: Insert a `hitl_denied` activity event with feedback preview (first 100 chars)
  - [ ] 1.6: Insert a message with messageType "denial", authorType "user", content = feedback

- [ ] Task 2: Create the `tasks:returnToLeadAgent` Convex mutation (AC: #8)
  - [ ] 2.1: Add a `returnToLeadAgent` mutation to `dashboard/convex/tasks.ts`
  - [ ] 2.2: Args: `taskId: v.id("tasks")`, `feedback: v.string()`, `userName: v.optional(v.string())`
  - [ ] 2.3: Reset task status to "inbox", clear `assignedAgent`
  - [ ] 2.4: Insert a denial message with the user's feedback
  - [ ] 2.5: Insert a system message: "Task returned to Lead Agent for re-routing"
  - [ ] 2.6: Insert a `task_retrying` activity event (reuse event type for re-routing)
  - [ ] 2.7: The Lead Agent routing loop (Story 4.1) will pick up the task from inbox with full thread context

- [ ] Task 3: Create the InlineRejection component (AC: #1, #2, #6, #7, #9)
  - [ ] 3.1: Create `dashboard/components/InlineRejection.tsx` with `"use client"` directive
  - [ ] 3.2: Accept props: `taskId: Id<"tasks">`, `onClose: () => void`
  - [ ] 3.3: Render a Framer Motion animated container that expands from height 0 to auto (150ms)
  - [ ] 3.4: Inside: ShadCN `Textarea` (placeholder: "Explain what needs to change..."), `Button` "Submit", and secondary `Button` "Return to Lead Agent"
  - [ ] 3.5: Auto-focus the textarea on mount using `useRef` + `useEffect`
  - [ ] 3.6: On "Submit" click: call `denyMutation({ taskId, feedback })`, then collapse animation, then call `onClose`
  - [ ] 3.7: On "Return to Lead Agent" click: call `returnToLeadAgentMutation({ taskId, feedback })`, then collapse, then call `onClose`
  - [ ] 3.8: Disable buttons while submitting
  - [ ] 3.9: Validate that feedback is not empty before allowing submit

- [ ] Task 4: Add Deny button to TaskCard (AC: #1)
  - [ ] 4.1: Update `dashboard/components/TaskCard.tsx`
  - [ ] 4.2: Add a red "Deny" button next to the Approve button (same visibility condition: `status === "review"` AND `trustLevel === "human_approved"`)
  - [ ] 4.3: Button styling: ShadCN `Button` with `variant="destructive"` and `text-xs h-7`
  - [ ] 4.4: On click: toggle `showRejection` state, render `InlineRejection` below the card
  - [ ] 4.5: Use `e.stopPropagation()` to prevent opening TaskDetailSheet

- [ ] Task 5: Add Deny button to TaskDetailSheet (AC: #1)
  - [ ] 5.1: Update `dashboard/components/TaskDetailSheet.tsx`
  - [ ] 5.2: Add a Deny button next to the Approve button in the sheet header
  - [ ] 5.3: On click: toggle inline rejection form below the header
  - [ ] 5.4: The rejection form uses the same `InlineRejection` component

- [ ] Task 6: Write Vitest tests (AC: #11)
  - [ ] 6.1: Create `dashboard/components/InlineRejection.test.tsx`
  - [ ] 6.2: Test textarea renders and receives focus on mount
  - [ ] 6.3: Test Submit button is disabled when textarea is empty
  - [ ] 6.4: Test Submit calls deny mutation with correct feedback
  - [ ] 6.5: Test "Return to Lead Agent" button is visible
  - [ ] 6.6: Test component collapses after submission

## Dev Notes

### Critical Architecture Requirements

- **Task stays in "review" after denial**: FR33 is explicit — denied tasks remain actionable. The task stays in "review" so the assigned agent can address the feedback. This is different from "Return to Lead Agent" which resets to inbox.
- **Two denial paths**: (1) "Submit" keeps the task in review for the current agent to revise. (2) "Return to Lead Agent" resets to inbox for re-routing.
- **Inline UI, not modal**: The rejection form expands inline on the card or sheet. No modal dialogs.
- **Thread preserves full context**: When "Return to Lead Agent" is used, all thread messages (including the denial) stay on the task. The Lead Agent sees the full history when re-routing.

### InlineRejection Component Pattern

```tsx
"use client";

import { useState, useRef, useEffect } from "react";
import { useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import { Id } from "../convex/_generated/dataModel";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import * as motion from "motion/react-client";

interface InlineRejectionProps {
  taskId: Id<"tasks">;
  onClose: () => void;
}

export function InlineRejection({ taskId, onClose }: InlineRejectionProps) {
  const [feedback, setFeedback] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const denyMutation = useMutation(api.tasks.deny);
  const returnMutation = useMutation(api.tasks.returnToLeadAgent);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  const handleDeny = async () => {
    if (!feedback.trim()) return;
    setIsSubmitting(true);
    await denyMutation({ taskId, feedback: feedback.trim() });
    setIsSubmitting(false);
    onClose();
  };

  const handleReturn = async () => {
    if (!feedback.trim()) return;
    setIsSubmitting(true);
    await returnMutation({ taskId, feedback: feedback.trim() });
    setIsSubmitting(false);
    onClose();
  };

  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: "auto", opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      transition={{ duration: 0.15 }}
      className="overflow-hidden"
    >
      <div className="pt-2 space-y-2">
        <Textarea
          ref={textareaRef}
          placeholder="Explain what needs to change..."
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          className="text-sm min-h-[80px]"
          disabled={isSubmitting}
        />
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="destructive"
            className="text-xs h-7"
            onClick={handleDeny}
            disabled={isSubmitting || !feedback.trim()}
          >
            Submit
          </Button>
          <Button
            size="sm"
            variant="secondary"
            className="text-xs h-7"
            onClick={handleReturn}
            disabled={isSubmitting || !feedback.trim()}
          >
            Return to Lead Agent
          </Button>
        </div>
      </div>
    </motion.div>
  );
}
```

### State Machine Extension

The "Return to Lead Agent" action needs `review -> inbox` transition. This is NOT currently in the state machine. Add it:

**Convex side (`tasks.ts`):**
The `returnToLeadAgent` mutation directly patches the status — it can bypass the `updateStatus` mutation validation since it's a specific user action, OR add `"inbox"` to the allowed transitions from "review".

**Python side (`state_machine.py`):**
Add `TaskStatus.REVIEW: [TaskStatus.DONE, TaskStatus.INBOX]` to allow the return-to-inbox path.

### Common LLM Developer Mistakes to Avoid

1. **DO NOT change task status on deny** — FR33: denied task stays in "review". Only "Return to Lead Agent" changes status to "inbox".

2. **DO NOT use a modal for rejection** — The UX spec says inline expansion. The textarea expands below the deny button.

3. **DO NOT allow empty feedback** — The Submit button should be disabled when the textarea is empty. Feedback is required for both deny and return actions.

4. **DO NOT forget to stop event propagation** — The Deny button on TaskCard must not trigger the card's onClick (which opens TaskDetailSheet).

5. **DO NOT clear the thread on "Return to Lead Agent"** — All existing messages must be preserved. The Lead Agent needs full context.

6. **DO NOT use `AnimatePresence` without proper key/exit handling** — Framer Motion's `AnimatePresence` requires careful setup. For a simple expand/collapse, `motion.div` with `initial`/`animate`/`exit` is sufficient.

### What This Story Does NOT Include

- **Agent receiving denial signal** — The bridge subscription to detect denial (FR33) is handled by the orchestrator
- **Agent revision after denial** — The agent's response to denial is orchestrator logic
- **Notification badges** — Story 6.3

### Files Created in This Story

| File | Purpose |
|------|---------|
| `dashboard/components/InlineRejection.tsx` | Expandable rejection feedback UI |
| `dashboard/components/InlineRejection.test.tsx` | Vitest tests for rejection component |

### Files Modified in This Story

| File | Changes |
|------|---------|
| `dashboard/convex/tasks.ts` | Add `deny` and `returnToLeadAgent` mutations |
| `dashboard/components/TaskCard.tsx` | Add Deny button and InlineRejection integration |
| `dashboard/components/TaskDetailSheet.tsx` | Add Deny button and InlineRejection in sheet |
| `nanobot/mc/state_machine.py` | Add review -> inbox transition for return-to-lead-agent |
| `dashboard/convex/tasks.ts` (updateStatus) | Add review -> inbox as valid transition |

### Verification Steps

1. Open a human_approved task in review — verify Deny button appears next to Approve
2. Click Deny — verify textarea expands inline with focus
3. Type feedback, click Submit — verify denial message in thread, task stays in "review"
4. Verify `hitl_denied` activity event in feed
5. Click Deny again, type feedback, click "Return to Lead Agent" — verify task moves to inbox
6. Verify thread history is preserved on the returned task
7. Verify empty feedback disables Submit button
8. Run `cd dashboard && npx vitest run` — tests pass

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 6.2`] — Original story definition
- [Source: `_bmad-output/planning-artifacts/prd.md#FR33`] — Denied task remains actionable
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#Component Strategy`] — InlineRejection spec (150ms expand, textarea + buttons)
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#UX Consistency Patterns`] — Inline action pattern, no modals
- [Source: `dashboard/components/TaskCard.tsx`] — Existing component to add Deny button
- [Source: `dashboard/components/TaskDetailSheet.tsx`] — Existing sheet to add Deny button
- [Source: `nanobot/mc/state_machine.py`] — State machine to extend with review -> inbox

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References
- TypeScript check: `npx tsc --noEmit` -- clean, no errors
- Vitest: `npx vitest run components/InlineRejection.test.tsx` -- 7/7 tests pass

### Completion Notes List
- Created `deny` mutation: validates review state, keeps task in review (FR33), writes hitl_denied activity + denial message
- Created `returnToLeadAgent` mutation: resets status to inbox, clears assignedAgent, writes denial message + system message + task_retrying activity
- Added review->inbox transition to both Convex and Python state machines
- Created InlineRejection component with Framer Motion expand/collapse, auto-focus textarea, Submit + Return to Lead Agent buttons, empty-feedback validation
- Added Deny button to TaskCard next to Approve button with stopPropagation
- Added Deny button to TaskDetailSheet header next to Approve with InlineRejection below header
- All 7 Vitest tests pass

### File List
- `dashboard/components/InlineRejection.tsx` (created) -- Expandable rejection feedback UI
- `dashboard/components/InlineRejection.test.tsx` (created) -- 7 Vitest tests
- `dashboard/convex/tasks.ts` (modified) -- Added deny + returnToLeadAgent mutations, review->inbox transition
- `dashboard/components/TaskCard.tsx` (modified) -- Added Deny button + InlineRejection integration
- `dashboard/components/TaskDetailSheet.tsx` (modified) -- Added Deny button + InlineRejection in sheet header
- `nanobot/mc/state_machine.py` (modified) -- Added review->inbox transition + event mapping
