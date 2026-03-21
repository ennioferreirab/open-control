<p align="center">
  <img src="assets/bento_hero.png" alt="Bento — Open Control mascot" width="700">
</p>

<h1 align="center">Open Control</h1>

<p align="center">
  AI agent orchestration platform — run, observe, and coordinate multi-agent workflows<br>
  from a Python backend and a realtime web dashboard.
</p>

---

This repository owns the orchestration layer, the dashboard, and the glue code
that connects local runtime state to Convex. It currently depends on
[`vendor/nanobot/`](vendor/nanobot/) as an upstream runtime substrate, so some
runtime compatibility surfaces still use the legacy `nanobot` name while the
public brand shifts to Open Control.

## Why Open Control

Open Control is built for work that needs more than a single chat loop:

- decompose work into steps and route them to specialist agents
- observe task, step, and agent state in a live dashboard
- keep local files, artifacts, memory, and agent definitions connected to the
  orchestration runtime
- evolve the system in the open without losing compatibility for current users

## Start Here

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+

### Local setup

```bash
make install
```

### Run the stack

```bash
make start
```

The dashboard lives in [`dashboard/`](dashboard/) and the local Convex backend
uses port `3210`.

> Only one local Convex backend can run at a time. If you are working from a
> separate worktree, use `make takeover PORT=300x` from that worktree instead
> of starting another default stack on port `3000`.

### Validate changes

```bash
make check
```

## Compatibility Notes

Open Control is the public product name for this repository.

Until the compatibility migration is complete, the following legacy surfaces are
still supported:

- the new `open-control` CLI alias for public docs and packaging
- the `nanobot` CLI name for current runtime commands
- the `~/.nanobot` runtime home directory
- upstream import paths exposed through `nanobot.*`

These are compatibility details, not the intended public brand.

## Repository Structure

```text
mc/                  Python backend for orchestration, runtime, and Convex bridge
dashboard/           Next.js + Convex dashboard
shared/              Cross-language workflow contracts
tests/mc/            Python test suite
vendor/nanobot/      Upstream runtime dependency - do not edit without approval
vendor/claude-code/  Maintained integration layer for Claude Code
agent_docs/          Binding structural and engineering contracts
```

## Architecture

- `mc/runtime/` composes service startup, orchestration, and worker lifecycle.
- `mc/contexts/` owns domain behavior such as conversation, execution, routing,
  planning, and agents.
- `mc/bridge/` is the Python-to-Convex integration boundary.
- `dashboard/convex/` is the persistent state source of truth.
- `dashboard/features/` groups UI and hooks by product area.

## Vendor Boundary

Open Control owns the orchestration layer, dashboard, repo docs, and local
platform integration. `vendor/nanobot/` is an upstream git subtree and must not
be edited without explicit approval. All modifications to the upstream nanobot
code are documented in
[`vendor/NANOBOT_PATCHES.md`](vendor/NANOBOT_PATCHES.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, validation commands, and repo
workflow expectations.

## Mascot

**Bento** is the Open Control mascot a black Shih Tzu who runs mission
control. The dogs in the control room represent AI agents; the humans represent
the people who work alongside them.

## License

This project is available under the [MIT License](LICENSE).
