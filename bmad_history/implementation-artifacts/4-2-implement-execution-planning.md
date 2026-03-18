# Story 4.2: Implement Execution Planning

Status: done

## Story

As a **user**,
I want the Lead Agent to create visible execution plans for complex tasks,
So that I can see how work is being broken down and which steps depend on each other.

## Acceptance Criteria

1. **Given** the Lead Agent receives a complex or batch task, **When** the Lead Agent analyzes it, **Then** it creates an execution plan identifying: individual sub-steps, blocking dependencies, parallelizable steps, and assigned agents per step
2. **Given** an execution plan is created, **Then** the plan is stored as a structured JSON field (`executionPlan`) on the task document in Convex
3. **Given** a `task_assigned` activity event is created for a planned task, **Then** the event description includes a summary of the plan (e.g., "Created 3-step plan: 2 parallel + 1 blocking")
4. **Given** an execution plan exists for a task, **When** a blocking step completes, **Then** dependent steps are automatically unblocked and dispatched (FR23)
5. **Given** an execution plan has parallelizable steps, **When** those steps are dispatched, **Then** they are sent to different agents simultaneously (FR22)
6. **Given** a step in the plan completes, **Then** the orchestrator updates the plan status in the task document and writes a `task_started` activity event for each newly unblocked step
7. **Given** all steps in the plan complete, **Then** the task transitions to "review" or "done" based on its trust level
8. **And** execution plan logic is implemented in `nanobot/mc/orchestrator.py` (extends Story 4.1)
9. **And** the Convex schema is extended with an `executionPlan` field on the `tasks` table
10. **And** unit tests cover plan creation, dependency resolution, and parallel dispatch

## Tasks / Subtasks

- [ ] Task 1: Extend the Convex schema with execution plan fields (AC: #2, #9)
  - [ ] 1.1: Add `executionPlan` optional field to the `tasks` table in `dashboard/convex/schema.ts` — type is `v.optional(v.any())` (JSON object storing plan structure)
  - [ ] 1.2: Add a Convex mutation `tasks:updateExecutionPlan` that patches the `executionPlan` field on a task
  - [ ] 1.3: Run `npx convex dev` to verify schema compiles

- [ ] Task 2: Define the ExecutionPlan data structure in Python types (AC: #1)
  - [ ] 2.1: Add `ExecutionPlanStep` dataclass to `nanobot/mc/types.py` with fields: `step_id` (str), `description` (str), `assigned_agent` (str | None), `depends_on` (list[str] — step_ids), `parallel_group` (str | None), `status` (str — "pending" | "in_progress" | "completed" | "failed")
  - [ ] 2.2: Add `ExecutionPlan` dataclass with fields: `steps` (list[ExecutionPlanStep]), `created_at` (str ISO 8601)
  - [ ] 2.3: Add `to_dict()` and `from_dict()` methods for serialization to/from Convex JSON

- [ ] Task 3: Implement plan creation in the orchestrator (AC: #1, #3)
  - [ ] 3.1: Add `_create_execution_plan(task: TaskData, agents: list[AgentData]) -> ExecutionPlan | None` method to `TaskOrchestrator`
  - [ ] 3.2: For simple single-step tasks, return `None` (no plan needed — direct routing as in Story 4.1)
  - [ ] 3.3: For tasks with descriptions containing step indicators (numbered lists, "then", "after", "first...then"), decompose into steps
  - [ ] 3.4: Analyze step dependencies — if step B references output of step A, mark B as `depends_on: [step_a_id]`
  - [ ] 3.5: Group independent steps into parallel groups
  - [ ] 3.6: Assign agents to steps using the scoring logic from Story 4.1
  - [ ] 3.7: Store the plan on the task via `bridge.mutation("tasks:updateExecutionPlan", ...)`
  - [ ] 3.8: Create activity event with plan summary

- [ ] Task 4: Implement dependency resolution and dispatch (AC: #4, #5, #6, #7)
  - [ ] 4.1: Add `_dispatch_ready_steps(task_id: str, plan: ExecutionPlan)` method
  - [ ] 4.2: Identify steps where all `depends_on` steps have status "completed" and the step itself is "pending"
  - [ ] 4.3: Dispatch ready steps by creating sub-tasks or updating step status to "in_progress"
  - [ ] 4.4: For parallel groups, dispatch all ready steps in the group simultaneously
  - [ ] 4.5: When a step completes, update plan status and call `_dispatch_ready_steps` again to unblock dependents
  - [ ] 4.6: When all steps reach "completed", transition the parent task based on trust level

- [ ] Task 5: Add bridge methods for execution plan operations (AC: #2)
  - [ ] 5.1: Add `update_execution_plan(task_id: str, plan: dict)` to `ConvexBridge`
  - [ ] 5.2: Add `get_task(task_id: str) -> dict` convenience method if not already present

- [ ] Task 6: Write unit tests (AC: #10)
  - [ ] 6.1: Test plan creation from a multi-step task description
  - [ ] 6.2: Test single-step task returns None (no plan)
  - [ ] 6.3: Test dependency identification between steps
  - [ ] 6.4: Test parallel group assignment for independent steps
  - [ ] 6.5: Test step dispatch only fires when all dependencies are met
  - [ ] 6.6: Test parallel dispatch sends multiple steps simultaneously
  - [ ] 6.7: Test all-steps-completed triggers parent task transition

## Dev Notes

### Critical Architecture Requirements

- **Execution plans are stored as JSON on the task document**: This is NOT a separate table. The `executionPlan` field is a structured JSON object stored directly on the task in Convex. This keeps all task data co-located and avoids cross-table joins.
- **The plan is visible to the dashboard**: Story 4.3 will read this field to render the plan visualization. The data structure must be dashboard-friendly (serializable, self-contained).
- **Sub-steps are NOT separate tasks**: For MVP, execution plan steps are logical steps tracked within the plan JSON — they do NOT create separate task documents. The parent task is the single entity on the Kanban board.

### ExecutionPlan Data Structure

```python
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

@dataclass
class ExecutionPlanStep:
    step_id: str            # e.g., "step_1"
    description: str        # e.g., "Research market data"
    assigned_agent: str | None = None
    depends_on: list[str] = field(default_factory=list)
    parallel_group: str | None = None  # e.g., "group_a"
    status: str = "pending"  # "pending" | "in_progress" | "completed" | "failed"

@dataclass
class ExecutionPlan:
    steps: list[ExecutionPlanStep] = field(default_factory=list)
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps": [asdict(s) for s in self.steps],
            "createdAt": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionPlan":
        steps = [
            ExecutionPlanStep(
                step_id=s["step_id"] if "step_id" in s else s.get("stepId", ""),
                description=s["description"],
                assigned_agent=s.get("assigned_agent") or s.get("assignedAgent"),
                depends_on=s.get("depends_on") or s.get("dependsOn", []),
                parallel_group=s.get("parallel_group") or s.get("parallelGroup"),
                status=s.get("status", "pending"),
            )
            for s in data.get("steps", [])
        ]
        return cls(steps=steps, created_at=data.get("createdAt", ""))
```

### Convex Schema Extension

```typescript
// In tasks table definition, add:
executionPlan: v.optional(v.any()),
```

Using `v.any()` for the execution plan because Convex doesn't have deep JSON schema validation — the structure is validated on the Python side before writing.

### Plan Creation Heuristics

For MVP, the orchestrator uses simple text analysis to detect multi-step tasks:

```python
STEP_INDICATORS = [
    r"\d+\.\s",        # "1. Do X"
    r"(?:first|then|after|next|finally)",
    r"(?:step \d+)",
    r"\n-\s",          # "- Do X"
]

def _is_multi_step(title: str, description: str | None) -> bool:
    """Heuristic: does this task need an execution plan?"""
    text = f"{title} {description or ''}"
    return any(re.search(pat, text, re.IGNORECASE) for pat in STEP_INDICATORS)
```

### Dispatch Pattern

```python
def _get_ready_steps(plan: ExecutionPlan) -> list[ExecutionPlanStep]:
    """Find steps that are ready to execute (all deps met, status pending)."""
    completed_ids = {s.step_id for s in plan.steps if s.status == "completed"}
    ready = []
    for step in plan.steps:
        if step.status != "pending":
            continue
        if all(dep in completed_ids for dep in step.depends_on):
            ready.append(step)
    return ready
```

### Common LLM Developer Mistakes to Avoid

1. **DO NOT create separate task documents for each step** — Steps live inside the `executionPlan` JSON field on the parent task. The Kanban board shows the parent task, not individual steps.

2. **DO NOT use `v.object()` with full schema for executionPlan** — Use `v.optional(v.any())` because the plan structure is complex and validated on the Python side. Deep Convex validation would be brittle.

3. **DO NOT forget to handle the camelCase conversion** — When writing the plan to Convex, the bridge converts `step_id` to `stepId` etc. The `to_dict()` method should output camelCase keys, OR the bridge conversion handles it.

4. **DO NOT block on step completion** — The orchestrator should be event-driven. When a step completes (detected via subscription or callback), it triggers dispatch of dependent steps.

5. **DO NOT re-implement routing** — Step agent assignment reuses the `_score_agent()` logic from Story 4.1.

6. **DO NOT send parallel dispatch sequentially** — Use `asyncio.gather()` or similar to dispatch parallel steps simultaneously.

### What This Story Does NOT Include

- **Execution plan visualization** — Dashboard rendering of the plan is Story 4.3
- **Agent execution logic** — Actually running agent work on each step
- **LLM-based task decomposition** — Using an LLM to break down tasks (post-MVP enhancement)

### Files Created in This Story

| File | Purpose |
|------|---------|
| (none — extends existing files) | |

### Files Modified in This Story

| File | Changes |
|------|---------|
| `dashboard/convex/schema.ts` | Add `executionPlan: v.optional(v.any())` to tasks table |
| `dashboard/convex/tasks.ts` | Add `updateExecutionPlan` mutation |
| `nanobot/mc/types.py` | Add `ExecutionPlanStep` and `ExecutionPlan` dataclasses |
| `nanobot/mc/orchestrator.py` | Add plan creation, dependency resolution, parallel dispatch |
| `nanobot/mc/bridge.py` | Add `update_execution_plan()` convenience method |
| `nanobot/mc/test_orchestrator.py` | Add tests for planning and dispatch |

### Verification Steps

1. Create a task "1. Research AI trends 2. Write summary 3. Review the summary" — verify a 3-step plan is created
2. Verify steps 1 and 2 are identified as parallelizable (no dependency between them)
3. Verify step 3 is blocked until steps 1 and 2 complete
4. Mark steps 1 and 2 as completed — verify step 3 is automatically dispatched
5. Verify the execution plan is stored on the task document in Convex
6. Verify activity events are created for each step dispatch
7. Create a simple task "Check my email" — verify no execution plan is created
8. Run `pytest nanobot/mc/test_orchestrator.py` — all tests pass

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 4.2`] — Original story definition
- [Source: `_bmad-output/planning-artifacts/prd.md#FR21`] — Execution planning with blocking/parallel identification
- [Source: `_bmad-output/planning-artifacts/prd.md#FR22`] — Parallel task dispatch
- [Source: `_bmad-output/planning-artifacts/prd.md#FR23`] — Auto-unblock dependent tasks
- [Source: `_bmad-output/planning-artifacts/prd.md#Domain-Specific Requirements`] — Lead Agent Planning Table format
- [Source: `_bmad-output/planning-artifacts/architecture.md#Data Architecture`] — Tasks table stores execution plan data
- [Source: `nanobot/mc/orchestrator.py`] — Extends routing logic from Story 4.1
- [Source: `nanobot/mc/types.py`] — Existing type definitions to extend
- [Source: `dashboard/convex/schema.ts`] — Schema to extend with executionPlan field

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References
All 288 tests in nanobot/mc/ pass (64 orchestrator tests, including 27 new execution planning tests).

### Completion Notes List
- Added ExecutionPlanStep and ExecutionPlan dataclasses to types.py with to_dict()/from_dict() serialization
- Added executionPlan field (v.optional(v.any())) to Convex tasks table schema
- Added updateExecutionPlan mutation to tasks.ts
- Added update_execution_plan() convenience method to bridge.py
- Added multi-step detection heuristic (numbered lists, sequence keywords, bullet lists, "step N")
- Added step parsing, dependency detection, and parallel group assignment
- Added _create_execution_plan(), _dispatch_ready_steps(), complete_step() to orchestrator
- Integrated plan creation into _process_inbox_task routing flow
- Parallel dispatch uses asyncio.gather() (FR22)
- Step completion auto-unblocks dependents (FR23)
- All-steps-completed transitions task to done/review based on trust level
- 27 new tests covering: types roundtrip, multi-step detection, plan creation, dependency detection, parallel groups, agent assignment, ready step detection, dispatch, completion, and end-to-end routing integration

### File List
- `nanobot/mc/types.py` — Added ExecutionPlanStep and ExecutionPlan dataclasses
- `nanobot/mc/orchestrator.py` — Added execution planning logic (is_multi_step, _parse_steps, _detect_dependencies, _assign_parallel_groups, get_ready_steps, plan creation/dispatch/completion methods)
- `nanobot/mc/bridge.py` — Added update_execution_plan() convenience method
- `nanobot/mc/test_orchestrator.py` — Added 27 execution planning tests
- `dashboard/convex/schema.ts` — Added executionPlan field to tasks table
- `dashboard/convex/tasks.ts` — Added updateExecutionPlan mutation
