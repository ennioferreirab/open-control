# Story 27.16: Add Nanobot Interactive MC Live Support

Status: done

## Story

As a Mission Control operator,
I want Nanobot agents running on the `mc` channel to expose a `Live` session too,
so that the same live-execution model works across Claude Code, Codex, and Nanobot.

## Acceptance Criteria

1. The interactive provider contract supports a Nanobot-backed interactive runtime for `mc` channel execution.
2. Nanobot interactive sessions can be created as backend-owned step sessions and attached through the task-detail `Live` surface.
3. Nanobot `Live` sessions support basic terminal interaction and visible execution ownership, even if the Nanobot TUI is simpler than Claude/Codex.
4. Nanobot interactive step execution follows the same step-scoped ownership rules as other providers: correct agent, active step, task thread integration, and no hidden fallback.
5. Existing remote terminal bridge sessions remain separate from this new step-owned interactive runtime.
6. Focused tests and browser validation cover at least one Nanobot-backed `Live` step flow.

## Success Metrics

- Nanobot agents can be marked interactive and run through the same backend-owned `Live` flow in covered tests
- Task-detail `Live` attaches to a Nanobot step session without using the legacy remote-terminal bridge
- No covered Nanobot interactive path relies on a hidden Claude/Codex-specific assumption

## Tasks / Subtasks

- [x] Task 1: Extend the interactive provider contract for Nanobot (AC: #1, #4, #5)
  - [x] Add Nanobot as a supported interactive provider where configuration/validation requires it
  - [x] Implement a Nanobot interactive adapter for `mc` channel execution
  - [x] Add focused backend tests for Nanobot adapter startup and session metadata

- [x] Task 2: Wire Nanobot into step execution and `Live` attach (AC: #2, #3, #4)
  - [x] Ensure step execution can choose Nanobot interactive runtime intentionally
  - [x] Surface Nanobot sessions in task-detail `Live` like other step-scoped providers
  - [x] Add focused dashboard/backend tests for attach and identity

- [x] Task 3: Validate Nanobot `Live` end-to-end (AC: #3, #6)
  - [x] Run a real Nanobot interactive step flow through the full MC stack
  - [x] Confirm thread/activity expectations still hold
  - [x] Capture Playwright screenshots of the Nanobot `Live` flow

## Dev Notes

- This is not the legacy remote terminal bridge.
- Keep Nanobot step execution on the `mc` channel contractually aligned with the interactive runtime instead of special-casing through old terminal polling.
- Prefer a thin adapter over duplicating agent-loop ownership.

### Project Structure Notes

- Likely touch points:
  - `mc/contexts/interactive/`
  - `mc/application/execution/`
  - `vendor/nanobot/`
  - `dashboard/features/interactive/`
  - `tests/mc/`

### References

- [Source: vendor/nanobot/nanobot/agent/loop.py]
- [Source: vendor/nanobot/nanobot/channels/mission_control.py]
- [Source: mc/contexts/interactive/types.py]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
