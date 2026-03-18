# Story CC-5: Executor Integration

Status: ready-for-dev

## Story

As **Mission Control**,
I want the executor to route tasks to the Claude Code backend when an agent has `backend: claude-code`,
so that CC agents are seamlessly integrated into the existing task execution pipeline.

## Acceptance Criteria

### AC1: Backend Routing in Executor

**Given** a task is assigned to an agent with `backend: claude-code`
**When** `_execute_task()` processes this task
**Then** it routes to `_execute_cc_task()` instead of the existing nanobot agent loop
**And** the nanobot agent loop path remains unchanged for `backend: nanobot` agents
**When** `backend` is not set on the agent
**Then** it defaults to the nanobot path (backward compatible)

### AC2: CC Task Execution Flow

**Given** a task routed to the CC backend
**When** `_execute_cc_task()` runs
**Then** it follows this sequence:
  1. Load agent config (existing `_load_agent_config()`)
  2. Prepare workspace via `CCWorkspaceManager.prepare()`
  3. Start the MCP IPC socket server
  4. Execute via `ClaudeCodeProvider.execute_task()` with stream callback
  5. Stop the MCP IPC socket server
  6. Process the `CCTaskResult`
**And** task status transitions follow the existing pattern: assigned → in_progress → done/crashed

### AC3: Stream → Activity Events

**Given** a CC agent is executing and producing streamed output
**When** the stream callback receives text content
**Then** it posts activity events to the Convex task record
**And** these appear in the dashboard's activity feed in real-time
**When** the stream callback receives tool_use events
**Then** it logs them (for debugging) but does not post activity events for every tool call

### AC4: MCP IPC Server Lifecycle

**Given** a CC task execution starts
**When** the workspace is prepared and socket_path is known
**Then** the executor starts the `MCSocketServer` on the socket path
**And** the server remains running for the duration of the CC subprocess
**When** the CC subprocess completes (success or failure)
**Then** the executor stops the `MCSocketServer` and removes the socket file
**When** the socket file already exists (stale from crash)
**Then** it is removed before starting the new server

### AC5: Error Handling

**Given** a CC task execution
**When** the Claude Code CLI fails (non-zero exit, error result)
**Then** the task is transitioned to `crashed` with the error message
**And** an activity event is posted with the error details
**When** the workspace preparation fails
**Then** the task is transitioned to `crashed` before any CC subprocess is spawned
**When** the MCP IPC server fails to start
**Then** the task is transitioned to `crashed` with a descriptive error

### AC6: Cost Tracking

**Given** a CC task completes successfully
**When** the `CCTaskResult` contains `cost_usd` and `usage`
**Then** these are logged in the activity events
**And** the cost is available for monitoring/alerting

### AC7: Consolidation on Completion

**Given** a CC task completes
**When** the result is successful
**Then** the agent's CC session_id is stored (for future resume in CC-6)
**And** a completion message is posted to the task thread
**And** the task is transitioned to `done`

## Tasks / Subtasks

- [ ] **Task 1: Add backend routing to _execute_task** (AC: #1)
  - [ ] 1.1 In `mc/executor.py` `_execute_task()`, after loading agent config, check backend:
    ```python
    agent_data = self._load_agent_data(agent_name)  # returns AgentData with backend field
    if agent_data and agent_data.backend == "claude-code":
        await self._execute_cc_task(task_id, title, description, agent_name, agent_data)
        return
    # ... existing nanobot path continues below
    ```
  - [ ] 1.2 Create `_load_agent_data()` helper that returns full `AgentData` (including backend, claude_code_opts):
    ```python
    def _load_agent_data(self, agent_name: str) -> AgentData | None:
        from mc.gateway import AGENTS_DIR
        from mc.yaml_validator import validate_agent_file
        config_path = AGENTS_DIR / agent_name / "config.yaml"
        if not config_path.exists():
            return None
        result = validate_agent_file(config_path)
        if isinstance(result, list):
            return None
        return result
    ```

- [ ] **Task 2: Implement _execute_cc_task** (AC: #2, #3, #4, #5, #6, #7)
  - [ ] 2.1 Create the main CC execution method:
    ```python
    async def _execute_cc_task(
        self, task_id: str, title: str, description: str | None,
        agent_name: str, agent_data: AgentData
    ) -> None:
        from mc.cc_workspace import CCWorkspaceManager
        from mc.cc_provider import ClaudeCodeProvider
        from mc.mcp_ipc_server import MCSocketServer

        # 1. Prepare workspace
        try:
            ws_mgr = CCWorkspaceManager()
            ws_ctx = ws_mgr.prepare(agent_name, agent_data, task_id)
        except Exception as exc:
            await self._crash_task(task_id, title, f"Workspace preparation failed: {exc}")
            return

        # 2. Start IPC server
        ipc_server = MCSocketServer(self._bridge, self._bus)
        try:
            await ipc_server.start(ws_ctx.socket_path)
        except Exception as exc:
            await self._crash_task(task_id, title, f"MCP IPC server failed: {exc}")
            return

        # 3. Execute via CC provider
        try:
            provider = ClaudeCodeProvider()
            prompt = build_task_message(title, description)

            def on_stream(msg):
                if msg.get("type") == "text":
                    # Post activity event (fire-and-forget)
                    asyncio.create_task(self._post_cc_activity(task_id, agent_name, msg["text"]))

            result = await provider.execute_task(
                prompt=prompt,
                agent_config=agent_data,
                task_id=task_id,
                workspace_ctx=ws_ctx,
                on_stream=on_stream,
            )
        except Exception as exc:
            await self._crash_task(task_id, title, f"Claude Code execution failed: {exc}")
            return
        finally:
            await ipc_server.stop()

        # 4. Process result
        if result.is_error:
            await self._crash_task(task_id, title, f"Claude Code error: {result.output[:1000]}")
        else:
            await self._complete_cc_task(task_id, title, agent_name, result)
    ```

- [ ] **Task 3: Implement stream activity posting** (AC: #3)
  - [ ] 3.1 Create `_post_cc_activity()`:
    ```python
    async def _post_cc_activity(self, task_id: str, agent_name: str, text: str) -> None:
        try:
            self._bridge.mutation("activity:create", {
                "taskId": task_id,
                "eventType": "agent_output",
                "content": text[:500],
                "authorType": "agent",
                "authorName": agent_name,
            })
        except Exception:
            pass  # Non-critical, don't fail the task
    ```

- [ ] **Task 4: Implement task completion** (AC: #7)
  - [ ] 4.1 Create `_complete_cc_task()`:
    ```python
    async def _complete_cc_task(
        self, task_id: str, title: str, agent_name: str, result: CCTaskResult
    ) -> None:
        # Post completion message to thread
        self._bridge.send_message(
            task_id, agent_name, "agent",
            result.output[:2000], "text"
        )
        # Post cost as activity event
        self._bridge.mutation("activity:create", {
            "taskId": task_id,
            "eventType": "completed",
            "content": f"Task completed. Cost: ${result.cost_usd:.4f}",
            "authorType": "agent",
            "authorName": agent_name,
        })
        # Transition task to done
        from mc.state_machine import transition_task
        transition_task(self._bridge, task_id, TaskStatus.DONE)
        logger.info("[executor] CC task %s done (cost=$%.4f)", title, result.cost_usd)
    ```

- [ ] **Task 5: Implement crash handler** (AC: #5)
  - [ ] 5.1 Create `_crash_task()` helper (or reuse existing crash logic):
    ```python
    async def _crash_task(self, task_id: str, title: str, error: str) -> None:
        logger.error("[executor] CC task crashed: %s — %s", title, error)
        self._bridge.send_message(
            task_id, "System", "system", f"Task crashed: {error}", "system_event"
        )
        from mc.state_machine import transition_task
        transition_task(self._bridge, task_id, TaskStatus.CRASHED)
    ```

- [ ] **Task 6: Tests** (AC: all)
  - [ ] 6.1 Create `tests/mc/test_executor_cc.py`:
    - Test backend routing: agent with `backend: claude-code` routes to `_execute_cc_task`
    - Test agent with `backend: nanobot` routes to existing path
    - Test agent with no backend routes to existing path
    - Test workspace preparation failure → crash
    - Test IPC server failure → crash
    - Test CC provider failure → crash
    - Test successful CC execution → done
    - Test cost tracking in activity events
  - [ ] 6.2 Mock: `CCWorkspaceManager`, `ClaudeCodeProvider`, `MCSocketServer`, `ConvexBridge`
  - [ ] 6.3 Run: `uv run pytest tests/mc/test_executor_cc.py -v`
  - [ ] 6.4 Run existing executor tests to verify no regressions: `uv run pytest tests/mc/test_executor.py -v`

## Dev Notes

### Architecture & Design Decisions

**Minimal changes to existing executor**: The CC path is a separate method (`_execute_cc_task`) that branches early in `_execute_task`. The existing nanobot path is untouched. This minimizes risk of regressions.

**Fire-and-forget activity events**: Stream callbacks post activity events without awaiting confirmation. This prevents slow Convex writes from blocking the CC agent. Non-critical — if an activity event fails, the task continues.

**IPC server lifecycle**: The socket server starts before the CC subprocess and stops after it completes. This ensures the MCP bridge can always connect. Stale sockets are cleaned up on start.

### Code to Reuse

- `mc/executor.py` — existing `_execute_task()`, `_load_agent_config()`, task state transitions
- `mc/state_machine.py` — `transition_task()` function
- `mc/bridge.py` — `send_message()`, `mutation()`
- `mc/cc_workspace.py` — `CCWorkspaceManager` (from CC-3)
- `mc/cc_provider.py` — `ClaudeCodeProvider` (from CC-4)
- `mc/mcp_ipc_server.py` — `MCSocketServer` (from CC-2)

### Common Mistakes to Avoid

- Do NOT modify the existing nanobot execution path — only add branching logic
- Do NOT forget to stop the IPC server in the `finally` block
- Do NOT await activity event posts in the stream callback (would slow down agent)
- The `_bridge` is synchronous — use `asyncio.to_thread()` if called from async context
- Use `uv run python` not `python3`. Use `uv run pytest` for tests.

### Project Structure Notes

- **MODIFIED**: `mc/executor.py` — Add backend routing + `_execute_cc_task` method (~80 lines)
- **NEW**: `tests/mc/test_executor_cc.py`

### References

- `mc/executor.py` — `_execute_task()` starting at line ~620
- `mc/state_machine.py` — `transition_task()` function
- `mc/types.py` — TaskStatus enum, AgentData, CCTaskResult
- `mc/cc_workspace.py` — CCWorkspaceManager (CC-3)
- `mc/cc_provider.py` — ClaudeCodeProvider (CC-4)
- `mc/mcp_ipc_server.py` — MCSocketServer (CC-2)

## Review Follow-ups (AI)

- [ ] [AI-Review][HIGH] session_id from CCTaskResult is never stored -- AC7 requires persistence for CC-6 resume. Store via bridge mutation or filesystem. [mc/executor.py:1368-1408]
- [ ] [AI-Review][HIGH] _complete_cc_task parameter typed as `result: "Any"` instead of `"CCTaskResult"`, plus dead import of CCTaskResult at line 1376. Fix type annotation and remove unused import. [mc/executor.py:1373,1376]
- [ ] [AI-Review][MEDIUM] _on_task_completed callback never invoked for CC tasks. Nanobot path calls it on success/crash for cron result delivery. CC path skips it, which may cause cron jobs to hang. [mc/executor.py:857-858]
- [ ] [AI-Review][MEDIUM] Unused `import os` added at module level by this commit. Only usage is a local import inside _get_iana_timezone(). Remove line 16. [mc/executor.py:16]
- [ ] [AI-Review][LOW] MCSocketServer instantiated with bus=None. Add comment explaining why and note CC-6 consideration. [mc/executor.py:1311]
- [ ] [AI-Review][LOW] No test coverage for _on_task_completed callback integration with CC path. [tests/mc/test_executor_cc.py]
- [ ] [AI-Review][LOW] Stream callback test draining via asyncio.sleep(0) is fragile. Consider more robust task draining. [tests/mc/test_executor_cc.py:502-503]

## Dev Agent Record

### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
