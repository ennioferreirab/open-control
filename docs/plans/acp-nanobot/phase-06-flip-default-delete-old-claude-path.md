# Phase 6 — Flip default to ACP, delete the NDJSON Claude path

Back to [overview.md](overview.md).

## Goal

Make ACP the default for Claude Code and remove the old `claude -p --output-format stream-json` parser in the same wave (the **migrate-callers-then-delete-legacy-apis** principle: no dual path left alive).

## Changes

- Flip the selector so Claude Code agents resolve to `RunnerType.ACP` by default; remove the Phase 5 opt-in flag.
- Delete `ClaudeCodeCLIParser` (the NDJSON parser, `mc/contexts/provider_cli/providers/claude_code.py`) and its registration. Delete the deprecated `ClaudeCodeProvider` SDK path ([vendor/claude-code/claude_code/provider.py](../../../vendor/claude-code/claude_code/provider.py)) and `RunnerType.CLAUDE_CODE` if nothing else references it after this flip (the investigation found it already effectively dead).
- Keep `ProviderCliRunnerStrategy` and the Codex parser intact. Codex is out of scope and still uses provider-cli.
- Update tests: delete tests that only asserted NDJSON parsing internals; rewrite execution tests to assert the ACP contract (the migrate-then-delete rule on tests).

## Data structures

- No new types. This is removal plus a default change.

## Verification

**Static.** `make check`; `uv run pytest`. Grep proves zero references to the deleted parser and to `claude -p ... stream-json` remain.

**Runtime.** `make start`. A normal Claude Code task (no flag) now runs through ACP. Confirm a Codex task still runs through provider-cli unchanged (regression guard). Drive both on the real stack; capture in the PR. Intermediate breakage between Phase 5 and here is acceptable and planned (the **outcome-oriented-execution** principle); full runtime verification is mandatory at this boundary.
