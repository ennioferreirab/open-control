# Story 28.28: Remove Duplicate `-p` From Provider CLI Command Builder

Status: review

## Story

As a Mission Control maintainer,
I want the provider-cli strategy to emit a single valid Claude CLI prompt argument,
so that the backend runtime uses the exact command contract that works in real execution.

## Problem Found

The runtime now injects `-p <prompt>` in the builder, but the default base command still ends with a second `-p`. The final command shape becomes:

`claude -p "<prompt>" --verbose --output-format stream-json -p ...`

This leaves a dangling prompt flag in the command and makes the runtime contract incorrect.

## Acceptance Criteria

1. The final command emitted by `_build_command()` contains exactly one prompt flag pair: `-p <prompt>`.
2. The default base command used by the execution engine no longer contributes a stray trailing `-p`.
3. Strategy tests assert the full command shape, not only the prefix.
4. A real smoke command built from the same contract is accepted by the Claude CLI.

## Files To Adjust

- `mc/application/execution/strategies/provider_cli.py`
  Hint line: `96`
- `mc/application/execution/post_processing.py`
  Hint line: `399`
- `mc/application/execution/engine.py`
  Hint line: search for the default provider-cli command list and `-p`
- `tests/mc/application/execution/test_provider_cli_strategy.py`
  Hint line: `409`
- `tests/mc/provider_cli/test_runtime_wiring.py`
  Hint line: search for `_command[:5]`

## Tasks / Subtasks

- [x] Remove the duplicate prompt flag source from the default command path
- [x] Keep `_build_command()` as the single authority for prompt injection
- [x] Tighten tests so they assert the entire effective command contract
- [x] Re-run backend tests plus one real Claude CLI smoke check

## Dev Notes

- This is backend-only.
- Do not mix this story with Convex persistence changes.
- The real CLI behavior is the source of truth, not prior assumptions from the migration branch.

## Dev Agent Record

### Implementation Plan

Removed the stray trailing `-p` from the default base command list in
`mc/application/execution/post_processing.py` (line 399-405). The `_build_command()`
method in `provider_cli.py` was already the correct authority for injecting `-p <prompt>`
at position 1 (right after the binary). The duplicate was purely in the default command
list passed to `ProviderCliRunnerStrategy`.

### Completion Notes

- Removed `-p` from `_command` default in `build_execution_engine()`.
- Updated `test_default_provider_cli_command_supports_stream_json_contract` to assert
  the base command does NOT include `-p` and has exactly 4 elements.
- Updated `test_build_execution_engine_wires_provider_cli_strategy` in
  `test_runtime_wiring.py` to assert the same correct base command.
- Added new test `test_effective_command_has_exactly_one_prompt_flag` that verifies the
  full effective command shape: exactly one `-p`, prompt at position 1, followed by
  `--verbose --output-format stream-json`.
- AC4 smoke check verified: `claude -p "echo hello" --verbose --output-format stream-json`
  is accepted and processes normally by the real Claude CLI (v2.1.76).
- 116 tests pass (44 provider-cli tests + 72 architecture guardrails), 0 failures.

## File List

- `mc/application/execution/post_processing.py` — removed trailing `-p` from default command
- `tests/mc/application/execution/test_provider_cli_strategy.py` — updated + new test
- `tests/mc/provider_cli/test_runtime_wiring.py` — updated command assertion

## Change Log

- 2026-03-15: Removed duplicate `-p` from provider-cli default command (Story 28-28)
