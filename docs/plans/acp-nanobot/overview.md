# ACP harness layer + nanobot extraction — Overview

> Formal multi-phase plan. The plan is the deliverable. Do not implement from this file; each phase is shipped independently after its own review.

## Context

Today the orchestrator drives agent backends through two unrelated mechanisms:

- **Task execution** runs a coding-agent subprocess through the provider-cli seam (`claude -p ... --output-format stream-json`, NDJSON over stdout) behind `RunnerStrategy` ([mc/application/execution/strategies/base.py](../../../mc/application/execution/strategies/base.py)).
- **Internal one-shot LLM calls** (auto-title, task routing, memory consolidation, the @mention chat reply) go through a provider Factory (`create_provider()` → `LiteLLMProvider.chat()`) that lives on top of the vendored `nanobot` package ([mc/infrastructure/providers/factory.py](../../../mc/infrastructure/providers/factory.py)).

Two decisions set the target state:

1. **Every model interaction will sit behind a harness** (Claude Code, Codex, hermes-agent, openclaw, ...). There will be no raw LLM completions. The provider Factory and nanobot's provider layer are therefore removed, not re-homed.
2. **The uniform protocol between the orchestrator and each harness is ACP** — the Zed Agent Client Protocol, JSON-RPC 2.0 over stdio between a client (this orchestrator) and an agent (a harness). See [agentclientprotocol.com](https://agentclientprotocol.com/get-started/introduction). This is an agent-level protocol, not a completion-level one, so it slots at the `RunnerStrategy`/parser seam, never at the old Factory.

Why now. nanobot is leaving the project. The hardest slice of removing it (re-homing the LiteLLM, OAuth, Codex and Custom providers) only exists to serve the Factory. Adopting ACP first lets that whole slice be deleted instead of ported. The two efforts are one migration.

## Scope

**In scope.**
- An ACP client and an `AcpParser` satisfying the existing `ProviderCLIParser` protocol ([mc/contexts/provider_cli/parser.py](../../../mc/contexts/provider_cli/parser.py)).
- A `RunnerType.ACP` wired into the engine strategy table ([mc/application/execution/engine.py](../../../mc/application/execution/engine.py)).
- A harness registry mapping a backend name to how its ACP agent is launched. Seeded with **Claude Code only** via the `claude-agent-acp` adapter.
- Migrating task execution for Claude Code from the NDJSON `claude -p` path to ACP, then deleting the old path.
- Migrating the internal one-shot call sites off the Factory.
- Deleting the provider Factory and nanobot's provider layer.
- Re-homing the remaining nanobot couplings (config, memory base, cron, telegram helpers, patched tools, skills loader), owning the CLI, and deleting `vendor/nanobot`.

**Out of scope (explicitly).**
- Codex, Gemini, OpenCode, hermes-agent, openclaw harness onboarding. The harness registry is built so each is later a data entry plus an adapter, but none are wired here.
- ACP permission round-trip. Task execution stays autonomous (`--permission-mode bypassPermissions` today); `session/request_permission` is not implemented. Recorded as deferred.
- ACP remote transport (HTTP/WebSocket). Local stdio only.
- The async Convex-mediated approval UX. Untouched.

## Constraints

- **Layered imports** ([agent_docs/code_conventions/python.md](../../../agent_docs/code_conventions/python.md)). `mc/contexts/` may import `mc/infrastructure/`; `mc/runtime/` imports everything. The ACP parser lives at `mc/contexts/provider_cli/providers/acp.py` next to `claude_code.py` and `codex.py`. `from __future__ import annotations`, absolute imports, `str | None` unions, 100-col, double quotes, ruff + pyright via `make check`. 500-line soft cap per module.
- **The `claude-agent-acp` adapter is a Node package** that wraps the Claude Agent SDK. Adopting it adds a Node runtime dependency to the Claude Code execution path and a launch step in Docker. This is a real new dependency; Phase 1 verifies it before anything is built on it.
- **Agent SDK credit quota (spike-verified).** On a MAX subscription the adapter authenticates via the Claude OAuth in the macOS Keychain (no `ANTHROPIC_API_KEY`) and draws from a monthly Agent SDK credit quota, not per-token billing. The `cost.amount` the adapter reports is a notional API-equivalent estimate, not a charge. Routing every model interaction through harnesses consumes this quota; track it as a scaling concern, and always pin an explicit cheap tier (`haiku`) for utility calls rather than the Opus default.
- **Codex still uses the provider-cli NDJSON path.** Phase 6 deletes only the Claude parser, not the parser-agnostic `ProviderCliRunnerStrategy`, so Codex keeps working untouched.
- **Pre-production, no backward compatibility.** Breaking changes are absorbed in-wave. No compatibility shims (the **migrate-callers-then-delete-legacy-apis** and **outcome-oriented-execution** principles).
- **Docker hot-reload.** Python changes need `docker compose restart mc`; the global-solutions rule means every env/volume/entrypoint change lands for `mc` and `mc-test` together.

## Alternatives considered

The **exhaust-the-design-space** principle. Three approaches were weighed.

| Approach | Sketch | Verdict |
|----------|--------|---------|
| **A. ACP at the RunnerStrategy seam + delete the Factory** | Every backend is an ACP harness. Internal one-shot calls move onto a harness. The Factory and nanobot's provider layer are deleted. | **Chosen.** Matches the "no raw calls" direction, and it collapses the hardest slice of the nanobot extraction. |
| B. ACP for task execution, keep a thin mc-owned completion Factory for the internal helpers | Avoids spawning a full agent for a one-line title. | Rejected as the default. It contradicts the stated direction and keeps a provider layer alive. Its one real concern (helper cost) is handled inside Phase 7 instead. |
| C. No ACP; just extract nanobot's Factory into mc | Smallest immediate change. | Rejected. Misses the plug-and-play goal entirely and ports the hard slice instead of deleting it. |

The honest tension in A. The internal one-shot helpers are not agentic tasks. Spawning a coding-agent subprocess per auto-title is wasteful in latency and cost. Phase 7 resolves this per call site with a spike, choosing between a lightweight utility-harness turn and dropping the LLM call where a heuristic suffices. This is the one place A is not free, and it is called out rather than hidden.

## Target architecture (redesign from first principles)

The **redesign-from-first-principles** principle. If built today with these requirements, backend invocation is one protocol at one seam:

- `RunnerStrategy.execute(request) -> ExecutionResult` stays as the seam.
- `RunnerType.ACP` is the one execution path that matters; `PROVIDER_CLI` survives only for Codex until it too moves to ACP later.
- A **harness registry** maps `agent.backend` (`claude-code`, future `codex`, `hermes-agent`, `openclaw`) to an ACP launch spec. Adding a backend is a registry entry plus, if it has no native ACP support, an adapter.
- There is **no provider Factory** and **no `nanobot` import** anywhere in `mc/`.

## Phases

Ordered so shared types and scaffolding land first (the **foundational-thinking** principle), each phase independently shippable. Track A is additive and never imports nanobot, so it proceeds while Track B waits on it.

**Track A — ACP harness layer (additive).**
1. [phase-01-acp-client-transport.md](phase-01-acp-client-transport.md) — ACP Python client, session/turn types, dependency, de-risk spike.
2. [phase-02-acp-parser.md](phase-02-acp-parser.md) — `AcpParser` satisfying `ProviderCLIParser`; `RunnerType.ACP`; engine wiring.
3. [phase-03-harness-registry.md](phase-03-harness-registry.md) — harness registry; seed Claude Code via `claude-agent-acp`.
4. [phase-04-backend-selection.md](phase-04-backend-selection.md) — `agent.backend` drives `RunnerType.ACP` selection.
5. [phase-05-claude-code-onboard.md](phase-05-claude-code-onboard.md) — Claude Code through ACP behind a flag; real-task end-to-end proof.

**Bridge — flip and migrate.**
6. [phase-06-flip-default-delete-old-claude-path.md](phase-06-flip-default-delete-old-claude-path.md) — ACP becomes the Claude Code default; delete the NDJSON `claude -p` parser.
7. [phase-07-internal-helpers-migration.md](phase-07-internal-helpers-migration.md) — title, routing, memory, chat off the Factory. Contested; spike + adversarial review.

**Track B — nanobot removal (unlocked once the Factory has no callers).**
8. [phase-08-delete-provider-factory.md](phase-08-delete-provider-factory.md) — delete the Factory and all `nanobot.providers` imports.
9. [phase-09-rehome-config.md](phase-09-rehome-config.md) — mc-owned config replacing `nanobot.config`.
10. [phase-10-rehome-runtime-bits.md](phase-10-rehome-runtime-bits.md) — memory base, telegram helpers, cron, patched tools, skills loader into `mc/`.
11. [phase-11-own-cli-delete-vendor.md](phase-11-own-cli-delete-vendor.md) — mc owns the CLI; packaging, Docker, dashboard, docs, tests; delete `vendor/nanobot`.

## Verification

Project-level, run at every phase boundary and again at plan completion (the **outcome-oriented-execution** principle requires full verification before done):

- `make check` (pre-commit aggregate)
- `make lint && make typecheck`
- `uv run pytest`
- `cd dashboard && npm run test`
- Runtime: `make start`, then exercise the touched path on the real stack. See [testing.md](testing.md).

## Implementation guidance

The implementer applies these poteto-mode non-negotiables, by name:

- The **how** skill over each unfamiliar subsystem before changing it (provider-cli seam, engine dispatch, memory store).
- The **architect** skill on Phase 2 (the parser seam crosses a function boundary and has design latitude in event mapping).
- The **interrogate** skill (four-model adversarial) on Phase 7, the one contested design, before shipping it.
- The **skill-creator** skill for any phase that authors or edits a SKILL.md (none currently, but Phase 10 touches the skills loader).
- The `/simplify` command over each diff, and the **unslop** skill over every prose surface, before commit.
- The **show-me-your-work** skill to keep an auditable decision trail; this migration is large enough to warrant committing it.
- Monitor each PR after opening (CI and review); `/loop` can drive periodic checks.
- TDD for behavior changes and bug fixes: failing test first (red), then fix (green).
- Worktree per phase; never implement on `main`. Delete the worktree after merge.

## Data shapes introduced

Named here so they are decided once (the **foundational-thinking** principle); detail lives in the phase files.

- `AcpClient` — owns one stdio JSON-RPC connection to a harness; `initialize`, `session/new`, `session/prompt`, `session/cancel`, consumes `session/update`.
- `AcpParser` — class attr `provider_name = "acp"`; satisfies `ProviderCLIParser`; maps `session/update` notifications to `ParsedCliEvent`.
- `HarnessSpec` — `{ name, launch_command, env_keys, native_acp, model_tiers }`; one row per backend in the harness registry. `model_tiers` is a tier de-para (`low`/`medium`/`high` → that harness's concrete model id).
- Title-generation config — `{ mode: "heuristic" | "llm", harness: <name> }`; LLM mode runs one turn on that harness at its `low` tier.
- mc-owned `Config` — the ~8 fields `mc/` actually reads, replacing `nanobot.config.schema.Config`.
