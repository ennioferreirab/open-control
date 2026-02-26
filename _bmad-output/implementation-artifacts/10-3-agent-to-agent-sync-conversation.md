# Story 10.3: Agent-to-Agent Synchronous Conversation

Status: ready-for-dev

## Story

As an **agent**,
I want a tool to ask another agent a question synchronously and wait for the response,
so that I can get clarification or brainstorm during task execution without delegating an entire task.

## Acceptance Criteria

### AC1: ask_agent Tool Definition

**Given** an agent is executing a task via AgentLoop
**When** the tool definitions are loaded
**Then** an `ask_agent` tool is available with parameters: `target_agent` (string, required), `question` (string, required)
**And** the tool description clearly states: "Ask another agent a question and wait for their response. Use for clarification or brainstorming. The target agent will answer based on their specialization and context."
**And** the tool returns the target agent's response as a string

### AC2: Synchronous Execution

**Given** an agent calls `ask_agent(target_agent="secretary", question="What format should the report use?")`
**When** the tool executes
**Then** it loads the target agent's config (prompt, model, skills) from `~/.nanobot/agents/{target_agent}/config.yaml`
**And** it creates an AgentLoop for the target agent with an isolated session key: `mc:ask:{caller}:{target}:{uuid}`
**And** it calls `process_direct()` with a focused prompt: "You are being asked by {caller_agent} for clarification during task execution. Answer concisely and specifically.\n\nQuestion: {question}"
**And** the calling agent's execution is blocked (awaited) until the target agent responds
**And** the target agent's response text is returned to the calling agent as the tool result

### AC3: Depth Limit

**Given** Agent A calls `ask_agent` targeting Agent B
**When** Agent B's execution encounters a situation where it would also call `ask_agent` targeting Agent C
**Then** Agent B's `ask_agent` call is rejected with error: "Inter-agent conversation depth limit reached (max 2). Cannot nest ask_agent calls beyond A -> B."
**And** the depth is tracked via a context variable (e.g., `_ask_agent_depth`) passed through the MC context
**And** depth 0 = no ask_agent in progress, depth 1 = A asked B (allowed), depth 2 = B asked C (blocked)

### AC4: Timeout Protection

**Given** an agent calls `ask_agent`
**When** the target agent takes longer than 120 seconds to respond
**Then** the call is terminated via `asyncio.wait_for(timeout=120)`
**And** the tool returns an error message: "ask_agent timed out after 120 seconds. Target agent '{target_agent}' did not respond in time."
**And** the calling agent can handle this gracefully (continue with alternative approach)

### AC5: Lead Agent Protection

**Given** an agent calls `ask_agent(target_agent="lead-agent", ...)`
**When** the tool validates the target
**Then** the call is rejected immediately with error: "Cannot ask the Lead Agent. The Lead Agent is a pure orchestrator and cannot be targeted by ask_agent."
**And** this check happens before any agent loading or execution

### AC6: Thread Logging

**Given** an agent calls `ask_agent` during task execution
**When** the inter-agent conversation completes (success or failure)
**Then** a system_event message is posted to the task thread with content:
  ```
  Inter-agent conversation: {caller_agent} asked {target_agent}
  Question: {question}
  Response: {response_or_error}
  ```
**And** this message is visible in the task's thread view in the dashboard
**And** the message uses `authorType="system"`, `messageType="system_event"`

### AC7: Target Agent Not Found

**Given** an agent calls `ask_agent(target_agent="nonexistent", ...)`
**When** the tool validates the target
**Then** it returns an error: "Agent 'nonexistent' not found. Available agents: {comma-separated list of agent names}."
**And** this check happens before attempting to create an AgentLoop

## Tasks / Subtasks

- [ ] Task 1: Create the ask_agent tool (AC: 1, 2, 4, 5, 7)
  - [ ] 1.1: Create `nanobot/agent/tools/ask_agent.py`. Define class `AskAgentTool(Tool)` following the pattern from `mc_delegate.py` and `cron.py`. Properties:
    - `name` -> `"ask_agent"`
    - `description` -> `"Ask another agent a question synchronously and wait for their response. Use for clarification, brainstorming, or getting a specialist opinion during task execution. The target agent responds based on their specialization. Do NOT use this for delegating full tasks — use delegate_task instead."`
    - `parameters` -> `{ "type": "object", "properties": { "target_agent": { "type": "string", "description": "Name of the agent to ask (e.g., 'secretary', 'researcher')" }, "question": { "type": "string", "description": "The question to ask the target agent" } }, "required": ["target_agent", "question"] }`
  - [ ] 1.2: Add instance variables in `__init__`:
    - `self._caller_agent: str | None = None` — set via `set_context()`
    - `self._task_id: str | None = None` — set via `set_context()`
    - `self._depth: int = 0` — current ask_agent nesting depth
    - `self._bridge: ConvexBridge | None = None` — for thread logging
  - [ ] 1.3: Add `set_context(self, caller_agent: str, task_id: str | None, depth: int, bridge: ConvexBridge | None)` method to receive MC execution context.
  - [ ] 1.4: Implement `async def execute(self, target_agent: str, question: str, **kwargs) -> str`:
    - Validate `self._caller_agent` is set (return error if tool used outside MC context).
    - Validate target_agent != "lead-agent" and != LEAD_AGENT_NAME (AC5).
    - Validate depth < 2 (AC3). If depth >= 2, return depth limit error.
    - Load target agent config: import `validate_agent_file` from `nanobot.mc.yaml_validator`, read `AGENTS_DIR / target_agent / config.yaml`. If file not found or validation fails, list available agents and return error (AC7).
    - Create provider: import `create_provider` from `nanobot.mc.provider_factory`.
    - Build focused prompt: `f"You are being asked by {self._caller_agent} for clarification during task execution. Answer concisely and specifically.\n\nQuestion: {question}"`. If the target agent has a YAML prompt, prepend it: `f"[System instructions]\n{agent_prompt}\n\n[Inter-agent query]\n{focused_prompt}"`.
    - Create isolated session key: `f"mc:ask:{self._caller_agent}:{target_agent}:{uuid.uuid4().hex[:8]}"`.
    - Create AgentLoop (lazy import inside execute to avoid import cycle):
      ```python
      from nanobot.agent.loop import AgentLoop
      from nanobot.bus.queue import MessageBus
      workspace = AGENTS_DIR / target_agent
      bus = MessageBus()
      loop = AgentLoop(bus=bus, provider=provider, workspace=workspace, model=resolved_model, allowed_skills=agent_skills)
      ```
    - Wrap in timeout: `response = await asyncio.wait_for(loop.process_direct(content=focused_prompt, session_key=session_key, channel="mc", chat_id=target_agent), timeout=120)` (AC4).
    - Log to task thread if `self._bridge` and `self._task_id` are available (AC6).
    - Return the response string.
  - [ ] 1.5: Implement thread logging helper `_log_to_thread(self, question: str, target_agent: str, response: str) -> None`:
    ```python
    if self._bridge and self._task_id:
        content = (
            f"Inter-agent conversation: {self._caller_agent} asked {target_agent}\n"
            f"Question: {question}\n"
            f"Response: {response[:500]}"
        )
        try:
            await asyncio.to_thread(
                self._bridge.send_message,
                self._task_id, "System", "system", content, "system_event",
            )
        except Exception:
            logger.warning("Failed to log inter-agent conversation to thread")
    ```
  - [ ] 1.6: Handle errors gracefully in `execute()`:
    - `asyncio.TimeoutError` -> return timeout error message (AC4)
    - Agent config not found -> return "Agent not found" with available agents list (AC7)
    - Provider error -> return `f"Failed to create provider for {target_agent}: {error}"`
    - Any other exception -> return `f"ask_agent failed: {error}"`, log with `logger.exception`
    - Always attempt to log the conversation to the thread (even failures).

- [ ] Task 2: Register ask_agent tool in AgentLoop (AC: 1)
  - [ ] 2.1: In `nanobot/agent/loop.py`, import the tool in `_register_default_tools()` (lazy, inside try/except, matching the `mc_delegate` pattern at lines 126-131):
    ```python
    try:
        from nanobot.agent.tools.ask_agent import AskAgentTool
        self.tools.register(AskAgentTool())
    except Exception:
        pass  # MC context not available — tool not registered
    ```
  - [ ] 2.2: Add the import AFTER the existing `McDelegateTool` registration block (line 131) to keep the registration order logical (delegate, then ask).

- [ ] Task 3: Pass MC context to ask_agent tool from executor (AC: 2, 3, 6)
  - [ ] 3.1: In `nanobot/mc/executor.py`, inside `_run_agent_on_task()` (lines 91-165), after the AgentLoop is created (line 145-154), check if the `ask_agent` tool is registered and set its context:
    ```python
    if ask_tool := loop.tools.get("ask_agent"):
        from nanobot.agent.tools.ask_agent import AskAgentTool
        if isinstance(ask_tool, AskAgentTool):
            # Bridge is not directly available here; pass None for thread logging
            # The executor passes bridge through a different mechanism
            ask_tool.set_context(
                caller_agent=agent_name,
                task_id=task_id,
                depth=0,
                bridge=None,  # Will be set in Task 3.2
            )
    ```
  - [ ] 3.2: To make the bridge available to the ask_agent tool, pass it via the executor context. The cleanest approach: add an optional `bridge` parameter to `_run_agent_on_task()`:
    - Add `bridge: ConvexBridge | None = None` parameter to `_run_agent_on_task()` signature.
    - In `_execute_task()`, pass `self._bridge` when calling `_run_agent_on_task()`.
    - In `_run_agent_on_task()`, after creating the AgentLoop, set the bridge on the ask_agent tool:
      ```python
      if ask_tool := loop.tools.get("ask_agent"):
          from nanobot.agent.tools.ask_agent import AskAgentTool
          if isinstance(ask_tool, AskAgentTool):
              ask_tool.set_context(
                  caller_agent=agent_name,
                  task_id=task_id,
                  depth=0,
                  bridge=bridge,
              )
      ```
  - [ ] 3.3: For depth tracking: when the ask_agent tool creates a child AgentLoop (inside its `execute()` method), it must set the child's ask_agent tool depth to `self._depth + 1`. After creating the child loop:
    ```python
    if child_ask_tool := child_loop.tools.get("ask_agent"):
        from nanobot.agent.tools.ask_agent import AskAgentTool
        if isinstance(child_ask_tool, AskAgentTool):
            child_ask_tool.set_context(
                caller_agent=target_agent,
                task_id=self._task_id,
                depth=self._depth + 1,
                bridge=self._bridge,
            )
    ```

- [ ] Task 4: Tests (AC: all)
  - [ ] 4.1: Create `tests/mc/test_ask_agent.py` with unit tests:
    - Test successful ask: mock `validate_agent_file` to return valid AgentData, mock `create_provider`, mock `AgentLoop.process_direct` to return a response. Assert tool returns the response.
    - Test lead agent protection: call with `target_agent="lead-agent"`, assert error returned without any agent loading.
    - Test depth limit: set `_depth = 2`, call execute, assert depth limit error returned.
    - Test timeout: mock `process_direct` to sleep > 120s (use `asyncio.sleep`), assert timeout error.
    - Test agent not found: mock `validate_agent_file` to fail, assert error with available agents list.
    - Test thread logging: mock bridge.send_message, verify it is called with correct system_event content.
  - [ ] 4.2: Run all tests: `uv run pytest tests/mc/test_ask_agent.py -v`
  - [ ] 4.3: Verify existing tests still pass: `uv run pytest tests/mc/ -v` (ensure no regressions from executor.py changes).

## Dev Notes

### Architecture & Design Decisions

**Synchronous (Blocking) Design**: The `ask_agent` tool blocks the calling agent's execution until the target agent responds. This is intentional -- the calling agent needs the response to continue its work. The `await asyncio.wait_for()` provides timeout protection. This is fundamentally different from `delegate_task` (which is fire-and-forget, creating a Convex task that the orchestrator picks up asynchronously).

**Depth Limit Rationale**: The depth limit of 2 (A->B allowed, B->C blocked) prevents infinite recursion and excessive resource usage. Without a limit, Agent A could ask Agent B, which asks Agent C, which asks Agent D, etc., creating an unbounded chain of concurrent LLM calls. The limit of 2 means at most 2 concurrent agent sessions per ask_agent chain. The depth is tracked per-tool-instance via `self._depth`, set during `set_context()`.

**Isolated Session Keys**: Each ask_agent call uses a unique session key `mc:ask:{caller}:{target}:{uuid}`. This ensures:
1. No session state leaks between different ask_agent calls
2. No interference with the target agent's task sessions (`mc:task:{agent}`) or chat sessions (`mc-chat:{agent}`)
3. Sessions are ephemeral -- they accumulate during the conversation but are not explicitly cleared (they naturally expire when the AgentLoop is garbage collected)

**Lead Agent Protection**: The Lead Agent is a pure orchestrator (no execution capability). Allowing agents to `ask_agent` the Lead Agent would violate this invariant and potentially cause confusion (the Lead Agent's prompt is designed for routing, not answering questions). This mirrors the existing `is_lead_agent()` guard in `executor.py` (line 109-113).

**Thread Logging**: Inter-agent conversations are logged to the task thread as `system_event` messages. This provides visibility into what happened during task execution. The log is truncated to 500 characters for the response to prevent excessively long thread messages. The full response is returned to the calling agent regardless.

**No Memory Consolidation for ask_agent Sessions**: Unlike task sessions (which call `end_task_session` to consolidate memory), ask_agent sessions are ephemeral. The target agent's response is a one-shot answer, not a multi-turn conversation. Memory consolidation would add unnecessary overhead and pollute the target agent's MEMORY.md with fragments of other agents' questions.

### Existing Code to Reuse

**mc_delegate.py** (lines 1-91):
- Pattern for a tool that interacts with MC/Convex
- `_init_bridge()` pattern for lazy bridge initialization
- `Tool` base class with `name`, `description`, `parameters`, `execute` properties

**executor.py _run_agent_on_task()** (lines 91-165):
- Agent config loading pattern (lines 108-120)
- Provider creation via `_make_provider()` (line 142)
- AgentLoop instantiation with workspace, model, skills (lines 144-154)
- `process_direct()` call pattern (lines 156-162)
- Note: ask_agent does NOT call `end_task_session()` -- sessions are ephemeral

**executor.py _load_agent_config()** (lines 470-496):
- YAML validation via `validate_agent_file(config_file)`
- Returns `(prompt, model, skills)` tuple
- Handles missing config gracefully

**cron.py CronTool** (lines 1-151):
- Pattern for a tool with `set_context()` method
- Instance variables for context: `self._channel`, `self._chat_id`, `self._task_id`

**types.py**:
- `LEAD_AGENT_NAME` constant for lead agent check
- `is_lead_agent()` function for robust lead agent detection
- `AuthorType.SYSTEM`, `MessageType.SYSTEM_EVENT` for thread logging

### Common Mistakes to Avoid

1. **Do NOT import `nanobot.agent` at module level** -- the `ask_agent.py` tool file lives inside `nanobot/agent/tools/` but must lazily import `AgentLoop`, `MessageBus`, etc. inside `execute()`. This prevents circular imports and keeps gateway startup fast. Follow the `mc_delegate.py` pattern.
2. **Do NOT use `_run_agent_on_task()` from executor.py** -- that function includes task-specific logic (orientation injection, thread context, output file scanning, session clearing) that is not appropriate for a quick synchronous question. Use `AgentLoop.process_direct()` directly.
3. **Do NOT forget to set the child loop's ask_agent depth** -- if the child AgentLoop has an ask_agent tool registered and `_depth` is not incremented, Agent B could call ask_agent on Agent C with depth 0, bypassing the limit.
4. **Do NOT call `end_task_session()` on the child session** -- ask_agent sessions are ephemeral. Consolidating memory would pollute the target agent's MEMORY.md with fragments of other agents' questions.
5. **Do NOT use synchronous bridge calls in the tool** -- all bridge calls must use `await asyncio.to_thread()` since the Convex Python SDK is synchronous and the tool runs in an asyncio context.
6. **Do NOT pass the full task description to the target agent** -- the target agent should only see the focused question. Including the full task context could confuse the target agent or leak sensitive information between agent domains.

### Project Structure Notes

- **NEW**: `nanobot/agent/tools/ask_agent.py` — The ask_agent tool implementation
- **NEW**: `tests/mc/test_ask_agent.py` — Unit tests for the tool
- **MODIFIED**: `nanobot/agent/loop.py` — Register ask_agent tool in `_register_default_tools()` (2 lines)
- **MODIFIED**: `nanobot/mc/executor.py` — Pass bridge and set context on ask_agent tool in `_run_agent_on_task()` (~10 lines)
- **No frontend changes**
- **No schema changes**
- **No new dependencies**

### References

- [Source: nanobot/agent/tools/base.py — Tool base class, lines 1-103]
- [Source: nanobot/agent/tools/mc_delegate.py — MC tool pattern, lines 1-91]
- [Source: nanobot/agent/tools/cron.py — Tool with set_context() pattern, lines 1-151]
- [Source: nanobot/agent/tools/registry.py — ToolRegistry.register/get, lines 1-73]
- [Source: nanobot/agent/loop.py — _register_default_tools lines 109-131, process_direct lines 482-496]
- [Source: nanobot/mc/executor.py — _run_agent_on_task lines 91-165, _load_agent_config lines 470-496, _execute_task lines 620-891]
- [Source: nanobot/mc/bridge.py — send_message lines 279-314]
- [Source: nanobot/mc/types.py — LEAD_AGENT_NAME, is_lead_agent, AuthorType, MessageType constants]
- [Source: nanobot/mc/gateway.py — AGENTS_DIR constant line 32]

## Dev Agent Record

### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
