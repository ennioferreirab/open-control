# Phase 2 — AcpRunnerStrategy and RunnerType.ACP

Back to [overview.md](overview.md).

> Design corrected after the **architect** skill (three independent model sketches, strong consensus). ACP is NOT wrapped as an `AcpParser` satisfying `ProviderCLIParser`. That protocol's load-bearing method is `parse_output(chunk: bytes)`, a byte-deserialization seam that exists to recover structure a subprocess loses on stdout. ACP never loses it (the SDK delivers typed objects via push). Forcing ACP through `parse_output(bytes)` would serialize structured updates back to bytes then re-parse them, and the `ProviderCliRunnerStrategy._run` loop is hardwired to `supervisor.stream_output()`. So Phase 2 adds a new strategy, not a parser.

## Goal

Make ACP a first-class execution backend with a new `AcpRunnerStrategy` that consumes the SDK-owned `AcpClient`'s structured update stream and maps it to the shared `ParsedCliEvent` vocabulary, reusing the existing registry, live-stream, and activity infrastructure. No backend is selected yet (Phase 4); this phase makes the path exist and runnable.

## Changes

- Add `ACP = "acp"` to `RunnerType` ([request.py](../../../mc/application/execution/request.py)).
- Expose a public `session_id` property on `AcpClient` ([mc/infrastructure/acp/client.py](../../../mc/infrastructure/acp/client.py)); the strategy needs it for the registry record. Small Phase 1-module addition.
- New `mc/application/execution/strategies/acp.py`:
  - `AcpRunnerStrategy` satisfying `RunnerStrategy.execute(request) -> ExecutionResult`. It opens `AcpClient(command, cwd, model=request.model)`, creates a registry record (`provider="acp"`, `pid=0` sentinel, `supports_resume=False`), runs `client.prompt(request.prompt, on_update=...)`, and builds `ExecutionResult` from the returned `AcpTurnResult`.
  - A pure module-level `_acp_update_to_event(update) -> ParsedCliEvent | None`. The `on_update` handler is synchronous and inline (updates arrive before `prompt()` returns, so no queue is needed); it maps each update, then feeds the SAME `LiveStreamProjector`, `SessionActivityService`, and supervision sink the provider-cli strategy uses.
- Register `RunnerType.ACP` in the engine default table ([engine.py](../../../mc/application/execution/engine.py)) and in [post_processing.py](../../../mc/application/execution/post_processing.py) `build_execution_engine`, sharing the same registry/projector/control-plane instances. Command hardcoded to `["npx", "-y", "@agentclientprotocol/claude-agent-acp"]` (Phase 3 replaces with the harness registry). Model flows `request.model` → `AcpClient` → `ANTHROPIC_MODEL` at spawn.
- **Reuse verbatim**: `ProviderSessionRegistry`, `LiveStreamProjector`, `SessionActivityService`. **Bypass entirely** (still serve provider-cli/Codex): `ProviderProcessSupervisor`, `ProviderCLIParser`, `ProviderCliRunnerStrategy`, `_build_command`.

## Deferred to follow-up (flagged, not in Phase 2)

- Ask-user pause parity (provider-cli pauses on `ask_user_requested`). Phase 2 runs autonomous/bypass to completion; the event is mapped for visibility but the pause/resume is not wired.
- Graceful `session/cancel` intervention. Phase 2 stop cancels the `prompt()` task and tears down via `AcpClient.__aexit__`.
- MCP-config and workspace delivery to the ACP harness (the Claude CLI gets `--mcp-config`; the harness needs it via `session/new` or env — depends on the SDK surface, confirm at implementation).

## Data structures

- `RunnerType.ACP`.
- `AcpRunnerStrategy` — stateless; collaborators injected via `__init__`; `async def execute(request) -> ExecutionResult`.
- `_acp_update_to_event(update) -> ParsedCliEvent | None` — pure. `AgentMessageChunk` → `kind="text"`; `ToolCallStart`/`ToolCallProgress` → `kind="tool_use"`/`"tool_result"`; `UsageUpdate` → `kind="system_event"` (cost/tokens in metadata); others → `None`.

## Verification

**Static.** `make check`. Unit tests `tests/mc/application/execution/test_acp_strategy.py`: feed synthetic ACP update objects to `_acp_update_to_event` and assert the `ParsedCliEvent`; drive `AcpRunnerStrategy.execute` with a mocked `AcpClient` and assert a populated `ExecutionResult` plus registry/projector/activity calls. No real subprocess in unit tests.

**Runtime (bring Phase 5's proof early).** A real task runs end-to-end through `RunnerType.ACP` on haiku and returns `success=True` with output. Drive it on the worktree against the real adapter; capture in the PR.
