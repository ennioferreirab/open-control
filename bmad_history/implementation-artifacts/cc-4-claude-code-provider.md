# Story CC-4: ClaudeCodeProvider

Status: ready-for-dev

## Story

As **Mission Control**,
I want a provider that spawns Claude Code CLI as a headless subprocess and manages its lifecycle,
so that agents configured with `backend: claude-code` execute tasks using Claude Code's agentic loop.

## Acceptance Criteria

### AC1: Spawn Claude Code CLI in Headless Mode

**Given** a task assigned to a `backend: claude-code` agent
**When** `ClaudeCodeProvider.execute_task()` is called
**Then** it spawns a subprocess:
```bash
claude -p "<task prompt>" \
  --output-format stream-json \
  --cwd <agent_workspace> \
  --mcp-config <.mcp.json> \
  --model <resolved_model> \
  --max-turns <max_turns> \
  --max-budget-usd <max_budget_usd> \
  --allowedTools "mcp__nanobot__*" <...other_tools>
```
**And** the subprocess runs asynchronously (non-blocking)
**And** stdout is consumed line-by-line as NDJSON

### AC2: Stream JSON Parsing

**Given** the Claude Code subprocess is running
**When** it emits NDJSON lines to stdout
**Then** the provider parses each line and classifies it:
  - `type: "assistant"` with `content[].type: "text"` → text output (relay to callback)
  - `type: "assistant"` with `content[].type: "tool_use"` → tool call (log)
  - `type: "user"` with `content[].type: "tool_result"` → tool result (log)
  - `type: "result"` → final result (capture output, cost, session_id)
**And** malformed JSON lines are logged and skipped (not crash)
**And** stderr is captured for debugging

### AC3: TaskResult Return

**Given** the Claude Code subprocess completes
**When** the `type: "result"` message is received
**Then** `execute_task()` returns a `TaskResult`:
```python
@dataclass
class CCTaskResult:
    output: str           # result text
    session_id: str       # CC session ID for resume
    cost_usd: float       # total cost from result message
    usage: dict           # {input_tokens, output_tokens, ...}
    is_error: bool        # True if result.is_error
```
**When** the subprocess exits with non-zero code before emitting a result
**Then** `is_error` is `True` and `output` contains stderr

### AC4: Session Resume

**Given** a previous CC session exists (session_id stored)
**When** `execute_task()` is called with `session_id` parameter
**Then** the CLI invocation includes `--resume <session_id>`
**And** the conversation continues from where it left off
**When** the session_id is invalid or expired
**Then** the CLI starts a fresh session (CC handles this gracefully)

### AC5: Process Lifecycle Management

**Given** a CC subprocess is running
**When** the task is cancelled or times out
**Then** the provider sends SIGTERM to the subprocess
**And** waits up to 10 seconds for graceful shutdown
**And** sends SIGKILL if the process doesn't exit
**When** the subprocess crashes unexpectedly
**Then** `is_error` is `True` and stderr is included in output

### AC6: Stream Callback

**Given** `execute_task()` is called with `on_stream` callback
**When** the CC agent produces text output or tool calls
**Then** the callback is invoked with each parsed message
**And** this enables real-time progress reporting to Convex/dashboard
**When** no callback is provided
**Then** messages are silently consumed and only the final result is returned

### AC7: Global Config Integration

**Given** the global config has a `claude_code` section
**When** `ClaudeCodeProvider` is instantiated
**Then** it reads defaults from `config.claude_code`:
  - `cli_path` — path to claude binary
  - `default_model` — model if not specified per-agent
  - `default_max_budget_usd` — budget limit
  - `default_max_turns` — turn limit
**And** per-agent `claude_code` options override these defaults

## Tasks / Subtasks

- [ ] **Task 1: Create CCTaskResult dataclass** (AC: #3)
  - [ ] 1.1 In `mc/types.py`, add:
    ```python
    @dataclass
    class CCTaskResult:
        output: str
        session_id: str
        cost_usd: float
        usage: dict
        is_error: bool
    ```

- [ ] **Task 2: Create ClaudeCodeProvider class** (AC: #1, #7)
  - [ ] 2.1 Create `mc/cc_provider.py` with class `ClaudeCodeProvider`:
    ```python
    class ClaudeCodeProvider:
        def __init__(self, cli_path: str = "claude", defaults: ClaudeCodeConfig | None = None):
            self._cli = cli_path
            self._defaults = defaults or ClaudeCodeConfig()

        async def execute_task(
            self,
            prompt: str,
            agent_config: AgentData,
            task_id: str,
            workspace_ctx: WorkspaceContext,
            session_id: str | None = None,
            on_stream: Callable[[dict], None] | None = None,
        ) -> CCTaskResult:
            ...
    ```
  - [ ] 2.2 Build CLI command list from agent config + defaults:
    ```python
    def _build_command(self, prompt, agent_config, workspace_ctx, session_id) -> list[str]:
        cmd = [self._cli, "-p", prompt, "--output-format", "stream-json"]
        cmd.extend(["--cwd", str(workspace_ctx.cwd)])
        cmd.extend(["--mcp-config", str(workspace_ctx.mcp_config)])

        # Model: per-agent > global default
        model = agent_config.model or self._defaults.default_model
        if model:
            cmd.extend(["--model", model])

        # Budget and turns
        cc = agent_config.claude_code_opts
        budget = (cc and cc.max_budget_usd) or self._defaults.default_max_budget_usd
        turns = (cc and cc.max_turns) or self._defaults.default_max_turns
        if budget:
            cmd.extend(["--max-budget-usd", str(budget)])
        if turns:
            cmd.extend(["--max-turns", str(turns)])

        # Tools
        if cc and cc.allowed_tools:
            for tool in cc.allowed_tools:
                cmd.extend(["--allowedTools", tool])
        cmd.extend(["--allowedTools", "mcp__nanobot__*"])

        if cc and cc.disallowed_tools:
            for tool in cc.disallowed_tools:
                cmd.extend(["--disallowedTools", tool])

        # Session resume
        if session_id:
            cmd.extend(["--resume", session_id])

        return cmd
    ```

- [ ] **Task 3: Implement subprocess execution** (AC: #1, #5)
  - [ ] 3.1 In `execute_task()`, spawn subprocess:
    ```python
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(workspace_ctx.cwd),
    )
    ```
  - [ ] 3.2 Consume stdout line-by-line in async loop
  - [ ] 3.3 Implement cancellation: on `asyncio.CancelledError`, send SIGTERM → wait 10s → SIGKILL

- [ ] **Task 4: Implement NDJSON stream parser** (AC: #2)
  - [ ] 4.1 Create `_parse_stream()` async generator:
    ```python
    async def _parse_stream(self, proc) -> AsyncIterator[dict]:
        async for line in proc.stdout:
            line = line.decode().strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Malformed JSON from claude CLI: %s", line[:200])
    ```
  - [ ] 4.2 In `execute_task()`, iterate stream and classify messages:
    ```python
    result = CCTaskResult(output="", session_id="", cost_usd=0, usage={}, is_error=False)
    async for msg in self._parse_stream(proc):
        msg_type = msg.get("type")
        if msg_type == "result":
            result.output = msg.get("result", "")
            result.session_id = msg.get("session_id", "")
            result.cost_usd = msg.get("total_cost_usd", 0)
            result.usage = msg.get("usage", {})
            result.is_error = msg.get("is_error", False)
        elif msg_type == "assistant":
            # Extract text content for streaming
            for block in msg.get("message", {}).get("content", []):
                if block.get("type") == "text" and on_stream:
                    on_stream({"type": "text", "text": block["text"]})
                elif block.get("type") == "tool_use" and on_stream:
                    on_stream({"type": "tool_use", "name": block.get("name")})
        # Capture session_id from any message
        if "session_id" in msg and not result.session_id:
            result.session_id = msg["session_id"]
    ```

- [ ] **Task 5: Handle subprocess exit** (AC: #3, #5)
  - [ ] 5.1 After stream exhausts, await process completion:
    ```python
    returncode = await proc.wait()
    stderr_output = await proc.stderr.read()
    if returncode != 0 and not result.output:
        result.is_error = True
        result.output = stderr_output.decode()[:2000]
    ```

- [ ] **Task 6: Tests** (AC: all)
  - [ ] 6.1 Create `tests/mc/test_cc_provider.py`:
    - Test `_build_command()` with various config combinations
    - Test stream parser with mock NDJSON lines (valid + malformed)
    - Test result extraction from stream
    - Test session resume flag in command
    - Test process cancellation (mock subprocess)
    - Test on_stream callback invocation
  - [ ] 6.2 Run: `uv run pytest tests/mc/test_cc_provider.py -v`

## Dev Notes

### Architecture & Design Decisions

**Full agentic loop delegation**: The CC CLI manages its own tool calls, context window, and compaction. MC only sees the stream of messages and the final result. This is intentional — CC's built-in agentic capabilities (Read, Edit, Bash, Glob, Grep) are superior to nanobot's basic tools.

**Stream-first design**: Even though we only need the final result, streaming enables real-time progress reporting. The `on_stream` callback allows the executor to post activity events as the agent works.

**No stdin interaction**: We use one-shot `claude -p` mode, not the stdin streaming mode (`--input-format stream-json`). For multi-turn, we use `--resume` instead. This avoids the duplicate entries bug in stdin mode.

### Code to Reuse

- `mc/provider_factory.py` — `create_provider()` pattern for creating providers
- `mc/types.py` — `AgentData`, `ClaudeCodeOpts`, `WorkspaceContext` (from CC-1, CC-3)
- `vendor/nanobot/nanobot/config/schema.py` — `ClaudeCodeConfig` (from CC-1)

### Common Mistakes to Avoid

- Do NOT use `--input-format stream-json` for multi-turn — use `--resume` instead
- Do NOT forget to close the subprocess on cancellation — leaked processes waste API credits
- Do NOT parse partial JSON lines — wait for complete newline-terminated lines
- The `--allowedTools` flag takes one tool per flag (repeat the flag for each tool)
- `--max-budget-usd` requires a float string, not int
- Use `uv run python` not `python3`. Use `uv run pytest` for tests.

### Project Structure Notes

- **NEW**: `mc/cc_provider.py` — ClaudeCodeProvider class
- **MODIFIED**: `mc/types.py` — Add CCTaskResult dataclass
- **NEW**: `tests/mc/test_cc_provider.py`

### References

- `mc/provider_factory.py` — existing provider creation pattern
- `mc/executor.py` — `_make_provider()`, `_execute_task()` integration point
- Claude Code CLI reference: https://code.claude.com/docs/en/cli-reference
- Claude Code headless mode: https://code.claude.com/docs/en/headless
- Stream JSON format: NDJSON with type field (assistant, user, result)

## Review Follow-ups (AI)

- [ ] [AI-Review][CRITICAL] Files located under `nanobot/mc/` and `nanobot/config/` instead of `mc/` and `vendor/nanobot/nanobot/config/`. All imports use `nanobot.mc.` prefix instead of `mc.`. Must relocate and rewrite all imports before merge. [nanobot/mc/cc_provider.py:17, tests/mc/test_cc_provider.py:21-22]
- [ ] [AI-Review][CRITICAL] Duplicate types re-implemented from CC-1: `ClaudeCodeOpts`, `AgentData.backend`, `AgentData.claude_code_opts`, `ClaudeCodeConfig`, `Config.claude_code` already exist on main. Only `CCTaskResult` (and `WorkspaceContext` from CC-3) are new. Will cause merge conflicts. [nanobot/mc/types.py:288-295, nanobot/config/schema.py:291-302]
- [ ] [AI-Review][HIGH] Cost field name `cost_usd` does not match story spec (`total_cost_usd`). Actual Claude Code CLI field name needs empirical verification. [nanobot/mc/cc_provider.py:199]
- [ ] [AI-Review][HIGH] `on_stream` callback receives raw content blocks from CLI instead of normalized events as specified in story spec AC2/AC6 (should be `{"type": "text", "text": ...}` and `{"type": "tool_use", "name": ...}`). [nanobot/mc/cc_provider.py:210-211]
- [ ] [AI-Review][HIGH] `session_id` overwrite logic differs from spec -- implementation overwrites on every message vs spec captures only first occurrence. Current behavior is acceptable but undocumented deviation. [nanobot/mc/cc_provider.py:192-193]
- [ ] [AI-Review][MEDIUM] `defaults` parameter typed as `Any` instead of `ClaudeCodeConfig | None` with `TYPE_CHECKING` import. [nanobot/mc/cc_provider.py:32]
- [ ] [AI-Review][MEDIUM] `assert` statements used for runtime invariants (`proc.stdout/stderr is not None`) -- will silently pass under `python -O`. [nanobot/mc/cc_provider.py:92,172]
- [ ] [AI-Review][MEDIUM] Cancellation test uses confusing dead-code `yield` after `return` and relies on `asyncio.sleep(0)` timing. [tests/mc/test_cc_provider.py:532-535]
- [ ] [AI-Review][LOW] Test hardcodes logger name `nanobot.mc.cc_provider` which will be wrong after file relocation. [tests/mc/test_cc_provider.py:286]
- [ ] [AI-Review][LOW] `isinstance(content, str)` branch in `_handle_message` is defensive but untested. [nanobot/mc/cc_provider.py:212-213]

## Dev Agent Record

### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
