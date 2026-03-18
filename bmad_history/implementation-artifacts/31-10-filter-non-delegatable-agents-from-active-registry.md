# Story 31.10: Filter Non-Delegatable Agents from Active Registry

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want the active registry view to expose only delegatable agents,
so that lead-agent routing cannot pick runtime-only surfaces such as remote
terminals.

## Overall Objective

Tighten the delegatability contract behind `agents:listActiveRegistryView` so it
matches the actual set of agents that may receive normal task delegation.

## Acceptance Criteria

1. `agents:listActiveRegistryView` excludes remote-terminal agents even when
   they are enabled and not marked as system.
2. The registry filtering rule is based on delegatability semantics, not only
   `isSystem` or soft-delete flags.
3. The Python bridge returns the filtered delegatable roster unchanged.
4. Delegatable agents still expose role, skills, squads, metrics, and
   `lastActiveAt`.
5. Focused tests prove non-delegatable runtime surfaces cannot appear in the
   registry.

## Files To Change

- `dashboard/convex/agents.ts`
- `dashboard/convex/agents.test.ts`
- `dashboard/convex/terminalSessions.ts`
- `mc/bridge/repositories/agents.py`
- `mc/bridge/facade_mixins.py`

## Tasks / Subtasks

- [ ] Task 1: Define delegatable-agent filtering rules
  - [ ] 1.1 Exclude remote-terminal agents from the registry
  - [ ] 1.2 Centralize the delegatable-agent predicate
  - [ ] 1.3 Preserve current registry shape for valid agents

- [ ] Task 2: Keep bridge consumers aligned
  - [ ] 2.1 Confirm Python bridge reads the filtered set
  - [ ] 2.2 Avoid introducing hidden fallback candidates in Python
  - [ ] 2.3 Keep dashboard and runtime using the same registry truth

- [ ] Task 3: Add regression coverage
  - [ ] 3.1 Prove terminal-session agents stay out of the registry
  - [ ] 3.2 Prove valid agents remain visible
  - [ ] 3.3 Prove returned shape still includes metrics and squads

## Dev Notes

- Prefer one delegatability rule that can evolve with future runtime-only agent
  roles.
- Do not solve this by marking remote terminals as system-only unless that is
  already the intended product contract.

## References

- [Source: review findings on March 17, 2026]
- [Source: `31-2-add-active-agent-registry-view-and-metrics-fields.md`]

