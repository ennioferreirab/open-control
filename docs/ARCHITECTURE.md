# Open Control Architecture

Open Control is a multi-agent orchestration platform built from three owned
layers plus two vendor dependencies:

- `mc/` is the Python orchestration backend. It owns runtime lifecycle,
  execution, agent routing, and the bridge to Convex.
- `dashboard/` is the Next.js and Convex dashboard. It owns the operator UI,
  realtime state, and dashboard-side APIs that interact with local runtime
  files.
- `shared/` holds cross-language contracts that must stay aligned between the
  Python runtime and TypeScript dashboard.
- `vendor/nanobot/` is the upstream runtime dependency that still provides part
  of the agent substrate.
- `vendor/claude-code/` is the Claude Code integration layer maintained in this
  repository.

## Ownership Boundaries

Open Control owns the orchestration layer, dashboard, local platform glue, and
cross-service contracts. Do not modify `vendor/nanobot/` without explicit
approval because it is an upstream subtree.

## Runtime Compatibility Notes

The public product name is **Open Control**, but some runtime compatibility
surfaces still carry the legacy `nanobot` name:

- CLI examples may still use `nanobot mc ...`
- local runtime data still lives under `~/.nanobot`
- vendor import paths still resolve through `nanobot.*`

These legacy names are compatibility details, not the intended public brand.

## High-Level Structure

- `mc/runtime/` composes services and process lifecycle.
- `mc/contexts/` owns domain behavior such as conversation, execution, routing,
  planning, and agents.
- `mc/bridge/` is the Python to Convex integration boundary.
- `dashboard/convex/` is the persistent state source of truth.
- `dashboard/features/` groups UI and hooks by product area.

For day-to-day development workflow and startup commands, see
[`CONTRIBUTING.md`](../CONTRIBUTING.md) and the binding docs in
[`agent_docs/`](../agent_docs/).
