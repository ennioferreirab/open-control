# Story 28.20: Add Real Provider CLI Interrupt Stop Resume Control Plane

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want interrupt, stop, and resume operations to affect the real provider-cli subprocess,
so that operator controls are not just metadata patches.

## Acceptance Criteria

1. Backend exposes real interrupt and stop operations for provider-cli sessions.
2. Resume works where supported or fails explicitly where unsupported.
3. Registry, Convex state, and subprocess behavior stay consistent.
4. Tests prove the control plane reaches the real runtime services.

## Tasks / Subtasks

- [ ] Add failing tests for real intervention control routing
- [ ] Create backend control plane for provider-cli sessions
- [ ] Connect backend control entrypoints to the control plane and runtime services

## Dev Notes

- This story is backend-first and process-effect oriented.
- Existing human takeover metadata is not sufficient proof.

## References

- [Source: docs/plans/2026-03-15-provider-cli-live-observability-and-intervention-plan.md]
- [Source: docs/plans/2026-03-15-provider-cli-live-observability-and-intervention-wave-plan.md]
