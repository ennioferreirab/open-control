---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
---

# nanobot-ennio - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for nanobot-ennio, decomposing the requirements from the PRD, Architecture, and UX Design Specification into implementable stories.

## Requirements Inventory

### Functional Requirements

**Task & Step Management**

- FR1: User can create a task by describing a goal in natural language
- FR2: System decomposes a task into one or more steps (etapas), each representing a unit of work for a specialist agent
- FR3: Steps are displayed as individual cards on the Kanban board, grouped under their parent task
- FR4: User can select supervision mode (autonomous or supervised) when creating a task
- FR5: User can attach files to a task at creation time

**Execution Planning**

- FR6: Lead Agent generates an execution plan for every submitted task, including single-step tasks
- FR7: Execution plan specifies: steps, assigned agents, blocking dependencies, and parallel groups
- FR8: Lead Agent assigns agents to steps based on capability matching and task context
- FR9: Lead Agent considers attached file metadata (types, sizes, names) when routing steps to agents
- FR10: nanobot agent is always available as a system-level fallback agent for any step not matching a specialist

**Pre-Kickoff Plan Review (Supervised Mode)**

- FR11: In supervised mode, system presents a pre-kickoff modal showing the full execution plan before any step executes
- FR12: User can reassign agents to any step in the pre-kickoff modal
- FR13: User can reorder steps in the pre-kickoff modal
- FR14: User can change blocking dependencies between steps in the pre-kickoff modal
- FR15: User can attach documents to specific steps in the pre-kickoff modal
- FR16: User can chat with the Lead Agent in the pre-kickoff modal to negotiate plan changes
- FR17: Lead Agent can dynamically modify the plan in response to user chat requests (add/remove/change steps)
- FR18: User can approve the plan and trigger kick-off from the pre-kickoff modal

**Agent Orchestration & Dispatch**

- FR19: Lead Agent never executes tasks directly — it only plans, delegates, and coordinates
- FR20: In autonomous mode, the plan dispatches immediately after generation without user intervention
- FR21: Parallel steps launch simultaneously as separate processes
- FR22: Sequential steps execute in dependency order, each waiting for its blockers to complete
- FR23: Step completion automatically unblocks dependent steps

**Unified Thread & Agent Communication**

- FR24: Each task has a single unified thread shared by all agents and the user
- FR25: Agents post structured completion messages to the thread containing: file paths, diffs for modified files, and descriptions for created files
- FR26: User can post messages to the thread during task execution
- FR27: Agents read the full thread context (including user messages and prior agent completions) when starting their step
- FR28: Thread context is managed to fit within LLM context windows (truncation with omission note for long threads)

**Step Lifecycle & Error Handling**

- FR29: Steps progress through a defined lifecycle: assigned -> running -> completed (or crashed)
- FR30: Blocked steps display a visual indicator showing which steps they depend on
- FR31: When a step crashes, the system posts an error message to the thread with actionable recovery instructions
- FR32: A crashed step does not crash sibling or parent steps — only blocks dependents
- FR33: User can manually retry a crashed step, re-entering the execution pipeline
- FR34: Successful retry of a crashed step automatically unblocks its dependents

**Dashboard & Visualization**

- FR35: Kanban board displays step cards with real-time status updates (assigned, running, completed, crashed, blocked)
- FR36: Execution plan visualization shows steps, dependencies, parallel groups, and assigned agents
- FR37: Thread view shows structured agent messages with file path references in real-time
- FR38: Activity feed shows step completion and error events

**File Attachment & Viewing (from Architecture — Thread Files Layer, 29 FRs)**

- FR-F1: User can attach one or more files to a task at creation time via file picker
- FR-F2: User can attach additional files to an existing task from the task detail view
- FR-F3: User can see attached file names as chips/indicators on the task input before submitting
- FR-F4: User can remove a pending attachment before task submission
- FR-F5: System creates a dedicated task directory with attachments/ and output/ subdirectories when a task is created
- FR-F6: User can view a list of all files (attachments and outputs) in a Files tab within the task detail Sheet
- FR-F7: User can open any file from the file list in a multi-format viewer modal
- FR-F8: User can view PDF files with page-by-page rendering, zoom controls, and pagination
- FR-F9: User can view code files with syntax highlighting and line numbers
- FR-F10: User can view HTML files in rendered mode and toggle to raw source view
- FR-F11: User can view Markdown files in rendered mode and toggle to raw source view
- FR-F12: User can view image files with zoom controls
- FR-F13: User can view plain text and CSV files with zoom controls
- FR-F14: User can download any file from the viewer
- FR-F15: System serves files from the task directory to the dashboard via an API endpoint
- FR-F16: System detects file type based on MIME type and file extension to route to the correct viewer
- FR-F17: System includes the task directory path in the agent's task context when the agent receives a task
- FR-F18: System includes a file manifest (name, type, size, subfolder) for all task files in the agent's task context
- FR-F19: Agent can read files from the task's attachments/ directory using its existing tools
- FR-F20: Agent can write output files to the task's output/ directory using its existing tools
- FR-F21: System updates the file manifest when the agent creates new output files
- FR-F22: System stores file metadata (name, type, size, subfolder, uploadedAt) on the task record
- FR-F23: System updates the file manifest when the user uploads new attachments to an existing task
- FR-F24: System updates the file manifest when the agent produces new output files
- FR-F25: Dashboard reactively reflects file manifest changes (new files appear without manual refresh)
- FR-F26: User can see a paperclip icon on task cards that have attached files on the Kanban board
- FR-F27: User can see the file count next to the paperclip icon on the task card
- FR-F28: Lead Agent receives the file manifest as part of the task context when routing unassigned tasks
- FR-F29: Lead Agent can include file metadata context in its delegation message when assigning a task to a specialist agent

### NonFunctional Requirements

**Performance (Core)**

- NFR1: Plan generation completes in < 10 seconds from task submission
- NFR2: Pre-kickoff modal renders the full plan with editable fields within 2 seconds of opening
- NFR3: Kanban board reflects step status changes within 1 second of the event (Convex reactive query)
- NFR4: Thread messages from agents appear in the UI within 1 second of being posted to Convex
- NFR5: Thread context injection for agents truncates to last 20 messages to stay within LLM context window limits

**Reliability (Core)**

- NFR6: A crashed agent step does not affect other running or pending steps — only blocks its direct dependents
- NFR7: The system recovers gracefully from LLM provider errors (OAuth expiry, rate limits, timeouts) with actionable error messages
- NFR8: Agent subprocesses run in isolation — a crash in one subprocess does not bring down the Python engine or other subprocesses
- NFR9: Dependency unblocking is atomic — a step is unblocked only after all its blockers report completion
- NFR10: Planning failures surface as backend errors on the task with clear error messages — no silent failures

**Integration (Core)**

- NFR11: The AsyncIO-Convex bridge maintains a persistent connection and reconnects automatically on disconnection
- NFR12: LLM provider calls include timeout handling and retry logic for transient errors
- NFR13: Structured completion messages follow a consistent format parseable by both the UI (for rendering) and agents (for context injection)

**Performance (File Layer)**

- NFR-F1: File upload from dashboard to filesystem completes within 3 seconds for files up to 10MB
- NFR-F2: File list in the task detail Sheet loads within 1 second of opening the Files tab
- NFR-F3: File viewer opens and renders the first page/content within 2 seconds for files up to 10MB
- NFR-F4: PDF viewer page navigation (next/previous) renders within 500ms
- NFR-F5: File serving API endpoint returns file bytes with correct Content-Type within 1 second for files up to 10MB

**Reliability (File Layer)**

- NFR-F10: Task directory creation never fails silently — if directory creation fails, the task creation fails with a clear error
- NFR-F11: File manifest is always reconcilable with the filesystem — the system can detect and resolve discrepancies
- NFR-F12: File upload that fails mid-transfer does not leave partial files in the task directory
- NFR-F13: Viewer gracefully handles unsupported file types with a download fallback instead of a blank screen or error

**Integration (File Layer)**

- NFR-F6: File manifest reflects a new user upload within 2 seconds of upload completion
- NFR-F7: File manifest reflects new agent output files within 5 seconds of the agent notifying the backend
- NFR-F8: Agent receives updated file manifest (including newly attached files) within 1 second of its next task context fetch
- NFR-F9: Dashboard reactively displays new files without page refresh when the file manifest updates

### Additional Requirements

**From Architecture — Data Model & Infrastructure:**

- No starter template needed (brownfield — extends existing codebase)
- Separate `steps` table in Convex with Task/Step parent-child hierarchy
- ExecutionPlan as structured TypeScript type stored on task record (pre-kickoff, editable)
- `blockedBy` array on steps for dependency resolution
- Step status values: "planned" | "assigned" | "running" | "completed" | "crashed" | "blocked"
- Task status values: "planning" | "reviewing_plan" | "ready" | "running" | "completed" | "failed"
- Supervision mode values: "autonomous" | "supervised"
- Plan materialization: ExecutionPlan object converted into real step records on kick-off
- Subprocess model: each agent runs as separate Python subprocess via asyncio.gather() for parallel groups
- bridge.py as sole Python-Convex boundary with snake_case ↔ camelCase field conversion
- Lead Agent enforcement: executor checks agent identity and routes Lead Agent to planner module only (architectural invariant)
- nanobot agent bootstrapped from YAML definition at gateway startup, always registered, cannot be deleted
- Activity event logging: every task/step state change MUST write a corresponding activity event
- Python SDK retry pattern: 3x with exponential backoff for bridge calls
- Structured completion message format: ThreadMessage type with role, type, content, artifacts array (path, action, description, diff)
- Pre-kickoff modal as full-screen modal (not Sheet overlay) with two-panel layout: plan editor (left) + Lead Agent chat (right)
- Steps as flat Kanban cards with task grouping header in columns
- Task status derivation: task "completed" when all steps "completed"; "failed" when any step "crashed" with no retries pending; "running" otherwise
- Pre-kickoff chat triggers Lead Agent re-planning: user posts lead_agent_chat message, bridge subscription fires, Lead Agent responds with updated ExecutionPlan
- Thread context for dependent steps: always inject structured completion messages of direct blockedBy predecessors, even if outside 20-message window
- @dnd-kit/core suggested for drag-and-drop step reordering in pre-kickoff modal
- File layer: task directories under ~/.nanobot/tasks/{task-id}/ with attachments/ and output/ subdirs
- File manifest stored as `files` field on Convex tasks table
- Next.js API routes for file upload and serving (filesystem access, not Convex)
- Python bridge manifest sync for agent output files

**From UX Design — Interaction & Accessibility:**

- WCAG 2.1 AA compliance baseline (ShadCN/Radix provides defaults)
- Color contrast: all text/background combinations meet 4.5:1 ratio (normal text), 3:1 (large text)
- Keyboard navigation: Radix UI primitives provide focus management, arrow key nav, escape-to-close
- Screen reader support: ARIA attributes, role assignments, live regions from Radix UI
- Status indicators: always combine color + text label (not color-only)
- Motion sensitivity: prefers-reduced-motion media query disables card animations
- Desktop-only MVP (no mobile/tablet breakpoints)
- Single-screen layout: Kanban, agent sidebar, activity feed, task detail, settings — all visible/accessible without page navigation
- Persistent session design (stays open throughout workday)
- Motion library (Framer Motion) for card transitions (layoutId), fade-ins, expand/collapse animations
- ShadCN UI + Tailwind CSS as design system; all custom components are ShadCN compositions
- No custom loading states or skeleton screens for MVP — Convex built-in loading states
- Pre-kickoff modal: plan editor uses editable step cards with agent dropdown, drag-and-drop reorder, dependency toggles, file attachment per step
- Step cards on Kanban: title, assigned agent avatar, status badge, blocked indicator (lock icon + dependency names), file indicator, parent task label

### FR Coverage Map

| FR | Epic | Description |
|----|------|-------------|
| FR1 | Epic 1 | Create task by describing a goal |
| FR2 | Epic 1 | System decomposes task into steps |
| FR3 | Epic 1 | Steps displayed as Kanban cards grouped by task |
| FR4 | Epic 1 | Select supervision mode at task creation |
| FR5 | Epic 5 | Attach files to task at creation time |
| FR6 | Epic 1 | Lead Agent generates execution plan for every task |
| FR7 | Epic 1 | Plan specifies steps, agents, dependencies, parallel groups |
| FR8 | Epic 1 | Lead Agent assigns agents based on capability matching |
| FR9 | Epic 6 | Lead Agent considers file metadata when routing |
|| FR10 | Epic 1 | nanobot agent always available as fallback
| FR11 | Epic 4 | Pre-kickoff modal shows full plan in supervised mode |
| FR12 | Epic 4 | Reassign agents in pre-kickoff modal |
| FR13 | Epic 4 | Reorder steps in pre-kickoff modal |
| FR14 | Epic 4 | Change blocking dependencies in pre-kickoff modal |
| FR15 | Epic 4 | Attach documents to specific steps |
| FR16 | Epic 4 | Chat with Lead Agent to negotiate plan changes |
| FR17 | Epic 4 | Lead Agent dynamically modifies plan from chat |
| FR18 | Epic 4 | Approve plan and trigger kick-off |
| FR19 | Epic 1 | Lead Agent never executes — pure orchestrator |
| FR20 | Epic 2 | Autonomous mode dispatches immediately |
| FR21 | Epic 2 | Parallel steps launch simultaneously |
| FR22 | Epic 2 | Sequential steps wait for blockers |
| FR23 | Epic 2 | Step completion auto-unblocks dependents |
| FR24 | Epic 2 | Unified thread per task shared by all agents |
| FR25 | Epic 2 | Structured completion messages in thread |
| FR26 | Epic 2 | User posts messages to thread during execution |
| FR27 | Epic 2 | Agents read full thread context when starting step |
| FR28 | Epic 2 | Thread context managed for LLM window limits |
| FR29 | Epic 3 | Steps progress through defined lifecycle |
| FR30 | Epic 3 | Blocked steps show visual indicator |
| FR31 | Epic 3 | Crashed step posts error with recovery instructions |
| FR32 | Epic 3 | Crashed step doesn't crash siblings — only blocks dependents |
| FR33 | Epic 3 | User can manually retry crashed step |
| FR34 | Epic 3 | Successful retry auto-unblocks dependents |
| FR35 | Epic 1 | Kanban displays step cards with real-time status |
| FR36 | Epic 1 | Execution plan visualization |
| FR37 | Epic 2 | Thread view shows structured messages in real-time |
| FR38 | Epic 3 | Activity feed shows step events |
| FR-F1 | Epic 5 | Attach files at task creation via file picker |
| FR-F2 | Epic 5 | Attach files to existing task from detail view |
| FR-F3 | Epic 5 | File chips on task input before submitting |
| FR-F4 | Epic 5 | Remove pending attachment before submission |
| FR-F5 | Epic 5 | Task directory with attachments/ and output/ subdirs |
| FR-F6 | Epic 5 | Files tab in task detail Sheet |
| FR-F7 | Epic 5 | Open file in multi-format viewer modal |
| FR-F8 | Epic 5 | PDF viewer with pages, zoom, pagination |
| FR-F9 | Epic 5 | Code viewer with syntax highlighting |
| FR-F10 | Epic 5 | HTML viewer with raw/rendered toggle |
| FR-F11 | Epic 5 | Markdown viewer with raw/rendered toggle |
| FR-F12 | Epic 5 | Image viewer with zoom |
| FR-F13 | Epic 5 | Text/CSV viewer with zoom |
| FR-F14 | Epic 5 | Download file from viewer |
| FR-F15 | Epic 5 | File serving API endpoint |
| FR-F16 | Epic 5 | File type detection for viewer routing |
| FR-F17 | Epic 6 | Task directory path in agent context |
| FR-F18 | Epic 6 | File manifest in agent context |
| FR-F19 | Epic 6 | Agent reads from attachments/ |
| FR-F20 | Epic 6 | Agent writes to output/ |
| FR-F21 | Epic 6 | System updates manifest for agent output |
| FR-F22 | Epic 5 | File metadata stored on task record |
| FR-F23 | Epic 5 | Manifest updated on user upload |
| FR-F24 | Epic 6 | Manifest updated on agent output |
| FR-F25 | Epic 5 | Dashboard reactively reflects manifest changes |
| FR-F26 | Epic 5 | Paperclip icon on task cards with files |
| FR-F27 | Epic 5 | File count next to paperclip icon |
| FR-F28 | Epic 6 | Lead Agent receives file manifest for routing |
| FR-F29 | Epic 6 | Lead Agent includes file metadata in delegation |

### NFR Distribution

| NFR | Primary Epic | Integration |
|-----|-------------|-------------|
| NFR1 (plan < 10s) | Epic 1 | AC on planning stories |
| NFR2 (modal < 2s) | Epic 4 | AC on pre-kickoff modal story |
| NFR3 (Kanban < 1s) | Epic 2 | AC on step status stories |
| NFR4 (thread < 1s) | Epic 2 | AC on thread stories |
| NFR5 (truncation 20 msgs) | Epic 2 | AC on thread context story |
| NFR6 (crash isolation) | Epic 3 | AC on crash handling stories |
| NFR7 (LLM error recovery) | Epic 3 | AC on error handling stories |
| NFR8 (subprocess isolation) | Epic 2 | AC on dispatch stories |
| NFR9 (atomic unblocking) | Epic 2 | AC on unblocking stories |
| NFR10 (no silent failures) | Epic 1 | AC on planning stories |
| NFR11 (bridge reconnect) | Epic 2 | AC on bridge stories |
| NFR12 (LLM retry) | Epic 2 | AC on dispatch stories |
| NFR13 (message format) | Epic 2 | AC on structured message stories |
| NFR-F1 (upload < 3s) | Epic 5 | AC on upload stories |
| NFR-F2 (file list < 1s) | Epic 5 | AC on Files tab story |
| NFR-F3 (viewer < 2s) | Epic 5 | AC on viewer stories |
| NFR-F4 (PDF nav < 500ms) | Epic 5 | AC on PDF viewer story |
| NFR-F5 (serve API < 1s) | Epic 5 | AC on file serving story |
| NFR-F6 (manifest after upload < 2s) | Epic 5 | AC on upload stories |
| NFR-F7 (manifest after agent < 5s) | Epic 6 | AC on bridge sync story |
| NFR-F8 (agent gets fresh manifest) | Epic 6 | AC on agent context story |
| NFR-F9 (reactive display) | Epic 5 | AC on Files tab story |
| NFR-F10 (directory creation atomic) | Epic 5 | AC on directory creation story |
| NFR-F11 (manifest reconcilable) | Epic 6 | AC on bridge sync story |
| NFR-F12 (no partial files) | Epic 5 | AC on upload story |
| NFR-F13 (unsupported type fallback) | Epic 5 | AC on viewer story |

## Epic List

### Epic 1: Task Creation & Execution Planning
User creates a task, selects supervision mode, and the Lead Agent generates a structured execution plan with steps, agent assignments, dependencies, and parallel groups — visualized as cards on the Kanban board.
**FRs covered:** FR1, FR2, FR3, FR4, FR6, FR7, FR8, FR10, FR19, FR35, FR36
**NFRs as AC:** NFR1 (plan < 10s), NFR10 (no silent planning failures)
**Implementation scope:** Convex steps table, Lead Agent planner (pure orchestrator), nanobot agent registration, ExecutionPlan type, step materialization, Kanban step cards with task grouping, execution plan visualization.

### Epic 2: Autonomous Execution & Agent Collaboration
In autonomous mode, the plan dispatches immediately. Agents execute steps in parallel/sequence, post structured completion messages to the unified thread, and dependent steps auto-unblock.
**FRs covered:** FR20, FR21, FR22, FR23, FR24, FR25, FR26, FR27, FR28, FR37
**NFRs as AC:** NFR3, NFR4, NFR5, NFR8, NFR9, NFR11, NFR12, NFR13
**Implementation scope:** Step dispatcher with asyncio.gather(), subprocess agent execution, unified thread messaging, structured completion messages with artifacts, thread context builder with truncation, dependency unblocking, real-time Kanban updates.
**Depends on:** Epic 1

### Epic 3: Step Lifecycle & Error Recovery
Steps progress through a defined lifecycle with visual indicators. Crashed steps are isolated, errors are actionable, and users can retry failed steps to unblock dependents.
**FRs covered:** FR29, FR30, FR31, FR32, FR33, FR34, FR38
**NFRs as AC:** NFR6 (crash isolation), NFR7 (LLM error recovery)
**Implementation scope:** Step status state machine, crash isolation in dispatcher, error message posting with recovery instructions, retry mechanism, activity feed with step-level events, visual indicators (blocked lock icon, crashed badge).
**Depends on:** Epic 2

### Epic 4: Pre-Kickoff Plan Review & Negotiation
In supervised mode, the user reviews the execution plan in a full-screen pre-kickoff modal, reassigns agents, reorders steps, changes dependencies, attaches documents to steps, chats with the Lead Agent to negotiate changes, and approves the plan before kick-off.
**FRs covered:** FR11, FR12, FR13, FR14, FR15, FR16, FR17, FR18
**NFRs as AC:** NFR2 (modal renders < 2s)
**Implementation scope:** Full-screen PreKickoffModal with two-panel layout (plan editor + Lead Agent chat), PlanEditor with editable step cards, agent dropdown per step, drag-and-drop reorder (@dnd-kit), dependency toggles, file attachment per step, Lead Agent chat thread, plan approval and kick-off trigger.
**Depends on:** Epic 1 (independent of Epic 2/3)

### Epic 5: File Attachment & Viewing
User attaches files to tasks at creation or later, views them in a multi-format dashboard viewer (PDF, code, HTML, Markdown, images, text), and sees file indicators on Kanban cards.
**FRs covered:** FR5, FR-F1, FR-F2, FR-F3, FR-F4, FR-F5, FR-F6, FR-F7, FR-F8, FR-F9, FR-F10, FR-F11, FR-F12, FR-F13, FR-F14, FR-F15, FR-F16, FR-F22, FR-F23, FR-F25, FR-F26, FR-F27
**NFRs as AC:** NFR-F1, NFR-F2, NFR-F3, NFR-F4, NFR-F5, NFR-F6, NFR-F9, NFR-F10, NFR-F12, NFR-F13
**Implementation scope:** Convex schema extension (files field on tasks), task directory creation (Python), Next.js API routes for upload and serving, file picker + chips on TaskInput, Files tab in TaskDetailSheet, DocumentViewerModal (PDF/code/HTML/Markdown/image/text viewers), paperclip icon + count on TaskCard.
**Depends on:** Epic 1

### Epic 6: Agent File Integration
Agents receive file context (directory path + manifest) when assigned a step, read attachments, write output files, and the dashboard reflects agent-produced files. Lead Agent uses file metadata for intelligent routing.
**FRs covered:** FR9, FR-F17, FR-F18, FR-F19, FR-F20, FR-F21, FR-F24, FR-F28, FR-F29
**NFRs as AC:** NFR-F7 (manifest after agent < 5s), NFR-F8 (fresh manifest), NFR-F11 (manifest reconcilable)
**Implementation scope:** Agent context injection (filesDir + fileManifest), Python bridge manifest sync (scan output/ → update Convex), Lead Agent file-aware routing in orchestrator, file metadata in delegation messages, activity events for file operations.
**Depends on:** Epic 2 + Epic 5

### Epic Dependencies

```
Epic 1 (Plan) ─────┬──→ Epic 2 (Execute) ──→ Epic 3 (Error Recovery)
                    │                    \
                    ├──→ Epic 4 (Pre-Kickoff)   ← independent of 2/3
                    │
                    └──→ Epic 5 (Files)  ──→ Epic 6 (Agent Files) ← also needs Epic 2
```

## Epic 1: Task Creation & Execution Planning

User creates a task, selects supervision mode, and the Lead Agent generates a structured execution plan with steps, agent assignments, dependencies, and parallel groups — visualized as cards on the Kanban board.

### Story 1.1: Extend Convex Schema for Task/Step Hierarchy

As a **developer**,
I want the Convex schema to support steps as first-class entities with task relationships and structured message types,
So that the system can track individual work units assigned to agents and their dependencies.

**Acceptance Criteria:**

**Given** the existing Convex schema with `tasks`, `messages`, and `agents` tables
**When** the schema is extended
**Then** a new `steps` table is created with fields: `taskId` (reference to tasks), `title` (string), `description` (string), `assignedAgent` (string), `status` (string — one of "planned", "assigned", "running", "completed", "crashed", "blocked"), `blockedBy` (optional array of step IDs), `parallelGroup` (number), `order` (number)
**And** the `steps` table has an index `by_taskId` for querying steps by parent task
**And** the `tasks` table gains: `executionPlan` (optional object), `supervisionMode` (optional string — "autonomous" or "supervised")
**And** the `messages` table gains: `stepId` (optional reference to steps), `type` (optional string — one of "step_completion", "user_message", "system_error", "lead_agent_plan", "lead_agent_chat"), `artifacts` (optional array of objects with path, action, description, diff)
**And** the Convex dev server starts without schema validation errors
**And** existing data in all tables continues to work (all new fields are optional)

**Given** the new schema is deployed
**When** a developer queries the steps table with `by_taskId` index
**Then** steps for a specific task are returned efficiently

### Story 1.2: Add Supervision Mode to Task Creation

As a **user**,
I want to select autonomous or supervised mode when creating a task,
So that I can choose whether to review the execution plan before agents start working.

**Acceptance Criteria:**

**Given** the TaskInput component on the dashboard
**When** the user expands the task creation options
**Then** a supervision mode selector is visible with two options: "Autonomous" (default) and "Supervised"
**And** the selector uses a ShadCN `Select` or toggle component consistent with the existing design system

**Given** the user types a task description and selects a supervision mode
**When** the user submits the task
**Then** the task is created in Convex with the selected `supervisionMode` value ("autonomous" or "supervised")
**And** the task card appears in the Inbox column on the Kanban board

**Given** the user submits a task without explicitly selecting supervision mode
**When** the task is created
**Then** the `supervisionMode` defaults to "autonomous"

**Given** the task is created with supervision mode set
**When** the task record is queried from Convex
**Then** the `supervisionMode` field reflects the user's selection

### Story 1.3: Register nanobot Agent as System Fallback

As a **user**,
I want a nanobot agent always available in the system,
So that any task step that doesn't match a specialist agent still has a capable agent to handle it.

**Acceptance Criteria:**

**Given** the agent definitions directory exists
**When** the system is initialized
**Then** a `nanobot.yaml` definition file exists with: a general-purpose system prompt, no specialized skills restrictions, and a name of "nanobot"

**Given** the Agent Gateway starts up
**When** the gateway syncs agent definitions to the Convex `agents` table
**Then** the nanobot agent is present in the agents table with status "active"
**And** if the nanobot agent was missing from the table, it is recreated from the YAML definition

**Given** a user or system attempts to delete the nanobot agent
**When** the deletion is attempted
**Then** the deletion is rejected — the nanobot agent cannot be deleted or deactivated
**And** a clear message indicates "nanobot agent is a system agent and cannot be removed"

**Given** the agents sidebar in the dashboard
**When** the nanobot agent is displayed
**Then** it is visually distinguishable as a system agent (e.g., a subtle "System" badge or 🦉 Owl icon)

### Story 1.4: Enforce Lead Agent as Pure Orchestrator

As a **developer**,
I want the Lead Agent to be structurally prevented from executing tasks,
So that the pure orchestrator invariant is guaranteed — the Lead Agent only plans, delegates, and coordinates.

**Acceptance Criteria:**

**Given** a task is submitted and the Lead Agent is invoked
**When** the executor module receives the Lead Agent as the agent to run
**Then** the executor routes the request to the planner module (`planner.py`), NOT the execution pipeline
**And** the Lead Agent never spawns as an execution subprocess

**Given** the Lead Agent's agent configuration
**When** the agent loop is initialized for the Lead Agent
**Then** the Lead Agent has ONLY planning tools available (no file write, no code execution, no shell access)
**And** execution tools are structurally absent from the Lead Agent's tool set

**Given** any code path that could potentially dispatch the Lead Agent as an executor
**When** the dispatch is attempted
**Then** the system raises an error or redirects to the planner — there is no code path where the Lead Agent executes a task step

**Given** the orchestrator module coordinates a multi-step task
**When** steps are assigned to agents
**Then** the Lead Agent is never assigned as the executor of any step — it only appears as the plan generator

### Story 1.5: Generate Execution Plans

As a **user**,
I want the Lead Agent to generate a structured execution plan when I submit a task,
So that I can see how my goal will be broken into steps with assigned agents, dependencies, and parallel groups.

**Acceptance Criteria:**

**Given** a task is created in Convex with status "planning"
**When** the Python bridge subscription detects the new task
**Then** the Lead Agent planner is invoked with the task description, available agents list (from agents table), and any attached file metadata
**And** the task status remains "planning" during plan generation

**Given** the Lead Agent planner processes the task
**When** planning completes
**Then** it produces an `ExecutionPlan` object with: an array of steps (each with tempId, title, description, assignedAgent, blockedBy references, parallelGroup, order), generatedAt timestamp (ISO 8601), and generatedBy "lead-agent"
**And** the plan is written to the task record's `executionPlan` field via the bridge
**And** plan generation completes in < 10 seconds from task submission (NFR1)

**Given** the Lead Agent assigns agents to steps
**When** a step matches a specialist agent's capabilities
**Then** that specialist is assigned to the step
**And** when no specialist matches, the nanobot agent is assigned as fallback (FR10)

**Given** the Lead Agent identifies steps that can run in parallel
**When** the plan is structured
**Then** parallel steps share the same `parallelGroup` number
**And** steps that depend on others have those dependencies listed in `blockedBy` (referencing tempIds)

**Given** plan generation fails (LLM error, timeout, invalid output)
**When** the failure is detected
**Then** the task status is set to "failed" with a clear error message (NFR10)
**And** an activity event is created with the error details
**And** no steps are created — the task stays in a recoverable state

**Given** a task with a single-step goal (e.g., "remind me to call the dentist")
**When** the Lead Agent plans it
**Then** the plan still contains a valid ExecutionPlan with a single step assigned to an appropriate agent

### Story 1.6: Materialize Plans into Step Records

As a **developer**,
I want execution plans to be converted into real step records in Convex on kick-off,
So that individual steps can be tracked, dispatched, and displayed on the Kanban board.

**Acceptance Criteria:**

**Given** a task has an `executionPlan` stored on its record
**When** the plan is kicked off (autonomous mode: immediately after plan generation; supervised mode: after user approval)
**Then** the `plan_materializer` creates one `steps` document in Convex for each step in the ExecutionPlan
**And** each step document includes: `taskId` referencing the parent task, `title`, `description`, `assignedAgent`, `status`, `blockedBy` (converted from tempIds to real step IDs), `parallelGroup`, `order`

**Given** a step has no entries in its `blockedBy` array
**When** the step record is created
**Then** its status is set to "assigned" (ready for dispatch)

**Given** a step has one or more entries in its `blockedBy` array
**When** the step record is created
**Then** its status is set to "blocked"

**Given** plan materialization completes
**When** all step records are created
**Then** the task status transitions from "planning" (autonomous) or "reviewing_plan" (supervised) to "running"
**And** the `executionPlan` field is preserved on the task record as a snapshot of the original plan
**And** an activity event is created: "Task kicked off with {N} steps"

**Given** plan materialization fails (Convex error, invalid data)
**When** the error is detected
**Then** no partial step records are left — materialization is atomic (all or nothing)
**And** the task status is set to "failed" with a clear error message

### Story 1.7: Render Step Cards on Kanban Board

As a **user**,
I want to see steps as individual cards on the Kanban board grouped by parent task,
So that I can track the progress of each unit of work across my agents.

**Acceptance Criteria:**

**Given** a task has been kicked off and step records exist in Convex
**When** the Kanban board renders
**Then** each step appears as an individual `StepCard` in the column matching its status (assigned → "To Do", running → "In Progress", completed → "Done")
**And** steps belonging to the same task are visually grouped with a `TaskGroupHeader` showing the parent task title

**Given** a StepCard renders on the board
**When** the card is displayed
**Then** it shows: step title, assigned agent name/avatar, status badge (color + text label per UX spec), and parent task name as a subtle label
**And** the card follows the ShadCN Card component pattern with Tailwind styling consistent with the existing design system

**Given** a step's status changes in Convex (e.g., "assigned" → "running")
**When** the Convex reactive query fires
**Then** the StepCard moves to the new column with a smooth Motion transition (layoutId)
**And** the status badge updates in real-time
**And** the update is reflected within 1 second of the event (NFR3)

**Given** multiple tasks have been kicked off
**When** the Kanban board renders
**Then** steps from different tasks are separated by their respective TaskGroupHeaders within each column
**And** the board handles multiple task groups without layout issues

**Given** a task with no steps (still in "planning" status)
**When** the Kanban board renders
**Then** the task appears as a regular task card (not step cards) until steps are materialized

### Story 1.8: Visualize Execution Plan

As a **user**,
I want to see the execution plan showing steps, dependencies, parallel groups, and assigned agents,
So that I understand the full structure of how my goal will be accomplished before and during execution.

**Acceptance Criteria:**

**Given** a task has an `executionPlan` on its record (before or after kick-off)
**When** the user opens the task detail and navigates to the Execution Plan tab
**Then** the `ExecutionPlanTab` displays all steps from the plan with: step title, assigned agent, parallel group indicator, and dependency relationships

**Given** steps have dependency relationships (blockedBy)
**When** the execution plan renders
**Then** visual indicators (lines, arrows, or indentation) show which steps depend on which
**And** parallel steps (same parallelGroup) are visually grouped side by side or in a parallel lane

**Given** steps are in various statuses (after kick-off)
**When** the plan visualization renders
**Then** each step shows its current status with the appropriate color coding (consistent with Kanban status badges)
**And** completed steps are visually distinct from pending/running steps

**Given** the user opens the execution plan for a task still in "planning" status
**When** the plan has not yet been generated
**Then** a muted placeholder displays: "Generating execution plan..." with a loading indicator

**Given** the task's `executionPlan` field is populated
**When** the ExecutionPlanTab renders
**Then** it renders within 2 seconds (leveraging Convex reactive queries for real-time data)

## Epic 2: Autonomous Execution & Agent Collaboration

In autonomous mode, the plan dispatches immediately. Agents execute steps in parallel/sequence, post structured completion messages to the unified thread, and dependent steps auto-unblock.

### Story 2.1: Dispatch Steps in Autonomous Mode

As a **user**,
I want my task to start executing immediately after the plan is generated in autonomous mode,
So that I don't have to manually trigger execution for straightforward goals.

**Acceptance Criteria:**

**Given** a task was created with `supervisionMode: "autonomous"`
**When** the plan materializer finishes creating step records (Story 1.6)
**Then** the step dispatcher is triggered automatically — no user action required (FR20)
**And** the task status transitions to "running"
**And** an activity event is created: "Task dispatched in autonomous mode"

**Given** steps are dispatched in autonomous mode
**When** the dispatch begins
**Then** all steps with status "assigned" (no blockers) are queued for immediate execution
**And** steps with status "blocked" remain blocked until their dependencies complete

**Given** a task was created with `supervisionMode: "supervised"`
**When** the plan materializer finishes
**Then** the step dispatcher is NOT triggered — the task waits in "reviewing_plan" status for user approval (Epic 4)

### Story 2.2: Execute Steps as Agent Subprocesses

As a **developer**,
I want steps to execute as isolated agent subprocesses with parallel dispatch for independent steps,
So that agents run concurrently without contention and a failure in one doesn't crash others.

**Acceptance Criteria:**

**Given** the step dispatcher receives a set of steps to execute
**When** multiple steps share the same `parallelGroup` and all have status "assigned"
**Then** the dispatcher launches all of them simultaneously using `asyncio.gather()` (FR21)
**And** each agent runs as a separate Python subprocess with its own workspace under `~/.nanobot/agents/{agentName}/`
**And** no shared state exists between concurrent agent subprocesses (NFR8)

**Given** steps are in different parallel groups with sequential dependencies
**When** the dispatcher processes them
**Then** it dispatches parallel group 1 first, waits for all steps in that group to complete, then dispatches parallel group 2, and so on (FR22)

**Given** an agent subprocess starts for a step
**When** the subprocess is running
**Then** the step's status is updated to "running" in Convex via the bridge
**And** an activity event is created: "Agent {agentName} started step: {stepTitle}"

**Given** an agent subprocess completes successfully
**When** the completion is detected
**Then** the step's status is updated to "completed" in Convex
**And** an activity event is created: "Agent {agentName} completed step: {stepTitle}"

**Given** an agent subprocess crashes (exception, timeout, provider error)
**When** the failure is detected
**Then** the step's status is updated to "crashed" (handled in Epic 3)
**And** other running subprocesses in the same parallel group continue unaffected (NFR8)
**And** the asyncio.gather() call uses `return_exceptions=True` to prevent one crash from cancelling siblings

### Story 2.3: Auto-Unblock Dependent Steps

As a **user**,
I want dependent steps to start automatically when their prerequisites complete,
So that multi-step tasks progress without manual intervention.

**Acceptance Criteria:**

**Given** a step completes with status "completed"
**When** the completion is recorded in Convex
**Then** the system checks all steps in the same task that reference this step in their `blockedBy` array (FR23)

**Given** a blocked step has ALL of its `blockedBy` references now in "completed" status
**When** the unblocking check runs
**Then** the step's status transitions from "blocked" to "assigned"
**And** the `blockedBy` array is cleared
**And** an activity event is created: "Step {stepTitle} unblocked"
**And** the unblocking is atomic — a step is only unblocked when ALL blockers are completed (NFR9)

**Given** a blocked step has SOME but not ALL of its blockers completed
**When** the unblocking check runs
**Then** the step remains "blocked" — no premature unblocking

**Given** newly unblocked steps exist after a completion
**When** the dispatcher detects newly "assigned" steps
**Then** it dispatches them for execution (respecting parallel groups)

**Given** all steps in a task reach "completed" status
**When** the last step completes and unblocking finishes
**Then** the task status transitions to "completed"
**And** an activity event is created: "Task completed — all {N} steps finished"

### Story 2.4: Build Unified Thread per Task

As a **user**,
I want a single thread per task where all agents, the system, and I can communicate,
So that I have one place to follow the entire execution story.

**Acceptance Criteria:**

**Given** a task exists in Convex
**When** any participant (agent, user, system) posts a message
**Then** the message is stored in the `messages` table with the task's `taskId` (FR24)
**And** all messages for the task are queryable via a `by_taskId` index

**Given** a task is being executed
**When** the user types a message in the thread input and submits
**Then** the message is stored with `role: "user"` and `type: "user_message"` (FR26)
**And** the message appears in the thread in real-time via Convex reactive query

**Given** the Lead Agent generates or updates a plan
**When** the plan message is posted
**Then** it is stored with `role: "lead_agent"` and `type: "lead_agent_plan"` or `type: "lead_agent_chat"`

**Given** multiple agents work on steps for the same task
**When** they each post messages to the thread
**Then** all messages appear in a single chronological stream — no separate per-agent or per-step threads

### Story 2.5: Post Structured Completion Messages

As a **user**,
I want agents to post structured completion messages showing what files they created or modified,
So that I can see exactly what each agent produced and dependent agents get precise context.

**Acceptance Criteria:**

**Given** an agent completes its step and produced file operations
**When** the completion message is posted to the unified thread
**Then** the message includes `role: "agent"`, `type: "step_completion"`, `agentName`, `stepId`, human-readable `content`, and an `artifacts` array (FR25, NFR13)
**And** each artifact entry includes: `path` (file path relative to task directory), `action` ("created" or "modified"), `description` (for created files), `diff` (for modified files)

**Given** an agent completes a step with no file operations
**When** the completion message is posted
**Then** the message includes `content` describing what was done and `artifacts` is an empty array or omitted

**Given** multiple agents complete steps on the same task
**When** their completion messages are posted
**Then** each message is associated with the correct `stepId` in the unified thread
**And** the chronological order in the thread reflects the actual completion order

### Story 2.6: Build Thread Context for Agents

As a **developer**,
I want agents to receive relevant thread context when starting their step,
So that dependent agents have the information they need to continue the work.

**Acceptance Criteria:**

**Given** an agent is about to start a step
**When** the executor builds the thread context for that agent
**Then** the context includes the last 20 messages from the task's unified thread (NFR5)
**And** if more than 20 messages exist, a note is prepended: "(N earlier messages omitted)"
**And** the latest user message (if any) is separated into a `[Latest Follow-up]` section

**Given** a step has direct predecessors in its `blockedBy` array
**When** the thread context is built
**Then** the structured completion messages of ALL direct predecessors are ALWAYS included in the context, even if they fall outside the 20-message window
**And** predecessor messages are injected at their chronological position (or as a preamble if before the window)

**Given** the thread contains structured completion messages with artifacts
**When** the context is injected into the agent's prompt
**Then** artifact details (file paths, diffs, descriptions) are formatted in a parseable way that fits within the LLM context window alongside the agent's system prompt and task description

**Given** the thread is empty (first step to execute)
**When** the context is built
**Then** the agent receives only the task description and no thread context

### Story 2.7: Render Thread View in Real-Time

As a **user**,
I want to see the unified thread with structured agent messages and file references updating in real-time,
So that I can follow agent collaboration as it happens.

**Acceptance Criteria:**

**Given** a task's thread has messages
**When** the user opens the task detail and navigates to the Thread tab
**Then** all messages are displayed chronologically with: author (agent name with avatar, user, or system), timestamp, message content, and artifacts if present (FR37)

**Given** an agent posts a structured completion message with artifacts
**When** the ThreadMessage component renders it
**Then** each artifact is displayed with: file path (visually clickable), action badge ("created" or "modified"), description (for created files), and diff preview (for modified files)
**And** the `ArtifactRenderer` component handles the artifact display

**Given** a new message is posted to the thread (by agent, user, or system)
**When** the Convex reactive query fires
**Then** the new message appears in the thread within 1 second (NFR4)
**And** the thread auto-scrolls to the latest message

**Given** the thread has many messages
**When** the user scrolls up
**Then** older messages are visible and the auto-scroll pauses until the user scrolls back to the bottom

**Given** a user message is posted (Story 2.4)
**When** it appears in the thread
**Then** it is visually distinct from agent messages (different alignment or background per UX spec)

## Epic 3: Step Lifecycle & Error Recovery

Steps progress through a defined lifecycle with visual indicators. Crashed steps are isolated, errors are actionable, and users can retry failed steps to unblock dependents.

### Story 3.1: Implement Step Status State Machine

As a **developer**,
I want step status transitions to follow a defined state machine,
So that steps never enter invalid states and the UI can reliably reflect their lifecycle.

**Acceptance Criteria:**

**Given** the step lifecycle is defined as: planned → assigned → running → completed | crashed, and blocked as a parallel state
**When** a step status update is requested via Convex mutation
**Then** the mutation validates that the transition is legal (e.g., "assigned" → "running" is valid, "completed" → "assigned" is invalid unless retrying)
**And** illegal transitions are rejected with a clear error

**Given** a step transitions to any new status
**When** the mutation completes
**Then** a corresponding activity event is created with eventType matching the status (e.g., "step_started", "step_completed", "step_crashed") (FR29)
**And** the activity includes: taskId, stepId, agentName, description, timestamp

**Given** the `state_machine.py` module in the Python backend
**When** it is refactored for step-level states
**Then** it validates step transitions identically to the Convex-side validation
**And** Python and Convex agree on valid transitions — no drift

### Story 3.2: Visualize Blocked and Crashed Steps

As a **user**,
I want to see at a glance which steps are blocked and which have crashed,
So that I understand the current state of my task without clicking into each step.

**Acceptance Criteria:**

**Given** a step has status "blocked" with entries in its `blockedBy` array
**When** the StepCard renders on the Kanban board
**Then** a lock icon is displayed on the card (FR30)
**And** the names/titles of the blocking steps are shown as a tooltip or subtitle on the card
**And** the card is visually muted (reduced opacity or gray tint) to indicate it cannot proceed

**Given** a step has status "crashed"
**When** the StepCard renders
**Then** a red "Crashed" badge is displayed on the card
**And** the card uses the destructive color from the design system
**And** the card is NOT removed from the board — it stays visible in its column

**Given** a step transitions from "blocked" to "assigned" (unblocked)
**When** the Kanban updates
**Then** the lock icon is removed, opacity returns to normal, and the card moves to the appropriate column with a smooth Motion transition

### Story 3.3: Post Crash Errors with Recovery Instructions

As a **user**,
I want to see exactly what went wrong when an agent crashes with actionable recovery instructions,
So that I can fix the issue and retry.

**Acceptance Criteria:**

**Given** an agent subprocess crashes during step execution
**When** the crash is detected by the step dispatcher
**Then** the step status is set to "crashed" in Convex
**And** a structured error message is posted to the unified thread with: `role: "system"`, `type: "system_error"`, `stepId`, human-readable `content` describing the error and recovery action (FR31)
**And** an activity event is created: "Agent {agentName} crashed on step: {stepTitle}"

**Given** the crash is due to an LLM provider error (OAuth expiry, rate limit, timeout)
**When** the error message is constructed
**Then** the content includes the specific provider error and an actionable command (e.g., "Run `nanobot provider login --provider anthropic`") (NFR7)

**Given** the crash is due to an unknown exception
**When** the error message is constructed
**Then** the content includes the exception type and message, and suggests checking agent logs

**Given** a step crashes
**When** the crash is processed
**Then** sibling steps in the same parallel group continue running unaffected (FR32, NFR6)
**And** only direct dependents of the crashed step remain "blocked"
**And** the parent task does NOT transition to "failed" — it stays "running" (the user can still retry)

### Story 3.4: Retry Crashed Steps

As a **user**,
I want to retry a crashed step so it re-enters the execution pipeline,
So that I can recover from transient errors without restarting the entire task.

**Acceptance Criteria:**

**Given** a step has status "crashed"
**When** the user views the step (on StepCard or in task detail)
**Then** a "Retry" button is visible on the crashed step

**Given** the user clicks "Retry" on a crashed step
**When** the retry is triggered
**Then** the step status transitions from "crashed" to "assigned" (FR33)
**And** the step is re-queued for dispatch by the step dispatcher
**And** an activity event is created: "User retried step: {stepTitle}"
**And** a system message is posted to the thread: "Step {stepTitle} retried by user"

**Given** a retried step completes successfully
**When** the completion is recorded
**Then** the auto-unblock mechanism runs for its dependents (FR34)
**And** previously blocked dependents are unblocked and dispatched

**Given** a retried step crashes again
**When** the crash is recorded
**Then** the step returns to "crashed" status with a new error message
**And** the user can retry again — there is no retry limit for MVP

### Story 3.5: Extend Activity Feed with Step Events

As a **user**,
I want the activity feed to show step-level events alongside task events,
So that I have a timeline of everything happening across my agents.

**Acceptance Criteria:**

**Given** step lifecycle events occur (assigned, started, completed, crashed, unblocked, retried)
**When** the activity feed renders
**Then** each event appears as a FeedItem with: event type icon, agent name, step title, timestamp, and brief description (FR38)
**And** step events use the activity event types: "step_assigned", "step_started", "step_completed", "step_crashed", "step_retrying", "step_unblocked"

**Given** the feed has both task-level and step-level events
**When** the ActivityFeed renders
**Then** events are displayed in reverse chronological order (newest first)
**And** step events are visually distinguishable from task events (e.g., indented or with a step icon)

**Given** multiple steps complete rapidly (parallel execution)
**When** the feed updates
**Then** all events appear in real-time without missing any

**Given** an error event occurs (step_crashed, system_error)
**When** the FeedItem renders
**Then** it uses the destructive color to draw attention

## Epic 4: Pre-Kickoff Plan Review & Negotiation

In supervised mode, the user reviews the execution plan in a full-screen pre-kickoff modal, reassigns agents, reorders steps, changes dependencies, attaches documents to steps, chats with the Lead Agent to negotiate changes, and approves the plan before kick-off.

### Story 4.1: Build Pre-Kickoff Modal Shell

As a **user**,
I want a full-screen modal to open when my supervised task's plan is ready,
So that I have a dedicated workspace to review and edit the plan before anything executes.

**Acceptance Criteria:**

**Given** a task was created with `supervisionMode: "supervised"`
**When** the Lead Agent completes plan generation and the task status becomes "reviewing_plan"
**Then** the `PreKickoffModal` opens automatically as a full-screen modal overlay (not a Sheet) (FR11)
**And** the modal has a two-panel layout: plan editor (left) and Lead Agent chat (right)
**And** the modal header shows the task title and a "Kick-off" button (disabled until the user is ready)

**Given** the PreKickoffModal is open
**When** the execution plan data is loaded from the task's `executionPlan` field
**Then** the plan renders with all steps, agent assignments, dependencies, and parallel groups within 2 seconds (NFR2)

**Given** the user clicks outside the modal or presses Escape
**When** the close action is triggered
**Then** the modal closes but the task remains in "reviewing_plan" status — the plan is preserved
**And** the user can reopen the modal from the task detail or a "Review Plan" button on the task card

### Story 4.2: Reassign Agents to Steps

As a **user**,
I want to change which agent is assigned to any step in the plan,
So that I can override the Lead Agent's assignments based on my knowledge of agent strengths.

**Acceptance Criteria:**

**Given** the PlanEditor displays step cards in the PreKickoffModal
**When** the user clicks the agent assignment on a step card
**Then** a dropdown appears listing all available agents from the agents table (FR12)
**And** the currently assigned agent is highlighted

**Given** the user selects a different agent from the dropdown
**When** the selection is made
**Then** the step's `assignedAgent` is updated in the local plan state immediately (optimistic UI)
**And** the plan editor reflects the new assignment on the step card

**Given** the user reassigns multiple steps
**When** the plan is reviewed
**Then** all reassignments are preserved in the local plan state until kick-off

### Story 4.3: Reorder Steps and Edit Dependencies

As a **user**,
I want to reorder steps and change blocking dependencies in the plan,
So that I can adjust the execution sequence based on my understanding of the work.

**Acceptance Criteria:**

**Given** the PlanEditor displays step cards
**When** the user drags a step card to a new position
**Then** the step order updates to reflect the new position (FR13)
**And** drag-and-drop uses @dnd-kit/core (or equivalent) for accessible, smooth reordering
**And** the `order` and `parallelGroup` values update accordingly

**Given** the user wants to change a dependency
**When** the user toggles a dependency relationship between two steps (e.g., via a checkbox or connection line UI)
**Then** the `blockedBy` array on the dependent step is updated to add or remove the blocker (FR14)
**And** the plan editor visually shows the updated dependency (arrow/line appears or disappears)

**Given** the user creates a circular dependency (A blocks B, B blocks A)
**When** the invalid state is detected
**Then** the UI prevents the action and shows a warning: "Circular dependency detected"

**Given** the user reorders or changes dependencies
**When** reviewing the plan
**Then** all changes are reflected in the local plan state and the visual layout updates immediately

### Story 4.4: Attach Documents to Steps

As a **user**,
I want to attach documents to specific steps in the plan,
So that individual agents receive targeted context for their work.

**Acceptance Criteria:**

**Given** a step card in the PlanEditor
**When** the user clicks an "Attach" button on the step card
**Then** a file picker opens allowing selection of files (FR15)

**Given** the user selects files for a specific step
**When** the files are attached
**Then** the step card shows the attached file names
**And** the step's `attachedFiles` array in the plan is updated

**Given** the user attaches files to multiple steps
**When** reviewing the plan
**Then** each step shows only its own attached files

**Given** the plan is kicked off with step-level file attachments
**When** the step records are materialized
**Then** each step's file attachments are included in the agent's context when the step is dispatched

### Story 4.5: Chat with Lead Agent for Plan Negotiation

As a **user**,
I want to chat with the Lead Agent in the pre-kickoff modal to request plan changes,
So that I can negotiate the execution strategy conversationally.

**Acceptance Criteria:**

**Given** the PreKickoffModal is open with the chat panel on the right
**When** the user types a message and sends it
**Then** the message is posted to the task's unified thread with `role: "user"` and `type: "lead_agent_chat"` (FR16)
**And** the message appears in the chat panel immediately

**Given** the user posts a chat message requesting a plan change (e.g., "Add a final step for the general agent to write a summary")
**When** the Lead Agent receives the message via bridge subscription
**Then** the Lead Agent processes the request and responds with either:
  - An updated `ExecutionPlan` written to the task record (FR17)
  - A clarifying question or acknowledgment posted as a `lead_agent_chat` message

**Given** the Lead Agent updates the ExecutionPlan
**When** the task record's `executionPlan` field changes
**Then** the PlanEditor re-renders with the updated plan (new steps, changed assignments, etc.)
**And** the chat panel shows the Lead Agent's response explaining the changes

**Given** the user and Lead Agent exchange multiple messages
**When** the conversation continues
**Then** all messages appear chronologically in the chat panel
**And** the plan editor always reflects the latest version of the plan

### Story 4.6: Approve Plan and Kick-Off

As a **user**,
I want to approve the plan and trigger execution from the pre-kickoff modal,
So that I have a clear moment of "go" after reviewing and shaping the plan.

**Acceptance Criteria:**

**Given** the PreKickoffModal is open and the user has finished reviewing/editing the plan
**When** the user clicks the "Kick-off" button
**Then** the current plan state (including any user edits — reassignments, reorders, dependency changes, file attachments) is saved to the task's `executionPlan` field in Convex (FR18)
**And** the plan materializer is triggered to create step records (Story 1.6)
**And** the step dispatcher begins execution (Story 2.1)
**And** the modal closes
**And** the task status transitions from "reviewing_plan" to "running"
**And** an activity event is created: "User approved plan and kicked off task"

**Given** the user clicks "Kick-off" without making any edits
**When** the kick-off is triggered
**Then** the original Lead Agent plan is used as-is

**Given** the user closes the modal without clicking "Kick-off"
**When** the modal is closed
**Then** the task remains in "reviewing_plan" status with the plan preserved
**And** the user can reopen the modal and resume editing at any time

## Epic 5: File Attachment & Viewing

User attaches files to tasks at creation or later, views them in a multi-format dashboard viewer (PDF, code, HTML, Markdown, images, text), and sees file indicators on Kanban cards.

### Story 5.1: Extend Schema and Create Task Directories

As a **developer**,
I want the tasks table to support file metadata and the backend to create per-task directories,
So that files have a structured home and the dashboard knows what files exist on each task.

**Acceptance Criteria:**

**Given** the existing Convex `tasks` table schema
**When** the schema is extended
**Then** the `tasks` table gains a `files` field: optional array of objects with `{ name: string, type: string, size: number, subfolder: string, uploadedAt: string }` (FR-F22)
**And** the Convex dev server starts without schema validation errors
**And** existing tasks without files continue to work (field is optional)

**Given** a new task is created in Convex
**When** the Python bridge detects the new task via subscription
**Then** the bridge creates `~/.nanobot/tasks/{task-id}/attachments/` and `~/.nanobot/tasks/{task-id}/output/` (FR-F5)
**And** directory creation is atomic — failure is logged as an activity event with a clear error (NFR-F10)
**And** the task-id used in the directory path is a filesystem-safe conversion of the Convex task ID

**Given** the task directory already exists (idempotent)
**When** directory creation is triggered again
**Then** no error occurs

### Story 5.2: Upload Files at Task Creation

As a **user**,
I want to attach files when creating a task by selecting them from a file picker,
So that agents receive relevant documents alongside my task description.

**Acceptance Criteria:**

**Given** the TaskInput component on the dashboard
**When** the user clicks the attachment button (paperclip icon) next to the task input
**Then** a native file picker dialog opens allowing selection of one or more files (FR-F1)

**Given** the user selects files
**When** the files are selected
**Then** each file appears as a chip below the task input showing file name and size (FR-F3)
**And** the user can remove any pending attachment by clicking X on the chip (FR-F4)

**Given** the user submits a task with pending file attachments
**When** the form is submitted
**Then** the task is created in Convex first (optimistic UI)
**And** files are uploaded to `~/.nanobot/tasks/{task-id}/attachments/` via `POST /api/tasks/[taskId]/files` (multipart form data)
**And** on success, the task's `files` array is updated with metadata: `{ name, type, size, subfolder: "attachments", uploadedAt }` (FR-F23)
**And** upload completes within 3 seconds for files up to 10MB (NFR-F1)
**And** manifest reflects upload within 2 seconds (NFR-F6)

**Given** a file upload fails mid-transfer
**When** the error is detected
**Then** no partial file is left in the task directory (NFR-F12)
**And** an error message is shown to the user

### Story 5.3: Build Files Tab in Task Detail

As a **user**,
I want to see a list of all files on a task in a dedicated Files tab,
So that I can browse attachments and outputs in one place.

**Acceptance Criteria:**

**Given** the TaskDetailSheet exists
**When** the user opens the detail sheet for a task
**Then** a "Files" tab is available alongside existing tabs (FR-F6)

**Given** the user opens the Files tab
**When** the task has files in its manifest
**Then** files are listed with: file type icon, name, size (human-readable), subfolder label ("attachment" or "output")
**And** attachments and outputs are grouped with clear section headers
**And** the list loads within 1 second (NFR-F2)

**Given** the task's file manifest updates (new upload or agent output)
**When** the reactive query fires
**Then** the Files tab updates in real-time without manual refresh (FR-F25, NFR-F9)

**Given** a task has no files
**When** the Files tab is opened
**Then** a muted placeholder displays: "No files yet. Attach files or wait for agent output."

### Story 5.4: Attach Files to Existing Tasks

As a **user**,
I want to add files to a task that already exists,
So that I can provide additional context to agents working on in-progress tasks.

**Acceptance Criteria:**

**Given** the Files tab is open in TaskDetailSheet
**When** the user clicks "Attach File"
**Then** a file picker opens (FR-F2)

**Given** the user selects files
**When** the upload completes
**Then** files are uploaded to `~/.nanobot/tasks/{task-id}/attachments/` via the same API route as Story 5.2
**And** the task's `files` array is updated (FR-F23)
**And** the Files tab updates reactively (FR-F25)
**And** an activity event is created: "User attached {count} file(s)"
**And** upload completes within 3 seconds for files up to 10MB (NFR-F1)

### Story 5.5: File Indicators on Task Cards

As a **user**,
I want to see at a glance which tasks have files on the Kanban board,
So that I can identify document-related tasks without clicking into each one.

**Acceptance Criteria:**

**Given** a task has one or more files in its manifest
**When** the TaskCard or StepCard renders on the Kanban board
**Then** a paperclip icon is displayed (FR-F26)
**And** the file count is shown next to the icon (FR-F27)

**Given** a task has no files
**When** the card renders
**Then** no paperclip icon or count is shown

**Given** a file is added (by user or agent)
**When** the reactive query updates
**Then** the icon and count appear or update in real-time

### Story 5.6: File Serving API Route

As a **developer**,
I want an API endpoint that serves files from task directories with correct content types,
So that the dashboard viewer can fetch and render any file.

**Acceptance Criteria:**

**Given** a file exists at `~/.nanobot/tasks/{task-id}/{subfolder}/{filename}`
**When** the dashboard requests `GET /api/tasks/[taskId]/files/[subfolder]/[filename]`
**Then** the raw file bytes are returned with correct `Content-Type` header (FR-F15, FR-F16)
**And** response includes `Content-Disposition` header
**And** response returns within 1 second for files up to 10MB (NFR-F5)

**Given** the file does not exist
**When** the API is called
**Then** a 404 response is returned

**Given** a request includes path traversal characters (`../`)
**When** the path is validated
**Then** the request is rejected with 400 — no directory traversal outside the task directory

**Given** a file has ambiguous or missing extension
**When** MIME detection runs
**Then** fallback to `application/octet-stream`

### Story 5.7: Viewer Modal with Text and Code Viewers

As a **user**,
I want to click a file and see it rendered in a viewer modal with support for text and code files,
So that I can read content and syntax-highlighted code without leaving the dashboard.

**Acceptance Criteria:**

**Given** the Files tab is open
**When** the user clicks a file entry
**Then** a `DocumentViewerModal` opens showing the file (FR-F7)
**And** the modal header shows: file name, size, type badge
**And** a "Download" button triggers browser download (FR-F14)
**And** the modal closes with Escape or clicking outside

**Given** the user opens a plain text file (`.txt`, `.csv`, `.log`, `.json`, `.xml`, `.yaml`)
**When** the viewer renders
**Then** content is displayed in monospace font with zoom controls (FR-F13)
**And** renders within 2 seconds for files up to 10MB (NFR-F3)

**Given** the user opens a code file (`.py`, `.ts`, `.tsx`, `.js`, `.jsx`, etc.)
**When** the viewer renders
**Then** content is displayed with syntax highlighting via `react-syntax-highlighter` and line numbers (FR-F9)
**And** language is auto-detected from file extension

**Given** the user opens an unsupported file type
**When** the viewer cannot render it
**Then** a message shows: "Preview not available" with a Download button as fallback (NFR-F13)

### Story 5.8: PDF Viewer

As a **user**,
I want to view PDF files in the dashboard with page navigation and zoom,
So that I can read documents without opening an external app.

**Acceptance Criteria:**

**Given** the user opens a PDF file from the Files tab
**When** the DocumentViewerModal renders
**Then** the PDF is displayed using `react-pdf` with the first page visible (FR-F8)
**And** page navigation: previous, next, current/total indicator
**And** zoom controls: zoom in, zoom out, fit-to-width
**And** first page renders within 2 seconds (NFR-F3)

**Given** the user navigates pages
**When** next/previous is clicked
**Then** the target page renders within 500ms (NFR-F4)

**Given** a corrupted PDF
**When** rendering fails
**Then** error message shown with Download fallback (NFR-F13)

### Story 5.9: HTML and Markdown Viewers

As a **user**,
I want to view HTML and Markdown files in rendered mode with a raw source toggle,
So that I can read agent-produced reports and inspect the source when needed.

**Acceptance Criteria:**

**Given** the user opens an HTML file
**When** the viewer renders
**Then** HTML is displayed in a sandboxed iframe (`sandbox="allow-same-origin"`) (FR-F10)
**And** a "Raw / Rendered" toggle is visible
**And** "Raw" shows HTML source with syntax highlighting
**And** scripts do not execute in the sandbox

**Given** the user opens a Markdown file
**When** the viewer renders
**Then** Markdown is rendered as formatted HTML using `react-markdown` (FR-F11)
**And** supports: headings, lists, tables, code blocks, bold/italic, links
**And** a "Raw / Rendered" toggle is visible
**And** "Raw" shows raw Markdown in monospace

### Story 5.10: Image Viewer

As a **user**,
I want to view image files in the dashboard with zoom controls,
So that I can inspect screenshots and reference images.

**Acceptance Criteria:**

**Given** the user opens an image file (`.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`, `.webp`)
**When** the viewer renders
**Then** the image is displayed centered with zoom controls: zoom in, zoom out, fit-to-container, actual size (FR-F12)
**And** loads within 2 seconds (NFR-F3)

**Given** the user zooms in beyond the viewer area
**When** the image is larger than the container
**Then** scroll/pan is available

**Given** a corrupted or unrecognized image
**When** rendering fails
**Then** broken image placeholder with Download fallback (NFR-F13)

## Epic 6: Agent File Integration

Agents receive file context (directory path + manifest) when assigned a step, read attachments, write output files, and the dashboard reflects agent-produced files. Lead Agent uses file metadata for intelligent routing.

### Story 6.1: Inject File Context into Agent Task Context

As a **developer**,
I want agents to receive the task directory path and file manifest when assigned a step,
So that agents know what files are available and where to read/write them.

**Acceptance Criteria:**

**Given** a step is assigned to an agent and the parent task has files
**When** the agent receives the task context via the bridge
**Then** the context includes `filesDir`: absolute path to `~/.nanobot/tasks/{task-id}/` (FR-F17)
**And** the context includes `fileManifest`: array of `{ name, type, size, subfolder }` for all files (FR-F18)
**And** the manifest is fetched fresh from Convex — no stale data (NFR-F8)

**Given** the agent uses its read tool on a file in `{filesDir}/attachments/`
**When** the read completes
**Then** the agent receives the file content (FR-F19)

**Given** the agent uses its write tool to create a file in `{filesDir}/output/`
**When** the write completes
**Then** the file is persisted in the output directory (FR-F20)

**Given** a task has no files
**When** the agent receives context
**Then** `filesDir` is still provided (directory exists) and `fileManifest` is empty

**Given** an instruction is included in the agent context
**When** the agent starts working
**Then** it sees: "Task has attached files at {filesDir}. Review the file manifest before starting work."

### Story 6.2: Bridge Manifest Sync for Agent Output

As a **developer**,
I want the file manifest in Convex to update automatically when agents produce output files,
So that the dashboard reflects agent-produced artifacts without manual intervention.

**Acceptance Criteria:**

**Given** an agent writes a file to `{filesDir}/output/`
**When** the agent notifies the bridge (or the bridge scans the output directory)
**Then** the bridge constructs metadata: `{ name, type, size, subfolder: "output", uploadedAt }` (FR-F21)
**And** the Convex task's `files` array is updated with the new entries (FR-F24)
**And** the update is reflected within 5 seconds (NFR-F7)
**And** an activity event is created: "{agentName} produced output: {fileNames}"

**Given** files exist on filesystem but not in the Convex manifest
**When** reconciliation runs
**Then** missing files are added to the manifest (NFR-F11)

**Given** the Convex manifest lists files that no longer exist on filesystem
**When** reconciliation detects the discrepancy
**Then** orphaned entries are removed and a warning is logged (NFR-F11)

**Given** the manifest updates in Convex
**When** the dashboard's reactive query fires
**Then** new output files appear in the Files tab and TaskCard file count updates

### Story 6.3: Lead Agent File-Aware Routing

As a **user**,
I want the Lead Agent to consider attached file metadata when routing steps to agents,
So that file-heavy tasks are routed to agents best equipped to handle them.

**Acceptance Criteria:**

**Given** a task is created with file attachments
**When** the Lead Agent generates the execution plan
**Then** it receives the file manifest as part of the task context: file names, types, sizes (FR-F28)

**Given** the Lead Agent assigns an agent to a step
**When** the delegation context is constructed
**Then** file metadata is included: number of files, types, total size, and names (FR-F29)
**And** example: "Task includes 2 attached files: invoice.pdf (847KB), notes.md (12KB). Available at the task's attachments directory."

**Given** a task has no file attachments
**When** the Lead Agent routes the task
**Then** routing proceeds normally without file metadata — no empty file context noise

**Given** file metadata is provided to the Lead Agent
**When** it informs agent assignment
**Then** file awareness enriches the routing context but does not override the capability-matching algorithm
