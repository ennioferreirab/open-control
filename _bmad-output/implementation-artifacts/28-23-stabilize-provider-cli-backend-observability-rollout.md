# Story 28.23: Stabilize Provider CLI Backend Observability Rollout

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want rollout gates and diagnostics tightened for provider-cli backend observability and control,
so that the runtime is considered trustworthy only after backend proof of state projection and subprocess effects.

## Acceptance Criteria

1. Rollout checklist requires backend E2E control proof.
2. Event fidelity, prompt visibility, and command diagnostics are part of the gate.
3. No dashboard dependency exists in the acceptance gate for this stage.
4. Final documentation reflects the backend-first control path.

## Tasks / Subtasks

- [ ] Update rollout checklist and references
- [ ] Require backend E2E proof before downstream consumers are enabled
- [ ] Document current observability limits and operator guarantees

## Dev Notes

- This story is about stabilization and rollout discipline.
- Dashboard remains out of scope for this stage.

## References

- [Source: docs/plans/2026-03-15-provider-cli-live-observability-and-intervention-plan.md]
- [Source: docs/plans/2026-03-15-provider-cli-live-observability-and-intervention-wave-plan.md]
