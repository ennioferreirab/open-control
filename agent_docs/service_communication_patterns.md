# Service Communication Patterns

This document describes every **communication channel, protocol, and data-flow pattern** used across the system. For the service overview and boot sequence, see [`service_architecture.md`](service_architecture.md). For the database schema, see [`database_schema.md`](database_schema.md). For naming contracts, see [`code_conventions/cross_service_naming.md`](code_conventions/cross_service_naming.md).

---

## Communication Map

```text
                        ┌──────────────────────────────────────────────┐
                        │               User's Browser                  │
                        │  Dashboard (Next.js, React 19)                │
                        │                                              │
                        │  useQuery ─────┐    useMutation ────┐        │
                        │  (real-time)   │    (writes)        │        │
                        │                │                    │        │
                        │  API Routes ───┼── Local FS I/O     │        │
                        │  (REST)        │                    │        │
                        │                │   WebSocket ──┐    │        │
                        │                │   (xterm.js)  │    │        │
                        └────────────────┼───────────────┼────┼────────┘
                                         │               │    │
                          Convex SDK WS  │    WS :8765   │    │ Convex SDK WS
                                         ▼               ▼    ▼
┌──────────────────┐   ┌──────────────┐   ┌──────────────────────────────┐
│  Terminal Bridge  │──▶│   Convex     │◀──│         MC Gateway           │
│  (optional)       │   │   Local      │   │         (Python)             │
│  polling Convex   │   │   Backend    │   │                              │
└──────────────────┘   │   :3210      │   │  ┌─ Orchestrator workers ──┐ │
                        └──────────────┘   │  │  InboxWorker (3s)       │ │
                                           │  │  PlanningWorker (5s)    │ │
                              ▲            │  │  ReviewWorker (5s)      │ │
                              │            │  │  KickoffWorker (5s)     │ │
                     Convex SDK (query/    │  │  TaskExecutor (2s)      │ │
                      mutation + retry)    │  └────────────────────────┘ │
                              │            │                              │
                              │            │  SleepController (1s ctrl)  │
                              │            │  TimeoutChecker (60s)       │
                              │            │  MentionWatcher (10s)       │
                              │            │  AskUserWatcher (1.5s)      │
                              │            │  ChatHandler (5s/60s)       │
                              │            │  PlanNegotiation (per-task) │
                              │            │  CronDelivery              │
                              │            │  InteractiveRuntime :8765   │
                              │            │                              │
                              │            │  ┌─ MCSocketServer ───────┐ │
                              │            │  │  Unix socket (per-task)│ │
                              │            │  │  10 RPC methods        │ │
                              │            │  └───────────┬────────────┘ │
                              │            └──────────────┼──────────────┘
                              │                           │
                              │              Unix socket   │ JSON-RPC
                              │                           │
                     ┌────────┴───────┐     ┌─────────────┴──────────────┐
                     │  Convex Bridge  │     │    Agent Subprocesses       │
                     │  (mc/bridge/)   │     │                             │
                     │                 │     │  ┌─ MCP Bridge (stdio) ──┐ │
                     │  snake↔camel    │     │  │  MCSocketClient       │ │
                     │  retry+backoff  │     │  │  → ask_user           │ │
                     │  idempotency    │     │  │  → delegate_task      │ │
                     │  OCC locking    │     │  │  → send_message       │ │
                     └─────────────────┘     │  │  → ask_agent          │ │
                                             │  │  → cron               │ │
                                             │  │  → create_agent_spec  │ │
                                             │  │  → publish_squad_graph│ │
                                             │  └──────────────────────┘ │
                                             │                             │
                                             │  Hook Bridge (stdin→IPC)    │
                                             │  → emit_supervision_event   │
                                             └─────────────────────────────┘
                                                          │
                                                          ▼
                                                External LLM APIs
                                          (Anthropic, OpenRouter, OpenAI)
```

---

## 1. IPC Socket Protocol (Unix Domain Socket)

The primary channel between agent subprocesses and the MC Gateway.

### 1.1 Server

| Property | Value |
|----------|-------|
| Implementation | `vendor/claude-code/claude_code/ipc_server.py` (`MCSocketServer`) |
| Transport | `asyncio.start_unix_server()` |
| Protocol | Newline-delimited JSON (NDJSON) — one request/response per connection |
| Stream limit | 1 MB (`_IPC_STREAM_LIMIT`) |
| Permissions | `0o600` (owner-only) |
| Lifecycle | Created per-task before agent spawn, destroyed in `finally` after execution |

**Socket path formula** (generated in `vendor/claude-code/claude_code/workspace.py`):

```
/tmp/mc-{agent_name}-{task_id[:8]}.sock
```

- First 8 chars of `task_id` prevent collision for concurrent tasks by the same agent.
- If no `task_id`, a random `uuid4().hex[:8]` is used.
- Maximum 104 characters (macOS `AF_UNIX` limit).

**Who creates the server:**

| Caller | File | Context |
|--------|------|---------|
| `ClaudeCodeStrategy._run_cc()` | `mc/application/execution/strategies/claude_code.py` | Task execution |
| `CCExecutorMixin` | `mc/contexts/execution/cc_executor.py` | Task + thread-reply execution |
| `TaskPlanner` | `mc/contexts/planning/planner.py` | CC-backed planning |
| `ClaudeCodeAdapter` | `mc/contexts/interactive/adapters/claude_code.py` | Interactive PTY sessions |

### 1.2 Wire Format

```text
Client → Server:  {"method": "<name>", "params": {<args>}}\n
Server → Client:  {<response>}\n
```

- One connection = one request + one response. Connection closes immediately after.
- No JSON-RPC `id` field. No batching. No persistent connections.

### 1.3 All RPC Methods

| Method | Handler | Key Params | Response | Timeout |
|--------|---------|------------|----------|---------|
| `ask_user` | `_handle_ask_user` | `question`, `options?`, `questions?`, `task_id?` | `{"answer": str}` | Indefinite (waits for user) |
| `send_message` | `_handle_send_message` | `content`, `channel?`, `chat_id?`, `media?`, `task_id?` | `{"status": "Message sent"}` | — |
| `delegate_task` | `_handle_delegate_task` | `description`, `agent?`, `priority?` | `{"task_id": str, "status": "created"}` | — |
| `ask_agent` | `_handle_ask_agent` | `agent_name`, `question`, `depth?` | `{"response": str}` | 120s |
| `report_progress` | `_handle_report_progress` | `message`, `percentage?` | `{"status": "Progress reported"}` | — |
| `cron` | `_handle_cron` | `action` (`list`/`add`/`remove`), schedule params | `{"result": str}` | — |
| `emit_supervision_event` | `_handle_emit_supervision_event` | `provider`, `raw_event` | `{"status": "ok", "session_id": str?}` | — |
| `create_agent_spec` | `_handle_create_agent_spec` | `name`, `role`, V2 fields | `{"spec_id": str}` | — |
| `publish_squad_graph` | `_handle_publish_squad_graph` | `graph` (squad blueprint) | `{"squad_id": str}` | — |

**Key behaviors:**

- `ask_user` — blocks until user replies in dashboard. Posts question to task thread via Convex, registers an `asyncio.Future` in `AskUserRegistry`, transitions task to `review` with `review_phase="execution_pause"`.
- `delegate_task` — self-delegation guard (agent cannot delegate to itself). Creates task via `bridge.mutation("tasks:create", ...)`. Title is silently truncated to 120 chars from the `description` field.
- `ask_agent` — spawns an isolated `AgentLoop` with a fresh `MessageBus`. Max recursion depth: 2 (`ASK_AGENT_MAX_DEPTH`). 120-second timeout. Resolves tier model references via `TierResolver` before spawning.
- `send_message` — two delivery paths: (1) `bus.publish_outbound()` if `channel` + `chat_id` given; (2) `bridge.send_message()` if `task_id` + bridge available. Media files copied to `~/.nanobot/tasks/{id}/output/`.

### 1.4 Client Implementations

| Client | File | Transport | Timeout | Used By |
|--------|------|-----------|---------|---------|
| `MCSocketClient` (async) | `vendor/claude-code/claude_code/ipc_client.py` | `asyncio.open_unix_connection()` | 300s | MCP bridges |
| `SyncIPCClient` (blocking) | `mc/hooks/ipc_sync.py` | `socket.socket(AF_UNIX)` | 5s | Hook handlers |
| `hook_bridge` (subprocess) | `vendor/claude-code/claude_code/hook_bridge.py` | Reads stdin, calls `MCSocketClient` | 300s | CC hooks → `emit_supervision_event` |

All clients open a new connection per request — no pooling.

### 1.5 Error Handling

| Layer | Behavior |
|-------|----------|
| Server: unknown method | Returns `{"error": "Unknown method: {name}"}` |
| Server: handler exception | Returns `{"error": str(exc)}`, logs warning |
| Server: connection error | Logs warning, closes connection silently |
| Async client: socket not found | Raises `ConnectionError` |
| Async client: empty response | Raises `ConnectionError("...closed without response")` |
| MCP bridge: `ConnectionError` | Returns `TextContent("Mission Control not reachable. Is the gateway running?")` |
| Sync client: timeout | Raises `ConnectionError("...timed out after {n}s")` |
| Hook bridge: any error | Prints to stderr, exits 0 (non-fatal by design) |

### 1.6 Timeout Summary

| Location | Operation | Timeout |
|----------|-----------|---------|
| Server | `readline()` from client | 305s |
| Async client | `readline()` response | 300s |
| Async client | `writer.wait_closed()` | 2s |
| Sync client | `socket.settimeout` | 5s (default) |
| `ask_agent` handler | `AgentLoop.process_direct()` | 120s |
| `ask_user` handler | Waits for user reply | Indefinite |

---

## 2. Convex Bridge (Python → Convex)

All Python-to-Convex communication is centralized in `mc/bridge/`.

### 2.1 Architecture

```text
Python callers (workers, services, contexts)
        │
   ConvexBridge  (mc/bridge/__init__.py)
        │── inherits BridgeRepositoryFacadeMixin  (mc/bridge/facade_mixins.py)
        │── owns _BridgeClientAdapter  (mc/bridge/adapter.py)
        │
   Repository Layer  (mc/bridge/repositories/*.py)
        │── TaskRepository        → tasks:* Convex functions
        │── StepRepository        → steps:* Convex functions
        │── MessageRepository     → messages:* Convex functions
        │── AgentRepository       → agents:* Convex functions
        │── BoardRepository       → boards:* Convex functions
        │── ChatRepository        → chats:* Convex functions
        │── SpecsRepository       → agentSpecs:*, squadSpecs:* Convex functions
        │
   Direct bridge.query()/mutation() calls  → settings:* Convex functions (no repository)
        │
   SubscriptionManager  (mc/bridge/subscriptions.py)
        │
   Raw ConvexClient (Python SDK)
        │
   Convex HTTP → localhost:3210
```

`ConvexBridge` is a **delegating facade**. All public methods are defined in `BridgeRepositoryFacadeMixin` and delegate 1:1 to the matching repository instance. Callers import only `ConvexBridge`.

### 2.2 Key Conversion

**File:** `mc/bridge/key_conversion.py`

```text
Python snake_case  ←→  Bridge  ←→  Convex camelCase
```

| Direction | Function | Special Cases |
|-----------|----------|---------------|
| Outbound (to Convex) | `_to_camel_case()` | Keys starting with `_` passed unchanged (`_id`, `_creationTime`) |
| Inbound (from Convex) | `_to_snake_case()` | `_id` → `id`, `_creationTime` → `creation_time` |

Applied recursively to all nested dicts/lists. Status values are **never converted** — they are identical across all layers.

### 2.3 Retry & Idempotency

**File:** `mc/bridge/retry.py`, `mc/bridge/idempotency.py`

| Property | Value |
|----------|-------|
| Max retries | 3 (4 total attempts) |
| Backoff base | 1 second |
| Delay schedule | 1s → 2s → 4s (`1 * 2^(attempt-1)`) |
| Scope | Mutations only — queries have no retry |

**Idempotency key generation** (for 6 supported mutations):

```
messages:create, messages:postStepCompletion, messages:postLeadAgentMessage,
activities:create, tasks:transition, steps:transition
```

Formula: `"{function_name}:{sha256(deterministic_json(args))[:16]}"`. Caller-supplied keys take precedence. The Convex-side `runtimeReceipts` table stores results keyed by `idempotencyKey`, returning cached results on retry.

After 4 failures: logs `ERROR`, writes a best-effort `activities:create` error event (bypasses retry to avoid infinite loop), then re-raises.

### 2.4 Optimistic Concurrency Control (OCC)

Task and step records include a `stateVersion` field. The full round-trip:

```text
1. Python reads snapshot (task_data with state_version + status)
2. Calls transition_task_from_snapshot(task_data, to_status, reason)
3. Bridge builds idempotency key: "py:{task_id}:v{version}:{from}:{to}:..."
4. Converts to camelCase, calls tasks:transition (internalMutation)
5. Convex checks:
   a. Idempotency receipt exists? → return cached noop
   b. Semantic noop (already in target state)? → return noop
   c. Status mismatch (task.status ≠ fromStatus)? → return conflict
   d. Stale version (current ≠ expected)? → return conflict
   e. Apply: increment stateVersion, patch DB, store receipt
6. Bridge receives {kind: "applied"|"noop"|"conflict"}
7. On conflict: caller re-fetches task and retries with fresh snapshot
```

**Distributed locking** via `runtimeClaims` table: lease-based claims with `owner_id`, `lease_expires_at`. Used to prevent duplicate task pickup across gateway instances.

### 2.5 Subscription Patterns

> **Rule: Use real Convex subscriptions, never polling.** The Convex Python SDK (`ConvexClient.subscribe()`) returns a `QuerySubscription` that supports native async iteration over a WebSocket — zero queries when data hasn't changed. **Do not use polling strategies** (`asyncio.sleep` + `client.query` loops). The legacy `_poll_loop` in `subscriptions.py` is preserved only as a fallback; all new code must use `_subscribe_loop`.

The Python side uses two modes, both in `mc/bridge/subscriptions.py`:

**Mode A: Blocking iterator** (`subscribe()`) — uses native Convex SDK WebSocket subscription. Rarely used at runtime.

**Mode B: Async reactive subscription** (`async_subscribe()`) — the primary mode:

- Returns an `asyncio.Queue`. Starts a `_subscribe_loop` task that uses `raw_client.subscribe()` for native WebSocket push.
- **Zero cost when idle:** no queries are made while data hasn't changed — the subscription blocks on `__anext__()` until the server pushes an update.
- **Change detection:** only pushes to queues when `result != last_result`.
- **Fan-out dedup:** keyed on `(function_name, frozen_args)`. Multiple subscribers to the same query share one subscription loop — each gets their own queue.
- **Sleep integration:** calls `sleep_controller.record_work_found()` / `record_idle()` on each update. Unlike polling, subscriptions cannot be paused — they remain connected but cost nothing when idle.
- **Error recovery:** exponential backoff reconnection on failure (2^n seconds, max 30s). After 10 consecutive failures, pushes `{"_error": True}` to all consumer queues and exits.

**Active subscriptions:**

| Consumer | Query | Status |
|----------|-------|--------|
| InboxWorker | `tasks:listByStatus` | `inbox` |
| PlanningWorker | `tasks:listByStatus` | `planning` |
| ReviewWorker | `tasks:listByStatusLite` | `review` |
| KickoffResumeWorker | `tasks:listByStatus` | `in_progress` |
| TaskExecutor | `tasks:listByStatusLite` | `assigned` |
| PlanNegotiationSupervisor | `tasks:listByStatus` | `review` (shared loop) |
| PlanNegotiationSupervisor | `tasks:listByStatus` | `in_progress` (shared loop) |
| PlanNegotiation (per-task) | `messages:listByTask` | per `task_id` |

The `review` and `in_progress` loops each serve two consumers via fan-out. Consumers that don't need heavy fields (`executionPlan`, `routingDecision`, `files`, merge fields) use `tasks:listByStatusLite`.

### 2.6 All Convex Functions Called from Python

#### Tasks

| Python Method | Convex Function | Kind |
|---------------|-----------------|------|
| `get_task(task_id)` | `tasks:getById` | query |
| `update_task_status(...)` | `tasks:updateStatus` | internalMutation |
| `transition_task(...)` | `tasks:transition` | internalMutation |
| `update_execution_plan(task_id, plan)` | `tasks:updateExecutionPlan` | internalMutation |
| `patch_routing_decision(...)` | `tasks:patchRoutingDecision` | internalMutation |
| `kick_off_task(task_id, step_count)` | `tasks:kickOff` | internalMutation |
| `approve_and_kick_off(task_id, plan?)` | `tasks:approveAndKickOff` | mutation |
| `sync_task_output_files(...)` | `tasks:updateTaskOutputFiles` | internalMutation |
| `sync_output_files_to_parent(...)` | `tasks:getById` + `tasks:updateTaskOutputFiles` + `activities:create` | query + internalMutation |

Subscription queries: `tasks:listByStatus` (inbox, needs full doc) and `tasks:listByStatusLite` (all other consumers).

#### Steps

| Python Method | Convex Function | Kind |
|---------------|-----------------|------|
| `create_step(step_data)` | `steps:create` | internalMutation |
| `batch_create_steps(task_id, steps)` | `steps:batchCreate` | internalMutation |
| `update_step_status(step_id, status)` | `steps:getById` + `steps:transition` | query + internalMutation |
| `transition_step(...)` | `steps:transition` | internalMutation |
| `get_step(step_id)` | `steps:getById` | query |
| `get_steps_by_task(task_id)` | `steps:getByTask` | query |
| `check_and_unblock_dependents(step_id)` | `steps:checkAndUnblockDependents` | internalMutation |

#### Messages

| Python Method | Convex Function | Kind |
|---------------|-----------------|------|
| `get_task_messages(task_id)` | `messages:listByTask` | query |
| `get_recent_user_messages(since)` | `messages:listRecentUserMessages` | query |
| `send_message(...)` | `messages:create` | internalMutation |
| `post_step_completion(...)` | `messages:postStepCompletion` | internalMutation |
| `post_lead_agent_message(...)` | `messages:postLeadAgentMessage` | internalMutation |
| `post_system_error(...)` | `messages:create` | internalMutation |

#### Agents

| Python Method | Convex Function | Kind |
|---------------|-----------------|------|
| `sync_agent(agent_data)` | `agents:upsertByName` | mutation |
| `list_agents()` | `agents:list` | query |
| `get_agent_by_name(name)` | `agents:getByName` | query |
| `list_active_registry_view()` | `agents:listActiveRegistryView` | query |
| `list_deleted_agents()` | `agents:listDeleted` | query |
| `deactivate_agents_except(names)` | `agents:deactivateExcept` | mutation |
| `update_agent_status(name, status)` | `agents:updateStatus` | mutation |
| `backup_agent_memory(name, boards_data, global_data)` | `agents:upsertMemoryBackup` | mutation |
| `get_agent_memory_backup(name)` | `agents:getMemoryBackup` | query |

#### Other Namespaces

| Python Method | Convex Function | Kind |
|---------------|-----------------|------|
| `get_board_by_id(board_id)` | `boards:getById` | query |
| `get_default_board()` | `boards:getDefault` | query |
| `ensure_default_board()` | `boards:ensureDefaultBoard` | mutation |
| `get_pending_chat_messages()` | `chats:listPending` | query |
| `send_chat_response(...)` | `chats:send` | mutation |
| `mark_chat_processing(chat_id)` | `chats:updateStatus` | mutation |
| `mark_chat_done(chat_id)` | `chats:updateStatus` | mutation |
| `create_activity(...)` | `activities:create` | mutation |
| `acquire_runtime_claim(...)` | `runtimeClaims:acquire` | mutation |
| `create_agent_spec(...)` | `agentSpecs:createDraft` | mutation |
| `publish_agent_spec(spec_id)` | `agentSpecs:publish` | mutation |
| `get_agent_spec_by_name(name)` | `agentSpecs:getByName` | query |
| `create_board_agent_binding(...)` | `agentSpecs:bindToBoard` | mutation |
| `publish_squad_graph(graph)` | `squadSpecs:publishGraph` | mutation |

#### Settings (Direct bridge calls, no repository)

| Call | Convex Function | Kind |
|------|-----------------|------|
| `bridge.query("settings:get", ...)` | `settings:get` | query |
| `bridge.mutation("settings:set", ...)` | `settings:set` | mutation |
| `bridge.query("settings:list", ...)` | `settings:list` | query |
| `bridge.query("settings:getGatewaySleepControl", ...)` | `settings:getGatewaySleepControl` | query |

---

## 3. MCP Bridge (Agent ↔ Gateway)

The MCP bridge translates agent tool calls into IPC socket requests. There are **two implementations** serving different agent backends.

### 3.1 Implementations

| Bridge | Entry Point | Used By | Tools |
|--------|------------|---------|-------|
| CC bridge | `vendor/claude-code/claude_code/mcp_bridge.py` | ClaudeCodeRunner + ProviderCliRunner (Claude Code parser) | 8 tools |
| MC bridge | `mc/runtime/mcp/bridge.py` | NanobotRunner (in-process AgentLoop) | 9 tools (Phase 1) |

Both are **stdio MCP servers** launched as subprocesses by the agent runtime.

### 3.2 Launch Mechanism

`CCWorkspaceManager._generate_mcp_json()` writes a `.mcp.json` file into the agent workspace:

```json
{
  "mcpServers": {
    "nanobot": {
      "command": "uv",
      "args": ["run", "python", "-m", "claude_code.mcp_bridge"],
      "env": {
        "MC_SOCKET_PATH": "/tmp/mc-agent-ab12cd34.sock",
        "AGENT_NAME": "researcher",
        "TASK_ID": "abc123...",
        "CONVEX_URL": "http://localhost:3210",
        "CONVEX_ADMIN_KEY": "...",
        "MEMORY_WORKSPACE": "~/.nanobot/agents/researcher/",
        "BOARD_NAME": "default"
      }
    }
  }
}
```

The agent process (Claude Code CLI or nanobot) reads `.mcp.json` on startup and spawns the bridge. The JSON key is `"openmc"` and the MCP `Server` name is `"mc"` — tools appear as `mcp__mc__<tool_name>` in the agent's tool palette (the prefix comes from the server name, not the JSON key).

### 3.3 Tool Catalog

**CC bridge (6 tools):**

| Tool | IPC Method | Target |
|------|-----------|--------|
| `ask_user` | `ask_user` | `AskUserHandler.ask()` → task thread |
| `send_message` | `send_message` | `MessageBus` or Convex thread |
| `delegate_task` | `delegate_task` | `tasks:create` mutation |
| `ask_agent` | `ask_agent` | Isolated `AgentLoop` (120s, depth≤2) |
| `cron` | `cron` | `CronService` |
| `search_memory` | *(local, no IPC)* | `mc.memory.create_memory_store().search()` |

**MC bridge (7 Phase 1 tools)** — defined in `mc/runtime/mcp/tool_specs.py`:

Same as CC bridge minus `search_memory`, plus:

| Tool | IPC Method | Target |
|------|-----------|--------|
| `create_agent_spec` | `create_agent_spec` | `agentSpecs:createDraft` + `agentSpecs:publish` |
| `publish_squad_graph` | `publish_squad_graph` | `squadSpecs:publishGraph` |

Tool registration is **static** — hardcoded lists in both bridges.

### 3.4 Data Flow

```text
Agent LLM calls tool
  │  (MCP stdio protocol)
  ▼
MCP Bridge subprocess
  │
  ├─ Fast path: if CONVEX_URL + MC_INTERACTIVE_SESSION_ID set (and no chat_id for send_message)
  │     → InteractionService → direct Convex HTTP
  │
  └─ Normal path: MCSocketClient.request(method, params)
       │  {"method": "ask_user", "params": {...}}\n
       │  Unix socket
       ▼
     MCSocketServer (in MC Gateway event loop)
       │  dispatch to handler
       ▼
     Handler → bridge.mutation(...) → Convex
       │
       ▼
     Response: {"answer": "..."}\n → back through socket → MCP response
```

### 3.5 Error Propagation

Tool failures are returned as `TextContent` strings, never exceptions:

- Socket unreachable → `"Mission Control not reachable. Is the gateway running?"`
- Handler error → `"Error: {message}"`
- Memory search import error → `"Memory search not available"`

---

## 4. Agent Subprocess Communication

The Gateway uses the **Strategy pattern** to dispatch work to different execution backends. Each strategy has distinct communication mechanisms.

### 4.1 Runner Strategies

| Strategy | File | Spawn | IPC | Output |
|----------|------|-------|-----|--------|
| `NanobotRunnerStrategy` | `mc/application/execution/strategies/nanobot.py` | In-process coroutine (but MCP bridge spawns subprocess) | MCP bridge subprocess → direct Convex (no socket) | Direct Python return |
| `ClaudeCodeRunnerStrategy` | `mc/application/execution/strategies/claude_code.py` | `asyncio.create_subprocess_exec` (stderr=PIPE, separate) | NDJSON stdout + Unix socket (starts MCSocketServer) | `type="result"` NDJSON message |
| `ProviderCliRunnerStrategy` | `mc/application/execution/strategies/provider_cli.py` | `asyncio.create_subprocess_exec` (stderr=STDOUT, merged; new session) | Chunked stdout + Unix socket (reuses existing .mcp.json, does NOT start MCSocketServer) | Parsed `kind="result"` events |
| `InteractiveTuiRunnerStrategy` | `mc/application/execution/strategies/interactive.py` | Delegates to `SessionCoordinator` | Polls Convex every 250ms | `interactiveSessions.final_result` |
| `HumanRunnerStrategy` | `mc/application/execution/strategies/human.py` | None | None | Static `"Waiting for human action."` |

### 4.2 Claude Code Runner — Dual-Layer IPC

**Layer 1 — NDJSON stdout stream:**

The `claude` CLI is invoked with `--output-format stream-json`. Each stdout line is a JSON object:

| `type` | Content | Meaning |
|--------|---------|---------|
| `"system"` + `subtype="init"` | `session_id` | Session started |
| `"assistant"` | text blocks, tool_use blocks | Streaming agent output |
| `"result"` + `subtype="success"` | `result`, `total_cost_usd`, `session_id` | Final output |
| `"stream_event"` | error details | Error during execution |

**Layer 2 — Unix socket IPC (MC tools):**

The `.mcp.json` causes Claude to spawn a `claude_code.mcp_bridge` subprocess, which connects to `MCSocketServer` over the Unix socket. This is the same channel described in Section 1.

**CLI command built by `ClaudeCodeProvider._build_command()`:**

```
claude -p "<prompt>" --output-format stream-json --verbose
       --mcp-config <workspace>/.mcp.json
       --model <model>
       --max-budget-usd <budget>          # CC runner only (not in ProviderCLI)
       --max-turns <turns>                # CC runner only (not in ProviderCLI)
       --permission-mode <mode>
       --allowedTools <tool1> ... --allowedTools mcp__mc__*
       --disallowedTools <tool> ...
       --effort <level>
       --resume <session_id>    # only if resuming
```

**Note:** `ProviderCliRunnerStrategy._build_command()` builds a similar command but **omits** `--max-budget-usd` and `--max-turns`. Budget/turn limits are exclusive to `ClaudeCodeProvider`.

### 4.3 Provider CLI Runner — Chunked Stdout Parsing

`ProviderProcessSupervisor.stream_output()` reads 4096-byte chunks. Each provider has a parser:

| Parser | File | Mode |
|--------|------|------|
| `ClaudeCodeCLIParser` | `mc/contexts/provider_cli/providers/claude_code.py` | NDJSON (same as above) |
| `CodexCLIParser` | `mc/contexts/provider_cli/providers/codex.py` | Regex-based plain text |
| `NanobotCLIParser` | `mc/contexts/provider_cli/providers/nanobot.py` | Prefix-based (`[progress]`, `[tool]`, `[nanobot-live]`) |

**Event types from parsers** (`ParsedCliEvent(kind=...)`):

| Kind | Emitted By |
|------|-----------|
| `text` | ClaudeCodeCLIParser, CodexCLIParser |
| `tool_use` | ClaudeCodeCLIParser |
| `result` | ClaudeCodeCLIParser only (Codex/Nanobot never emit this — fall back to text concatenation) |
| `error` | ClaudeCodeCLIParser, CodexCLIParser |
| `session_id` | ClaudeCodeCLIParser |
| `session_discovered` | CodexCLIParser |
| `ask_user_requested` | ClaudeCodeCLIParser |
| `approval_requested` | CodexCLIParser |
| `output` | CodexCLIParser, NanobotCLIParser |
| `tool` | NanobotCLIParser |
| `progress` | NanobotCLIParser |
| `session_ready` / `session_failed` | NanobotCLIParser |

**Process lifecycle:**

| Phase | Timeout | Mechanism |
|-------|---------|-----------|
| Startup | 30s | `parser.start_session()` via `wait_for` |
| Stream idle | 300s | Per-chunk read timeout |
| Exit wait | 30s | `supervisor.wait_for_exit()` via `wait_for` |

**Signals:** `interrupt` → `SIGINT` to pgid; `stop`/`terminate` → `SIGTERM` to pgid; `kill` → `SIGKILL` to pgid. Process group (`start_new_session=True`) ensures all children are signaled.

### Provider-to-Live Canonical Translation

All runner strategies write to `sessionActivityLog` via `SessionActivityService` (`mc/contexts/interactive/activity_service.py`). This service is the **single point** for Live tab persistence — both nanobot and provider-cli runners use it.

| Python metadata key | Convex field | Description |
|---------------------|-------------|-------------|
| `source_type` | `sourceType` | Canonical event classification: `system`, `assistant`, `tool_use`, `result`, `error` |
| `source_subtype` | `sourceSubtype` | Finer classification (e.g. `init`, `text`, tool name, `success`, `error`) |
| `turn_id` | `groupKey` | Groups related events from the same provider turn. Only set when the parser provides explicit turn boundaries; absent for Claude Code sessions until turn-boundary parsing is added. |
| `event.text` | `rawText` | Original text content from the parsed event |
| `metadata.tool_input` | `rawJson` | Raw JSON payload (tool input or structured data) |

The service provides four write methods, each targeting a different event source:

| Method | Used by | Purpose |
|--------|---------|---------|
| `upsert_session()` | All runners | Create/update session in `interactiveSessions` |
| `append_event()` | Nanobot `on_progress` callback | Generic event (text, tool_use) |
| `append_result()` | All runners | Result event after execution |
| `append_parsed_cli_event()` | Provider-CLI | Translates `ParsedCliEvent` into unified format |

The frontend normalizer in `providerLiveEvents.ts` prefers canonical `sourceType` for classification when present, falling back to the existing heuristic path for legacy rows without canonical metadata.

### 4.4 Nanobot Runner — In-Process

The agent loop runs **in-process** as an async coroutine (`AgentLoop.process_direct_result()`). The nanobot `AgentLoop` has a built-in `on_progress(text, *, tool_hint=False)` callback that `NanobotRunnerStrategy` wires to `SessionActivityService.append_event()` for real-time Live tab events. Session lifecycle (ready/ended/error) and result events also go through the service.

When the model calls MC tools, the `AgentLoop` spawns a child `mc.runtime.mcp.bridge` subprocess via MCP stdio transport. This child process uses `InteractionService` (direct Convex HTTP) rather than a Unix socket — `MC_SOCKET_PATH` is **not set** for the nanobot MCP bridge; only `TASK_ID`, `AGENT_NAME`, `CONVEX_URL`, and `CONVEX_ADMIN_KEY` are injected.

### 4.5 Environment Variable Injection

All runners inject environment variables into their subprocess. The base set:

| Variable | Set By | Purpose |
|----------|--------|---------|
| `AGENT_NAME` | All runners | Agent identity |
| `TASK_ID` | All runners | Task context |
| `STEP_ID` | Provider CLI | Step context |
| `MC_SOCKET_PATH` | CC + ProviderCLI only (via `.mcp.json`) | IPC socket location |
| `MC_INTERACTIVE_SESSION_ID` | Provider CLI, CC (interactive) | Session identity |
| `CONVEX_URL` | All runners | Convex connection |
| `CONVEX_ADMIN_KEY` | All runners | Convex auth |

**API keys** are resolved via `resolve_secret_env()` (`mc/infrastructure/secrets.py`): reads all `spec.env_key` values from registered providers (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.) plus `BRAVE_API_KEY`.

---

## 5. Subscription & Event Architecture

The MC Gateway uses **native Convex WebSocket subscriptions** for real-time updates from Convex to Python. This replaced the previous polling strategy — do not reintroduce polling.

### 5.1 Gateway Async Tasks

`run_gateway()` creates **11 named `asyncio.create_task()`** calls:

| Task | Component | File |
|------|-----------|------|
| `inbox_task` | `orchestrator.start_inbox_routing_loop()` | `mc/runtime/orchestrator.py` |
| `routing_task` | `orchestrator.start_routing_loop()` | `mc/runtime/orchestrator.py` |
| `review_task` | `orchestrator.start_review_routing_loop()` | `mc/runtime/orchestrator.py` |
| `kickoff_task` | `orchestrator.start_kickoff_watch_loop()` | `mc/runtime/orchestrator.py` |
| `execution_task` | `executor.start_execution_loop()` | `mc/contexts/execution/executor.py` |
| `timeout_task` | `timeout_checker.start()` | `mc/runtime/timeout_checker.py` |
| `plan_negotiation_task` | `_run_plan_negotiation_manager()` | `mc/contexts/planning/supervisor.py` |
| `chat_task` | `chat_handler.run()` | `mc/contexts/conversation/chat_handler.py` |
| `mention_task` | `mention_watcher.run()` | `mc/contexts/conversation/mentions/watcher.py` |
| `ask_user_watcher_task` | `ask_user_watcher.run()` | `mc/contexts/conversation/ask_user/watcher.py` |
| `sleep_control_task` | `sleep_controller.watch_control()` | `mc/runtime/sleep_controller.py` |

All tasks are independent. No `gather()` or `TaskGroup`. Each has its own error handling — one task crashing does not affect others. Shutdown: explicit `.cancel()` on each task followed by `await`, suppressing `CancelledError`.

### 5.2 All Subscription & Polling Loops

> **Subscription (preferred):** Uses `async_subscribe()` → `_subscribe_loop` with native Convex WebSocket. Zero queries when idle.
> **Polling (legacy/specific use):** Uses `asyncio.sleep` + `client.query` loops. Only acceptable for components that cannot use subscriptions (e.g. `TimeoutChecker` which runs periodic one-shot queries, `SleepController` which polls a control setting).

| Component | Query | Mode | Sleep Aware |
|-----------|-------|------|-------------|
| InboxWorker | `tasks:listByStatus {inbox}` | Subscription | Yes |
| PlanningWorker | `tasks:listByStatus {planning}` | Subscription | Yes |
| ReviewWorker | `tasks:listByStatusLite {review}` | Subscription | Yes |
| KickoffResumeWorker | `tasks:listByStatus {in_progress}` | Subscription | Yes |
| TaskExecutor | `tasks:listByStatusLite {assigned}` | Subscription | Yes |
| PlanNegotiationSupervisor | `tasks:listByStatus {review}` | Subscription (shared) | Yes |
| PlanNegotiationSupervisor | `tasks:listByStatus {in_progress}` | Subscription (shared) | Yes |
| PlanNegotiation (per-task) | `messages:listByTask {task_id}` | Subscription | Yes |
| ChatHandler | `chats:listPending` | Subscription | Yes |
| MentionWatcher | `messages:listRecentUserMessages` | Subscription | Yes |
| AskUserReplyWatcher | `messages:listByTask` (per active ask) | Subscription | Yes |
| TimeoutChecker | `tasks:listByStatusLite` (2 queries) | Polling (one-shot) | Yes |
| SleepController | `settings:getGatewaySleepControl` | Polling (1s control) | N/A |

### 5.3 Sleep Controller

**File:** `mc/runtime/sleep_controller.py`

Two modes: `active` and `sleep`. With real subscriptions, the sleep controller no longer throttles query frequency — subscriptions are zero-cost when idle. The controller now tracks work/idle state for auto-sleep transitions and waking.

| Property | Value |
|----------|-------|
| Auto-sleep timeout | 120s of idle |
| Control poll | 1s |

**Transitions:**
- `record_work_found()` → `active` (resets idle timer)
- `record_idle()` → `sleep` (only if idle ≥ `auto_sleep_after_seconds`)
- `apply_manual_mode(mode)` → manual override from Convex `settings:getGatewaySleepControl`

**Subscription behavior during sleep:** Unlike the old polling loops, WebSocket subscriptions cannot be paused. During sleep mode, subscriptions remain connected (zero cost) and `record_work_found()` / `record_idle()` are called normally. If data arrives during sleep, it immediately wakes the controller.

**Notification:** Uses `asyncio.Event`. On mode transition, the old event is `.set()` and replaced. All pollers waiting on `wait_for_next_cycle()` wake immediately.

### 5.4 Event Propagation: Convex → Gateway

```text
1. Dashboard/user calls Convex mutation (e.g., tasks:create)
2. Poll loop queries tasks:listByStatus on timer
3. Result differs from last → pushed to consumer queue
4. Worker unblocks (queue.get()), calls process_batch()
5. Worker checks dedup (known_ids + runtime claim)
6. Worker processes task → Convex mutations → state change
```

### 5.5 Deduplication Mechanisms

#### In-Memory Sets

| Location | Set/Dict | Max Size | Eviction |
|----------|----------|----------|----------|
| InboxWorker `_known_inbox_ids` | `set[str]` | Unbounded | `&= current_ids` each batch |
| PlanningWorker `_known_planning_ids` | `set[str]` | Unbounded | `&= current_ids` each batch |
| ReviewWorker `_known_review_task_ids` | `set[str]` | Unbounded | `&= current_ids` each batch |
| TaskExecutor `_known_assigned_ids` | `set[str]` | Unbounded | `discard()` on completion |
| Orchestrator `_known_kickoff_ids` (shared) | `set[str]` | Unbounded | `&= current_ids` each batch; **written by both PlanningWorker and KickoffResumeWorker** (prevents double-dispatch) |
| KickoffResumeWorker `_processed_signatures` | `dict[str,str]` | Unbounded | Stale task_ids removed each batch |
| PlanNegotiationSupervisor `_active_negotiation_ids` | `set[str]` | Unbounded | `discard()` on cleanup |
| PlanNegotiationSupervisor `_cron_requeued_ids` | `set[str]` | Unbounded | One-shot: `discard()` after skipping, prevents negotiation for cron-requeued tasks |
| TimeoutChecker `_flagged_stalled` | `set[str]` | Unbounded | **Never evicted** (process-lifetime); resolved tasks won't be re-flagged until restart |
| TimeoutChecker `_flagged_reviews` | `set[str]` | Unbounded | **Never evicted** (same as above) |
| MentionWatcher `_seen_message_ids` | `set[str]` | **5,000** | Replace with current batch when over limit |
| PlanNegotiation (per-task) `seen_message_ids` | `set[str]` | **1,000** | Replace with current batch when over limit |
| AskUserReplyWatcher `_seen_messages` | `dict[str,set]` | Unbounded | Task-level cleanup on registry exit |

#### Distributed Dedup via `runtimeClaims:acquire`

**File:** `mc/bridge/runtime_claims.py`

Every worker calls `acquire_runtime_claim()` before processing. This is a Convex mutation returning `{granted: bool}`.

| Property | Value |
|----------|-------|
| Owner ID | UUID per bridge instance |
| Default lease | 300s |
| Claim kind formula | `"{scope}:v{state_version}:{status}:{review_phase}"` |

Claim kinds: `inbox:v...`, `planning:v...`, `review:v...`, `executor:v...`, `plan-negotiation:v...`, `kickoff:{signature}`, `mention-message`, `ask-user-reply`, `timeout-stalled:{updated_at}`, `timeout-review:{updated_at}`.

---

## 6. Dashboard ↔ Backend Communication

### 6.1 Convex Real-Time Subscriptions

The dashboard connects to Convex via the JS SDK WebSocket (reactive). Key subscription groups:

| Domain | Key Queries | Hooks |
|--------|-------------|-------|
| Tasks | `tasks.getDetailView`, `tasks.searchMergeCandidates`, `tasks.listDoneHistory` | `useTaskDetailView`, `useBoardView`, `useDoneTasksSheetData` |
| Boards | `boards.getBoardView`, `boards.getById`, `boards.list`, `boards.getDefault` | `useBoardView`, `useBoardSelectorData`, `useBoardSettingsSheet` |
| Agents | `agents.list`, `agents.listDeleted`, `agents.getByName` | `useAgentSidebarData`, `useAgentConfigSheetData` |
| Steps | (via `tasks.getDetailView`) | `useTaskDetailView` |
| Messages | (via `tasks.getDetailView`) | `useTaskDetailView` |
| Sessions | `interactiveSessions.listSessions`, `sessionActivityLog.listForSession` | `useTaskInteractiveSession`, `useProviderSession` |
| Settings | `settings.list`, `settings.get`, `settings.getGatewaySleepRuntime` | `useSettingsPanelState`, `useModelTierSettings`, `useGatewaySleepRuntime` |
| Tags | `taskTags.list`, `tagAttributes.list` | `useTagsPanelData`, `useTaskInputData` |
| Squads | `squadSpecs.list`, `squadSpecs.getById`, `workflowSpecs.listBySquad` | `useSquadSidebarData`, `useSquadDetailData` |
| Skills | `skills.list` | `useSkillsSelectorData` |
| Terminal | `terminalSessions.get` | `useTerminalPanelState` |
| Chat | `chats.listByAgent` | `useChatMessages` |
| Activity | `activities.listRecent` | `useActivityFeed` |

**Pattern:** Feature hooks abstract all Convex access. Components never call `useQuery`/`useMutation` directly — they go through hooks like `useTaskDetailView(taskId)`, `useBoardView(filters)`, `useAgentConfigSheetData(name)`.

### 6.2 Key Convex Mutations from Dashboard

#### Task Lifecycle

| Mutation | Trigger |
|----------|---------|
| `tasks.create` | TaskInput form submit |
| `tasks.approve` | "Approve" button |
| `tasks.approveAndKickOff` | "Kick off" button |
| `tasks.pauseTask` | "Pause" button |
| `tasks.resumeTask` | "Resume" button |
| `tasks.retry` | "Retry" on failed task |
| `tasks.softDelete` / `tasks.restore` | Trash / restore actions |
| `tasks.saveExecutionPlan` / `tasks.clearExecutionPlan` | Plan editor |
| `tasks.manualMove` | Kanban drag-and-drop |
| `tasks.startInboxTask` | "Start" on inbox task |
| `tasks.launchMission` | Squad mission dialog |
| `tasks.createMergedTask` / `tasks.addMergeSource` / `tasks.removeMergeSource` | Merge actions |
| `tasks.updateTags` / `tasks.updateTitle` / `tasks.updateDescription` | Inline editing |
| `tasks.addTaskFiles` / `tasks.removeTaskFile` | File management |
| `tasks.toggleFavorite` | Star/favorite button |
| `tasks.clearAllDone` | "Clear done" board action |
| `tasks.deny` / `tasks.returnToLeadAgent` | Rejection actions |

#### Steps

| Mutation | Trigger |
|----------|---------|
| `steps.acceptHumanStep` | "Accept" on human-review step |
| `steps.retryStep` | Retry crashed step |
| `steps.manualMoveStep` | Manual step status change |
| `steps.addStep` / `steps.updateStep` / `steps.deleteStep` | Plan editor |

#### Messages

| Mutation | Trigger |
|----------|---------|
| `messages.sendThreadMessage` | Thread composer → agent |
| `messages.postUserPlanMessage` | Thread composer → plan review |
| `messages.postComment` | Thread composer → comment |
| `messages.postUserReply` | Reply input |
| `messages.postMentionMessage` | `@agent` mention send |
| `chats.send` | Direct agent chat |

#### Agents / Settings / Boards

| Mutation | Trigger |
|----------|---------|
| `agents.updateConfig` | AgentConfigSheet save |
| `agents.setEnabled` | Enable/disable toggle |
| `agents.softDeleteAgent` / `agents.restoreAgent` | Agent delete/restore |
| `settings.set` | SettingsPanel save |
| `settings.requestGatewaySleepMode` | Sleep toggle |
| `boards.create` / `boards.update` / `boards.softDelete` | Board management |
| `squadSpecs.publishGraph` / `squadSpecs.updatePublishedGraph` | Squad authoring |
| `squadSpecs.archiveSquad` / `squadSpecs.unarchiveSquad` | Squad lifecycle |
| `taskTags.create` / `taskTags.remove` / `taskTags.updateAttributeIds` | Tag management |
| `tagAttributes.create` / `tagAttributes.remove` | Attribute management |
| `tagAttributeValues.upsert` / `tagAttributeValues.removeByTaskAndTag` | Tag attribute values |
| `activities.create` / `activities.clearAll` | Activity feed |

#### Interactive Sessions

| Mutation | Trigger |
|----------|---------|
| `interactiveSessions.requestHumanTakeover` | "Take over" button |
| `interactiveSessions.resumeAgentControl` | "Resume agent" button |
| `interactiveSessions.markManualStepDone` | "Done" in takeover |
| `terminalSessions.sendInput` | Terminal key input |
| `terminalSessions.wake` | Wake sleeping terminal |

### 6.3 Next.js API Routes

All routes under `dashboard/app/api/`. These handle operations requiring server-side filesystem access or subprocess spawning.

#### Authentication

| Method | Route | Backend |
|--------|-------|---------|
| `POST` | `/api/auth` | Validates `token` against `MC_ACCESS_TOKEN` env var; sets `mc_session` cookie (SHA-256 hash, httpOnly, 7-day) |
| `POST` | `/api/auth/logout` | Clears `mc_session` cookie |

#### Files & Artifacts

| Method | Route | Backend |
|--------|-------|---------|
| `POST` | `/api/tasks/[taskId]/files` | Writes to `~/.nanobot/tasks/{id}/attachments/` (max 10MB) |
| `DELETE` | `/api/tasks/[taskId]/files` | Deletes from `attachments/` only |
| `GET` | `/api/tasks/[taskId]/files/[subfolder]/[filename]` | Serves from `attachments/` or `output/` (path-traversal-safe) |
| `GET/POST` | `/api/boards/[boardName]/artifacts` | List / upload board artifacts |
| `GET` | `/api/boards/[boardName]/artifacts/[...path]` | Serve artifact file |

#### Agents

| Method | Route | Backend |
|--------|-------|---------|
| `POST` | `/api/agents/create` | Creates `config.yaml` + `SOUL.md` in `~/.nanobot/agents/{name}/` |
| `PUT` | `/api/agents/[name]/config` | Reads, merges, writes agent YAML |
| `GET/PUT` | `/api/agents/[name]/memory/[file]` | Read/write `MEMORY.md` or `HISTORY.md` |
| `POST` | `/api/agents/assist` | *Deprecated* — LLM-generates YAML config from chat transcript (Python subprocess) |

#### Specs (Convex Admin)

| Method | Route | Backend |
|--------|-------|---------|
| `POST` | `/api/specs/agent` | `agentSpecs:createDraft` + `agentSpecs:publish` via `ConvexHttpClient` (admin key) |
| `POST` | `/api/specs/squad` | `squadSpecs:publishGraph` via `ConvexHttpClient` (admin key) |
| `GET` | `/api/specs/squad/context` | Queries Convex for agents, skills, reviewSpecs, models |

#### Other

| Method | Route | Backend |
|--------|-------|---------|
| `POST` | `/api/authoring/agent-wizard` | Python subprocess → LLM-driven agent authoring |
| `GET` | `/api/settings/global-orientation-default` | Reads `~/.nanobot/mc/agent-orientation.md` |
| `GET` | `/api/channels` | Reads `~/.nanobot/config.json` |
| `GET/DELETE/PATCH` | `/api/cron[/jobId]` | Reads/writes `~/.nanobot/cron/jobs.json` |
| `POST` | `/api/terminal/launch` | Spawns OS terminal running `claude` CLI |

### 6.4 WebSocket (Interactive Terminal)

| Component | URL | Purpose |
|-----------|-----|---------|
| `AgentTerminal` | `ws://{host}:8765/interactive?...` | xterm.js terminal for agent chat sessions |
| `InteractiveTerminalPanel` (deprecated) | `ws://{host}:8765/interactive?...` | Full task-scoped interactive terminal with takeover |

**Messages (client → server):**

```json
{"type": "input", "data": "<keystrokes>"}
{"type": "resize", "columns": 120, "rows": 40}
{"type": "terminate"}
```

**Messages (server → client):**

```json
{"type": "attached"}
{"type": "error", "message": "..."}
```

Plus raw binary `ArrayBuffer` for PTY output.

### 6.5 Authentication Flow

1. User POSTs `{token}` to `/api/auth`
2. Server validates against `process.env.MC_ACCESS_TOKEN`
3. Sets `mc_session` cookie = `SHA-256(token)` (httpOnly, sameSite=lax, 7-day)
4. Middleware on all routes checks cookie against hash
5. If `MC_ACCESS_TOKEN` not set → open mode (no auth required)
6. No JWT, OAuth, or user accounts — single shared token for local use

---

## 7. Inter-Agent Communication

All agent-to-agent communication is **mediated through Convex**. No direct socket or RPC channel exists between agents.

### 7.1 Delegation Patterns

Three routing modes, selected during inbox processing (`mc/runtime/workers/inbox.py`):

**Mode A: AI Workflow** (`work_mode = "ai_workflow"`)
- Task has a pre-compiled execution plan
- `inbox` → `review` (awaitingKickoff=true, reviewPhase="plan_review")
- User kicks off → `KickoffResumeWorker` materializes steps and dispatches

**Mode B: Direct Delegate** (`work_mode = "direct_delegate"`)
- `DirectDelegationRouter.route()` selects agent by:
  1. Board-scoped filtering (`enabledAgents`)
  2. Explicit `assignedAgent` override
  3. Least-loaded agent by `tasksExecuted`
- `inbox` → `assigned` with selected agent

**Mode C: Lead Agent Planning** (default)
- `inbox` → `planning`
- `TaskPlanner.plan_task()` calls LLM with `NEGOTIATION_SYSTEM_PROMPT`
- LLM returns JSON plan with steps (agent assignments, dependencies, parallel groups)
- If supervised: → `review` for user approval
- If autonomous: → materialize + dispatch immediately

### 7.2 Task Thread Messaging

**Schema** (`dashboard/convex/schema.ts`, `messages` table):

| Field | Type | Description |
|-------|------|-------------|
| `taskId` | `Id<"tasks">` | Required link to task |
| `authorName` | `string` | Who posted |
| `authorType` | `"agent"` \| `"user"` \| `"system"` | Poster type |
| `content` | `string` | Message body |
| `messageType` | `string` | Legacy: `work`, `review_feedback`, `approval`, `denial`, `system_event`, `user_message` |
| `type` | `string?` | Unified: `step_completion`, `user_message`, `system_error`, `lead_agent_plan`, `lead_agent_chat`, `comment` |
| `artifacts` | `[{path, action, description?, diff?}]?` | File artifacts |
| `planReview` | `{kind, planGeneratedAt, decision?}?` | Plan review metadata |
| `leadAgentConversation` | `boolean?` | Participates in plan negotiation |

### 7.3 Mention Routing

```text
User writes "@researcher summarize this"
  → Any message mutation (postMentionMessage, sendThreadMessage, postUserReply, etc.)
  → MentionWatcher polls messages:listRecentUserMessages (10s, with 30s overlap window)
  → Detects new message, checks _seen_message_ids
  → acquire_runtime_claim(claim_kind="mention-message", entity_id=msg_id)
  → ConversationIntentResolver.resolve(content, task_data)
    Priority: empty→COMMENT, @mention→MENTION, pending_ask→MANUAL_REPLY,
              negotiable→PLAN_CHAT, active+assigned→FOLLOW_UP, default→COMMENT
  → MENTION → handle_all_mentions()
    → extract_mentions() via regex: r"@([\w][\w\-]*)"
    → filter to agents with config.yaml in ~/.nanobot/agents/
    → asyncio.gather(handle_mention(agent1), handle_mention(agent2))
      → load agent YAML, resolve tier, inject global orientation
      → build full prompt with task context + thread history
      → AgentLoop.process_direct() → LLM call → response
      → bridge.send_message(task_id, agent_name, "agent", response, "work")
```

### 7.4 Ask-User Lifecycle

```text
1. Agent calls ask_user tool → MCSocketServer._handle_ask_user()
   → delegates to AskUserHandler.ask() (mc/contexts/conversation/ask_user/handler.py)

2. AskUserHandler.ask():
   a. Posts question to task thread (bridge.send_message)
   b. Creates asyncio.Future, registers in AskUserRegistry (_task_to_request)
   c. Transitions step to waiting_human (bridge.update_step_status)
   d. Transitions task to review (review_phase="execution_pause")
   e. Creates REVIEW_REQUESTED activity event
   f. await future  ← blocks agent execution

3. AskUserReplyWatcher polls every 1.5s:
   a. For each task in registry.active_task_ids()
   b. Queries messages:listByTask
   c. Finds new user message
   d. Classifies intent (skips if MENTION)
   e. acquire_runtime_claim(claim_kind="ask-user-reply")
   f. registry.deliver_reply(task_id, content)
      → future.set_result(content)  ← unblocks agent

4. Agent resumes (back in AskUserHandler.ask()):
   a. Transitions task back to in_progress
   b. Transitions step back to running
   c. Creates STEP_STARTED activity event
   d. Returns answer to agent loop
```

### 7.5 Plan Negotiation Loop

```text
1. PlanNegotiationSupervisor subscribes to review + in_progress queues (5s each)
2. For eligible tasks (has execution_plan, review_phase=plan_review):
   a. acquire_runtime_claim
   b. Spawn per-task start_plan_negotiation_loop()
3. Per-task loop subscribes to messages:listByTask (2s poll):
   a. Filters for new user messages with leadAgentConversation=true
   b. Skips @mentions (MentionWatcher owns those)
   c. Calls handle_plan_negotiation():
      → LLM chat with NEGOTIATION_SYSTEM_PROMPT
      → Parses JSON response: action="update_plan" or "clarify"
      → update_plan: validates no locked steps touched, writes to Convex
      → clarify: posts follow-up question as lead_agent_chat message
4. Loop exits when task leaves negotiable status
```

### 7.6 Review Flow

```text
1. All steps complete → task transitions to review
2. ReviewWorker picks up (5s poll):
   a. If reviewers list non-empty: posts "Review requested" system message
   b. If trust_level="human_approved": creates HITL_REQUESTED activity

3. On approval (dashboard mutation):
   a. Posts approval message (MessageType.APPROVAL)
   b. If autonomous: task → done
   c. If human_approved: awaits human confirmation

4. On feedback/revision:
   a. Posts review_feedback message
   b. Agent revises → posts work message
   c. Returns to review

5. Workflow review steps (step_type="review"):
   a. Agent outputs verdict: {verdict: "approved"|"rejected", recommended_return_step}
   b. On rejection: step → BLOCKED, return_step → ASSIGNED (restarts branch)
```

---

## 8. Hooks System

Two independent hook mechanisms serve different purposes.

### 8.1 Interactive Supervision Hooks (CC Lifecycle)

**File:** `vendor/claude-code/claude_code/hook_bridge.py`

**Purpose:** Forward all Claude Code lifecycle events to `MCSocketServer.emit_supervision_event()`.

**Activation:** Only when `MC_INTERACTIVE_SESSION_ID` is set (step-execution sessions). `CCWorkspaceManager._generate_hook_settings()` writes `.claude/settings.json` with hooks for 7 event types:

```
SessionStart, UserPromptSubmit, PermissionRequest, Stop,
PreToolUse, PostToolUse, PostToolUseFailure
```

All route to the same subprocess command:
```bash
MC_SOCKET_PATH=... MC_INTERACTIVE_SESSION_ID=... uv run python -m claude_code.hook_bridge
```

**Flow:** stdin JSON event → enrich with session/task/agent IDs → `emit_supervision_event` IPC call → `normalize_provider_event()` → `interactive_supervisor.handle_event()`.

### 8.2 Plan Tracking & Agent Tracking Hooks

**File:** `mc/hooks/dispatcher.py`, `mc/hooks/handlers/`

**Purpose:** Local state tracking (plans, agents, skills) with optional IPC reporting.

**Discovery:** Convention-based. `discovery.discover_handlers()` auto-imports all `.py` files in `mc/hooks/handlers/`, collects `BaseHandler` subclasses. Results are cached.

| Handler | Events | IPC | Purpose |
|---------|--------|-----|---------|
| `PlanTrackerHandler` | `PostToolUse/Write`, `TaskCompleted` | None | Parses plan files, writes `.claude/plan-tracker/` |
| `MCPlanSyncHandler` | `PostToolUse/Write`, `TaskCompleted` | `report_progress` | Same + notifies MC via `SyncIPCClient` |
| `SkillTrackerHandler` | `PostToolUse/Skill` | None | Records `active_skill` in session state |
| `AgentTrackerHandler` | `SubagentStart`, `SubagentStop` | None | Maintains `active_agents` dict |
| `PlanCaptureHandler` | `PostToolUse/ExitPlanMode` | None | Records `active_plan` from context |

**Session state:** Per-session JSON at `.claude/hook-state/{session_id}.json` with `fcntl.flock` concurrency control. Auto-prunes files older than 24 hours.

**Output:** If any handler returns non-empty string, dispatcher writes to stdout:
```json
{"hookSpecificOutput": {"hookEventName": "<event>", "additionalContext": "<combined>"}}
```

This is injected as context for the agent's next turn.

---

## 9. Workflow State Machine

**Single source of truth:** `shared/workflow/workflow_spec.json`

Loaded by both Python (`mc/domain/workflow_contract.py`) and TypeScript (`dashboard/convex/lib/workflowContract.ts`).

### Task Transitions

```text
inbox       → [assigned, planning]
planning    → [failed, review, ready, in_progress]
ready       → [in_progress, planning, failed]
failed      → [planning]
assigned    → [in_progress, assigned]
in_progress → [review, done, assigned]
review      → [done, inbox, assigned, in_progress, planning]
done        → [assigned]
retrying    → [in_progress, crashed]
crashed     → [inbox, assigned]

Universal targets (from any status): retrying, crashed, deleted
```

### Step Transitions

```text
planned        → [assigned, blocked]
assigned       → [running, review, completed, crashed, blocked, waiting_human]
running        → [review, completed, crashed]
review         → [running, completed, crashed]
waiting_human  → [running, completed, crashed]
completed      → []   (terminal)
crashed        → [assigned]   (retry)
blocked        → [assigned, crashed]
```

### Transition Events

| Transition | Activity Event |
|------------|---------------|
| `inbox → assigned` | `task_assigned` |
| `inbox → planning` | `task_planning` |
| `planning → failed` | `task_failed` |
| `planning → review` | `task_planning` |
| `planning → ready` | `task_planning` |
| `planning → in_progress` | `task_started` |
| `ready → in_progress` | `task_started` |
| `ready → planning` | `task_planning` |
| `ready → failed` | `task_failed` |
| `failed → planning` | `task_planning` |
| `assigned → in_progress` | `task_started` |
| `assigned → assigned` | `task_reassigned` |
| `in_progress → review` | `review_requested` |
| `in_progress → done` | `task_completed` |
| `in_progress → assigned` | `task_assigned` |
| `review → done` | `task_completed` |
| `review → inbox` | `task_retrying` |
| `review → assigned` | `thread_message_sent` |
| `review → in_progress` | `task_started` |
| `review → planning` | `task_planning` |
| `done → assigned` | `thread_message_sent` |
| `retrying → in_progress` | `task_retrying` |
| `retrying → crashed` | `task_crashed` |
| `crashed → inbox` | `task_retrying` |
| `crashed → assigned` | `thread_message_sent` |

**Universal target events:** `→ retrying` emits `task_retrying`; `→ crashed` emits `task_crashed`.

### Mention-Safe Statuses

`["inbox", "assigned", "in_progress", "review", "done", "crashed", "retrying"]` — tasks in these statuses accept `@agent` mentions.

---

## 10. External Platform Integrations (Linear)

### 10.1 Inbound — Webhook Flow

```text
Linear sends POST /api/integrations/linear/webhook
  → Next.js route handler (dashboard/app/api/integrations/linear/webhook/route.ts)
    → Validates HMAC-SHA256 signature (Linear-Signature header, via LinearAdapter.verify_webhook_signature)
    → On success: writes raw payload to Convex via public mutation (integrations:recordWebhookEvent)
  → MC Gateway InboxWorker detects new tasks naturally via existing polling
```

Key properties:

| Property | Value |
|----------|-------|
| Signature algorithm | HMAC-SHA256 |
| Signature header | `Linear-Signature` |
| Loop prevention | Skip events with `actor.type == "application"` (our own app) |
| MC comment prefix | `[MC]` — inbound pipeline skips these to prevent echo |

### 10.2 Outbound — MC → Linear Sync

```text
MC Gateway boot:
  IntegrationSyncService.initialize()
    → bridge.get_enabled_integration_configs()
    → For each config: AdapterRegistry.create_adapter(config)
    → LinearAdapter created with LinearGraphQLClient(api_key)

  If active_integrations > 0:
    OutboundPipeline + IntegrationOutboundWorker spawned as asyncio task (10s poll)

Each poll cycle (IntegrationOutboundWorker):
  → bridge.get_enabled_integration_configs()  (re-reads, live config)
  → For each config_id:
      OutboundPipeline.process_outbound_batch(config_id, since_timestamp)
        → bridge.get_outbound_pending(config_id, since)  → {messages, activities}
        → For messages: adapter.publish_comment(external_id, body) → Linear GraphQL
        → For activities: adapter.publish_status_change(external_id, mc_status, mapped_status)
                             → resolves workflow state ID → Linear GraphQL updateIssue
```

| Property | Value |
|----------|-------|
| Poll interval | 10s active, 60s sleep (configurable `integration_poll_seconds`) |
| GraphQL endpoint | `https://api.linear.app/graphql` |
| Auth | Bearer token (api_key from Convex integrationConfigs) |
| Workflow state cache | Per-team, in-memory, for the lifetime of the adapter instance |

### 10.3 Inbound Pipeline — Deduplication

`InboundPipeline` (`mc/contexts/integrations/pipeline/inbound.py`) is the normalizer for external webhooks:

1. Looks up adapter by `integration_id` from `AdapterRegistry`
2. Calls `adapter.normalize_webhook(raw_payload, headers)` → `list[IntegrationEvent]`
3. Deduplicates via in-memory `_processed_keys: set[str]` (idempotency_key per event)

| Component | File |
|-----------|------|
| `InboundPipeline` | `mc/contexts/integrations/pipeline/inbound.py` |
| `OutboundPipeline` | `mc/contexts/integrations/pipeline/outbound.py` |
| `IntegrationOutboundWorker` | `mc/runtime/integrations/outbound_worker.py` |
| `IntegrationSyncService` | `mc/runtime/integrations/sync_service.py` |
| `AdapterRegistry` | `mc/contexts/integrations/registry.py` |
| `LinearAdapter` | `mc/contexts/integrations/adapters/linear.py` |
| `LinearGraphQLClient` | `mc/contexts/integrations/adapters/linear_client.py` |
