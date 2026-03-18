# Story CC-2: MCP Server Bridge

Status: ready-for-dev

## Story

As a **Claude Code agent**,
I want to access nanobot ecosystem tools (ask_user, send_message, delegate_task, ask_agent, report_progress) via MCP,
so that I can interact with users and other agents through Mission Control's channels and orchestration.

## Acceptance Criteria

### AC1: MCP Server Startup as stdio Process

**Given** the MCP bridge is configured in an agent's `.mcp.json`
**When** Claude Code starts and connects to the MCP server
**Then** the bridge process starts via `uv run python -m mc.mcp_bridge`
**And** it communicates with Claude Code via stdin/stdout using the MCP stdio protocol
**And** it receives environment variables: `MC_SOCKET_PATH`, `AGENT_NAME`, `TASK_ID`

### AC2: IPC with Mission Control via Unix Socket

**Given** the MCP bridge process is running
**When** it needs to communicate with the MC process (different PID)
**Then** it connects to a Unix domain socket at the path specified by `MC_SOCKET_PATH`
**And** sends JSON-RPC requests to MC and receives responses
**And** the MC process runs a socket server that handles these requests
**When** the socket connection fails
**Then** the MCP bridge returns a tool error: "Mission Control not reachable. Is the gateway running?"

### AC3: ask_user Tool

**Given** a Claude Code agent calls `mcp__nanobot__ask_user`
**When** the tool receives `question` (str) and optional `options` (list[str])
**Then** the MCP bridge sends the question to MC via socket
**And** MC routes it to the user's active channel (Telegram, Discord, dashboard thread)
**And** the tool **blocks** until the user responds (with a 300-second timeout)
**And** returns the user's answer as a string
**When** the user doesn't respond within 300 seconds
**Then** the tool returns: "User did not respond within 5 minutes. Proceed with your best judgment."

### AC4: send_message Tool

**Given** a Claude Code agent calls `mcp__nanobot__send_message`
**When** the tool receives `content` (str) and optional `channel` (str), `chat_id` (str)
**Then** the message is sent via MC's MessageBus to the specified channel
**And** if channel/chat_id are omitted, defaults to the task's originating channel
**And** returns confirmation: "Message sent"

### AC5: delegate_task Tool

**Given** a Claude Code agent calls `mcp__nanobot__delegate_task`
**When** the tool receives `description` (str), optional `agent` (str), optional `priority` (str)
**Then** MC creates a new task via Convex
**And** the orchestrator routes it to the specified agent (or auto-routes if omitted)
**And** returns: `{"task_id": "<id>", "status": "created"}`
**And** self-delegation is prevented (same agent cannot delegate to itself)

### AC6: ask_agent Tool

**Given** a Claude Code agent calls `mcp__nanobot__ask_agent`
**When** the tool receives `agent_name` (str) and `question` (str)
**Then** MC performs a synchronous inter-agent query (matching nanobot's ask_agent behavior)
**And** creates an isolated session for the target agent
**And** returns the target agent's response as a string
**And** depth limit of 2 is enforced (matching existing ask_agent behavior)

### AC7: report_progress Tool

**Given** a Claude Code agent calls `mcp__nanobot__report_progress`
**When** the tool receives `message` (str) and optional `percentage` (int)
**Then** MC posts an activity event to the task's Convex record
**And** the dashboard shows the progress update in real-time
**And** returns: "Progress reported"

## Tasks / Subtasks

- [ ] **Task 1: Create MCP bridge server module** (AC: #1)
  - [ ] 1.1 Create `mc/mcp_bridge.py` as a runnable module (`python -m mc.mcp_bridge`)
  - [ ] 1.2 Use the `mcp` Python SDK (`pip install mcp`) to create a stdio MCP server:
    ```python
    from mcp.server import Server
    from mcp.server.stdio import stdio_server

    server = Server("nanobot")
    ```
  - [ ] 1.3 Read config from environment: `MC_SOCKET_PATH`, `AGENT_NAME`, `TASK_ID`
  - [ ] 1.4 Add `if __name__ == "__main__"` block that runs the stdio server

- [ ] **Task 2: Implement Unix socket IPC client** (AC: #2)
  - [ ] 2.1 Create `mc/mcp_ipc.py` with `MCSocketClient` class:
    ```python
    class MCSocketClient:
        def __init__(self, socket_path: str):
            self._path = socket_path

        async def request(self, method: str, params: dict) -> dict:
            # Connect to unix socket, send JSON-RPC request, receive response
            reader, writer = await asyncio.open_unix_connection(self._path)
            request = json.dumps({"method": method, "params": params}) + "\n"
            writer.write(request.encode())
            await writer.drain()
            response = await asyncio.wait_for(reader.readline(), timeout=300)
            writer.close()
            return json.loads(response)
    ```
  - [ ] 2.2 Create `mc/mcp_ipc_server.py` with `MCSocketServer` class for the MC side:
    ```python
    class MCSocketServer:
        def __init__(self, bridge: ConvexBridge, bus: MessageBus):
            self._bridge = bridge
            self._bus = bus
            self._handlers: dict[str, Callable] = {}

        def register(self, method: str, handler: Callable): ...
        async def start(self, socket_path: str): ...
        async def stop(): ...
    ```
  - [ ] 2.3 Register handlers for: `ask_user`, `send_message`, `delegate_task`, `ask_agent`, `report_progress`

- [ ] **Task 3: Implement ask_user tool** (AC: #3)
  - [ ] 3.1 Register MCP tool in `mcp_bridge.py`:
    ```python
    @server.tool()
    async def ask_user(question: str, options: list[str] | None = None) -> str:
        result = await ipc.request("ask_user", {
            "question": question,
            "options": options,
            "agent_name": AGENT_NAME,
            "task_id": TASK_ID,
        })
        return result["answer"]
    ```
  - [ ] 3.2 Implement MC-side handler that posts question to task thread and waits for user response via Convex subscription or polling
  - [ ] 3.3 Add 300-second timeout with fallback message

- [ ] **Task 4: Implement send_message tool** (AC: #4)
  - [ ] 4.1 Register MCP tool with params: `content`, `channel` (optional), `chat_id` (optional)
  - [ ] 4.2 MC-side handler publishes `OutboundMessage` to MessageBus
  - [ ] 4.3 Default channel/chat_id from task metadata if omitted

- [ ] **Task 5: Implement delegate_task tool** (AC: #5)
  - [ ] 5.1 Register MCP tool with params: `description`, `agent` (optional), `priority` (optional)
  - [ ] 5.2 MC-side handler creates task in Convex via bridge mutation
  - [ ] 5.3 Prevent self-delegation: check `agent != AGENT_NAME`
  - [ ] 5.4 Return task_id and status

- [ ] **Task 6: Implement ask_agent tool** (AC: #6)
  - [ ] 6.1 Register MCP tool with params: `agent_name`, `question`
  - [ ] 6.2 MC-side handler reuses existing `AskAgentTool` logic (from `vendor/nanobot/nanobot/agent/tools/ask_agent.py`):
    - Load target agent config
    - Create isolated AgentLoop session
    - Execute with timeout (120s)
    - Enforce depth limit
  - [ ] 6.3 Return response string

- [ ] **Task 7: Implement report_progress tool** (AC: #7)
  - [ ] 7.1 Register MCP tool with params: `message`, `percentage` (optional)
  - [ ] 7.2 MC-side handler posts activity event to Convex:
    ```python
    bridge.mutation("activity:create", {
        "taskId": task_id,
        "eventType": "progress",
        "content": message,
        "authorType": "agent",
        "authorName": agent_name,
    })
    ```

- [ ] **Task 8: Add mcp dependency** (AC: #1)
  - [ ] 8.1 Add `mcp` to `pyproject.toml` dependencies: `mcp = ">=1.0"`
  - [ ] 8.2 Run `uv sync` to install

- [ ] **Task 9: Tests** (AC: all)
  - [ ] 9.1 Create `tests/mc/test_mcp_bridge.py` with unit tests:
    - Test each tool handler with mocked IPC
    - Test socket connection failure handling
    - Test ask_user timeout
    - Test self-delegation prevention
  - [ ] 9.2 Create `tests/mc/test_mcp_ipc.py` for socket client/server:
    - Test round-trip JSON-RPC message
    - Test connection error handling
  - [ ] 9.3 Run: `uv run pytest tests/mc/test_mcp_bridge.py tests/mc/test_mcp_ipc.py -v`

## Dev Notes

### Architecture & Design Decisions

**Why Unix sockets?** The MCP bridge runs as a subprocess of `claude` CLI (not MC). It needs to communicate with the MC process which has the ConvexBridge, MessageBus, and orchestrator. Unix domain sockets provide low-latency, reliable IPC on the same machine. Alternative: localhost HTTP — works but adds HTTP overhead. Unix sockets are simpler and more performant.

**Why a separate module (`mc.mcp_bridge`)?** The MCP bridge must be runnable as `python -m mc.mcp_bridge` because Claude Code spawns it as a stdio subprocess. It cannot import heavy MC dependencies at module level — it's a lightweight process that delegates to MC via IPC.

**Tool design mirrors nanobot tools**: Each MCP tool corresponds to an existing nanobot tool (`ask_agent`, `delegate_task`, `message`). This ensures behavioral consistency between nanobot agents and CC agents.

**ask_user is the key differentiator**: This tool replaces Claude Code's `AskUserQuestion` (which silently fails in headless mode). The MCP bridge routes questions through MC's channels to reach the user wherever they are (Telegram, Discord, dashboard).

### Code to Reuse

- `vendor/nanobot/nanobot/agent/tools/ask_agent.py` — synchronous inter-agent logic
- `vendor/nanobot/nanobot/agent/tools/mc_delegate.py` — task delegation logic
- `vendor/nanobot/nanobot/agent/tools/message.py` — message sending via bus
- `mc/bridge.py` — ConvexBridge for Convex mutations
- `mc/types.py` — ActivityEventType, MessageType enums

### Common Mistakes to Avoid

- Do NOT import ConvexBridge or MessageBus in `mcp_bridge.py` — it runs in a separate process. Use IPC.
- Do NOT make ask_user non-blocking — the Claude Code agent needs the answer before continuing.
- The `mcp` Python SDK uses asyncio — ensure the server loop runs properly.
- Unix socket paths have a max length (~104 chars on macOS). Use `/tmp/mc-{agent}.sock` format.
- Use `uv run python` not `python3`. Use `uv run pytest` for tests.

### Project Structure Notes

- **NEW**: `mc/mcp_bridge.py` — stdio MCP server (runs as subprocess of claude CLI)
- **NEW**: `mc/mcp_ipc.py` — Unix socket IPC client (used by mcp_bridge)
- **NEW**: `mc/mcp_ipc_server.py` — Unix socket IPC server (runs in MC gateway process)
- **NEW**: `tests/mc/test_mcp_bridge.py`
- **NEW**: `tests/mc/test_mcp_ipc.py`
- **MODIFIED**: `pyproject.toml` — add `mcp` dependency

### References

- `vendor/nanobot/nanobot/agent/tools/ask_agent.py` — inter-agent conversation
- `vendor/nanobot/nanobot/agent/tools/mc_delegate.py` — task delegation
- `vendor/nanobot/nanobot/agent/tools/message.py` — message sending
- `mc/bridge.py` — ConvexBridge class
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk

## Review Follow-ups (AI)

### CRITICAL

- [ ] [AI-Review][CRITICAL] C1: Files placed in `nanobot/mc/` instead of `mc/` (top-level). All imports use `nanobot.mc.*` but main branch uses `mc.*`. Move files to `mc/` and rewrite all imports. [nanobot/mc/mcp_bridge.py, nanobot/mc/mcp_ipc.py, nanobot/mc/mcp_ipc_server.py, tests/mc/test_mcp_bridge.py, tests/mc/test_mcp_ipc.py — ALL files]
- [ ] [AI-Review][CRITICAL] C2: `self._bus.publish(msg)` on line 181 of mcp_ipc_server.py will raise `AttributeError` — `MessageBus` has `publish_outbound()`, not `publish()`. [nanobot/mc/mcp_ipc_server.py:181]

### HIGH

- [ ] [AI-Review][HIGH] H1: No `ConnectionError` handling in `call_tool()` — AC2 requires returning "Mission Control not reachable. Is the gateway running?" on socket failure. Currently the exception propagates unhandled. [nanobot/mc/mcp_bridge.py:156-232]
- [ ] [AI-Review][HIGH] H2: AC6 depth limit (2) not enforced in `_handle_ask_agent`. No depth tracking or recursion limit exists. [nanobot/mc/mcp_ipc_server.py:243-330]
- [ ] [AI-Review][HIGH] H3: `_handle_send_message` returns `{"status": "Message sent"}` even when no delivery path succeeded (no bus, no bridge, no task_id). AC4 requires defaulting to originating channel — no such lookup exists. [nanobot/mc/mcp_ipc_server.py:202]
- [ ] [AI-Review][HIGH] H4: `priority` parameter from `delegate_task` tool is accepted but silently discarded — never passed to Convex mutation. [nanobot/mc/mcp_ipc_server.py:225-241]

### MEDIUM

- [ ] [AI-Review][MEDIUM] M1: `_handle_ask_user` posts question with `message_type="user_message"` — semantically incorrect for an agent-originated question. Should be `"work"` or a dedicated ask type. [nanobot/mc/mcp_ipc_server.py:139]
- [ ] [AI-Review][MEDIUM] M2: Module-level env var reads (`MC_SOCKET_PATH`, `AGENT_NAME`, `TASK_ID`) evaluated at import time — prevents runtime reconfiguration. Consider lazy reads. [nanobot/mc/mcp_bridge.py:25-27]
- [ ] [AI-Review][MEDIUM] M3: `report_progress` uses event type `"agent_output"` instead of `"progress"` as specified in AC7 / Task 7.2 spec. [nanobot/mc/mcp_ipc_server.py:349]
- [ ] [AI-Review][MEDIUM] M4: Test `test_ask_user_ipc_failure` asserts that `ConnectionError` propagates — this validates the bug (H1), not the spec requirement. Update test to verify friendly error message once H1 is fixed. [tests/mc/test_mcp_bridge.py:65-77]

### LOW

- [ ] [AI-Review][LOW] L1: `_pending_ask` keyed by `task_id` — concurrent `ask_user` calls for same task will clobber each other's futures. Use unique request ID. [nanobot/mc/mcp_ipc_server.py:147]
- [ ] [AI-Review][LOW] L2: `_handle_ask_agent` creates `MessageBus` and `AgentLoop` without cleanup — potential resource/task leaks from MCP connections. [nanobot/mc/mcp_ipc_server.py:303-304]
- [ ] [AI-Review][LOW] L3: `stop()` does not remove the socket file from disk — stale `.sock` remains after clean shutdown. [nanobot/mc/mcp_ipc_server.py:67-73]

## Dev Agent Record

### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
