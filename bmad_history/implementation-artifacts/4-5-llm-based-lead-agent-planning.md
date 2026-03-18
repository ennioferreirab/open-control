# Story 4.5: LLM-Based Lead Agent Planning

Status: done

## Story

As a **user**,
I want the Lead Agent to use LLM reasoning to decompose every task into a structured execution plan and intelligently assign agents,
So that tasks are always routed to the right specialist with proper step decomposition — not limited to word-matching heuristics.

## Acceptance Criteria

1. **Given** any task arrives in the inbox (whether simple or complex), **When** the Lead Agent processes it, **Then** the Lead Agent ALWAYS creates an ExecutionPlan via an LLM call — even single-step tasks get a 1-step plan with an assigned agent
2. **Given** the Lead Agent receives a task, **When** it invokes the LLM planner, **Then** the LLM receives a structured prompt containing: the task title, task description, and a summary of ALL enabled agents (name, role, skills list) so it can reason about assignment
3. **Given** the LLM planner generates a plan, **Then** the plan is returned as structured JSON matching the existing `ExecutionPlan` schema: each step has a `step_id`, `description`, `assigned_agent`, and `depends_on` list
4. **Given** the LLM planner assigns an agent to a step, **Then** the assigned agent name MUST match one of the registered agent names exactly (validated before storage)
5. **Given** the LLM planner cannot match a step to any specialist agent, **Then** it assigns that step to `lead-agent` as the fallback
6. **Given** the LLM returns a multi-step plan, **Then** the Lead Agent detects dependencies between steps and identifies which steps can run in parallel (via the LLM's reasoning, not heuristic keyword matching)
7. **Given** the LLM planner generates a valid plan, **Then** the plan is stored on the task document in Convex via the existing `bridge.update_execution_plan()` method and dispatched via the existing `_dispatch_ready_steps()` flow
8. **Given** a task has an explicitly assigned agent (user assigned at creation via Story 4.4), **When** the task enters the inbox, **Then** the Lead Agent still creates a plan but assigns ALL steps to the explicitly assigned agent (respects user intent)
9. **Given** the LLM call fails (provider error, timeout, malformed response), **Then** the system falls back to the existing heuristic planner so tasks are never stuck
10. **Given** the LLM returns a response that is not valid JSON or doesn't match the expected schema, **Then** the system logs a warning, falls back to heuristic planning, and the task is still processed
11. **And** the planner module is created at `nanobot/mc/planner.py` as a new module (not added to orchestrator.py to respect NFR21 500-line limit)
12. **And** the orchestrator's `_process_inbox_task()` calls the new planner instead of the heuristic logic
13. **And** unit tests exist in `tests/mc/test_planner.py` covering: valid plan generation, fallback on LLM error, agent name validation, single-step plans, multi-step plans with dependencies, explicit agent assignment pass-through

## Tasks / Subtasks

- [x] Task 1: Create the planner module with LLM-based planning (AC: #1, #2, #3, #5, #6)
  - [x] 1.1: Create `nanobot/mc/planner.py` with a `TaskPlanner` class
  - [x] 1.2: Implement `plan_task()` async method that accepts task title, description, list of `AgentData`, and optional explicit agent name
  - [x] 1.3: Build the structured prompt for the LLM that includes: task info, agent roster with roles and skills, output format instructions (JSON schema)
  - [x] 1.4: Use `provider_factory.create_provider()` to get the LLM provider (same as executor.py)
  - [x] 1.5: Parse the LLM JSON response into `ExecutionPlan` with `ExecutionPlanStep` objects
  - [x] 1.6: Handle single-step tasks (LLM decides 1 step is enough) and multi-step decomposition

- [x] Task 2: Implement agent name validation and fallback (AC: #4, #5, #8, #9, #10)
  - [x] 2.1: After parsing the LLM response, validate every `assigned_agent` name exists in the provided agents list
  - [x] 2.2: Replace any invalid agent names with `lead-agent`
  - [x] 2.3: If the task has an explicit `assigned_agent` from user input, override all step assignments to that agent
  - [x] 2.4: Implement `_fallback_heuristic_plan()` that wraps the existing `score_agent()` + `extract_keywords()` logic as a fallback
  - [x] 2.5: Wrap the LLM call in try/except — on ANY failure (provider error, JSON parse error, timeout), fall back to heuristic planning

- [x] Task 3: Integrate planner into orchestrator (AC: #7, #12)
  - [x] 3.1: Import `TaskPlanner` in `orchestrator.py`
  - [x] 3.2: Replace the body of `_process_inbox_task()` to call `planner.plan_task()` instead of `score_agent()` + `_create_execution_plan()`
  - [x] 3.3: Keep the existing `_dispatch_ready_steps()`, `_store_execution_plan()`, and `complete_step()` flows unchanged — the planner just produces the plan, execution is the same
  - [x] 3.4: Remove or deprecate `is_multi_step()`, `_parse_steps()`, `_detect_dependencies()`, `_assign_parallel_groups()` heuristic functions (keep `score_agent` and `extract_keywords` for fallback)

- [x] Task 4: Write unit tests (AC: #13)
  - [x] 4.1: Create `tests/mc/test_planner.py`
  - [x] 4.2: Test valid single-step plan generation (mock LLM response)
  - [x] 4.3: Test valid multi-step plan with dependencies (mock LLM response)
  - [x] 4.4: Test agent name validation — invalid names replaced with lead-agent
  - [x] 4.5: Test explicit agent override — all steps assigned to the user-specified agent
  - [x] 4.6: Test LLM failure fallback — provider error triggers heuristic planning
  - [x] 4.7: Test malformed JSON fallback — invalid LLM output triggers heuristic planning
  - [x] 4.8: Update `tests/mc/test_gateway.py` to reflect the new planner integration (orchestrator tests are in test_gateway.py)

## Dev Notes

### Critical Architecture Requirements

- **New module `nanobot/mc/planner.py`**: The orchestrator is already near the 500-line limit (NFR21). The planner MUST be a separate module. The orchestrator calls `planner.plan_task()` and receives an `ExecutionPlan` — it does not know about the LLM prompt internals.
- **Reuse existing ExecutionPlan infrastructure**: The `ExecutionPlan` and `ExecutionPlanStep` dataclasses in `types.py` are the contract. The planner produces these, and the existing dispatch/completion logic in orchestrator.py consumes them unchanged.
- **Reuse existing provider_factory**: Use `nanobot.mc.provider_factory.create_provider()` to get the LLM provider, same as `executor.py:74-82`. This respects the user's configured model, OAuth tokens, etc.
- **Every task gets a plan**: Unlike the heuristic approach that only planned for "multi-step" tasks, the LLM planner ALWAYS produces a plan. Even a simple task gets a 1-step plan. This provides a uniform execution model and makes all routing visible in the dashboard.

### LLM Prompt Design

The planner prompt should be structured as a system + user message pair:

**System prompt:**
```
You are a task planning assistant for a multi-agent system. Your job is to:
1. Decompose a task into one or more execution steps
2. Assign each step to the most appropriate agent based on their skills
3. Identify dependencies between steps (which steps must complete before others can start)

You MUST respond with valid JSON only, no markdown, no explanation.

Response format:
{
  "steps": [
    {
      "step_id": "step_1",
      "description": "Clear description of what this step does",
      "assigned_agent": "agent-name",
      "depends_on": []
    }
  ]
}

Rules:
- step_id must be "step_1", "step_2", etc.
- assigned_agent must be one of the agent names listed below, or "lead-agent" if no specialist fits
- depends_on is a list of step_ids that must complete before this step can start
- For simple tasks, a single step is fine
- Only create multiple steps if the task genuinely has distinct phases
```

**User message:**
```
Task: {title}
Description: {description or "No description provided"}

Available agents:
- {agent.name} (role: {agent.role}, skills: {', '.join(agent.skills)})
- {agent.name} (role: {agent.role}, skills: {', '.join(agent.skills)})
...

Create an execution plan for this task.
```

### Planner Module Structure

```python
# nanobot/mc/planner.py
"""LLM-based task planner for intelligent agent routing."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from nanobot.mc.types import AgentData, ExecutionPlan, ExecutionPlanStep

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

LEAD_AGENT_NAME = "lead-agent"


class TaskPlanner:
    """Plans task execution using LLM reasoning."""

    async def plan_task(
        self,
        title: str,
        description: str | None,
        agents: list[AgentData],
        explicit_agent: str | None = None,
    ) -> ExecutionPlan:
        """Create an execution plan for a task.

        If explicit_agent is set, all steps are assigned to that agent.
        On LLM failure, falls back to heuristic planning.
        """
        try:
            plan = await self._llm_plan(title, description, agents)
            self._validate_agent_names(plan, agents)
            if explicit_agent:
                self._override_agents(plan, explicit_agent)
            return plan
        except Exception as exc:
            logger.warning(
                "[planner] LLM planning failed, using heuristic fallback: %s", exc
            )
            return self._fallback_heuristic_plan(title, description, agents, explicit_agent)

    async def _llm_plan(self, title, description, agents) -> ExecutionPlan:
        """Call LLM to generate the plan."""
        ...

    def _validate_agent_names(self, plan: ExecutionPlan, agents: list[AgentData]) -> None:
        """Replace invalid agent names with lead-agent."""
        valid_names = {a.name for a in agents} | {LEAD_AGENT_NAME}
        for step in plan.steps:
            if step.assigned_agent and step.assigned_agent not in valid_names:
                logger.warning("[planner] Invalid agent '%s', replacing with lead-agent", step.assigned_agent)
                step.assigned_agent = LEAD_AGENT_NAME

    def _override_agents(self, plan: ExecutionPlan, agent_name: str) -> None:
        """Override all step assignments with an explicit agent."""
        for step in plan.steps:
            step.assigned_agent = agent_name

    def _fallback_heuristic_plan(self, title, description, agents, explicit_agent) -> ExecutionPlan:
        """Heuristic fallback using existing score_agent logic."""
        from nanobot.mc.orchestrator import extract_keywords, score_agent
        ...
```

### Orchestrator Integration Point

The change in `orchestrator.py` is minimal — replace the routing logic in `_process_inbox_task()`:

```python
# BEFORE (heuristic):
keywords = extract_keywords(title, description)
scored = [(agent, score_agent(agent, keywords)) for agent in agents]
scored.sort(key=lambda x: x[1], reverse=True)
plan = self._create_execution_plan(title, description, agents)
if plan is not None:
    ...
elif scored and scored[0][1] > 0:
    ...
else:
    # fallback to lead-agent

# AFTER (LLM planner):
planner = TaskPlanner()
plan = await planner.plan_task(title, description, agents, assigned_agent)
await self._store_execution_plan(task_id, plan)
# Determine the primary agent from the plan
primary_agent = plan.steps[0].assigned_agent if plan.steps else LEAD_AGENT_NAME
await asyncio.to_thread(
    self._bridge.update_task_status,
    task_id, TaskStatus.ASSIGNED, primary_agent,
    f"Lead Agent planned '{title}' ({len(plan.steps)} steps)",
)
await self._dispatch_ready_steps(task_id, plan)
```

### LLM Provider Configuration

The planner uses the same provider_factory as the executor. Key points:

- `provider_factory.create_provider(model=None)` → uses user's default model from config
- Consider using a smaller/faster model for planning (e.g., haiku) if latency is a concern — this can be configurable later
- The LLM call should use `temperature=0.3` (low creativity, high consistency for structured output)
- Set `max_tokens=2048` — plans should be concise

```python
from nanobot.mc.provider_factory import create_provider

provider, model = create_provider()  # Uses user's default
response = await asyncio.to_thread(
    provider.chat,
    model=model,
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
    temperature=0.3,
    max_tokens=2048,
)
```

### JSON Parsing Strategy

The LLM response may contain markdown fencing or extra text. Parse defensively:

```python
def _parse_plan_response(self, raw: str) -> ExecutionPlan:
    """Parse LLM response into ExecutionPlan, handling markdown fencing."""
    # Strip markdown code fencing if present
    text = raw.strip()
    if text.startswith("```"):
        # Remove ```json or ``` prefix and trailing ```
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    data = json.loads(text)
    return ExecutionPlan.from_dict(data)
```

### Common LLM Developer Mistakes to Avoid

1. **DO NOT modify ExecutionPlan or ExecutionPlanStep dataclasses** — The planner must produce plans in the EXISTING format. The dashboard's ExecutionPlanTab.tsx already renders them.

2. **DO NOT remove the heuristic functions from orchestrator.py entirely** — Keep `score_agent()` and `extract_keywords()` as they are used by the fallback path in the planner module. Remove only the multi-step detection heuristics (`is_multi_step`, `_parse_steps`, `_detect_dependencies`, `_assign_parallel_groups`).

3. **DO NOT make the LLM call blocking** — Use `asyncio.to_thread()` to wrap synchronous provider calls, same as executor.py does.

4. **DO NOT hardcode a specific LLM model** — Use `provider_factory.create_provider()` which respects the user's config. The planner should work with any provider (Anthropic, OpenAI, etc.).

5. **DO NOT skip the fallback on LLM failure** — The heuristic fallback is critical. If the LLM provider is misconfigured, tasks must still be routed.

6. **DO NOT put the LLM prompt template in a separate file** — Keep it as constants in `planner.py`. The prompt is code, not configuration.

7. **DO NOT create a plan for manual tasks** — The `is_manual` check in `_process_inbox_task()` must remain, and manual tasks should still be skipped.

8. **DO NOT forget to filter disabled agents** — The agent list passed to the planner should only include `enabled=True` agents (already filtered in the orchestrator before calling the planner).

### What This Story Does NOT Include

- **Dashboard changes** — The existing `ExecutionPlanTab.tsx` already renders execution plans. No UI changes needed.
- **Convex schema changes** — The `executionPlan` field on tasks is already `v.optional(v.any())`. No schema changes needed.
- **Agent YAML changes** — No changes to agent configuration format.
- **Configurable planner model** — Using the user's default model for now. A separate "planner model" setting can be added later.
- **Plan caching or reuse** — Each task gets a fresh plan. No caching.

### Project Structure Notes

- New file: `nanobot/mc/planner.py` — LLM-based task planner
- New file: `tests/mc/test_planner.py` — Planner unit tests
- Modified: `nanobot/mc/orchestrator.py` — Replace heuristic routing with planner call
- Modified: `tests/mc/test_orchestrator.py` — Update tests for new integration
- Unchanged: `nanobot/mc/types.py` — ExecutionPlan/ExecutionPlanStep (reused as-is)
- Unchanged: `nanobot/mc/bridge.py` — update_execution_plan() (reused as-is)
- Unchanged: `nanobot/mc/executor.py` — Task execution (consumes plans as-is)
- Unchanged: `dashboard/components/ExecutionPlanTab.tsx` — Renders plans (reused as-is)

### References

- [Source: `nanobot/mc/orchestrator.py`] — Current heuristic routing (to be replaced)
- [Source: `nanobot/mc/types.py#ExecutionPlan`] — Plan data structure (to be reused)
- [Source: `nanobot/mc/executor.py#_run_agent_on_task`] — Agent execution using provider_factory
- [Source: `nanobot/mc/bridge.py#update_execution_plan`] — Plan persistence to Convex
- [Source: `_bmad-output/planning-artifacts/epics.md#Story 4.1`] — FR19 Lead Agent capability matching
- [Source: `_bmad-output/planning-artifacts/epics.md#Story 4.2`] — FR21 Execution planning
- [Source: `_bmad-output/planning-artifacts/architecture.md#Task Orchestration`] — Orchestration architecture
- [Source: `_bmad-output/planning-artifacts/prd.md#FR19-FR23`] — Lead Agent routing requirements

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

- Created `nanobot/mc/planner.py` with `TaskPlanner` class implementing LLM-based task planning
- TaskPlanner.plan_task() builds a structured prompt with task info and agent roster, calls LLM, parses JSON response into ExecutionPlan
- Implemented agent name validation (invalid names → lead-agent), explicit agent override (all steps → user-specified agent)
- Implemented heuristic fallback using existing score_agent/extract_keywords when LLM fails (provider error, timeout, malformed JSON)
- Defensive JSON parsing handles markdown code fencing and missing 'steps' key
- Replaced orchestrator's _process_inbox_task() to use TaskPlanner — every task now gets a plan (even single-step)
- Removed heuristic functions from orchestrator: is_multi_step, _parse_steps, _detect_dependencies, _assign_parallel_groups, _create_execution_plan, _plan_summary
- Kept score_agent and extract_keywords in orchestrator (used by planner's fallback path)
- Orchestrator reduced from 690 to 445 lines (well under NFR21 500-line limit)
- Updated 3 existing tests in test_gateway.py (TestOrchestratorNoDuplicateActivity) to mock TaskPlanner
- Created 19 tests in test_planner.py covering all AC requirements
- All 115 tests pass with no regressions

### Change Log

- 2026-02-23: Implemented Story 4.5 — LLM-based lead agent planning (all 4 tasks, all 13 ACs)
- 2026-02-23: Code review fixes — H1: fixed None assigned_agent defaulting to lead-agent; M1: added 30s timeout on LLM call; M2: deduplicated LEAD_AGENT_NAME to types.py; M3: moved extract_keywords/score_agent to planner.py breaking circular dependency; L1: removed dead TYPE_CHECKING block; L2: added test for None agent edge case

### File List

- `nanobot/mc/planner.py` — NEW: LLM-based task planner module (+ scoring functions moved from orchestrator)
- `nanobot/mc/orchestrator.py` — MODIFIED: Replaced heuristic routing with planner integration, removed scoring functions
- `nanobot/mc/types.py` — MODIFIED: Added LEAD_AGENT_NAME constant
- `tests/mc/test_planner.py` — NEW: 20 unit tests for planner module
- `tests/mc/test_gateway.py` — MODIFIED: Updated 3 orchestrator tests for planner integration
