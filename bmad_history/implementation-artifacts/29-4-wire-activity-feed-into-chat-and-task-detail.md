# Story 29.4: Wire Activity Feed into Chat and Task Detail

Status: ready-for-dev

## Story

As a Mission Control operator,
I want the agent activity feed to appear in both the chat panel and the task
detail sheet,
so that I can monitor agents from any context without opening a terminal.

## Acceptance Criteria

1. `ChatPanel` renders `AgentActivityFeed` as a companion panel when an active
   interactive session exists
2. `TaskDetailSheet` renders `AgentActivityFeed` in place of (or alongside)
   `InteractiveTerminalPanel` for step live share
3. The same `AgentActivityFeed` component is reused in both contexts
4. The `InteractiveTerminalPanel` import in `TaskDetailSheet` is marked deprecated
   with a clear TODO
5. Focused tests verify the feed appears in both contexts

## Tasks / Subtasks

- [ ] Task 1: Wire `AgentActivityFeed` into `ChatPanel`
- [ ] Task 2: Wire `AgentActivityFeed` into `TaskDetailSheet`
- [ ] Task 3: Add focused integration tests
- [ ] Task 4: Update `docs/ARCHITECTURE.md` to document
      `dashboard/features/interactive`

## Dev Notes

- The chat panel already has `InteractiveChatTabs` which passes through
  `chatView`. The `AgentActivityFeed` should appear alongside the chat, not
  replace it. Consider a split layout or a tab.
- For `TaskDetailSheet`, replace the `InteractiveTerminalPanel` usage with
  `AgentActivityFeed` when the session exists.
- Keep `InteractiveTerminalPanel` available as a deprecated fallback but not
  as the default path.

### References

- [Source: docs/plans/2026-03-14-agent-activity-feed-design.md]
- [Source: dashboard/features/interactive/components/InteractiveChatTabs.tsx]
- [Source: dashboard/features/tasks/components/TaskDetailSheet.tsx]
