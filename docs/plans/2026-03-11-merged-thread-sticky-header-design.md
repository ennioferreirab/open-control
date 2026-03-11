# Merged Thread Sticky Header Design

## Summary

Keep merged source-thread collapses visible at the top of the Thread tab instead of letting them flow downward with the live chat content.

## Decisions

| Decision | Choice |
|----------|--------|
| Placement | Keep merged source threads inside the same `ScrollArea` |
| Behavior | Render them in a `sticky` block pinned to the top of the thread viewport |
| Existing UI | Reuse the current `details` / `summary` collapsible sections |
| Scroll ownership | Live thread messages keep the current bottom sentinel and auto-scroll behavior |
| Data flow | No schema or query changes |

## Architecture

The Thread tab currently renders live messages first and merged source-thread sections after them. The change is purely compositional:

1. Split the scrollable thread body into two visual sections.
2. Move merged source-thread sections into a dedicated container rendered before live messages.
3. Apply `sticky top-0` styling, a solid background, border, spacing, and stacking context so the merged-thread block remains pinned while messages scroll underneath.
4. Leave the bottom sentinel and `isAtBottom` tracking attached to the live-message list so incoming messages still scroll to the end of the current thread instead of interacting with the sticky block.

## Rendering Model

Inside the existing `ScrollArea`:

- `sticky` merged-source container
  - renders only when `mergeSourceThreads.length > 0`
  - contains the existing `details` sections for each source thread
- live thread content container
  - empty-state placeholder when there are no direct messages
  - current task messages
  - bottom sentinel for intersection observer

## Error Handling And UX Notes

- If there are merged source threads but no direct messages, the empty live-thread placeholder still appears below the sticky block.
- Expanded merged-source sections can grow vertically; this is acceptable because the user explicitly asked for the old merged messages to stay pinned at the top.
- The sticky block must use an opaque background and separator so scrolling messages do not visually bleed through it.

## Files Touched

| File | Change |
|------|--------|
| `dashboard/features/tasks/components/TaskDetailSheet.tsx` | Reorder thread-tab rendering and add sticky container styling |
| `dashboard/components/TaskDetailSheet.test.tsx` | Add assertions for sticky merged-source rendering order/structure |
