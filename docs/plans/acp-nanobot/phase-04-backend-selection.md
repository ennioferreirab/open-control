# Phase 4 — Backend selection routes to ACP

Back to [overview.md](overview.md).

## Goal

Make the runner-type resolver return `RunnerType.ACP` for agents whose backend is an ACP harness, so a configured agent reaches the new path. Consolidate the selection in the one place it already lives.

## Changes

- Extend `_resolve_interactive_runner_type` ([mc/application/execution/interactive_mode.py:16](../../../mc/application/execution/interactive_mode.py)) so that when `agent.backend` names a harness in the registry, it returns `RunnerType.ACP`. This branch precedes the existing `provider-cli` default. The `agent.backend` field on `AgentData` ([mc/types.py](../../../mc/types.py)) is the selector; confirm it exists or add it in this phase.
- Keep the existing `is_cc` / `interactive_provider` branches working for Codex and the legacy paths. ACP selection is additive here; the default flip is Phase 6.
- Audit the silent `PROVIDER_CLI` catch-all noted in the investigation. Where an unknown backend currently falls through silently, make it explicit (the no-silent-fallbacks rule).

## Data structures

- `agent.backend: str` — the selector value (`"claude-code"` once Phase 6 flips it; arbitrary harness names later). One field, decided once.

## Verification

**Static.** `make check`. Extend `tests/mc/application/execution/test_interactive_mode.py`: an agent with an ACP-harness backend resolves to `RunnerType.ACP`; non-ACP agents are unchanged; unknown backend raises rather than silently defaulting.

**Runtime.** Exercised end-to-end in Phase 5.
