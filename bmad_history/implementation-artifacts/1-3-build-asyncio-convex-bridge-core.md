# Story 1.3: Build AsyncIO-Convex Bridge Core

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want a Python bridge module that connects the nanobot AsyncIO runtime to Convex via the Python SDK,
So that agents can read and write shared state through a single, well-defined integration point.

## Acceptance Criteria

1. **Given** the Convex schema is defined (Story 1.2), **When** the developer creates `nanobot/mc/bridge.py`, **Then** a `ConvexBridge` class exists that can establish a connection to a Convex deployment using a deployment URL
2. **Given** a `ConvexBridge` instance is connected, **When** a mutation is called with Python dict arguments, **Then** the bridge calls the Convex mutation and field names are converted from snake_case to camelCase at the boundary
3. **Given** a `ConvexBridge` instance is connected, **When** a query is called, **Then** the bridge returns results as Python dicts with field names converted from camelCase to snake_case
4. **Given** a `ConvexBridge` instance is connected, **When** a subscription is created, **Then** the bridge receives real-time updates via the Convex Python SDK subscribe mechanism and converts field names from camelCase to snake_case
5. **Given** outgoing data is sent from Python to Convex, **When** the bridge processes the arguments, **Then** ALL dict keys are converted from snake_case to camelCase (e.g., `assigned_agent` becomes `assignedAgent`)
6. **Given** incoming data is received from Convex to Python, **When** the bridge processes the results, **Then** ALL dict keys are converted from camelCase to snake_case (e.g., `assignedAgent` becomes `assigned_agent`)
7. **Given** the bridge module is created, **Then** `nanobot/mc/__init__.py` exists making `nanobot.mc` a valid Python package
8. **Given** the bridge module is created, **Then** `nanobot/mc/types.py` exists with shared Python dataclasses/enums for TaskStatus, TrustLevel, AgentStatus, ActivityEventType, MessageType, and AuthorType — mirroring the exact string values from Story 1.2
9. **Given** the bridge module is created, **Then** `bridge.py` is the ONLY Python module in the entire codebase that imports the `convex` Python SDK package
10. **Given** the bridge module is created, **Then** unit tests exist in `nanobot/mc/test_bridge.py` covering connection, mutation calls, query calls, and case conversion
11. **Given** the bridge module is created, **Then** `bridge.py` does NOT exceed 500 lines (NFR21)

## Tasks / Subtasks

- [x] Task 1: Create the `nanobot/mc/` package structure (AC: #7, #8)
  - [x] 1.1: Create `nanobot/mc/__init__.py` with package docstring
  - [x] 1.2: Create `nanobot/mc/types.py` with all shared Python types (dataclasses and string enums)
  - [x] 1.3: Verify `from nanobot.mc.types import TaskStatus` works from project root
- [x] Task 2: Implement the `ConvexBridge` class (AC: #1, #2, #3, #4, #5, #6, #9, #11)
  - [x] 2.1: Create `nanobot/mc/bridge.py` with `ConvexBridge` class
  - [x] 2.2: Implement `__init__` with Convex deployment URL parameter and optional admin auth key
  - [x] 2.3: Implement `_to_camel_case()` and `_to_snake_case()` private helper functions for key conversion
  - [x] 2.4: Implement `_convert_keys_to_camel()` and `_convert_keys_to_snake()` for recursive dict key conversion
  - [x] 2.5: Implement `query()` method — calls Convex query and returns snake_case results
  - [x] 2.6: Implement `mutation()` method — converts args to camelCase and calls Convex mutation
  - [x] 2.7: Implement `subscribe()` method — wraps Convex subscription with snake_case conversion on received data
  - [x] 2.8: Verify the module does not exceed 500 lines (124 lines)
  - [x] 2.9: Verify no other module in `nanobot/mc/` imports from `convex` directly
- [x] Task 3: Write unit tests (AC: #10)
  - [x] 3.1: Create `nanobot/mc/test_bridge.py`
  - [x] 3.2: Test `_to_camel_case` conversion (snake_case to camelCase)
  - [x] 3.3: Test `_to_snake_case` conversion (camelCase to snake_case)
  - [x] 3.4: Test `_convert_keys_to_camel` with nested dicts and lists
  - [x] 3.5: Test `_convert_keys_to_snake` with nested dicts and lists
  - [x] 3.6: Test `query()` method (mock ConvexClient)
  - [x] 3.7: Test `mutation()` method (mock ConvexClient)
  - [x] 3.8: Test edge cases: empty dicts, already-correct casing, single-word keys

## Dev Notes

### Critical Architecture Requirements

- **Boundary 1**: `bridge.py` is the ONLY Python module that imports the `convex` Python SDK. All other Python modules (`gateway.py`, `orchestrator.py`, `state_machine.py`, etc.) call `bridge.py` methods — NEVER import `convex` directly.
- **One-directional writes (NFR16)**: Only the nanobot backend writes to Convex. The dashboard is read-only plus user actions via Convex mutations. The bridge enforces this by being the single write path.
- **500-line limit (NFR21)**: `bridge.py` must not exceed 500 lines. Retry logic is handled in Story 1.4, so this story keeps the bridge lean.
- **No retry logic in this story**: Retry with exponential backoff is Story 1.4. This story implements the core connection, query, mutation, and subscription methods WITHOUT retry wrapping.
- **No dual logging in this story**: Logging to both stdout and Convex activity feed is Story 1.4. This story may include basic `logging` module usage for debugging, but not the dual-logging pattern.

### Convex Python SDK API Reference

**Package**: `convex` (PyPI), version 0.7.0
**Install**: `pip install convex`
**License**: Apache-2.0
**Min Python**: 3.9

#### Core Client

```python
from convex import ConvexClient

# Create client with deployment URL
client = ConvexClient("https://example-lion-123.convex.cloud")

# Optional: set admin auth for server-side access
client.set_admin_auth("admin-key-from-convex-dashboard")

# Optional: enable debug logging
client.set_debug(True)
```

#### Function Call Format

Convex functions are called using **colon notation** — `"filename:functionName"`:

```python
# Query: "tasks:list" means file convex/tasks.ts, export "list"
result = client.query("tasks:list")

# Mutation: "tasks:create" means file convex/tasks.ts, export "create"
client.mutation("tasks:create", {"title": "Research AI trends", "status": "inbox"})

# With arguments as dict
messages = client.query("messages:listByTask", {"taskId": "jd7abc123..."})
```

**CRITICAL**: Use colon notation `"tasks:create"`, NOT dot notation `"tasks.create"`. The colon separates the filename from the exported function name.

#### Subscriptions

```python
# Subscribe returns an iterator that yields on each update
for result in client.subscribe("tasks:list", {}):
    print(f"Tasks updated: {len(result)} tasks")
    # Loop continues until interrupted
```

The subscription is blocking (uses an iterator pattern). For integration with AsyncIO, the bridge should run subscriptions in a background thread or use `asyncio.to_thread()`.

#### Type Mappings (Python to Convex)

| Python Type | Convex Type | Notes |
|------------|-------------|-------|
| `None` | `null` | |
| `bool` | `boolean` | |
| `int` | `Float64` | Python ints convert to Float64 |
| `float` | `Float64` | |
| `str` | `string` | |
| `bytes` | `ArrayBuffer` | |
| `list` | `Array` | |
| `dict` | `object` | **Keys must be camelCase for Convex** |
| `ConvexInt64` | `bigint` | `from convex import ConvexInt64` |

#### Error Handling

```python
import convex

try:
    client.mutation("tasks:create", args)
except convex.ConvexError as err:
    # err.data contains application-specific error info
    if isinstance(err.data, str):
        print(f"Convex error: {err.data}")
    elif isinstance(err.data, dict):
        print(f"Error code: {err.data.get('code')}")
except Exception as err:
    # Network errors, connection failures, etc.
    print(f"Connection error: {err}")
```

### ConvexBridge Class Design

```python
"""
ConvexBridge — Single integration point between nanobot AsyncIO runtime and Convex.

This is the ONLY module in the nanobot codebase that imports the `convex` Python SDK.
All other modules interact with Convex exclusively through this bridge.
"""

import logging
from typing import Any, Iterator

from convex import ConvexClient, ConvexError

logger = logging.getLogger(__name__)


class ConvexBridge:
    """Bridge between nanobot Python runtime and Convex backend."""

    def __init__(self, deployment_url: str, admin_key: str | None = None):
        """
        Initialize the Convex bridge.

        Args:
            deployment_url: Convex deployment URL (e.g., "https://example.convex.cloud")
            admin_key: Optional admin key for server-side auth
        """
        ...

    def query(self, function_name: str, args: dict[str, Any] | None = None) -> Any:
        """
        Call a Convex query function.

        Args:
            function_name: Convex function in colon notation (e.g., "tasks:list")
            args: Optional arguments dict (snake_case keys — converted to camelCase)

        Returns:
            Query result with camelCase keys converted to snake_case
        """
        ...

    def mutation(self, function_name: str, args: dict[str, Any] | None = None) -> Any:
        """
        Call a Convex mutation function.

        Args:
            function_name: Convex function in colon notation (e.g., "tasks:create")
            args: Optional arguments dict (snake_case keys — converted to camelCase)

        Returns:
            Mutation result (if any) with camelCase keys converted to snake_case
        """
        ...

    def subscribe(self, function_name: str, args: dict[str, Any] | None = None) -> Iterator[Any]:
        """
        Subscribe to a Convex query for real-time updates.

        Args:
            function_name: Convex query in colon notation (e.g., "tasks:list")
            args: Optional arguments dict (snake_case keys — converted to camelCase)

        Yields:
            Updated results with camelCase keys converted to snake_case
        """
        ...
```

### Case Conversion Implementation

The bridge must convert dict keys at the boundary. Conversion must be **recursive** — nested dicts and dicts inside lists must also have their keys converted.

#### snake_case to camelCase (outgoing: Python to Convex)

```python
def _to_camel_case(snake_str: str) -> str:
    """Convert a snake_case string to camelCase."""
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])

# Examples:
# "assigned_agent"    -> "assignedAgent"
# "trust_level"       -> "trustLevel"
# "created_at"        -> "createdAt"
# "inter_agent_timeout" -> "interAgentTimeout"
# "name"              -> "name" (single word, no change)
# "task_id"           -> "taskId"
```

#### camelCase to snake_case (incoming: Convex to Python)

```python
import re

def _to_snake_case(camel_str: str) -> str:
    """Convert a camelCase string to snake_case."""
    s1 = re.sub(r"([A-Z])", r"_\1", camel_str)
    return s1.lower().lstrip("_")

# Examples:
# "assignedAgent"      -> "assigned_agent"
# "trustLevel"         -> "trust_level"
# "createdAt"          -> "created_at"
# "interAgentTimeout"  -> "inter_agent_timeout"
# "name"               -> "name" (single word, no change)
# "taskId"             -> "task_id"
```

#### Recursive Key Conversion

```python
def _convert_keys_to_camel(data: Any) -> Any:
    """Recursively convert all dict keys from snake_case to camelCase."""
    if isinstance(data, dict):
        return {_to_camel_case(k): _convert_keys_to_camel(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_convert_keys_to_camel(item) for item in data]
    return data

def _convert_keys_to_snake(data: Any) -> Any:
    """Recursively convert all dict keys from camelCase to snake_case."""
    if isinstance(data, dict):
        return {_to_snake_case(k): _convert_keys_to_snake(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_convert_keys_to_snake(item) for item in data]
    return data
```

### Cross-Boundary Naming Convention (Complete Reference)

This table shows ALL field name conversions the bridge handles. Copied from Story 1.2 for developer convenience:

| Python (snake_case) | Convex (camelCase) |
|---------------------|-------------------|
| `title` | `title` |
| `description` | `description` |
| `status` | `status` |
| `assigned_agent` | `assignedAgent` |
| `trust_level` | `trustLevel` |
| `reviewers` | `reviewers` |
| `tags` | `tags` |
| `task_timeout` | `taskTimeout` |
| `inter_agent_timeout` | `interAgentTimeout` |
| `created_at` | `createdAt` |
| `updated_at` | `updatedAt` |
| `task_id` | `taskId` |
| `author_name` | `authorName` |
| `author_type` | `authorType` |
| `content` | `content` |
| `message_type` | `messageType` |
| `timestamp` | `timestamp` |
| `name` | `name` |
| `display_name` | `displayName` |
| `role` | `role` |
| `skills` | `skills` |
| `model` | `model` |
| `last_active_at` | `lastActiveAt` |
| `agent_name` | `agentName` |
| `event_type` | `eventType` |
| `key` | `key` |
| `value` | `value` |

Single-word keys (`title`, `status`, `name`, etc.) are unchanged by conversion. The bridge handles this correctly because `_to_camel_case("name")` returns `"name"` and `_to_snake_case("name")` returns `"name"`.

### `nanobot/mc/types.py` Specification

This module defines Python-side types that mirror the Convex schema enum values. These are the ONLY place enum string values are defined on the Python side.

```python
"""
Shared Python types for Mission Control.

These types mirror the Convex schema defined in dashboard/convex/schema.ts.
String values MUST match exactly — any mismatch will cause runtime errors.
"""

from dataclasses import dataclass, field
from enum import StrEnum


class TaskStatus(StrEnum):
    """Task lifecycle states. Matches Convex tasks.status union type."""
    INBOX = "inbox"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"
    RETRYING = "retrying"
    CRASHED = "crashed"


class TrustLevel(StrEnum):
    """Trust levels for task oversight. Matches Convex tasks.trustLevel union type."""
    AUTONOMOUS = "autonomous"
    AGENT_REVIEWED = "agent_reviewed"
    HUMAN_APPROVED = "human_approved"


class AgentStatus(StrEnum):
    """Agent runtime states. Matches Convex agents.status union type."""
    ACTIVE = "active"
    IDLE = "idle"
    CRASHED = "crashed"


class ActivityEventType(StrEnum):
    """Activity feed event types. Matches Convex activities.eventType union type."""
    TASK_CREATED = "task_created"
    TASK_ASSIGNED = "task_assigned"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_CRASHED = "task_crashed"
    TASK_RETRYING = "task_retrying"
    REVIEW_REQUESTED = "review_requested"
    REVIEW_FEEDBACK = "review_feedback"
    REVIEW_APPROVED = "review_approved"
    HITL_REQUESTED = "hitl_requested"
    HITL_APPROVED = "hitl_approved"
    HITL_DENIED = "hitl_denied"
    AGENT_CONNECTED = "agent_connected"
    AGENT_DISCONNECTED = "agent_disconnected"
    AGENT_CRASHED = "agent_crashed"
    SYSTEM_ERROR = "system_error"


class MessageType(StrEnum):
    """Message categories. Matches Convex messages.messageType union type."""
    WORK = "work"
    REVIEW_FEEDBACK = "review_feedback"
    APPROVAL = "approval"
    DENIAL = "denial"
    SYSTEM_EVENT = "system_event"


class AuthorType(StrEnum):
    """Message author types. Matches Convex messages.authorType union type."""
    AGENT = "agent"
    USER = "user"
    SYSTEM = "system"


@dataclass
class TaskData:
    """Python representation of a Convex task document (snake_case fields)."""
    title: str
    status: str  # TaskStatus value
    trust_level: str  # TrustLevel value
    created_at: str  # ISO 8601
    updated_at: str  # ISO 8601
    description: str | None = None
    assigned_agent: str | None = None
    reviewers: list[str] | None = None
    tags: list[str] | None = None
    task_timeout: float | None = None
    inter_agent_timeout: float | None = None
    id: str | None = None  # Convex _id (populated on read)


@dataclass
class AgentData:
    """Python representation of a Convex agent document (snake_case fields)."""
    name: str
    display_name: str
    role: str
    skills: list[str] = field(default_factory=list)
    status: str = "idle"  # AgentStatus value
    model: str | None = None
    last_active_at: str | None = None
    id: str | None = None  # Convex _id (populated on read)


@dataclass
class MessageData:
    """Python representation of a Convex message document (snake_case fields)."""
    task_id: str
    author_name: str
    author_type: str  # AuthorType value
    content: str
    message_type: str  # MessageType value
    timestamp: str  # ISO 8601
    id: str | None = None  # Convex _id (populated on read)


@dataclass
class ActivityData:
    """Python representation of a Convex activity document (snake_case fields)."""
    event_type: str  # ActivityEventType value
    description: str
    timestamp: str  # ISO 8601
    task_id: str | None = None
    agent_name: str | None = None
    id: str | None = None  # Convex _id (populated on read)
```

**Key decisions:**
- Uses `StrEnum` (Python 3.11+) for enum types — values are the exact strings that match Convex schema. If the project needs Python 3.9 compatibility, fall back to `str` + `Enum` combination.
- Dataclasses use snake_case field names — the bridge converts to/from camelCase.
- The `id` field on dataclasses maps to Convex's auto-generated `_id`. The bridge handles `_id` to `id` conversion.
- Dataclasses are optional convenience types — the bridge works with plain dicts. Other modules MAY use these types for clarity.

### `nanobot/mc/__init__.py` Specification

```python
"""
nanobot Mission Control — Multi-agent orchestration platform.

This package provides the Python-side components for Mission Control:
- bridge: ConvexBridge for Convex backend communication
- types: Shared Python types mirroring the Convex schema
- gateway: Agent Gateway (Story 1.5+)
- orchestrator: Lead Agent routing (Story 4.1+)
- state_machine: Task state transitions (Story 2.4+)
- yaml_validator: Agent YAML validation (Story 3.1+)
- process_manager: Subprocess management (Story 1.5+)
"""
```

### Handling Convex `_id` and `_creationTime`

Convex auto-generates `_id` (document ID) and `_creationTime` (epoch timestamp) for every document. The bridge must handle these special fields:

- **Incoming** (Convex to Python): `_id` is converted to `id` (strip the underscore). `_creationTime` is converted to `creation_time`.
- **Outgoing** (Python to Convex): `id` is NOT sent back — Convex manages `_id` internally. If the caller passes `task_id` as an argument to a mutation, the bridge converts it to `taskId` as normal.

Special conversion rules for underscore-prefixed Convex fields:

```python
def _to_snake_case(camel_str: str) -> str:
    """Convert a camelCase string to snake_case. Handles Convex _prefixed fields."""
    if camel_str.startswith("_"):
        # Strip leading underscore, convert rest, keep as-is
        # _id -> id, _creationTime -> creation_time
        inner = camel_str[1:]
        s1 = re.sub(r"([A-Z])", r"_\1", inner)
        return s1.lower().lstrip("_")
    s1 = re.sub(r"([A-Z])", r"_\1", camel_str)
    return s1.lower().lstrip("_")
```

### AsyncIO Integration Strategy

The Convex Python SDK (`ConvexClient`) is **synchronous** — it uses blocking calls for queries, mutations, and a blocking iterator for subscriptions. The nanobot runtime is **AsyncIO-based**.

**Integration approach for this story:**
- The `ConvexBridge` class exposes **synchronous** methods (`query()`, `mutation()`, `subscribe()`) that wrap `ConvexClient` directly.
- Callers in the AsyncIO runtime use `asyncio.to_thread()` to run bridge methods in a thread pool without blocking the event loop.
- The bridge itself does NOT import `asyncio` — keeping it simple and testable.

**Example caller pattern (for later stories):**

```python
# In gateway.py or orchestrator.py (AsyncIO context):
import asyncio

bridge = ConvexBridge("https://example.convex.cloud")

# Non-blocking mutation call
result = await asyncio.to_thread(
    bridge.mutation,
    "tasks:updateStatus",
    {"task_id": task_id, "status": "in_progress", "agent_name": agent_name}
)

# Non-blocking query call
tasks = await asyncio.to_thread(bridge.query, "tasks:list")
```

This pattern is documented here so the developer understands the design intent, but the `asyncio.to_thread()` calls are implemented by callers (Story 1.5+), NOT by `bridge.py`.

### Common LLM Developer Mistakes to Avoid

1. **DO NOT use dot notation for function names** — Use `"tasks:create"` (colon), NOT `"tasks.create"` (dot). The Convex Python SDK uses colon notation to separate file from function.

2. **DO NOT import `convex` from any module other than `bridge.py`** — This is a hard architectural boundary. `gateway.py`, `orchestrator.py`, `state_machine.py`, and all other modules call `bridge.query()` and `bridge.mutation()` — they never import `ConvexClient` directly.

3. **DO NOT add retry logic** — Retry with exponential backoff is Story 1.4. This story implements the core methods without retry wrapping. Keep it simple.

4. **DO NOT add logging to Convex activity feed** — Dual logging (stdout + Convex) is Story 1.4. This story may use Python's `logging` module for local debug output only.

5. **DO NOT make the bridge async** — The `ConvexClient` is synchronous. The bridge exposes synchronous methods. AsyncIO callers use `asyncio.to_thread()`. Do not add `async def` to bridge methods.

6. **DO NOT forget recursive key conversion** — Converting only top-level dict keys is insufficient. Nested objects (e.g., a task with a nested tags array or a settings dict) must also have their keys converted.

7. **DO NOT convert non-dict values** — Only dict keys are converted. String values, list items that are strings, numbers, etc. are passed through unchanged. `"in_progress"` (a status value) must NOT be converted to `"inProgress"`.

8. **DO NOT convert Convex document IDs** — Document IDs (strings like `"jd7abc123..."`) are opaque values — never convert their content. Only dict KEYS are converted.

9. **DO NOT create a ConvexClient per method call** — Create one `ConvexClient` in `__init__` and reuse it across all method calls. The client manages its own connection state.

10. **DO NOT use pydantic in bridge.py** — The bridge works with plain Python dicts. The `types.py` dataclasses are optional convenience types used by callers. The bridge itself converts and passes dicts.

11. **DO NOT exceed 500 lines** — If the module approaches this limit, the developer has over-engineered it. The core bridge without retry logic should be well under 200 lines.

12. **DO NOT hardcode the deployment URL** — The URL is passed as a constructor parameter. It comes from environment variables (`CONVEX_URL`) managed by the caller.

### Test Strategy

Tests go in `nanobot/mc/test_bridge.py` (co-located with source, using pytest naming convention `test_*.py` that matches the existing nanobot testing pattern).

**Test categories:**

1. **Case conversion unit tests** (no mocking needed):
   - `_to_camel_case`: single word, two words, three+ words, already camelCase
   - `_to_snake_case`: single word, two words, three+ words, already snake_case, underscore-prefixed (`_id`, `_creationTime`)
   - `_convert_keys_to_camel`: flat dict, nested dict, list of dicts, empty dict, mixed (dict + list + primitives)
   - `_convert_keys_to_snake`: same cases as above

2. **Bridge method tests** (mock `ConvexClient`):
   - `query()`: calls `client.query()` with camelCase args, returns snake_case result
   - `mutation()`: calls `client.mutation()` with camelCase args
   - `subscribe()`: yields snake_case-converted results
   - Error propagation: `ConvexError` raised by client is not swallowed

3. **Edge cases**:
   - `None` args (no arguments to mutation/query)
   - Empty dict args
   - Keys that are already in the target case (no double-conversion)
   - Value strings containing underscores or uppercase are NOT converted (only keys)

**Mocking approach:**

```python
from unittest.mock import MagicMock, patch

def test_query_converts_keys():
    with patch("nanobot.mc.bridge.ConvexClient") as MockClient:
        mock_client = MockClient.return_value
        mock_client.query.return_value = [
            {"taskId": "abc", "assignedAgent": "financeiro", "createdAt": "2026-02-22T10:00:00Z"}
        ]

        bridge = ConvexBridge("https://test.convex.cloud")
        result = bridge.query("tasks:list")

        assert result[0]["task_id"] == "abc"
        assert result[0]["assigned_agent"] == "financeiro"
        assert result[0]["created_at"] == "2026-02-22T10:00:00Z"
```

### What This Story Does NOT Include

- **No retry logic** — That is Story 1.4 (Add Bridge Retry Logic & Dual Logging)
- **No dual logging (stdout + Convex activity feed)** — That is Story 1.4
- **No gateway or orchestrator** — Those start in Stories 1.5 and 4.1
- **No state machine** — That is Story 2.4
- **No CLI commands** — Those start in Story 1.6
- **No dashboard/TypeScript code** — The bridge is purely Python
- **No Convex functions (queries/mutations in TypeScript)** — Those start in Story 2.2

### Files Created in This Story

| File | Purpose |
|------|---------|
| `nanobot/mc/__init__.py` | Package init — makes `nanobot.mc` importable |
| `nanobot/mc/types.py` | Shared Python types: StrEnum classes + dataclasses mirroring Convex schema |
| `nanobot/mc/bridge.py` | `ConvexBridge` class — sole integration point with Convex Python SDK |
| `nanobot/mc/test_bridge.py` | Unit tests for bridge: case conversion + query/mutation/subscribe methods |

### Files Modified in This Story

None. This story only creates new files.

### Dependency Addition

The `convex` Python package must be added to the project's dependencies:

```
pip install convex
```

If the project uses `pyproject.toml` for dependency management, add `convex>=0.7.0` to the dependencies list. Check the existing `pyproject.toml` for the correct dependency format.

### Verification Steps

1. `from nanobot.mc.bridge import ConvexBridge` — imports successfully
2. `from nanobot.mc.types import TaskStatus, AgentStatus, TrustLevel` — imports successfully
3. `python -m pytest nanobot/mc/test_bridge.py -v` — all tests pass
4. `wc -l nanobot/mc/bridge.py` — output is < 500 lines
5. `grep -r "from convex" nanobot/` — only `nanobot/mc/bridge.py` appears

### References

- [Source: `_bmad-output/planning-artifacts/architecture.md#Boundary 1: Python to Convex`] — Bridge as sole integration point, responsibilities
- [Source: `_bmad-output/planning-artifacts/architecture.md#Communication Patterns`] — Python bridge call pattern, mutation + activity event rule
- [Source: `_bmad-output/planning-artifacts/architecture.md#Naming Patterns`] — Cross-boundary naming: snake_case (Python) to camelCase (Convex)
- [Source: `_bmad-output/planning-artifacts/architecture.md#Process Patterns`] — Error handling per layer
- [Source: `_bmad-output/planning-artifacts/epics.md#Story 1.3`] — Original story definition with acceptance criteria
- [Source: `_bmad-output/planning-artifacts/prd.md#NFR15`] — Bridge retry logic (deferred to Story 1.4)
- [Source: `_bmad-output/planning-artifacts/prd.md#NFR16`] — One-directional writes: only nanobot writes to Convex
- [Source: `_bmad-output/planning-artifacts/prd.md#NFR21`] — 500-line module limit
- [Source: `_bmad-output/implementation-artifacts/1-2-define-convex-data-schema.md`] — Exact enum values, table field names, cross-boundary naming table
- [Web: pypi.org/project/convex] — Convex Python SDK v0.7.0, API reference, type mappings
- [Web: github.com/get-convex/convex-py] — SDK source: ConvexClient, ConvexError, colon notation, subscribe iterator
- [Web: docs.convex.dev/client/python] — Official Python client documentation
- [Web: docs.convex.dev/quickstart/python] — Python quickstart: client setup, query/mutation examples

## Review Findings

### Issues Found and Fixed

1. **HIGH: `_to_camel_case` corrupted underscore-prefixed Convex system fields** -- `_to_camel_case("_id")` produced `"Id"` and `_to_camel_case("_creationTime")` produced `"CreationTime"`. Fixed by adding a guard: if the key starts with `_`, return it unchanged. This prevents silent data corruption if system fields ever flow through outgoing conversion.

2. **LOW: Unused `ConvexError` import with misleading `noqa: F401`** -- `ConvexError` was imported in bridge.py but never used there. Removed the import; tests import directly from `convex`.

3. **LOW: `convex>=0.7.0` dependency lacked upper bound** -- Every other dependency in pyproject.toml uses upper-bound pinning (e.g., `<1.0.0`). Fixed to `convex>=0.7.0,<1.0.0` for consistency.

### Tests Added
- `test_preserves_convex_id` -- `_to_camel_case("_id")` returns `"_id"`
- `test_preserves_convex_creation_time` -- `_to_camel_case("_creationTime")` returns `"_creationTime"`
- `test_preserves_underscore_prefixed_keys` -- `_convert_keys_to_camel` preserves `_id` and `_creationTime` keys in outgoing dicts

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
None needed — all tests pass on first run after fixing ConvexError constructor signature.

### Completion Notes List
- All 4 files created: `__init__.py`, `types.py`, `bridge.py`, `test_bridge.py`
- Added `from __future__ import annotations` to `bridge.py` and `types.py` for broader Python version compatibility
- `convex>=0.7.0` dependency added to `pyproject.toml`
- 54 unit tests pass (10 camelCase, 12 snakeCase, 8 convertKeysToCamel, 9 convertKeysToSnake, 4 query, 3 mutation, 2 subscribe, 4 init/close, 2 edge cases)
- bridge.py is 124 lines (well under 500-line limit)
- Only `bridge.py` imports `convex` — architectural boundary maintained
- ConvexError requires 2 positional args (message, data) — test fixed accordingly

### File List
- `nanobot/mc/__init__.py` — Package init with module listing
- `nanobot/mc/types.py` — 6 StrEnum classes + 4 dataclasses mirroring Convex schema
- `nanobot/mc/bridge.py` — ConvexBridge class (124 lines) with query/mutation/subscribe/close + case conversion helpers
- `nanobot/mc/test_bridge.py` — 54 unit tests covering all acceptance criteria
- `pyproject.toml` — Added `convex>=0.7.0` dependency
