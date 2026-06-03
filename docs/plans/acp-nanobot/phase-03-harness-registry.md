# Phase 3 — Harness registry

Back to [overview.md](overview.md).

## Goal

Introduce the single source of truth that maps a backend name to how its ACP agent is launched, so adding a backend later is a data entry, not new wiring (the **laziness-protocol** principle: consolidate the decision, pass a simple result). Seed it with Claude Code only.

## Changes

- New `mc/infrastructure/acp/harness_registry.py` holding an immutable table of `HarnessSpec` rows and a lookup by backend name. One row: Claude Code, launched through the `claude-agent-acp` adapter, with the env keys it needs.
- The ACP parser/strategy reads the launch command from the registry rather than hardcoding it, so the engine wiring from Phase 2 stops carrying a literal command.
- Each `HarnessSpec` carries a **tier de-para**: a mapping from a uniform tier label (`low`, `medium`, `high`) to that harness's concrete model id. The orchestrator asks for a tier; the registry resolves it to the model the harness understands (the **boundary-discipline** principle: a uniform tier inside, translated at the harness boundary). This relocates the tier concept that today lives in the global Convex `model_tiers` setting and [mc/infrastructure/providers/tier_resolver.py](../../../mc/infrastructure/providers/tier_resolver.py); that global resolver is deleted with the Factory in Phase 8. Align the tier vocabulary (`low`/`medium`/`high` vs the existing named tiers) here.
- **Model-selection mechanism is spike-verified.** `claude-agent-acp` v0.40.0 resolves its model from the `ANTHROPIC_MODEL` env var (highest priority; accepts aliases `haiku`/`sonnet`/`default`). The ACP launch sets `ANTHROPIC_MODEL` to the tier-resolved value in the harness subprocess env. The adapter default on a MAX account is Opus 4.8, so the launch must ALWAYS set an explicit model and never fall through to that default.
- No selection logic here; that is Phase 4. This phase is pure data plus a lookup.

## Data structures

- `HarnessSpec` — `{ name: str, launch_command: list[str], env_keys: tuple[str, ...], native_acp: bool, model_tiers: dict[str, str] }`. `model_tiers` is the tier de-para (`low`/`medium`/`high` → this harness's concrete model id). For Claude Code (spike-verified): `{low: "haiku", medium: "sonnet", high: "default"}`, where the `default` alias is Opus 4.8 on a MAX account. `native_acp=False` (adapter-wrapped); future native backends are `True`.
- `HARNESSES` — a frozen mapping `name -> HarnessSpec`; lookup raises explicitly on unknown name (no silent fallback, per the no-silent-fallbacks rule).

## Verification

**Static.** `make check`. Unit test `tests/mc/test_harness_registry.py`: lookup returns the Claude Code spec; unknown name raises a clear error; the table is immutable.

**Runtime.** None beyond static; this is pure data exercised live in Phase 5.
