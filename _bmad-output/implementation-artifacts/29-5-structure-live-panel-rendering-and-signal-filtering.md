# Story 29.5: Structure Live Panel Rendering and Signal Filtering

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Mission Control operator,
I want the `Live` panel to render provider events with structured presentation and filter them by signal category,
so that I can understand tools, skills, text, actions, and results without reading raw plain-text output.

## Acceptance Criteria

1. `ProviderLiveChatPanel` no longer renders every event as raw `<pre>` text and instead uses a structured event row renderer.
2. The live event renderer supports the current persisted session activity shape, including `kind`, `summary`, `error`, `toolName`, `toolInput`, `filePath`, and `requiresAction`.
3. Live events are classified into stable visual categories for filtering, covering at least `text`, `tool`, `skill`, `result`, `action`, `error`, and `system`.
4. The `Live` panel exposes local category filtering without affecting the thread tab or the `AgentActivityFeed` column.
5. Events with richer content render correctly using the existing markdown-capable rendering approach already used elsewhere in the dashboard rather than plain text only.
6. Focused tests cover event classification, hook normalization, live event row rendering, and category filtering behavior.
7. The implementation preserves the existing two-column task-detail `Live` layout and does not require backend schema changes.

## Tasks / Subtasks

- [ ] Task 1: Add a structured Live event taxonomy and normalization layer
  - [ ] Create a pure utility to classify raw activity entries into UI categories
  - [ ] Build a structured `ProviderLiveEvent` view-model from `sessionActivityLog` entries
  - [ ] Update `useProviderSession` to return structured events instead of flat text-only events
- [ ] Task 2: Add a dedicated structured renderer for Live events
  - [ ] Create a reusable `ProviderLiveEventRow` component
  - [ ] Reuse markdown-capable rendering for event bodies where appropriate
  - [ ] Render tool/action/error/result/system states with kind-appropriate visuals
- [ ] Task 3: Add local category filtering to the Live panel
  - [ ] Add multi-select category controls inside `ProviderLiveChatPanel`
  - [ ] Filter only the left `Live` stream column
  - [ ] Keep `AgentActivityFeed` unchanged
- [ ] Task 4: Run focused validation for the dashboard change
  - [ ] Run targeted Vitest coverage for the new taxonomy, hook, row renderer, and panel
  - [ ] Run touched-file format and lint checks
  - [ ] Run `npm run test:architecture`
  - [ ] Validate the flow in the full MC runtime with `playwright-cli`

## Dev Notes

- Keep the backend contract unchanged in this story. Use `sessionActivityLog` as the source of truth.
- Do not force `Live` events into the `messages` schema. Reuse rendering primitives and markdown behavior, not fake message records.
- `skill` may require a heuristic based on `toolName`; centralize that logic in one tested helper.
- Keep ownership inside `dashboard/features/interactive/` except for any minimal call-site typing updates needed in task detail.
- Follow TDD strictly: failing test first, verify failure, minimal implementation, verify pass.

### Project Structure Notes

- Primary touch points:
  - `dashboard/features/interactive/lib/`
  - `dashboard/features/interactive/hooks/`
  - `dashboard/features/interactive/components/`
  - `dashboard/features/tasks/components/TaskDetailSheet.tsx` only if integration typing needs adjustment
- Do not add direct `convex/react` calls in new presentational components.

### References

- [Source: /Users/ennio/Documents/nanobot-ennio/docs/plans/2026-03-15-live-panel-structured-rendering-design.md]
- [Source: /Users/ennio/Documents/nanobot-ennio/docs/plans/2026-03-15-live-panel-structured-rendering-implementation-plan.md]
- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/features/interactive/components/ProviderLiveChatPanel.tsx]
- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/features/interactive/hooks/useProviderSession.ts]
- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/features/thread/components/ThreadMessage.tsx]
- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/convex/sessionActivityLog.ts]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
