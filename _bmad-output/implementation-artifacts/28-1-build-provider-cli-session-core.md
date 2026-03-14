# Story 28.1: Build Provider CLI Session Core

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Mission Control platform maintainer,
I want a provider-agnostic process and session core for live CLI execution,
so that Mission Control can own provider sessions without depending on remote
PTY/xterm browser terminals.

## Acceptance Criteria

1. A new provider CLI session domain exists and includes canonical shared types
   for:
   - process handle
   - provider session snapshot
   - parsed CLI events
2. A new `ProviderCLIParser` abstraction exists and supports:
   - session discovery
   - output parsing
   - interrupt
   - resume
   - stop
   - process-tree inspection
3. A runtime-owned process supervisor can launch provider CLIs, capture `pid`
   and `pgid`, stream `stdout/stderr`, and signal the owning process tree.
4. A provider session registry stores the canonical MC session record including:
   - `mc_session_id`
   - `provider`
   - `provider_session_id`
   - `pid`
   - `pgid`
   - `child_pids`
   - `mode`
   - `status`
   - capability flags
5. A live stream projector emits a normalized stream that can later back both
   chat live share and step live share without depending on PTY transport.
6. Focused tests cover the shared types, parser contract, process supervisor,
   registry transitions, and live stream ordering.
7. Production execution wiring can select this core for interactive step
   execution without routing through `RunnerType.INTERACTIVE_TUI`.

## Success Metrics

- Provider CLI sessions can be launched and registered without any PTY or xterm
  dependency.
- A launched process reports usable `pid` and `pgid` metadata in focused tests.
- Live stream ordering is deterministic in focused tests.
- No new provider session code depends on `interactive_transport.py`.

## Tasks / Subtasks

- [ ] Task 1: Add the provider CLI shared types and parser protocol (AC: #1, #2)
  - [ ] Create canonical dataclasses and capability fields
  - [ ] Define the parser protocol with `start_session`, `parse_output`,
        `discover_session`, `inspect_process_tree`, `interrupt`, `resume`, and
        `stop`
  - [ ] Add focused tests for type shape and protocol contract

- [ ] Task 2: Implement the provider process supervisor (AC: #3)
  - [ ] Launch subprocesses under MC ownership
  - [ ] Capture `pid` and `pgid`
  - [ ] Stream `stdout/stderr` into the parsing pipeline
  - [ ] Add signal helpers for interrupt and terminate semantics
  - [ ] Add focused process lifecycle tests

- [ ] Task 3: Implement the provider session registry (AC: #4)
  - [ ] Create the canonical in-process registry
  - [ ] Record process metadata, discovered session ids, and capability flags
  - [ ] Model state transitions for `starting`, `running`, `interrupting`,
        `human_intervening`, `resuming`, `completed`, `stopped`, and `crashed`
  - [ ] Add focused registry tests

- [ ] Task 4: Implement the live stream projector (AC: #5)
  - [ ] Normalize parsed events into a single ordered live stream
  - [ ] Keep chat and step consumers out of scope for this story
  - [ ] Add focused ordering and projection tests

- [ ] Task 5: Run focused guardrails (AC: #6)
  - [ ] Run provider CLI focused pytest suites
  - [ ] Run Python architecture guardrails
  - [ ] Record residual risks for provider-specific adapters

- [ ] Task 6: Activate the core in runtime selection (AC: #7)
  - [ ] Add or wire the execution runner type used by provider-owned sessions
  - [ ] Update `interactive_mode.py` so supported interactive providers no
        longer resolve to the legacy `INTERACTIVE_TUI` path
  - [ ] Update execution-engine and gateway composition to construct the new
        runtime as a first-class dependency
  - [ ] Add focused tests proving the production path no longer selects the
        tmux-backed runner for cut-over providers

## Dev Notes

- Keep this story strictly at the shared foundation layer.
- Do not wire any browser TUI, xterm, websocket attach flow, or tmux
  dependency into this story.
- Keep new modules aligned with `docs/ARCHITECTURE.md`:
  - shared behavior in `mc/contexts/provider_cli/`
  - runtime process services in `mc/runtime/provider_cli/`
- This story should leave the old interactive stack untouched but clearly
  isolated from the new provider CLI core until the cutover wiring lands.
- The definition of done for this story is stronger than “core modules exist”:
  the active runtime path must be able to select the new core for cut-over
  providers.

### Project Structure Notes

- Likely touch points:
  - `mc/contexts/provider_cli/`
  - `mc/runtime/provider_cli/`
  - `tests/mc/`
- Do not expand:
  - `mc/runtime/interactive_transport.py`
  - browser terminal components
  unless needed only to detach them from step execution selection

### References

- [Source: docs/plans/2026-03-14-provider-cli-parser-design.md]
- [Source: docs/plans/2026-03-14-provider-cli-parser-plan.md]
- [Source: docs/ARCHITECTURE.md]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
