# Story 2.6: Build Thread Context for Agents

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want agents to receive relevant thread context when starting their step,
So that dependent agents have the information they need to continue the work.

## Acceptance Criteria

1. **20-message truncation window** — Given an agent is about to start a step, when the executor builds the thread context for that agent, then the context includes the last 20 messages from the task's unified thread (NFR5), and if more than 20 messages exist, a note is prepended: "(N earlier messages omitted)".

2. **Latest user message separated** — Given the thread contains user messages, when the context is built, then the latest user message (if any) is separated into a `[Latest Follow-up]` section so the agent can clearly identify the new instruction.

3. **Predecessor completion messages always included** — Given a step has direct predecessors in its `blockedBy` array, when the thread context is built, then the structured completion messages of ALL direct predecessors are ALWAYS included in the context, even if they fall outside the 20-message window, and predecessor messages are injected at their chronological position (or as a preamble if before the window).

4. **Artifact details formatted** — Given the thread contains structured completion messages with artifacts, when the context is injected into the agent's prompt, then artifact details (file paths, diffs, descriptions) are formatted in a parseable way that fits within the LLM context window alongside the agent's system prompt and task description.

5. **Empty thread handling** — Given the thread is empty (first step to execute), when the context is built, then the agent receives only the task description and step description with no thread context.

6. **Step-aware context building** — Given the executor is building context for a specific step (not a legacy task-level execution), when the step has `blockedBy` references, then the bridge fetches the step records to identify predecessor step IDs, and the context builder uses those IDs to locate predecessor completion messages in the thread.

7. **Backward compatibility preserved** — Given legacy task-level execution (no step context), when the executor builds thread context, then the existing `_build_thread_context()` behavior is preserved unchanged (20-message window, latest user message separation, no predecessor logic).

## Tasks / Subtasks

- [x] **Task 1: Add bridge method to fetch step records by IDs** (AC: 3, 6)
  - [x] 1.1 Add `get_steps_by_task(task_id: str) -> list[dict]` method to `ConvexBridge` in `nanobot/mc/bridge.py` that queries `steps:getByTask`
  - [x] 1.2 Add unit test in `nanobot/mc/test_bridge.py` for the new method

- [x] **Task 2: Extend messages schema/bridge to support step-aware queries** (AC: 3, 6)
  - [x] 2.1 Verify that `messages:listByTask` returns `stepId` and `type` and `artifacts` fields (already in schema — confirm bridge snake_case conversion handles them)
  - [x] 2.2 Add integration note: messages with `type: "step_completion"` and a `step_id` field are the ones to match against predecessor step IDs

- [x] **Task 3: Create `ThreadContextBuilder` class in `nanobot/mc/thread_context.py`** (AC: 1, 2, 3, 4, 5, 6, 7)
  - [x] 3.1 Extract the existing `_build_thread_context()` function from `executor.py` into a new `nanobot/mc/thread_context.py` module as a `ThreadContextBuilder` class
  - [x] 3.2 Implement `build(messages, max_messages=20, predecessor_step_ids=None)` as the main entry point
  - [x] 3.3 When `predecessor_step_ids` is None or empty, delegate to existing logic (backward compat)
  - [x] 3.4 When `predecessor_step_ids` is provided, implement predecessor-aware context building:
    - Identify predecessor completion messages by matching `step_id` field against `predecessor_step_ids`
    - Separate messages into: predecessor completions + recent window + latest user message
    - If predecessor messages fall within the 20-message window, include them at their natural chronological position
    - If predecessor messages fall outside the 20-message window, inject them as a `[Predecessor Context]` preamble section before the `[Thread History]` section
    - Always include the `"(N earlier messages omitted)"` note when messages are truncated
  - [x] 3.5 Implement `_format_message(message)` helper that renders a single message including artifacts if present
  - [x] 3.6 Implement `_format_artifacts(artifacts)` helper that renders artifact details in a compact, parseable format
  - [x] 3.7 Keep the `_build_thread_context()` function in `executor.py` as a thin shim that calls `ThreadContextBuilder().build()` for backward compatibility

- [x] **Task 4: Integrate step-aware context into executor** (AC: 1, 2, 3, 4, 5, 6)
  - [x] 4.1 Add a new method `_build_step_context()` to `TaskExecutor` (or extend `_execute_task`) that accepts step metadata (step_id, blockedBy, title, description)
  - [x] 4.2 When executing a step: fetch step records for the task via bridge, resolve `blockedBy` to predecessor step IDs
  - [x] 4.3 Call `ThreadContextBuilder().build(messages, predecessor_step_ids=predecessor_ids)` instead of the legacy `_build_thread_context(messages)`
  - [x] 4.4 Inject step description alongside task description in the agent's prompt context
  - [x] 4.5 When thread is empty and this is the first step, inject only task description + step description

- [x] **Task 5: Write comprehensive tests for `ThreadContextBuilder`** (AC: 1, 2, 3, 4, 5, 6, 7)
  - [x] 5.1 Create `nanobot/mc/test_thread_context.py`
  - [x] 5.2 Test: empty messages list returns empty string
  - [x] 5.3 Test: messages within 20-message window are all included
  - [x] 5.4 Test: messages exceeding 20-message window are truncated with omission note
  - [x] 5.5 Test: latest user message separated into `[Latest Follow-up]` section
  - [x] 5.6 Test: predecessor completion messages within window appear at natural position
  - [x] 5.7 Test: predecessor completion messages outside window appear in `[Predecessor Context]` preamble
  - [x] 5.8 Test: predecessor messages with artifacts are formatted with file paths, actions, descriptions, diffs
  - [x] 5.9 Test: backward compat — no predecessor_step_ids produces same output as legacy function
  - [x] 5.10 Test: messages with no user messages return empty string (preserves existing behavior)
  - [x] 5.11 Test: step-aware context includes step description in output

- [x] **Task 6: Update executor tests** (AC: 7)
  - [x] 6.1 Verify existing `_build_thread_context` tests in executor still pass (shim delegates correctly)
  - [x] 6.2 Add test for step-aware execution path showing predecessor context injection

## Dev Notes

### Critical: This Story Bridges Task-Level and Step-Level Execution

The existing system executes tasks, not steps. The current `_build_thread_context()` in `executor.py` (lines 168-223) operates at the task level — it fetches all messages for a task and applies a 20-message truncation window. This story extends that pattern to be step-aware, without breaking the existing task-level flow.

The new `ThreadContextBuilder` must handle both:
1. **Legacy task-level execution** — no step metadata, no predecessor logic (backward compat)
2. **Step-level execution** — step has `blockedBy` predecessors, their completion messages must always be included

### Existing `_build_thread_context()` Behavior (Preserve This)

```python
# Current implementation in executor.py lines 168-223:
# 1. Returns "" if no messages
# 2. Returns "" if no user messages exist (first execution)
# 3. Finds latest user message, separates it into [Latest Follow-up]
# 4. Truncates to last 20 messages with "(N earlier messages omitted)"
# 5. Formats as "[Thread History]\n..." + "\n\n[Latest Follow-up]\nUser: ..."
```

**IMPORTANT:** The existing function skips context entirely if there are no user messages (`has_user_messages` check). For step-level execution, this check must be relaxed — a step may need predecessor context even when no user has posted yet. The `ThreadContextBuilder` should:
- When called WITHOUT predecessor IDs: preserve the `has_user_messages` guard (backward compat)
- When called WITH predecessor IDs: always build context if predecessors exist, even without user messages

### Predecessor Injection Strategy

Architecture gap #4 (from architecture.md validation section) explicitly calls this out:

> "When Step 3 depends on Step 1 and Step 2, how does Step 3's agent know what those steps produced? The thread truncation (20 messages) might exclude earlier completion messages. **Recommendation:** When building step context, always inject the structured completion messages of direct `blockedBy` predecessors, even if they fall outside the 20-message window."

**Algorithm:**

```python
def build(messages, max_messages=20, predecessor_step_ids=None):
    predecessor_ids = set(predecessor_step_ids or [])

    # Separate predecessor completion messages from the rest
    predecessor_msgs = []
    other_msgs = []
    for m in messages:
        if m.get("step_id") in predecessor_ids and m.get("type") == "step_completion":
            predecessor_msgs.append(m)
        else:
            other_msgs.append(m)  # actually, keep all in order for chronological rendering

    # Apply 20-message window to the full list
    total = len(messages)
    window = messages[-max_messages:] if total > max_messages else messages

    # Check which predecessors fell outside the window
    window_ids = {id(m) for m in window}
    predecessors_outside_window = [
        m for m in predecessor_msgs if id(m) not in window_ids
        # (use message index or _id for identity, not Python id())
    ]

    # Build output:
    # 1. [Predecessor Context] section (only for predecessors outside window)
    # 2. "(N earlier messages omitted)" note
    # 3. [Thread History] section (the 20-message window, predecessors inside appear naturally)
    # 4. [Latest Follow-up] section (latest user message)
```

### Artifact Formatting

Structured completion messages include an `artifacts` array. These must be formatted compactly for LLM consumption:

```python
def _format_artifacts(artifacts: list[dict]) -> str:
    """Format artifacts for LLM context injection.

    Example output:
      Files:
      - CREATED: /output/report.pdf — Financial summary report (47 pages)
      - MODIFIED: /output/data.json — diff: +12 matched, -3 removed
    """
    if not artifacts:
        return ""
    lines = ["  Files:"]
    for a in artifacts:
        action = a.get("action", "unknown").upper()
        path = a.get("path", "unknown")
        desc = a.get("description", "")
        diff = a.get("diff", "")
        detail = desc if desc else f"diff: {diff}" if diff else ""
        line = f"  - {action}: {path}"
        if detail:
            line += f" — {detail}"
        lines.append(line)
    return "\n".join(lines)
```

### Message Field Mapping (Bridge snake_case)

Messages from `bridge.get_task_messages()` arrive with snake_case keys after bridge conversion:

| Convex Field (camelCase) | Python Field (snake_case) | Used For |
|---|---|---|
| `authorName` | `author_name` | Display name in context |
| `authorType` | `author_type` | Identify user messages |
| `messageType` | `message_type` | Identify user_message type |
| `type` | `type` | Identify step_completion type |
| `stepId` | `step_id` | Match against predecessor step IDs |
| `artifacts` | `artifacts` | Extract file paths, diffs, descriptions |
| `content` | `content` | Message body text |
| `timestamp` | `timestamp` | Chronological ordering |

### Existing Code That Touches This Story

| File | What exists | What changes |
|---|---|---|
| `nanobot/mc/executor.py` | `_build_thread_context()` function (lines 168-223), `_execute_task()` method (lines 586-811) that calls it | Extract context builder to new module; add step-aware execution path; keep shim for backward compat |
| `nanobot/mc/bridge.py` | `get_task_messages()` method; no step query method | Add `get_steps_by_task()` convenience method |
| `nanobot/mc/types.py` | `MessageData` dataclass (no `step_id`, `type`, `artifacts` fields) | No changes in this story — raw dict messages are used, not MessageData |
| `dashboard/convex/messages.ts` | `listByTask` query returns all message fields including `stepId`, `type`, `artifacts` | No changes needed |
| `dashboard/convex/steps.ts` | `getByTask` query returns step records with `blockedBy` | No changes needed — already exists |
| `dashboard/convex/schema.ts` | Messages table has `stepId`, `type`, `artifacts` fields | No changes needed — already exists from Story 1.1 |

### New File: `nanobot/mc/thread_context.py`

```python
"""Thread context builder for agent prompt injection.

Builds the thread context that agents receive when starting a step.
Handles 20-message truncation (NFR5), predecessor completion message
injection, artifact formatting, and latest user message separation.

Extracted from executor.py _build_thread_context() to support
step-aware context building while preserving backward compatibility.
"""

from __future__ import annotations

from typing import Any

MAX_THREAD_MESSAGES = 20


class ThreadContextBuilder:
    """Builds formatted thread context for agent prompt injection."""

    def build(
        self,
        messages: list[dict[str, Any]],
        max_messages: int = MAX_THREAD_MESSAGES,
        predecessor_step_ids: list[str] | None = None,
    ) -> str:
        """Build thread context string for agent injection.

        Args:
            messages: Thread messages in chronological order (snake_case keys).
            max_messages: Truncation window size (default 20, NFR5).
            predecessor_step_ids: Step IDs of direct blockedBy predecessors.
                When provided, their completion messages are always included.
                When None, falls back to legacy behavior.

        Returns:
            Formatted context string, or "" if no relevant context.
        """
        ...
```

### Step-Aware Execution Flow

The executor currently calls `_build_thread_context()` inside `_execute_task()` at line 653-670. For step-level execution, the flow changes:

1. **Step dispatcher** (future story) calls executor with step metadata
2. Executor fetches thread messages via `bridge.get_task_messages(task_id)`
3. Executor fetches step records via `bridge.get_steps_by_task(task_id)` to resolve `blockedBy` to real step IDs
4. Executor calls `ThreadContextBuilder().build(messages, predecessor_step_ids=[...])`
5. Context is injected into the agent's prompt alongside task description + step description

For this story, the integration point in executor should be prepared but the step dispatcher integration is a separate story. The key deliverable is:
- `ThreadContextBuilder` class (new module)
- `_build_thread_context()` shim in executor (backward compat)
- Bridge method `get_steps_by_task()` (needed for predecessor resolution)
- Step-aware build path in `ThreadContextBuilder.build()`

### Context Window Budget Awareness

The agent's total context includes:
- System prompt (agent's YAML prompt + orientation)
- Task description + step description
- File manifest (attached files metadata)
- **Thread context** (this story's output)
- Agent workspace/memory context (from AgentLoop)

Thread context should be the most compressible component. The 20-message window (NFR5) is a hard cap on recent messages. Predecessor messages are exempt from this cap because they are essential for dependent agents — but artifact diffs within predecessor messages should be truncated if they exceed a reasonable size (e.g., 2000 characters per diff). The `_format_artifacts()` helper should enforce this limit.

### Testing Strategy

- **Unit tests** for `ThreadContextBuilder` in `nanobot/mc/test_thread_context.py` — pure Python, no Convex dependency
- **Unit tests** for bridge `get_steps_by_task()` in `nanobot/mc/test_bridge.py` — mocked ConvexClient
- **Shim test** — verify `_build_thread_context()` in executor still works and delegates to `ThreadContextBuilder`
- **No frontend tests** — this story is purely Python backend
- **No E2E tests** — step-level execution E2E requires the step dispatcher (future story)

### Git Intelligence (Recent Commits)

```
830fd64 fix card ui
e685c07 Fix Design broken
acc0318 wip: alinhamento do design da dashboard
823f0a7 feat: Implement cron job task linking and output file syncing
479bc23 feat: highlight prompt variables with amber color
```

Recent work has been UI alignment and cron job features. No conflicts expected with executor/bridge changes.

### Project Structure Notes

- **New file:** `nanobot/mc/thread_context.py` — ThreadContextBuilder class
- **New file:** `nanobot/mc/test_thread_context.py` — comprehensive unit tests
- **Modified:** `nanobot/mc/executor.py` — extract `_build_thread_context()` to shim, add step-aware integration point
- **Modified:** `nanobot/mc/bridge.py` — add `get_steps_by_task()` convenience method
- **Modified:** `nanobot/mc/test_bridge.py` — test for new bridge method
- **No Convex changes** — all needed schema/queries already exist from Story 1.1
- **No frontend changes** — this story is backend-only

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#Unified Thread & Communication] — Thread context management requirements
- [Source: _bmad-output/planning-artifacts/architecture.md#Implementation Readiness Validation, Gap #4] — Predecessor injection recommendation
- [Source: _bmad-output/planning-artifacts/architecture.md#Cross-Cutting Concerns Mapping] — Thread context management file mapping
- [Source: _bmad-output/planning-artifacts/architecture.md#Structured Completion Message Format] — ThreadMessage type with artifacts
- [Source: _bmad-output/planning-artifacts/prd.md#FR27] — Agents read full thread context when starting their step
- [Source: _bmad-output/planning-artifacts/prd.md#FR28] — Thread context managed to fit within LLM context windows
- [Source: _bmad-output/planning-artifacts/prd.md#NFR5] — Thread context truncation to last 20 messages
- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.6] — Full BDD acceptance criteria
- [Source: nanobot/mc/executor.py:168-223] — Existing `_build_thread_context()` implementation
- [Source: nanobot/mc/executor.py:652-670] — Thread context injection in `_execute_task()`
- [Source: nanobot/mc/bridge.py:271-274] — `get_task_messages()` method
- [Source: dashboard/convex/messages.ts:5-13] — `listByTask` query
- [Source: dashboard/convex/steps.ts:170-181] — `getByTask` query returning steps with blockedBy
- [Source: dashboard/convex/schema.ts:91-127] — Messages table with stepId, type, artifacts fields
