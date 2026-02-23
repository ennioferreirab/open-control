---
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-02b-vision
  - step-02c-executive-summary
  - step-03-success
  - step-04-journeys
  - step-05-domain
  - step-06-innovation
  - step-07-project-type
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
classification:
  projectType: Orchestration Platform (Web App + Developer Tool + Workflow Engine)
  domain: AI Agent DevOps
  complexity: medium-high
  projectContext: brownfield
inputDocuments:
  - README.md
  - workspace/AGENTS.md
  - workspace/SOUL.md
  - workspace/TOOLS.md
  - workspace/USER.md
  - workspace/HEARTBEAT.md
  - nanobot/agent/loop.py
  - nanobot/agent/subagent.py
  - nanobot/agent/context.py
  - nanobot/agent/memory.py
  - nanobot/agent/skills.py
  - nanobot/agent/tools/spawn.py
  - nanobot/bus/queue.py
  - nanobot/bus/events.py
  - nanobot/config/schema.py
  - nanobot/heartbeat/service.py
workflowType: 'prd'
documentCounts:
  briefs: 0
  research: 0
  brainstorming: 0
  projectDocs: 16
---

# Product Requirements Document - nanobot-ennio

**Author:** Ennio
**Date:** 2026-02-22

## Executive Summary

nanobot Mission Control is a multi-agent orchestration platform that brings coordinated AI agent workflows to the nanobot ecosystem. Built on nanobot's ultra-lightweight foundation (~3,862 lines of core agent code), it enables users to deploy, coordinate, and supervise teams of specialized AI agents through a real-time web dashboard — delivering the same multi-agent power that community projects built for OpenClaw (430k+ lines), but with full code readability and minimal complexity.

The platform bridges nanobot's existing AsyncIO-based agent infrastructure with a Convex real-time backend and a Next.js + ShadCN UI dashboard, providing a visual Kanban board for task management, WebSocket-streamed agent activity, configurable inter-agent collaboration and review workflows, and human-in-the-loop approval gates for critical decisions.

Target users are nanobot operators who need to orchestrate multiple specialized agents — researchers, writers, analysts, developers — working on complex tasks that benefit from parallel execution, peer review, and human oversight.

### What Makes This Special

**Readable orchestration.** Every line of coordination code is understandable. Where OpenClaw Mission Control projects sit on top of a 430k-line codebase, nanobot Mission Control extends a system you can read end-to-end in an afternoon. No black boxes, no hidden complexity.

**Configurable trust.** Each task can be configured with its own trust level — from fully autonomous execution to mandatory human approval, with inter-agent review in between. Users decide per-task whether agents run free, review each other's work, or pause for human sign-off.

**First-mover in nanobot's ecosystem.** While OpenClaw has 5+ community-built dashboards, nanobot has zero multi-agent orchestration options. This fills a critical gap as nanobot adoption grows.

**Minimal tax.** The orchestration layer follows nanobot's philosophy: deliver maximum capability with minimum code. No bloated abstractions — just the primitives needed to coordinate agents effectively.

## Project Classification

- **Project Type:** Orchestration Platform (Web App + Developer Tool + Workflow Engine)
- **Domain:** AI Agent DevOps (multi-agent coordination & operations)
- **Complexity:** Medium-High — real-time state sync, inter-agent messaging, workflow state machines, HITL approval flows, dual-system bridging (AsyncIO ↔ Convex)
- **Project Context:** Brownfield — extending the existing nanobot framework
- **Tech Stack:** Next.js + Convex + ShadCN UI (dashboard), Python/AsyncIO (nanobot backend)

## Success Criteria

### User Success

- User creates a task, assigns agents, and watches them work on the Kanban board in real-time — no page refresh, no manual intervention needed
- Agents move from "Assigned" to "In Progress" within seconds of task creation
- When a task is configured with "needs review," the assigned agent pauses and the reviewing agent provides feedback — visible on the dashboard as a threaded discussion
- Human-in-the-loop approval gates work reliably: agent pauses, dashboard shows approval request, user clicks approve/deny, agent resumes or stops
- All four "wow" elements work simultaneously: real-time Kanban, HITL gates, inter-agent review, WebSocket streaming
- The "aha!" moment: user sees 3 agents collaborating on tasks autonomously while one reviews another's work — without touching anything after initial setup

### Business Success

- **3-month target:** Ennio uses Mission Control daily for real work, not just demos
- **6-month target:** Shipped as a separate open-source project with documentation good enough for the nanobot community to self-onboard
- **12-month target:** Community adoption — other nanobot users running their own Mission Control instances, contributing improvements
- Positioning as the reference Mission Control implementation for the nanobot ecosystem

### Technical Success

- Dashboard updates are real-time via Convex reactive queries — zero polling, zero page refresh
- Agent task pickup latency < 5 seconds from assignment to "In Progress"
- System runs reliably unattended — no crashes, no stuck agents, no orphaned tasks
- Inter-agent messaging is reliable — messages are delivered, never lost
- Orchestration layer maintains nanobot's code readability philosophy — clean, minimal, understandable

### Measurable Outcomes

- 3 agents running simultaneously without degradation
- 4+ tasks on the Kanban board managed concurrently
- Agent configuration via YAML files dropped into a folder — zero code required to add a new agent persona
- Single command startup: `nanobot mc start`

## User Journeys

### Journey 1: Ennio's Morning — The Daily Command Center

**Opening Scene:** It's 7:30 AM. Ennio opens his laptop and navigates to the Mission Control dashboard. Three agents are already listed on the sidebar: Financeiro (financial), Secretário (secretary), and Pesquisador (researcher). The Kanban board shows yesterday's completed tasks and two new items that agents picked up overnight via heartbeat.

**Rising Action:** Ennio sees a notification badge: Secretário has already connected to Gmail and Google Calendar, scanned the inbox, and prepared a daily briefing. The task "Daily Plan - Feb 23" is in the **Review** column — waiting for Ennio's approval. He clicks it and sees:

> "Bom dia, Ennio. Hoje você tem 3 reuniões: 10h standup, 14h client call, 16h code review. Há 4 emails que precisam de resposta — 2 urgentes. Sugiro começar pelos emails urgentes antes da standup. Bloco de foco disponível das 11h às 13h30."

Ennio approves the plan with one click. The task moves to **Done**.

Meanwhile, Financeiro has a task in **In Progress**: "Verificar boletos vencendo esta semana." Ennio watches the activity feed as the agent scans his financial data and surfaces 2 boletos due in 3 days, total R$1,847.00.

**Climax:** Ennio types a new task in the dashboard: "Research the latest trends in AI agent orchestration for a blog post." He doesn't assign a specific agent. The **Lead Agent** receives it, analyzes the task description, searches the available agents, and routes it to Pesquisador — who starts scanning YouTube channels, blog feeds, and LinkedIn posts. Ennio watches the task move from **Inbox → Assigned → In Progress** in seconds.

**Resolution:** By 9 AM, Ennio has his day planned, knows his financial obligations, and has a research task running in background. He didn't write a single prompt — just approved one plan and created one task. The dashboard shows 3 agents active, 5 tasks across the board. He closes the laptop and starts his day with clarity.

### Journey 2: The Lead Agent Delegates — Intelligent Routing

**Opening Scene:** A new task arrives: "Agendar pagamento do boleto da internet para amanhã." No agent is specified. The Lead Agent picks it up from **Inbox**.

**Rising Action:** The Lead Agent analyzes the task: keywords "boleto", "pagamento" → financial domain. It queries the registered agents and finds Financeiro with matching capabilities (financial management, boleto tracking). It delegates the task to Financeiro with context.

**Climax:** Financeiro picks up the task, processes it, and moves it to **Review** with a note: "Boleto NET R$189,90 agendado para 24/02. Confirma?" The dashboard shows the HITL approval gate — Ennio sees the notification, clicks **Approve**, and the task moves to **Done**.

**Edge Case:** A task arrives: "Translate this document to Japanese." The Lead Agent searches agents — none have translation capabilities. The Lead Agent executes the task itself using its general-purpose abilities, noting in the activity feed: "No specialist found. Executing directly."

**Resolution:** The Lead Agent acts as an intelligent router that makes the system feel effortless. Users don't need to know which agent does what — they just describe what they need.

### Journey 3: Inter-Agent Collaboration — Targeted Review Flow

**Opening Scene:** Ennio creates a task: "Prepare a weekly financial summary and include it in tomorrow's daily plan." He configures it at creation time with:

```yaml
assigned_to: financeiro
review:
  enabled: true
  reviewers: [secretario]
  require_human_approval: true
```

Only the agents specified in `reviewers` participate in the review — no broadcast.

**Rising Action:** Financeiro picks up the task and generates the weekly summary: income, expenses, pending boletos, cash flow projection. The task moves to **Review**. It goes specifically to Secretário — the configured reviewer — not to all agents.

**Climax:** Secretário reviews the financial summary and provides feedback via an inter-agent message (visible on the dashboard as a threaded discussion):

> Secretário → Financeiro: "O resumo está bom, mas falta incluir o pagamento recorrente do Spotify que vence dia 25. Também sugiro adicionar um alerta sobre o saldo projetado ficando abaixo de R$2.000."

Financeiro updates the summary and moves it back to **Review**. Secretário approves. Since `require_human_approval: true`, the task now moves to Ennio for final human sign-off.

**Resolution:** Ennio sees a polished financial summary that was already peer-reviewed by the specific agent he chose. He approves it in one click. Secretário automatically incorporates it into tomorrow's daily briefing. The review chain was explicit, predictable, and configured at task creation.

### Journey 4: Community User — First-Time Setup

**Opening Scene:** A nanobot user named Lucas discovers nanobot Mission Control on GitHub. He's been using nanobot with Telegram for a month and wants multi-agent capabilities.

**Rising Action:** Lucas clones the repo, reads the README. He runs `nanobot mission-control start` — the dashboard opens at `localhost:3000`. The Kanban board is empty. A welcome screen says: "Create your first agent."

Lucas drops a YAML file into `~/.nanobot/agents/`:

```yaml
name: dev-agent
role: Senior Python Developer
skills: [code-review, debugging, testing]
prompt: "You are a senior Python developer. Focus on clean, tested code."
```

The dashboard auto-detects the new agent and shows it in the sidebar. Lucas creates his first task from the dashboard: "Write unit tests for my auth module." The agent picks it up. Lucas watches it work in real-time.

**Climax:** It works. The agent writes tests, the activity feed shows each tool call, and the task moves across the board. Lucas adds two more agents — a researcher and a code reviewer — and sets up his first inter-agent review workflow. All via YAML files, no code changes.

**Resolution:** Lucas is running his own Mission Control in 15 minutes. No OpenClaw. No 430k lines. Just nanobot + a few YAML files + one command.

### Journey Requirements Summary

| Journey | Capabilities Revealed |
|---------|----------------------|
| **Morning Command Center** | Dashboard with Kanban, agent sidebar, activity feed, HITL approval (one-click), task creation from UI, overnight heartbeat tasks |
| **Lead Agent Delegates** | Intelligent agent matching/routing, agent capability registry, fallback to self-execution, real-time task state transitions |
| **Inter-Agent Review** | Per-task reviewer assignment at creation time, targeted review routing (not broadcast), inter-agent messaging with threaded discussions, configurable review chain (agent reviewers + optional human gate) |
| **Community Setup** | YAML-based agent creation, auto-detection of new agents, single command startup, welcome/onboarding screen, zero-code configuration |

## Domain-Specific Requirements

### Reliability & State Management

- **Crash recovery:** Retrying (1x auto) → Crashed (red flag + error log + manual "Retry from Beginning" button). No silent failures.
- **Task completion integrity:** Done status only set on explicit agent confirmation. Lost contact → task stays in current state until timeout.
- **Configurable timeouts:** `taskTimeout` (In Progress stall detection) and `interAgentTimeout` (review response escalation). Global defaults in dashboard settings, overridable per-task.

### Task Distribution & Race Condition Prevention

**Lead Agent as Single Distributor:**
- The Lead Agent is the sole task router — no agent self-claims tasks
- On receiving a batch of tasks (or a complex multi-step task), the Lead Agent creates an **execution plan** upfront
- The plan identifies:
  - **Blocking tasks** — must complete before dependents start
  - **Parallelizable tasks** — can run simultaneously on different agents
  - **Review chains** — which agent reviews which output

**Lead Agent Planning Table (in Soul/System Prompt):**

The Lead Agent's system prompt includes a structured planning template:

```
## Task Execution Plan

| # | Task | Assigned To | Depends On | Parallel | Reviewer | Status |
|---|------|-------------|------------|----------|----------|--------|
| 1 | Research market data | pesquisador | - | Yes (with #2) | - | pending |
| 2 | Scan boletos this week | financeiro | - | Yes (with #1) | - | pending |
| 3 | Build daily briefing | secretario | #1, #2 | No (blocked) | - | blocked |
| 4 | Final daily plan | secretario | #3 | No (blocked) | financeiro | blocked |
```

- Lead Agent updates this table as tasks complete, auto-unblocking dependents
- Parallelizable tasks are dispatched simultaneously
- Blocked tasks wait until all dependencies resolve

### Data Privacy

- All data flows through Convex (cloud) for real-time sync — acceptable for current scope
- **README.md notice:** Document that sensitive data (financial, email, calendar) transits through Convex; users handling highly sensitive data should evaluate their risk tolerance
- Future consideration: local-only mode for sensitive agent outputs (post-MVP)

## Innovation & Novel Patterns

### Detected Innovation Areas

**1. Readable Orchestration — The Anti-Complexity Play**
Where OpenClaw community projects (ClawDeck, ClawControl, Clawe, crshdn/mission-control) all build their Mission Control on top of a 430k+ line codebase, nanobot Mission Control extends a system of ~3,862 lines. Every line of orchestration code is understandable. This isn't just a marketing angle — it's a fundamental architectural decision that makes the system debuggable, auditable, and contributable by solo developers and small teams.

**2. Lead Agent Planning — Structured Task Distribution**
The Lead Agent acts as a single intelligent router with upfront execution planning. Instead of agents self-claiming tasks (race conditions) or round-robin distribution (no intelligence), the Lead Agent analyzes incoming tasks, matches them against agent capabilities, creates dependency-aware execution plans (blocking vs. parallelizable), and dispatches accordingly. If no specialist is found, it executes the task itself. This eliminates race conditions by design and provides visible, predictable task routing.

**3. Configurable Trust Spectrum — Per-Task Trust Levels**
Each task is configured at creation time with its own trust level: fully autonomous (agent runs and completes), agent-reviewed (specific configured reviewers provide feedback before completion), or human-approved (HITL gate requiring explicit user sign-off). This per-task granularity — rather than system-wide trust settings — lets users run low-risk tasks autonomously while maintaining human oversight on critical decisions, all within the same workflow.

### Market Context & Competitive Landscape

- **OpenClaw ecosystem:** 5+ community-built Mission Control dashboards exist, all sitting on 430k+ lines of framework code. None offer the readability proposition.
- **nanobot ecosystem:** Zero multi-agent orchestration options exist today. This is the first-mover opportunity as nanobot adoption grows.
- **General AI orchestration:** Tools like CrewAI, AutoGen, and LangGraph offer multi-agent coordination but require significant setup and Python expertise. nanobot Mission Control targets a simpler, YAML-configured, visual-first approach.
- **Unique positioning:** The only orchestration platform where you can read the entire coordination layer in an afternoon and understand every decision the system makes.

### Validation Approach

- **Phase 1 — Dogfooding:** Ennio uses Mission Control daily for real work (financial tracking, daily planning, research) for 3 months. If it replaces manual workflows, the core value is validated.
- **Phase 2 — Community Beta:** Ship as open-source. If a nanobot user (like Lucas in Journey 4) can set up and run Mission Control in under 15 minutes with just YAML files, the simplicity proposition is validated.
- **Phase 3 — Feature Validation:** Track which features (HITL gates, inter-agent review, Lead Agent routing) are actually used vs. configured. Remove unused complexity.

## Orchestration Platform Specific Requirements

### Project-Type Overview

nanobot Mission Control is a hybrid Orchestration Platform combining three dimensions: a **real-time web dashboard** (SPA), a **developer tool** (CLI + YAML configuration), and a **workflow engine** (task state machine + agent coordination). The platform is a purely authenticated, localhost/private-deployment application with no SEO requirements. Real-time performance optimization is deferred to post-MVP and documented as a README improvement point.

### Technical Architecture Considerations

**Dashboard (SPA):**
- Single Page Application architecture — fits naturally with Convex's reactive query model
- No SEO requirements — purely authenticated app (localhost or private deployment)
- Real-time performance benchmarks deferred to post-MVP (documented in README as improvement area)
- Navigation structure: dashboard-first with views for Kanban board, agent management, settings, and activity feed

**State Machine — Task Lifecycle:**
- Linear state flow: **Inbox → Assigned → In Progress → Review → Done**
- Error states: **Retrying** (automatic single retry) → **Crashed** (red flag, manual retry)
- **No backward transitions** — Review is a terminal working state before Done. If the reviewer requests changes, the task stays in Review while the assigned agent addresses feedback. This keeps the state machine simple and predictable.
- Stalled state: triggered by configurable timeout (global default, per-task override)

**Lead Agent Execution Plan — Dashboard Visibility:**
- The Lead Agent's execution plan (task dependency table with blocking/parallel/review assignments) is **visible on the dashboard**
- Accessible via click-to-expand on any task that was routed by the Lead Agent
- Shows task dependencies, parallelization decisions, assigned agents, and current status of each sub-task
- Updates in real-time as tasks complete and dependents unblock

**Inter-Agent Communication — Threaded on Task:**
- All inter-agent messages are stored **as part of the task** in a threaded conversation format
- Visible on the dashboard as a discussion thread within the task detail view
- Includes: reviewer feedback, agent responses, revision notes, approval/denial records
- No separate communication log — everything is task-scoped for clarity

### CLI Interface

**Subcommand Structure:**
- `nanobot mc start` — Launch Mission Control (dashboard + agent gateway)
- `nanobot mc stop` — Graceful shutdown
- `nanobot mc agents list` — List registered agents and their status
- `nanobot mc agents create` — Interactive or flag-based agent creation (generates YAML)
- `nanobot mc tasks list` — List current tasks and their states
- `nanobot mc tasks create` — Create a task from CLI
- `nanobot mc status` — Show system overview (agents running, task counts, health)

**Agent-Assisted CLI:**
- The nanobot agent itself can help create agents and workflows via natural language — e.g., "create a financial agent that tracks boletos" generates the YAML configuration
- CLI serves as both a direct interface and an entry point for agent-assisted operations

### Configuration & Validation

**YAML Agent Configuration:**
- Agent YAML files are validated on load with **clear, actionable error messages**
- Invalid configurations produce explicit errors: field name, expected type/value, line number
- The system refuses to start an agent with invalid config — no silent degradation
- Validation covers: required fields (name, role, prompt), valid skill references, reviewer references pointing to existing agents

**Auto-Generated Documentation:**
- API documentation auto-generated from Convex schema and function definitions
- Built-in help accessible via `nanobot mc help` and `nanobot mc [command] --help`
- Dashboard includes contextual help tooltips for configuration options

### Performance & Scalability (README Improvement Points)

Documented in README as post-MVP optimization targets:
- Dashboard load time benchmarks
- Maximum concurrent dashboard viewers
- Agent message throughput under load
- Convex query performance with large task histories
- WebSocket connection stability over extended sessions

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Experience MVP — deliver the full "aha!" moment (3 agents collaborating on a Kanban board with HITL and inter-agent review) for a single power user (Ennio), then expand to community.

**Resource Requirements:** Solo developer (Ennio) building on existing nanobot infrastructure. The brownfield advantage — SubagentManager, MessageBus, HeartbeatService, and SkillsLoader already exist. New work is the orchestration layer, Convex integration, and dashboard.

### MVP Feature Set (Phase 1)

**Core User Journeys Supported:**
- Journey 1: Morning Command Center (Kanban + HITL approval + activity feed)
- Journey 2: Lead Agent Routing (intelligent delegation + fallback self-execution)
- Journey 3: Inter-Agent Review (targeted reviewer flow + threaded messages)

**Must-Have Capabilities:**

| Category | Feature | Rationale |
|----------|---------|-----------|
| Dashboard | Real-time Kanban board (Inbox → Assigned → In Progress → Review → Done) | Core visual interface — the product IS the board |
| Dashboard | Agent sidebar with status indicators | Must see who's running |
| Dashboard | Activity feed with real-time streaming | Visibility into agent actions |
| Dashboard | HITL approval UI (approve/deny buttons) | Critical trust mechanism |
| Dashboard | Task detail view with threaded inter-agent messages | Review flow visibility |
| Dashboard | Lead Agent execution plan (click-to-expand) | Transparency into task routing decisions |
| Dashboard | Global settings panel (timeouts, defaults) | Configuration without YAML editing |
| Backend | Convex real-time state (tasks, agents, activities, messages) | Source of truth for all shared state |
| Backend | AsyncIO ↔ Convex bridge | Connects nanobot agents to dashboard |
| Orchestration | Lead Agent with capability matching + execution planning | Intelligent task distribution |
| Orchestration | Task state machine (linear flow + Retrying/Crashed error states) | Reliable task lifecycle |
| Orchestration | Inter-agent messaging (targeted to configured reviewers) | Collaboration without broadcast |
| Orchestration | Configurable trust per-task (autonomous / reviewed / human-approved) | Flexible oversight |
| Orchestration | Crash recovery (1x auto-retry → Crashed with error + manual retry) | Reliability |
| Orchestration | Configurable timeouts (task + inter-agent, global defaults) | Prevent stuck states |
| Config | YAML-based agent definitions with clear validation errors | Zero-code agent creation |
| Config | LLM model configurable per agent, with system-wide default | Agents can use different models (e.g., fast model for secretary, powerful model for research) |
| CLI | `nanobot mc start/stop` | Single-command startup/shutdown |
| CLI | `nanobot mc agents list/create` | Agent management from terminal |
| CLI | `nanobot mc tasks list/create` | Task management from terminal |
| CLI | `nanobot mc status` | System health overview |
| CLI | Agent-assisted CLI (natural language → YAML generation) | nanobot helps configure itself |
| Docs | Auto-generated API docs from Convex schema | Developer reference |
| Docs | Built-in `--help` for all CLI commands | Discoverability |

**MVP Capacity:** 3 simultaneous agents, 4+ concurrent tasks.

### Post-MVP Features

**Phase 2 — Growth (Community Ready):**
- Journey 4: Community Setup (welcome screen, 15-minute onboarding, auto-detection of new agents)
- Dashboard setup wizard for visual agent/task creation
- Agent performance metrics and cost tracking (tokens used, time per task)
- Task templates with default agent assignments and review rules
- Task dependencies that auto-unblock when prerequisites complete
- Mobile-responsive dashboard
- Notification system (browser push, Telegram, email) for approval requests
- Performance benchmarks and optimization (load time, throughput, connection stability)

**Phase 3 — Expansion (Ecosystem):**
- Agent marketplace — share and import agent personas
- Multi-user support with roles and permissions
- Pipeline orchestration — visual workflow builder for multi-step agent chains
- Analytics dashboard — agent productivity, task completion rates, bottleneck identification
- Integration with nanobot's existing channels (Telegram, Discord, Slack) for approval flows
- Self-improving agents — agents that learn from review feedback

### Risk Mitigation Strategy

**Technical Risks (all HIGH priority):**

| Risk | Impact | Mitigation |
|------|--------|------------|
| AsyncIO ↔ Convex bridge reliability | Data loss, sync failures, stale dashboard | Convex as single source of truth. One-directional flow: nanobot writes → Convex stores → dashboard reads. Retry logic on writes. Health check endpoint. |
| Lead Agent intelligence quality | Bad routing, wrong agent assignments, poor execution plans | Capability matching via explicit skill tags in YAML (not fuzzy NLP). Fallback to self-execution. Users can always override with direct assignment. |
| Real-time Kanban performance | Laggy updates, missed state transitions | Convex reactive queries handle this natively. Optimistic UI updates on dashboard side. Degrade gracefully (show spinner, not stale data). |
| Lead Agent becomes a bottleneck | Single point of failure for task distribution | Users can always assign tasks directly to specific agents, bypassing the Lead Agent. The Lead Agent is an optimizer, not a gatekeeper. |
| Configurable trust too complex | Users avoid configuring trust, reducing product value | Sensible defaults (autonomous for most tasks, HITL for financial actions). Users only configure when they want to. |
| nanobot architecture insufficient | Orchestration exceeds lightweight framework capacity | Existing SubagentManager and MessageBus provide core primitives. Mission Control extends these, not replaces them. |

**Market Risks:**
- Dogfooding first. If Ennio doesn't use it daily for 3 months, the product needs rethinking before community launch.

## Functional Requirements

### Task Management

- **FR1:** User can create a new task from the dashboard with a title and optional description
- **FR2:** User can assign a task to a specific agent at creation time, or leave it unassigned for Lead Agent routing
- **FR3:** User can configure per-task trust level at creation time (autonomous / agent-reviewed / human-approved)
- **FR4:** User can configure specific reviewer agents for a task at creation time
- **FR5:** User can view all tasks on a real-time Kanban board organized by state (Inbox → Assigned → In Progress → Review → Done)
- **FR6:** User can view task details including description, assigned agent, status, and threaded inter-agent messages
- **FR7:** User can view the Lead Agent's execution plan for any routed task via click-to-expand
- **FR8:** User can create a task from the CLI (`nanobot mc tasks create`)
- **FR9:** User can list all tasks and their states from the CLI (`nanobot mc tasks list`)

### Agent Management

- **FR10:** User can register a new agent by dropping a YAML definition file into the agents folder
- **FR11:** User can define agent name, role, skills, system prompt, and LLM model in the YAML configuration
- **FR12:** User can set a system-wide default LLM model that applies to all agents unless overridden per-agent
- **FR13:** System validates agent YAML configurations on load and surfaces clear, actionable error messages for invalid configs
- **FR14:** System refuses to start an agent with invalid configuration — no silent degradation
- **FR15:** User can view all registered agents and their current status (active, idle, crashed) on the dashboard sidebar
- **FR16:** User can list registered agents and their status from the CLI (`nanobot mc agents list`)
- **FR17:** User can create a new agent configuration from the CLI (`nanobot mc agents create`)
- **FR18:** User can create agent configurations via natural language through the nanobot agent itself (agent-assisted CLI)

### Task Orchestration

- **FR19:** Lead Agent can receive unassigned tasks and route them to the most appropriate agent based on capability matching against agent skill tags
- **FR20:** Lead Agent can execute a task directly when no specialist agent matches the required capabilities
- **FR21:** Lead Agent can create an execution plan for complex or batch tasks, identifying blocking dependencies, parallelizable tasks, and review chains
- **FR22:** Lead Agent can dispatch parallelizable tasks simultaneously to different agents
- **FR23:** Lead Agent can auto-unblock dependent tasks when their prerequisites complete
- **FR24:** System transitions tasks through the state machine: Inbox → Assigned → In Progress → Review → Done
- **FR25:** System sets task status to "Done" only when the assigned agent explicitly confirms completion

### Inter-Agent Collaboration

- **FR26:** Agents can send messages to other agents within the context of a task (threaded on the task)
- **FR27:** When a task is configured with reviewers, the system routes the completed work to the specified reviewer agents only — no broadcast
- **FR28:** Reviewing agent can provide feedback on a task, visible as a threaded discussion on the dashboard
- **FR29:** Assigned agent can address reviewer feedback while the task remains in Review state
- **FR30:** Reviewing agent can approve a task, advancing it to the next stage (human approval if configured, or Done)

### Human Oversight

- **FR31:** User can approve or deny a task that requires human approval via dashboard buttons
- **FR32:** When user approves a task, the agent resumes or the task moves to Done
- **FR33:** When user denies a task, the agent receives the denial and the task remains actionable
- **FR34:** Dashboard displays a notification indicator when tasks require human attention (approval requests)
- **FR35:** User can view a real-time activity feed showing agent actions as they happen
- **FR36:** User can trigger a manual "Retry from Beginning" for crashed tasks from the dashboard

### Reliability & Error Handling

- **FR37:** System automatically retries a task once when an agent crashes mid-execution (status: Retrying)
- **FR38:** If retry also fails, system sets task status to Crashed with a red flag indicator and full error log
- **FR39:** System flags tasks as stalled when they exceed the configured task timeout
- **FR40:** System escalates inter-agent review requests that exceed the configured inter-agent timeout

### System Configuration

- **FR41:** User can configure global default timeouts (task timeout, inter-agent timeout) from the dashboard settings panel
- **FR42:** User can override global timeout defaults per-task at creation time
- **FR43:** User can configure the system-wide default LLM model from settings
- **FR44:** User can view system health overview from the CLI (`nanobot mc status`)

### System Lifecycle

- **FR45:** User can start the entire Mission Control system (dashboard + agent gateway) with a single command (`nanobot mc start`)
- **FR46:** User can stop Mission Control gracefully (`nanobot mc stop`)
- **FR47:** System provides auto-generated API documentation from Convex schema
- **FR48:** System provides built-in help for all CLI commands (`--help`)

## Non-Functional Requirements

### Performance

- **NFR1:** Dashboard Kanban board updates reflect agent state changes within 2 seconds of occurrence
- **NFR2:** Agent task pickup latency < 5 seconds from assignment to "In Progress" status
- **NFR3:** Activity feed streams agent actions with < 3 seconds delay from execution
- **NFR4:** Dashboard initial load completes within 5 seconds on localhost
- **NFR5:** CLI commands (`mc status`, `mc agents list`, `mc tasks list`) return results within 2 seconds
- **NFR6:** `nanobot mc start` launches the full system (dashboard + agent gateway) within 15 seconds

### Reliability

- **NFR7:** System runs unattended for 24+ hours with 3 agents actively processing tasks without crashes, stuck agents, or orphaned tasks
- **NFR8:** Every task state transition is explicitly visible on the Kanban board — no silent failures
- **NFR9:** 100% of inter-agent messages sent are received and visible in the task thread within 10 seconds — no message loss
- **NFR10:** Agent crash recovery (auto-retry) completes within 30 seconds of crash detection
- **NFR11:** System handles simultaneous operation of 3 agents and 4+ concurrent tasks without degradation
- **NFR12:** Concurrent agent updates to the same task never result in lost writes (Convex transactional integrity)
- **NFR13:** Dashboard detects Convex connection loss and displays a disconnection indicator — never shows stale data as current
- **NFR14:** Graceful shutdown (`nanobot mc stop`) completes within 30 seconds, preserving all task state in Convex

### Integration

- **NFR15:** AsyncIO ↔ Convex bridge retries failed writes up to 3 times with exponential backoff; surfaces error on activity feed only after retry exhaustion
- **NFR16:** No component other than the nanobot backend writes to Convex; dashboard is read-only plus user actions via Convex mutations
- **NFR17:** Agent YAML configuration changes are detected on next CLI command (`mc agents list`) or dashboard refresh — no file watcher required for MVP
- **NFR18:** CLI and dashboard operate on the same Convex state — actions in one are immediately reflected in the other

### Security

- **NFR19:** Dashboard requires authentication via configurable access token for localhost deployment
- **NFR20:** Data privacy notice documented in README regarding sensitive data (financial, email, calendar) transiting through Convex cloud

### Code Quality

- **NFR21:** No single orchestration module exceeds 500 lines — maintaining nanobot's readability philosophy
- **NFR22:** YAML validation errors include field name, expected type/value, and actionable fix suggestion
- **NFR23:** All agent and task state transitions are logged to both the activity feed (Convex) and local stdout for debugging
