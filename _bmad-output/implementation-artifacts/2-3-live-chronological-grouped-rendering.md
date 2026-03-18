# Story 2.3: Chronological Grouped Live Rendering

Status: ready-for-dev

## Story

As an operator,
I want Live output to read like a chronological chat while grouping related events from the same call,
so that I can understand long provider runs more quickly.

## Acceptance Criteria

1. `ProviderLiveChatPanel` renders the Live feed in chronological order by timestamp.
2. Consecutive events with the same `groupKey` render as one grouped visual block.
3. Grouped blocks clearly distinguish `system`, `assistant`, `tool`, `result`, and `error` content.
4. Rows without canonical grouping metadata render as standalone chronological entries.
5. Existing filter affordances continue to work with the new grouped model.

## Tasks / Subtasks

- [ ] Task 1: Expand the shared Live normalizer into a grouped timeline builder (AC: #1, #2, #4)
  - [ ] 1.1 Extend `dashboard/features/interactive/lib/providerLiveEvents.ts` with a grouped chronological view model
  - [ ] 1.2 Preserve backward compatibility for legacy rows with heuristic classification
  - [ ] 1.3 Add tests for grouping, standalone fallbacks, ordering, and canonical source-type precedence

- [ ] Task 2: Adapt the provider session hook and panel to the grouped model (AC: #1, #2, #3, #5)
  - [ ] 2.1 Update `dashboard/features/interactive/hooks/useProviderSession.ts` to expose grouped Live items
  - [ ] 2.2 Update `dashboard/features/interactive/components/ProviderLiveChatPanel.tsx` to render grouped chronological blocks
  - [ ] 2.3 Update `dashboard/features/interactive/components/ProviderLiveEventRow.tsx` or replace it with grouped row primitives as needed

- [ ] Task 3: Verify visual semantics through tests (AC: #2, #3, #4, #5)
  - [ ] 3.1 Extend `dashboard/features/interactive/hooks/useProviderSession.test.ts`
  - [ ] 3.2 Extend `dashboard/features/interactive/components/ProviderLiveChatPanel.test.tsx`
  - [ ] 3.3 Extend `dashboard/features/interactive/components/ProviderLiveEventRow.test.tsx` or the replacement component tests

## Dev Notes

### Why this story exists

The current panel categorizes one event at a time. Operators need chronological readability plus semantic grouping so a provider turn feels like one conversation block rather than scattered cards.

### Expected Files

| File | Change |
|------|--------|
| `dashboard/features/interactive/lib/providerLiveEvents.ts` | Build grouped timeline items |
| `dashboard/features/interactive/lib/providerLiveEvents.test.ts` | Grouping/fallback coverage |
| `dashboard/features/interactive/hooks/useProviderSession.ts` | Expose grouped model |
| `dashboard/features/interactive/hooks/useProviderSession.test.ts` | Hook contract coverage |
| `dashboard/features/interactive/components/ProviderLiveChatPanel.tsx` | Render grouped chronology |
| `dashboard/features/interactive/components/ProviderLiveEventRow.tsx` | Adapt or split row rendering |
| `dashboard/features/interactive/components/ProviderLiveChatPanel.test.tsx` | Panel interaction/rendering coverage |
| `dashboard/features/interactive/components/ProviderLiveEventRow.test.tsx` | Row/group rendering coverage |

### Technical Constraints

- Chronology is the primary axis; grouping is a visual enhancement on top of ordered time.
- The UI must not hide legacy events that lack canonical metadata.
- Keep presentational concerns in components and grouping logic in the pure normalizer layer.

### Testing Guidance

- Follow `agent_docs/running_tests.md`.
- The most important tests are pure grouping tests and panel tests that assert grouped blocks still preserve visible chronology.

### References

- [Source: AGENTS.md]
- [Source: agent_docs/code_conventions/typescript.md]
- [Source: agent_docs/running_tests.md]
- [Source: dashboard/features/interactive/lib/providerLiveEvents.ts]
- [Source: dashboard/features/interactive/hooks/useProviderSession.ts]
- [Source: dashboard/features/interactive/components/ProviderLiveChatPanel.tsx]
- [Source: dashboard/features/interactive/components/ProviderLiveEventRow.tsx]

## Dev Agent Record

### Agent Model Used

TBD

### Debug Log References

### Completion Notes List

### File List
