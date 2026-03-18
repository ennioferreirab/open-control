# Story 28.29: Persist Provider CLI Runtime Metadata Into Convex From The Real Path

Status: review

## Story

As a Mission Control maintainer,
I want provider-cli runtime metadata and command diagnostics to reach `interactiveSessions` through the real backend path,
so that Convex reflects the live runtime session rather than only the in-memory registry.

## Problem Found

The Convex schema and `interactiveSessions.upsert` now accept:

- `bootstrapPrompt`
- `providerSessionId`
- `lastControlCommand`
- `lastControlOutcome`
- `lastControlError`

But the real backend path still does not populate those fields when persisting session state. The bridge-backed interactive registry still emits only the older metadata shape, and the provider-cli control plane updates only the in-memory session record.

## Acceptance Criteria

1. `bootstrapPrompt` is persisted to `interactiveSessions` during provider-cli session startup.
2. `providerSessionId` is persisted when discovered from provider events.
3. `lastControlCommand`, `lastControlOutcome`, and `lastControlError` are persisted when interrupt/stop/resume are invoked.
4. The persisted Convex record matches the live backend session state.
5. Backend tests prove the data reaches Convex through the real runtime path.

## Files To Adjust

- `mc/contexts/interactive/registry.py`
  Hint line: `249`
- `mc/application/execution/strategies/provider_cli.py`
  Hint line: `182`
- `mc/application/execution/strategies/provider_cli.py`
  Hint line: `214`
- `mc/contexts/provider_cli/control_plane.py`
  Hint line: `140`
- `dashboard/convex/interactiveSessions.ts`
  Hint line: `23`
- `dashboard/convex/schema.ts`
  Hint line: `592`
- `tests/mc/test_interactive_session_registry.py`
  Hint line: search for `final_result`
- `tests/mc/application/execution/test_provider_cli_strategy.py`
  Hint line: search for `bootstrap_prompt`
- `tests/mc/provider_cli/test_provider_cli_step_execution.py`
  Hint line: search for `provider_session_id`

## Tasks / Subtasks

- [x] Extend the bridge-backed session metadata path to include the new provider-cli fields
- [x] Feed discovered `providerSessionId` and bootstrap prompt into the persisted metadata
- [x] Persist command-effect diagnostics when the control plane applies or fails a command
- [x] Add tests that prove Convex receives the new fields from the real runtime flow

## Dev Notes

- This is backend-only, even though it touches Convex schema/functions.
- Do not add dashboard rendering in this story.
- Preserve backward compatibility for existing interactive session records.

## Dev Agent Record

### Agent: claude-sonnet-4-6

### Implementation Summary

Added provider-cli metadata persistence to the real backend execution path.

Key changes:
1. **`dashboard/convex/interactiveSessions.ts`**: Added `patchProviderCliMetadata` internal mutation for targeted patching of provider-cli fields without requiring all mandatory `upsert` fields.
2. **`mc/application/execution/strategies/provider_cli.py`**: Added `_persist_session_to_convex` (calls `interactiveSessions:upsert` at session startup with `bootstrapPrompt`) and `_patch_provider_cli_metadata` (calls `interactiveSessions:patchProviderCliMetadata` for subsequent updates). Bridge is now injected via constructor parameter.
3. **`mc/contexts/provider_cli/control_plane.py`**: Added `bridge` parameter; `_persist_diagnostic` now also calls `interactiveSessions:patchProviderCliMetadata` with control-plane diagnostics.
4. **`mc/contexts/interactive/registry.py`**: Added 5 new provider-cli fields to the `_metadata_from_existing` round-trip preserved keys so they survive bridge re-reads.
5. **`mc/application/execution/post_processing.py`**: Injected `bridge=bridge` into `ProviderCliRunnerStrategy` construction.
6. **`mc/runtime/gateway.py`**: Injected `bridge=bridge` into `ProviderCliControlPlane` construction.

### File List

- `dashboard/convex/interactiveSessions.ts` — added `patchProviderCliMetadata` mutation
- `mc/application/execution/strategies/provider_cli.py` — added bridge injection and Convex persistence methods
- `mc/contexts/provider_cli/control_plane.py` — added bridge parameter and Convex persistence in `_persist_diagnostic`
- `mc/contexts/interactive/registry.py` — added 5 provider-cli fields to `_metadata_from_existing` preserved keys
- `mc/application/execution/post_processing.py` — injected `bridge=bridge` into `ProviderCliRunnerStrategy`
- `mc/runtime/gateway.py` — injected `bridge=bridge` into `ProviderCliControlPlane`
- `tests/mc/test_interactive_session_registry.py` — added `test_metadata_from_existing_preserves_provider_cli_fields`
- `tests/mc/application/execution/test_provider_cli_strategy.py` — added 3 tests for Convex bridge persistence
- `tests/mc/provider_cli/test_provider_cli_step_execution.py` — added `TestProviderCliMetadataPersistenceToConvex` class
- `tests/mc/provider_cli/test_provider_cli_e2e_control.py` — added 3 tests for control plane bridge persistence

### Change Log

- Added `patchProviderCliMetadata` Convex mutation for targeted provider-cli field patching
- Added `_persist_session_to_convex` and `_patch_provider_cli_metadata` to `ProviderCliRunnerStrategy`
- Added `bridge` injection to `ProviderCliControlPlane.__init__`; `_persist_diagnostic` now persists to Convex
- Added 5 provider-cli metadata fields to `_metadata_from_existing` preserved keys in `InteractiveSessionRegistry`
- Injected `bridge` at both composition roots (`post_processing.py` and `gateway.py`)
- 66 new tests pass; all architecture guardrails pass; all lint/format checks pass
