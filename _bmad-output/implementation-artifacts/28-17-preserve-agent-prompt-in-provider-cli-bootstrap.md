# Story 28.17: Preserve Agent Prompt In Provider CLI Bootstrap

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want the `provider-cli` bootstrap prompt to preserve the agent's system instructions and orientation,
so that the supported backend executes with the same persona, guardrails, and role-specific behavior as the legacy paths.

## Acceptance Criteria

1. The canonical bootstrap passed to `provider-cli` includes both the agent instructions and the operational mission.
2. `agent_prompt`, `description`, and `prompt` remain semantically distinct in the execution request model.
3. Backend tests prove the provider-cli path preserves orientation/persona instead of sending only the task body.
4. No dashboard/frontend work is required in this story.

## Tasks / Subtasks

- [ ] Add failing tests that prove the provider-cli bootstrap includes agent instructions
- [ ] Define the canonical composition rule for provider-cli bootstrap input
- [ ] Verify task and step paths both preserve `agent_prompt`

## Dev Notes

- Do not collapse `agent_prompt` into `description`.
- Do not reintroduce prompt assembly ad hoc inside the parser.
- Prefer a single canonical bootstrap contract that can be tested at `ContextBuilder` and `ProviderCliRunnerStrategy` boundaries.
- Validation for this story is backend-only.

## References

- [Source: docs/plans/2026-03-15-provider-cli-cutover-remediation-plan.md]
- [Source: docs/plans/2026-03-15-provider-cli-cutover-remediation-wave-plan.md]
