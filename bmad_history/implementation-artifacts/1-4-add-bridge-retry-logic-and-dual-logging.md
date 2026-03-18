# Story 1.4: Add Bridge Retry Logic & Dual Logging

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want the Convex bridge to retry failed writes and log all state transitions to both Convex and local stdout,
So that the system is resilient to transient failures and all activity is observable for debugging.

## Acceptance Criteria

1. **Given** the bridge core is implemented (Story 1.3), **When** a Convex mutation call fails, **Then** the bridge retries up to 3 times with exponential backoff (1s, 2s, 4s delays)
2. **Given** retry exhaustion occurs (all 3 retries failed), **Then** the bridge logs the error to local stdout with full context: mutation name, arguments, and error message
3. **Given** retry exhaustion occurs, **Then** the bridge makes a best-effort attempt to write a `system_error` activity event to the Convex `activities` table (this write itself is NOT retried — fire and forget)
4. **Given** any task or agent state transition is written via the bridge, **When** the mutation succeeds, **Then** the state transition is logged to local stdout with timestamp, entity type, and description
5. **Given** a successful mutation writes a state transition, **Then** a corresponding activity event is written to the Convex `activities` table in the same mutation call (enforced by the Convex mutation handler, not by the bridge adding a second mutation)
6. **Given** the bridge retry logic is active, **When** a retry succeeds on attempt 2 or 3, **Then** the successful retry is logged to stdout noting which attempt succeeded (e.g., "Mutation tasks:updateStatus succeeded on attempt 2/3")
7. **Given** a retry succeeds on attempt 2 or 3, **Then** NO error activity event is written to Convex (error events are only written on exhaustion)
8. **Given** a Convex query call fails, **Then** the query is NOT retried — only mutations are retried (queries are idempotent reads and the caller can retry if needed)
9. **Given** the retry and logging additions, **Then** `bridge.py` does NOT exceed 500 lines total (NFR21)
10. **Given** the retry logic is implemented, **Then** unit tests exist in `nanobot/mc/test_bridge.py` covering: retry success on attempt 2, retry success on attempt 3, retry exhaustion with error logging, exponential backoff timing, dual logging output

## Tasks / Subtasks

- [x] Task 1: Add retry wrapper method to ConvexBridge (AC: #1, #6, #7, #8, #9)
  - [x] 1.1: Add `_mutation_with_retry()` private method to `ConvexBridge` class
  - [x] 1.2: Implement exponential backoff with delays: 1s (attempt 1 fail), 2s (attempt 2 fail), 4s (attempt 3 fail)
  - [x] 1.3: Log each retry attempt to stdout via Python `logging` module
  - [x] 1.4: On successful retry, log which attempt succeeded — no error activity event
  - [x] 1.5: Update `mutation()` public method to call `_mutation_with_retry()` instead of calling `ConvexClient.mutation()` directly
  - [x] 1.6: Confirm that `query()` does NOT use retry logic — queries pass through directly
- [x] Task 2: Add retry exhaustion error handling (AC: #2, #3)
  - [x] 2.1: After 3 failed attempts, log full error context to stdout: mutation name, camelCase-converted args, error message, all attempt errors
  - [x] 2.2: After logging, make a best-effort call to write a `system_error` activity event to Convex `activities` table
  - [x] 2.3: The best-effort error activity write must NOT itself retry or raise — wrap in try/except and silently log if it also fails
  - [x] 2.4: After best-effort logging, re-raise the original exception to the caller
- [x] Task 3: Add dual logging for state transitions (AC: #4, #5)
  - [x] 3.1: Add `_log_state_transition()` private method that logs to stdout via Python `logging`
  - [x] 3.2: Log format: `"[MC] {timestamp} {entity_type}: {description}"` — e.g., `"[MC] 2026-02-22T10:30:00Z task: Task status changed to in_progress by dev"`
  - [x] 3.3: Document that activity event writing happens inside the Convex mutation handler (TypeScript side) — the bridge does NOT make a separate mutation call for activity events
- [x] Task 4: Add convenience methods for common operations (AC: #4, #5)
  - [x] 4.1: Add `update_task_status()` method — calls `tasks:updateStatus` mutation with retry, logs state transition to stdout
  - [x] 4.2: Add `update_agent_status()` method — calls `agents:updateStatus` mutation with retry, logs state transition to stdout
  - [x] 4.3: Add `create_activity()` method — calls `activities:create` mutation with retry, logs to stdout
  - [x] 4.4: Add `send_message()` method — calls `messages:create` mutation with retry, logs to stdout
  - [x] 4.5: Confirm all convenience methods use `_mutation_with_retry()` internally
- [x] Task 5: Write/update unit tests (AC: #10)
  - [x] 5.1: Test retry succeeds on attempt 2 (first call fails, second succeeds)
  - [x] 5.2: Test retry succeeds on attempt 3 (first two calls fail, third succeeds)
  - [x] 5.3: Test retry exhaustion (all 3 calls fail) — verify error is logged and re-raised
  - [x] 5.4: Test best-effort error activity event is attempted on exhaustion
  - [x] 5.5: Test best-effort error activity failure is silently caught (no cascading exception)
  - [x] 5.6: Test exponential backoff timing (1s, 2s, 4s) using mocked `time.sleep`
  - [x] 5.7: Test that successful retry does NOT write error activity event
  - [x] 5.8: Test that query failures are NOT retried
  - [x] 5.9: Test stdout logging output for state transitions and retry attempts
  - [x] 5.10: Verify bridge.py stays under 500 lines after all additions (274 lines)

## Dev Notes

### Critical Architecture Requirements

- **This story EXTENDS bridge.py from Story 1.3** — do not create a new file. Add retry logic and logging to the existing `ConvexBridge` class.
- **500-line limit still applies (NFR21)** — After adding retry logic, dual logging, and convenience methods, `bridge.py` must remain under 500 lines total. The Story 1.3 core should be ~150-200 lines; retry + logging should add ~100-150 lines, keeping the total well under 500.
- **Activity events are written by Convex mutations (TypeScript)** — NOT by the Python bridge making a separate mutation call. The architecture pattern (from architecture.md) is: each Convex mutation that changes task state ALSO writes an activity event in the same transaction. The bridge's role is to (a) call the mutation and (b) log the same transition to local stdout. The bridge does NOT call `activities:create` as a second step after `tasks:updateStatus`.
- **Exception on retry exhaustion**: The last exception is the one that broke through. The bridge logs it and the best-effort activity event, then **re-raises** the original exception. The caller decides what to do (e.g., gateway marks agent as crashed).
- **No async** — Same as Story 1.3: the bridge remains synchronous. AsyncIO callers use `asyncio.to_thread()`.
- **Retry applies to mutations only** — Queries are idempotent reads. If a query fails, the caller can retry at their discretion. The bridge does not auto-retry queries.

### Retry Logic Design

#### `_mutation_with_retry()` Method

```python
import time
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Constants
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 1  # 1s, 2s, 4s

class ConvexBridge:
    # ... existing __init__, query, etc. from Story 1.3 ...

    def _mutation_with_retry(
        self,
        function_name: str,
        args: dict[str, Any] | None = None,
    ) -> Any:
        """
        Call a Convex mutation with retry and exponential backoff.

        Retries up to 3 times on failure. On exhaustion, logs error to stdout
        and makes a best-effort attempt to write a system_error activity event.

        Args:
            function_name: Convex function in colon notation (e.g., "tasks:updateStatus")
            args: Optional arguments dict (already converted to camelCase by caller)

        Returns:
            Mutation result (if any)

        Raises:
            Exception: Re-raises the last exception after retry exhaustion
        """
        camel_args = self._convert_keys_to_camel(args) if args else None
        last_exception = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = self._client.mutation(function_name, camel_args or {})
                if attempt > 1:
                    logger.info(
                        f"Mutation {function_name} succeeded on attempt {attempt}/{MAX_RETRIES}"
                    )
                return self._convert_keys_to_snake(result) if result else result
            except Exception as e:
                last_exception = e
                if attempt < MAX_RETRIES:
                    delay = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))  # 1s, 2s, 4s
                    logger.warning(
                        f"Mutation {function_name} failed (attempt {attempt}/{MAX_RETRIES}), "
                        f"retrying in {delay}s: {e}"
                    )
                    time.sleep(delay)

        # All retries exhausted
        logger.error(
            f"Mutation {function_name} failed after {MAX_RETRIES} attempts. "
            f"Args: {camel_args}. Error: {last_exception}"
        )

        # Best-effort error activity event
        self._write_error_activity(function_name, str(last_exception))

        raise last_exception
```

#### Exponential Backoff Schedule

| Attempt | Delay Before Retry | Cumulative Wait |
|---------|-------------------|-----------------|
| 1 (initial) | 0s (immediate) | 0s |
| 2 (1st retry) | 1s | 1s |
| 3 (2nd retry) | 2s | 3s |
| 4 (3rd retry) | 4s | 7s |
| Exhaustion | N/A — raise exception | 7s total |

The delay formula is `BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))`:
- After attempt 1 fails: sleep 1s (`1 * 2^0`)
- After attempt 2 fails: sleep 2s (`1 * 2^1`)
- After attempt 3 fails: no sleep, log + raise

**Total maximum wait before failure: 7 seconds** (1 + 2 + 4). This is acceptable given the NFR15 requirement.

### Best-Effort Error Activity Event

When all retries are exhausted, the bridge attempts to write a `system_error` activity event to Convex. This is "best-effort" — if this write also fails (e.g., Convex is completely down), the error is silently caught and logged to stdout only.

```python
def _write_error_activity(self, mutation_name: str, error_message: str) -> None:
    """
    Best-effort write of a system_error activity event to Convex.

    This is called after retry exhaustion. If this write also fails,
    the error is silently logged — no cascading exceptions.
    """
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        self._client.mutation("activities:create", {
            "eventType": "system_error",
            "description": f"Mutation {mutation_name} failed after {MAX_RETRIES} retries: {error_message}",
            "timestamp": timestamp,
        })
    except Exception as e:
        logger.error(
            f"Failed to write error activity event (best-effort): {e}"
        )
```

**Key points:**
- The error activity write uses `self._client.mutation()` directly — NOT `_mutation_with_retry()`. Retrying the error activity write would create an infinite loop.
- The activity event has no `taskId` or `agentName` because those may not be known or relevant at the bridge level. The `description` field contains all context.
- The activity event uses `eventType: "system_error"` which is one of the 16 valid ActivityEventType values from Story 1.2.

### Dual Logging Design

"Dual logging" means every state transition is logged to TWO destinations:

1. **Local stdout** — via Python's `logging` module (this story implements)
2. **Convex `activities` table** — via the Convex mutation itself (implemented in TypeScript mutation handlers, starting in Story 2.4)

The bridge's responsibility for dual logging is:
- **stdout side**: The bridge logs state transitions to stdout using `logger.info()` with a structured format
- **Convex side**: The bridge calls the mutation (e.g., `tasks:updateStatus`), and the mutation handler in TypeScript writes the activity event in the same transaction. The bridge does NOT make a separate `activities:create` call for this.

#### Stdout Log Format

```
[MC] 2026-02-22T10:30:00Z task: Task 'Research AI trends' status changed to in_progress by financeiro
[MC] 2026-02-22T10:30:05Z agent: Agent 'financeiro' status changed to active
[MC] 2026-02-22T10:31:00Z message: Message sent by financeiro on task jd7abc123
```

The `[MC]` prefix distinguishes Mission Control logs from other nanobot log output.

#### `_log_state_transition()` Method

```python
def _log_state_transition(self, entity_type: str, description: str) -> None:
    """
    Log a state transition to local stdout.

    Args:
        entity_type: "task", "agent", "message", "activity", or "setting"
        description: Human-readable description of the transition
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    logger.info(f"[MC] {timestamp} {entity_type}: {description}")
```

### Convenience Methods

These methods provide a typed, semantic API for common operations. Each method:
1. Accepts snake_case arguments (Python convention)
2. Calls `_mutation_with_retry()` with the correct Convex function name
3. Logs the state transition to stdout via `_log_state_transition()`

```python
def update_task_status(
    self,
    task_id: str,
    status: str,
    agent_name: str | None = None,
    description: str | None = None,
) -> Any:
    """
    Update a task's status with retry and logging.

    Args:
        task_id: Convex task document ID
        status: New TaskStatus value (e.g., "in_progress")
        agent_name: Agent performing the transition (optional)
        description: Human-readable description for activity log (optional)
    """
    result = self._mutation_with_retry(
        "tasks:updateStatus",
        {
            "task_id": task_id,
            "status": status,
            "agent_name": agent_name or "",
        },
    )
    self._log_state_transition(
        "task",
        description or f"Task status changed to {status}"
        + (f" by {agent_name}" if agent_name else ""),
    )
    return result


def update_agent_status(
    self,
    agent_name: str,
    status: str,
    description: str | None = None,
) -> Any:
    """
    Update an agent's status with retry and logging.

    Args:
        agent_name: Agent name
        status: New AgentStatus value (e.g., "active")
        description: Human-readable description for activity log (optional)
    """
    result = self._mutation_with_retry(
        "agents:updateStatus",
        {"agent_name": agent_name, "status": status},
    )
    self._log_state_transition(
        "agent",
        description or f"Agent '{agent_name}' status changed to {status}",
    )
    return result


def create_activity(
    self,
    event_type: str,
    description: str,
    task_id: str | None = None,
    agent_name: str | None = None,
) -> Any:
    """
    Create an activity event with retry and logging.

    Args:
        event_type: ActivityEventType value (e.g., "task_created")
        description: Human-readable event description
        task_id: Optional related task ID
        agent_name: Optional related agent name
    """
    args: dict[str, Any] = {
        "event_type": event_type,
        "description": description,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if task_id:
        args["task_id"] = task_id
    if agent_name:
        args["agent_name"] = agent_name

    result = self._mutation_with_retry("activities:create", args)
    self._log_state_transition("activity", description)
    return result


def send_message(
    self,
    task_id: str,
    author_name: str,
    author_type: str,
    content: str,
    message_type: str,
) -> Any:
    """
    Send a task-scoped message with retry and logging.

    Args:
        task_id: Convex task document ID
        author_name: Message author name
        author_type: AuthorType value ("agent", "user", "system")
        content: Message text
        message_type: MessageType value ("work", "review_feedback", etc.)
    """
    result = self._mutation_with_retry(
        "messages:create",
        {
            "task_id": task_id,
            "author_name": author_name,
            "author_type": author_type,
            "content": content,
            "message_type": message_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    self._log_state_transition(
        "message",
        f"Message sent by {author_name} on task {task_id}",
    )
    return result
```

**Note on `update_task_status` and activity events**: The `tasks:updateStatus` Convex mutation (implemented in Story 2.4) internally writes both the status change AND the corresponding activity event in the same transaction. The bridge method `update_task_status()` calls this single mutation. The bridge does NOT call `activities:create` separately — that would be redundant and break the transactional guarantee.

### Updated `mutation()` Public Method

The existing `mutation()` method from Story 1.3 must be updated to use `_mutation_with_retry()`:

```python
def mutation(self, function_name: str, args: dict[str, Any] | None = None) -> Any:
    """
    Call a Convex mutation function with retry.

    Args:
        function_name: Convex function in colon notation (e.g., "tasks:create")
        args: Optional arguments dict (snake_case keys — converted to camelCase)

    Returns:
        Mutation result (if any) with camelCase keys converted to snake_case
    """
    return self._mutation_with_retry(function_name, args)
```

The `query()` method remains UNCHANGED — no retry logic for reads.

### Common LLM Developer Mistakes to Avoid

1. **DO NOT retry queries** — Only mutations are retried. Queries are idempotent reads. If the caller needs retry, they implement it themselves.

2. **DO NOT retry the best-effort error activity write** — Using `_mutation_with_retry()` for the error activity event would create an infinite retry loop. Call `self._client.mutation()` directly, wrapped in a bare try/except.

3. **DO NOT swallow exceptions after retry exhaustion** — The bridge MUST re-raise the last exception after logging and the best-effort activity write. The caller (gateway, orchestrator) needs to know the mutation failed so it can handle accordingly (e.g., mark agent as crashed).

4. **DO NOT use `asyncio.sleep()`** — The bridge is synchronous (Story 1.3 design decision). Use `time.sleep()` for the backoff delay. AsyncIO callers wrap the entire call in `asyncio.to_thread()`.

5. **DO NOT make a separate `activities:create` call for every state transition** — The Convex mutation handler (TypeScript) writes the activity event in the same transaction. The bridge calls ONE mutation, not two. The bridge's stdout logging is the Python-side half of "dual logging."

6. **DO NOT use `print()` for logging** — Use Python's `logging` module with `logger = logging.getLogger(__name__)`. This integrates with nanobot's existing logging infrastructure and allows log level configuration.

7. **DO NOT log sensitive data** — Mutation arguments may contain task content. Log the mutation name and error message, but be cautious about logging full argument dicts in production. For MVP, full argument logging is acceptable for debugging.

8. **DO NOT make the backoff delays configurable** — For MVP, hardcode 1s/2s/4s. Making delays configurable adds complexity without value at this stage. The constants `MAX_RETRIES = 3` and `BACKOFF_BASE_SECONDS = 1` at the top of the file are sufficient.

9. **DO NOT add jitter to backoff** — Simple exponential backoff (1s, 2s, 4s) is sufficient for MVP with a single client. Jitter is a optimization for multiple concurrent clients hitting the same service — not applicable here.

10. **DO NOT create a separate retry utility module** — The retry logic lives in `bridge.py` as a private method. There's no need for a generic retry decorator or utility at this stage.

11. **DO NOT change the `subscribe()` method** — Subscriptions are long-lived iterators. If a subscription disconnects, the `ConvexClient` handles reconnection internally. The bridge does not add retry to subscriptions.

12. **DO NOT forget to update existing tests** — The `mutation()` method behavior changes (it now retries). Existing tests from Story 1.3 that mock `ConvexClient.mutation()` must still pass, but may need updating to account for the retry wrapper.

### Test Strategy

Tests are added to the existing `nanobot/mc/test_bridge.py` file (co-located, extending Story 1.3 tests).

**Mocking approach:**

```python
import time
from unittest.mock import MagicMock, patch, call
from convex import ConvexError


def test_mutation_retry_succeeds_on_attempt_2():
    """Mutation fails once, succeeds on retry."""
    with patch("nanobot.mc.bridge.ConvexClient") as MockClient:
        mock_client = MockClient.return_value
        mock_client.mutation.side_effect = [
            Exception("Connection timeout"),  # Attempt 1 fails
            {"_id": "abc123"},                # Attempt 2 succeeds
        ]

        with patch("nanobot.mc.bridge.time.sleep") as mock_sleep:
            bridge = ConvexBridge("https://test.convex.cloud")
            result = bridge.mutation("tasks:create", {"title": "Test"})

            assert mock_client.mutation.call_count == 2
            mock_sleep.assert_called_once_with(1)  # 1s backoff after attempt 1
            assert result is not None


def test_mutation_retry_exhaustion():
    """Mutation fails 3 times, raises exception."""
    with patch("nanobot.mc.bridge.ConvexClient") as MockClient:
        mock_client = MockClient.return_value
        mock_client.mutation.side_effect = Exception("Convex unavailable")

        with patch("nanobot.mc.bridge.time.sleep"):
            bridge = ConvexBridge("https://test.convex.cloud")

            with pytest.raises(Exception, match="Convex unavailable"):
                bridge.mutation("tasks:create", {"title": "Test"})

            # 3 mutation attempts + 1 best-effort error activity
            assert mock_client.mutation.call_count == 4


def test_retry_exhaustion_best_effort_activity_failure():
    """Best-effort error activity write also fails — no cascading exception."""
    with patch("nanobot.mc.bridge.ConvexClient") as MockClient:
        mock_client = MockClient.return_value
        # All calls fail — including the best-effort error activity
        mock_client.mutation.side_effect = Exception("Total failure")

        with patch("nanobot.mc.bridge.time.sleep"):
            bridge = ConvexBridge("https://test.convex.cloud")

            with pytest.raises(Exception, match="Total failure"):
                bridge.mutation("tasks:create", {"title": "Test"})

            # 3 retry attempts + 1 best-effort (also fails, silently caught)
            assert mock_client.mutation.call_count == 4


def test_exponential_backoff_timing():
    """Verify backoff delays: 1s, 2s (attempt 3 raises, no further sleep)."""
    with patch("nanobot.mc.bridge.ConvexClient") as MockClient:
        mock_client = MockClient.return_value
        mock_client.mutation.side_effect = Exception("fail")

        with patch("nanobot.mc.bridge.time.sleep") as mock_sleep:
            bridge = ConvexBridge("https://test.convex.cloud")

            with pytest.raises(Exception):
                bridge.mutation("tasks:create", {"title": "Test"})

            # Sleep called after attempt 1 (1s) and attempt 2 (2s)
            # No sleep after attempt 3 (exhaustion)
            assert mock_sleep.call_args_list == [call(1), call(2)]


def test_query_not_retried():
    """Query failures are not retried."""
    with patch("nanobot.mc.bridge.ConvexClient") as MockClient:
        mock_client = MockClient.return_value
        mock_client.query.side_effect = Exception("Query failed")

        bridge = ConvexBridge("https://test.convex.cloud")

        with pytest.raises(Exception, match="Query failed"):
            bridge.query("tasks:list")

        assert mock_client.query.call_count == 1  # No retry


def test_successful_retry_no_error_activity():
    """When retry succeeds, no error activity event is written."""
    with patch("nanobot.mc.bridge.ConvexClient") as MockClient:
        mock_client = MockClient.return_value
        mock_client.mutation.side_effect = [
            Exception("Temporary failure"),
            {"_id": "success"},  # Attempt 2 succeeds
        ]

        with patch("nanobot.mc.bridge.time.sleep"):
            bridge = ConvexBridge("https://test.convex.cloud")
            bridge.mutation("tasks:create", {"title": "Test"})

            # Only 2 calls: the failed attempt and the success
            # No additional best-effort error activity call
            assert mock_client.mutation.call_count == 2
```

### What This Story Does NOT Include

- **No Convex mutation implementations (TypeScript)** — The `tasks:updateStatus`, `agents:updateStatus`, `activities:create`, and `messages:create` mutations are implemented in later stories (Stories 2.2, 2.4, 3.2). This story adds Python-side convenience methods that CALL those mutations. The mutations must exist before these convenience methods can be tested end-to-end.
- **No gateway or orchestrator** — Those start in Stories 1.5 and 4.1
- **No state machine validation** — Valid state transitions are validated in Story 2.4's Convex mutation and Python state machine
- **No dashboard changes** — This story is purely Python
- **No async methods** — Bridge remains synchronous (Story 1.3 decision)

### Files Modified in This Story

| File | Changes |
|------|---------|
| `nanobot/mc/bridge.py` | Add `_mutation_with_retry()`, `_write_error_activity()`, `_log_state_transition()`, convenience methods (`update_task_status()`, `update_agent_status()`, `create_activity()`, `send_message()`). Update `mutation()` to use retry wrapper. Add `import time` and `from datetime import datetime, timezone`. |
| `nanobot/mc/test_bridge.py` | Add test cases for retry logic, exhaustion, backoff timing, dual logging, query non-retry |

### Files Created in This Story

None. This story only modifies files created in Story 1.3.

### Import Additions to bridge.py

```python
import time
from datetime import datetime, timezone
```

These are standard library imports — no new dependencies.

### Verification Steps

1. `python -m pytest nanobot/mc/test_bridge.py -v` — all tests pass (both Story 1.3 and new Story 1.4 tests)
2. `wc -l nanobot/mc/bridge.py` — output is < 500 lines
3. Verify logging output: run a test that triggers retry and check stdout contains `[MC]` prefixed log lines
4. `grep -r "from convex" nanobot/` — still only `nanobot/mc/bridge.py` (no new convex imports added elsewhere)

### References

- [Source: `_bmad-output/planning-artifacts/architecture.md#Communication Patterns`] — Python bridge call pattern: `_call_mutation_with_retry()` pattern with try-retry-log
- [Source: `_bmad-output/planning-artifacts/architecture.md#Process Patterns`] — Error handling per layer: "Python bridge: Catch, retry 3x with exponential backoff, then log + write error activity"
- [Source: `_bmad-output/planning-artifacts/architecture.md#Enforcement Guidelines`] — Rule 2: "Never change task status without writing a corresponding activity event"
- [Source: `_bmad-output/planning-artifacts/epics.md#Story 1.4`] — Original story definition with acceptance criteria
- [Source: `_bmad-output/planning-artifacts/prd.md#NFR15`] — "AsyncIO-Convex bridge retries failed writes up to 3 times with exponential backoff; surfaces error on activity feed only after retry exhaustion"
- [Source: `_bmad-output/planning-artifacts/prd.md#NFR23`] — "All agent and task state transitions are logged to both the activity feed (Convex) and local stdout for debugging"
- [Source: `_bmad-output/planning-artifacts/prd.md#NFR21`] — 500-line module limit
- [Source: `_bmad-output/implementation-artifacts/1-3-build-asyncio-convex-bridge-core.md`] — ConvexBridge class design, SDK API, synchronous design decision, test patterns

## Review Findings

### Issues Found and Fixed

1. **MEDIUM: Retry count contradicted AC #1** -- AC #1 says "retries up to 3 times with exponential backoff (1s, 2s, 4s delays)." The implementation only did 3 total attempts (initial + 2 retries) with delays 1s, 2s. Fixed to 4 total attempts (initial + 3 retries) with delays 1s, 2s, 4s matching the AC exactly. `MAX_RETRIES = 3` now means 3 retries after the initial attempt.

2. **LOW: Error activity description was inaccurate** -- The best-effort error activity said "failed after 3 retries" but with the fix it should say "failed after 4 attempts (3 retries)". Updated for accuracy.

### Tests Added/Updated
- `test_retry_succeeds_on_attempt_4` -- new test: mutation fails 3 times, succeeds on 4th (last) attempt with delays [1s, 2s, 4s]
- `test_retry_exhaustion_raises` -- updated: expects 5 mutation calls (4 attempts + 1 best-effort)
- `test_retry_exhaustion_best_effort_activity` -- updated: 4 failures + best-effort at index 4
- `test_best_effort_activity_failure_silent` -- updated: 5 total calls
- `test_exponential_backoff_timing` -- updated: expects [1s, 2s, 4s] delays
- `test_retry_success_logs_attempt` -- updated: expects "2/4" in log message
- `test_retry_failure_logs_error` -- updated: expects "4 attempts" in log message
- Total tests: 75 (up from 71)

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
None -- all 71 tests pass cleanly.

### Completion Notes List
- Added `_mutation_with_retry()` with exponential backoff (1s, 2s delays; MAX_RETRIES=3)
- Updated `mutation()` to delegate to `_mutation_with_retry()`
- Added `_write_error_activity()` -- best-effort system_error activity on exhaustion, uses `self._client.mutation()` directly (not retried)
- Added `_log_state_transition()` with `[MC]` prefix for stdout dual logging
- Added 4 convenience methods: `update_task_status()`, `update_agent_status()`, `create_activity()`, `send_message()`
- All convenience methods use `_mutation_with_retry()` internally
- `query()` remains unchanged -- no retry for reads
- bridge.py is 274 lines (well under 500-line NFR21 limit)
- 71 total tests pass (54 from Story 1.3 + 17 new Story 1.4 tests)
- Added `import time` and `from datetime import datetime, timezone` (stdlib only, no new deps)
- Existing Story 1.3 tests updated to account for retry behavior (added `mock_sleep` where needed)

### File List
- `nanobot/mc/bridge.py` -- Modified: added retry, logging, convenience methods (274 lines)
- `nanobot/mc/test_bridge.py` -- Modified: added 17 new tests for retry, logging, convenience methods (71 total)
