# Agent Sidebar and Squad Authoring Design

**Date:** 2026-03-15

**Objective:** Expand the Agents sidebar UX while making `Create Agent` and `Create Squad` publish the same canonical global agent contract.

## Goal

Make the Agents area easier to navigate at scale and eliminate the split between agents created directly and agents created through squad authoring. The sidebar should support global text search, collapsible sections, and bounded scrolling. Agent detail should show active squad memberships. Squad authoring should reuse active registered agents when appropriate and persist the same canonical fields as the direct agent flow.

## Approved Scope

- Add a global text filter to the Agents sidebar.
- Search across `Squads`, `Registered`, `System`, and `Remoto`.
- Match agents by `displayName`, `name`, and `@name`.
- Match squads by `displayName` and `name`.
- Make `Registered` collapsible and align all sections to the same collapsible pattern.
- Limit each section to a 10-row visible window with internal scrolling.
- Show only active squads in agent detail.
- Clicking a squad from agent detail opens the squad detail sheet.
- Fix squad-created agents so they persist and display the same canonical agent data as direct agent creation, including `prompt`, `model`, and `soul`.
- Extend squad authoring so it checks active registered agents for reuse candidates before creating new agents.

## Problems in the Current Model

- `AgentSidebar` lists items but has no text filter, so larger registries become hard to scan.
- `Registered` is always expanded while other sections already use collapsible affordances.
- Sections grow unbounded, so long lists push lower sections out of view instead of keeping each section locally scrollable.
- `AgentConfigSheet` does not surface squad membership, so an operator cannot see which active squads reference the selected agent.
- The squad publish path currently creates or reuses agents with an incomplete payload, so agents authored via `Create Squad` can lose canonical fields such as `model`, `prompt`, and `soul`.
- `Create Squad` does not consult active registered agents before inventing new squad members, so it can duplicate capability that already exists globally.

## Core Decisions

### 1. The sidebar uses one global query string, section-local filtering

There is a single search input at the top of the Agents sidebar. Every visible section filters its own list against that query without changing the underlying base ordering. Empty sections remain visible and show a section-specific empty state instead of replacing the entire sidebar with a global empty screen.

### 2. Every sidebar section shares the same bounded-list pattern

`Squads`, `Registered`, `System`, and `Remoto` all adopt the same structure:

- collapsible header
- list body with a 10-item visible window
- internal scroll when the filtered or unfiltered result exceeds that window

This keeps the sidebar stable as the registry grows.

### 3. Agent detail owns the active-squad membership view

When an agent is opened, the agent sheet shows an `Active Squads` section that resolves squad membership from active `squadSpecs` whose `agentIds` include the selected agent. Archived squads are excluded. Each row is clickable and opens the existing squad detail sheet.

### 4. `Create Agent` and `Create Squad` publish the same canonical agent contract

The global `agents` table remains the source of truth. No publish path should create a reduced or squad-only shape. At minimum, the canonical authoring payload must preserve:

- `name`
- `displayName`
- `role`
- `prompt`
- `model`
- `skills`
- `soul`

If a new global agent is created through squad authoring, it must persist this same field set.

### 5. Squad authoring reuses active registered agents through explicit confirmation

During squad authoring, the system should inspect active registered agents and identify likely reuse candidates using:

- similar `role`
- supporting similarity in `prompt`
- supporting similarity in `displayName`
- supporting similarity in `name`

When a candidate exists, the flow asks the user whether to reuse that agent for the proposed squad function. Reuse is never automatic. If the user declines, the flow creates a new canonical global agent with the full authoring payload.

## UX Behavior

### Sidebar Search

- The input lives at the top of the Agents sidebar.
- Search is reactive as the user types.
- Agents match on `displayName`, `name`, and `@name`.
- Squads match on `displayName` and `name`.
- Deleted agents and archived squads are not part of the active search result.

### Sidebar Empty States

- No data for a section: show the existing section-specific empty state.
- No matches for a section under search: show a concise search-specific message.
- No results anywhere: keep all sections visible with their local no-match messages.

### Agent Detail

- Add `Active Squads` below the primary agent metadata.
- Render squad name and optional description.
- Clicking a squad row opens the existing `SquadDetailSheet`.
- When no active squad exists, show a concise empty state.

## Data and Flow Changes

### Sidebar

- Keep section source data in hooks.
- Derive filtered section lists in the sidebar layer or an extracted helper hook.
- Preserve delete-mode selection behavior after filtering.

### Agent Membership

- Add a query or hook that resolves active squads by agent id.
- Use that data in the agent config sheet and keep squad navigation inside the same sidebar/sheet surface.

### Squad Publish

- Extend the squad authoring graph payload so agent entries can carry canonical authoring fields needed by the global registry.
- Update squad graph publish to persist canonical fields when inserting a new global agent.
- When reusing an existing global agent, reference that record instead of creating a duplicate.

### Squad Authoring Reuse Prompt

- The squad authoring assistant receives active registered agents as reuse context.
- For each proposed role, it may present a reuse question before final approval/publish.
- The resulting draft graph must carry either a reference to the chosen existing agent or a complete new-agent payload for creation.

## Risks and Tradeoffs

### Risk: Search and delete mode interaction becomes confusing

Filtering can hide selected items during delete mode. The implementation should either preserve hidden selections explicitly or clear selection when the query changes. The safer choice is to preserve selection state keyed by item identity while making the selected count visible via the existing bulk-delete affordance.

### Risk: Reuse heuristics can suggest the wrong agent

Similarity in `role`, `prompt`, `displayName`, and `name` is intentionally advisory only. User confirmation is required before reuse so the authoring flow does not silently bind the wrong agent into a squad.

### Tradeoff: Squad authoring gains an extra confirmation step

This adds friction, but it is necessary to protect the global registry from duplicated or conflicting agents and to preserve the promise that the app has a single creation flow.

## Recommended Delivery Shape

1. Add story and implementation plan artifacts for this combined sidebar and authoring work.
2. Add failing tests for sidebar filtering, bounded scrolling, and agent-detail squad membership.
3. Implement sidebar search, collapsibles, and section scroll windows.
4. Add active-squad membership loading and navigation in agent detail.
5. Add failing tests for squad-authoring canonical field persistence and reuse decisions.
6. Update squad authoring and publish so new agents carry canonical fields and reuse existing active agents when confirmed.
