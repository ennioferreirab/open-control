# Story 28.27: Revalidate Provider CLI Backend Cutover With Real Smoke Gates

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want the provider-cli backend cutover revalidated after remediation,
so that completion is based on passing backend tests and real smoke checks instead of commit presence.

## Problem Found

The earlier story set was reported complete, but the backend validation still found failing strategy tests, an invalid real Claude CLI command shape, and missing runtime composition. The rollout gate needs a final revalidation story tied to concrete backend proof.

## Acceptance Criteria

1. The remediation suites for strategy, runtime wiring, supervision, control plane, and E2E subprocess tests all pass.
2. A real Claude CLI smoke command succeeds with the same command contract emitted by the strategy.
3. A runtime composition check confirms the provider-cli strategy is built with live `control_plane` and `supervision_sink`.
4. Any remaining failure blocks rollout and is documented explicitly.
5. The backend cutover is not considered complete without this story passing.

## Tasks / Subtasks

- [ ] Run the backend test suites covering command contract, wiring, and subprocess effects
- [ ] Run the real Claude CLI smoke validation against the remediated command shape
- [ ] Run the runtime composition check for control plane and supervision sink
- [ ] Record the gate result and any remaining blockers

## Dev Notes

- This story is verification-first.
- Do not declare rollout complete from unit tests alone.
- Use backend proof as the only acceptance source for this stage.

## References

- [Source: review findings from 2026-03-15 provider-cli backend validation]

