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
  projectType: Orchestration Platform (Web App + Workflow Engine)
  domain: AI Agent DevOps
  complexity: medium-high
  projectContext: brownfield
inputDocuments:
  - _bmad-output/planning-artifacts/prd-backup-2026-02-24.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/epics.md
  - _bmad-output/implementation-artifacts/4-1-implement-lead-agent-capability-matching.md
  - _bmad-output/implementation-artifacts/4-2-implement-execution-planning.md
  - _bmad-output/implementation-artifacts/4-3-build-execution-plan-visualization.md
  - _bmad-output/implementation-artifacts/4-4-add-agent-assignment-to-task-input.md
  - _bmad-output/implementation-artifacts/4-5-llm-based-lead-agent-planning.md
  - _bmad-output/implementation-artifacts/5-2-implement-inter-agent-messaging.md
  - _bmad-output/implementation-artifacts/9-13-lead-agent-file-aware-routing.md
  - _bmad-output/implementation-artifacts/8-9-agent-memory-history-viewer.md
  - nanobot/agent/memory.py
  - nanobot/mc/executor.py
  - nanobot/skills/memory/SKILL.md
workflowType: 'prd'
documentCounts:
  briefs: 0
  research: 0
  brainstorming: 0
  projectDocs: 14
---

# Product Requirements Document - nanobot-ennio

**Author:** Ennio
**Date:** 2026-02-24

## Executive Summary

nanobot-ennio's Lead Agent evolves from a hybrid planner/executor into a **pure orchestrator** — a project manager that plans, delegates, and coordinates multi-agent work but never executes tasks itself. The system introduces a **Task/Step hierarchy** where a Task represents the user's goal and Steps (etapas) are the units of work assigned to specialist agents, displayed as cards on the Kanban board. All agents working on a Task share a **unified thread** — the single communication channel where agents post structured completion messages containing file paths, diffs for modified files, and descriptions for created files, giving dependent agents the context they need to continue.

The user controls how much oversight they want. In **autonomous mode**, the Lead Agent creates an execution plan and dispatches immediately. In **supervised (hybrid) mode**, the Lead Agent presents the plan in a pre-kickoff modal where the user can reassign agents, reorder steps, change blocking dependencies, attach documents to specific steps, and negotiate the plan with the Lead Agent via thread chat — before anything executes. The **General Agent** is a system-level fallback that handles any work not matching a specialist, ensuring the Lead Agent never needs to self-execute.

### What Makes This Special

The pre-kickoff planning workspace is the differentiator. No other agent orchestration tool lets you see the full execution plan — agents, steps, dependencies, timeline — and then sit down with the AI planner to shape it collaboratively before kick-off, while also offering the option to let it run fully autonomous. It's collaborative project management with AI: the user is the PM, the Lead Agent is the planning partner, and the specialist agents are the team.

## Project Classification

- **Project Type:** Orchestration Platform (Web App + Workflow Engine)
- **Domain:** AI Agent DevOps
- **Complexity:** Medium-High — multi-agent coordination with dependency management, unified thread context, dual supervision modes, and real-time plan visualization
- **Project Context:** Brownfield — extends the existing nanobot-ennio platform. The Lead Agent (planner.py, orchestrator.py), execution plan visualization (ExecutionPlanTab), inter-agent messaging, and file-aware routing already exist and will be refactored to support the new pure-orchestrator model.

## Success Criteria

### User Success

- User submits a goal and receives a structured execution plan showing steps, assigned agents, dependencies, and parallel groups — within seconds
- In hybrid mode, the user opens the pre-kickoff modal and can reassign agents, reorder steps, toggle blocking dependencies, attach documents to specific steps, and chat with the Lead Agent to negotiate changes — all before anything executes
- In autonomous mode, the plan dispatches immediately without user intervention
- The user watches agents collaborate in the unified thread — each agent posts structured completion messages with file paths, diffs for modified files, and descriptions for created files
- Dependent agents pick up seamlessly — the thread gives them full context of what previous agents did
- The final output arrives without the user needing to micromanage intermediate steps

### Business Success

- Single-user productivity tool — success is measured by the user's confidence in delegating complex, multi-step work to agents without babysitting
- The Lead Agent reduces the user's cognitive load: describe the goal once, review the plan (or don't), get the result
- Agents become a reliable team, not a collection of isolated tools

### Technical Success

- Lead Agent never executes tasks — pure orchestrator invariant, no exceptions
- General Agent is always present as a system agent — planning never fails due to missing fallback
- Parallel steps run in truly parallel Python subprocesses — no serialization, no agent contention
- Thread messages follow structured format: file paths + diffs (modified) + file descriptions (created)
- Step completion triggers automatic unblocking of dependent steps
- Planning failures surface as backend errors on the task — no silent failures
- Agent completion messages are posted to the unified task thread, not per-step threads

### Measurable Outcomes

- Lead Agent produces a valid execution plan for 100% of submitted tasks (single-step or multi-step)
- Plan generation completes in < 10 seconds
- Step-to-step context handoff via thread is sufficient for the dependent agent to continue without asking for clarification
- Pre-kickoff modal renders the full plan with editable fields within 2 seconds of opening
- Agent structured completion messages contain all file paths and diffs — no missing context

## User Journeys

### Journey 1: The Autonomous Delegator

**Ennio, founder and solo operator, has a complex goal but no time to micromanage.**

It's Monday morning. Ennio needs a financial report compiled from February invoices, cross-referenced with his bank statements, formatted as a PDF, and sent to his accountant. He opens the dashboard, types: "Compile February financial report from invoices and bank statements, generate PDF summary, email to accountant."

He hits Create. The Lead Agent picks it up instantly — within seconds, the Kanban board shows a plan: Step 1 (financial agent: extract invoice data), Step 2 (financial agent: reconcile with bank statements), Step 3 (general agent: generate PDF report), Step 4 (secretary agent: email to accountant). Steps 1 and 2 run in parallel. Step 3 blocks on both. Step 4 blocks on Step 3.

Ennio glances at the plan, sees it makes sense, and moves on to other work. Over the next few minutes, cards move across the board. The unified thread fills with structured completion messages — the financial agent posts: "Created `/output/invoice-summary.csv` (47 line items extracted)" and "Modified `/output/reconciliation.xlsx` — diff: +12 matched transactions, 3 flagged discrepancies." The general agent picks up, sees the thread context, generates the PDF. The secretary agent sends the email.

Ennio comes back 15 minutes later. The task is done. He opens the thread, skims the conversation, downloads the PDF. No micromanagement needed.

**Requirements revealed:** Autonomous plan dispatch, parallel step execution, structured completion messages in thread, end-to-end goal completion without user intervention, file output tracking.

### Journey 2: The Collaborative Planner

**Ennio has a nuanced goal that needs his input before execution.**

Ennio wants to restructure his agent workspace — reorganize config files, update prompts, and test each agent afterward. This is sensitive work. He types the goal and selects "Supervised" mode.

The Lead Agent generates a plan and the pre-kickoff modal opens. Ennio sees 6 steps laid out: 3 agents involved, 2 parallel groups, 1 blocking dependency chain. He notices the Lead Agent assigned the config reorganization to the general agent — but Ennio knows his dev agent is better for file operations. He clicks the agent dropdown on Step 2 and reassigns it.

He also notices Steps 4 and 5 are marked as parallel, but he wants them sequential — Step 5 should only run after Step 4 confirms all tests pass. He drags the dependency line. He attaches his `workspace-structure.md` document to Step 1 so the agent has context.

Then he opens the thread chat in the modal and types: "Add a final step — the general agent should write a summary of all changes made." The Lead Agent acknowledges, adds Step 7 to the plan, assigns it to the general agent, blocks it on all previous steps.

Ennio reviews the updated plan, clicks "Kick-off." Steps start executing.

**Requirements revealed:** Pre-kickoff modal with editable plan, agent reassignment, dependency editing, document attachment per step, thread chat with Lead Agent during planning, dynamic plan modification before dispatch.

### Journey 3: The Observer

**Ennio checks in on a running multi-agent task.**

Ennio submitted a goal 10 minutes ago. He opens the task from the Kanban board and clicks into the unified thread. He sees the conversation:

> **financial-agent** (Step 1 - completed): Extracted 47 invoices from `/attachments/invoices-feb.zip`. Created `/output/invoice-data.json`. Files created: `invoice-data.json` (structured JSON, 47 entries with date, vendor, amount, category).

> **general-agent** (Step 2 - completed): Reconciled invoice data with bank statement. Modified `/output/invoice-data.json` — diff: +`matched` field on 44/47 entries, 3 entries flagged as `unmatched`. Created `/output/reconciliation-report.md` (summary table of matched/unmatched transactions).

> **financial-agent** (Step 3 - in progress): Generating PDF summary report...

Ennio sees exactly what each agent did, which files were created or modified, and what the diffs look like. He can click on file paths to open them in the viewer. The thread is the single source of truth — no need to dig through individual agent logs.

He notices 3 unmatched transactions in the reconciliation. He posts a message in the thread: "The 3 unmatched items are from a vendor name change — Acme Corp is now Acme Inc. Please re-reconcile." The financial agent on Step 3 will see this in the thread context.

**Requirements revealed:** Unified thread with structured agent messages, file path links in thread, real-time thread updates, user can post to thread mid-execution, agents read full thread context including user messages.

### Journey 4: The Firefighter

**A step fails and Ennio needs to recover.**

Ennio's 4-step task is running. Steps 1 and 2 completed. Step 3 crashes — the agent hit a provider error (OAuth token expired). The Kanban card for Step 3 turns red with a "crashed" badge. An activity event appears in the feed: "Agent dev-agent crashed on Step 3: AnthropicOAuthExpired. Action: Run `nanobot provider login`."

Step 4, which depends on Step 3, stays blocked — its card shows a lock icon.

Ennio sees the error in the thread:

> **System** (Step 3 - crashed): Provider error: AnthropicOAuthExpired. Action: Run `nanobot provider login --provider anthropic`

He fixes the OAuth token from his terminal. He clicks the "Retry" button on Step 3's card. The step re-enters "assigned" status, the agent picks it up again, and this time it completes. Step 4 automatically unblocks and starts executing.

**Requirements revealed:** Step-level error reporting with actionable messages, crashed step visualization, blocked step indicators, manual retry per step, automatic unblocking on retry success, error details in unified thread.

### Journey Requirements Summary

| Capability Area | J1 | J2 | J3 | J4 |
|---|---|---|---|---|
| Autonomous plan dispatch | X | | | |
| Pre-kickoff modal | | X | | |
| Plan editing (agents, deps, docs) | | X | | |
| Thread chat with Lead Agent | | X | | |
| Unified thread per task | X | X | X | X |
| Structured completion messages | X | | X | |
| File path links in thread | | | X | |
| User messages in thread | | | X | |
| Step-level error handling | | | | X |
| Manual step retry | | | | X |
| Automatic dependency unblocking | X | | | X |
| Parallel step execution | X | X | | |
| Real-time Kanban updates | X | X | X | X |

## Domain-Specific Requirements

### Context Window Management

The unified thread is the single source of truth for all agent collaboration. As tasks grow in complexity (many steps, many agents), threads accumulate significant content — structured completion messages with file paths, diffs, and descriptions compound quickly.

- **Existing pattern:** `_build_thread_context()` in `executor.py` truncates to the last 20 messages, prepends `"(N earlier messages omitted)"`, and separates the latest user message into a `[Latest Follow-up]` section
- Thread context injected into each agent's prompt must fit within the LLM context window alongside the agent's system prompt, task description, and file attachments
- Structured completion messages (diffs, file paths) are denser than conversational messages — 20 messages of diffs may consume more tokens than 20 messages of chat
- Dependent agents need the *relevant* prior context, not necessarily *all* prior context — selective injection matters more than raw message count

### LLM Provider Reliability

- Agents depend on external LLM providers that can fail mid-execution (OAuth expiry, rate limits, outages)
- Step-level error handling must surface actionable recovery messages
- Provider errors must not cascade — a crashed step blocks dependents but doesn't crash the entire task

### Agent Isolation & Parallelism

- Parallel steps run as separate Python subprocesses — no shared state, no agent contention
- Each agent gets its own workspace under `~/.nanobot/agents/{agentName}/`
- Memory consolidation (`end_task_session()`) happens only after the agent completes its step — mid-execution memory is not shared
- Thread is the ONLY inter-agent communication channel during execution

### Cost Awareness

- Each agent invocation consumes LLM tokens — planning + N agent executions per task
- Thread context injection multiplies cost: every dependent agent re-reads the thread
- No hard ceiling, but the system should avoid unnecessary token waste (e.g., don't inject full diffs when file paths suffice for certain step types)

## Innovation & Novel Patterns

### Detected Innovation Areas

1. **Pre-Kickoff Collaborative Planning** — Existing agent orchestration tools either run fully autonomous or require the user to hardcode the plan in code. nanobot-ennio lets the user *negotiate* the plan with the AI planner in a visual modal — reassigning agents, reordering steps, changing dependencies, attaching documents — before anything executes. The AI planner is a collaborative partner, not a black box.

2. **Dual Supervision Model** — The same system supports both autonomous dispatch (plan then execute) and supervised dispatch (plan then review then negotiate then kick-off). The user picks the level of control per task. Most tools are either fully autonomous or fully manual.

3. **Pure Orchestrator + General Agent Fallback** — The Lead Agent never self-executes. Combined with the General Agent as a system-level fallback, planning never fails due to missing capabilities. This is an architectural invariant.

4. **Unified Thread as Single Source of Truth** — All agents on a task share one thread with structured completion messages (file paths + diffs + descriptions). This replaces per-agent logs or opaque internal state with a transparent, human-readable conversation that both agents and users can follow.

### Market Context & Competitive Landscape

- **OpenClaw** — The open-source agent framework that powers the system
- **OpenClaw Mission Control** — The orchestration dashboard where the Lead Agent, Kanban board, unified threads, and pre-kickoff modal live
- The innovation exists within the OpenClaw ecosystem: evolving Mission Control from individual agent execution into a collaborative multi-agent orchestration platform with visual plan negotiation
- The pre-kickoff modal and dual supervision model are the differentiators within the OpenClaw Mission Control experience

### Validation Approach

- The pre-kickoff modal must prove its value: does editing the plan before execution actually improve outcomes compared to pure autonomous mode?
- Measurable: compare task completion rate and quality between autonomous and supervised runs
- User confidence metric: does the user trust the system more when they can review and shape the plan?

## Orchestration Platform Specific Requirements

### Project-Type Overview

nanobot-ennio is a **single-user orchestration platform** combining:
- **Next.js + Convex dashboard** — Real-time reactive UI (Kanban board, threads, execution plan visualization)
- **Python workflow engine** — Agent lifecycle, LLM-based planning, subprocess-based parallel execution
- **AsyncIO-Convex bridge** — The glue between the Python backend and Convex real-time database

This is NOT a SaaS product. It's a personal productivity tool where one user orchestrates multiple AI agents through a visual interface.

### Technical Architecture

- **Real-time reactivity**: Convex provides reactive queries — Kanban cards, thread messages, and step statuses update live without polling
- **Process model**: Each agent runs as a separate Python subprocess. Parallel steps use `asyncio.gather()` for true concurrency
- **State management**: Convex is the single source of truth. The Python backend reads/writes via the bridge. No local state persistence beyond agent workspaces (`~/.nanobot/agents/`)
- **Communication flow**: User -> Dashboard -> Convex -> Bridge -> Python Engine -> Agent Subprocess -> Convex -> Dashboard

### Implementation Considerations

- **No authentication layer**: Single-user tool, runs locally
- **No SEO**: Dashboard is a local app, not a public website
- **No multi-tenancy**: Single user, single instance
- **Offline mode**: Not required — agents need LLM providers which require internet
- **Browser support**: Modern browsers only (Chrome/Safari), no legacy support needed

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Problem-solving MVP — the minimum that makes the Lead Agent useful as a pure orchestrator for multi-agent work.
**Resource:** Single developer, brownfield codebase with existing planner, orchestrator, and execution plan visualization.

### MVP Feature Set (Phase 1)

**Core User Journeys Supported:** All four — Autonomous Delegator, Collaborative Planner, Observer, Firefighter.

**Must-Have Capabilities:**
- Lead Agent as pure orchestrator (never executes)
- General Agent as system fallback agent
- Task/Step hierarchy: Task = goal, Steps = etapas on Kanban board
- LLM-based execution planning with agent assignment, dependencies, parallel groups
- Unified thread per task shared by all agents
- Structured agent completion messages (file paths + diffs + descriptions)
- Autonomous mode: plan and dispatch immediately
- Supervised (hybrid) mode: pre-kickoff modal with plan review/editing
- Modal capabilities: reassign agents, reorder steps, change dependencies, attach documents, chat with Lead Agent
- Automatic unblocking of dependent steps on completion
- Step-level error reporting and manual retry
- Parallel step execution via asyncio.gather()

### Post-MVP Features

**Phase 2 (Growth):**
- Plan templates: save and reuse execution plan patterns for recurring goals
- Agent performance analytics: track which agents succeed on which types of steps
- Plan versioning: compare before/after when the user edits a plan in the modal
- Multi-task orchestration: Lead Agent manages dependencies across tasks

**Phase 3 (Vision):**
- Lead Agent learns from past plans to improve future planning quality
- Proactive suggestions: Lead Agent proposes tasks based on patterns it observes
- Cross-board orchestration: Lead Agent coordinates agents across multiple boards

### Risk Mitigation Strategy

- **Technical risk:** LLM planning quality — mitigated by General Agent fallback and structured plan format that constrains LLM output
- **UX risk:** Pre-kickoff modal complexity — mitigated by making supervised mode optional (autonomous is always available)
- **Resource risk:** Single developer — mitigated by brownfield approach (existing codebase with planner, orchestrator, execution plan viz already built)

## Functional Requirements

### Task & Step Management

- **FR1:** User can create a task by describing a goal in natural language
- **FR2:** System decomposes a task into one or more steps (etapas), each representing a unit of work for a specialist agent
- **FR3:** Steps are displayed as individual cards on the Kanban board, grouped under their parent task
- **FR4:** User can select supervision mode (autonomous or supervised) when creating a task
- **FR5:** User can attach files to a task at creation time

### Execution Planning

- **FR6:** Lead Agent generates an execution plan for every submitted task, including single-step tasks
- **FR7:** Execution plan specifies: steps, assigned agents, blocking dependencies, and parallel groups
- **FR8:** Lead Agent assigns agents to steps based on capability matching and task context
- **FR9:** Lead Agent considers attached file metadata (types, sizes, names) when routing steps to agents
- **FR10:** General Agent is always available as a system-level fallback agent for any step not matching a specialist

### Pre-Kickoff Plan Review (Supervised Mode)

- **FR11:** In supervised mode, system presents a pre-kickoff modal showing the full execution plan before any step executes
- **FR12:** User can reassign agents to any step in the pre-kickoff modal
- **FR13:** User can reorder steps in the pre-kickoff modal
- **FR14:** User can change blocking dependencies between steps in the pre-kickoff modal
- **FR15:** User can attach documents to specific steps in the pre-kickoff modal
- **FR16:** User can chat with the Lead Agent in the pre-kickoff modal to negotiate plan changes
- **FR17:** Lead Agent can dynamically modify the plan in response to user chat requests (add/remove/change steps)
- **FR18:** User can approve the plan and trigger kick-off from the pre-kickoff modal

### Agent Orchestration & Dispatch

- **FR19:** Lead Agent never executes tasks directly — it only plans, delegates, and coordinates
- **FR20:** In autonomous mode, the plan dispatches immediately after generation without user intervention
- **FR21:** Parallel steps launch simultaneously as separate processes
- **FR22:** Sequential steps execute in dependency order, each waiting for its blockers to complete
- **FR23:** Step completion automatically unblocks dependent steps

### Unified Thread & Agent Communication

- **FR24:** Each task has a single unified thread shared by all agents and the user
- **FR25:** Agents post structured completion messages to the thread containing: file paths, diffs for modified files, and descriptions for created files
- **FR26:** User can post messages to the thread during task execution
- **FR27:** Agents read the full thread context (including user messages and prior agent completions) when starting their step
- **FR28:** Thread context is managed to fit within LLM context windows (truncation with omission note for long threads)

### Step Lifecycle & Error Handling

- **FR29:** Steps progress through a defined lifecycle: assigned -> running -> completed (or crashed)
- **FR30:** Blocked steps display a visual indicator showing which steps they depend on
- **FR31:** When a step crashes, the system posts an error message to the thread with actionable recovery instructions
- **FR32:** A crashed step does not crash sibling or parent steps — only blocks dependents
- **FR33:** User can manually retry a crashed step, re-entering the execution pipeline
- **FR34:** Successful retry of a crashed step automatically unblocks its dependents

### Dashboard & Visualization

- **FR35:** Kanban board displays step cards with real-time status updates (assigned, running, completed, crashed, blocked)
- **FR36:** Execution plan visualization shows steps, dependencies, parallel groups, and assigned agents
- **FR37:** Thread view shows structured agent messages with file path references in real-time
- **FR38:** Activity feed shows step completion and error events

## Non-Functional Requirements

### Performance

- **NFR1:** Plan generation completes in < 10 seconds from task submission
- **NFR2:** Pre-kickoff modal renders the full plan with editable fields within 2 seconds of opening
- **NFR3:** Kanban board reflects step status changes within 1 second of the event (Convex reactive query)
- **NFR4:** Thread messages from agents appear in the UI within 1 second of being posted to Convex
- **NFR5:** Thread context injection for agents truncates to last 20 messages to stay within LLM context window limits

### Reliability

- **NFR6:** A crashed agent step does not affect other running or pending steps — only blocks its direct dependents
- **NFR7:** The system recovers gracefully from LLM provider errors (OAuth expiry, rate limits, timeouts) with actionable error messages
- **NFR8:** Agent subprocesses run in isolation — a crash in one subprocess does not bring down the Python engine or other subprocesses
- **NFR9:** Dependency unblocking is atomic — a step is unblocked only after all its blockers report completion
- **NFR10:** Planning failures surface as backend errors on the task with clear error messages — no silent failures

### Integration

- **NFR11:** The AsyncIO-Convex bridge maintains a persistent connection and reconnects automatically on disconnection
- **NFR12:** LLM provider calls include timeout handling and retry logic for transient errors
- **NFR13:** Structured completion messages follow a consistent format parseable by both the UI (for rendering) and agents (for context injection)
