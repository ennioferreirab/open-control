# Story 28.3: Add Codex Provider CLI Parser

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Mission Control operator,
I want Codex sessions to run through the same provider CLI parser contract as
Claude,
so that live share and intervention stay provider-agnostic.

## Acceptance Criteria

1. A Codex provider parser exists under the new provider CLI providers package.
2. The parser can discover the Codex provider session id through provider
   output or metadata without browser TUI coupling.
3. Codex live output is normalized into shared parsed CLI events.
4. Codex declares and implements provider-native `resume` support through the
   shared parser API.
5. Codex interrupt and stop behaviors are exposed through the shared
   intervention contract.
6. Focused tests cover session discovery, normalized output parsing, and
   capability wiring for Codex.

## Success Metrics

- Codex parser tests prove the provider can be driven through the same generic
  session contract as Claude.
- No Codex live-share path depends on the remote TUI transport.

## Tasks / Subtasks

- [ ] Task 1: Build the Codex parser (AC: #1, #2, #3)
  - [ ] Create the parser module
  - [ ] Discover session identity from provider output or metadata
  - [ ] Normalize live output into shared event shapes
  - [ ] Add focused parser tests

- [ ] Task 2: Wire Codex into the shared provider CLI core (AC: #3, #4, #5)
  - [ ] Adapt the current Codex interactive launch path to use the new parser
        and process supervisor
  - [ ] Route resume and interrupt through the generic abstraction
  - [ ] Keep any provider-specific escape hatches inside the parser boundary

- [ ] Task 3: Run focused guardrails (AC: #6)
  - [ ] Run Codex provider CLI focused tests
  - [ ] Run Python architecture guardrails
  - [ ] Record remaining provider-specific gaps explicitly

## Dev Notes

- Match the shared provider CLI contract first; do not let Codex become a
  special-case runtime path.
- If Codex session discovery requires auxiliary metadata, keep that detail
  behind the parser.

### Project Structure Notes

- Likely touch points:
  - `mc/contexts/provider_cli/providers/codex.py`
  - `mc/contexts/interactive/adapters/codex.py`
  - `tests/mc/`

### References

- [Source: docs/plans/2026-03-14-provider-cli-parser-design.md]
- [Source: docs/plans/2026-03-14-provider-cli-parser-plan.md]
- [Source: mc/contexts/interactive/adapters/codex.py]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
