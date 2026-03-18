# Story 2.1: Canonical Live Event Contract and Storage

Status: ready-for-dev

## Story

As an operator,
I want provider activity rows to preserve canonical Live metadata,
so that the Live surface can classify and group events consistently across providers.

## Acceptance Criteria

1. `dashboard/convex/schema.ts` and `dashboard/convex/sessionActivityLog.ts` support canonical Live metadata fields required by the `Live` UI contract.
2. `mc/application/execution/strategies/provider_cli.py` writes the canonical fields when persisting provider CLI activity rows.
3. `mc/contexts/provider_cli/providers/claude_code.py` maps Claude chunks into stable `sourceType`, `sourceSubtype`, and `groupKey` metadata whenever the raw chunk exposes enough information.
4. Historical rows that do not contain the new fields continue to render through a safe fallback path.
5. Structural contract docs are updated in the same change set.

## Tasks / Subtasks

- [ ] Task 1: Extend the persisted Live schema (AC: #1, #4)
  - [ ] 1.1 Add optional `sourceType`, `sourceSubtype`, `groupKey`, `rawText`, and `rawJson` to `dashboard/convex/schema.ts`
  - [ ] 1.2 Update `dashboard/convex/sessionActivityLog.ts` args and insert payload to persist the new fields
  - [ ] 1.3 Extend `dashboard/convex/sessionActivityLog.test.ts` for the new optional fields and truncation behavior

- [ ] Task 2: Emit canonical metadata from provider CLI persistence (AC: #2, #3)
  - [ ] 2.1 Enrich `ParsedCliEvent` handling in `mc/contexts/provider_cli/providers/claude_code.py` so Claude system/assistant/result chunks expose canonical metadata
  - [ ] 2.2 Update `mc/application/execution/strategies/provider_cli.py` to persist canonical metadata alongside legacy summary/tool fields
  - [ ] 2.3 Keep backward compatibility for existing `kind`, `summary`, `tool_input`, and error handling paths

- [ ] Task 3: Lock fallback semantics in the shared Live normalizer (AC: #4)
  - [ ] 3.1 Add regression coverage in `dashboard/features/interactive/lib/providerLiveEvents.test.ts` for rows with and without canonical metadata
  - [ ] 3.2 Ensure the shared normalizer prefers canonical metadata before heuristic classification

- [ ] Task 4: Update structural docs (AC: #5)
  - [ ] 4.1 Update `agent_docs/database_schema.md` with new `sessionActivityLog` fields
  - [ ] 4.2 Update `agent_docs/service_communication_patterns.md` with the provider-to-Live canonical translation path

## Dev Notes

### Why this story exists

The current Live UI can only infer meaning from flattened `summary` and `toolInput` data. That is not a stable contract for future Codex support. This story creates the storage contract that later UI stories consume.

### Expected Files

| File | Change |
|------|--------|
| `dashboard/convex/schema.ts` | Add optional canonical Live metadata fields to `sessionActivityLog` |
| `dashboard/convex/sessionActivityLog.ts` | Persist canonical metadata |
| `dashboard/convex/sessionActivityLog.test.ts` | Cover new fields |
| `mc/contexts/provider_cli/providers/claude_code.py` | Extract canonical metadata from Claude stream chunks |
| `mc/application/execution/strategies/provider_cli.py` | Write canonical metadata into the bridge mutation |
| `dashboard/features/interactive/lib/providerLiveEvents.test.ts` | Regression coverage for canonical-vs-legacy rows |
| `agent_docs/database_schema.md` | Structural contract update |
| `agent_docs/service_communication_patterns.md` | Structural contract update |

### Technical Constraints

- Use snake_case in Python and camelCase in Convex/TypeScript per cross-service naming.
- Do not remove legacy `summary`, `toolInput`, or `kind` fields; the UI still needs backward compatibility.
- Fail explicitly when parsing cannot determine a canonical value; fallback belongs in the UI normalizer, not silent backend mutation of meaning.

### Testing Guidance

- Follow `agent_docs/running_tests.md`: test real behavior and boundary contracts, skip mock-mirror tests.
- The highest-value tests are the Convex append mutation contract and the Live normalizer fallback behavior.

### References

- [Source: AGENTS.md]
- [Source: agent_docs/database_schema.md]
- [Source: agent_docs/service_communication_patterns.md]
- [Source: agent_docs/code_conventions/cross_service_naming.md]
- [Source: dashboard/convex/sessionActivityLog.ts]
- [Source: dashboard/features/interactive/lib/providerLiveEvents.ts]
- [Source: mc/application/execution/strategies/provider_cli.py]
- [Source: mc/contexts/provider_cli/providers/claude_code.py]

## Dev Agent Record

### Agent Model Used

TBD

### Debug Log References

### Completion Notes List

### File List
