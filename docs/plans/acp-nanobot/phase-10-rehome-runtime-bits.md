# Phase 10 — Re-home the remaining nanobot runtime pieces

Back to [overview.md](overview.md).

> This phase bundles several independent re-homings. Each is small and shippable on its own; split into sub-PRs if any grows past the phase-sizing limits.

## Goal

Move every remaining load-bearing piece mc imports from nanobot into mc-owned modules, so the only thing left tying us to `vendor/nanobot` is the subtree itself (deleted in Phase 11).

## Changes

Each item is a self-contained move (the investigation rated all of these trivial-to-moderate):

- **Memory base.** Move `nanobot.agent.memory.MemoryStore` into `mc/memory/` as the base for `HybridMemoryStore` ([mc/memory/store.py:14](../../../mc/memory/store.py)). Confirm the latent `MemoryStore.consolidate()` → `nanobot.session.Session` dependency is dead before dropping it.
- **Cron.** Move `nanobot.cron.service.CronService` into `mc/runtime/cron/` ([mc/runtime/gateway.py:106](../../../mc/runtime/gateway.py)). Self-contained scheduler; reconcile the two cron store paths the investigation flagged.
- **Telegram helpers.** Copy `_markdown_to_telegram_html` and `_split_message` into [mc/runtime/cron_delivery.py](../../../mc/runtime/cron_delivery.py). Two pure functions.
- **Patched tools (our code living in the vendor tree).** Re-home `AskAgentTool`, `McDelegateTool`, `MissionControlChannel`, `search_memory` from `vendor/nanobot/nanobot/...` into `mc/`. These already import from `mc.bridge` and `mc.infrastructure.config`; the move untangles a circular dependency. The Anthropic OAuth flow (`anthropic_oauth*`) is owned by the ACP harness now and need not be re-homed.
- **Skills loader.** Replace the dynamic `importlib` load of `vendor/nanobot/nanobot/agent/skills.py` ([mc/infrastructure/agent_bootstrap.py:541](../../../mc/infrastructure/agent_bootstrap.py)) with an mc-owned skills loader, or fold skill listing into Convex if that is the direction.

## Data structures

- mc-owned `MemoryStore` base — `read_long_term`, `write_long_term`, `append_history`, `memory_dir`/`_lock`. One-line contract, unchanged from today.

## Verification

**Static.** `make check`; `uv run pytest`. After each sub-move, grep proves the corresponding `nanobot.*` import is gone from `mc/`.

**Runtime.** `make start`. Per move, exercise it live: an agent accumulates memory; a cron job fires and delivers; an agent calls `ask_agent`/`mc_delegate`; a result posts to a Convex task thread; skills distribute at startup. Capture in the PR.
