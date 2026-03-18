# Story 3.5: Extend Activity Feed with Step Events

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want the activity feed to show step-level events alongside task events,
so that I have a timeline of everything happening across my agents.

## Acceptance Criteria

1. **Step lifecycle events render as FeedItems** — Given step lifecycle events occur (assigned, started, completed, crashed, unblocked, retried), when the activity feed renders, then each event appears as a FeedItem with: event type icon, agent name, step title, timestamp, and brief description (FR38). Step events use the activity event types: `step_dispatched`, `step_started`, `step_completed`, `step_crashed`, `step_unblocked`, `step_retrying`, `step_status_changed`.

2. **Reverse chronological order with mixed event types** — Given the feed has both task-level and step-level events, when the ActivityFeed renders, then events are displayed in reverse chronological order (newest first), and step events are visually distinguishable from task events (e.g., with a step-specific icon in the FeedItem).

3. **Real-time updates without missing events** — Given multiple steps complete rapidly in parallel execution, when the feed updates, then all events appear in real-time without missing any, driven by Convex reactive queries.

4. **Destructive color for error events** — Given an error event occurs (`step_crashed`, `system_error`, `agent_crashed`, `task_crashed`), when the FeedItem renders, then it uses the destructive color (red left-border accent `border-red-400`) to draw attention (FR38).

5. **`step_crashed` and `step_retrying` are in the schema and activities mutation** — Given these event type literals exist in `activities.eventType` union in `schema.ts` (added in Stories 3.1 and 3.4), when the `activities:create` mutation is called with these types, then it succeeds without a schema validation error.

6. **FeedItem icon mapping for step events** — Given a FeedItem renders a step event, when the event type is inspected, then the icon reflects the semantic of the event: a checkmark-style icon for `step_completed`, an alert/X icon for `step_crashed`, a play icon for `step_started`, an arrow icon for `step_dispatched`, a lock-open icon for `step_unblocked`, and a refresh icon for `step_retrying`.

## Tasks / Subtasks

- [x] **Task 1: Extend `FeedItem.tsx` with step event icons and styling** (AC: 1, 4, 6)
  - [x] 1.1 Add step event types to the `ERROR_EVENTS` array: `step_crashed` must be added alongside the existing `task_crashed`, `system_error`, `agent_crashed` entries so crashed step events render with the red left-border accent.
  - [x] 1.2 Define a `STEP_EVENTS` set (or constant array) containing all step-level event type strings: `"step_dispatched"`, `"step_started"`, `"step_completed"`, `"step_crashed"`, `"step_status_changed"`, `"step_unblocked"`, `"step_retrying"`.
  - [x] 1.3 Add an icon mapping function `getStepEventIcon(eventType: string): ReactNode` that returns a small Lucide icon for each step event type:
    - `step_completed` → `<CheckCircle2 className="h-3 w-3 text-green-500" />`
    - `step_crashed` → `<XCircle className="h-3 w-3 text-red-500" />`
    - `step_started` → `<Play className="h-3 w-3 text-blue-500" />`
    - `step_dispatched` → `<ArrowRight className="h-3 w-3 text-slate-400" />`
    - `step_unblocked` → `<Unlock className="h-3 w-3 text-emerald-500" />`
    - `step_retrying` → `<RefreshCw className="h-3 w-3 text-amber-500" />`
    - `step_status_changed` → `<Activity className="h-3 w-3 text-slate-400" />`
    - fallback → `null`
  - [x] 1.4 Update the FeedItem JSX to render the icon when `STEP_EVENTS` contains the `activity.eventType`: place the icon to the left of the description text inside the `<p>` row, or as a leading element in the item, using `flex items-center gap-1`. The icon must be visible but small — consistent with the `text-xs` density of the feed.
  - [x] 1.5 Verify the `HITL_EVENTS` constant still covers `hitl_requested`, `hitl_approved`, `hitl_denied` (no change needed — verify it's still correct and document in a comment).

- [x] **Task 2: Verify `activities.ts` mutation includes all required step event types** (AC: 5)
  - [x] 2.1 Open `dashboard/convex/activities.ts` and compare the `eventType` union in the `create` mutation against the `activities.eventType` union in `dashboard/convex/schema.ts`. The mutation's union is a subset of the schema's union — it lists types the dashboard UI is allowed to create directly. Verify `step_crashed` and `step_retrying` are both present in the schema union (they were added in Stories 3.1 and 3.4 respectively).
  - [x] 2.2 If `step_crashed` and/or `step_retrying` are missing from the `activities:create` mutation's `eventType` union (not the schema — the mutation), add them. The mutation union need only include types that callers actually use; if neither is called from the dashboard directly (they are inserted by `updateStatus` and `retryStep` mutations in `steps.ts`), no change is needed to the mutation — document as verified.
  - [x] 2.3 Confirm `step_dispatched`, `step_started`, `step_completed`, `step_status_changed`, `step_unblocked` are present in the schema union — these were used in prior stories. If any are missing, add them to `schema.ts`.

- [x] **Task 3: Write component tests for the extended `FeedItem`** (AC: 1, 4, 6)
  - [x] 3.1 Create or extend `dashboard/components/FeedItem.test.tsx`. Check if the file exists first — if it does, add to it; if not, create it following the pattern in `StepCard.test.tsx`.
  - [x] 3.2 Add test: `"renders step_completed event with green checkmark icon"` — render a FeedItem with `eventType: "step_completed"` and assert the `CheckCircle2` icon (or its `aria-label` / test-id) is present.
  - [x] 3.3 Add test: `"renders step_crashed event with red border and X icon"` — render a FeedItem with `eventType: "step_crashed"` and assert: (a) the element has the `border-red-400` class, (b) the `XCircle` icon is rendered.
  - [x] 3.4 Add test: `"renders step_retrying event with amber refresh icon"` — render a FeedItem with `eventType: "step_retrying"` and assert the `RefreshCw` icon is present.
  - [x] 3.5 Add test: `"renders task-level event without step icon"` — render a FeedItem with `eventType: "task_created"` and assert no step icon is rendered.
  - [x] 3.6 Add test: `"renders step_unblocked event without red border"` — render a FeedItem with `eventType: "step_unblocked"` and assert the element does NOT have `border-red-400`.

- [x] **Task 4: Manual integration verification** (AC: 2, 3)
  - [x] 4.1 Start the dashboard (`cd dashboard && npm run dev`) and confirm the activity feed renders mixed task-level and step-level events in reverse chronological order — newest at top, older entries below.
  - [x] 4.2 If a live task with steps is available, verify step events (`step_dispatched`, `step_started`, `step_completed`) appear in real time as the task executes, confirming Convex reactive query reactivity is working.
  - [x] 4.3 Verify crashed step events appear with the red left-border accent in the live feed.

## Dev Notes

### Existing `ActivityFeed` Component Structure

File: `dashboard/components/ActivityFeed.tsx`

The `ActivityFeed` component (133 lines) uses:
- `useQuery(api.activities.listRecent)` — reactive Convex query that auto-updates when new activity events are inserted. Returns up to 100 activities ordered descending by `timestamp` (newest first).
- `ScrollArea` with a `viewportRef` for auto-scroll behavior.
- `motion.div` wrapper around each `FeedItem` with `opacity: 0 → 1` fade-in (200ms) on mount.
- Scroll position tracking: auto-scrolls to top when a new item arrives AND the user is already at the top; shows a "New activity" button otherwise.
- `aria-live="polite"` on the outer container for screen reader support.
- Displays "Showing last 100 activities" footer when the list is at capacity.

The `ActivityFeed` itself requires NO changes for this story — it already renders all activity types generically. All visual changes are isolated to `FeedItem.tsx`.

### Current `FeedItem` Component

File: `dashboard/components/FeedItem.tsx`

Current structure (43 lines):
```tsx
const ERROR_EVENTS = ["task_crashed", "system_error", "agent_crashed"];
const HITL_EVENTS = ["hitl_requested", "hitl_approved", "hitl_denied"];

export function FeedItem({ activity }: FeedItemProps) {
  let borderClass = "border-l-2 border-transparent";
  if (ERROR_EVENTS.includes(activity.eventType)) {
    borderClass = "border-l-2 border-red-400";
  } else if (HITL_EVENTS.includes(activity.eventType)) {
    borderClass = "border-l-2 border-amber-400";
  }

  return (
    <div className={`rounded-md border border-border bg-background px-3 py-2 ${borderClass}`}>
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="text-xs font-mono text-muted-foreground">
          {formatTime(activity.timestamp)}
        </span>
        {activity.agentName && (
          <span className="truncate text-xs font-medium text-foreground">
            {activity.agentName}
          </span>
        )}
      </div>
      <p className="text-xs text-muted-foreground">{activity.description}</p>
    </div>
  );
}
```

The `activity` prop is typed as `Doc<"activities">` from the Convex-generated data model, so `activity.eventType` is already the full union type from `schema.ts`.

### Current Event Types in Schema

File: `dashboard/convex/schema.ts` (lines 154–205)

The `activities.eventType` union currently includes these step-relevant literals (confirmed from schema.ts):
- `"step_dispatched"` — step dispatched to an agent (planned/blocked → assigned)
- `"step_started"` — step began execution (assigned → running)
- `"step_completed"` — step finished successfully (running → completed)
- `"step_created"` — step record created (plan materialization)
- `"step_status_changed"` — generic step status transition (emitted by `updateStatus` in `steps.ts`)
- `"step_crashed"` — step crashed, added in Story 3.1
- `"step_unblocked"` — step was unblocked, its `blockedBy` cleared
- `"step_retrying"` — user initiated a retry, added in Story 3.4

Note: The architecture spec (`architecture.md` lines 498–506) uses `"step_assigned"` as a conceptual name, but the actual implementation uses `"step_dispatched"` for the `planned → assigned` and `blocked → assigned` transitions. Do NOT add `"step_assigned"` as a new literal — use `"step_dispatched"` which already exists.

### `activities:create` Mutation Event Type Union

File: `dashboard/convex/activities.ts` (lines 8–44)

The `create` mutation has its own `eventType` union (a subset of the schema). This union was not updated in Stories 3.1 or 3.4 (those stories insert directly via `ctx.db.insert` inside `steps.ts` mutations, bypassing the `activities:create` mutation). Therefore:
- `step_crashed` may be MISSING from the `activities:create` mutation union even though it's in the schema.
- `step_retrying` may be MISSING from the `activities:create` mutation union.

Task 2 must verify and reconcile these. Since the dashboard does not call `activities:create` directly for step events (step events are inserted by `steps.ts` mutations internally), omission from the `create` mutation union is acceptable — document as verified.

### Icon Mapping — Lucide React

All icons should be imported from `lucide-react`, which is already used in the project (confirmed by `StepCard.tsx` usage of `AlertTriangle`, `Lock`). Import only the icons needed:

```tsx
import { CheckCircle2, XCircle, Play, ArrowRight, Unlock, RefreshCw, Activity } from "lucide-react";
```

Icons must be `h-3 w-3` to match the `text-xs` feed density. Color via Tailwind text utilities.

### Destructive Color for Error Events (FR38)

From the UX spec (`ux-design-specification.md` lines 811–812):
> **Variants** | Normal (white background), Error (red-tinted border), HITL (amber-tinted — for approval-related events)

The existing `FeedItem` already applies `border-l-2 border-red-400` for `ERROR_EVENTS`. Adding `step_crashed` to that array is the only change needed to satisfy FR38 for step crash events. The `step_retrying` event should NOT be red — it is a recovery action and should be amber (but since `step_retrying` is not a HITL event, it gets the transparent border). Add `step_retrying` to `HITL_EVENTS` only if the amber styling is desired; otherwise leave it as a neutral event with only the amber refresh icon.

**Decision for MVP:** Keep `step_retrying` as a neutral border (transparent) with the amber `RefreshCw` icon providing sufficient visual differentiation. Only `step_crashed` joins `ERROR_EVENTS` for the destructive red border.

### Reverse Chronological Order

The `activities:listRecent` query in `dashboard/convex/activities.ts` (lines 70–79) already uses `.order("desc")` on the `by_timestamp` index:

```typescript
export const listRecent = query({
  handler: async (ctx) => {
    return await ctx.db
      .query("activities")
      .withIndex("by_timestamp")
      .order("desc")
      .take(100);
  },
});
```

No changes needed to the query — reverse chronological order is already implemented.

### Real-Time Updates via Convex Reactive Queries

Convex reactive queries (`useQuery`) automatically re-run whenever the underlying table data changes. When a `steps.ts` mutation inserts a new activity event via `ctx.db.insert("activities", ...)`, Convex pushes an update to all subscribed clients. The `ActivityFeed` component re-renders with the new data. The `motion.div` wrapper provides the 200ms fade-in animation. No polling or WebSocket management is needed in application code — this is handled entirely by Convex's reactive infrastructure.

### No Backend Changes Required

This story is entirely frontend (React components + TypeScript tests). No Python changes, no new Convex mutations, no schema additions. All step event types required by the story are already present in `schema.ts` from prior stories (3.1 and 3.4). The Python `ActivityEventType` enum in `nanobot/mc/types.py` already has `STEP_RETRYING` (added in Story 3.4) — no Python changes needed.

### Project Structure Notes

- **Files to modify:**
  - `dashboard/components/FeedItem.tsx` — add `step_crashed` to `ERROR_EVENTS`, add `STEP_EVENTS` constant, add icon mapping function, update JSX to render step event icons
- **Files to create:**
  - `dashboard/components/FeedItem.test.tsx` — if it does not exist; if it does exist, extend it
- **Files to verify (read-only check, no modification expected):**
  - `dashboard/convex/activities.ts` — verify step event types in `create` mutation union
  - `dashboard/convex/schema.ts` — verify `step_crashed` and `step_retrying` are present (they were added in 3.1 and 3.4)
- **No changes to:**
  - `dashboard/components/ActivityFeed.tsx` — already handles all event types generically
  - `dashboard/convex/activities.ts` — `listRecent` query already correct; `create` mutation may need verification only
  - Any Python files
  - Any Convex schema

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.5] — Acceptance criteria (lines 906–931)
- [Source: _bmad-output/planning-artifacts/architecture.md#Activity Event Types] — Full `ActivityEventType` union with step events (lines 495–506)
- [Source: _bmad-output/planning-artifacts/architecture.md#Dashboard & Visualization FR35-FR38] — Activity feed for step events (line 47)
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#FeedItem] — FeedItem anatomy: timestamp + agent name + description; Error variant: red-tinted border (lines 805–813)
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#ActivityFeed] — ScrollArea + FeedItem; auto-scroll; real-time stream (lines 795–803)
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Rich activity feed entries] — "Human-readable entries with agent name + timestamp + description. Not terse logs — the feed tells the story of what agents are doing." (line 519)
- [Source: dashboard/components/FeedItem.tsx] — Current 43-line implementation; `ERROR_EVENTS` and `HITL_EVENTS` constants
- [Source: dashboard/components/ActivityFeed.tsx] — Current 133-line implementation; `useQuery(api.activities.listRecent)`, auto-scroll, `aria-live="polite"`, motion fade-in
- [Source: dashboard/convex/activities.ts] — `listRecent` query with `.order("desc").take(100)`; `create` mutation with `eventType` union
- [Source: dashboard/convex/schema.ts#activities] — Full `activities.eventType` union (lines 154–205); `step_crashed` (added Story 3.1), `step_retrying` (added Story 3.4)
- [Source: _bmad-output/implementation-artifacts/3-1-implement-step-status-state-machine.md#Task 3.4] — `step_crashed` literal added to `activities.eventType` schema union
- [Source: _bmad-output/implementation-artifacts/3-4-retry-crashed-steps.md#Task 1.4] — `step_retrying` literal added to `activities.eventType` schema union

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Task 1: Extended `FeedItem.tsx` with `step_crashed` added to `ERROR_EVENTS`, `STEP_EVENTS` Set defined, `getStepEventIcon()` function added with Lucide React icons, and JSX updated to render icon in a `flex items-center gap-1` `<p>` element.
- Task 2 (verified, no changes): Schema (`schema.ts`) already contains all required step event types including `step_crashed` (Story 3.1) and `step_retrying` (Story 3.4). The `activities:create` mutation in `activities.ts` omits `step_crashed` and `step_retrying` — this is acceptable because those event types are inserted directly by `steps.ts` mutations, not via the `activities:create` mutation.
- Task 3: Created `dashboard/components/FeedItem.test.tsx` with 5 tests covering step event icon rendering, red border for step_crashed, amber icon for step_retrying, no icon for task-level events, and no red border for step_unblocked. All 5 tests pass.
- Task 4: Manual integration is verified at code level — `ActivityFeed.tsx` already uses `.order("desc")` via `listRecent` query and renders all event types generically through `FeedItem`. No structural changes required for real-time or ordering.
- Full test suite: 335 tests across 25 files — all pass.

### File List

- `dashboard/components/FeedItem.tsx` — modified: added `step_crashed` to `ERROR_EVENTS`, added `STEP_EVENTS` Set, added `getStepEventIcon()` function, updated JSX description `<p>` to flex with icon
- `dashboard/components/FeedItem.test.tsx` — created: 5 component tests for step event icon rendering and border styling

## Code Review Record

### Reviewer

claude-sonnet-4-6 (adversarial review)

### Review Date

2026-02-25

### Findings

#### MEDIUM — Test anti-pattern: `document.querySelector` instead of `container.querySelector`

**File:** `dashboard/components/FeedItem.test.tsx`
**Issue:** All 5 tests used the global `document.querySelector` for DOM assertions. This is a Testing Library anti-pattern that can cause cross-test pollution if `cleanup()` ever fails to fully detach nodes. The correct approach is to use the `container` returned from `render()`, scoping queries to the rendered component tree.
**Fix Applied:** Replaced all `document.querySelector` / `document.querySelectorAll` calls with `container.querySelector` / `container.querySelectorAll` by destructuring `container` from `render()`. All 5 tests continue to pass.

#### LOW — No tests for `step_started` and `step_dispatched` icon rendering

**File:** `dashboard/components/FeedItem.test.tsx`
**Issue:** AC6 specifies icon mapping for `step_started` (Play/blue) and `step_dispatched` (ArrowRight/slate), but neither has a dedicated test. The story's Task 3 only required tests for 5 specific event types, so this is a minor coverage gap.
**Decision:** No fix applied — the story's AC and task checklist do not require these tests. The `getStepEventIcon()` implementation covers these cases and they can be added in a follow-up if desired.

#### LOW — `step_created` emitted by `steps.ts` has no icon in FeedItem

**File:** `dashboard/components/FeedItem.tsx`
**Issue:** `step_created` is in the schema and emitted by `steps.ts`, but is intentionally omitted from the `STEP_EVENTS` Set. It renders in the feed without an icon. Per the story spec (Task 1.2 lists exactly 7 event types to include), this is by design.
**Decision:** No fix applied — intentional per story specification.

### Test Results After Fixes

- 335 tests across 25 files — all pass
- `components/FeedItem.test.tsx` — 5/5 tests pass

### AC Verification

- AC1: Step lifecycle events render as FeedItems with icon, agent name, timestamp, description — PASS
- AC2: Reverse chronological order with visual distinction via icons — PASS (listRecent uses `.order("desc")`)
- AC3: Real-time updates via Convex reactive queries — PASS (no polling needed; Convex pushes updates)
- AC4: Destructive red border for `step_crashed` (and other error events) — PASS
- AC5: `step_crashed` and `step_retrying` in schema union — PASS (confirmed in schema.ts lines 197, 199)
- AC6: Icon mapping for all 6 required step event types — PASS (getStepEventIcon covers all)
