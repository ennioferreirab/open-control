# Story 2.5: Build Activity Feed

Status: done

## Story

As a **user**,
I want to see a real-time activity feed showing what agents are doing as it happens,
So that I can monitor the system without clicking into individual tasks.

## Acceptance Criteria

1. **Given** activity events exist in the Convex `activities` table, **When** the dashboard loads, **Then** the ActivityFeed panel renders on the right side (280px) with an "Activity Feed" header
2. **Given** activity events exist, **Then** FeedItem components display chronologically (newest at bottom) with: timestamp (`text-xs`, monospace), agent name (`font-medium`), description (`text-xs`)
3. **Given** the feed renders, **Then** the feed uses ShadCN `ScrollArea` for vertical scrolling
4. **Given** a new activity event is written to Convex, **When** the reactive query updates, **Then** the new FeedItem fades in at the bottom (200ms fade-in)
5. **Given** auto-scroll behavior, **Then** the feed auto-scrolls to the latest entry if the user is already at the bottom
6. **Given** the user has scrolled up, **Then** auto-scroll pauses and a "New activity" indicator appears at the bottom
7. **Given** a new activity event appears, **Then** the feed update appears within 3 seconds of the event (NFR3)
8. **Given** error-type activity events exist (e.g., `task_crashed`, `system_error`), **When** they render in the feed, **Then** the FeedItem has a red-tinted left border
9. **Given** HITL-related events exist (e.g., `hitl_requested`, `hitl_approved`), **When** they render in the feed, **Then** the FeedItem has an amber-tinted left border
10. **Given** no activity events exist, **When** the feed renders, **Then** muted italic text displays: "Waiting for activity..."
11. **Given** the Convex connection is lost, **When** the feed detects disconnection, **Then** a subtle banner displays at the top of the feed: "Reconnecting..." (NFR13)
12. **And** `ActivityFeed.tsx` and `FeedItem.tsx` components are created
13. **And** Convex `activities.ts` contains a `list` query (ordered by timestamp, latest last)
14. **And** Vitest test exists for `ActivityFeed.tsx`

## Tasks / Subtasks

- [x] Task 1: Ensure Convex `activities.ts` has the `list` query (AC: #13)
  - [x]1.1: Verify `dashboard/convex/activities.ts` exists from Story 2.2
  - [x]1.2: Verify the `list` query returns activities ordered by timestamp ascending (newest at bottom)
  - [x]1.3: Add a `listRecent` query that returns the most recent N activities (e.g., last 100) to avoid loading entire history on initial load

- [x] Task 2: Create the FeedItem component (AC: #2, #8, #9)
  - [x]2.1: Create `dashboard/components/FeedItem.tsx`
  - [x]2.2: Accept props: `activity` object (matching Convex activity document shape)
  - [x]2.3: Render timestamp in `text-xs font-mono text-slate-400` format (e.g., "14:32:05")
  - [x]2.4: Render agent name in `text-xs font-medium text-slate-700`
  - [x]2.5: Render description in `text-xs text-slate-500`
  - [x]2.6: For error events (`task_crashed`, `system_error`, `agent_crashed`): add `border-l-2 border-red-400` left border tint
  - [x]2.7: For HITL events (`hitl_requested`, `hitl_approved`, `hitl_denied`): add `border-l-2 border-amber-400` left border tint
  - [x]2.8: Default events: no left border tint (or very subtle `border-l-2 border-transparent`)

- [x] Task 3: Create the ActivityFeed component (AC: #1, #3, #4, #5, #6, #7, #10, #11)
  - [x]3.1: Create `dashboard/components/ActivityFeed.tsx` with `"use client"` directive
  - [x]3.2: Use `useQuery(api.activities.list)` (or `listRecent`) to subscribe to activities
  - [x]3.3: Render "Activity Feed" header (`text-lg font-semibold`) at the top
  - [x]3.4: Render activities in a ShadCN `ScrollArea` as a list of `FeedItem` components
  - [x]3.5: Implement auto-scroll: when new items arrive and user is at the bottom, scroll to latest
  - [x]3.6: Implement scroll pause: when user scrolls up, stop auto-scrolling and show "New activity" indicator at the bottom
  - [x]3.7: Clicking "New activity" indicator scrolls to bottom and resumes auto-scroll
  - [x]3.8: Show "Waiting for activity..." muted italic text when no events exist
  - [x]3.9: New feed items fade in using Framer Motion (200ms fade-in, `opacity: 0 -> 1`)
  - [x]3.10: Handle Convex connection state: show "Reconnecting..." banner when disconnected

- [x] Task 4: Integrate ActivityFeed into the ActivityFeedPanel (AC: #1)
  - [x]4.1: Update `dashboard/components/ActivityFeedPanel.tsx` (from Story 2.1) to render the `ActivityFeed` component instead of placeholder text
  - [x]4.2: Ensure the feed fills the available height in the right panel

- [x] Task 5: Write unit tests (AC: #14)
  - [x]5.1: Create `dashboard/components/ActivityFeed.test.tsx`
  - [x]5.2: Test that feed renders activities in chronological order
  - [x]5.3: Test empty state shows "Waiting for activity..."
  - [x]5.4: Test FeedItem renders timestamp, agent name, and description
  - [x]5.5: Test error events have red left border
  - [x]5.6: Test HITL events have amber left border

## Dev Notes

### Critical Architecture Requirements

- **Convex reactive queries**: The `useQuery(api.activities.list)` hook automatically updates when new activities are inserted. This is the same reactivity mechanism used by the KanbanBoard. No polling needed.
- **Append-only table**: The `activities` table is append-only — events are never deleted or modified. This simplifies the feed implementation.
- **Activity events are written by mutations**: Every task state change in `tasks.updateStatus` writes an activity event. Every task creation writes an event. The bridge also writes events. The feed passively displays whatever arrives.
- **Feed is a passive display**: The activity feed does NOT trigger any actions. It is purely a read-only monitoring surface.

### Auto-Scroll Implementation Pattern

The auto-scroll behavior requires tracking whether the user is at the bottom of the scroll area. If they are, new items automatically scroll into view. If the user has scrolled up to read older entries, auto-scroll pauses.

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "convex/react";
import { api } from "../convex/_generated/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { FeedItem } from "./FeedItem";

export function ActivityFeed() {
  const activities = useQuery(api.activities.list);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [hasNewActivity, setHasNewActivity] = useState(false);
  const prevCountRef = useRef(0);

  // Detect scroll position
  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 30;
    setIsAtBottom(atBottom);
    if (atBottom) {
      setHasNewActivity(false);
    }
  };

  // Auto-scroll when new items arrive and user is at bottom
  useEffect(() => {
    if (!activities) return;

    if (activities.length > prevCountRef.current) {
      if (isAtBottom) {
        // Scroll to bottom
        scrollRef.current?.scrollTo({
          top: scrollRef.current.scrollHeight,
          behavior: "smooth",
        });
      } else {
        // User is scrolled up — show indicator
        setHasNewActivity(true);
      }
      prevCountRef.current = activities.length;
    }
  }, [activities, isAtBottom]);

  const scrollToBottom = () => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
    setHasNewActivity(false);
  };

  if (activities === undefined) return null;

  if (activities.length === 0) {
    return (
      <p className="text-sm text-slate-400 italic p-4">
        Waiting for activity...
      </p>
    );
  }

  return (
    <div className="relative h-full flex flex-col">
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-2 space-y-1"
        onScroll={handleScroll}
      >
        {activities.map((activity) => (
          <FeedItem key={activity._id} activity={activity} />
        ))}
      </div>

      {hasNewActivity && (
        <button
          onClick={scrollToBottom}
          className="absolute bottom-2 left-1/2 -translate-x-1/2
            bg-blue-500 text-white text-xs px-3 py-1 rounded-full
            shadow-md hover:bg-blue-600 transition-colors"
        >
          New activity
        </button>
      )}
    </div>
  );
}
```

### FeedItem Component Pattern

```tsx
// dashboard/components/FeedItem.tsx
import { Doc } from "../convex/_generated/dataModel";

interface FeedItemProps {
  activity: Doc<"activities">;
}

const ERROR_EVENTS = ["task_crashed", "system_error", "agent_crashed"];
const HITL_EVENTS = ["hitl_requested", "hitl_approved", "hitl_denied"];

function formatTime(isoTimestamp: string): string {
  const date = new Date(isoTimestamp);
  return date.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function FeedItem({ activity }: FeedItemProps) {
  let borderClass = "border-l-2 border-transparent";
  if (ERROR_EVENTS.includes(activity.eventType)) {
    borderClass = "border-l-2 border-red-400";
  } else if (HITL_EVENTS.includes(activity.eventType)) {
    borderClass = "border-l-2 border-amber-400";
  }

  return (
    <div className={`px-2 py-1.5 ${borderClass} rounded-sm`}>
      <div className="flex items-center gap-2">
        <span className="text-xs font-mono text-slate-400">
          {formatTime(activity.timestamp)}
        </span>
        {activity.agentName && (
          <span className="text-xs font-medium text-slate-700">
            {activity.agentName}
          </span>
        )}
      </div>
      <p className="text-xs text-slate-500 mt-0.5">{activity.description}</p>
    </div>
  );
}
```

### Convex Connection State Detection

Convex's React client provides connection state that can be used to detect disconnection:

```tsx
import { useConvex } from "convex/react";

// Inside component:
// The useQuery hook returns undefined while disconnected/loading.
// For a more explicit check, you can monitor the ConvexReactClient state.
// For MVP, showing "Reconnecting..." when useQuery returns undefined
// after having previously returned data is sufficient.
```

For MVP, the simplest approach is: if `activities` was previously defined (had data) and becomes `undefined`, show the "Reconnecting..." banner. When it returns to defined, remove the banner.

### Event Type Categorization

| Category | Event Types | FeedItem Style |
|----------|------------|----------------|
| Normal | `task_created`, `task_assigned`, `task_started`, `task_completed`, `review_requested`, `review_feedback`, `review_approved`, `agent_connected`, `agent_disconnected` | No border tint |
| Error | `task_crashed`, `system_error`, `agent_crashed` | Red left border |
| HITL | `hitl_requested`, `hitl_approved`, `hitl_denied` | Amber left border |
| Retry | `task_retrying` | No border tint (it's a recovery action, not an error) |

### Common LLM Developer Mistakes to Avoid

1. **DO NOT render activities in reverse chronological order** — The feed shows newest at the BOTTOM, not the top. This matches chat/messaging conventions where the latest message is at the bottom and you read top-to-bottom.

2. **DO NOT load ALL activities on initial load** — For a long-running system, the activities table could have thousands of entries. Implement a `listRecent` query that returns the most recent N entries (e.g., 100). Or use Convex pagination.

3. **DO NOT use `setInterval` for auto-scroll** — The auto-scroll is triggered by React effects when the `activities` data changes, not by a timer. The Convex reactive query handles the timing.

4. **DO NOT use `window.scrollTo` for the feed scroll** — The feed is inside a `ScrollArea` (or a div with `overflow-y-auto`). Scroll the feed container element, not the window.

5. **DO NOT forget the `"use client"` directive** — `ActivityFeed.tsx` uses React hooks and Convex hooks. It must have `"use client"` at the top.

6. **DO NOT auto-scroll when the user is reading** — This is an anti-disruption rule from the UX spec. If the user has scrolled up to read older entries, auto-scroll MUST pause. Show the "New activity" indicator instead.

7. **DO NOT use `useEffect` with `activities` as dependency for initial scroll** — This would scroll on every re-render. Only scroll when the count changes AND the user is at the bottom.

8. **DO NOT make feed items clickable** — Feed items are purely informational. Clicking a feed item does NOT navigate to the task. (This could be a future enhancement but is not in scope.)

9. **DO NOT add sound effects or browser notifications** — The feed is a calm monitoring surface. No audio, no browser push notifications. Just visual updates.

10. **DO NOT use Framer Motion `AnimatePresence` without careful exit handling** — `AnimatePresence` requires unique `key` props and can cause issues with Convex reactive updates. For the feed, a simple opacity transition on mount is sufficient.

### What This Story Does NOT Include

- **No activity filtering** — All activities are shown. Filtering by task, agent, or event type is a future enhancement.
- **No activity search** — No search functionality in the feed.
- **No click-to-navigate** — Clicking a feed item does not open the related task. This could be added later.
- **No pagination controls** — The feed loads recent items and auto-scrolls. Manual pagination is not needed for MVP.
- **No agent avatar in feed items** — The UX spec mentions agent avatar, but for MVP, the agent name text is sufficient. Avatars can be added when the Agent Sidebar (Story 3.3) establishes the avatar pattern.

### Files Created in This Story

| File | Purpose |
|------|---------|
| `dashboard/components/ActivityFeed.tsx` | Real-time activity feed with auto-scroll and scroll pause |
| `dashboard/components/FeedItem.tsx` | Single feed entry with event-type-based styling |
| `dashboard/components/ActivityFeed.test.tsx` | Unit tests for feed rendering and event styling |

### Files Modified in This Story

| File | Changes |
|------|---------|
| `dashboard/components/ActivityFeedPanel.tsx` | Replace placeholder with `ActivityFeed` component |
| `dashboard/convex/activities.ts` | Add `listRecent` query if not already present |

### Verification Steps

1. Create a task via TaskInput — Activity feed shows "Task created: {title}" entry
2. Update a task status via Convex dashboard — Feed shows the transition event
3. Verify entries show timestamp (HH:MM:SS format), agent name, description
4. Verify error events (manually insert `task_crashed`) have red left border
5. Verify HITL events (manually insert `hitl_requested`) have amber left border
6. Scroll up in the feed — "New activity" indicator appears when new events arrive
7. Click "New activity" — Feed scrolls to bottom
8. No activities exist — "Waiting for activity..." text is shown
9. Feed updates appear within 3 seconds of the event being written (NFR3)
10. `cd dashboard && npx vitest run` — Tests pass

### References

- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#Component Strategy`] — ActivityFeed and FeedItem component specs
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#UX Consistency Patterns`] — Real-time update patterns, feed auto-scroll behavior, anti-disruption rules
- [Source: `_bmad-output/planning-artifacts/architecture.md#Data Architecture`] — Activities table: append-only, ordered by timestamp
- [Source: `_bmad-output/planning-artifacts/epics.md#Story 2.5`] — Original story definition with acceptance criteria
- [Source: `_bmad-output/planning-artifacts/prd.md#NFR3`] — Activity feed delay < 3 seconds
- [Source: `_bmad-output/planning-artifacts/prd.md#NFR13`] — Connection loss indicator
- [Source: `dashboard/convex/schema.ts`] — Activities table schema and indexes
- [Source: `dashboard/lib/constants.ts`] — ACTIVITY_EVENT_TYPE constants

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References
- TypeScript compilation: clean (zero errors)
- Vitest: 8/8 ActivityFeed tests pass
- Pre-existing DashboardLayout test failure (unrelated to this story)

### Completion Notes List
- Task 1: Added `listRecent` query to `convex/activities.ts` — fetches last 100 activities ordered desc, then reverses for chronological display
- Task 2: Created `FeedItem.tsx` with error (red) and HITL (amber) border styling, timestamp formatting, agent name + description rendering
- Task 3: Created `ActivityFeed.tsx` with Convex reactive subscription, auto-scroll with scroll-pause detection, "New activity" indicator, empty state, reconnection banner, Framer Motion fade-in
- Task 4: Updated `ActivityFeedPanel.tsx` to render `ActivityFeed` component instead of placeholder
- Task 5: Created `ActivityFeed.test.tsx` with 8 tests covering empty state, loading state, chronological order, border styles, agent name presence/absence

### File List
- `dashboard/components/ActivityFeed.tsx` (created)
- `dashboard/components/FeedItem.tsx` (created)
- `dashboard/components/ActivityFeed.test.tsx` (created)
- `dashboard/components/ActivityFeedPanel.tsx` (modified)
- `dashboard/convex/activities.ts` (modified)
