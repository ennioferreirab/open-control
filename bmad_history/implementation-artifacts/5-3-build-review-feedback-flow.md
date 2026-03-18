# Story 5.3: Build Review Feedback Flow

Status: done

## Story

As a **user**,
I want to see agents reviewing each other's work as a threaded discussion,
So that I can follow the review process and trust the quality of agent output.

## Acceptance Criteria

1. **Given** a task is in "review" state and a reviewer agent receives it, **When** the reviewer provides feedback, **Then** a message is created with messageType "review_feedback" and appears in the task thread
2. **Given** a review feedback message renders in the thread, **Then** the `ThreadMessage` component renders it with amber-50 background (review feedback variant)
3. **Given** a `review_feedback` activity event is created, **Then** it appears in the activity feed
4. **Given** the reviewer has provided feedback, **When** the assigned agent addresses the feedback, **Then** the agent's response appears as a new thread message (messageType "work")
5. **Given** revision is happening, **Then** the task remains in "review" state (FR29) -- no backward transition
6. **Given** the revision cycle continues, **Then** the reviewer can provide additional rounds of feedback until satisfied
7. **Given** the reviewer approves the task (FR30), **When** the approval is submitted, **Then** a message is created with messageType "approval"
8. **Given** reviewer approval and trust level is "agent_reviewed", **Then** the task transitions to "done" and a `review_approved` activity event is created
9. **Given** reviewer approval and trust level is "human_approved", **Then** the task stays in "review" with a `hitl_requested` activity event created, and the HITL badge appears (Story 6.3)
10. **And** `ThreadMessage.tsx` variants are updated to visually distinguish review feedback (amber-50 bg) from regular agent messages
11. **And** the review flow is orchestrated in `nanobot/mc/orchestrator.py`
12. **And** unit tests cover feedback flow, revision cycles, and approval transitions

## Tasks / Subtasks

- [ ] Task 1: Update ThreadMessage component with review feedback variant (AC: #2, #10)
  - [ ] 1.1: Open `dashboard/components/ThreadMessage.tsx`
  - [ ] 1.2: Add conditional background styling based on `message.messageType`:
    - "review_feedback" -> `bg-amber-50` background
    - "approval" -> `bg-green-50` background
    - "denial" -> `bg-red-50` background
    - "work" (agent) -> default white background
    - "system_event" -> `bg-slate-50` with italic text
  - [ ] 1.3: Add a small label for review messages: "Review" in `text-xs text-amber-600 font-medium`
  - [ ] 1.4: Add a small label for approval messages: "Approved" in `text-xs text-green-600 font-medium`

- [ ] Task 2: Implement reviewer feedback handling in the orchestrator (AC: #1, #3, #4, #5, #6, #11)
  - [ ] 2.1: Add `handle_review_feedback(task_id: str, reviewer_name: str, feedback: str)` method to `TaskOrchestrator`
  - [ ] 2.2: Send the feedback as a message with messageType "review_feedback" via `bridge.send_message()`
  - [ ] 2.3: Create a `review_feedback` activity event: "{reviewer} provided feedback on '{task title}'"
  - [ ] 2.4: The task remains in "review" state — no status change on feedback
  - [ ] 2.5: Add `handle_agent_revision(task_id: str, agent_name: str, content: str)` method that sends a "work" type message for the revision

- [ ] Task 3: Implement reviewer approval in the orchestrator (AC: #7, #8, #9, #11)
  - [ ] 3.1: Add `handle_review_approval(task_id: str, reviewer_name: str)` method to `TaskOrchestrator`
  - [ ] 3.2: Send an approval message with messageType "approval" via `bridge.send_message()`: "Approved by {reviewer}"
  - [ ] 3.3: Create a `review_approved` activity event: "{reviewer} approved '{task title}'"
  - [ ] 3.4: Check the task's trust level:
    - If "agent_reviewed": transition task from "review" to "done"
    - If "human_approved": create `hitl_requested` activity event, do NOT transition status (task stays in "review" for human gate)
  - [ ] 3.5: For "human_approved", send an additional system message: "Agent review passed. Awaiting human approval."

- [ ] Task 4: Extend state machine for review-to-done transition validation (AC: #8)
  - [ ] 4.1: Verify `state_machine.py` allows `review -> done` transition (already present)
  - [ ] 4.2: Verify `tasks.ts` state machine allows `review -> done` (already present)
  - [ ] 4.3: No state machine changes needed — confirm the existing transitions support this flow

- [ ] Task 5: Write unit tests (AC: #12)
  - [ ] 5.1: Test reviewer feedback creates a "review_feedback" message
  - [ ] 5.2: Test task remains in "review" after feedback (no backward transition)
  - [ ] 5.3: Test agent revision creates a "work" message
  - [ ] 5.4: Test multiple feedback-revision cycles (task stays in "review" throughout)
  - [ ] 5.5: Test reviewer approval with "agent_reviewed" trust level transitions to "done"
  - [ ] 5.6: Test reviewer approval with "human_approved" trust level creates hitl_requested event and stays in "review"
  - [ ] 5.7: Test ThreadMessage rendering with review_feedback variant (Vitest)

## Dev Notes

### Critical Architecture Requirements

- **No backward transitions**: FR29 is explicit — the task remains in "review" state throughout the revision cycle. The assigned agent addresses feedback, the reviewer re-evaluates, but the task never moves backward (e.g., never goes back to "in_progress"). This keeps the state machine simple and predictable.
- **Thread is the communication medium**: All review interaction is visible as messages in the task thread. The user sees the conversation evolve in the TaskDetailSheet.
- **Approval is explicit**: FR30 requires the reviewer to explicitly approve. There is no auto-approval timer.
- **HITL gate is a layered concern**: When trust level is "human_approved", the agent review is just the first gate. After agent approval, the task stays in review awaiting human action (Story 6.1).

### Review Feedback Flow Diagram

```
Assigned Agent completes work
    |
    v
Task transitions to "review" (Story 5.2 handles routing)
    |
    v
Reviewer Agent receives review request
    |
    v
Reviewer reads task thread, evaluates work
    |
    +-- Needs changes?
    |       |
    |       v
    |   Reviewer sends feedback (messageType: "review_feedback")
    |   Task stays in "review"
    |       |
    |       v
    |   Assigned Agent reads feedback
    |   Agent sends revision (messageType: "work")
    |   Task stays in "review"
    |       |
    |       v
    |   Reviewer re-evaluates (loop back to review)
    |
    +-- Approved?
            |
            v
        Reviewer sends approval (messageType: "approval")
            |
            +-- trust_level == "agent_reviewed"
            |       -> Task transitions to "done"
            |
            +-- trust_level == "human_approved"
                    -> hitl_requested event created
                    -> Task stays in "review"
                    -> HITL badge appears on dashboard (Story 6.3)
```

### ThreadMessage Variant Pattern

```tsx
// In ThreadMessage.tsx, determine background based on message type:
function getMessageStyles(messageType: string, authorType: string) {
  switch (messageType) {
    case "review_feedback":
      return { bg: "bg-amber-50", label: "Review", labelColor: "text-amber-600" };
    case "approval":
      return { bg: "bg-green-50", label: "Approved", labelColor: "text-green-600" };
    case "denial":
      return { bg: "bg-red-50", label: "Denied", labelColor: "text-red-600" };
    case "system_event":
      return { bg: "bg-slate-50", label: null, labelColor: "" };
    default:
      if (authorType === "user") return { bg: "bg-blue-50", label: null, labelColor: "" };
      return { bg: "bg-white", label: null, labelColor: "" };
  }
}
```

### Orchestrator Methods Pattern

```python
def handle_review_feedback(
    self, task_id: str, reviewer_name: str, feedback: str
) -> None:
    """Handle reviewer feedback on a task."""
    self._bridge.send_message(
        task_id=task_id,
        author_name=reviewer_name,
        author_type="agent",
        content=feedback,
        message_type="review_feedback",
    )
    # Get task title for activity description
    task = self._bridge.query("tasks:getById", {"task_id": task_id})
    title = task.get("title", "Untitled") if task else "Untitled"
    self._bridge.create_activity(
        event_type="review_feedback",
        description=f"{reviewer_name} provided feedback on '{title}'",
        task_id=task_id,
        agent_name=reviewer_name,
    )

def handle_review_approval(self, task_id: str, reviewer_name: str) -> None:
    """Handle reviewer approval of a task."""
    self._bridge.send_message(
        task_id=task_id,
        author_name=reviewer_name,
        author_type="agent",
        content=f"Approved by {reviewer_name}",
        message_type="approval",
    )
    task = self._bridge.query("tasks:getById", {"task_id": task_id})
    title = task.get("title", "Untitled") if task else "Untitled"
    trust_level = task.get("trust_level", "autonomous") if task else "autonomous"

    self._bridge.create_activity(
        event_type="review_approved",
        description=f"{reviewer_name} approved '{title}'",
        task_id=task_id,
        agent_name=reviewer_name,
    )

    if trust_level == "agent_reviewed":
        self._bridge.update_task_status(task_id, "done", agent_name=reviewer_name)
    elif trust_level == "human_approved":
        self._bridge.send_message(
            task_id=task_id,
            author_name="system",
            author_type="system",
            content="Agent review passed. Awaiting human approval.",
            message_type="system_event",
        )
        self._bridge.create_activity(
            event_type="hitl_requested",
            description=f"Human approval requested for '{title}'",
            task_id=task_id,
        )
```

### Common LLM Developer Mistakes to Avoid

1. **DO NOT move the task backward from "review"** — FR29 is explicit. The task stays in "review" throughout the entire revision cycle. No transition to "in_progress" or "assigned".

2. **DO NOT auto-approve after a timeout** — Approval must be explicit (FR30). The reviewer agent or human user must actively approve.

3. **DO NOT create separate status values for "under review" vs "revision in progress"** — The task status is simply "review" throughout. The thread messages tell the story.

4. **DO NOT forget the human gate** — When trust level is "human_approved", agent approval does NOT complete the task. It creates a `hitl_requested` event and waits for human action.

5. **DO NOT modify ThreadMessage to make it interactive** — ThreadMessage is read-only. Review actions (approve, deny) are handled by the orchestrator (agent side) or HITL buttons (human side, Story 6.1).

6. **DO NOT use `replace_all` for ThreadMessage styles** — Add the variant logic as conditional classes, don't replace the existing styling.

### What This Story Does NOT Include

- **HITL approve/deny buttons** — That's Story 6.1 and 6.2
- **HITL notification badges** — That's Story 6.3
- **Inline rejection feedback from user** — That's Story 6.2
- **Agent execution of review work** — The actual agent work logic is not part of this story

### Files Created in This Story

| File | Purpose |
|------|---------|
| (none -- extends existing files) | |

### Files Modified in This Story

| File | Changes |
|------|---------|
| `dashboard/components/ThreadMessage.tsx` | Add review_feedback (amber-50), approval (green-50), denial (red-50) variants |
| `nanobot/mc/orchestrator.py` | Add `handle_review_feedback()`, `handle_review_approval()` methods |
| `nanobot/mc/test_orchestrator.py` | Add tests for feedback flow, revision cycles, approval transitions |

### Verification Steps

1. Send a review_feedback message to a task — verify ThreadMessage renders with amber-50 background
2. Send an approval message — verify green-50 background
3. Verify task stays in "review" after receiving feedback (no backward transition)
4. Send feedback + revision multiple times — verify task stays in "review" throughout
5. Approve a task with "agent_reviewed" trust level — verify transition to "done"
6. Approve a task with "human_approved" trust level — verify it stays in "review" with hitl_requested event
7. Run `pytest nanobot/mc/test_orchestrator.py` and `cd dashboard && npx vitest run` — all tests pass

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 5.3`] — Original story definition
- [Source: `_bmad-output/planning-artifacts/prd.md#FR28`] — Reviewer feedback visible on dashboard
- [Source: `_bmad-output/planning-artifacts/prd.md#FR29`] — Revision within Review state
- [Source: `_bmad-output/planning-artifacts/prd.md#FR30`] — Reviewer approves task
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#Component Strategy`] — ThreadMessage variants spec
- [Source: `dashboard/components/ThreadMessage.tsx`] — Existing component to update
- [Source: `nanobot/mc/orchestrator.py`] — Extends review routing from Story 5.2
- [Source: `nanobot/mc/state_machine.py`] — Validates review -> done transition

## Dev Agent Record

### Agent Model Used
claude-opus-4-6

### Debug Log References
- All 70 orchestrator tests pass (6 new for Story 5.3)
- TS type-check: only pre-existing error in convex/tasks.ts:129 (unrelated listByStatus v.string() type)

### Completion Notes List
- Task 1: Updated ThreadMessage.tsx with getMessageStyles() function — review_feedback (amber-50), approval (green-50), denial (red-50), system_event (slate-50) variants with labels
- Task 2: Added handle_review_feedback() and handle_agent_revision() to TaskOrchestrator — sends messages and activity events, task stays in "review" (FR29)
- Task 3: Added handle_review_approval() to TaskOrchestrator — agent_reviewed transitions to "done", human_approved creates hitl_requested event and stays in "review"
- Task 4: Verified state machine allows review -> done (already present in state_machine.py line 17)
- Task 5: Added 6 unit tests covering feedback, revision cycles, and approval transitions with both trust levels

### File List
- `dashboard/components/ThreadMessage.tsx` — Review variant styling with labels (amber-50 for feedback, green-50 for approval, red-50 for denial)
- `nanobot/mc/orchestrator.py` — Added handle_review_feedback(), handle_agent_revision(), handle_review_approval()
- `nanobot/mc/test_orchestrator.py` — Added TestReviewFeedbackFlow class with 6 tests
