# Mission Control Architecture

## Overview

Mission Control now uses a hybrid feature-first backend layout:

- `mc/runtime/` owns composition roots, lifecycle loops, and runtime wiring.
- `mc/contexts/` owns business flows such as planning, execution, conversation,
  review, and agent synchronization.
- `mc/domain/`, `mc/bridge/`, and `mc/infrastructure/` remain the shared
  stable base for rules, data access, and environment concerns.
- the `mc/` root is intentionally small and keeps only public facades plus
  `mc/types.py`.

The intended dependency shape is:

```text
boot.py
  -> mc.gateway                 # compatibility facade
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

### `mc/contexts/review`

Review owns approval, feedback, and review-state transitions.

Primary module:
- `mc.contexts.review.handler`

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

Rule:
- new execution behavior should land in the execution context or this nucleus,
  not back in top-level `mc/executor.py`.

## Compatibility Layer

The following top-level modules remain intentionally available during the
transition:

- `mc.gateway`
- `mc.orchestrator`
- `mc.planner`
- `mc.plan_materializer`
- `mc.plan_negotiator`
- `mc.executor`
- `mc.cc_executor`
- `mc.cc_step_runner`
- `mc.step_dispatcher`
- `mc.chat_handler`
- `mc.review_handler`
- `mc.services.conversation`
- `mc.services.conversation_intent`
- `mc.services.agent_sync`
- `mc.types`

Rule:
- these files are facades only
- the root should not gain new concrete modules
- new behavior should not be added there

## Workflow Contract

The workflow contract is versioned in:

- `shared/workflow/workflow_spec.json`

Consumers:

- [mc/domain/workflow_contract.py](/Users/ennio/Documents/nanobot-ennio/.worktrees/codex/hybrid-contexts/mc/domain/workflow_contract.py)
- [dashboard/convex/lib/workflowContract.ts](/Users/ennio/Documents/nanobot-ennio/.worktrees/codex/hybrid-contexts/dashboard/convex/lib/workflowContract.ts)

This contract defines:

- task statuses
- step statuses
- valid transitions
- workflow action mappings
- thread and workflow message semantics

## Guardrails

Architecture rules are protected by:

- [tests/mc/test_architecture.py](/Users/ennio/Documents/nanobot-ennio/.worktrees/codex/hybrid-contexts/tests/mc/test_architecture.py)
- [tests/mc/test_module_reorganization.py](/Users/ennio/Documents/nanobot-ennio/.worktrees/codex/hybrid-contexts/tests/mc/test_module_reorganization.py)
- [dashboard/tests/architecture.test.ts](/Users/ennio/Documents/nanobot-ennio/.worktrees/codex/hybrid-contexts/dashboard/tests/architecture.test.ts)

Current guardrails enforce:

- protected backend modules do not import `mc.gateway`
- runtime-facing modules do not import `mc.executor` directly
- canonical packages do not import root compatibility modules
- the `mc/` root is restricted to an allowlist of facade files
- top-level compatibility modules point to `runtime` or `contexts`
- dashboard feature components avoid direct Convex hooks where feature hooks exist
- dashboard hooks do not depend on UI components

## Design Rules

1. Runtime modules compose flows; contexts own behavior.
2. Shared rules belong in `domain`, not in runtime or UI.
3. Convex access stays behind `bridge`.
4. Environment and filesystem concerns stay in `infrastructure`.
5. `mc.application.execution` is a reusable kernel, not a competing architecture.
6. The `mc/` root is not an ownership layer.
7. Top-level compatibility shims may exist temporarily, but they are not architectural authority.
