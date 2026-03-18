# Story 6.3: Implement HITL Notification Badges

Status: done

## Story

As a **user**,
I want to see notification badges when tasks need my attention,
So that I can spot approval requests at a glance without scanning every card.

## Acceptance Criteria

1. **Given** tasks exist in "review" state with trust level "human_approved" awaiting user action, **When** the dashboard renders, **Then** the Review column header shows an amber badge with the count of tasks needing human approval (FR34)
2. **Given** the badge is displayed, **Then** it has an amber glow pulse animation once when the count increments
3. **Given** the user approves or denies a task, **When** the action is processed, **Then** the badge count decrements immediately (optimistic UI)
4. **Given** the badge count reaches zero, **Then** the badge is hidden
5. **Given** a new task enters HITL review while the dashboard is open, **When** the reactive query updates, **Then** the badge count increments and pulses once
6. **And** badge logic is added to `KanbanColumn.tsx` header
7. **And** the badge only counts tasks requiring human action, not tasks in agent-only review
8. **And** Vitest tests exist for the badge rendering and count logic

## Tasks / Subtasks

- [ ] Task 1: Add HITL count query to Convex (AC: #1, #7)
  - [ ] 1.1: Add a `countHitlPending` query to `dashboard/convex/tasks.ts`
  - [ ] 1.2: The query returns the count of tasks where `status === "review"` AND `trustLevel === "human_approved"`
  - [ ] 1.3: Use the `by_status` index to efficiently filter review tasks, then filter by trustLevel in the handler

- [ ] Task 2: Update KanbanColumn with badge support (AC: #1, #2, #3, #4, #6)
  - [ ] 2.1: Update `dashboard/components/KanbanColumn.tsx` (or wherever column headers are rendered)
  - [ ] 2.2: Accept an optional `hitlCount` prop (number)
  - [ ] 2.3: When `hitlCount > 0`, render an amber Badge next to the column title with the count
  - [ ] 2.4: Badge styling: `bg-amber-500 text-white text-xs rounded-full px-1.5 min-w-[20px] text-center`
  - [ ] 2.5: Add a one-time pulse animation when count changes (CSS `animate-pulse` for one cycle, or Framer Motion `animate={{ scale: [1, 1.2, 1] }}` with `duration: 0.3`)

- [ ] Task 3: Wire badge count in KanbanBoard (AC: #1, #3, #5)
  - [ ] 3.1: In the KanbanBoard component, use `useQuery(api.tasks.countHitlPending)` to get the HITL count
  - [ ] 3.2: Pass the count to the Review column's `KanbanColumn` component
  - [ ] 3.3: The count auto-updates via Convex reactive queries when tasks enter/leave HITL review

- [ ] Task 4: Implement pulse animation (AC: #2, #5)
  - [ ] 4.1: Track previous count with `useRef` to detect increments
  - [ ] 4.2: When count increases, add a CSS class `animate-pulse-once` that pulses amber glow for 600ms
  - [ ] 4.3: Define the animation in Tailwind config or use inline Framer Motion
  - [ ] 4.4: Respect `prefers-reduced-motion` — skip animation if reduced motion is preferred

- [ ] Task 5: Write Vitest tests (AC: #8)
  - [ ] 5.1: Test badge renders with correct count when HITL tasks exist
  - [ ] 5.2: Test badge is hidden when count is 0
  - [ ] 5.3: Test badge only counts human_approved tasks, not agent_reviewed
  - [ ] 5.4: Test badge count matches the number of qualifying tasks

## Dev Notes

### Critical Architecture Requirements

- **Badge only counts human-actionable tasks**: The badge counts tasks where the USER needs to act — `status === "review"` AND `trustLevel === "human_approved"`. Tasks in agent-only review (`trustLevel === "agent_reviewed"`) do NOT count.
- **Reactive query handles updates**: The `countHitlPending` query is reactive. When a task enters or leaves HITL review (via approve, deny, or new task arrival), the count updates automatically.
- **Optimistic UI**: When the user approves or denies a task (Stories 6.1, 6.2), the badge count decrements immediately via optimistic updates on the approval/denial mutations.

### Badge Count Query Pattern

```typescript
export const countHitlPending = query({
  args: {},
  handler: async (ctx) => {
    const reviewTasks = await ctx.db
      .query("tasks")
      .withIndex("by_status", (q) => q.eq("status", "review"))
      .collect();
    return reviewTasks.filter((t) => t.trustLevel === "human_approved").length;
  },
});
```

### Column Header Badge Pattern

```tsx
// In KanbanColumn header:
<div className="flex items-center gap-2">
  <h2 className="text-lg font-semibold">{columnName}</h2>
  <span className="text-xs text-slate-400">({taskCount})</span>
  {hitlCount > 0 && (
    <span
      className={`bg-amber-500 text-white text-xs font-medium rounded-full
        px-1.5 min-w-[20px] text-center ${isPulsing ? "animate-pulse" : ""}`}
    >
      {hitlCount}
    </span>
  )}
</div>
```

### Pulse Animation Pattern

```tsx
// Track previous count to detect increments
const prevCountRef = useRef(hitlCount);
const [isPulsing, setIsPulsing] = useState(false);

useEffect(() => {
  if (hitlCount > prevCountRef.current) {
    setIsPulsing(true);
    const timer = setTimeout(() => setIsPulsing(false), 600);
    return () => clearTimeout(timer);
  }
  prevCountRef.current = hitlCount;
}, [hitlCount]);
```

### Custom Pulse Animation (Tailwind)

Add to `tailwind.config.ts`:

```typescript
// In the extend.animation section:
animation: {
  "pulse-once": "pulse-once 0.6s ease-in-out",
},
keyframes: {
  "pulse-once": {
    "0%, 100%": { transform: "scale(1)", boxShadow: "0 0 0 0 rgba(245, 158, 11, 0)" },
    "50%": { transform: "scale(1.15)", boxShadow: "0 0 8px 2px rgba(245, 158, 11, 0.4)" },
  },
},
```

Alternatively, use Framer Motion for the pulse:

```tsx
<motion.span
  key={hitlCount} // Re-trigger animation when count changes
  initial={{ scale: 1 }}
  animate={{ scale: [1, 1.15, 1] }}
  transition={{ duration: 0.3 }}
>
  {hitlCount}
</motion.span>
```

### Common LLM Developer Mistakes to Avoid

1. **DO NOT count agent-reviewed tasks** — Only `trustLevel === "human_approved"` tasks count toward the badge. Tasks with "agent_reviewed" are handled by agents, not the user.

2. **DO NOT use polling for badge count** — Use `useQuery(api.tasks.countHitlPending)` which is reactive. Convex handles real-time updates.

3. **DO NOT show badge on all columns** — The badge only appears on the Review column header. No badges on other columns.

4. **DO NOT make the pulse animation continuous** — The pulse should fire once when the count increments, not loop continuously. Continuous pulsing would violate the "calm signals" UX principle.

5. **DO NOT forget `prefers-reduced-motion`** — Skip the pulse animation if the user has reduced motion enabled.

6. **DO NOT forget to handle the zero state** — When count is 0, the badge should be completely hidden, not show "0".

### What This Story Does NOT Include

- **Approve/Deny functionality** — Already implemented in Stories 6.1 and 6.2
- **Sound or browser notifications** — The UX spec explicitly says no sound
- **Badges on other columns** — Only the Review column gets a badge for MVP

### Files Created in This Story

| File | Purpose |
|------|---------|
| (none -- extends existing files) | |

### Files Modified in This Story

| File | Changes |
|------|---------|
| `dashboard/convex/tasks.ts` | Add `countHitlPending` query |
| `dashboard/components/KanbanColumn.tsx` | Add hitlCount prop and amber badge rendering |
| `dashboard/components/KanbanBoard.tsx` | Wire HITL count query to Review column |
| `dashboard/components/KanbanColumn.test.tsx` | Add tests for badge rendering |

### Verification Steps

1. Create 2 tasks with `trustLevel: "human_approved"` in review — verify badge shows "2"
2. Approve one task — verify badge decrements to "1"
3. Approve the second — verify badge disappears
4. Create an agent_reviewed task in review — verify badge does NOT count it
5. Add a new human_approved task to review — verify badge appears with pulse
6. Run `cd dashboard && npx vitest run` — tests pass

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 6.3`] — Original story definition
- [Source: `_bmad-output/planning-artifacts/prd.md#FR34`] — Notification indicator for HITL requests
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#UX Consistency Patterns`] — Badge-based attention pattern, amber glow pulse
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#Desired Emotional Response`] — Calm signals, not alarms
- [Source: `dashboard/components/KanbanBoard.tsx`] — Existing board to wire count
- [Source: `dashboard/components/KanbanColumn.tsx`] — Existing column to add badge

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References
- Fixed pre-existing KanbanBoard.test.tsx mock (missing useMutation) broken by Story 6.1 additions to TaskCard
- TypeScript: 0 errors, Vitest: 11/11 tests pass (5 new + 6 existing)

### Completion Notes List
- Task 1: Added `countHitlPending` query to `dashboard/convex/tasks.ts` using `by_status` index, filters by `trustLevel === "human_approved"`
- Task 2: Updated `KanbanColumn.tsx` with optional `hitlCount` prop, amber badge with data-testid, pulse-once animation class
- Task 3: Wired `useQuery(api.tasks.countHitlPending)` in `KanbanBoard.tsx`, passed to Review column only
- Task 4: Added `pulse-once` keyframes and animation to `tailwind.config.ts` with amber glow; respects `prefers-reduced-motion`
- Task 5: Created `KanbanColumn.test.tsx` with 5 tests covering badge rendering, zero/missing count hiding, count correctness, and amber styling

### File List
- `dashboard/convex/tasks.ts` — Added `countHitlPending` query
- `dashboard/components/KanbanColumn.tsx` — Added `hitlCount` prop, amber badge, pulse animation with reduced-motion support
- `dashboard/components/KanbanBoard.tsx` — Wired HITL count query, passed to Review column
- `dashboard/tailwind.config.ts` — Added `pulse-once` animation and keyframes
- `dashboard/components/KanbanColumn.test.tsx` — New: 5 Vitest tests for badge rendering
- `dashboard/components/KanbanBoard.test.tsx` — Fixed: added `useMutation` to convex/react mock
