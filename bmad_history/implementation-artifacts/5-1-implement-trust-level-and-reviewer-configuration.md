# Story 5.1: Implement Trust Level and Reviewer Configuration

Status: done

## Story

As a **user**,
I want to configure how much oversight a task gets when I create it,
So that I can balance speed (autonomous) with quality (reviewed) and control (human-approved).

## Acceptance Criteria

1. **Given** the TaskInput progressive disclosure panel is open (Story 4.4), **When** the user views the expanded options, **Then** a trust level selector shows three options: "Autonomous" (default), "Agent Reviewed", "Human Approved" (FR3)
2. **Given** "Agent Reviewed" or "Human Approved" is selected, **Then** a reviewer selector appears showing registered agents with multi-select capability (FR4)
3. **Given** "Human Approved" is selected, **Then** a checkbox "Require human approval" is checked and visible
4. **Given** the user creates a task with trust level "agent_reviewed" and reviewers ["secretario"], **When** the task is submitted, **Then** the task is created in Convex with `trustLevel: "agent_reviewed"` and `reviewers: ["secretario"]`
5. **Given** the user creates a task with trust level "autonomous", **When** the task completes, **Then** the task moves directly to "done" without entering review
6. **Given** the TaskCard renders a task with review configured, **Then** the card shows a small review indicator icon (circular arrows or shield icon) visible at a glance
7. **And** trust level and reviewer fields are stored on the task in Convex (already in schema)
8. **And** the progressive disclosure panel in `TaskInput.tsx` includes trust level `Select`, reviewer multi-select, and human approval `Checkbox`
9. **And** the Convex `tasks.create` mutation is extended to accept `trustLevel` and `reviewers` arguments
10. **And** Vitest tests exist for the trust level and reviewer configuration UI

## Tasks / Subtasks

- [ ] Task 1: Extend the Convex `tasks.create` mutation (AC: #4, #9)
  - [ ] 1.1: Add `trustLevel: v.optional(v.string())` to the `create` mutation args (defaults to "autonomous" in handler)
  - [ ] 1.2: Add `reviewers: v.optional(v.array(v.string()))` to the `create` mutation args
  - [ ] 1.3: Store both fields on the task document
  - [ ] 1.4: Include trust level in the activity event description when not autonomous

- [ ] Task 2: Add trust level selector to TaskInput (AC: #1, #8)
  - [ ] 2.1: Add a `Select` component for trust level in the progressive disclosure panel (below the agent selector from Story 4.4)
  - [ ] 2.2: Options: "Autonomous" (value: "autonomous"), "Agent Reviewed" (value: "agent_reviewed"), "Human Approved" (value: "human_approved")
  - [ ] 2.3: Default to "autonomous"
  - [ ] 2.4: Label the selector with "Trust Level" text (`text-xs text-slate-500 font-medium`)
  - [ ] 2.5: Track selected trust level with `useState<string>("autonomous")`

- [ ] Task 3: Add reviewer multi-select (AC: #2, #3)
  - [ ] 3.1: When trust level is "agent_reviewed" or "human_approved", show a reviewer selector below the trust level selector
  - [ ] 3.2: Use a multi-select pattern: render registered agents as checkboxes or use a ShadCN-compatible multi-select (since ShadCN Select is single-select)
  - [ ] 3.3: Implementation option: render agent names as a list of `Checkbox` items, each toggling that agent as a reviewer
  - [ ] 3.4: Track selected reviewers with `useState<string[]>([])`
  - [ ] 3.5: When trust level is "human_approved", show a checked, read-only `Checkbox` labeled "Require human approval" to confirm the gate is active
  - [ ] 3.6: When trust level changes back to "autonomous", clear selected reviewers

- [ ] Task 4: Update submission logic (AC: #4, #5)
  - [ ] 4.1: Include `trustLevel` in the mutation call (only if not "autonomous" — or always include it for clarity)
  - [ ] 4.2: Include `reviewers` in the mutation call when reviewers are selected
  - [ ] 4.3: After submission, reset trust level to "autonomous" and reviewers to `[]`

- [ ] Task 5: Add review indicator to TaskCard (AC: #6)
  - [ ] 5.1: Update `dashboard/components/TaskCard.tsx` to check if `task.trustLevel !== "autonomous"` or `task.reviewers?.length > 0`
  - [ ] 5.2: If review is configured, show a small icon (e.g., `Shield` or `RefreshCw` from Lucide) with `text-xs text-amber-500`
  - [ ] 5.3: If trust level is "human_approved", additionally show a small "HITL" text badge

- [ ] Task 6: Write Vitest tests (AC: #10)
  - [ ] 6.1: Test trust level selector renders with 3 options
  - [ ] 6.2: Test selecting "Agent Reviewed" shows reviewer selector
  - [ ] 6.3: Test selecting "Autonomous" hides reviewer selector
  - [ ] 6.4: Test submitting with trust level and reviewers passes correct args to mutation
  - [ ] 6.5: Test TaskCard shows review indicator when trustLevel is not autonomous

## Dev Notes

### Critical Architecture Requirements

- **Trust level and reviewers are already in the Convex schema**: The `tasks` table already has `trustLevel` (union of "autonomous" | "agent_reviewed" | "human_approved") and `reviewers` (optional array of strings). No schema changes needed.
- **The `tasks.create` mutation currently hardcodes `trustLevel: "autonomous"`**: This story changes it to accept the trust level as an argument.
- **Review routing is NOT implemented here**: This story only adds the UI for configuring trust level and reviewers at creation time. The actual review routing (sending work to reviewers) is Story 5.2 and 5.3.
- **The human approval gate** is not enforced here — that's Story 6.1. This story just stores the configuration.

### Layout of the Extended Progressive Disclosure Panel

```
┌────────────────────────────────────────────────────────┐
│ [  Create a new task...                    ] [Create] V │
├────────────────────────────────────────────────────────┤
│ Agent:       [ Auto (Lead Agent)          v ]          │  <-- Story 4.4
│ Trust Level: [ Autonomous                 v ]          │  <-- This story
│                                                        │
│ (When "Agent Reviewed" or "Human Approved" selected:)  │
│ Reviewers:                                             │
│   [x] secretario                                       │
│   [ ] pesquisador                                      │
│   [ ] financeiro                                       │
│                                                        │
│ (When "Human Approved" selected:)                      │
│   [x] Require human approval  (read-only checked)      │
└────────────────────────────────────────────────────────┘
```

### Multi-Select Pattern for Reviewers

ShadCN does not have a built-in multi-select. The simplest approach is to render checkboxes:

```tsx
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";

// Inside the options panel, when trustLevel is not "autonomous":
{agents?.map((agent) => (
  <div key={agent.name} className="flex items-center gap-2">
    <Checkbox
      id={`reviewer-${agent.name}`}
      checked={selectedReviewers.includes(agent.name)}
      onCheckedChange={(checked) => {
        setSelectedReviewers((prev) =>
          checked
            ? [...prev, agent.name]
            : prev.filter((r) => r !== agent.name)
        );
      }}
    />
    <Label htmlFor={`reviewer-${agent.name}`} className="text-sm">
      {agent.displayName || agent.name}
    </Label>
  </div>
))}
```

### Trust Level Select Pattern

```tsx
<div className="space-y-1">
  <label className="text-xs text-slate-500 font-medium">Trust Level</label>
  <Select value={trustLevel} onValueChange={(val) => {
    setTrustLevel(val);
    if (val === "autonomous") setSelectedReviewers([]);
  }}>
    <SelectTrigger className="h-9">
      <SelectValue />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="autonomous">Autonomous</SelectItem>
      <SelectItem value="agent_reviewed">Agent Reviewed</SelectItem>
      <SelectItem value="human_approved">Human Approved</SelectItem>
    </SelectContent>
  </Select>
</div>
```

### TaskCard Review Indicator

```tsx
import { Shield, RefreshCw } from "lucide-react";

// Inside TaskCard, after tags:
{task.trustLevel !== "autonomous" && (
  <div className="flex items-center gap-1 mt-1">
    <RefreshCw className="h-3 w-3 text-amber-500" />
    {task.trustLevel === "human_approved" && (
      <span className="text-[10px] font-medium text-amber-600 bg-amber-50 px-1 rounded">
        HITL
      </span>
    )}
  </div>
)}
```

### Common LLM Developer Mistakes to Avoid

1. **DO NOT add trust level validation in the frontend** — The Convex schema already validates trust level values via the `v.union()` validator. Let Convex handle it.

2. **DO NOT implement review routing here** — This story only stores the configuration. The actual routing of completed work to reviewers is Story 5.2.

3. **DO NOT make trust level required in the mutation** — It should be optional with a default of "autonomous" in the handler, so existing callers (CLI, tests) don't break.

4. **DO NOT use a custom multi-select library** — Checkboxes are simpler, more accessible, and sufficient for 3-5 agents.

5. **DO NOT show the reviewer section when trust level is "autonomous"** — Progressive disclosure: reviewer selection only appears when review is configured.

6. **DO NOT forget to reset state after submission** — Trust level, reviewers, and the expanded panel must all reset to defaults after creating a task.

### What This Story Does NOT Include

- **Review routing** — Sending completed work to reviewers is Story 5.2
- **Review feedback flow** — Reviewer providing feedback is Story 5.3
- **HITL approval enforcement** — The approve/deny buttons are Story 6.1 and 6.2
- **Per-task timeout overrides** — Story 7.3 adds timeout config to this panel

### Files Created in This Story

| File | Purpose |
|------|---------|
| (none -- extends existing files) | |

### Files Modified in This Story

| File | Changes |
|------|---------|
| `dashboard/components/TaskInput.tsx` | Add trust level selector, reviewer checkboxes, human approval indicator |
| `dashboard/components/TaskInput.test.tsx` | Add tests for trust/reviewer configuration |
| `dashboard/components/TaskCard.tsx` | Add review indicator icon |
| `dashboard/convex/tasks.ts` | Extend `create` mutation with `trustLevel` and `reviewers` args |

### Verification Steps

1. Expand TaskInput options — verify trust level selector shows 3 options
2. Select "Agent Reviewed" — verify reviewer checkboxes appear
3. Select "Autonomous" — verify reviewer section hides
4. Select "Human Approved" — verify "Require human approval" checkbox appears (checked)
5. Create a task with trust "agent_reviewed" and reviewer "secretario" — verify Convex doc has correct fields
6. Create an autonomous task — verify trustLevel is "autonomous" with no reviewers
7. Verify TaskCard shows review icon for non-autonomous tasks
8. Verify TaskCard shows "HITL" badge for human_approved tasks
9. Run `cd dashboard && npx vitest run` — tests pass

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 5.1`] — Original story definition
- [Source: `_bmad-output/planning-artifacts/prd.md#FR3`] — Per-task trust level
- [Source: `_bmad-output/planning-artifacts/prd.md#FR4`] — Configure specific reviewer agents
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#Component Strategy`] — TaskInput progressive disclosure spec
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#User Journey Flows`] — Journey 3 review configuration
- [Source: `dashboard/convex/schema.ts`] — Tasks table already has trustLevel and reviewers fields
- [Source: `dashboard/components/TaskInput.tsx`] — Existing component to extend
- [Source: `dashboard/lib/constants.ts`] — TRUST_LEVEL constants

## Dev Agent Record

### Agent Model Used
claude-opus-4-6

### Debug Log References
- All 34 tests pass (14 TaskCard + 20 TaskInput)
- Pre-existing TS error in listByStatus (line 129) — `args.status` string not assignable to status union. Not introduced by this story.

### Completion Notes List
- Extended `tasks.create` mutation with optional `trustLevel` and `reviewers` args (defaults to "autonomous")
- Activity event description includes trust level label when not autonomous
- Added trust level Select with 3 options (Autonomous, Agent Reviewed, Human Approved) to TaskInput progressive disclosure panel
- Added reviewer multi-select via Checkbox list, shown only when trust level is not autonomous
- Added read-only "Require human approval" checkbox when trust level is human_approved
- State resets (trustLevel, reviewers) on submission and when switching back to autonomous
- Added RefreshCw review indicator icon on TaskCard for non-autonomous tasks
- Added HITL badge on TaskCard for human_approved tasks
- 6 new tests: trust level selector rendering, reviewer show/hide, human approval checkbox, submission with trust+reviewers, review indicator, HITL badge

### File List
- `dashboard/convex/tasks.ts` — Extended create mutation with trustLevel and reviewers args
- `dashboard/components/TaskInput.tsx` — Trust level selector, reviewer checkboxes, human approval indicator
- `dashboard/components/TaskInput.test.tsx` — 6 new tests for trust/reviewer UI
- `dashboard/components/TaskCard.tsx` — Review indicator icon + HITL badge
- `dashboard/components/TaskCard.test.tsx` — 3 new tests for review indicator
