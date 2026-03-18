# Story 28.24: Align Provider CLI Command Contract With Real Claude CLI

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want the provider-cli strategy to launch Claude CLI with the real supported command contract,
so that backend execution uses the same invocation shape that works in production and in smoke tests.

## Problem Found

The current `ProviderCliRunnerStrategy` still builds the command with `--prompt`, which the real Claude CLI rejects. It also does not consistently include the Claude agent runtime flags that were expected by the earlier cutover plan, and it still drops useful stderr/stdout text in some nonzero-exit paths.

## Acceptance Criteria

1. `_build_command()` no longer emits `--prompt`; it uses the real supported Claude CLI input contract.
2. `_build_command()` includes the required runtime flags for Claude provider execution when present in `ExecutionRequest` or `AgentData`.
3. Nonzero exits without explicit `error` events prefer captured output text over the generic `Process exited with code X`.
4. The real smoke command shape used in validation matches the strategy contract.
5. The currently failing tests in `tests/mc/application/execution/test_provider_cli_strategy.py` pass.

## Tasks / Subtasks

- [ ] Replace the unsupported prompt flag with the real Claude CLI invocation contract
- [ ] Restore required runtime flags in the command builder
- [ ] Fix error-message fallback behavior for nonzero exits
- [ ] Rebaseline the strategy tests against the real command contract

## Dev Notes

- This story is backend-only.
- Use the real `claude` CLI contract as the source of truth, not earlier assumptions from the cutover branch.
- Do not merge this with control-plane wiring or Convex persistence changes.

## References

- [Source: review findings from 2026-03-15 provider-cli backend validation]

