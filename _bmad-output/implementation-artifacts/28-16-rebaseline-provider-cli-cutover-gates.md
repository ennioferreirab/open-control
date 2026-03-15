# Story 28.16: Rebaseline Provider CLI Cutover Gates

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want the remaining cutover stories rebaselined on top of the remediation work,
so that `28-11` and `28-12` only proceed after the backend path is actually proven.

## Acceptance Criteria

1. The cutover checklist reflects the real supported path requirements.
2. `28-11` depends on the remediation stories being complete.
3. `28-12` is explicitly blocked until the backend-only no-tmux proof is green.
4. No dashboard/frontend work is required in this story.

## Tasks / Subtasks

- [ ] Update the recovery plan and wave plan to include the remediation prerequisite chain
- [ ] Update `28-11` and `28-12` references and gates
- [ ] Tighten the checklist definition of "no tmux" to mean the real supported runtime path

## Dev Notes

- This story does not implement the cutover itself.
- This story resets the control plane so the next default flip is evidence-based.

## References

- [Source: docs/plans/2026-03-15-provider-cli-cutover-remediation-plan.md]
- [Source: docs/plans/2026-03-15-provider-cli-cutover-remediation-wave-plan.md]
