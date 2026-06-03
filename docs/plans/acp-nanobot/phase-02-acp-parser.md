# Phase 2 — AcpParser and RunnerType.ACP

Back to [overview.md](overview.md).

## Goal

Make ACP a first-class execution backend by implementing a parser that satisfies the existing provider-cli seam and registering a new runner type. No backend is selected yet; this phase only makes the path exist.

## Changes

- New `mc/contexts/provider_cli/providers/acp.py` defining `AcpParser` with class attribute `provider_name = "acp"`, structurally satisfying the `ProviderCLIParser` protocol ([mc/contexts/provider_cli/parser.py:15](../../../mc/contexts/provider_cli/parser.py)). It builds on the `AcpClient` from Phase 1. `start_session` launches with `stdin_mode="pipe"` (the supervisor already supports it, [process_supervisor.py:27](../../../mc/runtime/provider_cli/process_supervisor.py)), performs `initialize` + `session/new`, then sends the prompt via `session/prompt`. It sets `ANTHROPIC_MODEL` in the harness subprocess env to the tier-resolved model from the registry (spike-verified mechanism), never relying on the adapter's Opus default. `parse_output` maps ACP `session/update` notifications to the existing `ParsedCliEvent` types. `resume` sends a follow-up `session/prompt`. `interrupt` sends `session/cancel`. `stop` terminates the process.
- Add `ACP = "acp"` to `RunnerType` ([mc/application/execution/request.py:37](../../../mc/application/execution/request.py)).
- Register the strategy in the engine's default strategy table ([mc/application/execution/engine.py:99](../../../mc/application/execution/engine.py)). The existing `ProviderCliRunnerStrategy` is parser-agnostic, so reuse it with the ACP parser injected; no new strategy class unless event mapping forces one.
- Run the **architect** skill here first: the `session/update` → `ParsedCliEvent` mapping has real design latitude (turn boundaries, tool-use blocks, errors), so explore the mapping in parallel before committing.

## Data structures

- `AcpParser(provider_name="acp")` — satisfies `ProviderCLIParser`; no base class (convention is structural).
- Event mapping table — ACP update kinds to `ParsedCliEvent` variants; the artifact the architect step produces.

## Verification

**Static.** `make check`. New unit tests in `tests/mc/provider_cli/test_acp_parser.py` following `test_claude_code_parser.py`: feed synthetic `session/update` payloads, assert the emitted `ParsedCliEvent` list. Mock the client with `AsyncMock`. A test asserts `isinstance(AcpParser(), ProviderCLIParser)` (runtime-checkable protocol).

**Runtime.** Engine constructs with the ACP strategy present and no import error; `uv run pytest tests/mc/application/execution/test_engine.py`.
