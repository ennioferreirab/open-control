# Service Architecture

This document describes the **runtime services**, their boundaries, communication protocols, and shared infrastructure. For naming contracts, see [`code_conventions/cross_service_naming.md`](code_conventions/cross_service_naming.md). For the database schema reference, see [`database_schema.md`](database_schema.md).

---

## Services Overview

The system runs as **three cooperating processes** plus external provider APIs:

```text
┌─────────────────────────────────────────────────────────────┐
│                      User's Machine                         │
│                                                             │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────┐  │
│  │  MC Gateway   │   │   Convex     │   │   Dashboard    │  │
│  │  (Python)     │──▶│   Local      │◀──│   (Next.js)    │  │
│  │              │   │   Backend    │   │               │  │
│  └──────┬───────┘   └──────────────┘   └────────────────┘  │
│         │                                                   │
│         │ subprocess / IPC                                   │
│         ▼                                                   │
│  ┌──────────────────────────────────────┐                   │
│  │  Agent Processes                      │                   │
│  │  (Claude Code, Codex)                 │                   │
│  └──────────────────────────────────────┘                   │
│                                                             │
│  ┌──────────────┐                                           │
│  │  Terminal     │  (optional, for remote terminal agents)   │
│  │  Bridge       │                                           │
│  └──────────────┘                                           │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
   External APIs (Anthropic, OpenRouter, OpenAI)
```

---

## 1. Convex Local Backend

| Property | Value |
|----------|-------|
| Process | `npx convex dev --local` |
| Port | **3210** (exclusive — only one instance allowed) |
| Protocol | WebSocket (Convex SDK wire protocol) |
| Schema | `dashboard/convex/schema.ts` (26 tables) |
| Functions | `dashboard/convex/*.ts` — queries, mutations, actions |
| Business logic | `dashboard/convex/lib/*.ts` — shared domain rules |

### Role

Convex is the **single database and real-time engine**. All persistent state lives here. It provides:

- ACID transactions within each mutation
- Optimistic concurrency control via `stateVersion` fields
- Idempotent mutations via `runtimeReceipts` table
- Distributed locking via `runtimeClaims` table
- Real-time subscriptions for the dashboard frontend

For the complete table listing with fields and indexes, see [`database_schema.md`](database_schema.md).

### Singleton Constraint

Only **one** Convex local backend instance can run at a time. If port 3210 is occupied:

```bash
# Kill existing instance
lsof -ti:3210 | xargs kill
# Then restart
npx convex dev --local
```

**Worktrees share the same backend.** Do not run `npx convex dev --local` from a worktree. Deploy schema changes by restarting the backend from the main tree.

---

## 2. MC Gateway (Python Backend)

| Property | Value |
|----------|-------|
| Entry point | `boot.py` → `mc.cli` → `mc.runtime.gateway` |
| Start command | `mc start` |
| Long-running | Yes — async event loop with subscriptions plus targeted polling |
| HTTP server | **No** — communicates with Convex via SDK only |

### Role

The Gateway is the **orchestration engine**. It is a monolithic async daemon that runs all coordination components within a single `run_gateway()` event loop. It does NOT serve HTTP.

### Boot Sequence

All initialization happens inside `run_gateway()`:

1. Connect to Convex (`ConvexBridge(deployment_url, admin_key)`)
2. `AgentSyncService` runs once:
   - Bootstrap system agents (`ensure_low_agent()`)
   - Sync agent registry from `~/.nanobot/agents/` YAML files
   - Sync builtin skills and workspace skills to Convex
   - Sync model tier mappings and embedding model config
   - Ensure default board exists
3. Start all async components (see Internal Components below)

### Internal Components

All components run as asyncio tasks within the gateway. There are no separate microservices.

#### Task Orchestrator (`mc/runtime/orchestrator.py`)

Thin coordinator that spawns four status-based workers:

| Worker | Subscribes to | Poll interval | Responsibility |
|--------|--------------|---------------|----------------|
| `InboxWorker` | `inbox` tasks | 3s | Auto-title via `low-agent`, routing |
| `PlanningWorker` | `planning` tasks | 5s | Plan generation via `orchestrator-agent` LLM |
| `KickoffResumeWorker` | `in_progress` tasks | 5s | Materialize steps, kickoff/resume |
| `ReviewWorker` | `review` tasks | 5s | Route review, handle approval/denial |

#### Task Executor (`mc/contexts/execution/executor.py`)

Subscribes to `in_progress` tasks. Runs agents via `ExecutionEngine`, syncs output files post-completion, handles crashes via `CrashRecovery`.

#### Chat Handler (`mc/contexts/conversation/chat_handler.py`)

Subscribes to pending direct-chat messages (not task-thread messages) via
`chats:listPending`. Routes useful non-remote-terminal messages to
`ExecutionEngine` for agent response and keeps the runtime state payload in
Convex synchronized with active/sleep transitions.

| State | Poll interval |
|-------|---------------|
| Active runtime payload | 5s (configurable `chat_active_poll_seconds`) |
| Sleep runtime payload | 60s (configurable `chat_sleep_poll_seconds`) |

#### Mention Watcher (`mc/contexts/conversation/mentions/watcher.py`)

Subscribes to a bounded Convex watcher feed of recent user messages and routes
detected `@agent` mentions through `ConversationService` for intent
classification. Deduplicates via in-memory `_seen_message_ids` set (max 5000)
and performs a one-shot gap fill with `messages:listRecentUserMessages` only
when a full bounded snapshot indicates a reconnect or burst may have skipped
older unseen messages.

| Setting | Value |
|---------|-------|
| Feed limit | 50 recent user messages |
| Gap fill | One-shot bounded `messages:listRecentUserMessages` query when bounded snapshot continuity is uncertain |

#### Ask-User Reply Watcher (`mc/contexts/conversation/ask_user/watcher.py`)

Watches task threads for user replies to pending `ask_user()` calls. Uses
registry change notifications plus one bounded
`messages:listRecentByTaskForAskUser` subscription per active ask task,
instead of re-querying full active threads on an interval.

| Setting | Value |
|---------|-------|
| Feed | `messages:listRecentByTaskForAskUser` subscription per active ask |
| Activation | `AskUserRegistry` change notifications |

#### Plan Negotiation Supervisor (`mc/contexts/planning/supervisor.py`)

Manages per-task plan negotiation loops. Lazily spawns a negotiation loop for each task in `planning` or `review` status. Cleans up loops when negotiation completes.

#### Timeout Checker (`mc/runtime/timeout_checker.py`)

Periodic detector for stalled tasks and timed-out reviews.

| Setting | Default | Purpose |
|---------|---------|---------|
| Check interval | 60s | How often to scan |
| Task timeout | 30 min | Mark `in_progress` tasks as stalled |
| Inter-agent timeout | 10 min | Escalate review tasks |

#### Cron Delivery (`mc/runtime/cron_delivery.py`)

Uses `CronService` from nanobot vendor. Loads jobs from `~/.nanobot/cron/jobs.json`. When a cron job fires, it either re-queues an existing task or creates a new one.

#### Sleep Controller (`mc/runtime/sleep_controller.py`)

Adaptive polling optimizer. Controls gateway-wide active/sleep modes.

| Mode | Poll interval | Trigger |
|------|---------------|---------|
| Active | 5s | Startup, work detected, manual |
| Sleep | 300s | Idle timeout (default 300s), manual |

Responds to manual control via Convex `settings:getGatewaySleepControl`. Persists state to `"gateway_sleep_runtime"` setting. Injected into all polling loops as a dependency.

#### Interactive Runtime (`mc/runtime/interactive.py`)

WebSocket server for live terminal sessions (PTY-backed).

| Property | Value |
|----------|-------|
| Port | 8765 |
| Protocol | WebSocket |
| Purpose | Dashboard live terminal, legacy interactive-tui execution |

#### Integration Outbound Worker (`mc/runtime/integrations/outbound_worker.py`)

Subscribes to enabled integration configs and maintains one bounded outbound
feed subscription per enabled config. Publishes mapped messages and status
activities to external platforms (e.g., Linear), with one-shot gap fill via
`integrations:getOutboundPending` when a bounded snapshot indicates overflow.

| Setting | Default | Purpose |
|---------|---------|---------|
| Feed limit | 50 items per config feed | Bound recent outbound snapshot size |
| Gap fill | `integrations:getOutboundPending` | Recover missed items after reconnect or burst |

**Startup behavior:** `IntegrationSyncService` runs at boot, loads all enabled integration configs from Convex, and creates adapter instances via `AdapterRegistry`. If no active integrations are found the worker is skipped entirely.

**Pipeline:** `OutboundPipeline` publishes prepared outbound payloads from the
subscription feeds, mapping them to external actions (comments, status
updates). Echo suppression prevents re-publishing MC-originated comments
(identified by `[MC]` prefix).

**Inbound path:** `InboundPipeline` (`mc/contexts/integrations/pipeline/inbound.py`) normalizes webhook payloads from external platforms into canonical `IntegrationEvent` objects and deduplicates via an in-memory idempotency key set.

#### Crash Recovery (`mc/contexts/execution/crash_recovery.py`)

Handles agent process crashes during task execution. Called by `TaskExecutor` when execution fails — not a background loop.

| Setting | Value |
|---------|-------|
| Max auto-retries | 1 per task |
| On first crash | Task → `retrying`, re-dispatch |
| On second crash | Task → `crashed`, stop |

#### On-Demand Processes (Not Background Loops)

These are invoked synchronously, not polled:

| Process | Trigger | Location |
|---------|---------|----------|
| Memory consolidation | After task completion, when HISTORY.md > 160K chars | `mc/memory/consolidation.py` |
| File sync | After CC task completion | `mc/bridge/repositories/tasks.py` (`sync_task_output_files`) |
| Agent sync | Gateway startup only | `mc/contexts/agents/sync.py` |
| Conversation routing | Called by watchers/handlers | `mc/contexts/conversation/service.py` |

### Convex Communication

All Convex access is centralized in `mc/bridge/`:

- `ConvexBridge` facade composes all repository classes
- Automatic `snake_case` ↔ `camelCase` key conversion
- Retry with exponential backoff (`MAX_RETRIES=3`, `BACKOFF_BASE_SECONDS=1`)
- Delays: 1s, 2s, 4s
- Idempotency keys for mutation safety

```python
bridge = ConvexBridge(deployment_url, admin_key)
await bridge.mutation("tasks:transition", {
    "task_id": task_id,
    "from_status": "assigned",
    "to_status": "in_progress",
})
```

### Agent Execution

The Gateway spawns agent processes and monitors their lifecycle:

| Runner Strategy | Backend | Mechanism |
|----------------|---------|-----------|
| `ClaudeCodeRunnerStrategy` | Claude Code | Subprocess with IPC socket |
| `ProviderCliRunnerStrategy` | Any CLI provider | Subprocess with stdout parsing |
| `InteractiveTuiRunnerStrategy` | tmux terminal | PTY attachment (legacy) |
| `HumanRunnerStrategy` | Human | No process — waits for user action |

All strategies that produce live events use `SessionActivityService` for lightweight session metadata plus file-backed Live transcripts — see Live Reporting below.

### Live Reporting (`SessionActivityService`)

All runner strategies use `SessionActivityService` (`mc/contexts/interactive/activity_service.py`) as the unified layer for communicating with the dashboard Live tab. This service writes lightweight discovery metadata to Convex and persists transcript bytes under `OPEN_CONTROL_LIVE_HOME` (default `<OPEN_CONTROL_HOME>/live-sessions`).

| Store | Write Path | Purpose |
|-------|------------|---------|
| `interactiveSessions` | `interactiveSessions:upsert` | Session lifecycle and lightweight discovery metadata |
| Live filesystem | `LiveSessionStore` | Streaming transcript events and session meta |

```text
┌─────────────────────┐  ┌──────────────┐
│  ProviderCliRunner   │  │  Future CLI  │
└────────┬────────────┘  └──────┬───────┘
         │                      │
         ▼                      ▼
    ┌─────────────────────────────────────────────────┐
    │         SessionActivityService                   │
    │  upsert_session()        — session lifecycle     │
    │  append_event()          — streaming events      │
    │  append_result()         — execution result      │
    │  append_parsed_cli_event() — CLI parser events   │
    └────────────────────┬────────────────────────────┘
                         │
                         ▼
            `interactiveSessions:upsert` + filesystem writes
```

**Key behaviors:**
- Still writes transcript files when `bridge=None`
- Swallows `interactiveSessions:upsert` bridge exceptions with `logger.debug` (non-fatal)
- Applies `safe_string_for_convex()` overflow protection on `raw_text` and `raw_json`
- Accepts `ts` override for CLI parser events (preserves parser timestamp)
- Provider-specific fields pass through `**extra` kwargs

**Adding a new runner:** instantiate `SessionActivityService(bridge)` and call its methods. No payload-building duplication needed.

### IPC Socket

The Gateway exposes a **Unix socket** for subprocess communication:

| Property | Value |
|----------|-------|
| Default path | `/tmp/mc-agent.sock` |
| Env var | `MC_SOCKET_PATH` |
| Protocol | JSON-RPC over Unix domain socket |
| Clients | MCP bridge, hooks, Claude Code subprocess |

Agent subprocesses use this socket to:
- Report step completion
- Post messages to task threads
- Query task/step state
- Sync artifacts

### MCP Bridge

The MCP bridge (`mc/runtime/mcp/bridge.py`) is launched as a **stdio subprocess** by agent processes. It translates MCP tool calls into Convex mutations via the IPC socket.

Environment variables passed to the subprocess:

```
MC_SOCKET_PATH     — IPC socket location
AGENT_NAME         — calling agent identity
TASK_ID            — current task context
STEP_ID            — current step context
CONVEX_URL         — fallback direct Convex access
CONVEX_ADMIN_KEY   — fallback authentication
```

---

## 3. Dashboard (Next.js Frontend)

| Property | Value |
|----------|-------|
| Framework | Next.js 16 (App Router) + React 19 |
| Start command | `npm run dev:frontend` |
| Port | 3000 (default) |
| Convex connection | `NEXT_PUBLIC_CONVEX_URL` (browser-side) |

### Role

The Dashboard is the **user interface**. It provides real-time views of tasks, agents, boards, and execution sessions. It connects directly to Convex for reactive data.

### Data Flow

```text
React Component
  → Feature Hook (useTaskDetailView, useAgentSidebarItemState, ...)
    → Convex useQuery / useMutation
      → Convex Local Backend (port 3210)
```

Components never call Convex directly — they go through feature hooks.

### API Routes (Next.js)

The dashboard provides REST endpoints for operations that need server-side logic:

| Route | Purpose |
|-------|---------|
| `POST /api/auth` | Token validation, session cookie |
| `POST /api/auth/logout` | Session cleanup |
| `POST /api/agents/create` | Create agent (writes YAML to filesystem) |
| `POST /api/agents/assist` | Agent authoring assistance |
| `GET/POST /api/agents/[name]/config` | Agent config read/write |
| `GET/POST /api/agents/[name]/memory/[file]` | Agent memory file ops |
| `GET/POST /api/tasks/[id]/files` | Task file upload/download |
| `POST /api/terminal/launch` | Launch terminal session (platform-specific) |
| `POST /api/authoring/agent-wizard` | Agent wizard (spawns Python subprocess) |
| `GET /api/specs/agent` | Agent specification schema |
| `GET /api/specs/squad` | Squad specification schema |
| `GET /api/specs/workflow/context` | Workflow authoring context (published squads + agents + existing workflows + review specs + models) |
| `POST /api/specs/workflow` | Publish a standalone workflow via `workflowSpecs:publishStandalone` |
| `GET/POST /api/cron` | Cron job listing/creation |
| `GET/POST/DELETE /api/cron/[jobId]` | Individual cron job management |
| `GET/POST /api/settings/*` | Global settings |
| `GET/POST /api/boards/[name]/artifacts` | Board artifact storage |
| `/api/channels/*` | Channel integrations |

### Workflow-First Creation Paradigm

**Conceptual model:**
- **Squad** — reusable agent roster defining team composition. Once published, a squad is stable and can be linked to many workflows.
- **Workflow** — execution plan that references a squad's agents (by name) to define step sequences. `workflowSpecs.squadSpecId` links every workflow to its parent squad.

**Two creation paths:**

| Path | Skill | Mutation | When to use |
|------|-------|----------|-------------|
| Squad-first | `/create-squad-mc` | `squadSpecs:publishGraph` | Creating a new team from scratch — creates squad + agents + default workflow atomically |
| Workflow-first | `/create-workflow-mc` | `workflowSpecs:publishStandalone` | Adding a new workflow to an existing published squad |

**Agent reuse emphasis:** When creating squads with `/create-squad-mc`, Phase 4 (Agent Design) enforces a mandatory Reuse Assessment. Existing agents are preferred over new ones — a match of 60%+ fit triggers a reuse recommendation. Creating 3+ new agents requires explicit user confirmation.

**Data flow for standalone workflow creation:**
1. `GET /api/specs/workflow/context` — fetch published squads with their agents and existing workflows
2. User selects a squad and designs steps using agent names (keys) from the roster
3. `POST /api/specs/workflow` — calls `workflowSpecs:publishStandalone`, which resolves agent names to `agentId`s and inserts a published `workflowSpecs` record linked to the squad

### Authentication

- Token stored in `mc_session` cookie (httpOnly, secure, sameSite=lax, 7-day expiry)
- Validated against `MC_ACCESS_TOKEN` environment variable
- If `MC_ACCESS_TOKEN` is not set, dashboard runs in convenience mode (no auth)

---

## 4. Terminal Bridge (Optional)

| Property | Value |
|----------|-------|
| Entry point | `terminal_bridge.py` |
| Transport | Polling-based (not WebSocket) |
| Purpose | Connect remote terminal agents to Convex |

### Architecture

```text
[Convex DB] ←→ [Terminal Bridge] ←→ [tmux/Claude]
```

Two daemon threads:
- **Input poll loop** — polls Convex for `pendingInput`
- **Screen monitor loop** — polls tmux screen, pushes changes to Convex

### Polling Intervals

| Constant | Value | Purpose |
|----------|-------|---------|
| `POLL_INTERVAL` | 0.1s | Local pane reads |
| `ACTIVE_POLL_INTERVAL` | 1.0s | Active Convex polling |
| `SLEEP_POLL_INTERVAL` | 30.0s | When sleeping |
| `AUTO_SLEEP_AFTER_SECONDS` | 300s | Auto-sleep after 5 min inactivity |

---

## 5. Vendor Services

### 5.1 Nanobot (`vendor/nanobot/`)

| Property | Value |
|----------|-------|
| Source | Git subtree from [HKUDS/nanobot](https://github.com/HKUDS/nanobot) |
| Policy | **READ-ONLY** — do not edit without explicit permission |

Nanobot provides infrastructure components that MC uses:

| Component | What MC uses |
|-----------|-------------|
| `SkillsLoader` | Load markdown-based skills |
| `load_config` | Read nanobot YAML/JSON configuration |
| Provider registry | `find_by_model`, `find_by_name` for LLM providers |
| `CronService` | Scheduled task service |
| Channel integrations | Telegram, Discord, Slack (not used by MC directly) |

### 5.2 Claude Code (`vendor/claude-code/`)

| Property | Value |
|----------|-------|
| Source | Custom integration code |
| Policy | Must follow project code conventions |

Provides Claude Code integration:
- IPC client for subprocess communication
- Session management types (`CCTaskResult`, `ClaudeCodeOpts`, `WorkspaceContext`)
- Model detection helpers (`is_cc_model()`, `extract_cc_model_name()`)

---

## 6. External API Integrations

### LLM Providers

| Provider | SDK | Usage |
|----------|-----|-------|
| Anthropic | `anthropic` | Primary LLM for planning, execution, memory consolidation |
| OpenRouter | HTTP client | Model federation (alternative providers) |
| OpenAI/Codex | `openai` + OAuth | Interactive session backend, Codex CLI |
| LiteLLM | `litellm` | Unified provider abstraction, embeddings |

Provider resolution: `mc/infrastructure/providers/factory.py` → `create_provider(model)` returns `(provider, resolved_model)`.

### Model Tier System

Models are referenced by tier rather than concrete model ID:

```
tier:standard-low    → cheap, fast tasks (auto-titling)
tier:standard-medium → default execution
tier:standard-high   → complex planning
tier:reasoning-low   → simple reasoning tasks
tier:reasoning-medium → moderate reasoning
tier:reasoning-high  → complex multi-step reasoning
```

Resolved by `TierResolver` → concrete model strings based on user configuration.

---

## 7. Communication Protocol Summary

| Source → Target | Protocol | Transport | Key File |
|----------------|----------|-----------|----------|
| MC Gateway → Convex | Convex SDK | WebSocket to `:3210` | `mc/bridge/client.py` |
| Dashboard → Convex | Convex JS Client | WebSocket to `:3210` | `dashboard/convex/` |
| Dashboard API → Filesystem | Direct I/O | Local FS | `dashboard/app/api/` |
| Dashboard → Interactive Runtime | WebSocket | WS to `:8765` | `mc/runtime/interactive.py` |
| Agent subprocess → MC Gateway | JSON-RPC | Unix socket | `mc/runtime/mcp/bridge.py` |
| Hooks → MC Gateway | JSON-RPC | Unix socket | `mc/hooks/ipc_sync.py` |
| Terminal Bridge → Convex | Convex SDK | WebSocket to `:3210` | `terminal_bridge.py` |
| Terminal Bridge → tmux | `subprocess` | Process control | `terminal_bridge.py` |
| MC Gateway → LLM APIs | Provider SDK | HTTPS | `mc/infrastructure/providers/` |
| MC Gateway → Agent process | `subprocess` | stdout/stdin | `mc/runtime/provider_cli/` |

---

## 8. Shared State & Contracts

### Workflow Specification

**Single source of truth:** `shared/workflow/workflow_spec.json`

Defines the state machines for tasks and steps. Implemented in two adapters:

| Layer | Adapter | Purpose |
|-------|---------|---------|
| Python | `mc/domain/workflow_contract.py` | Transition validation, event mapping |
| Convex/TS | `dashboard/convex/lib/workflowContract.ts` | Same rules, TypeScript side |

**Notable task transitions:**
- `done -> assigned`: thread message on a completed task re-opens it for the agent.
- `done -> in_progress`: resuming completed tasks for continued work (e.g. step retry cascade).
- `done -> review`: re-opens the review gate without re-running execution.

See `dashboard/convex/lib/taskLifecycle.ts` `TASK_TRANSITIONS` for the full map.

### Key Conversion

The bridge converts keys automatically between Python and Convex:

```
Python snake_case  ←→  Bridge  ←→  Convex camelCase
```

Status values are **never converted** — they are identical across all layers.

### Filesystem Shared Paths

| Path | Owner | Purpose |
|------|-------|---------|
| `~/.nanobot/agents/` | MC Gateway | Agent YAML definitions |
| `~/.nanobot/config.json` | Nanobot | Provider configuration |
| `~/.nanobot/cron/jobs.json` | CronService | Cron job definitions |
| `~/.nanobot/boards/{board}/artifacts/` | Dashboard API | Board artifact storage |
| `~/.nanobot/tasks/{id}/output/` | Agent processes | Task output files |
| `~/.nanobot/tasks/{id}/attachments/` | Dashboard API | User-uploaded files |
| `dashboard/.env.local` | Convex CLI | `CONVEX_URL`, `CONVEX_ADMIN_KEY` |

---

## 9. Environment Variables

### Convex Connection

| Variable | Used by | Purpose |
|----------|---------|---------|
| `CONVEX_URL` | MC Gateway | Convex deployment URL (override) |
| `NEXT_PUBLIC_CONVEX_URL` | Dashboard | Browser-side Convex URL |
| `CONVEX_ADMIN_KEY` | MC Gateway | Admin authentication |
| `CONVEX_DEPLOYMENT` | Convex CLI | Local deployment name |

### MC Runtime

| Variable | Default | Purpose |
|----------|---------|---------|
| `MC_SOCKET_PATH` | `/tmp/mc-agent.sock` | IPC socket for subprocess communication |
| `MC_LOG_LEVEL` | `INFO` | Root logger level |
| `MC_ACCESS_TOKEN` | (none) | Dashboard authentication token |
| `MC_EXECUTION_MODE` | `provider-cli` | Execution mode (`provider-cli` or `interactive-tui`) |

### Agent Execution Context

Set by MC Gateway when spawning agent subprocesses:

| Variable | Purpose |
|----------|---------|
| `AGENT_NAME` | Current agent identity |
| `TASK_ID` | Current task context |
| `STEP_ID` | Current step context |
| `MC_INTERACTIVE_SESSION_ID` | Interactive session identity |

### Provider API Keys

Dynamically resolved from nanobot config and injected into subprocess environments:

```
ANTHROPIC_API_KEY
OPENAI_API_KEY
BRAVE_API_KEY
<PROVIDER>_API_KEY  (determined by provider registry)
```

---

## 10. Task Execution Lifecycle

End-to-end flow showing how all services participate:

```text
1. User creates task (Dashboard → Convex mutation)
2. MC Gateway detects new task (InboxWorker polling)
3. InboxWorker auto-titles task (LLM call via low-agent)
4. PlanningWorker generates execution plan (LLM call via orchestrator-agent)
5. User approves plan (Dashboard → Convex mutation)
6. KickoffResumeWorker materializes steps (Convex batch mutations)
7. TaskExecutor picks up in_progress task
8. ExecutionEngine selects runner strategy per agent backend
9. MC Gateway spawns agent subprocess with IPC socket
10. Agent process executes:
    a. Reads task context via MCP bridge (IPC → Convex)
    b. Calls LLM API for reasoning
    c. Executes tools (filesystem, web, etc.)
    d. Reports step completion via MCP bridge (IPC → Convex)
11. MC Gateway detects step completion (polling)
12. StepDispatcher unblocks dependent steps
13. Steps 8–12 repeat for remaining steps
14. Post-execution: file sync, memory consolidation (if threshold exceeded)
15. ReviewWorker routes to reviewer if needed
16. Task marked done (Convex mutation)
17. Dashboard updates in real-time (Convex subscription)
```

On crash at step 10: CrashRecovery retries once, then marks task as `crashed`.

---

## 11. Concurrency & Reliability

### Optimistic Locking

Task and step records include a `stateVersion` field. Mutations require `expectedStateVersion` — if another process modified the record, the mutation returns `{ kind: "conflict" }` and the caller retries.

### Idempotency

The `runtimeReceipts` table stores responses indexed by `idempotencyKey`. On retry with the same key, the cached response is returned without re-executing the mutation.

### Distributed Locking

The `runtimeClaims` table provides lease-based locking with expiration. Used to coordinate multi-agent operations and prevent duplicate task pickup.

### Retry Logic

The Python bridge retries Convex mutations with exponential backoff:
- Max retries: 3
- Backoff base: 1 second
- Delays: 1s, 2s, 4s

---

## 12. Interactive Session Architecture

For live agent sessions where a human can observe or take over:

```text
MC Gateway
  → InteractiveSessionCoordinator.create_or_attach()
    → Select provider adapter (Claude Code / Codex)
      → Adapter.prepare_launch() → launch spec
        → TmuxSessionManager.ensure_session()
          → Agent runs in tmux with terminal I/O
            → Supervision events → update Convex
              → Dashboard connects via WebSocket (:8765)
                → Live terminal view
```

Control modes:
- **Agent** — agent has full control
- **Human** — user takes over via `requestHumanTakeover()`
- **Resume** — agent resumes via `resumeAgentControl()`
