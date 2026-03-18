# Story 27.5: Harden Interactive Session Observability, Security, and Reuse

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Mission Control operator,
I want interactive TUI sessions to be observable, secure, and reusable,
so that the feature can graduate from a chat-only POC into a durable platform
capability.

## Acceptance Criteria

1. Interactive session lifecycle events are visible to operators, including:
   - created
   - attached
   - detached
   - reattached
   - terminated
   - crashed
2. Socket attach requests are authorized and scoped so that a browser cannot
   attach to arbitrary interactive sessions by guessing ids.
3. Idle timeout and cleanup behavior are documented, implemented, and tested.
4. Session metadata is reusable by other future surfaces without forcing a new
   provider process when a compatible live session already exists.
5. Full-stack verification covers:
   - supported startup path via `nanobot mc start`
   - browser validation via `playwright-cli`
   - focused backend and dashboard regression tests
6. Existing remote terminal agents and headless execution flows remain
   unaffected.

## Success Metrics

- Unauthorized attach attempts fail in 100% of negative tests
- Normal shutdown cleans up live interactive sessions in >= 90% of validation runs
- Reattach after transient disconnect succeeds in >= 95% of local validation runs
- Operators can inspect lifecycle state without opening the terminal itself

## Tasks / Subtasks

- [ ] Task 1: Add lifecycle observability (AC: #1, #4)
  - [ ] Emit interactive session activities and logs for major lifecycle events
  - [ ] Expose enough metadata for later surface reuse
  - [ ] Add focused tests for lifecycle event emission

- [ ] Task 2: Add attach authorization and safety checks (AC: #2, #6)
  - [ ] Gate socket attach requests by runtime-issued session metadata
  - [ ] Reject stale, unknown, or unauthorized attach attempts
  - [ ] Add negative tests for attach and reconnect safety

- [ ] Task 3: Add cleanup and idle-timeout handling (AC: #3, #4)
  - [ ] Implement idle timeout policy and cleanup behavior
  - [ ] Prevent duplicate provider launches when a reusable live session exists
  - [ ] Add tests for normal shutdown and orphan recovery

- [ ] Task 4: Run the feature exit gate (AC: #5, #6)
  - [ ] Validate on the full MC stack, not a frontend-only server
  - [ ] Run `playwright-cli` validation for the browser experience
  - [ ] Run relevant Python and dashboard guardrails
  - [ ] Record residual risks and follow-up opportunities

## Dev Notes

- This story should harden the interactive runtime without pushing new UI
  surfaces into scope.
- Reuse means lifecycle compatibility first; a second UI surface can ship later
  on top of the same metadata contract.
- Keep remote-terminal ownership and headless execution ownership untouched.

### Project Structure Notes

- Likely touch points:
  - `mc/contexts/interactive/`
  - `mc/runtime/`
  - `dashboard/features/interactive/`
  - activity/logging or session metadata read models
- Validation must use the full-stack startup path from the repo root.

### References

- [Source: docs/ARCHITECTURE.md]
- [Source: terminal_bridge.py]
- [Source: dashboard/convex/terminalSessions.ts]
- [Source: mc/runtime/gateway.py]
- [Source: _bmad-output/implementation-artifacts/tech-spec-convex-security-hardening.md]
- [Source: AGENTS.md]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
