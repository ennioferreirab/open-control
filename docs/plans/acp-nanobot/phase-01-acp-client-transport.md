# Phase 1 — ACP client transport, types, and de-risk spike

Back to [overview.md](overview.md).

## Goal

Stand up a minimal Python ACP client that can drive one harness over stdio, and prove the `claude-agent-acp` adapter works end-to-end before any mc code depends on it. This is scaffolding the later phases build on (the **foundational-thinking** principle).

## Changes

- Add the `agent-client-protocol` Python dependency to [pyproject.toml](../../../pyproject.toml). Confirm it ships both client and agent sides and pin the version verified in the spike.
- New module `mc/infrastructure/acp/client.py` holding a thin async wrapper over one stdio JSON-RPC connection. It owns process stdin/stdout framing and exposes the handful of calls mc needs (`initialize`, `session/new`, `session/prompt`, `session/cancel`) and an async iterator of `session/update` notifications. Keep it transport-only; no mc domain logic (the **boundary-discipline** principle: the protocol adapter is a thin shell, logic stays out of it).
- New module `mc/infrastructure/acp/types.py` for the request/response and update payload types mc consumes.
- **De-risk spike** (throwaway, not shipped): a standalone script that launches `claude-agent-acp` as a subprocess, runs one prompt turn, and prints the streamed updates. Its purpose is to confirm the adapter, the Node dependency, auth, and the update stream before Phase 2. Delete it once Phase 2 lands; its evidence goes in the PR description.

## Data structures

- `AcpClient` — wraps one stdio connection; async; one harness process per instance.
- ACP payload types in `types.py` — `SessionUpdate`, `PromptTurnResult`, capability/init structs, named to mirror the protocol schema.

## Verification

**Static.** `make lint && make typecheck`; `uv run pytest` for the new client's unit tests (mock the subprocess stdio with in-memory pipes, the dominant style in `tests/mc/provider_cli/`).

**Runtime (the de-risk gate, the prove-it-works principle).** Run the spike against a real `claude-agent-acp` process. Confirm: process launches, `initialize` handshake returns capabilities, `session/prompt` yields streamed `session/update` events, final result is captured. Capture the transcript in the PR. If the adapter or Node dependency does not behave, stop and revisit Alternative B before continuing.
