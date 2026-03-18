# Story 2.7: Render Thread View in Real-Time

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to see the unified thread with structured agent messages and file references updating in real-time,
So that I can follow agent collaboration as it happens.

## Acceptance Criteria

1. **Thread displays all message types chronologically** — Given a task's thread has messages of various types (agent completion, user message, system error, lead agent plan, lead agent chat), when the user opens the task detail and navigates to the Thread tab, then all messages are displayed chronologically with: author (agent name with avatar initials, "User", or "System"), timestamp, message content, and artifacts if present (FR37).

2. **Structured completion messages render artifacts** — Given an agent posts a structured completion message with artifacts, when the ThreadMessage component renders it, then each artifact is displayed with: file path (styled as a monospace clickable reference), action badge ("created" in green or "modified" in blue or "deleted" in red), description (for created files), and diff preview (for modified files) rendered via the ArtifactRenderer component.

3. **Real-time message appearance within 1 second** — Given a new message is posted to the thread (by agent, user, or system), when the Convex reactive query fires, then the new message appears in the thread within 1 second (NFR4), and the thread auto-scrolls to the latest message.

4. **Auto-scroll pauses on user scroll-up** — Given the thread has many messages, when the user scrolls up to read older messages, then auto-scroll pauses, and when the user scrolls back to the bottom, auto-scroll resumes for subsequent new messages.

5. **Visual distinction between message authors** — Given messages from different authors appear in the thread, when they are rendered, then user messages have a blue-50 background, agent messages have a white/background color, system error messages have a red-tinted background with italic text, lead agent plan/chat messages have an indigo-tinted background, and review feedback messages retain their amber-50 background.

6. **Diff preview for modified files** — Given a structured completion message includes an artifact with `action: "modified"` and a `diff` field, when the ArtifactRenderer renders it, then the diff is displayed in a collapsible code block with syntax highlighting (using the existing `react-syntax-highlighter` / `oneDark` theme), collapsed by default to avoid overwhelming the thread.

7. **New message entrance animation** — Given a new message appears in the thread via real-time update, when it renders, then it fades in with a subtle animation (200ms) using Framer Motion, consistent with the existing animation patterns in StepCard and the UX spec.

## Tasks / Subtasks

- [x] **Task 1: Extend ThreadMessage to handle structured message types** (AC: 1, 5)
  - [x] 1.1 Refactor `getMessageStyles()` in `ThreadMessage.tsx` to handle the new `type` field values: `step_completion`, `user_message`, `system_error`, `lead_agent_plan`, `lead_agent_chat` — in addition to the existing `messageType` field values
  - [x] 1.2 Add visual distinction: `system_error` type gets `bg-red-50` background with italic text styling and an `AlertTriangle` icon; `lead_agent_plan` and `lead_agent_chat` get `bg-indigo-50` background with a "Plan" or "Chat" label badge
  - [x] 1.3 When a message has `type: "step_completion"`, display a step reference badge showing the step title (derived from `stepId`) below the author name
  - [x] 1.4 Render the `artifacts` array by delegating to the new `ArtifactRenderer` component (Task 2)

- [x] **Task 2: Create ArtifactRenderer component** (AC: 2, 6)
  - [x] 2.1 Create `dashboard/components/ArtifactRenderer.tsx` that accepts an array of artifact objects (`{ path, action, description?, diff? }`)
  - [x] 2.2 For each artifact, render: file path in monospace font (`font-mono text-xs`), an action badge using existing Badge component — "created" (green: `bg-green-100 text-green-700`), "modified" (blue: `bg-blue-100 text-blue-700`), "deleted" (red: `bg-red-100 text-red-700`)
  - [x] 2.3 For created files with a `description`, render the description text below the file path in `text-xs text-muted-foreground`
  - [x] 2.4 For modified files with a `diff`, render a collapsible diff section using the existing `Collapsible` ShadCN component — collapsed by default, expand/collapse toggle shows "Show diff" / "Hide diff"
  - [x] 2.5 Inside the diff collapsible, render the diff content using `react-syntax-highlighter` with `oneDark` theme and `diff` language, matching the existing `CodeBlock` pattern in `MarkdownRenderer.tsx`
  - [x] 2.6 File paths are rendered as styled spans with `cursor-pointer hover:underline text-blue-500` to indicate clickability (actual navigation is out of scope for this story — future file viewer integration)

- [x] **Task 3: Implement auto-scroll with pause-on-scroll-up** (AC: 3, 4)
  - [x] 3.1 In `TaskDetailSheet.tsx`, replace the simple `scrollToBottom` / `useEffect` with a scroll behavior manager that tracks whether the user is at the bottom of the scroll area
  - [x] 3.2 Use an `IntersectionObserver` on the `threadEndRef` sentinel div — when the sentinel is visible, the user is "at bottom" and auto-scroll is active; when the sentinel is not visible (user scrolled up), auto-scroll pauses
  - [x] 3.3 When a new message arrives (detected via `messages?.length` change) and auto-scroll is active, scroll to the bottom smoothly
  - [x] 3.4 When auto-scroll is paused (user scrolled up), do NOT scroll on new messages — let the user continue reading

- [x] **Task 4: Add Framer Motion entrance animation for new messages** (AC: 7)
  - [x] 4.1 Wrap each `ThreadMessage` in the thread list with a `motion.div` from `motion/react-client` (matching the import pattern used in `StepCard.tsx`)
  - [x] 4.2 Apply `initial={{ opacity: 0, y: 8 }}`, `animate={{ opacity: 1, y: 0 }}`, `transition={{ duration: 0.2 }}` for a subtle fade-in-and-slide-up effect
  - [x] 4.3 Respect `useReducedMotion()` — if reduced motion is preferred, set `transition={{ duration: 0 }}` (matching the `StepCard.tsx` pattern)

- [x] **Task 5: Add constants for structured message types** (AC: 1, 5)
  - [x] 5.1 In `dashboard/lib/constants.ts`, add a `STRUCTURED_MESSAGE_TYPE` constant object with values: `STEP_COMPLETION`, `USER_MESSAGE`, `SYSTEM_ERROR`, `LEAD_AGENT_PLAN`, `LEAD_AGENT_CHAT`
  - [x] 5.2 Add a `StructuredMessageType` TypeScript type derived from the constant
  - [x] 5.3 Add an `ARTIFACT_ACTION` constant object with values: `CREATED`, `MODIFIED`, `DELETED`
  - [x] 5.4 Add an `ArtifactAction` TypeScript type derived from the constant

- [x] **Task 6: Write tests for ThreadMessage and ArtifactRenderer** (AC: 1, 2, 5, 6)
  - [x] 6.1 Add test cases to `ThreadMessage.test.tsx` (create if not exists) covering: agent message rendering, user message styling, system error styling, lead agent plan/chat styling, step_completion message with artifacts delegation
  - [x] 6.2 Create `ArtifactRenderer.test.tsx` with test cases: renders file paths with action badges, renders description for created files, renders collapsible diff for modified files, handles empty artifacts array, handles artifacts without optional fields

## Dev Notes

### Critical: Two Message Type Fields — `messageType` vs `type`

**The biggest implementation pitfall is understanding that messages have TWO type fields:**

| Field | Purpose | Values | Origin |
|-------|---------|--------|--------|
| `messageType` | Legacy/original classification | `"work"`, `"review_feedback"`, `"approval"`, `"denial"`, `"system_event"`, `"user_message"` | Existing — used by current `ThreadMessage.tsx` |
| `type` | New structured classification | `"step_completion"`, `"user_message"`, `"system_error"`, `"lead_agent_plan"`, `"lead_agent_chat"` | Added in Story 1.1 — optional field |

**DECISION:** `ThreadMessage` must handle BOTH fields. The rendering logic should prefer `type` when present (new structured messages), and fall back to `messageType` for backward compatibility (existing messages that don't have `type`). This means the `getMessageStyles()` function needs a two-pass approach:

```typescript
function getMessageStyles(message: Doc<"messages">) {
  // Prefer new structured type if present
  if (message.type) {
    switch (message.type) {
      case "step_completion": return { bg: "bg-background", label: "Step Complete", labelColor: "text-green-600" };
      case "system_error": return { bg: "bg-red-50", label: "Error", labelColor: "text-red-600" };
      case "lead_agent_plan": return { bg: "bg-indigo-50", label: "Plan", labelColor: "text-indigo-600" };
      case "lead_agent_chat": return { bg: "bg-indigo-50", label: "Chat", labelColor: "text-indigo-600" };
      case "user_message": return { bg: "bg-blue-50", label: null, labelColor: "" };
    }
  }
  // Fall back to legacy messageType
  return getlegacyMessageStyles(message.messageType, message.authorType);
}
```

### Existing Code That Touches This Story

| File | What exists | What changes |
|------|-------------|--------------|
| `dashboard/components/ThreadMessage.tsx` | Renders messages with `messageType`-based styling, avatar, author name, timestamp, markdown content | EXTEND: handle `type` field, render `artifacts` via ArtifactRenderer, add step_completion / system_error / lead_agent visual variants |
| `dashboard/components/TaskDetailSheet.tsx` | Thread tab with `ScrollArea`, simple `scrollToBottom` via `threadEndRef`, `useEffect` on `messages?.length` | EXTEND: replace naive auto-scroll with IntersectionObserver-based pause-on-scroll-up behavior, wrap messages in motion.div |
| `dashboard/components/ThreadInput.tsx` | User message input with agent selector, send mutation | No changes — already functional |
| `dashboard/components/MarkdownRenderer.tsx` | Renders markdown with syntax highlighting via `react-syntax-highlighter` + `oneDark` | No changes — reused as-is for message content; pattern reference for diff rendering |
| `dashboard/convex/messages.ts` | `listByTask` query, `create` mutation, `sendThreadMessage` mutation | No changes — the reactive query already returns all message fields including `type`, `stepId`, `artifacts` |
| `dashboard/convex/schema.ts` | Messages table with `type`, `stepId`, `artifacts` fields (added in Story 1.1) | No changes |
| `dashboard/lib/constants.ts` | `MESSAGE_TYPE`, `AUTHOR_TYPE` constants | EXTEND: add `STRUCTURED_MESSAGE_TYPE`, `ARTIFACT_ACTION` constants and types |
| `dashboard/components/ArtifactRenderer.tsx` | Does not exist | NEW — renders file paths, action badges, descriptions, and collapsible diffs |

### Architecture Patterns to Follow

1. **Component composition:** `ThreadMessage` composes `ArtifactRenderer` — ThreadMessage handles message-level rendering (avatar, author, timestamp, content), ArtifactRenderer handles the artifact list within a message
2. **ShadCN component usage:** `Badge` for action labels, `Collapsible` + `CollapsibleTrigger` + `CollapsibleContent` for diff toggle, `Avatar` + `AvatarFallback` for author
3. **Framer Motion pattern:** Import from `motion/react-client` (not `framer-motion` — the project uses the `motion` package v12+). Use `useReducedMotion()` from `motion/react` for accessibility
4. **Reactive queries:** The `useQuery(api.messages.listByTask, ...)` in `TaskDetailSheet.tsx` is already reactive — Convex automatically pushes new messages to the client. No polling or manual refresh needed. NFR4 compliance comes from Convex's built-in reactivity
5. **Color palette:** Use the established color tokens from `constants.ts` and the UX spec — `bg-blue-50` for user, `bg-red-50` for errors, `bg-indigo-50` for lead agent, `bg-amber-50` for review feedback, `bg-background` for standard agent messages
6. **Typography:** Thread messages use `text-sm` for content, `text-xs` for metadata (author name, timestamp, action badges, file paths) per the UX spec typography scale
7. **File naming:** One component per file, PascalCase — `ArtifactRenderer.tsx`

### ArtifactRenderer Component Design

```typescript
interface Artifact {
  path: string;
  action: "created" | "modified" | "deleted";
  description?: string;
  diff?: string;
}

interface ArtifactRendererProps {
  artifacts: Artifact[];
}
```

**Rendering layout per artifact:**

```
┌─────────────────────────────────────────────┐
│ 📄 /output/invoice-summary.csv   [created]  │
│ Structured JSON with 47 invoice entries      │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ 📄 /output/reconciliation.xlsx   [modified]  │
│ ▶ Show diff                                  │
│ ┌─────────────────────────────────────────┐  │
│ │ + matched: 44/47 entries                │  │
│ │ + flagged: 3 unmatched                  │  │
│ └─────────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

Each artifact card should be a compact row with:
- File icon (use `FileCode` or `FileText` from lucide based on extension, matching the pattern in `TaskDetailSheet.tsx`)
- File path in `font-mono text-xs text-blue-500 cursor-pointer hover:underline`
- Action badge: `Badge` with `variant="secondary"` and action-specific colors
- Description below in `text-xs text-muted-foreground` (if present)
- Collapsible diff below (if present)

### Auto-Scroll Implementation

The current implementation in `TaskDetailSheet.tsx` (lines 76-84) naively scrolls to bottom on every message change:

```typescript
const scrollToBottom = useCallback(() => {
  threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
}, []);

useEffect(() => {
  if (messages && messages.length > 0) {
    scrollToBottom();
  }
}, [messages?.length, scrollToBottom]);
```

**Replace with IntersectionObserver pattern:**

```typescript
const [isAtBottom, setIsAtBottom] = useState(true);
const threadEndRef = useRef<HTMLDivElement>(null);

// Track if user is at bottom via IntersectionObserver
useEffect(() => {
  const sentinel = threadEndRef.current;
  if (!sentinel) return;
  const observer = new IntersectionObserver(
    ([entry]) => setIsAtBottom(entry.isIntersecting),
    { threshold: 0.1 }
  );
  observer.observe(sentinel);
  return () => observer.disconnect();
}, []);

// Auto-scroll only when at bottom and new messages arrive
useEffect(() => {
  if (isAtBottom && messages && messages.length > 0) {
    threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }
}, [messages?.length, isAtBottom]);
```

**Key:** The `ScrollArea` component from ShadCN is a Radix primitive that creates its own scrollable viewport. The IntersectionObserver needs to observe within that viewport. If needed, set the `root` option of IntersectionObserver to the ScrollArea's viewport element — test this during implementation. Alternatively, if IntersectionObserver works without specifying root (observing within the nearest scrollable ancestor), use the simpler approach above.

### ThreadMessage Component Extension

The existing `ThreadMessage.tsx` is compact (80 lines). The extension should:

1. Keep backward compatibility with all existing `messageType` values
2. Add new rendering paths for `type` values when present
3. Delegate artifact rendering to `ArtifactRenderer`
4. Add step reference display for `step_completion` messages

**Step reference display:** When a message has `type: "step_completion"` and a `stepId`, the component should show a small label like "Step 1: Extract invoice data" below the author name. However, the message document only contains `stepId` (a Convex ID), not the step title. Two options:

- **Option A (recommended):** Pass step data from the parent. `TaskDetailSheet` already queries `liveSteps` via `api.steps.getByTask`. Pass the steps array to `ThreadMessage` (or a lookup map) so it can resolve `stepId` to step title without an additional query.
- **Option B:** Have `ThreadMessage` call `useQuery` for the step. This creates N queries for N messages — inefficient.

**Go with Option A.** Extend `ThreadMessageProps` to accept an optional `steps` array or `stepMap` for title resolution.

### Testing Strategy

- **Unit tests (vitest):** Test `ThreadMessage` rendering for each message type variant. Test `ArtifactRenderer` with various artifact configurations (created with description, modified with diff, deleted, empty array). Mock Convex `Doc` type for messages.
- **Existing test pattern:** Check if `ThreadMessage.test.tsx` exists — if not, create it. Follow the testing pattern from `StepCard.test.tsx` or `KanbanBoard.test.tsx`.
- **No E2E tests:** The real-time behavior (Convex reactive queries, auto-scroll) is best verified manually. The IntersectionObserver behavior is a browser API not easily tested in vitest.
- **Manual verification:** Open task detail, watch messages appear in real-time as agents post. Scroll up — verify no auto-scroll. Scroll back down — verify auto-scroll resumes.

### Dependencies on Prior Stories

| Story | Dependency | Status |
|-------|-----------|--------|
| 1.1 | Messages schema with `type`, `stepId`, `artifacts` fields | done |
| 2.4 | User posts messages to thread (ThreadInput already works) | Existing functionality — ThreadInput is already implemented |
| 2.5 | Agents post structured completion messages with artifacts | Must be complete before artifacts can be tested with real data; but component can be built and tested with mock data |

### Framer Motion Import Pattern

From `StepCard.tsx` (the project's established pattern):

```typescript
import * as motion from "motion/react-client";
import { useReducedMotion } from "motion/react";
```

NOT the older `framer-motion` package. The project uses the `motion` package v12+.

### Git Intelligence (Recent Commits)

```
830fd64 fix card ui
e685c07 Fix Design broken
acc0318 wip: alinhamento do design da dashboard
823f0a7 feat: Implement cron job task linking and output file syncing
479bc23 feat: highlight prompt variables with amber color
```

Recent work has been UI-focused. No conflicts expected with ThreadMessage/ArtifactRenderer changes. The ThreadMessage.tsx and TaskDetailSheet.tsx files are modified in the current branch (novo-plano) — coordinate carefully.

### Project Structure Notes

- **Modified files:** `ThreadMessage.tsx` (extend), `TaskDetailSheet.tsx` (extend auto-scroll + animation), `constants.ts` (add structured message type constants)
- **New file:** `ArtifactRenderer.tsx` — renders file paths, action badges, descriptions, and collapsible diffs
- **New test file:** `ArtifactRenderer.test.tsx`
- **Possible new test file:** `ThreadMessage.test.tsx` (if it does not already exist)
- **No backend changes** — this story is entirely frontend/dashboard
- **No Convex changes** — schema and queries already support the required fields from Story 1.1

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 2 Story 2.7] — Full acceptance criteria from epic breakdown
- [Source: _bmad-output/planning-artifacts/architecture.md#Unified Thread] — ThreadMessage structured format, ArtifactRenderer component definition, FR-to-file mapping
- [Source: _bmad-output/planning-artifacts/architecture.md#Structured Completion Message Format] — ThreadMessage type definition with artifacts array
- [Source: _bmad-output/planning-artifacts/prd.md#FR37] — Thread view shows structured agent messages with file path references in real-time
- [Source: _bmad-output/planning-artifacts/prd.md#NFR4] — Thread messages appear within 1 second of being posted to Convex
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#ThreadMessage] — Message variant styling (blue-50 for user, white for agent, amber-50 for review, gray-50 for system)
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Real-Time Update Patterns] — Auto-scroll rules, anti-disruption patterns, fade-in animation timing (200ms)
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#TaskDetailSheet] — Thread tab specification, newest-at-bottom, tabs layout
- [Source: dashboard/components/ThreadMessage.tsx] — Existing ThreadMessage implementation (80 lines)
- [Source: dashboard/components/TaskDetailSheet.tsx] — Existing thread tab with ScrollArea and naive auto-scroll
- [Source: dashboard/components/MarkdownRenderer.tsx] — CodeBlock pattern with react-syntax-highlighter + oneDark theme
- [Source: dashboard/components/StepCard.tsx] — Framer Motion import pattern and reduced motion handling
- [Source: dashboard/convex/schema.ts#messages] — Messages table with type, stepId, artifacts fields
- [Source: dashboard/convex/messages.ts#listByTask] — Reactive query returning all message fields
- [Source: dashboard/lib/constants.ts] — Existing constant patterns, MESSAGE_TYPE, AUTHOR_TYPE
