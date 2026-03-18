# Story 4.1: Implement Lead Agent Capability Matching

Status: done

## Story

As a **user**,
I want unassigned tasks to be automatically routed to the most appropriate agent,
So that I can delegate by intent without knowing which agent handles what.

## Acceptance Criteria

1. **Given** a task is created with no assigned agent (status "inbox"), **When** the Lead Agent picks up the task, **Then** the Lead Agent analyzes the task description and matches it against registered agent skill tags
2. **Given** the Lead Agent evaluates agent skills, **Then** the best-matching agent is selected based on skill tag overlap with task keywords extracted from the title and description
3. **Given** a matching agent is found, **Then** the task transitions from "inbox" to "assigned" with the selected agent's name, and a `task_assigned` activity event is created: "Lead Agent assigned '{task title}' to {agent name}"
4. **Given** no registered agent has matching skills for the task, **When** the Lead Agent evaluates routing, **Then** the Lead Agent assigns the task to itself for direct execution (FR20), and a `task_assigned` activity event is created: "No specialist found. Lead Agent executing directly."
5. **Given** a task is created with an explicitly assigned agent (FR2), **When** the task enters the system, **Then** the Lead Agent does NOT re-route it -- the explicit assignment is respected, and the task transitions directly from "inbox" to "assigned"
6. **Given** the Lead Agent receives a task, **Then** agent pickup latency is less than 5 seconds from task creation to "assigned" status (NFR2)
7. **Given** 3 agents and 4+ concurrent tasks exist, **Then** the system handles routing without degradation (NFR11)
8. **And** the routing logic is implemented in `nanobot/mc/orchestrator.py`
9. **And** the module does not exceed 500 lines (NFR21)
10. **And** unit tests exist in `nanobot/mc/test_orchestrator.py`

## Tasks / Subtasks

- [ ] Task 1: Create the `orchestrator.py` module with `TaskOrchestrator` class (AC: #8, #9)
  - [ ] 1.1: Create `nanobot/mc/orchestrator.py` with module docstring and imports
  - [ ] 1.2: Define `TaskOrchestrator` class with `__init__` accepting a `ConvexBridge` instance
  - [ ] 1.3: Implement `_extract_keywords(title: str, description: str | None) -> list[str]` — tokenize task text into lowercase keywords, strip common stopwords
  - [ ] 1.4: Implement `_score_agent(agent: AgentData, keywords: list[str]) -> float` — compute a match score by counting skill tag overlaps with task keywords
  - [ ] 1.5: Ensure module stays under 500 lines

- [ ] Task 2: Implement the inbox subscription and routing loop (AC: #1, #3, #4, #5, #6)
  - [ ] 2.1: Implement `start_routing_loop()` async method that subscribes to `tasks:listByStatus` (status="inbox") via the bridge
  - [ ] 2.2: For each inbox task, check if `assignedAgent` is already set — if so, transition directly to "assigned" (AC #5)
  - [ ] 2.3: If no agent assigned, call `_route_task(task)` which fetches all agents, scores them, and selects the best match
  - [ ] 2.4: If best match score > 0, assign to that agent via `bridge.update_task_status(task_id, "assigned", agent_name=best_agent.name)`
  - [ ] 2.5: If no match found (all scores = 0), assign to "lead-agent" as fallback self-execution (FR20)
  - [ ] 2.6: Create appropriate `task_assigned` activity event via `bridge.create_activity()`
  - [ ] 2.7: Ensure routing completes within 5 seconds of task creation (NFR2)

- [ ] Task 3: Add `listByStatus` query to Convex tasks (AC: #1)
  - [ ] 3.1: Add a `listByStatus` query to `dashboard/convex/tasks.ts` that filters tasks by the `by_status` index
  - [ ] 3.2: This query is used by the bridge subscription to watch for inbox tasks

- [ ] Task 4: Integrate orchestrator into the gateway (AC: #7)
  - [ ] 4.1: Update `nanobot/mc/gateway.py` to instantiate `TaskOrchestrator` and start its routing loop
  - [ ] 4.2: Ensure the orchestrator runs as an asyncio task alongside the gateway main loop
  - [ ] 4.3: Handle graceful shutdown — cancel the routing loop on gateway stop

- [ ] Task 5: Write unit tests (AC: #10)
  - [ ] 5.1: Create `nanobot/mc/test_orchestrator.py`
  - [ ] 5.2: Test keyword extraction from task title and description
  - [ ] 5.3: Test agent scoring — agent with matching skills scores higher
  - [ ] 5.4: Test routing selects the highest-scoring agent
  - [ ] 5.5: Test fallback to lead-agent when no skills match
  - [ ] 5.6: Test explicit assignment is respected (no re-routing)
  - [ ] 5.7: Test concurrent routing of multiple tasks

## Dev Notes

### Critical Architecture Requirements

- **`orchestrator.py` is the Lead Agent's brain**: This module implements FR19 (capability matching), FR20 (fallback self-execution), and FR25 (explicit completion only). It does NOT implement execution planning (Story 4.2) — that's a separate concern.
- **Bridge is the only Convex interface**: The orchestrator MUST use `ConvexBridge` methods exclusively. No direct Convex SDK imports.
- **Snake_case in Python**: All Python code uses snake_case. The bridge handles camelCase conversion at the boundary.
- **Activity events are mandatory**: Every routing decision MUST write a corresponding activity event. This is an architectural invariant (architecture.md: "Every Convex mutation that modifies task state MUST also write a corresponding activity event").

### Keyword Extraction Pattern

Simple keyword matching is sufficient for MVP. The orchestrator extracts keywords from the task title and description, then compares against agent skill tags.

```python
import re
from nanobot.mc.types import AgentData, TaskData

STOPWORDS = {"a", "an", "the", "is", "are", "was", "were", "be", "been",
             "to", "of", "in", "for", "on", "with", "at", "by", "from",
             "and", "or", "but", "not", "this", "that", "it", "my", "your"}

def _extract_keywords(title: str, description: str | None = None) -> list[str]:
    """Extract meaningful keywords from task text."""
    text = title.lower()
    if description:
        text += " " + description.lower()
    # Split on non-alphanumeric characters
    tokens = re.split(r"[^a-z0-9]+", text)
    # Filter stopwords and short tokens
    return [t for t in tokens if t and len(t) > 2 and t not in STOPWORDS]
```

### Agent Scoring Pattern

```python
def _score_agent(agent: AgentData, keywords: list[str]) -> float:
    """Score an agent based on skill tag overlap with task keywords."""
    if not agent.skills:
        return 0.0
    agent_skills_lower = {s.lower() for s in agent.skills}
    matches = sum(1 for kw in keywords if kw in agent_skills_lower)
    # Also check partial matches (keyword contained in skill or vice versa)
    for kw in keywords:
        for skill in agent_skills_lower:
            if kw in skill or skill in kw:
                matches += 0.5
    return matches
```

### Routing Loop Pattern

The orchestrator subscribes to inbox tasks and processes them. The bridge's `subscribe()` method yields updates whenever the query result changes.

```python
class TaskOrchestrator:
    def __init__(self, bridge: ConvexBridge):
        self._bridge = bridge
        self._lead_agent_name = "lead-agent"

    async def start_routing_loop(self) -> None:
        """Subscribe to inbox tasks and route them."""
        for tasks in self._bridge.subscribe("tasks:listByStatus", {"status": "inbox"}):
            for task_data in tasks:
                task = TaskData(**task_data)  # or dict access
                await self._process_inbox_task(task)

    async def _process_inbox_task(self, task: TaskData) -> None:
        """Route a single inbox task to the best agent."""
        if task.assigned_agent:
            # Explicit assignment — respect it, just transition
            self._bridge.update_task_status(
                task.id, "assigned", agent_name=task.assigned_agent
            )
            return

        # Fetch all agents
        agents_data = self._bridge.query("agents:list")
        agents = [AgentData(**a) for a in agents_data]

        # Score agents
        keywords = _extract_keywords(task.title, task.description)
        scored = [(agent, _score_agent(agent, keywords)) for agent in agents]
        scored.sort(key=lambda x: x[1], reverse=True)

        if scored and scored[0][1] > 0:
            best_agent = scored[0][0]
            self._bridge.update_task_status(
                task.id, "assigned", agent_name=best_agent.name,
                description=f"Lead Agent assigned '{task.title}' to {best_agent.name}",
            )
        else:
            # Fallback: Lead Agent executes directly
            self._bridge.update_task_status(
                task.id, "assigned", agent_name=self._lead_agent_name,
                description="No specialist found. Lead Agent executing directly.",
            )
```

### Convex Query Addition

Add a `listByStatus` query to `dashboard/convex/tasks.ts`:

```typescript
export const listByStatus = query({
  args: { status: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("tasks")
      .withIndex("by_status", (q) => q.eq("status", args.status))
      .collect();
  },
});
```

### Common LLM Developer Mistakes to Avoid

1. **DO NOT import the `convex` Python SDK directly** — The orchestrator must use `ConvexBridge` methods only. The bridge is the sole Convex integration point (Boundary 1 from architecture.md).

2. **DO NOT use async Convex calls** — The current `ConvexBridge` uses the synchronous `ConvexClient`. If the routing loop needs to be async, use `asyncio.to_thread()` to wrap synchronous bridge calls.

3. **DO NOT route tasks that already have an assigned agent** — FR2 requires explicit assignment to be respected. Check `task.assigned_agent` before routing.

4. **DO NOT forget activity events** — Every routing decision must write an activity event. This is a hard architectural invariant.

5. **DO NOT use fuzzy NLP for matching** — Simple keyword-to-skill-tag matching is sufficient for MVP. No LLM calls for routing decisions.

6. **DO NOT exceed 500 lines** — NFR21 requires all orchestration modules to stay under 500 lines.

7. **DO NOT block the gateway event loop** — If using synchronous bridge calls in an async context, wrap with `asyncio.to_thread()`.

8. **DO NOT make the routing loop poll** — Use `bridge.subscribe()` to reactively receive inbox tasks. No `time.sleep()` polling.

### What This Story Does NOT Include

- **Execution planning** — Complex task decomposition into sub-steps with dependencies is Story 4.2
- **Parallel dispatch** — Dispatching parallelizable tasks simultaneously is Story 4.2
- **Agent assignment UI** — The TaskInput agent selector is Story 4.4
- **Execution plan visualization** — Dashboard display of plans is Story 4.3
- **Agent execution** — Actually running agent work is not part of this story; this only routes/assigns

### Files Created in This Story

| File | Purpose |
|------|---------|
| `nanobot/mc/orchestrator.py` | Lead Agent routing logic with capability matching |
| `nanobot/mc/test_orchestrator.py` | Unit tests for routing, scoring, keyword extraction |

### Files Modified in This Story

| File | Changes |
|------|---------|
| `dashboard/convex/tasks.ts` | Add `listByStatus` query using `by_status` index |
| `nanobot/mc/gateway.py` | Integrate orchestrator into gateway main loop |

### Verification Steps

1. Create an agent with skills `["financial", "boletos"]` via Convex
2. Create a task "Verificar boletos vencendo" with no assigned agent
3. Verify the orchestrator assigns it to the financial agent within 5 seconds
4. Verify a `task_assigned` activity event is created
5. Create a task "Translate document to Japanese" — no agent has translation skills
6. Verify it's assigned to "lead-agent" with fallback message
7. Create a task with explicit `assignedAgent: "secretario"` — verify no re-routing
8. Run `pytest nanobot/mc/test_orchestrator.py` — all tests pass

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 4.1`] — Original story definition
- [Source: `_bmad-output/planning-artifacts/architecture.md#API & Communication Patterns`] — Bridge as single integration point
- [Source: `_bmad-output/planning-artifacts/architecture.md#Implementation Patterns`] — Naming conventions, activity event pattern
- [Source: `_bmad-output/planning-artifacts/prd.md#FR19`] — Lead Agent capability matching
- [Source: `_bmad-output/planning-artifacts/prd.md#FR20`] — Lead Agent fallback self-execution
- [Source: `_bmad-output/planning-artifacts/prd.md#FR25`] — Done only on explicit agent confirmation
- [Source: `_bmad-output/planning-artifacts/prd.md#NFR2`] — Agent pickup < 5 seconds
- [Source: `_bmad-output/planning-artifacts/prd.md#NFR11`] — 3 agents + 4 tasks concurrent
- [Source: `nanobot/mc/bridge.py`] — ConvexBridge API surface
- [Source: `nanobot/mc/types.py`] — TaskData, AgentData dataclasses
- [Source: `nanobot/mc/state_machine.py`] — Valid transitions (inbox -> assigned)
- [Source: `dashboard/convex/tasks.ts`] — Existing task mutations and queries

## Dev Agent Record

### Agent Model Used
claude-opus-4-6

### Debug Log References
None — all 27 tests passed on first run.

### Completion Notes List
- Created `orchestrator.py` (148 lines, well under 500 limit) with `TaskOrchestrator` class, `extract_keywords()`, and `score_agent()` functions
- Keyword extraction: tokenizes on non-alphanumeric, removes stopwords and short tokens (<3 chars)
- Agent scoring: exact match = 1.0, partial containment = 0.5 per keyword
- Routing loop uses `bridge.subscribe("tasks:listByStatus")` for reactive updates (no polling)
- All synchronous bridge calls wrapped in `asyncio.to_thread()` to avoid blocking the gateway event loop
- Explicit assignments respected — no re-routing (FR2)
- Fallback to "lead-agent" when no agent matches (FR20)
- Activity events created for every routing decision (architectural invariant)
- Added `listByStatus` query to `dashboard/convex/tasks.ts` using `by_status` index
- Integrated orchestrator into `gateway.py` via `run_gateway()` with graceful shutdown
- 27 unit tests covering: keyword extraction (8), agent scoring (9), routing logic (7), concurrent routing (1), routing loop (2)
- All 251 tests in `nanobot/mc/` pass

### File List
| File | Action | Lines |
|------|--------|-------|
| `nanobot/mc/orchestrator.py` | Created | 148 |
| `nanobot/mc/test_orchestrator.py` | Created | 290 |
| `dashboard/convex/tasks.ts` | Modified | +9 (listByStatus query) |
| `nanobot/mc/gateway.py` | Modified | +25 (run_gateway + orchestrator integration) |
