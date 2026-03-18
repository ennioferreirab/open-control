# Story 28.18: Project Provider CLI Events To Convex

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want provider-cli runtime events persisted to Convex,
so that backend observability is based on real session activity instead of logs and inferred state.

## Acceptance Criteria

1. Provider-cli sessions append normalized events to `sessionActivityLog`.
2. Event projection includes text, tool use, lifecycle, and failure events.
3. Sequence ordering is deterministic per session.
4. No chain-of-thought raw dump is persisted.

## Tasks / Subtasks

- [ ] Add failing tests for provider-cli event projection
- [ ] Project runtime events into `LiveStreamProjector` and the canonical supervision sink
- [ ] Normalize event kinds for backend consumers and persisted session activity

## Dev Notes

- Backend-first story.
- Reuse the existing supervision contract where possible; do not create a parallel provider-specific sink.

## References

- [Source: docs/plans/2026-03-15-provider-cli-live-observability-and-intervention-plan.md]
- [Source: docs/plans/2026-03-15-provider-cli-live-observability-and-intervention-wave-plan.md]
