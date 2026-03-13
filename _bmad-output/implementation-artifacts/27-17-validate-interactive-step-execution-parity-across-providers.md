# Story 27.17: Validate Interactive Step Execution Parity Across Providers

Status: done

## Story

As a Mission Control platform owner,
I want a full parity validation pass across Claude Code, Codex, and Nanobot interactive step execution,
so that `Live` and backend-owned TUI execution can be trusted as the default model.

## Acceptance Criteria

1. Real end-to-end validation covers interactive step execution for Claude Code, Codex, and Nanobot.
2. For each provider, validation confirms:
   - correct step/agent/provider ownership
   - `Live` attach shows the running session
   - final result reaches the task thread
   - ask-user/review transitions behave correctly when applicable
   - memory bootstrap and consolidation trigger as expected
3. Validation explicitly checks that there is no hidden fallback to headless execution in the tested flows.
4. Residual provider-specific gaps are documented clearly if any parity item remains intentionally incomplete.
5. Playwright evidence is captured for each provider where a visible `Live` flow exists.

## Success Metrics

- Parity checklist completed for all three providers
- Zero validated flows silently fall back to headless execution
- Residual risk list is explicit and provider-scoped, with no ambiguous “works in theory” outcomes

## Tasks / Subtasks

- [x] Task 1: Build a provider parity checklist and automated coverage (AC: #1, #2, #3)
  - [x] Add targeted tests that assert no-headless-fallback behavior in interactive flows
  - [x] Add focused coverage for provider-specific parity requirements
  - [x] Reuse the new contracts from Stories 27.12 through 27.16 rather than re-testing through ad hoc scripts only

- [x] Task 2: Run full-stack validation per provider (AC: #1, #2, #5)
  - [x] Validate Claude Code interactive step execution
  - [x] Validate Codex interactive step execution
  - [x] Validate Nanobot interactive step execution
  - [x] Capture Playwright screenshots for the visible `Live` flows

- [x] Task 3: Record residual risks and operator guidance (AC: #3, #4)
  - [x] Document any intentional limitations by provider
  - [x] Confirm the sprint artifacts and architecture notes reflect the final default runtime model
  - [x] Prepare the epic for closure only if parity criteria are actually met

## Dev Notes

- This story is a parity and trust pass, not a place to sneak in new runtime designs.
- If a provider still lacks parity, record it explicitly instead of masking it with fallback behavior.
- Keep validation on the full MC stack started from the repo root.

### Project Structure Notes

- Likely touch points:
  - `tests/mc/`
  - `tests/cc/`
  - `docs/`
  - `dashboard` Playwright artifacts
  - sprint tracking artifacts

### References

- [Source: docs/ARCHITECTURE.md]
- [Source: docs/plans/2026-03-13-tui-execution-supervision-plan.md]
- [Source: _bmad-output/implementation-artifacts/27-12-bind-live-sessions-to-the-active-step-and-correct-agent.md]
- [Source: _bmad-output/implementation-artifacts/27-16-add-nanobot-interactive-mc-live-support.md]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
