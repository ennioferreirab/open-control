# Story 29.3: Build Agent Activity Feed Component

Status: ready-for-dev

## Story

As a Mission Control operator,
I want a structured activity feed that shows what agents are doing in real time,
so that I can monitor tool calls, file edits, and session status without a
terminal emulator.

## Acceptance Criteria

1. An `AgentActivityFeed` component exists that renders session events
   reactively from Convex
2. Events render with kind-appropriate styling: tool calls show name + input,
   errors show in red, turn_completed shows summary highlighted
3. Fallback text renders when metadata fields are missing (e.g., no toolName)
4. A session header shows provider, agent name, and status
5. Auto-scroll to bottom with scroll-away detection
6. Footer has Interrupt and Stop buttons (wired to existing takeover hook)
7. `approval_requested` events render as informational status (no inline
   buttons in Phase 1)
8. Focused component tests cover all event kinds and empty states

## Tasks / Subtasks

- [ ] Task 1: Create `useAgentActivity` hook
      (`dashboard/features/interactive/hooks/useAgentActivity.ts`)
- [ ] Task 2: Create `AgentActivityFeed` component
      (`dashboard/features/interactive/components/AgentActivityFeed.tsx`)
- [ ] Task 3: Add focused tests
      (`dashboard/features/interactive/components/AgentActivityFeed.test.tsx`)

## Dev Notes

- Use Tailwind for styling. Match the project's dark theme (zinc palette).
- Use `useInteractiveTakeoverControls` for Interrupt/Stop — do not build new
  intervention mutations.
- Event rendering should use a mapping object (kind → render config) for
  maintainability.
- Collapsible tool input detail (click to expand) is nice-to-have but not
  required for Phase 1.
- Do NOT import from `convex/react` directly — use the `useAgentActivity` hook.

### References

- [Source: docs/plans/2026-03-14-agent-activity-feed-design.md]
