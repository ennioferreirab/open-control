# Live Tab Visualization Design

## Summary

Improve the task `Live` tab so it works as a durable execution timeline instead of a transient stream. The design introduces a canonical Live event contract that can be reused by Claude Code and Codex providers, exposes step/session navigation for active and historical Live data, and renders output chronologically while visually grouping items that belong to the same provider call.

## Problem

The current `Live` tab has three gaps:

1. Historical Live sessions exist in storage but are not first-class in the tab UX.
2. The frontend receives flattened `sessionActivityLog` entries, which drops useful provider semantics such as `system`, `assistant`, and `result`.
3. The Live renderer categorizes single events but does not group related events from the same provider call, making long runs hard to scan.

## Goals

- Preserve a provider-agnostic Live contract that Mission Control can reuse for Claude Code now and Codex later.
- Keep the default Live target on the currently active step, while allowing explicit navigation to completed/failed historical Live steps.
- Render Live output in chronological order like a chat transcript, but visually grouped when events belong to the same provider call.
- Preserve backward compatibility for previously stored `sessionActivityLog` rows.

## Non-Goals

- No new runtime transport layer.
- No redesign of the thread tab.
- No provider-specific UI branch for Codex in this phase.
- No worktree or implementation in this planning package.

## Current State

- `mc/application/execution/strategies/provider_cli.py` appends flattened activity rows to `sessionActivityLog`.
- `dashboard/convex/sessionActivityLog.ts` stores the flattened payload.
- `dashboard/features/interactive/lib/providerLiveEvents.ts` normalizes those rows into the current `ProviderLiveEvent` view model.
- `dashboard/features/interactive/hooks/useTaskInteractiveSession.ts` can resolve active and historical sessions, but the `Live` tab has no explicit session selector.

## Proposed Architecture

### 1. Canonical Live Contract

Treat the existing `providerLiveEvents.ts` normalizer as the seed of the shared Live translation layer, but enrich the stored activity payload first so the frontend is not forced to infer everything from `summary`.

Add canonical event metadata to `sessionActivityLog`:

- `sourceType`: stable source family such as `system`, `assistant`, `tool`, `result`, `error`
- `sourceSubtype`: provider-specific subtype such as Claude `init`, `hook_response`, `success`
- `groupKey`: stable correlation key for events that belong to the same provider call/turn
- `rawText`: canonical human-readable payload
- `rawJson`: optional serialized structured payload for future fallback/debug rendering

The backend should populate these fields where it has strong knowledge, especially in Claude Code parsing and provider CLI activity persistence. Codex can later emit the same canonical fields without changing the Live UI contract.

### 2. Step / Session Navigation

Expose a Live session selector above the `Live` timeline. It should:

- default to the currently active step session
- include historical ended/error sessions for steps that have persisted Live data
- include task-level sessions when a task has no step-scoped session
- show status and identity hints so users know what they are opening

The selector should prefer current sessions first, then historical sessions by most recent `updatedAt`.

### 3. Chronological Grouped Rendering

Render the Live feed in ascending timestamp order, preserving chat-like chronology. Introduce a grouped row model where consecutive events with the same `groupKey` are presented as a single visual block.

Within a group:

- `system` appears first
- `assistant` content follows
- `tool` details can appear inline or as sub-panels
- `result` appears last

If metadata is missing, fall back to single-event chronological rendering instead of hiding data.

### 4. Compatibility Strategy

Old rows remain readable:

- missing `sourceType` falls back to heuristics based on `kind`, `toolName`, and existing payload fields
- missing `groupKey` renders as a standalone event
- existing category filters keep working through a compatibility mapping

## Data Flow

1. Provider emits raw chunk/event.
2. Parser/persistence layer maps it into canonical Live metadata and appends `sessionActivityLog`.
3. `useProviderSession` reads session rows.
4. `providerLiveEvents.ts` normalizes rows into grouped chronological view data.
5. `ProviderLiveChatPanel` renders the selector filters and grouped timeline.

## Testing Strategy

- Convex unit tests for `sessionActivityLog` schema/persistence changes.
- TypeScript unit tests for Live event normalization, grouping, and fallbacks.
- Hook tests for active vs historical session selection.
- Component tests for the Live selector and grouped chronological rendering in `TaskDetailSheet` / `ProviderLiveChatPanel`.

## Risks

- Schema changes on `sessionActivityLog` affect a structural contract; planning must include contract doc updates.
- Provider metadata may be incomplete for some historical runs, so fallback behavior must be explicit and tested.
- Story parallelism should avoid overlapping write ownership around `TaskDetailSheet.tsx`.

## Planned Deliverables

- Design doc
- Implementation plan
- BMAD epic file
- Story files for implementation
- Wave plan coordinating story execution
