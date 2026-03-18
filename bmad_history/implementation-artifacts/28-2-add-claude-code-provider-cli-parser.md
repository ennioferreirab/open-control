# Story 28.2: Add Claude Code Provider CLI Parser

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Mission Control operator,
I want Claude Code sessions to run through the generic provider CLI parser
contract,
so that Claude live share, interruption, and resume work without a remote TUI.

## Acceptance Criteria

1. A Claude Code provider parser exists under the new provider CLI contract.
2. The parser can discover the Claude provider session id from structured output
   and/or official hook or MCP-side signals without scraping a browser TUI.
3. Claude live output is normalized into provider CLI events suitable for the
   shared live stream projector.
4. Claude declares and implements provider-native `resume` support through the
   new abstraction.
5. Claude interrupt behavior is exposed through the generic intervention
   contract and does not require websocket terminal takeover.
6. Focused tests cover session discovery, normalized output parsing,
   capability declaration, and interrupt/resume wiring.
7. Claude step execution in production uses the provider CLI runtime instead of
   the tmux-backed `InteractiveTuiRunnerStrategy`.
8. Claude startup still begins execution immediately from the backend-owned
   session using the task prompt, rather than waiting at an idle CLI prompt.

## Success Metrics

- Claude parser tests discover a provider session id deterministically.
- Claude live output reaches normalized events without any PTY/browser
  dependency.
- Interrupt and resume behavior are available through the shared parser API.

## Tasks / Subtasks

- [ ] Task 1: Build the Claude Code parser (AC: #1, #2, #3)
  - [ ] Create a Claude-specific parser under the new provider CLI providers
        package
  - [ ] Discover the provider session id from structured signals
  - [ ] Normalize output into parsed CLI events
  - [ ] Add focused parser tests

- [ ] Task 2: Wire Claude Code into the shared provider CLI core (AC: #3, #4, #5)
  - [ ] Adapt the existing Claude interactive launch path to use the new
        parser and process supervisor
  - [ ] Route resume through provider-native session semantics
  - [ ] Route interrupt through the shared intervention contract
  - [ ] Keep existing hook/MCP enrichments as secondary signals, not transport
  - [ ] Replace the Claude step runtime path so production no longer routes
        Claude through `RunnerType.INTERACTIVE_TUI`
  - [ ] Preserve automatic startup execution using the step task prompt

- [ ] Task 3: Run focused guardrails (AC: #6)
  - [ ] Run Claude provider CLI focused tests
  - [ ] Run focused execution-strategy tests proving Claude no longer uses the
        legacy runner
  - [ ] Run Python architecture guardrails
  - [ ] Record any Claude-specific follow-ups that should remain out of this
        story

## Dev Notes

- Reuse the existing Claude hook and MCP knowledge where it helps session
  discovery and lifecycle mapping.
- Do not reintroduce any browser terminal semantics in this story.
- Keep Claude-specific behavior inside the parser or adapter boundary.
- This story is the first real tmux-removal milestone. It is not complete if
  the new parser exists but real Claude step execution still routes through the
  legacy coordinator/runtime.

### Project Structure Notes

- Likely touch points:
  - `mc/contexts/provider_cli/providers/claude_code.py`
  - `mc/contexts/interactive/adapters/claude_code.py`
  - `tests/mc/`
  - `tests/cc/` if hook-side coverage is needed

### References

- [Source: docs/plans/2026-03-14-provider-cli-parser-design.md]
- [Source: docs/plans/2026-03-14-provider-cli-parser-plan.md]
- [Source: mc/contexts/interactive/adapters/claude_code.py]
- [Source: vendor/claude-code/]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
