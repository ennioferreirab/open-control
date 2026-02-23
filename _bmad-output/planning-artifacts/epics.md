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

This document provides the complete epic and story breakdown for nanobot-ennio, decomposing the requirements from the PRD, UX Design, and Architecture into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: User can create a new task from the dashboard with a title and optional description
FR2: User can assign a task to a specific agent at creation time, or leave it unassigned for Lead Agent routing
FR3: User can configure per-task trust level at creation time (autonomous / agent-reviewed / human-approved)
FR4: User can configure specific reviewer agents for a task at creation time
FR5: User can view all tasks on a real-time Kanban board organized by state (Inbox -> Assigned -> In Progress -> Review -> Done)
FR6: User can view task details including description, assigned agent, status, and threaded inter-agent messages
FR7: User can view the Lead Agent's execution plan for any routed task via click-to-expand
FR8: User can create a task from the CLI (`nanobot mc tasks create`)
FR9: User can list all tasks and their states from the CLI (`nanobot mc tasks list`)
FR10: User can register a new agent by dropping a YAML definition file into the agents folder
FR11: User can define agent name, role, skills, system prompt, and LLM model in the YAML configuration
FR12: User can set a system-wide default LLM model that applies to all agents unless overridden per-agent
FR13: System validates agent YAML configurations on load and surfaces clear, actionable error messages for invalid configs
FR14: System refuses to start an agent with invalid configuration — no silent degradation
FR15: User can view all registered agents and their current status (active, idle, crashed) on the dashboard sidebar
FR16: User can list registered agents and their status from the CLI (`nanobot mc agents list`)
FR17: User can create a new agent configuration from the CLI (`nanobot mc agents create`)
FR18: User can create agent configurations via natural language through the nanobot agent itself (agent-assisted CLI)
FR19: Lead Agent can receive unassigned tasks and route them to the most appropriate agent based on capability matching against agent skill tags
FR20: Lead Agent can execute a task directly when no specialist agent matches the required capabilities
FR21: Lead Agent can create an execution plan for complex or batch tasks, identifying blocking dependencies, parallelizable tasks, and review chains
FR22: Lead Agent can dispatch parallelizable tasks simultaneously to different agents
FR23: Lead Agent can auto-unblock dependent tasks when their prerequisites complete
FR24: System transitions tasks through the state machine: Inbox -> Assigned -> In Progress -> Review -> Done
FR25: System sets task status to "Done" only when the assigned agent explicitly confirms completion
FR26: Agents can send messages to other agents within the context of a task (threaded on the task)
FR27: When a task is configured with reviewers, the system routes the completed work to the specified reviewer agents only — no broadcast
FR28: Reviewing agent can provide feedback on a task, visible as a threaded discussion on the dashboard
FR29: Assigned agent can address reviewer feedback while the task remains in Review state
FR30: Reviewing agent can approve a task, advancing it to the next stage (human approval if configured, or Done)
FR31: User can approve or deny a task that requires human approval via dashboard buttons
FR32: When user approves a task, the agent resumes or the task moves to Done
FR33: When user denies a task, the agent receives the denial and the task remains actionable
FR34: Dashboard displays a notification indicator when tasks require human attention (approval requests)
FR35: User can view a real-time activity feed showing agent actions as they happen
FR36: User can trigger a manual "Retry from Beginning" for crashed tasks from the dashboard
FR37: System automatically retries a task once when an agent crashes mid-execution (status: Retrying)
FR38: If retry also fails, system sets task status to Crashed with a red flag indicator and full error log
FR39: System flags tasks as stalled when they exceed the configured task timeout
FR40: System escalates inter-agent review requests that exceed the configured inter-agent timeout
FR41: User can configure global default timeouts (task timeout, inter-agent timeout) from the dashboard settings panel
FR42: User can override global timeout defaults per-task at creation time
FR43: User can configure the system-wide default LLM model from settings
FR44: User can view system health overview from the CLI (`nanobot mc status`)
FR45: User can start the entire Mission Control system (dashboard + agent gateway) with a single command (`nanobot mc start`)
FR46: User can stop Mission Control gracefully (`nanobot mc stop`)
FR47: System provides auto-generated API documentation from Convex schema
FR48: System provides built-in help for all CLI commands (`--help`)

### NonFunctional Requirements

NFR1: Dashboard Kanban board updates reflect agent state changes within 2 seconds of occurrence
NFR2: Agent task pickup latency < 5 seconds from assignment to "In Progress" status
NFR3: Activity feed streams agent actions with < 3 seconds delay from execution
NFR4: Dashboard initial load completes within 5 seconds on localhost
NFR5: CLI commands (`mc status`, `mc agents list`, `mc tasks list`) return results within 2 seconds
NFR6: `nanobot mc start` launches the full system (dashboard + agent gateway) within 15 seconds
NFR7: System runs unattended for 24+ hours with 3 agents actively processing tasks without crashes, stuck agents, or orphaned tasks
NFR8: Every task state transition is explicitly visible on the Kanban board — no silent failures
NFR9: 100% of inter-agent messages sent are received and visible in the task thread within 10 seconds — no message loss
NFR10: Agent crash recovery (auto-retry) completes within 30 seconds of crash detection
NFR11: System handles simultaneous operation of 3 agents and 4+ concurrent tasks without degradation
NFR12: Concurrent agent updates to the same task never result in lost writes (Convex transactional integrity)
NFR13: Dashboard detects Convex connection loss and displays a disconnection indicator — never shows stale data as current
NFR14: Graceful shutdown (`nanobot mc stop`) completes within 30 seconds, preserving all task state in Convex
NFR15: AsyncIO-Convex bridge retries failed writes up to 3 times with exponential backoff; surfaces error on activity feed only after retry exhaustion
NFR16: No component other than the nanobot backend writes to Convex; dashboard is read-only plus user actions via Convex mutations
NFR17: Agent YAML configuration changes are detected on next CLI command (`mc agents list`) or dashboard refresh — no file watcher required for MVP
NFR18: CLI and dashboard operate on the same Convex state — actions in one are immediately reflected in the other
NFR19: Dashboard requires authentication via configurable access token for localhost deployment
NFR20: Data privacy notice documented in README regarding sensitive data (financial, email, calendar) transiting through Convex cloud
NFR21: No single orchestration module exceeds 500 lines — maintaining nanobot's readability philosophy
NFR22: YAML validation errors include field name, expected type/value, and actionable fix suggestion
NFR23: All agent and task state transitions are logged to both the activity feed (Convex) and local stdout for debugging

### Additional Requirements

**From Architecture:**
- Starter template: `get-convex/template-nextjs-shadcn` — initialize dashboard with `npm create convex@latest -t nextjs-shadcn` (must be first implementation story)
- Convex data model with 5 core tables: tasks, messages, agents, activities, settings
- AsyncIO-Convex bridge via Python SDK — single integration point (`bridge.py`), retry 3x with exponential backoff
- Convex as single communication hub — no REST API, no WebSocket server, no message broker
- One-directional data flow: nanobot writes -> Convex stores -> dashboard reads
- Process orchestration: `nanobot mc start` spawns Agent Gateway + Next.js dev server + Convex dev server
- Simple access token auth (`MC_ACCESS_TOKEN` env var) with cookie-based session
- Monorepo structure: `dashboard/` directory within nanobot project
- Python orchestration modules in `nanobot/mc/` package (gateway, bridge, orchestrator, state_machine, yaml_validator, process_manager, types)
- Dashboard structure: `app/`, `components/`, `convex/`, `lib/` directories
- Cross-boundary naming: snake_case (Python) <-> camelCase (Convex/TypeScript) conversion at bridge layer
- Every Convex mutation that modifies task state MUST also write a corresponding activity event
- Co-located tests: dashboard tests next to components, Python tests next to modules
- Testing: Vitest for dashboard, pytest for Python
- Task status values: "inbox" | "assigned" | "in_progress" | "review" | "done" | "retrying" | "crashed"
- Trust level values: "autonomous" | "agent_reviewed" | "human_approved"
- Agent status values: "active" | "idle" | "crashed"
- ISO 8601 timestamps everywhere
- 500-line module limit enforced across all orchestration files

**From UX Design:**
- ShadCN UI design system with Radix UI primitives + Tailwind CSS
- CSS Grid dashboard layout: Agent Sidebar (240px, collapsible to 64px) + Kanban Board (flex-1) + Activity Feed (280px, collapsible)
- Clean workspace aesthetic: white backgrounds, slate surfaces, clear status color palette (blue=active, green=done, amber=review, red=error, violet=inbox)
- Always-visible task creation input with progressive disclosure for trust config (chevron to expand)
- Framer Motion for card transitions between Kanban columns (layoutId), 300ms transitions
- Optimistic UI updates for all user actions — cards move before server confirms
- Card design (Card-Rich direction): 3px left-border accent in status color + title (`font-semibold`) + description preview (2-line clamp) + tags (small pills) + agent avatar + status badge + progress bar on In Progress cards. Cards use `p-3.5` (14px) padding and `rounded-[10px]` (10px) border radius
- TaskDetailSheet: ShadCN Sheet (480px right slide-out) with tabs for Thread / Execution Plan / Config
- Inline HITL rejection: Deny click expands textarea inline, with "Return to Lead Agent" secondary action
- Activity feed: human-readable narrative entries with agent avatar + timestamp + description, auto-scroll with pause on manual scroll
- Agent sidebar: avatar with 2-letter initials + name + role + status dot (blue=active, gray=idle, red=crashed with glow)
- WCAG 2.1 AA accessibility target — inherited from ShadCN/Radix
- Desktop-only MVP (minimum 1024px viewport)
- `prefers-reduced-motion` media query respect for all animations
- Empty states with helpful placeholder text (not sad states)
- Anti-disruption rules: never move hovered/clicked cards, never auto-scroll when user is reading above fold

### FR Coverage Map

| FR | Epic | Description |
|----|------|-------------|
| FR1 | Epic 2 | Create task from dashboard |
| FR2 | Epic 4 | Assign task to agent or leave for Lead Agent routing |
| FR3 | Epic 5 | Configure per-task trust level |
| FR4 | Epic 5 | Configure specific reviewer agents |
| FR5 | Epic 2 | View tasks on real-time Kanban board |
| FR6 | Epic 2 | View task details with threaded messages |
| FR7 | Epic 4 | View Lead Agent execution plan (click-to-expand) |
| FR8 | Epic 2 | Create task from CLI |
| FR9 | Epic 2 | List tasks from CLI |
| FR10 | Epic 3 | Register agent via YAML file |
| FR11 | Epic 3 | Define agent config in YAML |
| FR12 | Epic 3 | System-wide default LLM model (via config) |
| FR13 | Epic 3 | Validate agent YAML with actionable errors |
| FR14 | Epic 3 | Refuse invalid agent config |
| FR15 | Epic 3 | View agents on dashboard sidebar |
| FR16 | Epic 3 | List agents from CLI |
| FR17 | Epic 3 | Create agent from CLI |
| FR18 | Epic 3 | Agent-assisted CLI (natural language) |
| FR19 | Epic 4 | Lead Agent capability matching |
| FR20 | Epic 4 | Lead Agent fallback self-execution |
| FR21 | Epic 4 | Lead Agent execution planning |
| FR22 | Epic 4 | Parallel task dispatch |
| FR23 | Epic 4 | Auto-unblock dependent tasks |
| FR24 | Epic 2 | Task state machine transitions |
| FR25 | Epic 4 | Done only on explicit agent confirmation |
| FR26 | Epic 5 | Inter-agent messaging (task-scoped) |
| FR27 | Epic 5 | Targeted review routing |
| FR28 | Epic 5 | Reviewer feedback visible on dashboard |
| FR29 | Epic 5 | Revision within Review state |
| FR30 | Epic 5 | Reviewer approves task |
| FR31 | Epic 6 | User approve/deny from dashboard |
| FR32 | Epic 6 | Approved task resumes or moves to Done |
| FR33 | Epic 6 | Denied task remains actionable |
| FR34 | Epic 6 | Notification indicator for HITL requests |
| FR35 | Epic 2 | Real-time activity feed |
| FR36 | Epic 6 | Manual retry for crashed tasks |
| FR37 | Epic 7 | Auto-retry on agent crash |
| FR38 | Epic 7 | Crashed status with error log |
| FR39 | Epic 7 | Stalled task detection (timeout) |
| FR40 | Epic 7 | Inter-agent timeout escalation |
| FR41 | Epic 7 | Global timeout config from dashboard |
| FR42 | Epic 7 | Per-task timeout override |
| FR43 | Epic 7 | System-wide default LLM from dashboard settings |
| FR44 | Epic 7 | CLI system health overview |
| FR45 | Epic 1 | Single command start |
| FR46 | Epic 1 | Graceful stop |
| FR47 | Epic 7 | Auto-generated API docs |
| FR48 | Epic 1 | Built-in CLI help |

### NFR Distribution Map

NFRs are woven into epics as acceptance criteria on relevant stories. NFRs requiring dedicated implementation are noted.

| NFR | Primary Epic | Integration |
|-----|-------------|-------------|
| NFR1 | Epic 2 | AC on Kanban board stories — updates < 2s |
| NFR2 | Epic 4 | AC on agent routing stories — pickup < 5s |
| NFR3 | Epic 2 | AC on ActivityFeed story — delay < 3s |
| NFR4 | Epic 2 | AC on dashboard layout story — load < 5s |
| NFR5 | Epic 2 | AC on CLI task stories — results < 2s |
| NFR6 | Epic 1 | AC on system start story — startup < 15s |
| NFR7 | Epic 7 | AC on reliability stories — 24h unattended |
| NFR8 | Epic 2 | AC on Kanban stories — no silent failures |
| NFR9 | Epic 5 | AC on messaging stories — zero message loss |
| NFR10 | Epic 7 | AC on crash recovery story — recovery < 30s |
| NFR11 | Epic 4 | AC on orchestration stories — 3 agents + 4 tasks |
| NFR12 | Epic 2 | Inherent — Convex transactional integrity |
| NFR13 | Epic 2 | AC on dashboard layout — connection loss indicator |
| NFR14 | Epic 1 | AC on graceful shutdown — completes < 30s |
| NFR15 | Epic 1 | AC on bridge stories — 3x retry + exponential backoff |
| NFR16 | Epic 1 | Architectural constraint — enforced by bridge design |
| NFR17 | Epic 3 | AC on agent registration — detection on CLI/refresh |
| NFR18 | Epic 2 | Inherent — both CLI and dashboard use Convex state |
| NFR19 | Epic 7 | **Dedicated story** — access token auth middleware + login page |
| NFR20 | Epic 7 | **Dedicated story** — README data privacy notice |
| NFR21 | All | Architectural constraint — enforced during code review |
| NFR22 | Epic 3 | AC on YAML validator story — field + type + fix suggestion |
| NFR23 | Epic 1 | AC on bridge story — dual logging (Convex + stdout) |

## Epic List

### Epic 1: Project Foundation & System Lifecycle
User can start and stop the entire Mission Control system with a single command (`nanobot mc start` / `nanobot mc stop`) and see the dashboard at localhost:3000 with built-in CLI help.
**FRs covered:** FR45, FR46, FR48
**NFRs as AC:** NFR6 (startup < 15s), NFR14 (shutdown < 30s), NFR15 (bridge retry logic), NFR16 (one-directional writes), NFR23 (dual logging)
**Implementation scope:** Starter template initialization (`npm create convex@latest -t nextjs-shadcn`), complete Convex schema definition (all 5 tables), AsyncIO-Convex bridge skeleton with retry logic, process manager (3 subprocesses), `nanobot/mc/` Python package structure, CLI `--help` for all subcommands.

### Epic 2: Task Board & Real-Time Visibility
User can create tasks (from dashboard and CLI), see them on a real-time Kanban board organized by state, view task details with threaded messages, and monitor agent activity through a live streaming feed.
**FRs covered:** FR1, FR5, FR6, FR8, FR9, FR24, FR35
**NFRs as AC:** NFR1 (board updates < 2s), NFR3 (feed delay < 3s), NFR4 (load < 5s), NFR5 (CLI < 2s), NFR8 (no silent failures), NFR12 (transactional integrity), NFR13 (connection loss indicator), NFR18 (CLI-dashboard state parity)
**Implementation scope:** CSS Grid dashboard layout (sidebar + Kanban + feed), KanbanBoard + KanbanColumn + TaskCard components, TaskInput (collapsed mode), TaskDetailSheet (Thread tab), ActivityFeed + FeedItem, task state machine (Convex mutations with activity events), Framer Motion card transitions, optimistic UI, CLI `mc tasks create/list`.

### Epic 3: Agent Registration & Dashboard Presence
User can register agents via YAML files, see all agents and their status on the dashboard sidebar, manage agents via CLI, and create agent configurations through natural language (agent-assisted CLI). System validates configs with clear, actionable errors and refuses to start invalid agents.
**FRs covered:** FR10, FR11, FR12, FR13, FR14, FR15, FR16, FR17, FR18
**NFRs as AC:** NFR17 (YAML change detection on CLI/refresh), NFR22 (validation errors with field + type + fix)
**Implementation scope:** YAML validator (pydantic), agent registry sync to Convex `agents` table, AgentSidebar + AgentSidebarItem components (status dots, collapsed variant), CLI `mc agents list/create`, agent-assisted CLI (natural language -> YAML generation), system-wide default LLM model via config.
**Note:** FR12 sets the default LLM via config/YAML. FR43 (Epic 7) later adds a dashboard settings UI to change it — intentional layering of config-first, then UI convenience.

### Epic 4: Intelligent Task Routing & Orchestration
User creates a task without specifying an agent, and the Lead Agent intelligently routes it to the best specialist based on capability matching — with visible execution plans for complex tasks showing blocking dependencies and parallel dispatch.
**FRs covered:** FR2, FR7, FR19, FR20, FR21, FR22, FR23, FR25
**NFRs as AC:** NFR2 (agent pickup < 5s), NFR11 (3 agents + 4 tasks concurrent)
**Implementation scope:** `orchestrator.py` (Lead Agent routing logic, capability matching against skill tags), execution planning (blocking vs. parallelizable task identification), parallel dispatch, dependency auto-unblocking, fallback self-execution, execution plan visualization (collapsible flow on TaskDetailSheet), agent assignment UI on TaskInput.

### Epic 5: Inter-Agent Review & Collaboration
User configures reviewer agents and trust level on a task at creation time, and agents review each other's work with targeted feedback visible as threaded discussions on the dashboard. Revision cycles happen within Review state until the reviewer approves.
**FRs covered:** FR3, FR4, FR26, FR27, FR28, FR29, FR30
**NFRs as AC:** NFR9 (zero message loss, delivery < 10s)
**Implementation scope:** Task-scoped inter-agent messaging (Convex `messages` table mutations), targeted review routing (not broadcast), ThreadMessage component variants (agent/review/system), reviewer feedback and revision cycles, reviewer approval advancing task state, progressive disclosure on TaskInput (trust level selector, reviewer selector, human approval checkbox).

### Epic 6: Human-in-the-Loop Approval
User can approve or deny tasks requiring human oversight via one-click dashboard actions, with inline rejection feedback, notification badges for pending approvals, and the option to return denied tasks to the Lead Agent with full context.
**FRs covered:** FR31, FR32, FR33, FR34, FR36
**Implementation scope:** Approve/Deny buttons on TaskCard (Review state), InlineRejection component (expandable textarea + "Return to Lead Agent" secondary action), HITL notification badges on Review column header, manual "Retry from Beginning" for crashed tasks, user messages saved to task thread.
**Note:** Independent of Epic 5 — works for any task with `human_approved` trust level, regardless of whether inter-agent review is configured.

### Epic 7: Reliability, Configuration & Security
System handles crashes gracefully with auto-retry, respects configurable timeouts for stalled tasks and inter-agent review, provides a dashboard settings panel for global configuration, secures the dashboard with access token auth, and offers system health visibility via CLI.
**FRs covered:** FR37, FR38, FR39, FR40, FR41, FR42, FR43, FR44, FR47
**NFRs as AC:** NFR7 (24h unattended), NFR10 (crash recovery < 30s)
**NFR dedicated stories:** NFR19 (access token auth — middleware + login page), NFR20 (README privacy notice)
**Implementation scope — 4 sub-domains:**
1. **Crash recovery** (FR37, FR38): Auto-retry 1x -> Crashed with red flag + error log + manual retry button
2. **Timeout management** (FR39, FR40): Stalled task detection, inter-agent review escalation
3. **Settings & configuration** (FR41, FR42, FR43): Dashboard settings panel (global timeouts, default LLM model, per-task overrides)
4. **System operations** (FR44, FR47, NFR19, NFR20): CLI `mc status`, auto-generated API docs, access token auth, data privacy README notice

## Epic 2: Task Board & Real-Time Visibility

User can create tasks (from dashboard and CLI), see them on a real-time Kanban board organized by state, view task details with threaded messages, and monitor agent activity through a live streaming feed.

### Story 2.1: Build Dashboard Layout Shell

As a **user**,
I want to see a structured dashboard layout when I open Mission Control,
So that I have a clear visual workspace with dedicated areas for agents, tasks, and activity.

**Acceptance Criteria:**

**Given** the dashboard project is initialized (Epic 1)
**When** the user navigates to localhost:3000
**Then** the page renders a CSS Grid layout with 3 regions: Agent Sidebar (240px left), Kanban Board area (flex-1 center), Activity Feed (280px right)
**And** the Agent Sidebar uses ShadCN `sidebar-07` pattern and is collapsible to 64px icon-only mode
**And** the Kanban Board area contains a header with "Mission Control" title (`text-2xl`, `font-bold`)
**And** the Activity Feed panel is collapsible to hidden
**And** the layout uses the design system color palette: white background, slate-50 surfaces, slate-200 borders
**And** the `DashboardLayout.tsx` component orchestrates the grid layout
**And** the `app/layout.tsx` wraps the app in `ConvexProvider`
**And** the `app/providers.tsx` creates the `ConvexClientProvider` component
**And** the dashboard initial load completes within 5 seconds on localhost (NFR4)
**And** at viewport width < 1024px, a subtle banner displays: "Mission Control is designed for desktop browsers (1024px+)"
**And** at viewport 1024-1279px, sidebar is collapsed by default
**And** at viewport 1280px+, full layout with all panels visible

### Story 2.2: Implement Task Creation from Dashboard

As a **user**,
I want to type a task description and hit Enter to create a new task instantly,
So that I can delegate work to agents with zero friction.

**Acceptance Criteria:**

**Given** the dashboard layout is rendered (Story 2.1)
**When** the user types a task description in the always-visible TaskInput field at the top of the Kanban area and presses Enter
**Then** a new task is created in Convex via `tasks.create` mutation with status "inbox", trust level "autonomous" (default), optional tags (comma-separated or free-form input, stored as array of strings), and an ISO 8601 timestamp
**And** the task card appears in the Inbox column within 200ms via optimistic UI (violet accent fade-in)
**And** the TaskInput field clears after submission
**And** a `task_created` activity event is written to the `activities` table in the same mutation

**Given** the user submits an empty task description
**When** validation runs
**Then** the input border turns red with small text below: "Task description required"
**And** no mutation is called

**And** the `TaskInput.tsx` component is created with ShadCN `Input` + `Button`
**And** the Convex `tasks.ts` file contains the `create` mutation with activity event logging
**And** a Vitest test exists for `TaskInput.tsx` covering submission and empty validation

### Story 2.3: Build Kanban Board with Real-Time Task Cards

As a **user**,
I want to see all my tasks organized on a Kanban board that updates in real-time,
So that I can monitor task progress at a glance without refreshing the page.

**Acceptance Criteria:**

**Given** tasks exist in the Convex `tasks` table
**When** the dashboard loads
**Then** the KanbanBoard renders 5 columns via CSS Grid (`grid-template-columns: repeat(5, 1fr)`): Inbox, Assigned, In Progress, Review, Done
**And** each column has a header with the column name (`text-lg`, `font-semibold`) and a task count badge
**And** tasks appear as TaskCard components in the correct column based on their status
**And** each TaskCard displays (Card-Rich direction): 3px left-border accent in status color, title (`text-sm`, `font-semibold`), description preview (`text-xs`, 2-line clamp via `line-clamp-2`, optional), tags row (small pills, `text-xs`, `rounded-full`), assigned agent name and avatar dot (`text-xs`), status Badge, progress bar on In Progress cards
**And** cards use `p-3.5` (14px padding) and `rounded-[10px]` (10px border radius)
**And** cards within each column are rendered inside a ShadCN `ScrollArea` for vertical overflow

**Given** a task status changes in Convex (by any source — agent, CLI, or another browser tab)
**When** the reactive query updates
**Then** the card animates from its current column to the new column using Framer Motion `layoutId` (300ms transition)
**And** the board update reflects within 2 seconds of the state change (NFR1)
**And** every task state transition is visible on the board — no silent failures (NFR8)

**Given** no tasks exist
**When** the board renders
**Then** centered text appears: "No tasks yet. Type above to create your first task."
**And** empty columns show subtle muted text: "No tasks"

**Given** the user has `prefers-reduced-motion` enabled
**When** a card moves between columns
**Then** the card transitions instantly without animation

**And** `KanbanBoard.tsx`, `KanbanColumn.tsx`, and `TaskCard.tsx` components are created
**And** Convex `tasks.ts` contains a `list` query returning all tasks
**And** Vitest tests exist for `KanbanBoard.tsx` and `TaskCard.tsx`

### Story 2.4: Implement Task State Machine

As a **developer**,
I want a reliable task state machine that enforces valid transitions and logs every change,
So that tasks always follow the correct lifecycle and no state change goes unrecorded.

**Acceptance Criteria:**

**Given** a task exists in the Convex `tasks` table
**When** a state transition is requested via the `tasks.updateStatus` mutation
**Then** the mutation validates the transition is legal: inbox -> assigned, assigned -> in_progress, in_progress -> review, in_progress -> done, review -> done, any -> retrying, any -> crashed
**And** illegal transitions are rejected with a `ConvexError` describing the invalid transition (e.g., "Cannot transition from 'done' to 'inbox'")
**And** the task's `updatedAt` field is set to the current ISO 8601 timestamp
**And** a corresponding activity event is written to the `activities` table in the same mutation (e.g., `task_started`, `task_completed`)

**Given** a task transitions to "assigned"
**When** the mutation is called with an `agentName` argument
**Then** the task's `assignedAgent` field is updated to the provided agent name
**And** a `task_assigned` activity event is created with the agent name

**Given** a task transitions to "done"
**When** the mutation is called
**Then** the status is set ONLY if explicitly called (FR25 — no auto-completion)
**And** a `task_completed` activity event is created

**And** the `tasks.ts` Convex file contains `updateStatus` mutation with transition validation
**And** the `nanobot/mc/state_machine.py` Python module mirrors the valid transitions for bridge-side validation
**And** unit tests exist for both TypeScript (Convex) and Python state machine validation

### Story 2.5: Build Activity Feed

As a **user**,
I want to see a real-time activity feed showing what agents are doing as it happens,
So that I can monitor the system without clicking into individual tasks.

**Acceptance Criteria:**

**Given** activity events exist in the Convex `activities` table
**When** the dashboard loads
**Then** the ActivityFeed panel renders on the right side (280px) with a "Activity Feed" header
**And** FeedItem components display chronologically (newest at bottom) with: timestamp (`text-xs`, monospace), agent name (`font-medium`), description (`text-xs`)
**And** the feed uses ShadCN `ScrollArea` for vertical scrolling

**Given** a new activity event is written to Convex
**When** the reactive query updates
**Then** the new FeedItem fades in at the bottom (200ms fade-in)
**And** the feed auto-scrolls to the latest entry if the user is already at the bottom
**And** if the user has scrolled up, auto-scroll pauses and a "New activity" indicator appears
**And** the feed update appears within 3 seconds of the event (NFR3)

**Given** error-type activity events exist (e.g., `task_crashed`, `system_error`)
**When** they render in the feed
**Then** the FeedItem has a red-tinted left border

**Given** HITL-related events exist (e.g., `hitl_requested`, `hitl_approved`)
**When** they render in the feed
**Then** the FeedItem has an amber-tinted left border

**Given** no activity events exist
**When** the feed renders
**Then** muted italic text displays: "Waiting for activity..."

**Given** the Convex connection is lost
**When** the feed detects disconnection
**Then** a subtle banner displays at the top of the feed: "Reconnecting..." (NFR13)
**And** when reconnected, the banner disappears and the feed catches up with missed events

**And** `ActivityFeed.tsx` and `FeedItem.tsx` components are created
**And** Convex `activities.ts` contains a `list` query (ordered by timestamp, latest last)
**And** Vitest test exists for `ActivityFeed.tsx`

### Story 2.6: Build Task Detail Sheet

As a **user**,
I want to click on a task card and see its full details in a slide-out panel,
So that I can read the complete task story — description, status, agent, and threaded messages — without leaving the board.

**Acceptance Criteria:**

**Given** the Kanban board is displayed with task cards
**When** the user clicks a TaskCard
**Then** a ShadCN Sheet slides out from the right (480px wide) displaying the task detail view
**And** the Sheet header shows: task title (`text-lg`, `font-semibold`), status Badge, assigned agent name with avatar

**Given** the TaskDetailSheet is open
**When** the user views the Thread tab (default active tab)
**Then** threaded messages from the `messages` table are displayed chronologically (newest at bottom)
**And** each ThreadMessage shows: author avatar (24px), author name, timestamp, message content
**And** message variants are visually distinct: agent messages (white bg), user messages (blue-50 bg), system events (gray-50 bg, italic)

**Given** the TaskDetailSheet is open
**When** the underlying task is updated in Convex (status change, new message)
**Then** the sheet content refreshes in place without closing
**And** a subtle "Updated" indicator appears briefly

**Given** the TaskDetailSheet is open
**When** the user presses Escape or clicks outside the sheet
**Then** the sheet closes and focus returns to the triggering TaskCard

**Given** a task has no messages
**When** the Thread tab is viewed
**Then** muted text displays: "No messages yet. Agent activity will appear here."

**And** `TaskDetailSheet.tsx` and `ThreadMessage.tsx` components are created
**And** Convex `messages.ts` contains a `listByTask` query (filtered by taskId, ordered by timestamp)
**And** the Sheet provides `role="dialog"` and proper focus trap (inherited from ShadCN/Radix)
**And** Vitest test exists for `TaskDetailSheet.tsx`

### Story 2.7: Implement CLI Task Commands

As a **user**,
I want to create and list tasks from the terminal,
So that I can manage tasks without opening the dashboard.

**Acceptance Criteria:**

**Given** Mission Control is running
**When** the user runs `nanobot mc tasks create "Research AI trends"`
**Then** a new task is created in Convex with title "Research AI trends", status "inbox", trust level "autonomous"
**And** a `task_created` activity event is written
**And** the CLI prints confirmation: task title, status, and created timestamp
**And** the new task appears on the dashboard Kanban board in real-time (NFR18)

**Given** Mission Control is running
**When** the user runs `nanobot mc tasks create` without a title argument
**Then** the CLI prompts for a task title interactively

**Given** tasks exist in Convex
**When** the user runs `nanobot mc tasks list`
**Then** all tasks are displayed in a formatted table: ID, title (truncated), status, assigned agent, created date
**And** tasks are grouped or sorted by status
**And** results return within 2 seconds (NFR5)

**Given** no tasks exist
**When** the user runs `nanobot mc tasks list`
**Then** the CLI prints: "No tasks found."

**And** CLI task commands are added to `nanobot/cli/mc.py`
**And** task commands call bridge methods — no direct Convex SDK usage in CLI
**And** `nanobot mc tasks --help` shows available subcommands with descriptions

## Epic 3: Agent Registration & Dashboard Presence

User can register agents via YAML files, see all agents and their status on the dashboard sidebar, manage agents via CLI, and create agent configurations through natural language. System validates configs with clear errors and refuses to start invalid agents.

### Story 3.1: Implement YAML Agent Validator

As a **developer**,
I want a YAML validation module that enforces agent configuration schema with clear, actionable error messages,
So that invalid agent configs are caught early with guidance on how to fix them.

**Acceptance Criteria:**

**Given** a YAML agent configuration file exists in the agents folder
**When** the validator loads and parses the file
**Then** it validates required fields: name (string), role (string), prompt (string)
**And** it validates optional fields: skills (array of strings), model (string), displayName (string)
**And** for each validation error, the message includes: field name, expected type/value, and actionable fix suggestion (NFR22)
**And** all errors in a file are collected and returned together (not fail-on-first)

**Given** an agent YAML file has an invalid configuration
**When** the system attempts to load it
**Then** the system refuses to start that agent (FR14)
**And** the error is logged to stdout with full context
**And** other valid agents are not affected

**Given** a valid agent YAML file is loaded
**When** validation succeeds
**Then** the agent data is returned as a typed Python dataclass matching the Convex `agents` table schema

**And** the module is created at `nanobot/mc/yaml_validator.py` using pydantic for schema validation
**And** the module does not exceed 500 lines (NFR21)
**And** unit tests exist in `nanobot/mc/yaml_validator.test.py` covering valid configs, missing fields, wrong types, and multi-error collection

### Story 3.2: Build Agent Registry Sync

As a **developer**,
I want agents defined in YAML files to be synced to the Convex agents table,
So that the dashboard and CLI can display current agent information.

**Acceptance Criteria:**

**Given** valid YAML agent configuration files exist in the agents folder
**When** the Agent Gateway starts or `nanobot mc agents list` is run
**Then** all YAML files are loaded, validated, and synced to the Convex `agents` table
**And** new agents are inserted, existing agents are updated, removed YAML files result in agent status set to "idle"
**And** each agent sync writes an `agent_connected` activity event

**Given** the system-wide default LLM model is configured (FR12)
**When** an agent YAML does not specify a `model` field
**Then** the agent uses the system-wide default model
**And** the resolved model is stored in the Convex `agents` table

**Given** YAML files change between CLI invocations
**When** the user runs `nanobot mc agents list`
**Then** the agent registry is refreshed from YAML files before displaying results (NFR17)

**And** the sync logic lives in `nanobot/mc/gateway.py`
**And** sync uses bridge methods exclusively — no direct Convex SDK calls outside bridge

### Story 3.3: Build Agent Sidebar

As a **user**,
I want to see all registered agents and their current status on the dashboard sidebar,
So that I know which agents are available and what they're doing.

**Acceptance Criteria:**

**Given** agents exist in the Convex `agents` table
**When** the dashboard loads
**Then** the Agent Sidebar displays each agent as an AgentSidebarItem with: avatar (32px, colored, 2-letter initials), name (`text-sm`, `font-medium`), role (`text-xs`, muted), status dot (8px circle)
**And** status dots use correct colors: blue with glow ring (active), gray (idle), red with glow ring (crashed)
**And** agent status updates in real-time via Convex reactive queries

**Given** the sidebar is in collapsed mode (64px)
**When** the user views the sidebar
**Then** only agent avatars (36px) are shown with status dot overlaid at bottom-right
**And** hovering an avatar shows a ShadCN Tooltip with: name, role, status

**Given** no agents are registered
**When** the sidebar renders
**Then** it displays: "No agents found. Add a YAML config to `~/.nanobot/agents/`"

**And** `AgentSidebar.tsx` and `AgentSidebarItem.tsx` components are created
**And** Convex `agents.ts` contains a `list` query returning all agents
**And** status dot color transitions use CSS transition (200ms)

### Story 3.4: Implement CLI Agent Commands

As a **user**,
I want to list and create agents from the terminal,
So that I can manage my agent roster without editing YAML files manually.

**Acceptance Criteria:**

**Given** Mission Control is running
**When** the user runs `nanobot mc agents list`
**Then** all registered agents are displayed in a formatted table: name, role, status, model, skills
**And** results return within 2 seconds (NFR5)
**And** the agent registry is refreshed from YAML files before display (NFR17)

**Given** Mission Control is running
**When** the user runs `nanobot mc agents create`
**Then** an interactive prompt guides the user through: agent name, role, skills (comma-separated), system prompt, and optional LLM model
**And** a valid YAML file is generated and saved to the agents folder
**And** the CLI prints confirmation with the file path

**Given** no agents are registered
**When** the user runs `nanobot mc agents list`
**Then** the CLI prints: "No agents found. Create one with `nanobot mc agents create`"

**And** CLI agent commands are added to `nanobot/cli/mc.py`
**And** `nanobot mc agents --help` shows available subcommands

### Story 3.5: Implement Agent-Assisted CLI

As a **user**,
I want to describe an agent in natural language and have nanobot generate the YAML configuration for me,
So that I can create agents without knowing the YAML schema.

**Acceptance Criteria:**

**Given** Mission Control is running
**When** the user runs `nanobot mc agents create --assisted` or describes an agent in natural language (e.g., "create a financial agent that tracks boletos")
**Then** the nanobot agent interprets the natural language description
**And** generates a complete, valid YAML configuration with inferred: name, role, skills, and system prompt
**And** presents the generated YAML to the user for confirmation before saving

**Given** the user confirms the generated YAML
**When** the file is saved
**Then** it is written to the agents folder with the agent name as filename
**And** validation runs on the generated file (same as Story 3.1)
**And** the CLI prints confirmation with the file path

**Given** the user rejects the generated YAML
**When** they provide feedback
**Then** the agent regenerates with adjustments based on the feedback

**And** agent-assisted creation uses the existing nanobot agent infrastructure (SubagentManager)
**And** the generated YAML passes all validation rules from Story 3.1

## Epic 4: Intelligent Task Routing & Orchestration

User creates a task without specifying an agent, and the Lead Agent intelligently routes it to the best specialist based on capability matching — with visible execution plans for complex tasks.

### Story 4.1: Implement Lead Agent Capability Matching

As a **user**,
I want unassigned tasks to be automatically routed to the most appropriate agent,
So that I can delegate by intent without knowing which agent handles what.

**Acceptance Criteria:**

**Given** a task is created with no assigned agent (status "inbox")
**When** the Lead Agent picks up the task
**Then** the Lead Agent analyzes the task description and matches it against registered agent skill tags
**And** the best-matching agent is selected based on skill tag overlap with task keywords
**And** the task transitions from "inbox" to "assigned" with the selected agent's name
**And** a `task_assigned` activity event is created: "Lead Agent assigned '{task title}' to {agent name}"

**Given** no registered agent has matching skills for the task
**When** the Lead Agent evaluates routing
**Then** the Lead Agent assigns the task to itself for direct execution (FR20)
**And** a `task_assigned` activity event is created: "No specialist found. Lead Agent executing directly."

**Given** a task is created with an explicitly assigned agent (FR2)
**When** the task enters the system
**Then** the Lead Agent does NOT re-route it — the explicit assignment is respected
**And** the task transitions directly from "inbox" to "assigned"

**And** the routing logic is implemented in `nanobot/mc/orchestrator.py`
**And** the module does not exceed 500 lines (NFR21)
**And** unit tests exist in `nanobot/mc/orchestrator.test.py`

### Story 4.2: Implement Execution Planning

As a **user**,
I want the Lead Agent to create visible execution plans for complex tasks,
So that I can see how work is being broken down and which steps depend on each other.

**Acceptance Criteria:**

**Given** the Lead Agent receives a complex or batch task
**When** the Lead Agent analyzes it
**Then** it creates an execution plan identifying: individual sub-steps, blocking dependencies (must complete before dependents start), parallelizable steps (can run simultaneously), and assigned agents per step
**And** the execution plan is stored as a structured JSON field on the task in Convex
**And** a `task_assigned` activity event includes a summary of the plan

**Given** an execution plan exists for a task
**When** a blocking step completes
**Then** dependent steps are automatically unblocked and dispatched (FR23)
**And** a `task_started` activity event is created for each newly unblocked step

**Given** an execution plan has parallelizable steps
**When** those steps are dispatched
**Then** they are sent to different agents simultaneously (FR22)
**And** the activity feed shows parallel dispatch

**And** execution plan data is stored on the task document in Convex
**And** the orchestrator updates the plan status as steps complete
**And** unit tests cover plan creation, dependency resolution, and parallel dispatch

### Story 4.3: Build Execution Plan Visualization

As a **user**,
I want to see the Lead Agent's execution plan on the task detail panel,
So that I understand how work is being organized and track step-by-step progress.

**Acceptance Criteria:**

**Given** a task has an execution plan
**When** the user clicks the task card to open TaskDetailSheet
**Then** an "Execution Plan" tab is available alongside the Thread tab
**And** the Execution Plan tab displays steps as a vertical list with: step number, description, assigned agent, status icon (pending dot, in-progress spinner, completed checkmark)
**And** step dependencies are shown as connecting lines between dependent steps

**Given** execution plan steps are completing
**When** a step status changes in Convex
**Then** the visualization updates in real-time (status icon changes, connecting lines update)
**And** completed steps show a green checkmark

**Given** a task has no execution plan (single-step or directly assigned)
**When** the user opens TaskDetailSheet
**Then** the Execution Plan tab is either hidden or shows: "Direct execution — no multi-step plan"

**And** the Execution Plan tab is added to `TaskDetailSheet.tsx`
**And** uses ShadCN `Collapsible` for click-to-expand on the TaskCard (FR7)

### Story 4.4: Add Agent Assignment to Task Input

As a **user**,
I want to optionally assign a specific agent when creating a task,
So that I can bypass Lead Agent routing when I know which agent should handle the work.

**Acceptance Criteria:**

**Given** the TaskInput component exists (Story 2.2)
**When** the user clicks the chevron to expand progressive disclosure options
**Then** an agent selector (`Select` component) appears showing all registered agents from the Convex `agents` table
**And** the selector defaults to "Auto (Lead Agent)" indicating automatic routing

**Given** the user selects a specific agent and submits the task
**When** the task is created
**Then** the task is created with `assignedAgent` set to the selected agent's name
**And** the task transitions from "inbox" to "assigned" without Lead Agent routing

**Given** the user leaves the selector on "Auto (Lead Agent)"
**When** the task is created
**Then** the task is created with no `assignedAgent` and enters the Lead Agent routing flow

**And** the agent selector is added to the progressive disclosure panel in `TaskInput.tsx`

## Epic 5: Inter-Agent Review & Collaboration

User configures reviewer agents and trust level on a task at creation time, and agents review each other's work with targeted feedback visible as threaded discussions. Revision cycles happen within Review state until the reviewer approves.

### Story 5.1: Implement Trust Level & Reviewer Configuration

As a **user**,
I want to configure how much oversight a task gets when I create it,
So that I can balance speed (autonomous) with quality (reviewed) and control (human-approved).

**Acceptance Criteria:**

**Given** the TaskInput progressive disclosure panel is open (Story 4.4)
**When** the user views the expanded options
**Then** a trust level selector shows three options: "Autonomous" (default), "Agent Reviewed", "Human Approved" (FR3)
**And** when "Agent Reviewed" or "Human Approved" is selected, a reviewer selector appears showing registered agents with multi-select capability (FR4)
**And** when "Human Approved" is selected, a checkbox "Require human approval" is checked and visible

**Given** the user creates a task with trust level "agent_reviewed" and reviewer "secretario"
**When** the task is submitted
**Then** the task is created in Convex with `trustLevel: "agent_reviewed"` and `reviewers: ["secretario"]`
**And** the TaskCard shows a review icon (circular arrows) indicating review is configured

**Given** the user creates a task with trust level "autonomous"
**When** the task completes
**Then** the task moves directly to "done" without entering review

**And** trust level and reviewer fields are stored on the task in Convex
**And** the progressive disclosure panel in `TaskInput.tsx` includes `Switch`, `Select`, and `Checkbox` components

### Story 5.2: Implement Inter-Agent Messaging

As a **developer**,
I want agents to send task-scoped messages to each other,
So that inter-agent collaboration has a persistent, visible communication channel.

**Acceptance Criteria:**

**Given** a task exists and an agent is working on it
**When** the agent sends a message via the bridge
**Then** a message is created in the Convex `messages` table with: taskId, authorName, authorType ("agent"), content, messageType ("work"), and ISO 8601 timestamp
**And** the message appears in the task's thread on the dashboard in real-time

**Given** a task is configured with reviewers
**When** the assigned agent completes work and the task transitions to "review"
**Then** the system routes a review request ONLY to the specified reviewer agents — not broadcast (FR27)
**And** a `review_requested` activity event is created
**And** only the configured reviewers receive the review notification

**Given** 100% message delivery is required (NFR9)
**When** a message is written via the bridge
**Then** the message is persisted in Convex and visible in the task thread within 10 seconds
**And** the bridge retry logic (Story 1.4) ensures delivery on transient failures

**And** Convex `messages.ts` contains `create` mutation and `listByTask` query
**And** the bridge exposes `send_message()` method in `bridge.py`
**And** unit tests cover message creation, task-scoped filtering, and delivery reliability

### Story 5.3: Build Review Feedback Flow

As a **user**,
I want to see agents reviewing each other's work as a threaded discussion,
So that I can follow the review process and trust the quality of agent output.

**Acceptance Criteria:**

**Given** a task is in "review" state and a reviewer agent receives it
**When** the reviewer provides feedback
**Then** a message is created with messageType "review_feedback" and appears in the task thread
**And** the ThreadMessage renders with amber-50 background (review feedback variant)
**And** a `review_feedback` activity event is created in the feed

**Given** the reviewer has provided feedback
**When** the assigned agent addresses the feedback
**Then** the agent's response appears as a new thread message (messageType "work")
**And** the task remains in "review" state (FR29) — no backward transition
**And** the revision cycle continues until the reviewer approves

**Given** the reviewer approves the task (FR30)
**When** the approval is submitted
**Then** a message is created with messageType "approval"
**And** if trust level is "agent_reviewed": the task transitions to "done"
**And** if trust level is "human_approved": the task stays in "review" with an HITL badge, and a `hitl_requested` activity event is created
**And** a `review_approved` activity event is created

**And** `ThreadMessage.tsx` variants are updated: review feedback (amber-50 bg) distinct from regular agent messages
**And** the review flow is orchestrated in `nanobot/mc/orchestrator.py`

## Epic 6: Human-in-the-Loop Approval

User can approve or deny tasks requiring human oversight via one-click dashboard actions, with inline rejection feedback, notification badges for pending approvals, and the option to return denied tasks to the Lead Agent.

### Story 6.1: Implement HITL Approve Action

As a **user**,
I want to approve a task with one click,
So that I can quickly sign off on completed work and keep agents moving.

**Acceptance Criteria:**

**Given** a task is in "review" state with trust level "human_approved" (or after agent review passes for "agent_reviewed" + human gate)
**When** the user views the TaskCard on the Kanban board
**Then** a green "Approve" button is visible directly on the card

**Given** the user clicks the Approve button
**When** the approval is processed
**Then** the task transitions to "done" via optimistic UI — card slides to Done column immediately (300ms transition, green flash on border)
**And** a `hitl_approved` activity event is created
**And** a message with messageType "approval" and authorType "user" is added to the task thread
**And** the agent receives the approval signal via bridge subscription (FR32)

**Given** the TaskDetailSheet is open for a reviewable task
**When** the user views the sheet header
**Then** the Approve button is also available in the sheet header

**And** no confirmation dialog is shown — single click completes the action
**And** if the Convex mutation fails, the card reverts with a subtle shake animation

### Story 6.2: Implement HITL Deny with Inline Rejection

As a **user**,
I want to deny a task with feedback explaining what needs to change,
So that agents receive actionable context for revision.

**Acceptance Criteria:**

**Given** a task is in "review" state requiring human approval
**When** the user clicks the red "Deny" button on the TaskCard or TaskDetailSheet
**Then** an inline textarea expands smoothly below the button (150ms expand animation via Framer Motion)
**And** the textarea receives focus automatically

**Given** the user types rejection feedback and clicks "Submit"
**When** the denial is processed
**Then** a message is created with messageType "denial", authorType "user", and the feedback text as content
**And** the task remains in "review" state and stays actionable (FR33)
**And** a `hitl_denied` activity event is created
**And** the textarea collapses (150ms) and the new message appears in the task thread
**And** the agent receives the denial with feedback via bridge subscription

**Given** the user denies a task
**When** the inline rejection form is visible
**Then** a secondary button "Return to Lead Agent" is available below the textarea
**And** clicking "Return to Lead Agent" sends the task back with full thread history + user comment, so the Lead Agent can re-plan or re-assign

**And** the `InlineRejection.tsx` component is created with ShadCN `Textarea` + `Button` + Framer Motion expand animation
**And** Vitest test exists for `InlineRejection.tsx`

### Story 6.3: Implement HITL Notification Badges

As a **user**,
I want to see notification badges when tasks need my attention,
So that I can spot approval requests at a glance without scanning every card.

**Acceptance Criteria:**

**Given** tasks exist in "review" state with trust level "human_approved" awaiting user action
**When** the dashboard renders
**Then** the Review column header shows an amber badge with the count of tasks needing human approval (FR34)
**And** the badge has an amber glow pulse animation once when the count increments

**Given** the user approves or denies a task
**When** the action is processed
**Then** the badge count decrements immediately (optimistic UI)
**And** if count reaches zero, the badge is hidden

**Given** a new task enters HITL review while the dashboard is open
**When** the reactive query updates
**Then** the badge count increments and pulses once

**And** badge logic is added to `KanbanColumn.tsx` header
**And** badge only counts tasks requiring human action, not tasks in agent-only review

### Story 6.4: Implement Manual Crash Retry

As a **user**,
I want to retry a crashed task from the dashboard,
So that I can recover from agent failures without recreating the task.

**Acceptance Criteria:**

**Given** a task has status "crashed" with a red badge and red left-border accent
**When** the user clicks the TaskCard to open TaskDetailSheet
**Then** the sheet header shows a "Retry from Beginning" button
**And** the thread tab shows the error details (monospace, system event variant)

**Given** the user clicks "Retry from Beginning" (FR36)
**When** the retry is initiated
**Then** the task status resets to "inbox" to be picked up again by the Lead Agent or assigned agent
**And** a `task_retrying` activity event is created with note: "Manual retry initiated by user"
**And** the card moves from its current position back to Inbox column
**And** previous error messages remain in the thread for context

**And** retry mutation is added to Convex `tasks.ts`
**And** the state machine allows crashed -> inbox transition for manual retry

## Epic 7: Reliability, Configuration & Security

System handles crashes gracefully with auto-retry, respects configurable timeouts, provides a dashboard settings panel, secures the dashboard with access token auth, and offers system health via CLI.

### Story 7.1: Implement Auto-Retry on Agent Crash

As a **user**,
I want the system to automatically retry a task once when an agent crashes,
So that transient failures are recovered without my intervention.

**Acceptance Criteria:**

**Given** an agent crashes while processing a task in "in_progress" state
**When** the crash is detected by the Agent Gateway
**Then** the task status transitions to "retrying" (FR37)
**And** a `task_retrying` activity event is created: "Agent {name} crashed. Auto-retrying (attempt 1/1)"
**And** the TaskCard shows a "Retrying" badge and card border flashes red once
**And** the system re-dispatches the task to the same agent (or Lead Agent if unavailable)

**Given** the auto-retry succeeds
**When** the agent completes the retried task
**Then** normal task flow resumes (transitions to review or done based on trust level)
**And** the retry attempt is noted in the activity feed

**Given** the auto-retry also fails
**When** the second crash is detected
**Then** the task status transitions to "crashed" (FR38)
**And** a `task_crashed` activity event is created with full error log
**And** the TaskCard shows: red left-border accent, red "Crashed" badge, error icon
**And** crash recovery completes within 30 seconds of initial crash detection (NFR10)

**And** crash detection and retry logic is implemented in `nanobot/mc/gateway.py`
**And** the `state_machine.py` allows: in_progress -> retrying, retrying -> in_progress (on retry), retrying -> crashed

### Story 7.2: Implement Timeout Detection & Escalation

As a **user**,
I want stalled tasks and slow reviews to be flagged automatically,
So that nothing gets stuck without me noticing.

**Acceptance Criteria:**

**Given** a task has been in "in_progress" state longer than the configured task timeout
**When** the timeout threshold is exceeded
**Then** the system flags the task as stalled (FR39)
**And** a `system_error` activity event is created: "Task '{title}' stalled — in progress for {duration}"
**And** the TaskCard shows a warning indicator (amber badge "Stalled")

**Given** an inter-agent review request has been pending longer than the configured inter-agent timeout
**When** the timeout threshold is exceeded
**Then** the system escalates the review (FR40)
**And** a `system_error` activity event is created: "Review for '{title}' timed out — escalating"
**And** the task detail thread shows a system message about the escalation

**Given** no custom timeout is configured on a task
**When** timeout checking runs
**Then** the global default timeout values are used (from settings)

**Given** a task has a custom timeout configured (FR42)
**When** timeout checking runs
**Then** the per-task timeout overrides the global default

**And** timeout checking is implemented as a periodic check in `nanobot/mc/gateway.py`
**And** timeout values are read from Convex `settings` table with per-task override from task document

### Story 7.3: Build Dashboard Settings Panel

As a **user**,
I want to configure global system defaults from the dashboard,
So that I can adjust timeouts and model settings without editing files.

**Acceptance Criteria:**

**Given** the dashboard is loaded
**When** the user accesses the settings panel (via a settings icon/button in the layout)
**Then** a settings view displays with configurable options:
- Global task timeout (number input, in minutes) (FR41)
- Global inter-agent review timeout (number input, in minutes) (FR41)
- System-wide default LLM model (select dropdown with available models) (FR43)

**Given** the user changes a setting value
**When** the user saves (or settings auto-save on change)
**Then** the setting is persisted to the Convex `settings` table as a key-value pair
**And** a subtle green checkmark appears next to the save area (auto-fades after 1.5s)
**And** the new value takes effect immediately for subsequent operations

**Given** no settings have been configured
**When** the settings panel renders
**Then** sensible defaults are displayed (e.g., task timeout: 30 minutes, inter-agent timeout: 10 minutes)

**And** settings UI is integrated into `DashboardLayout.tsx`
**And** Convex `settings.ts` contains `get`, `set`, and `list` queries/mutations

### Story 7.4: Implement Access Token Authentication

As a **user**,
I want the dashboard to require an access token when configured,
So that my Mission Control instance is not accessible to anyone on the network.

**Acceptance Criteria:**

**Given** the `MC_ACCESS_TOKEN` environment variable is set
**When** the user navigates to localhost:3000 without a valid session
**Then** they are redirected to `/login` — a page with an access token input field
**And** the login page uses ShadCN components consistent with the design system

**Given** the user enters the correct access token
**When** they submit the form
**Then** a cookie-based session is created (NFR19)
**And** they are redirected to the main dashboard
**And** subsequent requests are authenticated via the session cookie

**Given** the user enters an incorrect token
**When** they submit the form
**Then** an error message displays: "Invalid access token"
**And** no session is created

**Given** `MC_ACCESS_TOKEN` is NOT set
**When** the user navigates to localhost:3000
**Then** the dashboard loads directly without authentication (localhost convenience mode)

**And** `dashboard/middleware.ts` validates the session token on all routes except `/login`
**And** `dashboard/app/login/page.tsx` is created with the token input form
**And** Convex deployment key authenticates the Python SDK (separate from dashboard auth)

### Story 7.5: Implement CLI System Health & Documentation

As a **user**,
I want to check system health from the terminal and access auto-generated API documentation,
So that I can monitor Mission Control and reference the API without opening the dashboard.

**Acceptance Criteria:**

**Given** Mission Control is running
**When** the user runs `nanobot mc status` (FR44)
**Then** the CLI displays: number of running agents and their statuses, number of tasks by state, system uptime, Convex connection status, dashboard URL
**And** results return within 2 seconds (NFR5)

**Given** Mission Control is not running
**When** the user runs `nanobot mc status`
**Then** the CLI prints: "Mission Control is not running. Start with `nanobot mc start`"

**Given** the Convex schema is defined
**When** API documentation is generated (FR47)
**Then** documentation is auto-generated from Convex schema and function definitions
**And** it is accessible via `nanobot mc docs` or a static file generated during build

**And** the data privacy notice is documented in README regarding sensitive data transiting through Convex cloud (NFR20)
**And** CLI status command is added to `nanobot/cli/mc.py`

### Epic Dependencies

```
Epic 1 (Foundation) --> Epic 2 (Task Board)  --> Epic 4 (Routing) --> Epic 5 (Review)
                    --> Epic 3 (Agents)      --> Epic 4 (Routing) --> Epic 6 (HITL)
                                                                  --> Epic 7 (Reliability)
```

- Epics 2 and 3 can be developed in parallel after Epic 1
- Epics 5 and 6 are independent of each other
- Epic 7 is a cross-cutting hardening layer, benefits from all previous epics

## Epic 1: Project Foundation & System Lifecycle

User can start and stop the entire Mission Control system with a single command (`nanobot mc start` / `nanobot mc stop`) and see the dashboard at localhost:3000 with built-in CLI help.

### Story 1.1: Initialize Dashboard Project with Starter Template

As a **developer**,
I want to initialize the Mission Control dashboard using the official Convex Next.js + ShadCN starter template,
So that I have a working foundation with the correct tech stack and monorepo structure to build on.

**Acceptance Criteria:**

**Given** the nanobot-ennio project root exists
**When** the developer runs `npm create convex@latest -t nextjs-shadcn` in a `dashboard/` directory
**Then** a Next.js + TypeScript + Convex + Tailwind CSS + ShadCN UI project is created inside `dashboard/`
**And** the monorepo structure has `dashboard/` as a sibling to existing `nanobot/` package
**And** `dashboard/app/`, `dashboard/components/`, `dashboard/convex/`, `dashboard/lib/` directories exist
**And** `framer-motion` is added as a dependency
**And** required ShadCN components are installed via CLI (Card, Badge, Sheet, Tabs, ScrollArea, Avatar, Sidebar, Tooltip, Separator, Collapsible, Switch, Select, Checkbox, Input, Textarea, Button)
**And** `dashboard/.env.example` is created with `NEXT_PUBLIC_CONVEX_URL` and `MC_ACCESS_TOKEN` placeholders
**And** `npm run dev` from `dashboard/` starts the Next.js dev server at localhost:3000 successfully

### Story 1.2: Define Convex Data Schema

As a **developer**,
I want to define the complete Convex data schema with all 5 core tables and their typed validators,
So that all subsequent epics have a stable, shared data model to build against.

**Acceptance Criteria:**

**Given** the dashboard project is initialized (Story 1.1)
**When** the developer creates `dashboard/convex/schema.ts`
**Then** the `tasks` table is defined with fields: title (string), description (optional string), status (string — one of "inbox", "assigned", "in_progress", "review", "done", "retrying", "crashed"), assignedAgent (optional string), trustLevel (string — one of "autonomous", "agent_reviewed", "human_approved"), reviewers (optional array of strings), tags (optional array of strings), taskTimeout (optional number), interAgentTimeout (optional number), createdAt (string, ISO 8601), updatedAt (string, ISO 8601)
**And** the `messages` table is defined with fields: taskId (id referencing tasks), authorName (string), authorType (string — "agent", "user", "system"), content (string), messageType (string — "work", "review_feedback", "approval", "denial", "system_event"), timestamp (string, ISO 8601)
**And** the `agents` table is defined with fields: name (string), displayName (string), role (string), skills (array of strings), status (string — one of "active", "idle", "crashed"), model (optional string), lastActiveAt (optional string, ISO 8601)
**And** the `activities` table is defined with fields: taskId (optional id referencing tasks), agentName (optional string), eventType (string — matching ActivityEventType values), description (string), timestamp (string, ISO 8601)
**And** the `settings` table is defined with fields: key (string), value (string)
**And** all tables have appropriate indexes defined for common query patterns (tasks by status, messages by taskId, activities by taskId, agents by name, settings by key)
**And** the Convex dev server starts without schema validation errors
**And** `dashboard/convex/_generated/` types are auto-generated from the schema

### Story 1.3: Build AsyncIO-Convex Bridge Core

As a **developer**,
I want a Python bridge module that connects the nanobot AsyncIO runtime to Convex via the Python SDK,
So that agents can read and write shared state through a single, well-defined integration point.

**Acceptance Criteria:**

**Given** the Convex schema is defined (Story 1.2)
**When** the developer creates `nanobot/mc/bridge.py`
**Then** the `ConvexBridge` class can establish a connection to a Convex deployment using the deployment URL and auth credentials
**And** the bridge can call Convex mutations (write operations) with Python dict arguments
**And** the bridge can call Convex queries (read operations) and return results as Python dicts
**And** the bridge can subscribe to Convex queries and receive real-time updates via callbacks
**And** all outgoing data converts field names from snake_case to camelCase at the bridge boundary
**And** all incoming data converts field names from camelCase to snake_case at the bridge boundary
**And** `nanobot/mc/__init__.py` and `nanobot/mc/types.py` are created with shared Python types/dataclasses for task status, trust level, agent status, and activity event types
**And** the bridge is the ONLY Python module that imports the `convex` Python SDK
**And** unit tests exist in `nanobot/mc/bridge.test.py` covering connection, mutation calls, query calls, and case conversion

### Story 1.4: Add Bridge Retry Logic & Dual Logging

As a **developer**,
I want the Convex bridge to retry failed writes and log all state transitions to both Convex and local stdout,
So that the system is resilient to transient failures and all activity is observable for debugging.

**Acceptance Criteria:**

**Given** the bridge core is implemented (Story 1.3)
**When** a Convex mutation call fails
**Then** the bridge retries up to 3 times with exponential backoff (e.g., 1s, 2s, 4s)
**And** after retry exhaustion, the bridge logs the error to local stdout with full context (mutation name, arguments, error message)
**And** after retry exhaustion, the bridge makes a best-effort attempt to write an error activity event to the Convex `activities` table

**Given** any task or agent state transition is written via the bridge
**When** the mutation succeeds
**Then** the state transition is logged to local stdout with timestamp, entity, old state, new state
**And** a corresponding activity event is written to the Convex `activities` table in the same mutation call

**Given** the bridge retry logic is active
**When** a retry succeeds on attempt 2 or 3
**Then** the successful retry is logged to stdout noting which attempt succeeded
**And** no error activity event is written (only on exhaustion)

**And** unit tests exist in `nanobot/mc/bridge.test.py` covering retry scenarios (success on retry, exhaustion), dual logging, and exponential backoff timing

### Story 1.5: Implement Process Manager

As a **developer**,
I want a process manager that spawns and monitors all Mission Control subprocesses,
So that the system can be started and stopped reliably as a coordinated unit.

**Acceptance Criteria:**

**Given** the bridge and dashboard project exist (Stories 1.1-1.4)
**When** the process manager is invoked to start
**Then** it spawns 3 child processes: Agent Gateway (Python AsyncIO main loop), Next.js dev server (`npm run dev` in `dashboard/`), and Convex dev server (`npx convex dev` in `dashboard/`)
**And** all 3 processes start within 15 seconds (NFR6)
**And** the process manager monitors child process health and detects crashes
**And** stdout/stderr from child processes are captured and forwarded to the main process stdout

**Given** the process manager receives a shutdown signal
**When** graceful shutdown is initiated
**Then** all child processes receive termination signals in reverse startup order
**And** the process manager waits up to 30 seconds for all processes to exit (NFR14)
**And** all task state in Convex is preserved (no in-flight mutations lost)
**And** if a child process does not exit within the timeout, it is force-killed

**And** the module is created at `nanobot/mc/process_manager.py`
**And** the module does not exceed 500 lines (NFR21)
**And** unit tests exist in `nanobot/mc/process_manager.test.py`

### Story 1.6: Implement CLI Lifecycle Commands

As a **user**,
I want to start and stop Mission Control with simple CLI commands and get help for all available subcommands,
So that I can manage the system lifecycle without manual process management.

**Acceptance Criteria:**

**Given** the process manager is implemented (Story 1.5)
**When** the user runs `nanobot mc start`
**Then** all Mission Control processes start (Agent Gateway, Next.js, Convex dev)
**And** the dashboard is accessible at localhost:3000
**And** the CLI prints startup status showing each process launched
**And** the CLI remains running, forwarding process output to stdout

**Given** Mission Control is running
**When** the user runs `nanobot mc stop`
**Then** graceful shutdown is initiated via the process manager
**And** the CLI prints shutdown progress for each process
**And** the CLI exits cleanly when all processes have stopped

**Given** the user wants to discover available commands
**When** the user runs `nanobot mc --help`
**Then** all available subcommands are listed with brief descriptions (start, stop, agents, tasks, status)
**And** each subcommand supports `--help` (e.g., `nanobot mc start --help`)

**And** the CLI module is created at `nanobot/cli/mc.py`
**And** the CLI is a thin layer that delegates to `nanobot/mc/` package functions — no business logic in CLI
**And** the module does not exceed 500 lines (NFR21)
