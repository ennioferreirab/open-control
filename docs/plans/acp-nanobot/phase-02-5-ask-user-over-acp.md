# Phase 2.5 — ask-user over ACP (deliver the mc MCP server)

Back to [overview.md](overview.md).

> Added after Phase 2. Grounding found the harness `claude-agent-acp` disables its built-in `AskUserQuestion` tool and that ACP `elicitation/create` is unstable and unwired in the Python SDK. So ask-user does NOT come through an ACP client method. Instead it comes through the mc MCP server: the agent calls `mcp__mc__ask_user`, which routes to the existing backend-agnostic blocking flow (`InteractionService` → Convex `executionQuestions` → human answers → answer returned → agent continues). A spike proved `claude-agent-acp` accepts an MCP server via `new_session(mcp_servers=[...])` and the agent calls its tools end-to-end.

## Goal

Let an ACP-backed agent ask the human a question mid-task, reusing the entire existing ask-user machinery, by delivering the mc MCP server to the ACP session.

## Changes

- `AcpClient` ([mc/infrastructure/acp/client.py](../../../mc/infrastructure/acp/client.py)): accept `mcp_servers: list[McpServerStdio] | None` and `allowed_tools: list[str] | None` in `__init__`; in `__aenter__` pass them to `new_session(cwd=..., mcp_servers=..., claudeCode={"options": {"strictMcpConfig": True, "allowedTools": allowed_tools}})`. The `claudeCode` option goes as a BARE kwarg (spike-verified: `_meta=` double-nests and is silently ignored). Keep current behavior (no MCP) when none passed.
- `AcpRunnerStrategy` ([mc/application/execution/strategies/acp.py](../../../mc/application/execution/strategies/acp.py)): build the mc `McpServerStdio` mirroring provider-cli's `_generate_mcp_json` + `_build_runtime_env`:
  - `name="mc"`, `command="uv"`, `args=["run", "--project", <repo_root>, "python", "-m", "mc.runtime.mcp.bridge"]`.
  - `env` = `CONVEX_URL`, `CONVEX_ADMIN_KEY` (from `os.environ`), `MC_INTERACTIVE_SESSION_ID=mc_session_id`, `AGENT_NAME`, `TASK_ID`, `STEP_ID` (if any), plus `resolve_secret_env()` ([secrets.py](../../../mc/infrastructure/secrets.py)).
  - `allowed_tools=["mcp__mc__ask_user", "mcp__mc__send_message"]`.
  - Pass both to `AcpClient`.

## Scope

`ask_user` and `send_message` only. They work through the direct-Convex path (`CONVEX_URL` + `CONVEX_ADMIN_KEY` + `MC_INTERACTIVE_SESSION_ID`) with no Unix socket. The other ~14 mc tools require a live `MC_SOCKET_PATH` (the gateway IPC socket); full mc-tool parity over ACP is a deferred follow-up, not Phase 2.5.

## Data structures

- `acp.schema.McpServerStdio` — `{name: str, command: str, args: list[str], env: list[EnvVariable]}` (`EnvVariable` = `{name, value}`). No `type` discriminator.
- `AcpClient` gains `mcp_servers` and `allowed_tools` constructor params.

## Verification

**Static.** `make check`. Unit tests: `AcpClient` forwards `mcp_servers` + the `claudeCode`/`allowedTools` option to `new_session` (mock the SDK); `AcpRunnerStrategy` builds the mc `McpServerStdio` with the Convex creds and `ask_user`/`send_message` in `allowed_tools`.

**Runtime.** The agent-calls-`mcp__mc__ask_user`-over-ACP delivery is provable against the real adapter. The full round-trip (pause → human answers in the dashboard → agent resumes) needs the live stack (`make start`, Convex). Flag the stack-dependent part; verify the pause (an `executionQuestions` record is created) and, on the stack, the resume.
