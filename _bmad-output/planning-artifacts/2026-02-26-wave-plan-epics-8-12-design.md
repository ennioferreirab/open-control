# Wave Plan: Epics 8-12 Implementation

**Date:** 2026-02-26
**Approach:** Fundacao Larga (dependency-driven, 3 waves, parallel execution)

## Context

Epics 1-7 (core MVP) are complete. Epics 8-12 contain 12 stories, all "ready-for-dev", covering UI/UX quick wins, task enhancements, agent communication, model tiers, and board/tag CRM features.

## Dependency Map

```
9-3 Edit Tags ──────────────────────► 12-2 Tags CRM
10-1 @Mentions ─────────────────────► 10-2 Direct Chat
11-1 Model Tiers ───────────────────► 11-2 Model Override
8-1, 8-2, 9-1, 9-2, 10-3, 12-1 ──► (no dependents)
```

## Wave 1 — Fundacao + Quick Wins

**Objective:** Unblock all dependencies and deliver visible quick wins.

**6 stories, all independent — run in parallel:**

| Story | Type | Size | Unblocks | Parallel Group |
|-------|------|------|----------|----------------|
| **8-1** Reduce TaskInput Layout Shift | FE | Small | - | A (FE pure) |
| **8-2** Cron Schedule Table | FE | Small | - | A (FE pure) |
| **9-1** Favorite Tasks | Full-stack | Small | - | B (Full-stack light) |
| **9-3** Edit Tags After Creation | Full-stack | Small | 12-2 | B (Full-stack light) |
| **10-1** @Mentions in Thread | FE | Medium | 10-2 | A (FE pure) |
| **11-1** Model Tier System | Full-stack | Medium | 11-2 | C (Infra) |

**Parallel groups (if limiting concurrency):**
- **Group A** (FE pure): 8-1, 8-2, 10-1 — no backend changes
- **Group B** (Full-stack light): 9-1, 9-3 — minimal schema changes, isolated areas
- **Group C** (Infra): 11-1 — touches types.py, executor.py, gateway.py

**Conflict risk:** Low. Code areas don't overlap significantly. Only attention point: `schema.ts` (9-1 and 9-3 both add fields, but in different areas).

**Completion criteria:** All 6 stories merged and functional.

## Wave 2 — Unlocked Features

**Objective:** Implement features unblocked by Wave 1, plus independent medium-complexity features.

**5 stories — mix of dependent and independent:**

| Story | Type | Size | Depends on | Parallel Group |
|-------|------|------|------------|----------------|
| **9-2** Thread Comments (no trigger) | Full-stack | Medium | - | D (Thread) |
| **10-2** Direct Chat with Agent | Full-stack | Large | 10-1 (W1) | E (Agent Comms) |
| **10-3** Agent-to-Agent Sync | Backend | Medium | - | E (Agent Comms) |
| **11-2** Model Override Per Agent | FE | Small | 11-1 (W1) | F (Models) |
| **12-1** Board Agent Memory Mode | Full-stack | Medium | - | F (Board) |

**Parallel groups:**
- **Group D** (Thread): 9-2 — touches ThreadInput, ThreadMessage, schema
- **Group E** (Agent Comms): 10-2 (FE+backend), 10-3 (backend pure) — don't conflict (10-2 creates ChatPanel, 10-3 creates ask_agent tool)
- **Group F** (Models/Board): 11-2 (FE, AgentConfigSheet), 12-1 (full-stack, BoardSettingsSheet + board_utils.py)

**Conflict risk:** Medium.
- 10-2 and 9-2 both touch `schema.ts` and messaging — but 9-2 adds "comment" type to messages, 10-2 creates separate "chats" table
- 10-2 and 10-3 both touch `executor.py` — recommend doing 10-3 first or merging carefully

**Completion criteria:** All 5 stories merged. 11 of 12 stories complete.

## Wave 3 — Tags CRM

**Objective:** Deliver the most complex feature with dedicated attention.

**1 story:**

| Story | Type | Size | Depends on |
|-------|------|------|------------|
| **12-2** Tags with Custom Attributes (lightweight CRM) | Full-stack | Large | 9-3 (W1) |

**Why isolated:**
- Most complex story in backlog — custom attribute system per tag (text/number/date/select), shared catalog, cascade operations, inline editors
- Touches schema.ts (2 new tables), creates new Convex modules, injects tag attributes into Python thread context
- Deserves dedicated wave for testing and UX tuning

**Completion criteria:** Story merged, tags function as mini-CRM. All 12 stories complete — Epics 8-12 closed.

## Visual Summary

```
Wave 1 (Foundation)        Wave 2 (Unlocked)            Wave 3 (CRM)
┌─────────────────────┐    ┌──────────────────────┐    ┌──────────────┐
│ 8-1  Layout Shift   │    │ 9-2  Comments        │    │ 12-2 Tags    │
│ 8-2  Cron Table     │    │ 10-2 Direct Chat  *  │    │      CRM  *  │
│ 9-1  Favorites      │    │ 10-3 Agent<>Agent    │    └──────────────┘
│ 9-3  Edit Tags    > │    │ 11-2 Model Override> │
│ 10-1 @Mentions    > │    │ 12-1 Memory Mode     │
│ 11-1 Model Tiers  > │    └──────────────────────┘
└─────────────────────┘
  > = unblocks feature in next wave
  * = large feature
```

## Story Count Summary

| Wave | Stories | Small | Medium | Large | Total |
|------|---------|-------|--------|-------|-------|
| Wave 1 | 6 | 4 | 2 | 0 | 6 |
| Wave 2 | 5 | 1 | 2 | 1 | 4+1 |
| Wave 3 | 1 | 0 | 0 | 1 | 1 |
| **Total** | **12** | **5** | **4** | **2** | **12** |
