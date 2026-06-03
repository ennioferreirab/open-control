# Phase 11 — Own the CLI, delete vendor/nanobot, clean up

Back to [overview.md](overview.md).

## Goal

Cut the last cords. mc owns its own CLI entry point, the `vendor/nanobot` subtree is deleted, and packaging, Docker, dashboard, docs, and tests carry no nanobot reference. The end state has zero `import nanobot` anywhere (the **outcome-oriented-execution** principle: converge on the target, verify fully).

## Changes

- **CLI ownership.** Make `mc_app` the standalone Typer root ([mc/cli/__init__.py](../../../mc/cli/__init__.py)); change the entry point to `open-control = "mc.cli:app"` in [pyproject.toml](../../../pyproject.toml); delete [boot.py](../../../boot.py) and the `mc`-into-nanobot registration. Drop the nanobot-only commands mc never uses (gateway, channels, onboard, provider). This is one atomic move; the CLI breaks all at once otherwise (investigation gotcha).
- **Packaging.** Remove the `nanobot-ai` dependency, the `nanobot = "boot:cli"` script, and the ruff/pyright/isort excludes and `known-third-party` entry for nanobot. `uv.lock` regenerates.
- **Docker.** Rename the `nanobot` binary invocations to `open-control` in [Dockerfile](../../../Dockerfile) and the entrypoint scripts; remove the `/root/.nanobot` mkdir and the legacy host-config copy block. Apply to `mc` and `mc-test` together (the global-solutions rule).
- **Dashboard / Convex.** Fix the broken `nanobot.mc.*` Python import path in [dashboard/app/api/agents/assist/route.ts](../../../dashboard/app/api/agents/assist/route.ts). **Back up Convex first (export the data), then drop** the `NANOBOT_HOME` env fallback and the legacy `"nanobot"` skill-provider enum in [dashboard/convex/schema.ts](../../../dashboard/convex/schema.ts) (decided). The export precedes the schema push because dropping the enum fails validation on any existing record still holding `"nanobot"`; reconcile or migrate those rows after the backup. Export only — never delete the Convex volume (the never-delete-volumes rule).
- **Tests.** Migrate the ~22 direct `import nanobot` test files, ~40 `patch("nanobot...")` strings, and the `~/.nanobot` fixture paths to the new module homes. Rename the special-cased `"nanobot"` agent name and the `NANOBOT_MEMORY_EMBEDDING_MODEL` env var.
- **Docs.** Rewrite the nanobot sections of [agent_docs/service_architecture.md](../../../agent_docs/service_architecture.md), [harness_engineering.md](../../../agent_docs/harness_engineering.md), [service_communication_patterns.md](../../../agent_docs/service_communication_patterns.md), and the vendor-boundary section of [CLAUDE.md](../../../CLAUDE.md). Add an ACP harness section reflecting the new architecture; keep the structural contracts in sync (the in-PR rule).
- **Delete** `vendor/nanobot/` and `vendor/NANOBOT_PATCHES.md`.

## Data structures

- Net removal. No new types.

## Verification

**Static.** `make check`; `uv run pytest`; `cd dashboard && npm run test`. Grep across the whole repo proves zero `import nanobot`, zero `nanobot.`, and zero `vendor/nanobot` references outside this plan's own history.

**Runtime (plan-completion gate).** `make start` from a clean build. Full smoke on the real stack: stack boots, a Claude Code task runs through ACP to completion, an @mention replies, memory and cron work, the dashboard renders task and thread state. This is the final verification boundary; nothing ships unproven. Capture the full transcript in the PR.
