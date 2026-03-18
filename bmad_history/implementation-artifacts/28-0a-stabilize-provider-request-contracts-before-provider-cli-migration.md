# Story 28.0a: Stabilize Provider Request Contracts Before Provider CLI Migration

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want the provider request contracts used by planning and reasoning to be
explicitly test-covered before the provider CLI migration starts,
so that the new runtime is not built on top of unstable provider behavior.

## Acceptance Criteria

1. Anthropic adaptive-thinking requests are covered by focused tests proving
   that `temperature=1.0` is sent whenever thinking is enabled.
2. Non-thinking Anthropic requests keep their intended caller-controlled
   temperature behavior.
3. Planning uses the Lead Agent's configured model instead of a hardcoded
   planning tier.
4. If the Lead Agent model is a tier reference, planning resolves that tier
   from the Lead Agent model rather than from a separate planning default.
5. If the Lead Agent model is a `cc/...` model, planning routes through the
   Claude Code planning path.
6. Planner failures remain visible and do not silently fall back to a different
   provider or heuristic path.

## Success Metrics

- Focused tests prove Anthropic thinking payload behavior for covered paths
- Focused tests prove planning sources its model from the Lead Agent config
- No covered planning path silently ignores a Lead Agent model override

## Tasks / Subtasks

- [ ] Task 1: Lock Anthropic thinking payload behavior with tests (AC: #1, #2)
  - [ ] Add focused tests for adaptive and enabled thinking payloads
  - [ ] Add a focused non-thinking regression test
  - [ ] Keep the fix narrowly scoped to thinking-enabled behavior

- [ ] Task 2: Lock planning to the Lead Agent configured model (AC: #3, #4, #5)
  - [ ] Add focused planning-worker tests for Lead Agent model lookup
  - [ ] Cover `cc/...` and tier-reference Lead Agent models
  - [ ] Ensure Lead Agent lookup does not depend on the delegatable agents list

- [ ] Task 3: Preserve explicit failure behavior (AC: #6)
  - [ ] Add regression coverage proving planning errors stay visible
  - [ ] Confirm no silent provider or heuristic fallback is reintroduced

## Dev Notes

- This story is intentionally about contract hardening, not new runtime design.
- Use TDD throughout; these fixes should be re-proven from failing tests.
- Keep provider-specific behavior isolated to the provider or planning boundary.

### Project Structure Notes

- Likely touch points:
  - `vendor/nanobot/nanobot/providers/anthropic_oauth_provider.py`
  - `mc/runtime/workers/planning.py`
  - `tests/cc/`
  - `tests/mc/workers/`

### References

- [Source: docs/plans/2026-03-14-interactive-runtime-stabilization-and-provider-cli-migration-plan.md]
- [Source: vendor/nanobot/nanobot/providers/anthropic_oauth_provider.py]
- [Source: mc/runtime/workers/planning.py]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
