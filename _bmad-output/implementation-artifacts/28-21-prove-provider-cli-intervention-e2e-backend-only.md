# Story 28.21: Prove Provider CLI Intervention E2E Backend Only

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want backend-only end-to-end tests proving provider-cli intervention changes a real subprocess,
so that the control plane is trusted before the dashboard depends on it.

## Acceptance Criteria

1. Automated tests start a real subprocess through the provider-cli runtime path.
2. Automated tests prove interrupt and stop change process state for real.
3. Session activity and registry state remain consistent after intervention.
4. No dashboard/frontend dependency is required for proof.

## Tasks / Subtasks

- [ ] Add failing backend e2e control tests with real subprocesses
- [ ] Prove start/stream/interrupt/stop behavior
- [ ] Prove consistent terminal states after failures and stops

## Dev Notes

- Use deterministic subprocess fixtures.
- This story is the proof gate for any live-control UI.

## References

- [Source: docs/plans/2026-03-15-provider-cli-live-observability-and-intervention-plan.md]
- [Source: docs/plans/2026-03-15-provider-cli-live-observability-and-intervention-wave-plan.md]
