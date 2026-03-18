# Story 27.4: Generalize Interactive Adapter Contract and Add Codex Adapter

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Mission Control platform maintainer,
I want the interactive runtime to support pluggable provider adapters and a
second real adapter beyond Claude Code,
so that the new TUI capability becomes a reusable platform surface rather than
another one-off integration.

## Acceptance Criteria

1. The interactive runtime exposes a provider adapter contract that covers:
   - launch command
   - environment/bootstrap
   - capabilities
   - health checks
   - shutdown semantics
2. The Claude Code interactive adapter conforms to that contract without
   requiring Chat UI or transport changes.
3. A Codex interactive adapter is added on the same runtime and can be opened
   in the same `TUI` chat surface.
4. Agent configuration/read models can express whether an agent supports the
   interactive TUI and which provider adapter it should use.
5. Adding a second adapter does not require changes to the browser terminal
   renderer or socket transport.
6. Non-interactive agents and headless-only agents continue to behave exactly as
   before.

## Success Metrics

- Codex support lands with no terminal-renderer changes
- Adding the Codex adapter requires changes only in adapter/config/capability
  wiring layers plus targeted tests
- Chat UI logic remains provider-agnostic after Claude and Codex both work

## Tasks / Subtasks

- [ ] Task 1: Formalize the interactive provider adapter interface (AC: #1, #2)
  - [ ] Define adapter capabilities and lifecycle hooks
  - [ ] Update Claude interactive integration to conform to the new contract
  - [ ] Add tests that block provider-specific UI branching

- [ ] Task 2: Add Codex interactive adapter support (AC: #3, #5)
  - [ ] Implement a Codex launch adapter over the same session runtime
  - [ ] Wire workspace/bootstrap inputs required by Codex
  - [ ] Add focused launch and reconnect tests

- [ ] Task 3: Expose interactive capabilities through configuration/read models (AC: #3, #4, #6)
  - [ ] Add or extend agent config/read-model fields for interactive capability
  - [ ] Keep headless and interactive config concerns distinct
  - [ ] Update dashboard capability detection for the Chat TUI tab

- [ ] Task 4: Run focused regression and compatibility verification (AC: #5, #6)
  - [ ] Re-run Claude interactive tests after Codex support lands
  - [ ] Re-run non-interactive chat regression coverage
  - [ ] Record proof that transport and terminal UI stayed untouched

## Dev Notes

- This story exists specifically to prevent a Claude-only special case from
  leaking into transport, UI, or session identity design.
- Prefer a narrow adapter contract with explicit capabilities over a large
  inheritance tree.
- Keep provider-specific details out of the browser terminal layer.

### Project Structure Notes

- Likely touch points:
  - `mc/contexts/interactive/`
  - `mc/infrastructure/interactive/`
  - agent configuration/read-model layers in backend and dashboard
  - `dashboard/features/interactive/`
- Keep the browser terminal feature provider-agnostic.

### References

- [Source: vendor/claude-code/claude_code/workspace.py]
- [Source: dashboard/components/ChatPanel.tsx]
- [Source: docs/ARCHITECTURE.md]
- [Source: _bmad-output/implementation-artifacts/cc-1-agent-config-backend-extension.md]
- [Source: _bmad-output/implementation-artifacts/11-3-cc-backend-config-dashboard.md]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
