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
lastStep: 8
status: 'complete'
completedAt: '2026-02-22'
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
workflowType: 'architecture'
project_name: 'nanobot-ennio'
user_name: 'Ennio'
date: '2026-02-22'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**

48 functional requirements across 8 categories:

| Category | FRs | Architectural Implication |
|----------|-----|--------------------------|
| Task Management (FR1-FR9) | 9 | Task entity is the central data model — CRUD from both dashboard and CLI, real-time Kanban visualization, configurable trust/review at creation |
| Agent Management (FR10-FR18) | 9 | YAML-driven agent registry with strict validation, auto-detection, agent-assisted CLI generation — configuration-driven architecture |
| Task Orchestration (FR19-FR25) | 7 | Lead Agent as intelligent router with execution planning, capability matching, dependency-aware parallel dispatch — requires structured agent metadata |
| Inter-Agent Collaboration (FR26-FR30) | 5 | Task-scoped threaded messaging, targeted reviewer routing (not broadcast), revision cycles within Review state — task entity carries conversation history |
| Human Oversight (FR31-FR36) | 6 | HITL approval gates with approve/deny from dashboard, notification indicators, activity feed streaming, manual crash retry — user actions as Convex mutations |
| Reliability & Error Handling (FR37-FR40) | 4 | Auto-retry (1x), crash detection with error logging, configurable timeouts for task stalls and inter-agent review escalation |
| System Configuration (FR41-FR44) | 4 | Global defaults (timeouts, LLM model) from dashboard settings, per-task overrides at creation — layered configuration model |
| System Lifecycle (FR45-FR48) | 4 | Single-command start/stop, auto-generated API docs, built-in CLI help — developer experience as a first-class concern |

**Non-Functional Requirements:**

23 NFRs across 5 categories:

| Category | NFRs | Key Constraints |
|----------|------|----------------|
| Performance (NFR1-NFR6) | 6 | Dashboard updates < 2s, agent pickup < 5s, feed delay < 3s, initial load < 5s, CLI < 2s, system startup < 15s |
| Reliability (NFR7-NFR14) | 8 | 24h unattended operation, no silent failures, zero message loss, crash recovery < 30s, 3 agents + 4 tasks concurrent, transactional integrity, connection loss detection, graceful shutdown < 30s |
| Integration (NFR15-NFR18) | 4 | AsyncIO-Convex bridge with 3x retry + exponential backoff, dashboard read-only (user actions via mutations), YAML change detection on CLI/refresh, CLI-dashboard state parity |
| Security (NFR19-NFR20) | 2 | Configurable access token auth, data privacy notice for Convex cloud transit |
| Code Quality (NFR21-NFR23) | 3 | No module > 500 lines, actionable YAML validation errors, dual logging (Convex activity feed + local stdout) |

**Scale & Complexity:**

- Primary domain: Full-stack (Python/AsyncIO backend + Next.js/Convex frontend)
- Complexity level: Medium-High
- Estimated architectural components: ~12-15 distinct modules spanning two runtimes

### Technical Constraints & Dependencies

- **Brownfield:** Extends existing nanobot framework — SubagentManager, MessageBus, HeartbeatService, SkillsLoader are existing primitives to build on, not replace
- **Dual runtime:** Python/AsyncIO (agent orchestration) + Node.js/Next.js (dashboard) — the AsyncIO-Convex bridge is the critical integration seam
- **Convex as real-time backend:** Provides reactive queries, transactional mutations, and persistent storage — eliminates need for custom WebSocket server or polling
- **One-directional data flow:** nanobot writes -> Convex stores -> dashboard reads. Dashboard user actions go through Convex mutations. No direct dashboard-to-nanobot communication
- **ShadCN UI + Tailwind CSS:** Component library chosen, design system established — architectural decisions must align with this stack
- **YAML-based configuration:** Agent definitions, not code — the system must load, validate, and hot-detect YAML files
- **500-line module limit (NFR21):** Forces modular decomposition — no monolithic orchestration files
- **MVP capacity:** 3 simultaneous agents, 4+ concurrent tasks — not a high-scale system, but must be reliable

### Cross-Cutting Concerns Identified

- **State consistency:** Task state must be identical across nanobot runtime, Convex, and dashboard at all times. The bridge is the single point of truth synchronization. Convex is the source of truth for shared state.
- **Error propagation:** Agent crashes, bridge failures, and Convex write failures must all surface to the user through consistent mechanisms (activity feed + card status + CLI output).
- **Configuration layering:** Global defaults (dashboard settings) -> per-agent config (YAML) -> per-task overrides (creation-time). Architecture must support this precedence chain.
- **Authentication:** Access token for dashboard (NFR19). Simple but must be consistent across dashboard routes and Convex API.
- **Observability:** Dual logging to Convex activity feed (for dashboard) and local stdout (for debugging). Every state transition must be logged to both (NFR23).
- **Graceful lifecycle:** Start and stop must be orchestrated across multiple processes (Next.js server, agent gateway, Convex connection). Single command, clean shutdown preserving state.

## Starter Template Evaluation

### Primary Technology Domain

Full-stack: Next.js/TypeScript (dashboard SPA) + Python/AsyncIO (nanobot backend, brownfield) + Convex (real-time BaaS)

### Starter Options Considered

| Template | Fit | Verdict |
|----------|-----|---------|
| `get-convex/template-nextjs-shadcn` | Next.js + TypeScript + Convex + Tailwind + ShadCN. No auth. | Best fit — minimal, exact stack match |
| `get-convex/template-nextjs-convexauth-shadcn` | Same + Convex Auth + middleware + sign-in | Over-engineered for localhost single-user access token auth |
| `get-convex/template-nextjs-clerk-shadcn` | Same + Clerk | External dependency, cost, overkill for MVP |
| `convex-ents-saas-starter` | Full SaaS starter with Clerk + subscriptions | Way too much — SaaS patterns not applicable |
| Manual setup (`create-next-app` + manual Convex + ShadCN) | Full control | More setup risk, no benefit over official template |

### Selected Starter: `get-convex/template-nextjs-shadcn`

**Rationale for Selection:**
- Exact stack match: Next.js App Router + TypeScript + Convex + Tailwind CSS + ShadCN UI
- No unnecessary auth dependency — PRD requires simple access token (NFR19), not a full auth system
- Minimal footprint aligns with nanobot's "readable orchestration" philosophy
- Official Convex template, actively maintained
- Pre-configured tooling: ESLint, Prettier, TypeScript, PostCSS

**Initialization Command:**

```bash
npm create convex@latest -t nextjs-shadcn
```

**Architectural Decisions Provided by Starter:**

**Language & Runtime:** TypeScript (strict), Node.js runtime for Next.js, Convex runtime for backend functions

**Styling Solution:** Tailwind CSS with PostCSS, ShadCN UI component library with CSS variables for theming

**Build Tooling:** Next.js built-in (Turbopack dev, Webpack production), Convex CLI for backend deployment

**Testing Framework:** Not included — to be decided in architectural decisions

**Code Organization:** `app/` (Next.js pages), `components/` (React/ShadCN), `convex/` (backend schema + functions), `lib/` (utilities)

**Development Experience:** Hot reloading via Next.js dev server, Convex dev server with live sync, TypeScript type generation from Convex schema

**Additional Packages Required:**

| Package | Purpose |
|---------|---------|
| `framer-motion` | Kanban card transitions, UI animations (per UX spec) |
| ShadCN components (via CLI) | Card, Badge, Sheet, Tabs, ScrollArea, Avatar, Sidebar, Tooltip, Separator, Collapsible, Switch, Select, Checkbox |

**Note:** The Python/AsyncIO nanobot backend is brownfield — extends existing framework code. No starter template needed; new orchestration modules are added to the existing codebase.

**Note:** Project initialization using this command should be the first implementation story.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- AsyncIO-Convex bridge via Python SDK (bidirectional communication)
- Data model with 5 core Convex tables
- Convex as single communication hub (no separate API layer)
- Process orchestration for `nanobot mc start`

**Important Decisions (Shape Architecture):**
- No external state management library (Convex reactive queries + React built-ins)
- Simple access token auth (no external auth service)
- Monorepo structure (`dashboard/` within nanobot project)
- Vitest for dashboard, pytest for Python

**Deferred Decisions (Post-MVP):**
- Full auth system (Convex Auth or similar) for multi-user support (Phase 3)
- Convex self-hosting for data privacy
- E2E testing framework
- Performance benchmarking infrastructure

### Data Architecture

**Database:** Convex (built-in with starter, document-based with typed schemas)

**Core Tables:**

| Table | Purpose | Key Relationships |
|-------|---------|-------------------|
| `tasks` | Central entity — Kanban card, task state machine, trust config, optional tags for Card-Rich display | References agents by name, has many messages and activities |
| `messages` | Task-scoped threaded conversation (inter-agent + HITL feedback) | Belongs to task, authored by agent or user |
| `agents` | Agent registry synced from YAML definitions | Referenced by tasks |
| `activities` | Append-only activity feed events | Optionally references task and agent |
| `settings` | Global configuration key-value store | Standalone |

**Data Validation:**
- Convex schema validators (`v.string()`, `v.number()`, etc.) enforce types at runtime in `schema.ts`
- Python-side YAML validation via pydantic or cerberus for agent configuration (FR13-FR14)
- No Zod — Convex validators are sufficient for the TypeScript side

**Data Flow:**
- YAML files are the source of truth for agent definitions
- nanobot reads YAML, validates, writes to Convex `agents` table
- Convex is the source of truth for all shared runtime state (tasks, messages, activities, settings)
- Dashboard reads exclusively from Convex reactive queries

### Authentication & Security

**MVP: Simple Access Token**
- `MC_ACCESS_TOKEN` environment variable
- Next.js middleware validates token on dashboard routes
- Cookie-based session after initial token input
- If no token configured, dashboard runs open (localhost convenience)
- Convex deployment key authenticates Python SDK

**Post-MVP: Full Auth System**
- Deferred to Phase 3 (multi-user support)
- Convex Auth or similar for user accounts, roles, permissions
- Documented as upgrade path, not a refactoring — current token pattern is easily replaceable

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
| Dashboard → Convex | Mutations | Create task, approve/deny, update settings |
| Convex → Dashboard | Reactive queries | Auto-updating Kanban, feed, agent status |
| nanobot → Convex | Mutations (Python SDK) | Task state changes, activity events, agent status, messages |
| Convex → nanobot | Subscriptions (Python SDK) | New tasks, HITL decisions, settings changes |
| CLI → Convex | Queries (Python SDK) | `mc tasks list`, `mc agents list`, `mc status` |

**Error Handling:**
- Python SDK retries failed writes 3x with exponential backoff (NFR15)
- After retry exhaustion: log to local stdout + best-effort error activity event
- Dashboard detects connection loss → "Reconnecting..." banner (NFR13)
- All errors surface through consistent mechanisms: activity feed + card status + local stdout (NFR23)

### Frontend Architecture

**State Management:**
- Primary: Convex reactive queries (tasks, agents, activities, settings — all server state)
- Local: React `useState`/`useReducer` (sidebar toggle, Sheet open/close, input text, form state)
- No additional library (no Redux, Zustand, Jotai)

**Routing:**
- `/` — Main dashboard (Kanban + sidebar + feed). Task detail is a Sheet overlay, not a route.
- `/login` — Access token input (only if `MC_ACCESS_TOKEN` is configured)

**Performance:**
- Optimistic UI via Convex built-in optimistic updates
- Framer Motion `layoutId` for GPU-accelerated card transitions
- `prefers-reduced-motion` media query respect
- No SSR — localhost SPA, no SEO requirements

**Component Organization:**
- `components/ui/` — ShadCN UI primitives
- `components/` — Custom compositions (KanbanBoard, TaskCard, TaskInput, ActivityFeed, etc.)
- Flat structure for MVP

### Infrastructure & Deployment

**Process Orchestration (`nanobot mc start`):**

| Process | Role | Lifecycle |
|---------|------|-----------|
| Agent Gateway | Python AsyncIO — connects agents to Convex, manages agent lifecycle | Main process |
| Next.js dev server | Dashboard at `localhost:3000` | Child subprocess |
| Convex dev server | Backend function sync + reactive backend | Child subprocess |

- `nanobot mc start` spawns all three, monitors health
- `nanobot mc stop` sends graceful shutdown, waits up to 30s (NFR14), preserves all state in Convex

**Convex Deployment:**
- MVP: Convex Cloud (zero infrastructure, free tier sufficient)
- Post-MVP: Self-hosted via Docker + SQLite/Postgres (data privacy upgrade path)

**Project Structure:**
- Monorepo — `dashboard/` directory within nanobot project
- Single `nanobot mc start` command runs everything
- Hot-reload for both dashboard (Next.js) and backend functions (Convex CLI)

**Testing Strategy:**
- Dashboard: Vitest (fast, native ESM, Convex-recommended)
- Python: pytest (existing nanobot convention)
- E2E: Manual testing through dashboard for MVP, framework deferred to post-MVP

### Decision Impact Analysis

**Implementation Sequence:**
1. Initialize dashboard project (`npm create convex@latest -t nextjs-shadcn`)
2. Define Convex schema (`tasks`, `messages`, `agents`, `activities`, `settings`)
3. Build AsyncIO-Convex bridge (Python SDK integration)
4. Implement task state machine (Convex mutations)
5. Build dashboard layout (Kanban + sidebar + feed)
6. Wire reactive queries to dashboard components
7. Implement HITL approval flow
8. Build CLI commands
9. Add access token auth

**Cross-Component Dependencies:**
- Convex schema must be defined before any dashboard or bridge work
- Python SDK bridge must work before agents can process tasks
- Task state machine (Convex mutations) must exist before dashboard can display state transitions
- Agent YAML validation (Python) feeds into Convex `agents` table — both sides must agree on the agent data shape

## Implementation Patterns & Consistency Rules

### Naming Patterns

**Convex Schema (TypeScript side):**

| Element | Convention | Example |
|---------|-----------|---------|
| Table names | camelCase, plural | `tasks`, `messages`, `agents`, `activities`, `settings` |
| Field names | camelCase | `assignedAgent`, `trustLevel`, `taskId`, `createdAt` |
| Convex functions | camelCase, verb-first | `tasks.create`, `tasks.updateStatus`, `agents.list` |
| Convex function files | camelCase, plural (matches table) | `convex/tasks.ts`, `convex/messages.ts` |

**React/Dashboard (TypeScript side):**

| Element | Convention | Example |
|---------|-----------|---------|
| Component files | PascalCase | `KanbanBoard.tsx`, `TaskCard.tsx`, `ActivityFeed.tsx` |
| Component names | PascalCase | `export function KanbanBoard()` |
| Hook files | camelCase, `use` prefix | `useTaskSubscription.ts` |
| Utility files | camelCase | `formatTimestamp.ts` |
| CSS/style | Tailwind utilities only | No CSS modules, no styled-components |
| Props interfaces | `{Component}Props` | `TaskCardProps`, `FeedItemProps` |

**Python (nanobot side):**

| Element | Convention | Example |
|---------|-----------|---------|
| Module files | snake_case | `convex_bridge.py`, `task_state_machine.py` |
| Classes | PascalCase | `ConvexBridge`, `AgentGateway`, `TaskOrchestrator` |
| Functions/methods | snake_case | `update_task_status()`, `sync_agent_registry()` |
| Constants | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT`, `DEFAULT_TIMEOUT_SECONDS` |
| Config keys (YAML) | snake_case | `assigned_to`, `trust_level`, `require_human_approval` |

**Cross-boundary rule:** When data crosses the Python-Convex boundary, field names convert to match the target convention. Python sends `snake_case`, the bridge layer converts to `camelCase` for Convex mutations. Convex subscription data arrives as `camelCase` and is converted to `snake_case` for Python consumption.

### Structure Patterns

**Dashboard (`dashboard/`) organization:**

```
dashboard/
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   └── login/
│       └── page.tsx
├── components/
│   ├── ui/                  # ShadCN primitives (auto-generated)
│   ├── KanbanBoard.tsx
│   ├── TaskCard.tsx
│   ├── TaskInput.tsx
│   ├── ActivityFeed.tsx
│   ├── FeedItem.tsx
│   ├── AgentSidebarItem.tsx
│   ├── TaskDetailSheet.tsx
│   ├── ThreadMessage.tsx
│   └── InlineRejection.tsx
├── convex/
│   ├── schema.ts
│   ├── tasks.ts
│   ├── messages.ts
│   ├── agents.ts
│   ├── activities.ts
│   └── settings.ts
├── lib/
│   └── utils.ts
└── public/
```

**Python orchestration modules (within existing nanobot):**

```
nanobot/
├── mc/
│   ├── __init__.py
│   ├── cli.py
│   ├── gateway.py
│   ├── bridge.py
│   ├── orchestrator.py
│   ├── state_machine.py
│   ├── yaml_validator.py
│   └── process_manager.py
```

**Test location:** Co-located with source files.
- Dashboard: `KanbanBoard.test.tsx` next to `KanbanBoard.tsx`
- Python: `test_bridge.py` next to `bridge.py`

### Format Patterns

**Task Status Values (exact strings, used across all systems):**

```typescript
type TaskStatus = "inbox" | "assigned" | "in_progress" | "review" | "done" | "retrying" | "crashed"
```

**Activity Event Types:**

```typescript
type ActivityEventType =
  | "task_created" | "task_assigned" | "task_started" | "task_completed"
  | "task_crashed" | "task_retrying"
  | "review_requested" | "review_feedback" | "review_approved"
  | "hitl_requested" | "hitl_approved" | "hitl_denied"
  | "agent_connected" | "agent_disconnected" | "agent_crashed"
  | "system_error"
```

**Trust Level Values:**

```typescript
type TrustLevel = "autonomous" | "agent_reviewed" | "human_approved"
```

**Agent Status Values:**

```typescript
type AgentStatus = "active" | "idle" | "crashed"
```

**Timestamps:** ISO 8601 strings (`2026-02-22T10:30:00Z`) everywhere — Convex, Python, dashboard.

### Communication Patterns

**Convex Mutation Pattern:** Every mutation that modifies task state MUST also write a corresponding activity event. No task state change without a feed entry.

```typescript
export const updateStatus = mutation({
  args: { taskId: v.id("tasks"), status: v.string(), agentName: v.string() },
  handler: async (ctx, args) => {
    await ctx.db.patch(args.taskId, { status: args.status });
    await ctx.db.insert("activities", {
      taskId: args.taskId,
      agentName: args.agentName,
      eventType: "task_started",
      description: "Agent started working on task",
      timestamp: new Date().toISOString(),
    });
  },
});
```

**Python Bridge Call Pattern:** Every bridge call follows try-retry-log pattern.

```python
async def update_task_status(self, task_id: str, status: str, agent_name: str):
    await self._call_mutation_with_retry(
        "tasks:updateStatus",
        {"taskId": task_id, "status": status, "agentName": agent_name}
    )
```

### Process Patterns

**Error Handling:**

| Layer | Pattern |
|-------|---------|
| Convex mutations | Throw `ConvexError` with user-readable message |
| Python bridge | Catch, retry 3x with exponential backoff, then log + write error activity |
| Dashboard | Convex handles errors via `useQuery`/`useMutation` error states — show in feed, red badge on card |
| YAML validation | Collect all errors, return list with field + expected + actual + line number |

**Loading States:**
- Convex's built-in loading states (`useQuery` returns `undefined` while loading)
- No custom loading state management, no skeleton screens for MVP
- Feed shows "Waiting for activity..." when empty (empty state, not loading state)

### Enforcement Guidelines

**All AI Agents MUST:**

1. Follow naming conventions exactly — camelCase in TypeScript, snake_case in Python, PascalCase for React components
2. Never change task status without writing a corresponding activity event
3. Use the exact string values for task status, trust level, agent status, and event types
4. Convert field names at the Python-Convex boundary (snake_case to camelCase and back)
5. Keep all modules under 500 lines (NFR21)
6. Co-locate tests with source files
7. Use Convex validators for TypeScript-side validation, pydantic for Python-side YAML validation
8. Use ISO 8601 for all timestamps

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
│   │   ├── commands.py
│   │   └── mc.py                       # NEW — nanobot mc subcommands
│   ├── config/
│   │   ├── loader.py
│   │   └── schema.py
│   ├── heartbeat/
│   │   └── service.py
│   ├── channels/
│   ├── providers/
│   ├── session/
│   ├── skills/
│   ├── utils/
│   │
│   └── mc/                             # NEW — Mission Control package
│       ├── __init__.py
│       ├── gateway.py                  # Agent Gateway — AsyncIO main loop
│       ├── gateway.test.py
│       ├── bridge.py                   # Convex Python SDK wrapper
│       ├── bridge.test.py
│       ├── orchestrator.py             # Lead Agent routing + execution planning
│       ├── orchestrator.test.py
│       ├── state_machine.py            # Task state transitions + validation
│       ├── state_machine.test.py
│       ├── yaml_validator.py           # Agent YAML schema validation (pydantic)
│       ├── yaml_validator.test.py
│       ├── process_manager.py          # Subprocess mgmt (Next.js, Convex dev)
│       └── types.py                    # Shared Python types/dataclasses
│
├── dashboard/                          # NEW — Next.js + Convex dashboard
│   ├── package.json
│   ├── package-lock.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── postcss.config.mjs
│   ├── eslint.config.mjs
│   ├── .prettierrc
│   ├── components.json                 # ShadCN UI config
│   ├── .env.local                      # NEXT_PUBLIC_CONVEX_URL, MC_ACCESS_TOKEN
│   ├── .env.example
│   │
│   ├── app/
│   │   ├── globals.css                 # Tailwind base + ShadCN theme tokens
│   │   ├── layout.tsx                  # Root layout — ConvexProvider wrapper
│   │   ├── page.tsx                    # Main dashboard
│   │   ├── providers.tsx               # ConvexClientProvider component
│   │   └── login/
│   │       └── page.tsx                # Access token input page
│   │
│   ├── components/
│   │   ├── ui/                         # ShadCN primitives (auto-generated)
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── badge.tsx
│   │   │   ├── input.tsx
│   │   │   ├── textarea.tsx
│   │   │   ├── sheet.tsx
│   │   │   ├── tabs.tsx
│   │   │   ├── scroll-area.tsx
│   │   │   ├── avatar.tsx
│   │   │   ├── tooltip.tsx
│   │   │   ├── separator.tsx
│   │   │   ├── collapsible.tsx
│   │   │   ├── switch.tsx
│   │   │   ├── select.tsx
│   │   │   └── checkbox.tsx
│   │   │
│   │   ├── DashboardLayout.tsx         # CSS Grid layout orchestrator
│   │   ├── KanbanBoard.tsx             # 5-column board with CSS Grid
│   │   ├── KanbanBoard.test.tsx
│   │   ├── KanbanColumn.tsx            # Single column with ScrollArea
│   │   ├── TaskCard.tsx                # Card with status border + badge + avatar
│   │   ├── TaskCard.test.tsx
│   │   ├── TaskInput.tsx               # Always-visible input + progressive disclosure
│   │   ├── TaskInput.test.tsx
│   │   ├── ActivityFeed.tsx            # Real-time event stream
│   │   ├── ActivityFeed.test.tsx
│   │   ├── FeedItem.tsx                # Single feed entry
│   │   ├── AgentSidebar.tsx            # Sidebar container (collapsible)
│   │   ├── AgentSidebarItem.tsx        # Agent entry with status dot
│   │   ├── TaskDetailSheet.tsx         # Slide-out panel with tabs
│   │   ├── TaskDetailSheet.test.tsx
│   │   ├── ThreadMessage.tsx           # Single message in task thread
│   │   └── InlineRejection.tsx         # Expandable deny feedback
│   │
│   ├── convex/
│   │   ├── _generated/                 # Auto-generated by Convex CLI
│   │   ├── schema.ts                   # All table definitions
│   │   ├── tasks.ts                    # Task queries + mutations
│   │   ├── messages.ts                 # Message queries + mutations
│   │   ├── agents.ts                   # Agent queries + mutations
│   │   ├── activities.ts               # Activity queries + mutations
│   │   └── settings.ts                 # Settings queries + mutations
│   │
│   ├── lib/
│   │   ├── utils.ts                    # ShadCN cn() utility + helpers
│   │   └── constants.ts                # Shared constants (status values, event types)
│   │
│   ├── middleware.ts                   # Access token validation
│   │
│   └── public/
│       └── favicon.ico
│
├── workspace/                          # Existing — shared agent workspace
│   ├── AGENTS.md
│   ├── SOUL.md
│   ├── TOOLS.md
│   ├── USER.md
│   ├── HEARTBEAT.md
│   └── memory/
│
├── tests/                              # Existing test directory
└── docs/
```

### Architectural Boundaries

**Boundary 1: Python to Convex (the Bridge)**

`nanobot/mc/bridge.py` is the ONLY Python module that imports the `convex` Python SDK. All other Python modules call `bridge.py` methods — never Convex directly. Bridge handles: connection management, retry logic, snake_case to camelCase conversion, error wrapping.

**Boundary 2: Convex Functions to Dashboard**

Components never access Convex directly — always through `useQuery(api.tasks.list)` or `useMutation(api.tasks.create)`. Convex functions are the API layer — all business logic (validation, state transitions, activity logging) lives in Convex functions. Components are purely presentational + user interaction.

**Boundary 3: Existing nanobot to Mission Control**

Mission Control imports from existing nanobot modules (SubagentManager, MessageBus, HeartbeatService). Existing nanobot modules do NOT import from `mc/` — the dependency is one-directional. `mc/gateway.py` is the integration point — it uses existing agent infrastructure to run Mission Control agents.

**Boundary 4: CLI to Mission Control**

`nanobot/cli/mc.py` defines the `nanobot mc` subcommands. CLI commands call `mc/` package functions — thin command layer, no business logic in CLI.

### Requirements to Structure Mapping

| FR Category | Dashboard Files | Python Files | Convex Files |
|-------------|----------------|--------------|--------------|
| Task Management (FR1-FR9) | `TaskInput.tsx`, `KanbanBoard.tsx`, `TaskCard.tsx`, `TaskDetailSheet.tsx` | — | `tasks.ts`, `schema.ts` |
| Agent Management (FR10-FR18) | `AgentSidebar.tsx`, `AgentSidebarItem.tsx` | `yaml_validator.py`, `gateway.py` | `agents.ts`, `schema.ts` |
| Task Orchestration (FR19-FR25) | `TaskCard.tsx` (status updates) | `orchestrator.py`, `state_machine.py` | `tasks.ts` (mutations) |
| Inter-Agent Collaboration (FR26-FR30) | `ThreadMessage.tsx`, `TaskDetailSheet.tsx` | `orchestrator.py`, `bridge.py` | `messages.ts` |
| Human Oversight (FR31-FR36) | `InlineRejection.tsx`, `TaskCard.tsx`, `ActivityFeed.tsx` | `bridge.py` (subscriptions) | `tasks.ts`, `activities.ts` |
| Reliability (FR37-FR40) | `TaskCard.tsx` (crashed badge), `FeedItem.tsx` | `state_machine.py`, `bridge.py` | `tasks.ts`, `activities.ts` |
| System Configuration (FR41-FR44) | Settings panel in `DashboardLayout.tsx` | `bridge.py` | `settings.ts` |
| System Lifecycle (FR45-FR48) | — | `cli/mc.py`, `process_manager.py` | — |

### Cross-Cutting Concerns Mapping

| Concern | Files Involved |
|---------|---------------|
| State consistency | `bridge.py`, `convex/tasks.ts`, all dashboard components via `useQuery` |
| Error propagation | `bridge.py` (retry + log), `convex/activities.ts` (error events), `FeedItem.tsx` (error display), `TaskCard.tsx` (crashed badge) |
| Dual logging | `bridge.py` (local stdout), `convex/activities.ts` (Convex feed) |
| Configuration layering | `convex/settings.ts` (global), `yaml_validator.py` (per-agent), `convex/tasks.ts` (per-task) |
| Access token auth | `middleware.ts`, `app/login/page.tsx`, `.env.local` |

### Data Flow

```
User Action (Dashboard)
  → Convex Mutation (convex/tasks.ts)
    → Convex DB updated
      → Python SDK Subscription (bridge.py) triggers
        → Agent Gateway (gateway.py) dispatches to agent
          → Agent processes task
            → Bridge writes status mutation (bridge.py)
              → Convex DB updated
                → Dashboard reactive query auto-updates
                  → KanbanBoard re-renders with new state
```

## Architecture Validation Results

### Coherence Validation

**Decision Compatibility:** All technology choices work together without conflicts. Next.js + Convex + ShadCN + Tailwind + Framer Motion on the dashboard, Python AsyncIO + Convex Python SDK on the backend. Convex as single communication hub eliminates transport conflicts.

**Pattern Consistency:** Naming conventions are standard per language, conversion rules at the Python-Convex boundary are explicit, activity event pattern is uniformly applied, test location strategy is consistent.

**Structure Alignment:** Clean separation between dashboard (TypeScript) and backend (Python). Single integration point (bridge.py). One-directional dependency from mc/ to existing nanobot modules.

### Requirements Coverage Validation

**Functional Requirements:** 48/48 FRs fully covered by architectural components with explicit file mapping.

**Non-Functional Requirements:** 23/23 NFRs addressed through architectural decisions (Convex reactive queries for performance, retry logic for reliability, access token for security, 500-line limit for code quality).

### Implementation Readiness Validation

**Decision Completeness:** All critical decisions documented with versions. 8 mandatory enforcement rules for AI agents. Code examples for key patterns.

**Structure Completeness:** Full directory tree defined. All custom components listed. All Convex function files specified. Python module structure mapped.

**Pattern Completeness:** Naming, structure, format, communication, and process patterns all defined. Exact string values specified for all enums (task status, trust level, agent status, event types).

### Architecture Completeness Checklist

**Requirements Analysis**
- [x] Project context thoroughly analyzed (48 FRs, 23 NFRs)
- [x] Scale and complexity assessed (medium-high)
- [x] Technical constraints identified (brownfield, dual runtime, 500-line limit)
- [x] Cross-cutting concerns mapped (state consistency, error propagation, config layering, auth, observability, lifecycle)

**Architectural Decisions**
- [x] Critical decisions documented (Convex Python SDK bridge, 5-table data model, Convex as comm hub, process orchestration)
- [x] Technology stack fully specified (versions verified via web search)
- [x] Integration patterns defined (bidirectional through Convex)
- [x] Performance considerations addressed (reactive queries, optimistic UI)

**Implementation Patterns**
- [x] Naming conventions established (per-language + cross-boundary conversion)
- [x] Structure patterns defined (co-located tests, flat component structure)
- [x] Communication patterns specified (mutation + activity event, bridge retry)
- [x] Process patterns documented (error handling, loading states)

**Project Structure**
- [x] Complete directory structure defined
- [x] Component boundaries established (4 explicit boundaries)
- [x] Integration points mapped (bridge.py as single point)
- [x] Requirements to structure mapping complete (FR to file mapping table)

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

**Confidence Level:** High

**Key Strengths:**
- Clean separation between two runtimes with a single, well-defined bridge
- Convex as single communication hub eliminates transport complexity
- Brownfield approach preserves existing nanobot infrastructure
- Every FR and NFR has an explicit architectural home
- Enforcement rules prevent AI agent inconsistency

**Areas for Future Enhancement:**
- Full auth system (Phase 3, multi-user)
- Convex self-hosting (post-MVP, data privacy)
- E2E testing framework (post-MVP)
- Performance benchmarking infrastructure (post-MVP)
- Heartbeat/cron integration detail (during gateway.py implementation)

### Implementation Handoff

**AI Agent Guidelines:**
- Follow all architectural decisions exactly as documented
- Use implementation patterns consistently across all components
- Respect project structure and boundaries — especially the 4 architectural boundaries
- Refer to this document for all architectural questions
- When in doubt, check the Enforcement Guidelines (8 mandatory rules)

**First Implementation Priority:**
1. `npm create convex@latest -t nextjs-shadcn` (initialize dashboard)
2. Define `convex/schema.ts` with all 5 tables
3. Build `nanobot/mc/bridge.py` (Python SDK integration)

