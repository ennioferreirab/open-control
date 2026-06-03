# Phase 8 — Delete the provider Factory, route utility calls through ACP

Back to [overview.md](overview.md).

## Goal

Delete the provider Factory and every `nanobot.providers` import it carried. The
internal one-shot LLM calls that still used the Factory (routing, memory
consolidation, opt-in auto-title) move onto the ACP harness instead of a
re-homed completion client (the **subtract-before-you-add** and
**outcome-oriented-execution** principles). No raw completions remain.

## Decisions taken during implementation

The overview's "approach A" (no raw completions; delete the provider layer,
do not re-home it) was confirmed by the user against the alternative of
re-homing the OAuth completion client ("approach B"). The contested per-site
choice from Phase 7 was then settled live:

- **Routing** keeps LLM judgment but runs as an ACP utility turn (the user
  chose this over a deterministic heuristic, accepting the per-task cost).
- **Memory consolidation** runs as an ACP utility turn.
- **Auto-title** stays heuristic by default (Phase 7); its opt-in LLM path
  now also runs as an ACP utility turn.

ACP-layer constraints that shaped the design (verified by reading the
Phase 1–5 code):

- **No structured tool output over ACP.** The harness executes tools itself
  and returns only final assistant text (`AcpTurnResult.text`). The old
  `save_memory` / routing function-tool pattern cannot survive, so callers
  prompt for text/JSON and parse it (`extract_json`, which tolerates agent
  preamble). `allowed_tools=[]` forbids the harness from wandering into tools.
- **Subprocess per call, no pool.** Each turn spawns the `claude-agent-acp`
  adapter; there is no pooling in this phase. The per-task latency cost is
  accepted; a persistent utility-harness pool is a possible later phase.
- **Harness self-authenticates.** It reads `CLAUDE_CODE_OAUTH_TOKEN` from the
  inherited env, so `mc` never needs `get_anthropic_token`. The OAuth helper
  is therefore neither re-homed nor referenced.

## Changes

- New `mc/infrastructure/acp/utility.py`: `run_utility_turn(prompt, *, tier,
  timeout_s, cwd) -> str` (one prompt through the claude-code harness, no
  tools, text out; raises `ProviderError` on failure/timeout/empty) and
  `extract_json(text) -> dict`.
- New `mc/infrastructure/providers/errors.py`: mc-owned `ProviderError`
  (replaces the Factory's). `AnthropicOAuthExpired` is gone — auth is the
  harness's job.
- Migrated callers to `run_utility_turn`: routing
  ([llm_delegator.py](../../../mc/contexts/routing/llm_delegator.py)), history
  consolidation ([consolidation.py](../../../mc/memory/consolidation.py)),
  task consolidation ([service.py](../../../mc/memory/service.py)), opt-in
  auto-title ([orchestrator.py](../../../mc/runtime/orchestrator.py)).
- Dropped the now-dead model/tier threading: `resolve_consolidation_model`,
  `HybridMemoryStore._resolve_consolidation_model`, the `model` params on both
  consolidate functions, and the model resolution in
  [post_processing.py](../../../mc/application/execution/post_processing.py).
- Provider-error catch sites source `ProviderError` from
  `mc.infrastructure.providers.errors` and drop the
  `nanobot.providers.anthropic_oauth` import; a dead duplicate of the
  collector in [contexts/execution/post_processing.py](../../../mc/contexts/execution/post_processing.py)
  was removed.
- `list_available_models` moved to
  [model_listing.py](../../../mc/infrastructure/providers/model_listing.py)
  (config/OAuth only; Codex merge dropped).
- Deleted [factory.py](../../../mc/infrastructure/providers/factory.py),
  `tool_adapters.py` (served only the out-of-scope Codex path), and the
  `mc/audit/memory_cohesion.py` diagnostic (nanobot-AgentLoop-coupled, used
  only by its own test).

## Known transitional state (resolved in Phases 10–11)

Two **vendor** call sites still reference the deleted Factory through *lazy*
imports, so they do not break import or the live ACP runtime: nanobot's CLI
`_make_provider` ([vendor cli/commands.py](../../../vendor/nanobot/nanobot/cli/commands.py))
and the `AskAgentTool` ([vendor ask_agent.py](../../../vendor/nanobot/nanobot/agent/tools/ask_agent.py)).
Both run only on the dead nanobot AgentLoop path and are re-homed when that
code moves into `mc/`. The `AskAgentTool` tests are skipped (not deleted)
until then.

## Data structures

- `ProviderError` (mc-owned). Otherwise net removal.

## Verification

**Static.** `make lint` (ruff) clean. `make typecheck` adds zero new pyright
errors (3 pre-existing errors in untouched files remain). `uv run pytest`
green. Grep proves zero `create_provider` in `mc/`; `nanobot.providers` in
`mc/` is reduced to the provider registry (secrets, memory embeddings) and one
litellm import in the deprecated agent-assist CLI, all owned by Phases 9/11.

**Runtime.** `make start`; exercise routing (a task picks an agent) and memory
consolidation end-to-end over ACP. This is the gate for the per-task ACP
utility-turn behavior (does the coding-agent harness return parseable
JSON/text for utility prompts). Capture in the PR.
