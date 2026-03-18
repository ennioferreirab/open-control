# Story 28.6: Add Human Intervention and Resume Controls

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Mission Control operator,
I want to interrupt a live provider iteration and send the next message in
resume mode,
so that I can intervene in a running step or chat session without relying on a
browser terminal takeover flow.

## Acceptance Criteria

1. A human intervention controller exists and supports:
   - interrupt current iteration
   - enter human intervention state
   - resume the same session with the next human message
   - stop the session explicitly
2. The provider session registry models and persists intervention state
   transitions for:
   - `running`
   - `interrupting`
   - `human_intervening`
   - `resuming`
3. The live chat UI exposes intervention actions through explicit controls
   rather than terminal keyboard capture semantics.
4. The next human message after a successful interrupt is routed through the
   provider parser `resume` path when the provider supports it.
5. Focused tests cover state transitions, action wiring, and resume routing.
6. Manual `Done` completes only the active step and still requires a canonical
   final result on the provider-owned session record.

## Success Metrics

- Human intervention works from the live chat surface without any remote TUI
  dependency.
- Focused tests prove the next message after intervention goes through resume
  semantics when supported.
- Stop behavior remains explicit and separate from interrupt.

## Tasks / Subtasks

- [ ] Task 1: Build the human intervention controller (AC: #1, #2)
  - [ ] Create the orchestration layer over the registry, process supervisor,
        and provider parser
  - [ ] Model the intervention state transitions explicitly
  - [ ] Add focused controller tests

- [ ] Task 2: Expose intervention controls in the live chat UI (AC: #3, #4)
  - [ ] Add `Interrupt`, `Resume`, and `Stop` controls to the unified live chat
        surface
  - [ ] Route the next human message through provider resume semantics
  - [ ] Preserve explicit manual `Done` for the active step only
  - [ ] Add focused UI wiring tests

- [ ] Task 3: Run focused guardrails (AC: #5)
  - [ ] Run provider intervention and UI tests
  - [ ] Run Python and dashboard guardrails for touched files
  - [ ] Record unsupported-provider behavior explicitly

## Dev Notes

- Keep interrupt and stop semantics distinct.
- Do not fall back to terminal key injection for intervention controls.
- Capability differences across providers should be explicit in the UI and
  registry rather than hidden behind best-effort behavior.
- This story owns intervention on the new provider runtime. It must not depend
  on browser-terminal takeover or legacy TUI keyboard capture.

### Project Structure Notes

- Likely touch points:
  - `mc/runtime/provider_cli/intervention.py`
  - `mc/contexts/provider_cli/registry.py`
  - `dashboard/features/interactive/components/`
  - `dashboard/features/interactive/hooks/`
  - `tests/mc/`

### References

- [Source: docs/plans/2026-03-14-provider-cli-parser-design.md]
- [Source: docs/plans/2026-03-14-provider-cli-parser-plan.md]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
