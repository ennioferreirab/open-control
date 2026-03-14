# Story 28.4: Add Nanobot Runtime-Owned Provider Parser

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Mission Control platform maintainer,
I want Nanobot to participate in the provider CLI session model through a
runtime-owned parser mode,
so that the abstraction supports both provider-native resume and MC-owned
session continuity.

## Acceptance Criteria

1. A Nanobot provider parser exists and declares `runtime-owned` session mode.
2. Nanobot session continuity uses the existing internal `session_key` model
   rather than pretending to have a provider-native external resume id.
3. Nanobot interrupt behavior maps to session cancellation and related loop
   controls where available.
4. Subagent or child-process/session metadata is surfaced into the canonical
   provider session registry when available.
5. Focused tests cover runtime-owned mode, session continuity, interrupt
   mapping, and subagent/session enrichment.

## Success Metrics

- Nanobot participates in the same high-level intervention and live-share flow
  without faking a native provider session id model.
- Focused tests prove the generic contract supports both provider-native and
  runtime-owned session semantics.

## Tasks / Subtasks

- [ ] Task 1: Build the Nanobot parser in runtime-owned mode (AC: #1, #2)
  - [ ] Create the parser module
  - [ ] Model Nanobot session continuity through `session_key`
  - [ ] Distinguish runtime-owned mode explicitly in the shared snapshot
  - [ ] Add focused parser tests

- [ ] Task 2: Wire Nanobot interrupt and enrichment behavior (AC: #3, #4)
  - [ ] Map interrupt to session cancellation logic
  - [ ] Surface available subagent or child-process metadata into the session
        registry
  - [ ] Keep Nanobot-specific details behind the parser boundary

- [ ] Task 3: Run focused guardrails (AC: #5)
  - [ ] Run Nanobot provider CLI focused tests
  - [ ] Run Python architecture guardrails
  - [ ] Record runtime-owned follow-ups explicitly

## Dev Notes

- Reuse the current Nanobot `session_key` ownership instead of bolting on a
  fake external resume contract.
- This story is the proof that `ProviderCLIParser` is truly generic.

### Project Structure Notes

- Likely touch points:
  - `mc/contexts/provider_cli/providers/nanobot.py`
  - `mc/contexts/interactive/adapters/nanobot.py`
  - `mc/runtime/nanobot_interactive_session.py`
  - `vendor/nanobot/nanobot/agent/`
  - `tests/mc/`

### References

- [Source: docs/plans/2026-03-14-provider-cli-parser-design.md]
- [Source: docs/plans/2026-03-14-provider-cli-parser-plan.md]
- [Source: mc/runtime/nanobot_interactive_session.py]
- [Source: vendor/nanobot/nanobot/agent/loop.py]
- [Source: vendor/nanobot/nanobot/agent/subagent.py]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
