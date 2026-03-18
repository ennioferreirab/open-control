# Story 8.4: Implement Agent Activation Status

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to activate or deactivate agents from the dashboard agent panel,
so that I can control which agents receive and execute tasks without removing their configuration.

## Acceptance Criteria

1. **Given** an agent exists in the Convex `agents` table, **when** the agent is created or synced from YAML, **then** the agent has an `enabled` field defaulting to `true`.

2. **Given** an agent is enabled (`enabled: true`), **when** the dashboard renders the AgentSidebarItem, **then** the status dot shows the current runtime status colors: blue+glow (active/working), gray (idle/connected but not working), red+glow (crashed).

3. **Given** an agent is disabled (`enabled: false`), **when** the dashboard renders the AgentSidebarItem, **then** the status dot shows solid red (no glow) regardless of the runtime status, and the agent name/role text is dimmed (`text-muted-foreground`).

4. **Given** the user opens the AgentConfigSheet for any agent, **when** the sheet renders, **then** a prominent toggle switch (ShadCN `Switch`) labeled "Active" / "Deactivated" is displayed at the top of the config form, above the Name field.

5. **Given** the user toggles the switch from Active to Deactivated, **when** the user clicks Save, **then** the agent's `enabled` field is set to `false` via the `agents.setEnabled` mutation, the status dot turns solid red, and an `agent_deactivated` activity event is logged. The toggle previews the change locally before save.

6. **Given** the user toggles the switch from Deactivated to Active, **when** the user clicks Save, **then** the agent's `enabled` field is set to `true` via the `agents.setEnabled` mutation, the status dot returns to the runtime status color, and an `agent_activated` activity event is logged. The toggle previews the change locally before save.

7. **Given** an agent is disabled, **when** the Lead Agent orchestrator evaluates task routing, **then** the disabled agent is excluded from capability matching and is never assigned new tasks.

8. **Given** an agent is disabled, **when** the TaskInput agent selector renders, **then** the disabled agent appears in the dropdown but is grayed out and non-selectable, with a "(Deactivated)" suffix.

9. **Given** an agent is disabled while it has an in-progress task, **when** the agent is deactivated, **then** the currently running task continues to completion (no interruption), but no NEW tasks are assigned to the agent after the current one finishes.

10. **Given** the sidebar is in collapsed mode (64px), **when** a disabled agent's avatar is shown, **then** the status dot overlay shows solid red (matching the expanded view), and the tooltip shows "Deactivated" as the status.

## Tasks / Subtasks

- [x] Task 1: Add `enabled` field to Convex schema and agent mutations (AC: #1, #5, #6)
  - [x]1.1: Add `enabled: v.optional(v.boolean())` to `agents` table in `convex/schema.ts` (defaults to `true` via mutation logic for backward compatibility)
  - [x]1.2: Add `agent_activated` and `agent_deactivated` to activity event type union in `convex/schema.ts` and `lib/constants.ts`
  - [x]1.3: Add `setEnabled` mutation to `convex/agents.ts` — accepts `agentName: string, enabled: boolean`, patches the agent, logs activity event
  - [x]1.4: Update `upsertByName` mutation in `convex/agents.ts` to preserve existing `enabled` value on update (don't reset to `true` on re-sync), and default to `true` for new agents
  - [x]1.5: Update `list` query to include `enabled` field in results

- [x] Task 2: Update AgentSidebarItem to show disabled state (AC: #2, #3, #10)
  - [x]2.1: Update status dot logic: if `enabled === false` → solid red (`bg-red-500`, no glow/shadow); else use existing runtime status colors
  - [x]2.2: Dim agent name and role text when `enabled === false` — add `text-muted-foreground opacity-60` class
  - [x]2.3: Update tooltip to show "Deactivated" when `enabled === false`, otherwise show runtime status
  - [x]2.4: Update collapsed mode avatar to show red dot overlay when disabled

- [x] Task 3: Add enable/disable toggle to AgentConfigSheet (AC: #4, #5, #6)
  - [x]3.1: Add ShadCN `Switch` component at the top of the form (above Name field) with label "Active" / "Deactivated" that reflects current `enabled` state
  - [x]3.2: On toggle, call `setEnabled` mutation immediately (not part of the Save flow — instant effect)
  - [x]3.3: Update status dot in sheet header to reflect disabled state (solid red when disabled)
  - [x]3.4: When disabled, show a subtle info banner below the toggle: "This agent will not receive new tasks"

- [x] Task 4: Update orchestrator to skip disabled agents (AC: #7, #9)
  - [x]4.1: Update Python `orchestrator.py` capability matching to filter out agents where `enabled === false` before routing
  - [x]4.2: Update Python bridge `list_agents()` to include `enabled` field in returned data
  - [x]4.3: Update Python `AgentData` dataclass in `types.py` to include `enabled: bool = True` field
  - [x]4.4: Ensure currently-running tasks are NOT interrupted when an agent is disabled mid-execution

- [x]Task 5: Update TaskInput agent selector (AC: #8)
  - [x]5.1: In `TaskInput.tsx` agent selector dropdown, show disabled agents as grayed-out with "(Deactivated)" suffix
  - [x]5.2: Make disabled agents non-selectable in the dropdown (disabled option)

## Dev Notes

### Architecture Patterns and Constraints

- **Separate `enabled` from `status`**: The `enabled` field is a user-controlled configuration flag (persistent). The `status` field remains a runtime state (active/idle/crashed) managed by the gateway. These are independent concerns — an agent can be `enabled: false, status: "idle"` (deactivated by user) or `enabled: true, status: "crashed"` (enabled but crashed at runtime).
- **Backward compatibility**: The `enabled` field is `v.optional(v.boolean())` in the schema. All existing agents without the field are treated as enabled (`enabled !== false` check pattern). The `upsertByName` mutation preserves existing `enabled` value on updates.
- **Toggle is part of Save flow**: The enable/disable toggle in AgentConfigSheet updates local form state on click and previews the change. The mutation only fires when the user clicks Save, consistent with the form's Save/Cancel flow. This prevents accidental activation/deactivation.
- **No task interruption**: Disabling an agent does NOT cancel or reassign in-progress tasks. The agent finishes its current work, but the orchestrator won't assign new tasks to it. This prevents data loss and mid-execution corruption.
- **Activity logging**: Every enable/disable toggle writes an activity event, following the architectural rule that all state transitions must be logged.
- **Convex mutation + activity event**: Per architecture enforcement rule, the `setEnabled` mutation MUST also write a corresponding activity event in the same transaction.

### Source Tree Components to Touch

| File | Action |
| ---- | ------ |
| `convex/schema.ts` | Add `enabled` field to agents table, add `agent_activated` / `agent_deactivated` to event type union |
| `convex/agents.ts` | Add `setEnabled` mutation, update `upsertByName` to preserve `enabled` |
| `lib/constants.ts` | Add `AGENT_ACTIVATED` and `AGENT_DEACTIVATED` to `ACTIVITY_EVENT_TYPE` |
| `components/AgentSidebarItem.tsx` | Update status dot logic + dimmed text for disabled agents |
| `components/AgentSidebarItem.test.tsx` | Add tests for disabled state rendering |
| `components/AgentConfigSheet.tsx` | Add Switch toggle at top of form |
| `components/AgentConfigSheet.test.tsx` | Add tests for toggle behavior |
| `components/TaskInput.tsx` | Gray out disabled agents in selector dropdown |
| `components/TaskInput.test.tsx` | Add test for disabled agents in selector |
| `nanobot/mc/types.py` | Add `enabled: bool = True` to `AgentData` |
| `nanobot/mc/bridge.py` | Include `enabled` in agent data mapping |
| `nanobot/mc/orchestrator.py` | Filter out disabled agents in capability matching |

### Testing Standards

- Vitest for all dashboard component tests
- Test AgentSidebarItem renders solid red dot when `enabled === false`
- Test AgentSidebarItem renders dimmed text when disabled
- Test AgentConfigSheet toggle calls `setEnabled` mutation
- Test AgentConfigSheet toggle shows correct label ("Active" / "Deactivated")
- Test TaskInput selector shows disabled agents as grayed out and non-selectable
- Python: test orchestrator skips disabled agents during routing

### Existing Patterns to Follow

- **Switch component**: ShadCN `Switch` — already installed, follow pattern from existing UI components
- **Optimistic UI**: Follow pattern from TaskCard approve/deny — immediate visual update before server confirms
- **Activity event logging**: Follow `updateConfig` mutation pattern in `agents.ts` (mutation + activity event in same handler)
- **Status dot styling**: Follow existing `AgentSidebarItem.tsx` status dot pattern (conditional `cn()` classes)
- **Agent selector**: Follow existing `TaskInput.tsx` agent dropdown pattern with `Select` component
- **Inline info banner**: Use subtle `text-xs text-muted-foreground` pattern consistent with other info text in the app

### Project Structure Notes

- All dashboard components in `dashboard/components/`
- Convex functions in `dashboard/convex/`
- Constants in `dashboard/lib/constants.ts`
- Python MC modules in `nanobot/mc/`
- Component tests co-located next to components

### Visual Status Reference

| State | Dot Color | Glow | Text Style | Tooltip Status |
|-------|-----------|------|------------|----------------|
| Active (working) | Blue (`bg-blue-500`) | Yes (blue glow) | Normal | "active" |
| Idle (connected) | Gray (`bg-muted-foreground`) | No | Normal | "idle" |
| Crashed | Red (`bg-red-500`) | Yes (red glow) | Normal | "crashed" |
| **Deactivated** | **Red (`bg-red-500`)** | **No** | **Dimmed (`opacity-60`)** | **"Deactivated"** |

### Distinguishing Disabled from Crashed

Both disabled and crashed use red, but they are visually distinct:
- **Crashed**: Red with glow ring (`shadow-[0_0_6px_rgba(239,68,68,0.5)]`) + normal text opacity
- **Deactivated**: Solid red without glow + dimmed text + "Deactivated" tooltip

### Implementation Sequence

Task 1 (backend schema + mutations) must complete before Tasks 2-5 (frontend). Tasks 2, 3, and 5 can be developed in parallel. Task 4 (Python orchestrator) is independent from frontend tasks and can run in parallel.

### References

- [Source: convex/schema.ts] Agents table definition with status union type
- [Source: convex/agents.ts] Agent mutations (upsertByName, updateStatus, updateConfig, deactivateExcept)
- [Source: components/AgentSidebarItem.tsx] Status dot color logic and collapsed mode layout
- [Source: components/AgentConfigSheet.tsx] Agent config form with Switch, validation, save flow
- [Source: components/TaskInput.tsx] Agent selector dropdown in progressive disclosure panel
- [Source: lib/constants.ts] AGENT_STATUS and ACTIVITY_EVENT_TYPE constants
- [Source: nanobot/mc/types.py] AgentData dataclass and AgentStatus enum
- [Source: nanobot/mc/orchestrator.py] Capability matching and task routing logic
- [Source: nanobot/mc/bridge.py] Agent data mapping and Convex communication
- [Source: architecture.md#Agent-Status-Values] Defined values: "active" | "idle" | "crashed"

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (team: backend-dev + frontend-dev + team-lead)

### Debug Log References

- Fixed DashboardLayout.test.tsx worker hang (279s → 5.9s) by mocking child components
- Changed vitest pool from forks to threads for faster teardown

### Completion Notes List

- Task 1: Added `enabled: v.optional(v.boolean())` to agents schema, `setEnabled` mutation, `agent_activated`/`agent_deactivated` event types
- Task 2: AgentSidebarItem shows solid red dot (no glow) + dimmed text when disabled, distinguishing from crashed (red + glow)
- Task 3: AgentConfigSheet has Switch toggle at top of form — toggle is part of Save flow (not instant), previews change locally before persist
- Task 4: Python orchestrator filters disabled agents before capability matching (`a.enabled is not False` for backward compat)
- Task 5: TaskInput selector shows disabled agents grayed-out with "(Deactivated)" suffix, non-selectable
- Bonus: Fixed vitest performance issue — DashboardLayout.test.tsx was hanging due to unmocked child component timers

### File List

- `dashboard/convex/schema.ts` — Added `enabled` field to agents table, added activity event types
- `dashboard/convex/agents.ts` — Added `setEnabled` mutation, updated `upsertByName` to preserve `enabled`
- `dashboard/lib/constants.ts` — Added `AGENT_ACTIVATED`, `AGENT_DEACTIVATED` constants
- `dashboard/components/AgentSidebarItem.tsx` — Disabled state: red dot, dimmed text, tooltip
- `dashboard/components/AgentSidebarItem.test.tsx` — 8 new tests for disabled state
- `dashboard/components/AgentConfigSheet.tsx` — Switch toggle (part of Save flow), info banner
- `dashboard/components/AgentConfigSheet.test.tsx` — 9 new/updated tests for toggle behavior
- `dashboard/components/TaskInput.tsx` — Grayed-out disabled agents in selector
- `dashboard/components/TaskInput.test.tsx` — 2 new tests for disabled agents
- `dashboard/components/DashboardLayout.test.tsx` — Rewritten with mocked child components (perf fix)
- `dashboard/vitest.config.ts` — Changed pool to threads, added teardownTimeout
- `nanobot/mc/types.py` — Added `enabled: bool = True` to AgentData, new activity event types
- `nanobot/mc/orchestrator.py` — Filter disabled agents before capability matching

### Code Review Record (2026-02-23)

**Reviewer:** Claude Opus 4.6 (adversarial code review)
**Issues Found:** 2 High, 2 Medium, 1 Low
**Issues Fixed:**
- [H1] AgentConfigSheet: setEnabled error handling — already inside try/catch, no code change needed
- [M1] AgentConfigSheet: System agent Switch now disabled for lead-agent/mc-agent with "System agents cannot be deactivated" text
- [L1] constants.ts: Added missing AGENT_DELETED constant
**Deferred:**
- [M2] Schema `enabled` field as optional — backward-compatible pattern consistent with project conventions, no change
