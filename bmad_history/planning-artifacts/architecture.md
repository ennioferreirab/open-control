---
stepsCompleted:
  - step-01-init
  - step-02-context
  - step-03-starter
  - step-04-decisions
  - step-05-patterns
  - step-06-structure
  - step-07-validation
  - step-08-complete
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
  - _bmad-output/planning-artifacts/epics.md
  - _bmad-output/planning-artifacts/prd-thread-files-context.md
  - _bmad-output/planning-artifacts/prd-thread-files-context-validation.md
  - _bmad-output/planning-artifacts/architecture-backup-2026-02-24.md
workflowType: 'architecture'
project_name: 'nanobot-ennio'
user_name: 'Ennio'
date: '2026-02-24'
lastStep: 8
status: 'complete'
completedAt: '2026-02-24'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**

38 FRs across 7 categories (core orchestration) + 29 FRs across 7 categories (file layer):

| Category | FRs | Architectural Implication |
|----------|-----|--------------------------|
| Task & Step Management (FR1-FR5) | 5 | Task/Step parent-child data model — Task is the goal, Steps are work units. Steps are Kanban cards grouped under parent Task. Supervision mode (autonomous/supervised) selected per task. |
| Execution Planning (FR6-FR10) | 5 | Lead Agent generates execution plans with steps, agent assignments, dependencies, and parallel groups. General Agent is always-present fallback. File metadata informs routing. |
| Pre-Kickoff Plan Review (FR11-FR18) | 8 | Supervised mode opens pre-kickoff modal for plan negotiation — reassign agents, reorder steps, change dependencies, attach documents per step, chat with Lead Agent. Most complex UI surface. |
| Agent Orchestration & Dispatch (FR19-FR23) | 5 | Pure orchestrator invariant: Lead Agent never executes. Parallel steps as separate subprocesses via asyncio.gather(). Completion auto-unblocks dependents. |
| Unified Thread & Communication (FR24-FR28) | 5 | Single thread per task shared by all agents + user. Structured completion messages (file paths, diffs, descriptions). Thread is the ONLY inter-agent channel. Context truncation to 20 messages for LLM windows. |
| Step Lifecycle & Error Handling (FR29-FR34) | 6 | Step lifecycle: assigned → running → completed/crashed. Crash isolation — doesn't cascade to siblings/parent. Manual retry with auto-unblock. Error messages in thread with recovery instructions. |
| Dashboard & Visualization (FR35-FR38) | 4 | Kanban with real-time step status, execution plan visualization, thread view with structured messages, activity feed for step events. |
| File Attachment (Thread Files) | 5 | Task directories with attachments/ and output/ subdirs. File picker at creation + on existing tasks. File manifest on task record. |
| File Viewing (Thread Files) | 9 | Multi-format viewer modal (PDF, code, HTML, Markdown, images, text). File serving API. Type detection. Download. |
| File Serving (Thread Files) | 2 | Next.js API routes for filesystem-to-browser file serving. MIME type detection. |
| Agent File Context (Thread Files) | 5 | Agent receives filesDir path + fileManifest. Reads attachments, writes to output. Manifest auto-sync. |
| File Manifest Management (Thread Files) | 4 | Convex stores file metadata. Reactive manifest updates on upload and agent output. |
| Task Card File Indicators (Thread Files) | 2 | Paperclip icon + file count on Kanban cards. |
| Lead Agent File Awareness (Thread Files) | 2 | File manifest in routing context. File metadata in delegation messages. |

**Non-Functional Requirements:**

13 NFRs across 3 categories (core) + 13 NFRs across 3 categories (file layer):

| Category | NFRs | Key Constraints |
|----------|------|----------------|
| Performance (NFR1-NFR5) | 5 | Plan generation < 10s, pre-kickoff modal < 2s, Kanban updates < 1s, thread messages < 1s, thread truncation to 20 messages |
| Reliability (NFR6-NFR10) | 5 | Crash isolation per step, graceful LLM provider error recovery, subprocess isolation, atomic dependency unblocking, planning failures surface as errors |
| Integration (NFR11-NFR13) | 3 | Bridge persistent connection + auto-reconnect, LLM timeout + retry, consistent structured message format |
| File Performance (NFR1-NFR5) | 5 | Upload < 3s for 10MB, file list < 1s, viewer < 2s, PDF nav < 500ms, file serving < 1s |
| File Reliability (NFR10-NFR13) | 4 | Atomic directory creation, manifest reconcilable with filesystem, no partial files on failure, viewer fallback for unsupported types |
| File Integration (NFR6-NFR9) | 4 | Manifest reflects upload < 2s, agent output < 5s, fresh manifest per context fetch, reactive dashboard display |

**Scale & Complexity:**

- Primary domain: Full-stack (Next.js/TypeScript dashboard + Python/AsyncIO backend + Convex real-time BaaS)
- Complexity level: Medium-High
- Estimated architectural components: ~18-22 distinct modules spanning two runtimes
- Single-user localhost deployment — no auth, no multi-tenancy, no SEO

### Technical Constraints & Dependencies

- **Brownfield:** Extends existing nanobot framework — the Lead Agent planner (planner.py), orchestrator (orchestrator.py), execution plan visualization (ExecutionPlanTab), inter-agent messaging, and file-aware routing already exist and will be refactored
- **Dual runtime:** Python/AsyncIO (agent orchestration, subprocess management) + Node.js/Next.js (dashboard) — the AsyncIO-Convex bridge remains the critical integration seam
- **Convex as real-time backend:** Reactive queries, transactional mutations, persistent storage — source of truth for all shared state
- **One-directional data flow:** nanobot writes → Convex stores → dashboard reads. Dashboard user actions go through Convex mutations
- **ShadCN UI + Tailwind CSS:** Component library and design system established in UX spec
- **Existing executor pattern:** `_build_thread_context()` in executor.py already truncates to last 20 messages with omission note — architecture must preserve and extend this
- **Agent subprocess model:** Each agent runs as a separate Python subprocess. Parallel steps use `asyncio.gather()` for true concurrency
- **No authentication:** Single-user tool runs locally — simplified from old architecture
- **Task directory convention:** `~/.nanobot/tasks/{task-id}/attachments/` and `output/` for file layer

### Cross-Cutting Concerns Identified

- **State consistency (Task/Step hierarchy):** Task and Step state must be identical across nanobot runtime, Convex, and dashboard. The bridge synchronizes. Convex is source of truth. The parent-child relationship (Task has Steps) adds a new dimension to state tracking.
- **Thread context management:** The unified thread accumulates structured completion messages (diffs, file paths, descriptions) that are denser than conversational messages. Context truncation, token awareness, and selective injection matter for LLM cost and quality.
- **Error isolation:** Step-level crash handling must not cascade — a crashed step blocks dependents but doesn't crash siblings, the parent task, or the system. Provider errors (OAuth, rate limits) must surface as actionable recovery messages.
- **Dependency management:** Auto-unblocking when prerequisites complete, parallel dispatch, blocking chains — all require reliable, atomic state transitions.
- **File integration:** File context in agent prompts (filesDir + manifest), manifest sync between filesystem and Convex, file serving from filesystem to browser.
- **Observability:** Activity feed for step events, thread as the human-readable record of all agent work, structured messages for both agent and human consumption.
- **Graceful lifecycle:** Start/stop across multiple processes (Next.js, Convex dev, agent gateway). Subprocess cleanup on shutdown.

## Starter Template Evaluation

### Primary Technology Domain

Full-stack: Next.js/TypeScript (dashboard SPA) + Python/AsyncIO (nanobot backend, brownfield) + Convex (real-time BaaS)

### Starter: Already Initialized (Brownfield)

The dashboard was initialized from `get-convex/template-nextjs-shadcn` and is a mature, working application with 47 component files, full Convex schema, and test coverage.

**No new starter template needed.** The new architecture extends and refactors existing code.

**Current Installed Stack:**

| Package | Version |
|---------|---------|
| Next.js | ^16.1.5 |
| React | ^19.2.4 |
| Convex | ^1.31.6 |
| TypeScript | ^5 |
| Tailwind CSS | ^3.4.1 |
| Motion | ^12.34.3 |
| Vitest | ^4.0.18 |
| react-pdf | ^10.4.0 |
| react-syntax-highlighter | ^16.1.0 |
| react-markdown | ^10.1.0 |

**Existing Components Relevant to New Architecture:**

| Component | Current State | New Architecture Impact |
|-----------|--------------|------------------------|
| `ExecutionPlanTab.tsx` | Shows execution plan | Refactor for Task/Step hierarchy with dependency visualization |
| `ThreadMessage.tsx` / `ThreadInput.tsx` | Thread messaging | Extend for structured completion messages (file paths, diffs, descriptions) |
| `DocumentViewerModal.tsx` | Multi-format file viewer | Already complete — reused as-is |
| `KanbanBoard.tsx` / `TaskCard.tsx` | Task cards on Kanban | Refactor: Steps become cards, grouped under parent Task |
| `TaskDetailSheet.tsx` | Task detail panel | Add pre-kickoff modal integration, supervision mode |
| `BoardContext.tsx` / `BoardSelector.tsx` | Board management | Already in place |
| `TaskInput.tsx` | Task creation | Add supervision mode selector, file attachment |
| `convex/schema.ts` | Current data model | Extend with steps table, step lifecycle fields |

**Additional Packages May Be Needed:**

| Package | Purpose |
|---------|---------|
| `@dnd-kit/core` (or similar) | Drag-and-drop for step reordering in pre-kickoff modal |

**Note:** The Python/AsyncIO nanobot backend is brownfield — existing planner.py, orchestrator.py, executor.py, and bridge.py will be refactored for the pure orchestrator model. No new Python packages anticipated.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Separate `steps` table in Convex (Task/Step hierarchy data model)
- Execution plan as structured object on task, materialized into steps on kick-off
- `blockedBy` array for step dependency resolution
- Unified thread with structured completion message format
- Lead Agent as pure orchestrator with architectural enforcement

**Important Decisions (Shape Architecture):**
- Pre-kickoff modal as dedicated full-screen modal (not Sheet overlay)
- Steps as flat Kanban cards with task grouping header
- General Agent as system-level fallback (always registered)

**Deferred Decisions (Post-MVP):**
- Plan templates (save/reuse execution plan patterns)
- Agent performance analytics
- Plan versioning (before/after comparison)
- Multi-task cross-board orchestration

### Data Architecture

**Database:** Convex (established — reactive queries, transactional mutations, typed schemas)

**Core Tables:**

| Table | Purpose | Key Relationships |
|-------|---------|-------------------|
| `tasks` | Parent entity — user's goal, supervision mode, execution plan (pre-kickoff), file manifest | Has many steps, has many messages |
| `steps` | Work unit — assigned agent, status, dependencies, parallel group. Kanban card entity. | Belongs to task, references agent by name, has `blockedBy` array of step IDs |
| `messages` | Unified thread — all agent completions, user messages, system events, Lead Agent planning | Belongs to task, authored by agent/user/system |
| `agents` | Agent registry synced from YAML definitions | Referenced by steps and tasks |
| `activities` | Append-only activity feed events | Optionally references task, step, and agent |
| `settings` | Global configuration key-value store | Standalone |

**Task/Step Hierarchy:**

```
Task (user's goal)
├── executionPlan: { ... }     # Structured plan object (pre-kickoff, editable)
├── supervisionMode: "autonomous" | "supervised"
├── status: "planning" | "ready" | "running" | "completed" | "failed"
├── files: [{ name, type, size, subfolder, uploadedAt }]
│
├── Step 1 (etapa)             # Separate Convex document
│   ├── taskId → Task
│   ├── assignedAgent: "financial-agent"
│   ├── status: "assigned" | "running" | "completed" | "crashed" | "blocked"
│   ├── blockedBy: [stepId, stepId]
│   ├── parallelGroup: 1
│   └── order: 1
│
├── Step 2 (etapa)
│   ├── blockedBy: []          # No dependencies — runs in parallel with Step 1
│   ├── parallelGroup: 1
│   └── order: 2
│
└── Step 3 (etapa)
    ├── blockedBy: [step1Id, step2Id]  # Blocked until both complete
    ├── parallelGroup: 2
    └── order: 3
```

**Execution Plan Structure (on task record, pre-kickoff):**

```typescript
type ExecutionPlan = {
  steps: Array<{
    tempId: string           // Temporary ID for pre-kickoff editing
    title: string
    description: string
    assignedAgent: string
    blockedBy: string[]      // References other tempIds
    parallelGroup: number
    order: number
    attachedFiles?: string[] // File paths attached to this specific step
  }>
  generatedAt: string        // ISO 8601
  generatedBy: "lead-agent"
}
```

On kick-off, each plan step is materialized into a real `steps` table document. The `executionPlan` field is preserved on the task as a snapshot of the original plan.

**Step Status Values:**

```typescript
type StepStatus = "planned" | "assigned" | "running" | "completed" | "crashed" | "blocked"
```

**Task Status Values:**

```typescript
type TaskStatus = "planning" | "reviewing_plan" | "ready" | "running" | "completed" | "failed"
```

- `planning` — Lead Agent is generating the execution plan
- `reviewing_plan` — Supervised mode, pre-kickoff modal is open
- `ready` — Plan approved, steps about to be dispatched
- `running` — At least one step is assigned/running
- `completed` — All steps completed
- `failed` — One or more steps crashed and were not retried

**Data Validation:**
- Convex schema validators (`v.string()`, `v.number()`, etc.) enforce types at runtime in `schema.ts`
- Python-side YAML validation via pydantic for agent configuration
- No Zod — Convex validators are sufficient for the TypeScript side

**Data Flow:**
- YAML files are the source of truth for agent definitions
- nanobot reads YAML, validates, writes to Convex `agents` table
- Convex is the source of truth for all shared runtime state (tasks, steps, messages, activities, settings)
- Dashboard reads exclusively from Convex reactive queries

### Authentication & Security

**No authentication for MVP.** Single-user tool running on localhost. No access token, no middleware.

**Post-MVP:** If multi-user or remote access is needed, add Convex Auth or simple token middleware.

### API & Communication Patterns

**Architecture: Convex as Single Communication Hub**

No REST API layer, no WebSocket server, no message broker. All communication flows through Convex's native primitives:

```
┌──────────────┐         ┌─────────┐         ┌──────────────┐
│   Dashboard  │ ←────── │  Convex │ ←────── │   nanobot    │
│  (Next.js)   │ ──────→ │ (Cloud) │ ──────→ │  (Python)    │
└──────────────┘         └─────────┘         └──────────────┘
  reactive queries        source of            mutations
  + mutations             truth                + subscriptions
```

| Path | Mechanism | Examples |
|------|-----------|---------|
| Dashboard → Convex | Mutations | Create task, approve plan, kick-off, post thread message |
| Convex → Dashboard | Reactive queries | Auto-updating Kanban (steps), thread, activity feed |
| nanobot → Convex | Mutations (Python SDK) | Step status changes, thread messages, activity events |
| Convex → nanobot | Subscriptions (Python SDK) | New tasks, plan approvals, step assignments |

**Exception: File I/O via Next.js API Routes**

File upload and serving bypass Convex (filesystem access required):
- `POST /api/tasks/[taskId]/files` — Upload files to task directory
- `GET /api/tasks/[taskId]/files/[...path]` — Serve files to viewer

**Structured Completion Message Format:**

```typescript
type ThreadMessage = {
  taskId: Id<"tasks">
  role: "agent" | "user" | "system" | "lead_agent"
  agentName?: string
  stepId?: Id<"steps">
  type: "step_completion" | "user_message" | "system_error" | "lead_agent_plan" | "lead_agent_chat"
  content: string                    // Human-readable text
  artifacts?: Array<{
    path: string                     // File path relative to task directory
    action: "created" | "modified"
    description?: string             // For created files
    diff?: string                    // For modified files
  }>
  timestamp: string                  // ISO 8601
}
```

**Error Handling:**
- Python SDK retries failed writes 3x with exponential backoff
- After retry exhaustion: log to local stdout + error activity event
- Dashboard detects connection loss → "Reconnecting..." banner
- Step crashes post structured error messages to the unified thread with actionable recovery instructions

### Frontend Architecture

**State Management:**
- Primary: Convex reactive queries (tasks, steps, agents, activities, settings, messages)
- Local: React `useState`/`useReducer` (modal state, form inputs, plan editing state)
- No additional library (no Redux, Zustand, Jotai)

**Routing:**
- `/` — Main dashboard (Kanban + sidebar + feed). Task detail is a Sheet overlay.
- Pre-kickoff modal is a full-screen modal overlay, not a route.

**Pre-Kickoff Modal:**
- Full modal with two-panel layout: plan editor (left) + Lead Agent chat (right)
- Plan editor: steps as editable cards, agent dropdown per step, drag-and-drop reorder, dependency toggles, file attachment per step
- Chat: thread with Lead Agent for plan negotiation (FR16-FR17)
- Kick-off button materializes plan into step records and dispatches

**Step Rendering on Kanban:**
- Steps are flat cards in Kanban columns
- Task grouping header separates steps by parent task within each column
- Step cards show: step title, assigned agent avatar, status badge, blocked indicator (lock icon + dependency names), file indicator
- Parent task name shown as subtle label on each step card

**Performance:**
- Optimistic UI via Convex built-in optimistic updates
- Motion `layoutId` for GPU-accelerated card transitions
- `prefers-reduced-motion` media query respect
- No SSR — localhost SPA

**Component Organization:**
- `components/ui/` — ShadCN UI primitives
- `components/` — Custom compositions (existing flat structure, extended with new components)

### Infrastructure & Deployment

**Process Orchestration (`nanobot mc start`):**

| Process | Role | Lifecycle |
|---------|------|-----------|
| Agent Gateway | Python AsyncIO — manages agent lifecycle, subprocess dispatch, bridge connection | Main process |
| Next.js dev server | Dashboard at `localhost:3000` | Child subprocess |
| Convex dev server | Backend function sync + reactive backend | Child subprocess |

**Subprocess Model for Parallel Steps:**

```python
# In gateway/executor
async def dispatch_parallel_group(steps: list[Step]):
    tasks = [run_agent_subprocess(step) for step in steps]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for step, result in zip(steps, results):
        if isinstance(result, Exception):
            await mark_step_crashed(step, result)
        else:
            await mark_step_completed(step)
            await unblock_dependents(step)
```

Each agent runs as a separate Python subprocess — no shared state, no agent contention. A crash in one subprocess doesn't bring down others.

**Lead Agent Orchestrator Enforcement:**
- The executor module checks agent identity before dispatch
- Lead Agent's agent loop only has planning tools (no execution tools)
- If executor receives Lead Agent as assigned agent, it routes to planner module
- Structurally impossible for Lead Agent to execute — not just a convention

**General Agent:**
- System-level agent, always registered in the agents table
- Configured with a general-purpose system prompt
- Used by Lead Agent as fallback when no specialist matches
- Cannot be deleted or deactivated

**Testing Strategy:**
- Dashboard: Vitest (established)
- Python: pytest (established)
- E2E: Manual testing for MVP

### Decision Impact Analysis

**Implementation Sequence:**
1. Extend Convex schema — add `steps` table, update `tasks` with `executionPlan` and `supervisionMode`, extend `messages` with structured format
2. Refactor Lead Agent planner — pure orchestrator, produces `ExecutionPlan` structure
3. Implement step materializer — converts `ExecutionPlan` into step records on kick-off
4. Build subprocess dispatcher — `asyncio.gather()` for parallel groups, dependency resolution
5. Refactor Kanban — steps as cards with task grouping headers
6. Build pre-kickoff modal — plan editor + Lead Agent chat
7. Extend thread — structured completion messages with artifacts
8. Implement step lifecycle — crash isolation, manual retry, auto-unblock

**Cross-Component Dependencies:**
- Convex schema (steps table) must exist before any step-related work
- Lead Agent planner must produce valid `ExecutionPlan` before pre-kickoff modal can render
- Step materializer must work before subprocess dispatcher can dispatch
- Structured message format must be defined before thread rendering and agent context injection

## Implementation Patterns & Consistency Rules

### Naming Patterns

**Convex Schema (TypeScript side):**

| Element | Convention | Example |
|---------|-----------|---------|
| Table names | camelCase, plural | `tasks`, `steps`, `messages`, `agents`, `activities`, `settings` |
| Field names | camelCase | `assignedAgent`, `taskId`, `blockedBy`, `parallelGroup`, `executionPlan` |
| Convex functions | camelCase, verb-first | `steps.create`, `steps.updateStatus`, `tasks.kickOff` |
| Convex function files | camelCase, plural (matches table) | `convex/tasks.ts`, `convex/steps.ts`, `convex/messages.ts` |

**React/Dashboard (TypeScript side):**

| Element | Convention | Example |
|---------|-----------|---------|
| Component files | PascalCase | `KanbanBoard.tsx`, `StepCard.tsx`, `PreKickoffModal.tsx` |
| Component names | PascalCase | `export function PreKickoffModal()` |
| Hook files | camelCase, `use` prefix | `useStepSubscription.ts` |
| Utility files | camelCase | `formatTimestamp.ts` |
| CSS/style | Tailwind utilities only | No CSS modules, no styled-components |
| Props interfaces | `{Component}Props` | `StepCardProps`, `PreKickoffModalProps` |

**Python (nanobot side):**

| Element | Convention | Example |
|---------|-----------|---------|
| Module files | snake_case | `convex_bridge.py`, `step_dispatcher.py` |
| Classes | PascalCase | `ConvexBridge`, `StepDispatcher`, `PlanMaterializer` |
| Functions/methods | snake_case | `dispatch_parallel_group()`, `materialize_plan()` |
| Constants | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT`, `DEFAULT_TIMEOUT_SECONDS` |
| Config keys (YAML) | snake_case | `assigned_to`, `parallel_group` |

**Cross-boundary rule:** When data crosses the Python-Convex boundary, field names convert to match the target convention. Python sends `snake_case`, the bridge layer converts to `camelCase` for Convex mutations. Convex subscription data arrives as `camelCase` and is converted to `snake_case` for Python consumption.

### Structure Patterns

**Test location:** Co-located with source files.
- Dashboard: `StepCard.test.tsx` next to `StepCard.tsx`
- Python: `test_step_dispatcher.py` next to `step_dispatcher.py`

**Component organization:** Flat structure in `components/`. No nested folders for MVP.

**Convex function organization:** One file per table (`tasks.ts`, `steps.ts`, `messages.ts`, etc.). All queries, mutations, and actions for a table in one file.

### Format Patterns

**Step Status Values (exact strings, used across all systems):**

```typescript
type StepStatus = "planned" | "assigned" | "running" | "completed" | "crashed" | "blocked"
```

**Task Status Values:**

```typescript
type TaskStatus = "planning" | "reviewing_plan" | "ready" | "running" | "completed" | "failed"
```

**Supervision Mode Values:**

```typescript
type SupervisionMode = "autonomous" | "supervised"
```

**Thread Message Roles:**

```typescript
type MessageRole = "agent" | "user" | "system" | "lead_agent"
```

**Thread Message Types:**

```typescript
type MessageType = "step_completion" | "user_message" | "system_error" | "lead_agent_plan" | "lead_agent_chat"
```

**Activity Event Types:**

```typescript
type ActivityEventType =
  | "task_created" | "task_planning" | "task_plan_approved" | "task_kicked_off"
  | "task_completed" | "task_failed"
  | "step_assigned" | "step_started" | "step_completed"
  | "step_crashed" | "step_retrying" | "step_unblocked"
  | "agent_connected" | "agent_disconnected" | "agent_crashed"
  | "file_uploaded" | "file_output_created"
  | "system_error"
```

**Agent Status Values:**

```typescript
type AgentStatus = "active" | "idle" | "crashed"
```

**Timestamps:** ISO 8601 strings (`2026-02-24T10:30:00Z`) everywhere — Convex, Python, dashboard.

### Communication Patterns

**Convex Mutation Pattern:** Every mutation that modifies step or task state MUST also write a corresponding activity event. No state change without a feed entry.

```typescript
export const updateStepStatus = mutation({
  args: { stepId: v.id("steps"), status: v.string(), agentName: v.string() },
  handler: async (ctx, args) => {
    const step = await ctx.db.get(args.stepId);
    await ctx.db.patch(args.stepId, { status: args.status });
    await ctx.db.insert("activities", {
      taskId: step.taskId,
      stepId: args.stepId,
      agentName: args.agentName,
      eventType: `step_${args.status}`,
      description: `Agent ${args.agentName} — step ${args.status}`,
      timestamp: new Date().toISOString(),
    });
  },
});
```

**Step Completion with Structured Message Pattern:** When an agent completes a step, it posts a structured completion message to the task's unified thread:

```typescript
export const postStepCompletion = mutation({
  args: {
    taskId: v.id("tasks"),
    stepId: v.id("steps"),
    agentName: v.string(),
    content: v.string(),
    artifacts: v.optional(v.array(v.object({
      path: v.string(),
      action: v.string(),
      description: v.optional(v.string()),
      diff: v.optional(v.string()),
    }))),
  },
  handler: async (ctx, args) => {
    await ctx.db.insert("messages", {
      taskId: args.taskId,
      stepId: args.stepId,
      role: "agent",
      agentName: args.agentName,
      type: "step_completion",
      content: args.content,
      artifacts: args.artifacts,
      timestamp: new Date().toISOString(),
    });
  },
});
```

**Python Bridge Call Pattern:** Every bridge call follows try-retry-log pattern.

```python
async def update_step_status(self, step_id: str, status: str, agent_name: str):
    await self._call_mutation_with_retry(
        "steps:updateStepStatus",
        {"stepId": step_id, "status": status, "agentName": agent_name}
    )
```

**Dependency Unblocking Pattern:** After a step completes, check all steps that reference it in `blockedBy`. If all blockers are completed, transition the dependent step from "blocked" to "assigned".

```typescript
export const checkAndUnblockDependents = mutation({
  args: { completedStepId: v.id("steps"), taskId: v.id("tasks") },
  handler: async (ctx, args) => {
    const allSteps = await ctx.db
      .query("steps")
      .withIndex("by_taskId", (q) => q.eq("taskId", args.taskId))
      .collect();
    for (const step of allSteps) {
      if (step.status === "blocked" && step.blockedBy?.includes(args.completedStepId)) {
        const remainingBlockers = step.blockedBy.filter((id) => id !== args.completedStepId);
        const allResolved = remainingBlockers.every((blockerId) => {
          const blocker = allSteps.find((s) => s._id === blockerId);
          return blocker?.status === "completed";
        });
        if (allResolved) {
          await ctx.db.patch(step._id, { status: "assigned", blockedBy: [] });
          // Activity event for unblocking
        }
      }
    }
  },
});
```

### Process Patterns

**Error Handling:**

| Layer | Pattern |
|-------|---------|
| Convex mutations | Throw `ConvexError` with user-readable message |
| Python bridge | Catch, retry 3x with exponential backoff, then log + write error activity |
| Step crash | Post structured error message to unified thread with actionable recovery instructions. Set step status to "crashed". Do NOT cascade to sibling steps. |
| Dashboard | Convex handles errors via `useQuery`/`useMutation` error states — show in feed, red badge on step card |

**Step Crash Isolation Rule:** A crashed step ONLY affects its direct dependents (they stay "blocked"). Sibling steps in the same parallel group continue running. The parent task does NOT fail unless explicitly marked by the user or all steps are crashed.

**Loading States:**
- Convex's built-in loading states (`useQuery` returns `undefined` while loading)
- No custom loading state management, no skeleton screens for MVP
- Feed shows "Waiting for activity..." when empty

**Plan Materialization Pattern:** On kick-off, the `executionPlan` object is converted into real step records:
1. For each plan step, create a `steps` document with `taskId` reference
2. Set initial status: "assigned" for steps with no blockers, "blocked" for steps with dependencies
3. Preserve the `executionPlan` on the task record as a snapshot
4. Update task status to "running"
5. Notify the Python backend via subscription that steps are ready for dispatch

### Enforcement Guidelines

**All AI Agents MUST:**

1. Follow naming conventions exactly — camelCase in TypeScript, snake_case in Python, PascalCase for React components
2. Never change step or task status without writing a corresponding activity event
3. Use the exact string values for step status, task status, supervision mode, message roles/types, and event types
4. Convert field names at the Python-Convex boundary (snake_case ↔ camelCase)
5. Post structured completion messages to the unified thread when a step completes — always include `artifacts` array for any file operations
6. Respect crash isolation — a crashed step blocks dependents only, never crashes siblings or parent task
7. Never allow the Lead Agent to execute tasks — route to planner module, not execution pipeline
8. Use `blockedBy` array for dependency resolution — check all blockers before unblocking a step
9. Co-locate tests with source files
10. Use Convex validators for TypeScript-side validation, pydantic for Python-side YAML validation
11. Use ISO 8601 for all timestamps

## Project Structure & Boundaries

### Complete Project Directory Structure

```
nanobot-ennio/                          # Root — existing nanobot project
├── README.md
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
│
├── nanobot/                            # Existing Python package
│   ├── __init__.py
│   ├── __main__.py
│   ├── agent/                          # Existing agent infrastructure
│   │   ├── context.py
│   │   ├── loop.py
│   │   ├── memory.py
│   │   ├── skills.py
│   │   ├── subagent.py
│   │   └── tools/
│   ├── bus/                            # Existing message bus
│   │   ├── events.py
│   │   └── queue.py
│   ├── cli/                            # Existing CLI
│   │   └── mc.py                       # nanobot mc subcommands
│   ├── config/
│   ├── heartbeat/
│   ├── channels/
│   ├── providers/
│   ├── session/
│   ├── skills/
│   ├── utils/
│   │
│   └── mc/                             # Mission Control package
│       ├── __init__.py
│       ├── gateway.py                  # Agent Gateway — AsyncIO main loop
│       ├── test_gateway.py
│       ├── bridge.py                   # Convex Python SDK wrapper (SOLE boundary)
│       ├── test_bridge.py
│       ├── orchestrator.py             # Lead Agent coordination (REFACTOR: pure orchestrator)
│       ├── test_orchestrator.py
│       ├── planner.py                  # Lead Agent planning — produces ExecutionPlan (REFACTOR)
│       ├── executor.py                 # Step execution — subprocess dispatch (REFACTOR)
│       ├── step_dispatcher.py          # NEW — asyncio.gather() parallel dispatch + dependency resolution
│       ├── plan_materializer.py        # NEW — converts ExecutionPlan → step records on kick-off
│       ├── state_machine.py            # Task/Step state transitions (REFACTOR for steps)
│       ├── test_state_machine.py
│       ├── yaml_validator.py           # Agent YAML schema validation (pydantic)
│       ├── test_yaml_validator.py
│       ├── process_manager.py          # Subprocess mgmt (Next.js, Convex dev)
│       ├── test_process_manager.py
│       ├── timeout_checker.py          # Step timeout detection
│       ├── test_timeout_checker.py
│       ├── provider_factory.py         # LLM provider setup
│       ├── agent_assist.py             # Agent-assisted CLI
│       ├── test_agent_assist.py
│       ├── init_wizard.py              # First-run setup
│       └── types.py                    # Shared Python types/dataclasses (EXTEND for steps)
│
├── dashboard/                          # Next.js + Convex dashboard
│   ├── package.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── postcss.config.mjs
│   ├── eslint.config.mjs
│   ├── components.json                 # ShadCN UI config
│   ├── .env.local
│   │
│   ├── app/
│   │   ├── globals.css
│   │   ├── layout.tsx
│   │   ├── page.tsx                    # Main dashboard
│   │   ├── login/
│   │   │   └── page.tsx
│   │   └── api/
│   │       ├── tasks/                  # File upload/serving API routes
│   │       ├── agents/                 # Agent config API routes
│   │       ├── auth/
│   │       └── cron/
│   │
│   ├── components/
│   │   ├── ui/                         # ShadCN primitives (auto-generated)
│   │   │
│   │   │   # === LAYOUT & NAVIGATION ===
│   │   ├── DashboardLayout.tsx
│   │   ├── DashboardLayout.test.tsx
│   │   ├── BoardContext.tsx
│   │   ├── BoardSelector.tsx
│   │   ├── BoardSettingsSheet.tsx
│   │   ├── ConvexClientProvider.tsx
│   │   ├── ThemeToggle.tsx
│   │   ├── UserMenu.tsx
│   │   │
│   │   │   # === KANBAN BOARD ===
│   │   ├── KanbanBoard.tsx             # REFACTOR: steps as cards with task grouping
│   │   ├── KanbanBoard.test.tsx
│   │   ├── KanbanColumn.tsx            # REFACTOR: step-based columns
│   │   ├── TaskCard.tsx                # REFACTOR → StepCard rendering
│   │   ├── TaskCard.test.tsx
│   │   ├── StepCard.tsx                # NEW — step card for Kanban
│   │   ├── TaskGroupHeader.tsx         # NEW — groups steps by parent task in columns
│   │   │
│   │   │   # === TASK CREATION & DETAIL ===
│   │   ├── TaskInput.tsx               # EXTEND: supervision mode selector
│   │   ├── TaskInput.test.tsx
│   │   ├── TaskDetailSheet.tsx         # EXTEND: step list, unified thread, plan snapshot
│   │   ├── TaskDetailSheet.test.tsx
│   │   ├── PreKickoffModal.tsx         # NEW — full-screen plan editor + Lead Agent chat
│   │   ├── PlanEditor.tsx              # NEW — step cards, drag-and-drop, dependency editing
│   │   ├── PlanStepCard.tsx            # NEW — editable step card in plan editor
│   │   │
│   │   │   # === THREAD & MESSAGING ===
│   │   ├── ThreadMessage.tsx           # EXTEND: structured completion messages with artifacts
│   │   ├── ThreadInput.tsx
│   │   ├── ArtifactRenderer.tsx        # NEW — renders file paths + diffs in thread messages
│   │   │
│   │   │   # === EXECUTION & VISUALIZATION ===
│   │   ├── ExecutionPlanTab.tsx         # REFACTOR: Task/Step hierarchy visualization
│   │   ├── ExecutionPlanTab.test.tsx
│   │   │
│   │   │   # === ACTIVITY FEED ===
│   │   ├── ActivityFeed.tsx
│   │   ├── ActivityFeed.test.tsx
│   │   ├── ActivityFeedPanel.tsx
│   │   ├── FeedItem.tsx                # EXTEND: step-level events
│   │   │
│   │   │   # === AGENT MANAGEMENT ===
│   │   ├── AgentSidebar.tsx
│   │   ├── AgentSidebarItem.tsx
│   │   ├── AgentSidebarItem.test.tsx
│   │   ├── AgentConfigSheet.tsx
│   │   ├── AgentConfigSheet.test.tsx
│   │   ├── AgentTextViewerModal.tsx
│   │   ├── CreateAgentSheet.tsx
│   │   ├── PromptEditModal.tsx
│   │   ├── SkillsSelector.tsx
│   │   ├── SkillsSelector.test.tsx
│   │   │
│   │   │   # === FILE VIEWING ===
│   │   ├── DocumentViewerModal.tsx     # Already built — multi-format viewer
│   │   ├── MarkdownRenderer.tsx
│   │   ├── Code.tsx
│   │   │
│   │   │   # === OTHER ===
│   │   ├── InlineRejection.tsx
│   │   ├── InlineRejection.test.tsx
│   │   ├── SettingsPanel.tsx
│   │   ├── SettingsPanel.test.tsx
│   │   ├── TagsPanel.tsx
│   │   ├── TrashBinSheet.tsx
│   │   ├── DoneTasksSheet.tsx
│   │   └── CronJobsModal.tsx
│   │
│   ├── convex/
│   │   ├── _generated/                 # Auto-generated by Convex CLI
│   │   ├── schema.ts                   # EXTEND: add steps table, update tasks/messages
│   │   ├── tasks.ts                    # REFACTOR: add executionPlan, supervisionMode, kickOff
│   │   ├── steps.ts                    # NEW — step CRUD, status updates, dependency unblocking
│   │   ├── messages.ts                 # EXTEND: structured completion message format
│   │   ├── agents.ts
│   │   ├── activities.ts               # EXTEND: step-level event types
│   │   ├── settings.ts
│   │   ├── boards.ts
│   │   ├── skills.ts
│   │   └── taskTags.ts
│   │
│   ├── lib/
│   │   └── utils.ts
│   │
│   └── public/
│
├── workspace/                          # Shared agent workspace
├── tests/                              # Additional Python tests
└── docs/
```

### Architectural Boundaries

**Boundary 1: Python to Convex (the Bridge)**

`nanobot/mc/bridge.py` is the ONLY Python module that imports the `convex` Python SDK. All other Python modules call `bridge.py` methods — never Convex directly. Bridge handles: connection management, retry logic, snake_case ↔ camelCase conversion, error wrapping.

**Boundary 2: Convex Functions to Dashboard**

Components never access Convex directly — always through `useQuery(api.steps.byTask)` or `useMutation(api.tasks.kickOff)`. Convex functions are the API layer — all business logic (validation, state transitions, activity logging, dependency unblocking) lives in Convex functions. Components are purely presentational + user interaction.

**Boundary 3: Existing nanobot to Mission Control**

Mission Control imports from existing nanobot modules (SubagentManager, MessageBus, HeartbeatService). Existing nanobot modules do NOT import from `mc/` — the dependency is one-directional. `mc/gateway.py` is the integration point.

**Boundary 4: Lead Agent Boundary**

The Lead Agent can ONLY interact with the planner module. The executor checks agent identity and routes the Lead Agent to `planner.py`, never to the execution pipeline. This is an architectural enforcement, not a convention.

**Boundary 5: File I/O Boundary**

File upload and serving go through Next.js API routes (`/api/tasks/[taskId]/files`), NOT through Convex. Convex stores file metadata only (manifest). The filesystem is accessed only by: the Python backend (reading/writing files) and the Next.js API routes (serving/uploading files).

### Requirements to Structure Mapping

| FR Category | Dashboard Files | Python Files | Convex Files |
|-------------|----------------|--------------|--------------|
| Task & Step Management (FR1-FR5) | `TaskInput.tsx`, `StepCard.tsx`, `TaskGroupHeader.tsx`, `TaskDetailSheet.tsx` | — | `tasks.ts`, `steps.ts`, `schema.ts` |
| Execution Planning (FR6-FR10) | `ExecutionPlanTab.tsx` | `planner.py`, `orchestrator.py` | `tasks.ts` (executionPlan field) |
| Pre-Kickoff Plan Review (FR11-FR18) | `PreKickoffModal.tsx`, `PlanEditor.tsx`, `PlanStepCard.tsx` | `planner.py` (chat responses) | `tasks.ts` (plan mutations), `messages.ts` (chat) |
| Agent Orchestration (FR19-FR23) | `StepCard.tsx` (status updates) | `step_dispatcher.py`, `plan_materializer.py`, `executor.py` | `steps.ts` (mutations) |
| Unified Thread (FR24-FR28) | `ThreadMessage.tsx`, `ArtifactRenderer.tsx`, `ThreadInput.tsx` | `executor.py` (builds thread context) | `messages.ts` |
| Step Lifecycle (FR29-FR34) | `StepCard.tsx` (crashed badge, blocked icon), `FeedItem.tsx` | `step_dispatcher.py`, `bridge.py` | `steps.ts`, `activities.ts` |
| Dashboard Viz (FR35-FR38) | `KanbanBoard.tsx`, `KanbanColumn.tsx`, `ActivityFeed.tsx` | — | all query files |
| File Layer (Thread Files PRD) | `DocumentViewerModal.tsx`, `TaskInput.tsx` (file picker) | `bridge.py` (manifest sync) | `tasks.ts` (files field) |

### Cross-Cutting Concerns Mapping

| Concern | Files Involved |
|---------|---------------|
| State consistency (Task/Step) | `bridge.py`, `convex/tasks.ts`, `convex/steps.ts`, all dashboard components via `useQuery` |
| Error isolation | `step_dispatcher.py` (subprocess crash handling), `convex/steps.ts` (crash status), `StepCard.tsx` (crashed badge), `convex/activities.ts` (error events) |
| Thread context management | `executor.py` (`_build_thread_context()`), `convex/messages.ts`, `ThreadMessage.tsx` |
| Dependency management | `convex/steps.ts` (`checkAndUnblockDependents`), `step_dispatcher.py` (dispatch order), `StepCard.tsx` (blocked indicator) |
| File integration | `bridge.py` (manifest sync), `/api/tasks/[taskId]/files` (upload/serve), `DocumentViewerModal.tsx`, `executor.py` (file context injection) |

### Data Flow

```
User creates task (Dashboard)
  → Convex Mutation (tasks.create) — sets status "planning"
    → Python bridge subscription fires
      → Lead Agent planner generates ExecutionPlan
        → Bridge writes plan to task (tasks.setExecutionPlan)
          → If autonomous: plan_materializer creates step records → dispatch
          → If supervised: task status → "reviewing_plan" → PreKickoffModal opens
            → User edits plan → chat with Lead Agent → clicks Kick-Off
              → plan_materializer creates step records in Convex
                → step_dispatcher reads steps, groups by parallelGroup
                  → asyncio.gather() dispatches parallel steps as subprocesses
                    → Each agent runs, posts structured completion to thread
                      → On step completion: checkAndUnblockDependents
                        → Next parallel group dispatched
                          → All steps done → task status "completed"
                            → Dashboard reactive queries update Kanban
```

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**

All technology choices are proven and compatible. Next.js 16.1.5 + React 19.2.4 + Convex 1.31.6 form a mature, well-tested stack already running in production for this project. Python/AsyncIO + Convex Python SDK are established in the existing nanobot codebase. No version conflicts detected — all dependencies are already installed and working.

The new architectural decisions (separate `steps` table, `blockedBy` dependency arrays, ExecutionPlan on task record, subprocess parallelism) layer cleanly on top of the existing infrastructure without requiring library changes.

**Pattern Consistency:**

- Naming conventions (camelCase for TS/Convex, snake_case for Python, PascalCase for React components) are consistent with existing codebase conventions
- The snake_case ↔ camelCase bridge conversion pattern is already implemented in `bridge.py` and extends naturally to step-related fields
- Communication patterns (Convex as single hub, mutations + reactive queries) align with the established data flow
- Activity event pattern (every state change writes an activity) is consistent across all new step-level events

**Structure Alignment:**

- Project structure preserves the existing flat component layout in `components/` and one-file-per-table pattern in `convex/`
- New files (`steps.ts`, `StepCard.tsx`, `PreKickoffModal.tsx`, `step_dispatcher.py`, `plan_materializer.py`) follow established naming patterns
- Architectural boundaries (bridge as sole Python-Convex boundary, components never call Convex directly, one-directional nanobot → MC dependency) remain intact and are extended, not violated

### Requirements Coverage Validation ✅

**Functional Requirements Coverage:**

| FR Category | Coverage | Notes |
|-------------|----------|-------|
| Task & Step Management (FR1-FR5) | ✅ Full | `steps` table, task/step hierarchy, supervision mode selector in TaskInput |
| Execution Planning (FR6-FR10) | ✅ Full | ExecutionPlan type, planner.py refactor, General Agent fallback |
| Pre-Kickoff Plan Review (FR11-FR18) | ✅ Full | PreKickoffModal with PlanEditor + Lead Agent chat panel |
| Agent Orchestration (FR19-FR23) | ✅ Full | Pure orchestrator enforcement, step_dispatcher.py, asyncio.gather() parallelism |
| Unified Thread (FR24-FR28) | ✅ Full | ThreadMessage structured format, artifacts array, context truncation to 20 messages |
| Step Lifecycle (FR29-FR34) | ✅ Full | Step status lifecycle, crash isolation, manual retry, checkAndUnblockDependents |
| Dashboard & Visualization (FR35-FR38) | ✅ Full | StepCard Kanban, TaskGroupHeader, ExecutionPlanTab refactor, ActivityFeed extension |
| File Layer (29 FRs) | ✅ Full | Task directories, file manifest, DocumentViewerModal (existing), API routes, agent file context |

**Non-Functional Requirements Coverage:**

| NFR Category | Coverage | Notes |
|-------------|----------|-------|
| Performance (NFR1-NFR5) | ✅ Full | Convex reactive queries (<1s updates), optimistic UI, Motion GPU transitions, thread truncation |
| Reliability (NFR6-NFR10) | ✅ Full | Subprocess crash isolation, bridge retry (3x exponential), atomic dependency unblocking |
| Integration (NFR11-NFR13) | ✅ Full | Persistent bridge connection, LLM retry, structured message format consistency |
| File Performance (5 NFRs) | ✅ Full | API routes for file serving, manifest reconciliation, reactive display |
| File Reliability (4 NFRs) | ✅ Full | Atomic directory creation, manifest sync, fallback viewer |
| File Integration (4 NFRs) | ✅ Full | Manifest reflects upload <2s via Convex mutation, fresh manifest per context fetch |

### Implementation Readiness Validation ✅

**Decision Completeness:**

- All critical decisions include exact type definitions (`StepStatus`, `TaskStatus`, `SupervisionMode`, `ExecutionPlan`, `ThreadMessage`)
- Implementation patterns include code examples for every major interaction (Convex mutations, bridge calls, dependency unblocking, subprocess dispatch)
- Enforcement guidelines provide 11 concrete rules for AI agent consistency
- String literal types prevent drift (exact status values used across all systems)

**Structure Completeness:**

- Complete directory tree with NEW/REFACTOR/EXTEND annotations for every affected file
- 5 architectural boundaries clearly defined with enforcement rules
- FR-to-file mapping table provides direct implementation routing
- Cross-cutting concerns mapped to specific files

**Pattern Completeness:**

- Naming patterns cover all three runtimes (TypeScript, Python, Convex)
- Communication patterns include complete Convex mutation examples with activity logging
- Error handling patterns cover all layers (Convex, Python bridge, step crash, dashboard)
- Process patterns include plan materialization sequence and dependency unblocking algorithm

### Gap Analysis Results

**Critical Gaps:** None identified. All blocking decisions are documented.

**Important Gaps (4):**

1. **Task Status Derivation from Steps** — The architecture defines `TaskStatus` values but doesn't specify the exact algorithm for deriving task status from step states. For example: when does a task transition from "running" to "completed" — when ALL steps complete? What if some steps are "crashed" and others "completed"? **Recommendation:** Define in the step lifecycle Convex mutation: task is "completed" when all steps are "completed"; task is "failed" when any step is "crashed" AND no retries are pending; task stays "running" otherwise.

2. **Pre-Kickoff Chat Interaction Pattern** — FR16-FR17 specify that the user can chat with the Lead Agent during plan review to request changes. The architecture defines the PreKickoffModal layout and message types (`lead_agent_plan`, `lead_agent_chat`) but doesn't specify how the chat triggers Lead Agent re-planning. **Recommendation:** Use the existing thread mechanism — user posts a `lead_agent_chat` message, Python bridge subscription fires, Lead Agent planner receives the message + current plan, responds with updated `ExecutionPlan` or a chat reply.

3. **General Agent Registration Mechanism** — The architecture states the General Agent is "always registered" and "cannot be deleted" but doesn't specify where it's defined or how it's bootstrapped. **Recommendation:** Define a `general-agent.yaml` in the agent definitions directory, loaded at gateway startup. The `agents` table seed logic ensures it exists — if missing, recreate from YAML.

4. **Thread Context for Dependent Steps** — When Step 3 depends on Step 1 and Step 2, how does Step 3's agent know what those steps produced? The thread truncation (20 messages) might exclude earlier completion messages. **Recommendation:** When building step context, always inject the structured completion messages of direct `blockedBy` predecessors, even if they fall outside the 20-message window. This is a targeted extension of the existing `_build_thread_context()` pattern.

**Nice-to-Have Gaps:**

- Drag-and-drop library selection (suggested `@dnd-kit/core` but not finalized)
- Step timeout configuration (timeout_checker.py exists but step-level timeout values not specified)
- Pre-kickoff modal keyboard shortcuts for plan editing efficiency

### Architecture Completeness Checklist

**✅ Requirements Analysis**

- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed
- [x] Technical constraints identified
- [x] Cross-cutting concerns mapped

**✅ Architectural Decisions**

- [x] Critical decisions documented with types and versions
- [x] Technology stack fully specified (brownfield — all packages installed)
- [x] Integration patterns defined (Convex as hub, bridge as boundary)
- [x] Performance considerations addressed (reactive queries, optimistic UI, thread truncation)

**✅ Implementation Patterns**

- [x] Naming conventions established (3 runtimes)
- [x] Structure patterns defined (flat components, one-file-per-table, co-located tests)
- [x] Communication patterns specified (mutations with activity events, structured thread messages)
- [x] Process patterns documented (error handling, plan materialization, dependency unblocking)

**✅ Project Structure**

- [x] Complete directory structure defined with change annotations
- [x] Component boundaries established (5 architectural boundaries)
- [x] Integration points mapped (FR-to-file mapping)
- [x] Requirements to structure mapping complete

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

**Confidence Level:** High — brownfield project with proven tech stack, all critical decisions documented with type definitions and code examples, 4 important gaps identified with clear recommendations.

**Key Strengths:**

- Precise type definitions eliminate ambiguity for AI agents (`StepStatus`, `TaskStatus`, `ExecutionPlan`, `ThreadMessage`)
- Code examples for every major pattern (Convex mutations, bridge calls, subprocess dispatch, dependency unblocking)
- 11 enforcement guidelines provide concrete guardrails
- Brownfield advantage — 47 existing components and full Convex schema reduce implementation risk
- Pure orchestrator enforcement is architectural (executor checks identity), not conventional
- Crash isolation is subprocess-based (true process boundaries), not exception-based

**Areas for Future Enhancement:**

- Plan templates (save/reuse common execution plan patterns)
- Agent performance analytics (track step completion times, crash rates)
- Plan versioning (compare original plan with actual execution)
- Multi-task cross-board orchestration
- Step timeout auto-escalation

### Implementation Handoff

**AI Agent Guidelines:**

- Follow all architectural decisions exactly as documented
- Use implementation patterns consistently across all components
- Respect project structure and boundaries (especially the 5 architectural boundaries)
- Refer to this document for all architectural questions
- Use the exact string literal types for all status values, message roles, and event types
- Convert field names at the Python-Convex boundary (snake_case ↔ camelCase)
- Always write an activity event when changing step or task status

**First Implementation Priority:**

1. Extend Convex schema (`schema.ts`) — add `steps` table, update `tasks` with `executionPlan` and `supervisionMode`, extend `messages` with structured format
2. Create `convex/steps.ts` — step CRUD, status updates, dependency unblocking
3. Refactor Lead Agent planner to produce `ExecutionPlan` structure
4. Implement `plan_materializer.py` — convert ExecutionPlan → step records on kick-off
5. Build `step_dispatcher.py` — asyncio.gather() parallel dispatch + dependency resolution
