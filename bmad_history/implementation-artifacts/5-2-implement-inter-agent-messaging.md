# Story 5.2: Implement Inter-Agent Messaging

Status: done

## Story

As a **developer**,
I want agents to send task-scoped messages to each other,
So that inter-agent collaboration has a persistent, visible communication channel.

## Acceptance Criteria

1. **Given** a task exists and an agent is working on it, **When** the agent sends a message via the bridge, **Then** a message is created in the Convex `messages` table with: taskId, authorName, authorType ("agent"), content, messageType ("work"), and ISO 8601 timestamp
2. **Given** a message is created, **Then** the message appears in the task's thread on the dashboard in real-time (via reactive query in TaskDetailSheet)
3. **Given** a task is configured with reviewers, **When** the assigned agent completes work and the task transitions to "review", **Then** the system routes a review request ONLY to the specified reviewer agents -- not broadcast (FR27)
4. **Given** a review request is routed, **Then** a `review_requested` activity event is created with description: "Review requested from {reviewer names} for '{task title}'"
5. **Given** only configured reviewers receive the review notification, **Then** the notification is targeted -- no other agents receive it
6. **Given** 100% message delivery is required (NFR9), **When** a message is written via the bridge, **Then** the message is persisted in Convex and visible in the task thread within 10 seconds
7. **And** Convex `messages.ts` contains `create` mutation and `listByTask` query (already exists from Story 2.6)
8. **And** the bridge exposes `send_message()` method in `bridge.py` (already exists from Story 1.3)
9. **And** the orchestrator handles review routing in `nanobot/mc/orchestrator.py`
10. **And** unit tests cover message creation, task-scoped filtering, and review routing

## Tasks / Subtasks

- [ ] Task 1: Implement review routing logic in the orchestrator (AC: #3, #4, #5, #9)
  - [ ] 1.1: Add `_handle_review_transition(task_id: str, task: TaskData)` method to `TaskOrchestrator`
  - [ ] 1.2: When a task transitions to "review" status, check if the task has `reviewers` configured
  - [ ] 1.3: If reviewers are configured, send a system message to the task thread: "Review requested from {reviewer names}"
  - [ ] 1.4: Create a `review_requested` activity event via `bridge.create_activity()`
  - [ ] 1.5: Mark the review as targeted to specific agents (store reviewer info accessible to the gateway for dispatching review work)
  - [ ] 1.6: If no reviewers configured and trust level is "autonomous", skip review entirely

- [ ] Task 2: Subscribe to task status changes for review routing (AC: #3)
  - [ ] 2.1: In the orchestrator routing loop, add subscription or polling for tasks transitioning to "review" status
  - [ ] 2.2: Use `bridge.subscribe("tasks:listByStatus", {"status": "review"})` to watch for review transitions
  - [ ] 2.3: For each task entering review, call `_handle_review_transition()`

- [ ] Task 3: Implement agent message sending via the orchestrator (AC: #1, #2, #6)
  - [ ] 3.1: Add `send_agent_message(task_id: str, agent_name: str, content: str, message_type: str = "work")` method to `TaskOrchestrator`
  - [ ] 3.2: This wraps `bridge.send_message()` with proper author type and timestamp
  - [ ] 3.3: The bridge's retry logic (Story 1.4) ensures delivery reliability (NFR9)
  - [ ] 3.4: Log message delivery to stdout for debugging

- [ ] Task 4: Add review notification message types (AC: #4)
  - [ ] 4.1: When review is requested, send a system message to the task thread with messageType "system_event" and content describing the review request
  - [ ] 4.2: The system message format: "Review requested. Awaiting review from: {reviewer1}, {reviewer2}"
  - [ ] 4.3: This message appears in the TaskDetailSheet thread tab

- [ ] Task 5: Write unit tests (AC: #10)
  - [ ] 5.1: Add tests to `nanobot/mc/test_orchestrator.py`
  - [ ] 5.2: Test review routing is triggered when a task with reviewers transitions to "review"
  - [ ] 5.3: Test no review routing for autonomous tasks
  - [ ] 5.4: Test review request creates activity event with correct description
  - [ ] 5.5: Test message sending calls bridge.send_message with correct args
  - [ ] 5.6: Test review routing only targets configured reviewers (not all agents)

## Dev Notes

### Critical Architecture Requirements

- **Messages are task-scoped**: All messages belong to a specific task via `taskId`. There is no global message bus visible on the dashboard — only task threads.
- **The `messages.create` mutation already exists**: Story 2.6 created the Convex mutation. The bridge's `send_message()` method already exists from Story 1.3. This story connects them for the review workflow.
- **Review routing is NOT broadcast**: FR27 is explicit — when a task has configured reviewers, only those specific agents receive the review request. No broadcast to all agents.
- **Bridge retry ensures delivery**: The bridge's 3x retry with exponential backoff (Story 1.4) guarantees NFR9 (100% message delivery) under normal conditions.

### Review Routing Flow

```
Task in_progress -> review transition detected
    |
    v
Check task.reviewers
    |
    +-- Has reviewers?
    |       |
    |       v
    |   Send system message to task thread: "Review requested from {reviewers}"
    |   Create review_requested activity event
    |   Notify reviewer agents (targeted, not broadcast)
    |
    +-- No reviewers?
            |
            +-- trust_level == "autonomous" -> Skip review, transition to done
            +-- trust_level == "human_approved" -> Create hitl_requested event
```

### Orchestrator Review Handling Pattern

```python
async def _handle_review_transition(self, task_id: str, task: dict) -> None:
    """Handle a task entering review state."""
    reviewers = task.get("reviewers") or []
    trust_level = task.get("trust_level", "autonomous")
    title = task.get("title", "Untitled")

    if not reviewers and trust_level == "autonomous":
        # No review needed — auto-complete
        self._bridge.update_task_status(task_id, "done")
        return

    if reviewers:
        # Targeted review routing (FR27)
        reviewer_names = ", ".join(reviewers)
        self._bridge.send_message(
            task_id=task_id,
            author_name="system",
            author_type="system",
            content=f"Review requested. Awaiting review from: {reviewer_names}",
            message_type="system_event",
        )
        self._bridge.create_activity(
            event_type="review_requested",
            description=f"Review requested from {reviewer_names} for '{title}'",
            task_id=task_id,
        )

    if trust_level == "human_approved" and not reviewers:
        # Human approval gate without agent review
        self._bridge.create_activity(
            event_type="hitl_requested",
            description=f"Human approval requested for '{title}'",
            task_id=task_id,
        )
```

### Message Flow Diagram

```
Agent A (assigned) -- completes work --> bridge.update_task_status("review")
    |
    v
Orchestrator detects review transition
    |
    v
Orchestrator sends system message to task thread
    |
    v
Orchestrator notifies reviewer agents (targeted)
    |
    v
Reviewer Agent B picks up review -- reads task thread
    |
    v
Reviewer Agent B sends feedback message via bridge.send_message()
    |
    v
Message appears in TaskDetailSheet thread tab (real-time via Convex)
```

### Common LLM Developer Mistakes to Avoid

1. **DO NOT broadcast review requests to all agents** — FR27 is explicit: only configured reviewers receive the notification. The orchestrator must check `task.reviewers` and route ONLY to those agents.

2. **DO NOT create a new Convex mutation for review messages** — Use the existing `messages:create` mutation via `bridge.send_message()`. The message type "system_event" distinguishes review system messages.

3. **DO NOT skip the activity event** — Every review request MUST create a `review_requested` activity event. This is visible in the activity feed.

4. **DO NOT assume all tasks have reviewers** — Many tasks will be "autonomous" with no reviewers. The orchestrator must handle this gracefully.

5. **DO NOT use `asyncio.sleep` polling** — Use `bridge.subscribe()` to reactively detect review transitions.

6. **DO NOT modify the task status from within the review routing** — The review routing responds to the transition to "review" status. It does not change the status itself (except for the auto-complete case for autonomous tasks without reviewers).

### What This Story Does NOT Include

- **Reviewer providing feedback** — That's Story 5.3
- **Reviewer approving a task** — That's Story 5.3
- **HITL approve/deny buttons** — That's Story 6.1 and 6.2
- **ThreadMessage visual variants for review messages** — That's Story 5.3

### Files Created in This Story

| File | Purpose |
|------|---------|
| (none -- extends existing files) | |

### Files Modified in This Story

| File | Changes |
|------|---------|
| `nanobot/mc/orchestrator.py` | Add review routing logic, review transition handling |
| `nanobot/mc/test_orchestrator.py` | Add tests for review routing |

### Verification Steps

1. Create a task with reviewers ["secretario"], assigned to "financeiro"
2. Transition the task to "in_progress", then to "review"
3. Verify a system message appears in the task thread: "Review requested. Awaiting review from: secretario"
4. Verify a `review_requested` activity event appears in the feed
5. Create an autonomous task with no reviewers — transition to review — verify it auto-completes to done
6. Verify review routing does NOT send messages to non-reviewer agents
7. Run `pytest nanobot/mc/test_orchestrator.py` — all tests pass

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 5.2`] — Original story definition
- [Source: `_bmad-output/planning-artifacts/prd.md#FR26`] — Agents send task-scoped messages
- [Source: `_bmad-output/planning-artifacts/prd.md#FR27`] — Targeted review routing (not broadcast)
- [Source: `_bmad-output/planning-artifacts/prd.md#NFR9`] — 100% message delivery within 10 seconds
- [Source: `nanobot/mc/bridge.py`] — `send_message()` method already exists
- [Source: `nanobot/mc/orchestrator.py`] — Extends routing logic from Story 4.1
- [Source: `dashboard/convex/messages.ts`] — `create` mutation already exists
- [Source: `dashboard/convex/schema.ts`] — Messages table schema

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References
- All 36 tests pass: `python3 -m pytest nanobot/mc/test_orchestrator.py -v` (36 passed in 0.12s)
- Pre-existing TS error in dashboard/convex/tasks.ts:129 (unrelated to this story)

### Completion Notes List
- Added `start_review_routing_loop()` to TaskOrchestrator — subscribes to tasks with "review" status via `bridge.subscribe()`, deduplicates already-handled tasks
- Added `_handle_review_transition()` — implements FR27 targeted review routing: sends system message to task thread naming only configured reviewers, creates `review_requested` activity event
- Auto-completes autonomous tasks with no reviewers to "done" status
- Creates `hitl_requested` activity event for human_approved tasks without reviewers
- Added `send_agent_message()` — wraps `bridge.send_message()` with agent author type for FR26
- Added 9 new unit tests covering: review with reviewers, multiple reviewers, autonomous auto-complete, human_approved HITL, targeted routing, deduplication, None handling, agent message sending, custom message types

### File List
- `nanobot/mc/orchestrator.py` — Added review routing loop, review transition handler, agent message sender
- `nanobot/mc/test_orchestrator.py` — Added TestReviewRouting (7 tests) and TestAgentMessageSending (2 tests)
