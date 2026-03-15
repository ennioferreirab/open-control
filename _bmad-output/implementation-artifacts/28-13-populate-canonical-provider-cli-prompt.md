# Story 28.13: Populate Canonical Provider CLI Prompt

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want the canonical execution pipeline to populate `ExecutionRequest.prompt` for provider-cli runs,
so that the provider process receives the actual task or step mission instead of starting with an empty prompt.

## Acceptance Criteria

1. The real task/step context-building flow populates `ExecutionRequest.prompt`.
2. `ProviderCliRunnerStrategy` receives a non-empty prompt from the canonical request path.
3. Tests cover both task and step request construction.
4. No dashboard/frontend work is required in this story.

## Tasks / Subtasks

- [ ] Add failing tests for task and step prompt population
- [ ] Define the canonical prompt rule in `ContextBuilder`
- [ ] Verify provider-cli command construction includes `--prompt` from the real request path

## Dev Notes

- Do not move prompt assembly into the strategy.
- Keep `agent_prompt`, `description`, and `prompt` semantically distinct.
- Validation for this story is backend-only.

## References

- [Source: docs/plans/2026-03-15-provider-cli-cutover-remediation-plan.md]
- [Source: docs/plans/2026-03-15-provider-cli-cutover-remediation-wave-plan.md]
