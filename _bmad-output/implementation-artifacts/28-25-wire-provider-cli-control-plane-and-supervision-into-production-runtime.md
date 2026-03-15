# Story 28.25: Wire Provider CLI Control Plane And Supervision Into Production Runtime

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want the provider-cli control plane and supervision sink to be part of the real execution path,
so that interrupt/stop/resume and session event projection work in the canonical backend runtime rather than only in isolated tests.

## Problem Found

The gateway composes `ProviderCliControlPlane`, registry, supervisor, and projector, but the canonical execution path does not inject the control plane or supervision sink into `ProviderCliRunnerStrategy`. As a result, the runtime strategy built by `build_execution_engine()` comes up with `control_plane=None` and `supervision_sink=None`.

## Acceptance Criteria

1. `build_execution_engine()` accepts and passes `provider_cli_control_plane` to `ProviderCliRunnerStrategy`.
2. `TaskExecutor` and `StepDispatcher` propagate `provider_cli_control_plane` through the canonical backend path.
3. The production runtime composition from `gateway.py` wires both control plane and supervision sink into the provider-cli strategy.
4. A runtime composition check proves that `build_execution_engine()` returns a provider-cli strategy with non-`None` `control_plane` and `supervision_sink` when the gateway services are provided.
5. No legacy interactive-tui dependency is reintroduced.

## Tasks / Subtasks

- [ ] Extend the execution engine builder contract with `provider_cli_control_plane`
- [ ] Propagate the dependency through executor and step dispatcher
- [ ] Wire the gateway composition root to the updated engine path
- [ ] Add runtime wiring tests for non-null control plane and supervision sink

## Dev Notes

- This story is backend-only.
- The canonical path is the gate; local test harnesses are not enough.
- Keep the fix narrowly focused on runtime composition.

## References

- [Source: review findings from 2026-03-15 provider-cli backend validation]

