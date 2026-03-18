# Story 2.2: Implement Task Creation from Dashboard

Status: done

## Story

As a **user**,
I want to type a task description and hit Enter to create a new task instantly,
So that I can delegate work to agents with zero friction.

## Acceptance Criteria

1. **Given** the dashboard layout is rendered (Story 2.1), **When** the user types a task description in the always-visible TaskInput field at the top of the Kanban area and presses Enter, **Then** a new task is created in Convex via `tasks.create` mutation with status "inbox", trust level "autonomous" (default), and an ISO 8601 timestamp
2. **Given** a task is created, **Then** the task card appears in the Inbox column within 200ms via optimistic UI (violet accent fade-in)
3. **Given** a task is created, **Then** the TaskInput field clears after submission
4. **Given** a task is created, **Then** a `task_created` activity event is written to the `activities` table in the same mutation
5. **Given** the user submits an empty task description, **When** validation runs, **Then** the input border turns red with small text below: "Task description required"
6. **Given** the user submits an empty description, **Then** no mutation is called
7. **Given** a task is created with optional tags (comma-separated), **Then** the tags are stored as an array of strings on the task
8. **And** the `TaskInput.tsx` component is created with ShadCN `Input` + `Button`
9. **And** the Convex `tasks.ts` file contains the `create` mutation with activity event logging
10. **And** a Vitest test exists for `TaskInput.tsx` covering submission and empty validation

## Tasks / Subtasks

- [x] Task 1: Create the Convex `tasks.ts` mutation file (AC: #1, #4, #9)
  - [x] 1.1: Create `dashboard/convex/tasks.ts`
  - [x] 1.2: Implement `create` mutation: accepts `title` (string), `description` (optional string), `tags` (optional array of strings)
  - [x] 1.3: Set default values: `status: "inbox"`, `trustLevel: "autonomous"`, `createdAt` and `updatedAt` to current ISO 8601 timestamp
  - [x] 1.4: In the same mutation, insert a `task_created` activity event into the `activities` table with the task title in the description
  - [x] 1.5: Return the newly created task ID

- [x] Task 2: Create the Convex `activities.ts` file (AC: #4)
  - [x] 2.1: Create `dashboard/convex/activities.ts`
  - [x] 2.2: Implement `create` mutation: accepts `eventType`, `description`, `timestamp`, optional `taskId`, optional `agentName`
  - [x] 2.3: Implement `list` query: returns all activities ordered by timestamp (ascending — newest last)

- [x] Task 3: Create the Convex `tasks.ts` query (AC: #1)
  - [x] 3.1: Implement `list` query in `dashboard/convex/tasks.ts`: returns all tasks (used by KanbanBoard in Story 2.3)

- [x] Task 4: Create the TaskInput component (AC: #1, #2, #3, #5, #6, #7, #8)
  - [x] 4.1: Create `dashboard/components/TaskInput.tsx` with `"use client"` directive
  - [x] 4.2: Render ShadCN `Input` (full width, placeholder: "Create a new task...") + ShadCN `Button` (text: "Create")
  - [x] 4.3: Handle Enter key press to submit
  - [x] 4.4: Implement empty validation: if input is empty on submit, show red border + "Task description required" error text below
  - [x] 4.5: On valid submit: call `useMutation(api.tasks.create)` with the task title
  - [x] 4.6: Clear the input field after successful submission
  - [x] 4.7: Parse comma-separated tags if present (e.g., user types "Research AI trends #tag1, tag2" — extract tags from the input or provide a separate tags field)

- [x] Task 5: Integrate TaskInput into DashboardLayout (AC: #1)
  - [x] 5.1: Import and render `TaskInput` in the main content area of `DashboardLayout.tsx`, below the "Mission Control" header
  - [x] 5.2: Add appropriate padding and margin (`p-4`, `mb-4`)

- [x] Task 6: Write unit tests (AC: #10)
  - [x] 6.1: Create `dashboard/components/TaskInput.test.tsx`
  - [x] 6.2: Test that input renders with placeholder text
  - [x] 6.3: Test that empty submission shows validation error
  - [x] 6.4: Test that valid submission calls the mutation
  - [x] 6.5: Test that input clears after submission

## Dev Notes

### Critical Architecture Requirements

- **Convex mutations are the API**: There is no REST API. The `TaskInput` component calls Convex mutations directly via the `useMutation` hook. The mutation runs on the Convex backend and writes to the database.
- **Every task creation MUST write an activity event**: The `tasks.create` mutation MUST also insert into the `activities` table. This is an architectural invariant — no task state change without a feed entry.
- **Optimistic UI**: Convex's `useMutation` supports optimistic updates. When the user submits, the task should appear in the Inbox column immediately (before server confirmation). If the mutation fails, the optimistic update is rolled back.
- **ISO 8601 timestamps**: All `createdAt`, `updatedAt`, and activity `timestamp` fields use ISO 8601 format (`new Date().toISOString()`).
- **snake_case vs camelCase**: Convex schema uses camelCase field names (`trustLevel`, `assignedAgent`, `createdAt`). The Python bridge converts at the boundary. TypeScript code uses camelCase everywhere.

### Convex Mutation Pattern

```typescript
// dashboard/convex/tasks.ts
import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const create = mutation({
  args: {
    title: v.string(),
    description: v.optional(v.string()),
    tags: v.optional(v.array(v.string())),
  },
  handler: async (ctx, args) => {
    const now = new Date().toISOString();

    // Create the task
    const taskId = await ctx.db.insert("tasks", {
      title: args.title,
      description: args.description,
      status: "inbox",
      trustLevel: "autonomous",
      tags: args.tags,
      createdAt: now,
      updatedAt: now,
    });

    // Write activity event (architectural invariant)
    await ctx.db.insert("activities", {
      taskId,
      eventType: "task_created",
      description: `Task created: "${args.title}"`,
      timestamp: now,
    });

    return taskId;
  },
});

export const list = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db.query("tasks").collect();
  },
});
```

### Convex Activities Pattern

```typescript
// dashboard/convex/activities.ts
import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const create = mutation({
  args: {
    taskId: v.optional(v.id("tasks")),
    agentName: v.optional(v.string()),
    eventType: v.string(),
    description: v.string(),
    timestamp: v.string(),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("activities", {
      taskId: args.taskId,
      agentName: args.agentName,
      eventType: args.eventType as any,
      description: args.description,
      timestamp: args.timestamp,
    });
  },
});

export const list = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db
      .query("activities")
      .withIndex("by_timestamp")
      .collect();
  },
});
```

### TaskInput Component Pattern

```tsx
// dashboard/components/TaskInput.tsx
"use client";

import { useState } from "react";
import { useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export function TaskInput() {
  const [title, setTitle] = useState("");
  const [error, setError] = useState("");
  const createTask = useMutation(api.tasks.create);

  const handleSubmit = async () => {
    const trimmed = title.trim();
    if (!trimmed) {
      setError("Task description required");
      return;
    }
    setError("");
    await createTask({ title: trimmed });
    setTitle("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSubmit();
    }
  };

  return (
    <div className="flex gap-2">
      <div className="flex-1">
        <Input
          placeholder="Create a new task..."
          value={title}
          onChange={(e) => { setTitle(e.target.value); setError(""); }}
          onKeyDown={handleKeyDown}
          className={error ? "border-red-500" : ""}
        />
        {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
      </div>
      <Button onClick={handleSubmit}>Create</Button>
    </div>
  );
}
```

### Import Path Convention

Convex API imports use the generated API types:

```typescript
import { api } from "../convex/_generated/api";  // From components/
import { api } from "@/convex/_generated/api";     // If path alias configured
```

The Convex `useMutation` and `useQuery` hooks come from `convex/react`:

```typescript
import { useMutation, useQuery } from "convex/react";
```

### Common LLM Developer Mistakes to Avoid

1. **DO NOT forget the `"use client"` directive** — `TaskInput.tsx` uses React hooks (`useState`) and Convex hooks (`useMutation`). It MUST have `"use client"` at the top of the file.

2. **DO NOT create a task without writing an activity event** — The `tasks.create` mutation MUST also insert into the `activities` table. This is an architectural invariant. Do not create separate mutations for task creation and activity logging.

3. **DO NOT use `v.literal()` unions in mutation args for eventType** — The `eventType` argument in the `activities.create` mutation should accept `v.string()` and cast it, because the union is already enforced by the schema. Using the full union in args makes calls from the bridge verbose.

4. **DO NOT use `fetch` or REST calls** — Convex mutations are called via `useMutation(api.tasks.create)`. There is no REST API. The Convex React hooks handle all communication.

5. **DO NOT skip input validation on the client** — Empty task titles must be caught on the client side before calling the mutation. The input border must turn red and show "Task description required".

6. **DO NOT forget to clear the input after submission** — Call `setTitle("")` after a successful mutation call. The input should be ready for the next task immediately.

7. **DO NOT use `Date.now()` for timestamps** — Use `new Date().toISOString()` to get ISO 8601 format. All timestamps in the system use ISO 8601 strings, not Unix milliseconds.

8. **DO NOT create a modal or dialog for task creation** — The TaskInput is always visible at the top of the Kanban area. It is NOT a modal, dialog, or expandable form (the progressive disclosure panel is added in Epic 4).

9. **DO NOT add trust level, agent selector, or reviewer config to TaskInput** — This story creates a SIMPLE input field. Trust level defaults to "autonomous". Agent assignment and review config are added in Stories 4.4 and 5.1.

10. **DO NOT import from `convex/server` in component files** — `convex/server` exports (`mutation`, `query`) are for Convex backend function files (`convex/*.ts`). Component files use `convex/react` hooks.

### What This Story Does NOT Include

- **No Kanban board display** — Tasks are created but not yet displayed on a board. Built in Story 2.3.
- **No task detail view** — Clicking a task does nothing yet. Built in Story 2.6.
- **No progressive disclosure** — No agent selector, trust level, or reviewer config. Added in Stories 4.4 and 5.1.
- **No optimistic UI for card appearance** — The optimistic card fade-in is implemented when the KanbanBoard exists (Story 2.3). This story just ensures the mutation works.
- **No tags UI** — Tags can be passed programmatically but the UI for tag input is minimal (can be enhanced later).

### Files Created in This Story

| File | Purpose |
|------|---------|
| `dashboard/convex/tasks.ts` | `create` mutation + `list` query for tasks table |
| `dashboard/convex/activities.ts` | `create` mutation + `list` query for activities table |
| `dashboard/components/TaskInput.tsx` | Always-visible task creation input with validation |
| `dashboard/components/TaskInput.test.tsx` | Unit tests for TaskInput component |

### Files Modified in This Story

| File | Changes |
|------|---------|
| `dashboard/components/DashboardLayout.tsx` | Add `TaskInput` to main content area |

### Verification Steps

1. `cd dashboard && npx convex dev` — Convex dev server starts, schema syncs without errors
2. Open Convex dashboard (localhost:3210) — `tasks` and `activities` tables are visible
3. Open localhost:3000 — TaskInput is visible below the "Mission Control" header
4. Type "Research AI trends" and press Enter — task is created in Convex `tasks` table
5. Verify in Convex dashboard: task has `status: "inbox"`, `trustLevel: "autonomous"`, ISO 8601 timestamps
6. Verify in Convex dashboard: `activities` table has a `task_created` event
7. Input field is cleared after submission
8. Submit with empty input — red border appears, "Task description required" shown, no mutation called
9. `cd dashboard && npx vitest run` — Tests pass

### References

- [Source: `_bmad-output/planning-artifacts/architecture.md#Communication Patterns`] — Convex mutation pattern, activity event co-write
- [Source: `_bmad-output/planning-artifacts/architecture.md#Data Architecture`] — Tasks table schema, activities table schema
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#Component Strategy`] — TaskInput spec: always-visible, Input + Button, progressive disclosure (deferred)
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#UX Consistency Patterns`] — Task created feedback: violet fade-in (200ms), input clears after submission
- [Source: `_bmad-output/planning-artifacts/epics.md#Story 2.2`] — Original story definition with acceptance criteria
- [Source: `dashboard/convex/schema.ts`] — Convex schema with tasks and activities table definitions
- [Source: `dashboard/lib/constants.ts`] — TASK_STATUS, TRUST_LEVEL, ACTIVITY_EVENT_TYPE constants

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References
- TypeScript compilation: clean (0 errors)
- Vitest: 17/17 tests passing (9 TaskInput + 8 DashboardLayout)

### Completion Notes List
- Created `convex/tasks.ts` with `create` mutation (writes task + activity event atomically) and `list` query
- Created `convex/activities.ts` with `create` mutation and `list` query (ordered by timestamp index)
- Created `TaskInput.tsx` component with ShadCN Input + Button, empty validation, Enter key support, and tag parsing via `#tag1, tag2` syntax
- Replaced TaskInput placeholder in DashboardLayout with real TaskInput component
- Added `convex/react` mock to DashboardLayout tests to prevent failures from TaskInput's `useMutation` hook
- 9 unit tests for TaskInput covering: render, empty validation, whitespace validation, mutation call, input clearing, Enter key submit, error clearing, and tag parsing

### File List
| File | Action | Purpose |
|------|--------|---------|
| `dashboard/convex/tasks.ts` | Created | `create` mutation + `list` query for tasks table |
| `dashboard/convex/activities.ts` | Created | `create` mutation + `list` query for activities table |
| `dashboard/components/TaskInput.tsx` | Created | Always-visible task creation input with validation |
| `dashboard/components/TaskInput.test.tsx` | Created | 9 unit tests for TaskInput component |
| `dashboard/components/DashboardLayout.tsx` | Modified | Replaced placeholder with real TaskInput component |
| `dashboard/components/DashboardLayout.test.tsx` | Modified | Added convex/react mock for TaskInput compatibility |

### Code Review Findings

**Reviewer:** Claude Opus 4.6 (adversarial review)

**Issues Found (4):**

1. **[HIGH - FIXED] No error handling for failed mutations** — `TaskInput.handleSubmit` called `await createTask(...)` without try/catch. If the Convex mutation fails, the error was unhandled and no user feedback was shown. Fixed: wrapped in try/catch with user-visible error message "Failed to create task. Please try again."

2. **[MEDIUM - FIXED] Tag parsing edge case with hash-only input** — Typing `#tag1, tag2` (hash at index 0) resulted in empty `taskTitle` but the fallback `taskTitle || trimmed` would use the raw hash string as the task title. Fixed: added explicit check that rejects empty title after tag parsing with "Task description required" error.

3. **[LOW] `activities.create` mutation accepts `v.string()` for eventType and casts** — The `eventType` arg accepts any string and casts it to the schema union type. The schema enforces the union at write time, but invalid event types would only fail at Convex runtime, not at the TypeScript level. Acceptable per dev notes: "Use `v.string()` and cast it, because the union is already enforced by the schema."

4. **[LOW] No test for failed mutation error display** — Tests cover successful submission and validation, but do not test the error state when the mutation itself fails. The new try/catch error handling is not covered by existing tests.

**Verification:** tsc --noEmit clean (0 errors), 69/69 vitest tests passing.
