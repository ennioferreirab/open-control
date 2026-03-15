# Story 28.19: Persist Provider CLI Session Metadata And Bootstrap Prompt

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want provider-cli session metadata persisted in Convex,
so that operators can inspect status, prompt, and failure state without relying on gateway logs.

## Acceptance Criteria

1. `interactiveSessions` reflects the provider-cli session lifecycle.
2. Bootstrap prompt is persisted or previewable.
3. Last error and last event metadata are updated during execution.
4. Provider session id is stored when discovered.

## Tasks / Subtasks

- [ ] Add failing tests for provider-cli session metadata
- [ ] Persist bootstrap prompt and lifecycle summary fields
- [ ] Update failure/completion metadata in real runtime flow

## Dev Notes

- Do not expose chain-of-thought.
- Prompt visibility is diagnostic, not editable.

## References

- [Source: docs/plans/2026-03-15-provider-cli-live-observability-and-intervention-plan.md]
- [Source: docs/plans/2026-03-15-provider-cli-live-observability-and-intervention-wave-plan.md]
