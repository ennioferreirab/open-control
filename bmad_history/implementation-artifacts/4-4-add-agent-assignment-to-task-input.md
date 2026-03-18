# Story 4.4: Add Agent Assignment to Task Input

Status: done

## Story

As a **user**,
I want to optionally assign a specific agent when creating a task,
So that I can bypass Lead Agent routing when I know which agent should handle the work.

## Acceptance Criteria

1. **Given** the TaskInput component exists (Story 2.2), **When** the user clicks the chevron to expand progressive disclosure options, **Then** a collapsible options panel appears below the input field
2. **Given** the options panel is expanded, **Then** an agent selector (`Select` component) is visible showing all registered agents from the Convex `agents` table
3. **Given** the agent selector, **Then** it defaults to "Auto (Lead Agent)" indicating automatic routing
4. **Given** the user selects a specific agent and submits the task, **When** the task is created, **Then** the task is created with `assignedAgent` set to the selected agent's name
5. **Given** the user leaves the selector on "Auto (Lead Agent)", **When** the task is created, **Then** the task is created with no `assignedAgent` and enters the Lead Agent routing flow
6. **Given** the user submits a task with an assigned agent, **Then** the progressive disclosure panel collapses after submission
7. **Given** the `tasks.create` mutation receives an `assignedAgent` argument, **Then** the task is created with that agent and a `task_created` activity event includes the agent name
8. **And** the agent selector is added to the progressive disclosure panel in `dashboard/components/TaskInput.tsx`
9. **And** the Convex `tasks.create` mutation is extended to accept an optional `assignedAgent` argument
10. **And** Vitest test exists for the expanded TaskInput with agent selection

## Tasks / Subtasks

- [ ] Task 1: Extend the Convex `tasks.create` mutation (AC: #7, #9)
  - [ ] 1.1: Add `assignedAgent: v.optional(v.string())` to the `create` mutation args in `dashboard/convex/tasks.ts`
  - [ ] 1.2: If `assignedAgent` is provided, set it on the task document and set initial status to "assigned" (not "inbox")
  - [ ] 1.3: Update the activity event description to include agent name if provided: `Task created and assigned to {agent}`

- [ ] Task 2: Add the progressive disclosure panel to TaskInput (AC: #1, #6, #8)
  - [ ] 2.1: Import ShadCN `Collapsible`, `CollapsibleTrigger`, `CollapsibleContent` components
  - [ ] 2.2: Add a chevron button (`ChevronDown` icon from Lucide) to the right of the Create button
  - [ ] 2.3: Clicking the chevron toggles a collapsible panel below the input
  - [ ] 2.4: Use `useState` to track `isExpanded` state
  - [ ] 2.5: The chevron rotates 180deg when expanded (CSS `rotate-180` transition)
  - [ ] 2.6: After task submission, reset `isExpanded` to false

- [ ] Task 3: Add the agent selector to the options panel (AC: #2, #3, #4, #5)
  - [ ] 3.1: Import ShadCN `Select`, `SelectTrigger`, `SelectValue`, `SelectContent`, `SelectItem`
  - [ ] 3.2: Use `useQuery(api.agents.list)` to fetch all registered agents
  - [ ] 3.3: Render a `Select` component with:
    - Default value: empty string (representing "Auto (Lead Agent)")
    - First option: "Auto (Lead Agent)" with value `""`
    - One option per agent: agent display name with value as agent name
  - [ ] 3.4: Track selected agent with `useState<string>("")`
  - [ ] 3.5: Pass the selected agent (or undefined if empty) to the `createTask` mutation
  - [ ] 3.6: After submission, reset selectedAgent to `""`

- [ ] Task 4: Update submission logic (AC: #4, #5)
  - [ ] 4.1: Modify `handleSubmit` to include `assignedAgent` in the mutation call when a specific agent is selected
  - [ ] 4.2: When "Auto (Lead Agent)" is selected, do NOT pass `assignedAgent` to the mutation
  - [ ] 4.3: Clear all expanded state (agent selection, isExpanded) after successful submission

- [ ] Task 5: Write Vitest tests (AC: #10)
  - [ ] 5.1: Update `dashboard/components/TaskInput.test.tsx` (or create new test file)
  - [ ] 5.2: Test chevron click toggles the options panel visibility
  - [ ] 5.3: Test agent selector renders with "Auto (Lead Agent)" as default
  - [ ] 5.4: Test submitting with a selected agent passes `assignedAgent` to the mutation
  - [ ] 5.5: Test submitting with "Auto" does not pass `assignedAgent`
  - [ ] 5.6: Test panel collapses after submission

## Dev Notes

### Critical Architecture Requirements

- **Progressive disclosure is a UX principle**: The expanded options panel is hidden by default. 80% of task creation uses the collapsed mode (type + enter). The expanded mode adds agent assignment, and later (Story 5.1) trust level and reviewer configuration.
- **The `agents.list` query already exists**: Story 3.3 (Agent Sidebar) creates the `agents.list` query. This story reuses it.
- **Agent assignment at creation time bypasses routing**: When `assignedAgent` is set, the task starts in "assigned" status — the Lead Agent routing loop (Story 4.1) skips it.

### TaskInput Component Update Pattern

```tsx
"use client";

import { useState } from "react";
import { useMutation, useQuery } from "convex/react";
import { api } from "../convex/_generated/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ChevronDown } from "lucide-react";

export function TaskInput() {
  const [title, setTitle] = useState("");
  const [error, setError] = useState("");
  const [isExpanded, setIsExpanded] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState("");

  const createTask = useMutation(api.tasks.create);
  const agents = useQuery(api.agents.list);

  const handleSubmit = async () => {
    const trimmed = title.trim();
    if (!trimmed) {
      setError("Task description required");
      return;
    }
    setError("");

    // Parse tags from comma-separated values after # symbol
    let taskTitle = trimmed;
    let tags: string[] | undefined;
    const hashIndex = trimmed.indexOf("#");
    if (hashIndex !== -1) {
      taskTitle = trimmed.substring(0, hashIndex).trim();
      const tagString = trimmed.substring(hashIndex + 1);
      tags = tagString.split(",").map((t) => t.trim()).filter((t) => t.length > 0);
    }

    const args: { title: string; tags?: string[]; assignedAgent?: string } = {
      title: taskTitle || trimmed,
      tags,
    };
    if (selectedAgent) {
      args.assignedAgent = selectedAgent;
    }

    await createTask(args);
    setTitle("");
    setSelectedAgent("");
    setIsExpanded(false);
  };

  // ... handleKeyDown, return JSX with Collapsible wrapper
}
```

### Convex Mutation Extension

```typescript
export const create = mutation({
  args: {
    title: v.string(),
    description: v.optional(v.string()),
    tags: v.optional(v.array(v.string())),
    assignedAgent: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const now = new Date().toISOString();
    const initialStatus = args.assignedAgent ? "assigned" : "inbox";

    const taskId = await ctx.db.insert("tasks", {
      title: args.title,
      description: args.description,
      status: initialStatus,
      assignedAgent: args.assignedAgent,
      trustLevel: "autonomous",
      tags: args.tags,
      createdAt: now,
      updatedAt: now,
    });

    const description = args.assignedAgent
      ? `Task created and assigned to ${args.assignedAgent}: "${args.title}"`
      : `Task created: "${args.title}"`;

    await ctx.db.insert("activities", {
      taskId,
      agentName: args.assignedAgent,
      eventType: "task_created",
      description,
      timestamp: now,
    });

    return taskId;
  },
});
```

### Layout of the Expanded Panel

```
┌────────────────────────────────────────────────────────┐
│ [  Create a new task...                    ] [Create] V │  <-- V = chevron
├────────────────────────────────────────────────────────┤
│ Agent:  [ Auto (Lead Agent)          v ]               │  <-- Select dropdown
│                                                        │
│ (Trust level and reviewer selectors added in Story 5.1)│
└────────────────────────────────────────────────────────┘
```

### Common LLM Developer Mistakes to Avoid

1. **DO NOT replace the existing TaskInput** — Extend it. The collapsed mode (type + enter) must continue to work exactly as before.

2. **DO NOT use a modal or dialog for the options** — Progressive disclosure uses a collapsible panel below the input, inline with the layout.

3. **DO NOT make agent selection required** — The default is "Auto (Lead Agent)" which means no agent is assigned and the Lead Agent routes it.

4. **DO NOT fetch agents inside the Select onChange** — Use `useQuery(api.agents.list)` at the component level. The query is reactive and cached.

5. **DO NOT forget to handle the case where no agents are registered** — If `agents` is empty or undefined, the Select should only show "Auto (Lead Agent)".

6. **DO NOT change the initial task status to "assigned" when no agent is selected** — Only when `assignedAgent` is explicitly provided should the status be "assigned". Default remains "inbox".

7. **DO NOT remove the existing tag parsing logic** — The `#` tag parsing must continue to work alongside the new agent selector.

### What This Story Does NOT Include

- **Trust level selector** — Added in Story 5.1
- **Reviewer selector** — Added in Story 5.1
- **Human approval checkbox** — Added in Story 5.1
- **Per-task timeout overrides** — Added in Story 7.3

### Files Created in This Story

| File | Purpose |
|------|---------|
| (none -- extends existing files) | |

### Files Modified in This Story

| File | Changes |
|------|---------|
| `dashboard/components/TaskInput.tsx` | Add progressive disclosure panel with agent selector |
| `dashboard/components/TaskInput.test.tsx` | Add tests for expanded panel and agent selection |
| `dashboard/convex/tasks.ts` | Extend `create` mutation with optional `assignedAgent` arg |

### Verification Steps

1. Click the chevron on TaskInput — verify the options panel expands
2. Verify the agent selector shows "Auto (Lead Agent)" as default
3. Verify registered agents appear in the dropdown
4. Select an agent, create a task — verify task is created with "assigned" status and that agent's name
5. Leave selector on "Auto", create a task — verify task is created with "inbox" status and no assignedAgent
6. After submission, verify the panel collapses and agent selection resets
7. Press Enter without expanding — verify default behavior (task created in inbox) still works
8. Run `cd dashboard && npx vitest run` — tests pass

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 4.4`] — Original story definition
- [Source: `_bmad-output/planning-artifacts/prd.md#FR2`] — Assign task to agent or leave for Lead Agent
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#Component Strategy`] — TaskInput progressive disclosure spec
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#User Journey Flows`] — Journey 3 progressive disclosure panel
- [Source: `dashboard/components/TaskInput.tsx`] — Existing component to extend
- [Source: `dashboard/convex/tasks.ts`] — Existing create mutation to extend
- [Source: `dashboard/convex/agents.ts`] — Existing agents.list query to reuse

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
- TypeScript check: `npx tsc --noEmit` passed with exit code 0
- Vitest: 14/14 tests passed (8 existing + 6 new)

### Completion Notes List
- Extended `tasks.create` mutation with optional `assignedAgent` arg (sets status to "assigned" when provided)
- Activity event includes agent name when assigned at creation
- Added progressive disclosure panel (Collapsible) with chevron toggle to TaskInput
- Added agent selector (Select) populated from `agents.list` query with "Auto (Lead Agent)" default
- Submission resets expanded state and agent selection
- Used value "auto" for the Auto option; only real agent names are passed as `assignedAgent`
- All existing tests preserved and passing; 6 new tests added

### File List
- `dashboard/convex/tasks.ts` — Extended `create` mutation with `assignedAgent` arg
- `dashboard/components/TaskInput.tsx` — Added progressive disclosure panel and agent selector
- `dashboard/components/TaskInput.test.tsx` — Added 6 new tests for expanded panel and agent selection
