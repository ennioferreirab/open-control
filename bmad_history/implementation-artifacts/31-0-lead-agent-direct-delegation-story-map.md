# Epic 31: Lead-Agent Direct Delegation Story Map

Status: ready-for-planning

## Goal

Break the approved lead-agent direct delegation design into implementation-ready
BMad stories with clear ownership boundaries, file targets, and safe sequencing.

## Recommended Delivery Order

Stories `31.1` through `31.4` are the minimum safe cut for semantic correctness.

1. `31.1` Add task work and routing modes
2. `31.2` Add the active agent registry view and agent metric fields
3. `31.3` Route normal tasks through lead-agent direct delegation
4. `31.4` Scope planning and plan-chat semantics to workflow only
5. `31.5` Persist direct delegation and human routing from the dashboard
6. `31.6` Scope task-detail plan review UI to workflow while keeping the plan
   tab shell
7. `31.7` Track agent task and step execution metrics

## Story Inventory

### Story 31.1: Add Task Work and Routing Modes

- Overall objective: add explicit `workMode` and `routingMode` contracts to
  tasks so workflow, lead-agent delegation, and human routing stop sharing
  implicit behavior.
- Primary files:
  - `dashboard/convex/schema.ts`
  - `dashboard/convex/lib/taskMetadata.ts`
  - `dashboard/convex/tasks.ts`
  - `dashboard/convex/lib/squadMissionLaunch.ts`
  - `dashboard/convex/tasks.test.ts`

### Story 31.2: Add Active Agent Registry View and Agent Metric Fields

- Overall objective: expose a routing-grade active-agent registry read model and
  add persistent metric fields that both routing and observability can use.
- Primary files:
  - `dashboard/convex/schema.ts`
  - `dashboard/convex/agents.ts`
  - `dashboard/convex/agents.test.ts`
  - `mc/bridge/repositories/agents.py`
  - `mc/bridge/facade_mixins.py`

### Story 31.3: Route Normal Tasks Through Lead-Agent Direct Delegation

- Overall objective: replace normal-task lead-agent planning with direct
  delegation that selects a target agent from the active registry and assigns
  the task without generating an execution plan.
- Primary files:
  - `mc/runtime/workers/inbox.py`
  - `mc/runtime/workers/planning.py`
  - `mc/runtime/orchestrator.py`
  - `mc/contexts/routing/router.py`
  - `tests/mc/workers/test_direct_delegate_routing.py`
  - `tests/mc/contexts/routing/test_router.py`

### Story 31.4: Scope Planning and Plan Chat to Workflow Only

- Overall objective: make planning, plan negotiation, and `plan_chat` behavior
  apply only to workflow-backed tasks.
- Primary files:
  - `mc/contexts/conversation/intent.py`
  - `mc/contexts/conversation/service.py`
  - `mc/contexts/planning/negotiation.py`
  - `mc/runtime/workers/planning.py`
  - `tests/mc/services/test_conversation_intent.py`
  - `tests/mc/services/test_conversation.py`

### Story 31.5: Persist Direct Delegation and Human Routing from the Dashboard

- Overall objective: make frontend task creation and explicit operator routing
  persist the new task-mode and routing-mode contract without changing the
  current shell UX.
- Primary files:
  - `dashboard/features/tasks/components/TaskInput.tsx`
  - `dashboard/features/tasks/hooks/useTaskInputData.ts`
  - `dashboard/convex/tasks.ts`
  - `dashboard/convex/lib/taskMetadata.ts`
  - `dashboard/components/TaskInput.test.tsx`

### Story 31.6: Scope Task Detail Plan Review UI to Workflow

- Overall objective: preserve the `Execution Plan` tab shell for all tasks, but
  remove lead-agent plan review affordances from non-workflow tasks.
- Primary files:
  - `dashboard/convex/lib/readModels.ts`
  - `dashboard/features/tasks/components/TaskDetailSheet.tsx`
  - `dashboard/features/tasks/components/PlanReviewPanel.tsx`
  - `dashboard/features/tasks/hooks/useTaskDetailView.ts`
  - `dashboard/features/tasks/components/TaskDetailSheet.test.tsx`
  - `dashboard/features/tasks/components/PlanReviewPanel.test.tsx`

### Story 31.7: Track Agent Task and Step Execution Metrics

- Overall objective: update task and step completion paths so agent-level
  execution metrics become durable and queryable.
- Primary files:
  - `dashboard/convex/lib/taskLifecycle.ts`
  - `dashboard/convex/lib/taskLifecycle.test.ts`
  - `dashboard/convex/steps.ts`
  - `dashboard/convex/steps.test.ts`
  - `dashboard/convex/agents.ts`

## References

- [Source: `docs/plans/2026-03-17-lead-agent-direct-delegation-design.md`]
- [Source: `docs/plans/2026-03-17-lead-agent-direct-delegation-implementation-plan.md`]
