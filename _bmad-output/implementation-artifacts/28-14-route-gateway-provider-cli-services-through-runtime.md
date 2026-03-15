# Story 28.14: Route Gateway Provider CLI Services Through Runtime

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want the real task and step execution paths to consume the provider-cli services composed in the gateway,
so that runtime state is shared consistently and the new backend has a single composition root.

## Acceptance Criteria

1. The runtime-composed provider-cli services are injected into the real execution path.
2. `Executor` and `StepDispatcher` use a coherent engine-construction contract.
3. The supported step path no longer creates hidden default registries/supervisors when runtime services exist.
4. No dashboard/frontend work is required in this story.

## Tasks / Subtasks

- [ ] Add failing tests for runtime service propagation
- [ ] Remove or bypass-proof the alternate under-injected step engine path
- [ ] Verify executor and dispatcher share the same provider-cli injection contract

## Dev Notes

- This story is about runtime cohesion, not parser behavior.
- Default object creation is acceptable only for isolated tests or explicit non-runtime call sites.

## References

- [Source: docs/plans/2026-03-15-provider-cli-cutover-remediation-plan.md]
- [Source: docs/plans/2026-03-15-provider-cli-cutover-remediation-wave-plan.md]
