# Holistic Integration Review: Claude Code Backend (CC-1 through CC-6)

**Reviewer**: Claude Opus 4.6 (Code Review Agent)
**Date**: 2026-03-04
**Test Suite**: 182/182 PASSED (all CC tests green)

---

## Executive Summary

The Claude Code backend implementation is **well-architected and largely production-ready**.
The execution flow is coherent end-to-end, type contracts are consistent across module
boundaries, import isolation is correctly maintained, and error handling covers all primary
failure modes. The test suite is thorough with 182 passing tests covering happy paths,
failure modes, and edge cases.

That said, this holistic review identifies **2 HIGH** issues, **5 MEDIUM** issues, and
**3 LOW** issues -- mostly in cross-cutting areas (concurrency, defaults passthrough,
socket security) that individual per-story reviews would not have caught.

---

## 1. Integration Flow Trace (End-to-End)

Verified execution path:

```
_execute_task() [mc/executor.py:834]
  -> _load_agent_data(agent_name) [mc/executor.py:686]
     -> reads ~/.nanobot/agents/{name}/config.yaml
     -> yaml_validator.validate_agent_file() -> AgentData with .backend field
  -> if agent_data.backend == "claude-code":
     -> _execute_cc_task() [mc/executor.py:1284]
        1. CCWorkspaceManager().prepare(agent_name, agent_data, task_id)
           -> creates workspace, CLAUDE.md, .mcp.json, returns WorkspaceContext
        2. MCSocketServer(bridge, None).start(ws_ctx.socket_path)
           -> listens on /tmp/mc-{agent_name}.sock
        3. settings:get to look up existing session_id
        4. ClaudeCodeProvider().execute_task(prompt, agent_config, ...)
           -> spawns `claude -p <prompt> --output-format stream-json ...`
           -> .mcp.json tells CC to start mc.mcp_bridge subprocess
           -> mc.mcp_bridge reads MC_SOCKET_PATH env var
           -> mc.mcp_bridge creates MCSocketClient(MC_SOCKET_PATH)
           -> IPC requests flow: CC -> mcp_bridge -> MCSocketClient -> MCSocketServer
        5. ipc_server.stop() in finally block
        6. result.is_error? -> _crash_task() : _complete_cc_task()
           _complete_cc_task stores session_id, posts message, posts activity, sets DONE
```

**Verdict**: The flow is correct and each handoff is properly wired.

---

## 2. Findings

### HIGH-1: ClaudeCodeProvider instantiated without defaults -- global config never applied

**Files**: `/Users/ennio/Documents/nanobot-ennio/mc/executor.py` lines 1337 and 1569

**What is wrong**: Both `_execute_cc_task()` and `handle_cc_thread_reply()` instantiate
`ClaudeCodeProvider()` with no arguments:

```python
provider = ClaudeCodeProvider()  # line 1337 in _execute_cc_task
provider = ClaudeCodeProvider()  # line 1569 in handle_cc_thread_reply
```

The `ClaudeCodeProvider.__init__()` accepts an optional `defaults: ClaudeCodeConfig`
parameter that provides global defaults for model, budget, turns, and permission mode
(CC-1 AC3). By never passing it, the global `claude_code` config section in
`~/.nanobot/config.json` is completely ignored. Agents without per-agent `claude_code_opts`
will get no `--model`, no `--max-budget-usd`, no `--max-turns`, and will fall back to a
hardcoded `acceptEdits` permission mode instead of reading the admin-configured defaults.

**Impact**: Budget limits configured globally will not be enforced. An agent without
per-agent cc opts could run with unbounded cost. The `cli_path` setting is also ignored,
so custom `claude` binary locations will not work.

**Fix**:

```python
# In _execute_cc_task():
from nanobot.config.loader import load_config
config = load_config()
provider = ClaudeCodeProvider(
    cli_path=config.claude_code.cli_path,
    defaults=config.claude_code,
)
```

Consider caching the loaded config on the TaskExecutor instance to avoid re-reading
the config file on every task.

---

### HIGH-2: Concurrent CC tasks for the same agent share and clobber the same socket path

**Files**:
- `/Users/ennio/Documents/nanobot-ennio/mc/cc_workspace.py` line 97
- `/Users/ennio/Documents/nanobot-ennio/mc/executor.py` lines 1312-1314

**What is wrong**: The socket path is deterministically `/tmp/mc-{agent_name}.sock`.
If two tasks are assigned to the same Claude Code agent concurrently (or a task retries
while the first is still running), the second `MCSocketServer.start()` call will
`os.unlink()` the first task's live socket (line 67 in mcp_ipc_server.py) and bind a new
listener. The first task's MCP bridge subprocess will lose its IPC connection silently.

The executor dispatches tasks concurrently via `asyncio.create_task()` (documented at
line 507), so this is a realistic scenario.

**Impact**: Silent IPC disconnection for the first task. The MCP bridge will get
`ConnectionError` on subsequent tool calls, returning "Mission Control not reachable"
to the CC agent. The task may complete with degraded behavior (no MC tool access) rather
than crashing cleanly.

**Fix**: Include the task_id in the socket path to ensure uniqueness:

```python
# In cc_workspace.py:
socket_path = f"/tmp/mc-{agent_name}-{task_id[:8]}.sock"
```

Or use a random suffix:

```python
import uuid
socket_path = f"/tmp/mc-{agent_name}-{uuid.uuid4().hex[:8]}.sock"
```

---

### MEDIUM-1: mcp_bridge._get_ipc() uses module-level MC_SOCKET_PATH, not the lazy _get_socket_path()

**File**: `/Users/ennio/Documents/nanobot-ennio/mc/mcp_bridge.py` lines 56-63

**What is wrong**: The `_get_ipc()` function creates the singleton IPC client using the
module-level `MC_SOCKET_PATH` variable (line 62), which is evaluated once at module
import time. The comment at line 24-25 says "read env vars lazily at first use, not at
module level", and there is a `_get_socket_path()` function for this purpose, but it is
never actually called.

```python
def _get_ipc():
    global _ipc_client
    if _ipc_client is None:
        from mc.mcp_ipc import MCSocketClient
        _ipc_client = MCSocketClient(MC_SOCKET_PATH)  # <-- uses module-level, not _get_socket_path()
    return _ipc_client
```

In practice this works because the MCP bridge is spawned as a separate subprocess per
task (via .mcp.json), so the module-level variable is set correctly at process start.
However, the inconsistency between the documented intent and the actual code is a
maintenance hazard. The `_get_socket_path()` function is dead code.

**Impact**: Low in production (each bridge is a fresh subprocess), but the dead code
and inconsistency is confusing for maintainers.

**Fix**: Either use `_get_socket_path()` in `_get_ipc()`, or remove the unused lazy
accessor functions and the misleading M2 comment.

---

### MEDIUM-2: Unix socket file created with default permissions (world-readable/writable)

**File**: `/Users/ennio/Documents/nanobot-ennio/mc/mcp_ipc_server.py` line 70-71

**What is wrong**: `asyncio.start_unix_server()` creates the socket file with the
process's default umask, typically `0o755` or even `0o777`. In `/tmp/`, any local user
can connect to the socket and invoke MC operations (create tasks, send messages, ask
agents) as the bridge agent.

```python
self._server = await asyncio.start_unix_server(
    self._handle_connection, path=socket_path
)
# No os.chmod() call after this
```

**Impact**: On multi-user systems, a local attacker could connect to the socket and
invoke delegate_task to create arbitrary tasks, or use ask_agent to query agents.
On single-user dev machines this is low risk, but for production deployments this
is a security gap.

**Fix**:

```python
await asyncio.start_unix_server(self._handle_connection, path=socket_path)
os.chmod(socket_path, 0o600)  # Owner-only access
```

---

### MEDIUM-3: No integration test that exercises the full stack (workspace -> IPC -> bridge -> provider)

**Files**: All test files under `tests/mc/test_cc_*.py` and `tests/mc/test_executor_cc.py`

**What is wrong**: Every test mocks either the IPC layer, the provider, or the workspace
manager. There is no single test that wires all components together and verifies that:
1. `CCWorkspaceManager.prepare()` produces a `.mcp.json` with the correct socket path
2. `MCSocketServer` starts on that path
3. `MCSocketClient` can connect and receive responses
4. The full `_execute_cc_task` flow works without mocks (other than the actual `claude` CLI)

The individual unit tests are thorough, but integration bugs (e.g., a socket path format
mismatch between workspace and bridge) would not be caught.

**Impact**: A wiring bug between components could slip into production undetected.

**Fix**: Add at least one integration test that wires workspace + IPC server + IPC client
together (mocking only the `claude` subprocess).

---

### MEDIUM-4: Session store-then-delete race in _complete_cc_task

**File**: `/Users/ennio/Documents/nanobot-ennio/mc/executor.py` lines 1420-1474

**What is wrong**: `_complete_cc_task()` first stores the session_id (lines 1422-1448),
then immediately soft-deletes the task-scoped key (lines 1460-1474):

```python
# Store session_id (AC1)
await ... mutation("settings:set", {"key": f"cc_session:{agent_name}:{task_id}", "value": result.session_id})
await ... mutation("settings:set", {"key": f"cc_session:{agent_name}:latest", "value": result.session_id})

# ... status transition to DONE ...

# Soft-delete task-scoped key (AC4)
await ... mutation("settings:set", {"key": f"cc_session:{agent_name}:{task_id}", "value": ""})
```

The task-scoped session is stored and then immediately set to empty string. This means
the task-scoped key is effectively never useful for resume -- by the time `_execute_cc_task`
looks it up on a re-run, it will find an empty string (which correctly falls through to
`session_id = None`). However, it also means that `handle_cc_thread_reply()` will find
an empty session for completed tasks, preventing session resume for thread follow-ups
on done tasks.

This is partially by design (AC4 says cleanup on done), but it creates a conflict with
AC3 (thread reply should resume session). A user replying in a done task's thread would
start a fresh session instead of continuing the conversation.

**Impact**: Thread follow-ups on completed tasks will not resume the CC session context.
The `:latest` key survives, but `handle_cc_thread_reply` looks up the task-scoped key,
not the latest key.

**Fix**: Either:
1. Have `handle_cc_thread_reply` fall back to the `:latest` key when the task-scoped key is empty.
2. Do not soft-delete the task-scoped key immediately -- instead, only clean it up on explicit archive or after a TTL.

---

### MEDIUM-5: output truncated to 2000 chars in _complete_cc_task without notification

**File**: `/Users/ennio/Documents/nanobot-ennio/mc/executor.py` line 1407

**What is wrong**:

```python
result.output[:2000],
```

The CC agent's output is silently truncated to 2000 characters when posting to the task
thread. For complex tasks, the full output could be significantly longer. The user sees
a truncated result with no indication that content was cut.

**Impact**: Loss of information for verbose task outputs. Users may miss important details
at the end of a long response.

**Fix**: Either increase the limit, add a truncation marker (e.g., `"... [truncated, full
output: {n} chars]"`), or store the full output in a separate artifact/file and link to it.

---

### LOW-1: executor.py exceeds the project's 500-line module limit (NFR21)

**File**: `/Users/ennio/Documents/nanobot-ennio/mc/executor.py` -- 1599 lines

**What is wrong**: The module docstring says "Extracted from orchestrator.py per NFR21
(500-line module limit)" but the file is now 1599 lines -- more than 3x the limit. The CC
backend methods alone add about 315 lines (lines 1284-1599).

**Impact**: Violates the project's stated non-functional requirement. Makes the file
harder to navigate and maintain.

**Fix**: Extract the CC-specific methods (`_execute_cc_task`, `_complete_cc_task`,
`_crash_task`, `handle_cc_thread_reply`, `_post_cc_activity`) into a separate module
(e.g., `mc/cc_executor.py`) and have the main `TaskExecutor` delegate to it. This
could be a mixin class or a composed helper.

---

### LOW-2: _crash_task author is hardcoded to "System" string instead of AuthorType.SYSTEM

**File**: `/Users/ennio/Documents/nanobot-ennio/mc/executor.py` lines 1493, 1506

**What is wrong**: The `_crash_task` method passes `"System"` as the author_name and
`AuthorType.SYSTEM` as the author_type. The string `"System"` is not an agent name --
it is a display label. This is inconsistent with `_complete_cc_task` which correctly
uses `agent_name` as the author.

```python
self._bridge.send_message(task_id, "System", AuthorType.SYSTEM, ...)
self._bridge.update_task_status(task_id, TaskStatus.CRASHED, "System", ...)
```

**Impact**: Cosmetic -- crash messages show "System" as the author rather than the agent
that was running when the crash occurred. This makes it harder to identify which agent
caused the crash.

**Fix**: Pass `agent_name` to `_crash_task` and use it as the first parameter:

```python
async def _crash_task(self, task_id, title, error, agent_name="System"):
    ...
    self._bridge.send_message(task_id, agent_name, AuthorType.SYSTEM, ...)
```

---

### LOW-3: test_mcp_bridge.py tests do not use pytest.mark.asyncio

**File**: `/Users/ennio/Documents/nanobot-ennio/tests/mc/test_mcp_bridge.py`

**What is wrong**: All test methods in test_mcp_bridge.py are defined as `async def`
but do not have the `@pytest.mark.asyncio` decorator. They still pass because pytest-asyncio
appears to be configured with `mode = "auto"` for this project, but this is implicit and
fragile.

**Impact**: Tests would break if the pytest-asyncio mode is changed to `"strict"`.

**Fix**: Add `@pytest.mark.asyncio` to each async test method, or add
`pytestmark = pytest.mark.asyncio` at the module level.

---

## 3. Import Graph Verification

Verified that `mc/mcp_bridge.py` does NOT import any heavy MC dependencies:

- Imports: `asyncio`, `os`, `sys`, `mcp.server`, `mcp.server.stdio`, `mcp.types`
- The only MC import is `mc.mcp_ipc.MCSocketClient` (lazy, inside `_get_ipc()`)
- No import of `ConvexBridge`, `MessageBus`, `gateway`, `executor`, etc.

All other cross-module imports are correct:
- `mc/cc_workspace.py` imports `mc.types` (AgentData, WorkspaceContext) -- correct
- `mc/cc_provider.py` imports `mc.types` (AgentData, CCTaskResult, WorkspaceContext) -- correct
- `mc/executor.py` lazy-imports `cc_workspace`, `cc_provider`, `mcp_ipc_server` inside methods -- correct
- `mc/mcp_ipc_server.py` uses TYPE_CHECKING for ConvexBridge and MessageBus -- correct
- No circular dependency chains detected.

---

## 4. Type Consistency Verification

| Type | Defined in | Used in | Consistent? |
|------|-----------|---------|-------------|
| CCTaskResult | mc/types.py:398 | cc_provider.py, executor.py | Yes |
| WorkspaceContext | mc/types.py:389 | cc_workspace.py, cc_provider.py, executor.py | Yes |
| AgentData.backend | mc/types.py:331 | yaml_validator.py, executor.py:855 | Yes |
| AgentData.claude_code_opts | mc/types.py:332 | yaml_validator.py, cc_provider.py | Yes |
| ClaudeCodeOpts | mc/types.py:307 | yaml_validator.py, cc_provider.py | Yes |
| ClaudeCodeConfig | vendor/.../schema.py:321 | cc_provider.py (TYPE_CHECKING) | Yes |

All type contracts are consistent across module boundaries.

---

## 5. Socket Path Consistency Verification

| Component | Socket Path Source | Value |
|-----------|-------------------|-------|
| cc_workspace.py:97 | Generated | `/tmp/mc-{agent_name}.sock` |
| .mcp.json env.MC_SOCKET_PATH | From workspace | Same path |
| mcp_bridge.py:39 | `os.environ["MC_SOCKET_PATH"]` | Reads from .mcp.json env |
| mcp_ipc_server.py:71 | `start(socket_path)` | Passed from executor via `ws_ctx.socket_path` |
| executor.py:1314 | `ws_ctx.socket_path` | From workspace prepare() |

**Verdict**: Socket paths are consistent across all components. The path flows correctly
from workspace manager -> .mcp.json -> bridge subprocess -> IPC client, and from
workspace manager -> executor -> IPC server.

---

## 6. What Was Done Well

1. **Clean separation of concerns**: Each module has a clear responsibility (workspace prep,
   IPC transport, CLI execution, orchestration). No module crosses its boundary.

2. **Defensive error handling**: Every phase of `_execute_cc_task` is wrapped in try/except
   with appropriate crash handling. IPC server is always stopped in a finally block.
   Bridge failures in `_crash_task` are tolerated (double-fault protection).

3. **Path traversal protection**: Agent names and skill names are validated against
   `"/"` and `"."` prefixes in cc_workspace.py. Socket path length is validated against
   the macOS limit.

4. **Idempotent workspace preparation**: The prepare() method is safe to call multiple
   times. Memory and session directories are preserved across calls.

5. **Graceful subprocess management**: The provider handles CancelledError correctly,
   sends SIGTERM with a 10s grace period before SIGKILL, and handles ProcessLookupError.

6. **Session management**: The store/lookup/cleanup lifecycle is complete and handles
   all failure modes gracefully (lookup failure starts fresh, store failure does not
   prevent task completion).

7. **Test coverage**: 182 tests covering unit and semi-integration scenarios for every
   component. Error paths are well tested (bridge failures, IPC failures, workspace
   failures, CLI crashes).

---

## 7. Summary of Findings

| # | Severity | Title | Files |
|---|----------|-------|-------|
| H1 | HIGH | ClaudeCodeProvider instantiated without global config defaults | executor.py:1337,1569 |
| H2 | HIGH | Concurrent CC tasks for same agent clobber shared socket path | cc_workspace.py:97, mcp_ipc_server.py:67 |
| M1 | MEDIUM | _get_ipc() uses module-level var, not lazy accessor (dead code) | mcp_bridge.py:62 |
| M2 | MEDIUM | Socket file created with default permissions (no chmod) | mcp_ipc_server.py:70 |
| M3 | MEDIUM | No integration test covering the full stack | tests/mc/ |
| M4 | MEDIUM | Session store-then-delete race prevents thread resume on done tasks | executor.py:1420-1474 |
| M5 | MEDIUM | Output truncated to 2000 chars without notification | executor.py:1407 |
| L1 | LOW | executor.py at 1599 lines, exceeds 500-line NFR21 limit | executor.py |
| L2 | LOW | _crash_task author hardcoded to "System" | executor.py:1493 |
| L3 | LOW | test_mcp_bridge.py async tests missing pytest.mark.asyncio | test_mcp_bridge.py |

**Recommendation**: Fix H1 and H2 before production use. Address M2 (socket permissions)
and M4 (session resume for done tasks) in the next sprint.
