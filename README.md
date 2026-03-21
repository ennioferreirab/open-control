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

## Agent Docs — Harness Engineering

The [`agent_docs/`](agent_docs/) directory is the most important entry point for
understanding how Open Control works. It contains the binding contracts that
every AI agent and every human contributor must read before modifying a
layer. While `CLAUDE.md` describes the full application in a single file,
`agent_docs/` breaks it down into focused, self-contained references:

| Document | What it covers |
|----------|----------------|
| [`service_architecture.md`](agent_docs/service_architecture.md) | Every runtime service, process lifecycle, IPC protocols, and the task execution state machine |
| [`service_communication_patterns.md`](agent_docs/service_communication_patterns.md) | How services talk to each other — IPC sockets, Convex bridge, webhooks, inter-agent messaging |
| [`database_schema.md`](agent_docs/database_schema.md) | All Convex tables, field types, indexes, relationships, and valid enum values |
| [`harness_engineering.md`](agent_docs/harness_engineering.md) | Platform internals — skills, memory, workspaces, threads, and squad routing |
| [`building_the_project.md`](agent_docs/building_the_project.md) | Setup, startup sequence, port assignments, and health checks |
| [`running_tests.md`](agent_docs/running_tests.md) | What to test, what to skip, banned anti-patterns, and the quality checklist |
| [`scaling_decisions.md`](agent_docs/scaling_decisions.md) | Architectural decisions that work now but need revisiting at scale |
| [`code_conventions/`](agent_docs/code_conventions/) | Python, TypeScript, and Convex coding standards |

These docs are structural contracts — if a code change alters behavior governed
by one of them, the doc must be updated in the same commit.

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

## Compatibility Notes

Open Control is the public product name for this repository.

Until the compatibility migration is complete, the following legacy surfaces are
still supported:

- the new `open-control` CLI alias for public docs and packaging
- the `nanobot` CLI name for current runtime commands
- the `~/.nanobot` runtime home directory
- upstream import paths exposed through `nanobot.*`

These are compatibility details, not the intended public brand.

## License

This project is available under the [MIT License](LICENSE).
