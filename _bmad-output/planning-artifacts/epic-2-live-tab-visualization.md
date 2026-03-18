# Epic 2: Live Tab Visualization

## Epic Goal

Upgrade the `Live` tab from a transient event stream into a durable execution surface that supports active and historical step navigation, canonical provider event translation, and chronological grouped rendering that works for Claude Code now and Codex later.

## Business Value

- Makes long-running executions auditable and easier to debug.
- Preserves the provider semantics needed to build a shared Live surface across providers.
- Reduces operator confusion when a task has multiple completed Live steps or mixed step/task-level sessions.

## Scope

- Canonical Live event contract for persisted activity rows
- Historical Live step/session navigation
- Chronological grouped rendering inside the `Live` tab
- Backward-compatible rendering for legacy activity rows

## Out of Scope

- Replacing the thread tab
- New transport/websocket infrastructure
- Provider-specific Codex UI branch

## Stories

### Story 2.1: Canonical Live Event Contract

As an operator,
I want provider activity rows to preserve canonical Live metadata,
so that the Live surface can classify and group events consistently across providers.

Acceptance Criteria

1. `sessionActivityLog` supports canonical Live metadata fields needed by the UI contract.
2. Claude Code persistence writes `sourceType`, `sourceSubtype`, and a stable `groupKey` when the raw chunk contains enough information.
3. Existing stored rows remain readable without migration.
4. Structural contract docs are updated for the schema/persistence change.

### Story 2.2: Live Step and Session Navigation

As an operator,
I want to switch between active and historical Live steps,
so that I can inspect completed Live runs without losing the default active Live context.

Acceptance Criteria

1. The `Live` tab shows a selector for all active and historical Live choices for the task.
2. The default choice remains the active step/session when one exists.
3. Completed and failed historical step sessions are selectable.
4. Task-level sessions remain accessible for tasks without step-scoped sessions.

### Story 2.3: Chronological Grouped Live Rendering

As an operator,
I want Live output to read like a chronological chat while grouping related events from the same call,
so that I can understand long provider runs more quickly.

Acceptance Criteria

1. Live output remains chronological by timestamp.
2. Consecutive events from the same provider call/group are rendered as one grouped block.
3. Grouped blocks distinguish `system`, `assistant`, `tool`, `result`, and `error` states clearly.
4. Rows without canonical grouping metadata render safely as standalone chronological items.

## Dependencies

- Story 2.1 is foundational.
- Story 2.2 depends on current/historical session selection data, but can proceed once the selector model is agreed.
- Story 2.3 depends on the canonical Live metadata contract and fallback rules from Story 2.1.

## Recommended Execution Order

1. Story 2.1
2. Story 2.2 and Story 2.3 in parallel after Story 2.1 lands
3. Cross-story verification and manual Live smoke test
