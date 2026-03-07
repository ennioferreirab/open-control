# Mission Control Architecture

## Overview

Mission Control uses a hybrid feature-first backend layout:

- `mc/runtime/` owns composition roots, lifecycle loops, and runtime wiring.
- `mc/contexts/` owns business flows such as planning, execution, conversation,
  review, and agent synchronization.
- `mc/domain/`, `mc/bridge/`, and `mc/infrastructure/` remain the shared
  stable base for rules, data access, and environment concerns.
- `mc/application/execution/` is the reusable execution kernel shared by the
  execution context.
- the `mc/` root is intentionally minimal and keeps only `mc/__init__.py` and
  `mc/types.py`.

The intended dependency shape is:

```text
boot.py
  -> mc.cli
    -> mc.runtime
      -> mc.runtime.gateway
      -> mc.runtime.orchestrator
      -> mc.contexts.*
        -> mc.application.execution.*
        -> mc.domain.*
        -> mc.bridge.*
        -> mc.infrastructure.*

dashboard/components/*
  -> dashboard/hooks/*
    -> dashboard/convex/*
      -> dashboard/convex/lib/*

shared/workflow/workflow_spec.json
  -> mc/domain/workflow_contract.py
  -> dashboard/convex/lib/workflowContract.ts
```

## Backend Structure

### `mc/runtime`

Runtime modules are the composition layer.

- `mc.runtime.gateway` wires long-running services and process lifecycle.
- `mc.runtime.orchestrator` subscribes to task streams and delegates to workers.
- `mc.runtime.workers` is the runtime-facing worker namespace.

Rule:
- runtime modules compose flows but do not become the home for business logic.

### `mc/contexts/planning`

Planning owns pre-execution task shaping.

- task planning
- plan materialization
- plan negotiation
- title generation

Primary modules:
- `mc.contexts.planning.planner`
- `mc.contexts.planning.materializer`
- `mc.contexts.planning.negotiation`
- `mc.contexts.planning.parser`
- `mc.contexts.planning.title_generation`

Canonical package API:
- `mc.contexts.planning.TaskPlanner`
- `mc.contexts.planning.PlanMaterializer`
- `mc.contexts.planning.handle_plan_negotiation`
- `mc.contexts.planning.start_plan_negotiation_loop`

### `mc/contexts/execution`

Execution owns task and step execution entrypoints.

- task execution
- Claude Code execution helpers
- step dispatch
- execution adapters layered over `mc.application.execution`

Primary modules:
- `mc.contexts.execution.executor`
- `mc.contexts.execution.cc_executor`
- `mc.contexts.execution.cc_step_runner`
- `mc.contexts.execution.crash_recovery`
- `mc.contexts.execution.post_processing`
- `mc.contexts.execution.step_dispatcher`

Canonical package API:
- `mc.contexts.execution.TaskExecutor`
- `mc.contexts.execution.StepDispatcher`
- `mc.contexts.execution.CCExecutorMixin`
- `mc.contexts.execution.execute_step_via_cc`

### `mc/contexts/conversation`

Conversation owns thread and user interaction flows.

- chat handling
- intent resolution
- plan-chat routing
- mention and ask-user ownership during the transition

Primary modules:
- `mc.contexts.conversation.chat_handler`
- `mc.contexts.conversation.service`
- `mc.contexts.conversation.intent`

Canonical package API:
- `mc.contexts.conversation.ChatHandler`
- `mc.contexts.conversation.ConversationService`
- `mc.contexts.conversation.ConversationIntent`

### `mc/contexts/review`

Review owns approval, feedback, and review-state transitions.

Primary module:
- `mc.contexts.review.handler`

Canonical package API:
- `mc.contexts.review.ReviewHandler`

### `mc/contexts/agents`

Agent management owns sync and registry coordination.

Primary module:
- `mc.contexts.agents.sync`

### Shared Base Layers

#### `mc/domain`

Pure rules and shared workflow behavior live here.

- workflow contract adapters
- transition validation
- generic pure helpers
- invariant helpers

Primary modules:
- `mc.domain.workflow.state_machine`
- `mc.domain.utils`

#### `mc/bridge`

Convex data-access boundary.

- repositories and subscriptions
- SDK adaptation
- backend-facing data access

#### `mc/infrastructure`

Environment and framework details.

- config paths
- filesystem layout
- bootstrap helpers
- runtime adapters
- agent validation
- provider creation and model tier resolution

Primary modules:
- `mc.infrastructure.boards`
- `mc.infrastructure.orientation`
- `mc.infrastructure.agents.yaml_validator`
- `mc.infrastructure.providers.factory`
- `mc.infrastructure.providers.tier_resolver`

#### `mc/application/execution`

Reusable execution nucleus shared by the execution context.

- request/result types
- context builders
- execution engine
- runner strategies
- post-processing helpers
- thread context assembly

Primary modules:
- `mc.application.execution.thread_context`
- `mc.application.execution.engine`
- `mc.application.execution.runtime`

Rule:
- new execution behavior should land in the execution context or this nucleus,
  not back in `mc/` root modules.

## Package Entry Points

The canonical import paths are package-based, not root-file-based.

Preferred imports:

- `from mc.runtime import TaskOrchestrator, run_gateway`
- `from mc.contexts.planning import TaskPlanner, PlanMaterializer`
- `from mc.contexts.execution import TaskExecutor, StepDispatcher`
- `from mc.contexts.conversation import ChatHandler, ConversationService`
- `from mc.contexts.review import ReviewHandler`

Legacy-style imports such as `mc.executor`, `mc.gateway`, `mc.planner`, and
similar root aliases are intentionally removed.

## Workflow Contract

The workflow contract is versioned in:

- `shared/workflow/workflow_spec.json`

Consumers:

- `mc/domain/workflow_contract.py`
- `dashboard/convex/lib/workflowContract.ts`

This contract defines:

- task statuses
- step statuses
- valid transitions
- workflow action mappings
- thread and workflow message semantics

## Guardrails

Architecture rules are protected by:

- `tests/mc/test_architecture.py`
- `tests/mc/test_module_reorganization.py`
- `tests/mc/infrastructure/test_boundary.py`
- `dashboard/tests/architecture.test.ts`

Current guardrails enforce:

- protected backend modules do not import `mc.runtime.gateway`
- runtime-facing modules do not import `mc.contexts.execution.executor` directly
- canonical packages do not import removed root modules
- the `mc/` root stays restricted to `__init__.py` and `types.py`
- removed root facade modules stay deleted
- dashboard feature components avoid direct Convex hooks where feature hooks exist
- dashboard hooks do not depend on UI components

## Design Rules

1. Runtime modules compose flows; contexts own behavior.
2. Shared rules belong in `domain`, not in runtime or UI.
3. Convex access stays behind `bridge`.
4. Environment and filesystem concerns stay in `infrastructure`.
5. `mc.application.execution` is a reusable kernel, not a competing architecture.
6. The `mc/` root is not an ownership layer.
7. New public imports should come from package `__init__.py` entrypoints where available.
