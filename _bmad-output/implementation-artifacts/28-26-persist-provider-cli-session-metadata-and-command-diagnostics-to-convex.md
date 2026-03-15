# Story 28.26: Persist Provider CLI Session Metadata And Command Diagnostics To Convex

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want provider-cli session metadata and command-effect diagnostics persisted to Convex,
so that backend state reflects the real runtime session instead of only the in-memory registry.

## Problem Found

The in-memory `ProviderSessionRegistry` now carries `bootstrap_prompt`, `provider_session_id`, and command-effect diagnostics, but the `interactiveSessions` Convex schema and mutations do not persist those fields. This breaks the contract promised by stories 28-19 and 28-22.

## Acceptance Criteria

1. `interactiveSessions` schema supports provider-cli bootstrap prompt, provider session id, and command-effect diagnostic fields.
2. The runtime path persists those fields from the in-memory session record into Convex.
3. `interactiveSessions.upsert` accepts and writes the new fields without breaking existing consumers.
4. Convex tests cover the new fields explicitly.
5. Backend tests prove the runtime session data survives beyond in-memory state.

## Tasks / Subtasks

- [ ] Add the missing provider-cli fields to the Convex schema
- [ ] Update `interactiveSessions.upsert` to persist the new metadata
- [ ] Connect runtime session metadata updates to the Convex persistence path
- [ ] Add tests for bootstrap prompt, provider session id, and command diagnostics

## Dev Notes

- This story is backend-only even though it touches Convex schema and functions.
- Do not add dashboard rendering in this story.
- Preserve backward compatibility for older interactive session records.

## References

- [Source: review findings from 2026-03-15 provider-cli backend validation]

