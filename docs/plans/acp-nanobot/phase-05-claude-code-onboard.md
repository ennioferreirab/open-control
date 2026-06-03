# Phase 5 — Onboard Claude Code through ACP (behind a flag)

Back to [overview.md](overview.md).

## Goal

Run a real task end-to-end through the ACP path for Claude Code, behind a flag, with the NDJSON `claude -p` path still the default. This is the proof gate for Track A (the **prove-it-works** principle): the seam is not done until a real task completes through it.

## Changes

- Wire the registry, parser, runner type, and selection so that an agent flagged onto the ACP backend executes a task by launching `claude-agent-acp` and driving it over ACP.
- Gate it behind an explicit opt-in (an env flag or an `agent.backend = "claude-code-acp"` value) so production keeps using the existing path until Phase 6.
- Ensure the existing surrounding machinery is reused unchanged: process supervisor, session registry, control plane, live-stream projection, activity logging to Convex. The investigation confirmed these are parser-agnostic; this phase proves it.
- Map the lifecycle: session create (`session/new`), prompt turn (`session/prompt`), streaming updates projected to the live stream, completion captured into `ExecutionResult`. Cancellation via `session/cancel` on interrupt.

## Data structures

- No new types. Reuses `ExecutionRequest` / `ExecutionResult` ([request.py](../../../mc/application/execution/request.py)) and `ProviderProcessHandle`.

## Verification

**Static.** `make check`; `uv run pytest`.

**Runtime (the gate).** `make start`. Create a task assigned to a Claude-Code-ACP-flagged agent. Drive it on the real stack and confirm: the harness subprocess launches, the task runs to completion, streamed updates appear in the dashboard live view, the final result and session id persist to Convex, and interrupt/stop work. No bundled control-cli/control-ui skill exists for this surface; drive mc via the CLI directly and the dashboard via Playwright or Chrome DevTools MCP (or the `/run` skill). Capture evidence in the PR. Compare output parity against the same task on the old NDJSON path.
