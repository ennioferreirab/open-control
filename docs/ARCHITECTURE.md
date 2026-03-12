# Mission Control Architecture

## Purpose

This document describes the architecture of Mission Control as it exists today.
It is a reference for:

- navigating the codebase
- understanding ownership boundaries
- choosing canonical import paths
- deciding where new code should live
- reviewing changes for architectural regressions

The codebase has two main surfaces:

- the Python backend under `mc/`
- the Next.js dashboard under `dashboard/`

Both are tied together by a shared workflow contract in
`shared/workflow/workflow_spec.json`.

## High-Level Shape

The architecture is intentionally layered.

Backend:

```text
boot.py
  -> mc.cli
    -> mc.runtime
      -> mc.contexts.*
        -> mc.application.execution.*
        -> mc.domain.*
        -> mc.bridge.*
        -> mc.infrastructure.*
```

Dashboard:

```text
dashboard/app
  -> dashboard/components/DashboardLayout
    -> dashboard/features/*
      -> dashboard/components/ui
      -> dashboard/components/viewers
      -> dashboard/lib/*
      -> dashboard/convex/*
```

Shared contract:

```text
shared/workflow/workflow_spec.json
  -> mc/domain/workflow_contract.py
  -> dashboard/convex/lib/workflowContract.ts
```

The central rule is simple:

1. Runtime composes flows.
2. Contexts own behavior.
3. Shared rules live in dedicated shared layers.
4. UI components do not become data-access owners.

## Architectural Principles

### 1. Ownership is explicit

Each area of behavior should have a canonical owner.

Examples:

- task planning belongs to `mc.contexts.planning`
- thread and mention handling belong to `mc.contexts.conversation`
- task and step execution belong to `mc.contexts.execution`
- board, task, agent, thread, and settings UI flows belong to their respective
  dashboard features

### 2. Composition and behavior are separate

Runtime and layout modules are allowed to wire things together, but they should
not become the long-term home of business logic.

Examples:

- `mc.runtime.gateway` may start loops and services
- `mc.runtime.orchestrator` may delegate work
- `dashboard/components/DashboardLayout.tsx` may compose feature panels

But decisions, transformations, and workflow rules should live below those
layers.

### 3. Shared logic must be factored deliberately

Rules that are reused across flows should not be copied into runtime modules or
UI components. They should be placed in explicit shared layers:

- backend rules in `mc.domain`
- execution kernel behavior in `mc.application.execution`
- dashboard cross-feature helpers in `dashboard/lib`
- workflow invariants in the shared workflow spec and its generated adapters

### 4. Data access should not leak arbitrarily

The backend uses `mc.bridge` as the runtime-facing boundary to Convex.
The dashboard uses feature hooks as the component-facing boundary to Convex.

That means:

- backend business flows should prefer the bridge rather than raw SDK usage
- dashboard feature components should prefer feature hooks rather than direct
  `convex/react` calls

### 5. Canonical imports matter

Public package entrypoints exist to give stable, readable import paths.
When there is a canonical package import, it should be preferred over deep
legacy aliases or removed roots.

## Backend Architecture

## `mc/` at a Glance

The `mc/` package is organized by role, not by framework convention:

- `mc/runtime/`: composition roots and long-running coordination
- `mc/contexts/`: behavior owners by domain flow
- `mc/application/`: reusable orchestration kernels
- `mc/domain/`: pure and shared rules
- `mc/bridge/`: Convex-facing runtime data-access boundary
- `mc/infrastructure/`: filesystem, config, providers, orientation, validation
- `mc/hooks/`: backend hook registration and dispatch support
- `mc/memory/`: memory-oriented backend support code
- `mc/skills/`: skill-related backend support code

The `mc/` root itself is intentionally minimal. It is not an ownership layer.

### `mc.runtime`

`mc.runtime` is the backend composition layer.

Primary responsibilities:

- booting long-running services
- wiring process lifecycle
- coordinating polling and orchestration loops
- delegating runtime work to worker modules

Important modules:

- `mc.runtime.gateway`
- `mc.runtime.orchestrator`
- `mc.runtime.timeout_checker`
- `mc.runtime.polling_settings`
- `mc.runtime.cron_delivery`
- `mc.runtime.task_requeue`
- `mc.runtime.workers.*`

Public package API:

- `mc.runtime.TaskOrchestrator`
- `mc.runtime.TimeoutChecker`
- `mc.runtime.main`
- `mc.runtime.run_gateway`
- `mc.runtime.generate_title_via_low_agent`

Design rule:

- `mc.runtime` can coordinate work, but it should not absorb domain behavior
  that properly belongs to a context.

### `mc.contexts`

`mc.contexts` is the primary ownership layer for backend behavior.

Each subpackage owns a business flow, not just a technical abstraction.

#### `mc.contexts.planning`

Planning owns everything that happens before execution is materially started.

Responsibilities:

- building execution plans
- materializing plans into steps
- parsing and validating plan structures
- negotiating plan revisions
- title generation
- supervising plan negotiation loops

Key modules:

- `mc.contexts.planning.planner`
- `mc.contexts.planning.materializer`
- `mc.contexts.planning.parser`
- `mc.contexts.planning.negotiation`
- `mc.contexts.planning.title_generation`
- `mc.contexts.planning.supervisor`

Public package API:

- `mc.contexts.planning.TaskPlanner`
- `mc.contexts.planning.PlanMaterializer`
- `mc.contexts.planning.PlanNegotiationSupervisor`
- `mc.contexts.planning.handle_plan_negotiation`
- `mc.contexts.planning.start_plan_negotiation_loop`
- `mc.contexts.planning.generate_title_via_low_agent`

#### `mc.contexts.execution`

Execution owns task execution, step execution, provider-facing execution
plumbing, and execution-side crash handling.

Responsibilities:

- task execution entrypoints
- Claude Code execution
- step dispatch and execution routing
- provider error handling
- task message construction
- execution session key handling
- post-processing and crash recovery

Key modules:

- `mc.contexts.execution.executor`
- `mc.contexts.execution.cc_executor`
- `mc.contexts.execution.cc_step_runner`
- `mc.contexts.execution.step_dispatcher`
- `mc.contexts.execution.crash_recovery`
- `mc.contexts.execution.post_processing`
- `mc.contexts.execution.agent_runner`
- `mc.contexts.execution.message_builder`
- `mc.contexts.execution.provider_errors`
- `mc.contexts.execution.session_keys`

Public package API:

- `mc.contexts.execution.TaskExecutor`
- `mc.contexts.execution.StepDispatcher`
- `mc.contexts.execution.CCExecutorMixin`
- `mc.contexts.execution.execute_step_via_cc`
- `mc.contexts.execution.build_task_message`

#### `mc.contexts.conversation`

Conversation owns user-facing interaction and task-thread logic.

Responsibilities:

- thread context assembly for conversations
- chat handling and routing
- conversation intent resolution
- ask-user request handling
- mention handling and watching
- conversation-level workflow decisions

Key modules:

- `mc.contexts.conversation.chat_handler`
- `mc.contexts.conversation.service`
- `mc.contexts.conversation.intent`
- `mc.contexts.conversation.ask_user.*`
- `mc.contexts.conversation.mentions.*`

Public package API:

- `mc.contexts.conversation.ChatHandler`
- `mc.contexts.conversation.ConversationService`
- `mc.contexts.conversation.ConversationIntent`
- `mc.contexts.conversation.ConversationIntentResolver`
- `mc.contexts.conversation.ResolveResult`
- `mc.contexts.conversation.build_thread_context`

#### `mc.contexts.review`

Review owns feedback, approval, rejection, and review-state actions.

Responsibilities:

- review-state transitions
- approval and review handling
- rejection and return flows

Key module:

- `mc.contexts.review.handler`

Public package API:

- `mc.contexts.review.ReviewHandler`

#### `mc.contexts.agents`

Agents owns backend-side agent synchronization concerns.

Responsibilities:

- syncing agent registry and related backend views

Key module:

- `mc.contexts.agents.sync`

### `mc.application`

`mc.application` holds reusable orchestration kernels that are broader than a
single context file but still more concrete than pure domain logic.

Today the most important package here is `mc.application.execution`.

#### `mc.application.execution`

This package acts as the execution kernel shared by the execution context.

Responsibilities:

- execution request/result types
- execution engine coordination
- runner strategies
- execution runtime helpers
- thread context assembly used by execution flows
- background task support for execution-related work

Key modules:

- `mc.application.execution.engine`
- `mc.application.execution.runtime`
- `mc.application.execution.request`
- `mc.application.execution.thread_context`
- `mc.application.execution.background_tasks`
- `mc.application.execution.strategies.*`

Design rule:

- execution-specific reusable behavior should land here instead of being copied
  across context modules
- this package is a kernel, not a competing top-level ownership layer

### `mc.domain`

`mc.domain` is where shared rules belong when they are not runtime-specific and
not infrastructure-specific.

Responsibilities:

- workflow state machine and transition rules
- workflow contract adaptation
- reusable domain helpers and invariants

Key modules:

- `mc.domain.workflow.state_machine`
- `mc.domain.workflow_contract`
- `mc.domain.utils`

Design rule:

- if a rule is shared, stable, and not tied to process wiring, UI, or storage,
  it is a candidate for `mc.domain`

### `mc.bridge`

`mc.bridge` is the backend runtime-facing data-access boundary to Convex.

It is the public bridge API for the backend, and its implementation is split
across repositories and client helpers.

Responsibilities:

- adapting the Convex Python SDK
- exposing runtime-friendly query/mutation methods
- organizing storage operations by repository
- handling retry/backoff and key conversion
- coordinating subscriptions

Key internal areas:

- `mc.bridge.repositories.tasks`
- `mc.bridge.repositories.steps`
- `mc.bridge.repositories.messages`
- `mc.bridge.repositories.agents`
- `mc.bridge.repositories.boards`
- `mc.bridge.repositories.chats`
- `mc.bridge.repositories.settings`
- `mc.bridge.subscriptions`
- `mc.bridge.retry`
- `mc.bridge.key_conversion`

Public entrypoint:

- `mc.bridge.ConvexBridge`

Design rule:

- backend code should prefer the bridge API over importing the Convex SDK
  directly

### `mc.infrastructure`

`mc.infrastructure` holds environment-specific and framework-specific support.

Responsibilities:

- filesystem and path conventions
- provider construction
- model tier resolution
- orientation loading
- board environment helpers
- agent YAML validation and related filesystem concerns

Representative modules:

- `mc.infrastructure.boards`
- `mc.infrastructure.orientation`
- `mc.infrastructure.agents.yaml_validator`
- `mc.infrastructure.providers.factory`
- `mc.infrastructure.providers.tier_resolver`

Design rule:

- if the code is about environment, files, config, providers, or external
  integration mechanics, it belongs here rather than in a context or domain

### Other backend support packages

These packages exist, but they are not equivalent to the primary ownership
layers above:

- `mc.hooks`
  - hook registration and handler support
- `mc.memory`
  - memory-related backend support code
- `mc.skills`
  - backend support around skills and distribution concerns

They should not become dumping grounds for unrelated business behavior.

## Dashboard Architecture

The dashboard is organized around feature ownership, with a small shell layer
and explicit shared UI primitives.

## Dashboard Layers

### `dashboard/app`

`dashboard/app` owns routing and route handlers.

Responsibilities:

- page entrypoints
- route handlers under `app/api`
- app-wide metadata and global CSS

Examples:

- `dashboard/app/page.tsx`
- `dashboard/app/layout.tsx`
- `dashboard/app/login/*`
- `dashboard/app/api/*`
- `dashboard/app/favicon.ico/*`

Design rule:

- `app/` should stay thin; feature behavior should move into features, shared
  components, or backend routes as appropriate

### `dashboard/components/DashboardLayout.tsx`

`DashboardLayout` is the composition shell for the main application surface.

Responsibilities:

- composing sidebars, boards, task detail sheet, settings and activity panels
- managing shell-level local UI state
- connecting the board provider to feature entrypoints

It is intentionally a shell, not the owner of task, board, agent, or thread
behavior.

### `dashboard/features`

`dashboard/features` is the primary ownership layer for dashboard workflows.

Placement rules are documented in `dashboard/features/README.md`.

Each feature may contain:

- `components/`: feature-specific UI
- `hooks/`: feature orchestration, query, mutation, and view-model hooks
- `lib/`: feature-local pure helpers

Current feature packages:

- `dashboard/features/tasks`
- `dashboard/features/boards`
- `dashboard/features/agents`
- `dashboard/features/thread`
- `dashboard/features/activity`
- `dashboard/features/search`
- `dashboard/features/settings`
- `dashboard/features/terminal`

#### `dashboard/features/tasks`

Owns task-centric UI and task detail workflows.

Responsibilities:

- task input
- task cards and step cards
- execution plan interaction
- task detail sheet and its tabs
- file attachment flows
- task tag editing
- task action hooks

Representative components:

- `TaskInput`
- `TaskCard`
- `StepCard`
- `ExecutionPlanTab`
- `TaskDetailSheet`
- `TaskDetailThreadTab`
- `TaskDetailConfigTab`
- `TaskDetailFilesTab`
- `PlanReviewPanel`

Representative hooks:

- `useTaskInputData`
- `useTaskDetailView`
- `useTaskDetailActions`
- `useExecutionPlanActions`
- `usePlanEditorState`
- `useStepCardActions`
- `useTaskCardActions`
- `useStepFileAttachmentActions`
- `useTagAttributeEditorActions`
- `useTrashBinSheetData`
- `useDoneTasksSheetData`
- `useFavoriteTask`
- `useInlineRejectionActions`

#### `dashboard/features/boards`

Owns board-level views and board-scoped settings.

Responsibilities:

- kanban board composition
- board columns and filtering
- board settings
- board selection
- board-provider-facing view hooks

Representative components:

- `KanbanBoard`
- `BoardSettingsSheet`

Representative hooks:

- `useBoardView`
- `useBoardColumns`
- `useBoardFilters`
- `useBoardSettingsSheet`
- `useBoardSelectorData`
- `useBoardProviderData`
- `useKanbanColumnInteractions`

#### `dashboard/features/agents`

Owns agent-specific UI and agent-facing workflows.

Responsibilities:

- sidebar of agents
- agent config sheet
- agent chat panel state
- create-agent interactions
- skill catalog loading for agent configuration

Representative components:

- `AgentSidebar`
- `AgentSidebarItem`
- `AgentConfigSheet`

Representative hooks:

- `useAgentSidebarData`
- `useAgentSidebarItemState`
- `useAgentConfigSheetData`
- `useAgentChatMessages`
- `useAgentChatPanel`
- `useCreateAgentSheetActions`
- `useSkillsCatalog`

#### `dashboard/features/thread`

Owns task-thread interaction UI and thread input behavior.

Responsibilities:

- thread message rendering
- thread input orchestration
- mention navigation helpers

Representative components:

- `ThreadInput`
- `ThreadMessage`

Representative hooks and libs:

- `useThreadInputController`
- `lib/mentionNavigation`

Note:

- the older shared hook `dashboard/hooks/useThreadComposer.ts` still exists as a
  reusable hook and is covered by tests, but feature-facing task-thread input is
  orchestrated through `features/thread`

#### `dashboard/features/activity`

Owns activity feed presentation.

Responsibilities:

- activity feed list
- activity panel state

Representative modules:

- `ActivityFeed`
- `ActivityFeedPanel`
- `useActivityFeed`
- `useActivityFeedPanelState`

#### `dashboard/features/search`

Owns search UI and search filter parsing at the feature layer.

Responsibilities:

- search bar rendering
- search feature hook state

Representative modules:

- `SearchBar`
- `useSearchBarFilters`

#### `dashboard/features/settings`

Owns global settings and tag/settings panels.

Responsibilities:

- settings panel state
- model tier settings
- tag management
- gateway sleep mode requests

Representative modules:

- `SettingsPanel`
- `TagsPanel`
- `ModelTierSettings`
- `useSettingsPanelState`
- `useTagsPanelData`
- `useModelTierSettings`
- `useGatewaySleepModeRequest`

#### `dashboard/features/terminal`

Owns remote terminal views.

Responsibilities:

- terminal board composition
- terminal panel state

Representative modules:

- `TerminalBoard`
- `useTerminalBoard`
- `useTerminalPanelState`

### `dashboard/components`

`dashboard/components` is not the primary feature ownership layer, but it is
still important.

It currently serves three roles:

1. shared widgets used by multiple features
2. shell/support components that are not owned by a single feature
3. low-level view components that are not feature-specific

Examples:

- `DashboardLayout`
- `BoardContext`
- `BoardSelector`
- `CronJobsModal`
- `DocumentViewerModal`
- `PromptEditModal`
- `AgentTextViewerModal`
- `TaskGroupHeader`
- `FileChip`
- `AgentMentionAutocomplete`
- `MarkdownRenderer`
- `ArtifactRenderer`

This folder should contain clearly shared modules, not feature-specific owners
that merely happen to be reused once.

Notably, feature entry-point aliases such as root-level `TaskDetailSheet`,
`TaskInput`, `TaskCard`, `SearchBar`, `TagsPanel`, `AgentConfigSheet`, and
similar wrappers should not live here. Those owners now import directly from
`dashboard/features/*`.

### `dashboard/hooks`

`dashboard/hooks` is a curated shared-hook layer, not a mirror of the feature
tree.

Keep hooks here only when they are genuinely cross-feature or app-shell scoped.

Examples:

- `useBoardColumns`
- `useBoardFilters`
- `useSelectableAgents`
- `useGatewaySleepRuntime`
- `useThreadComposer`
- `useDocumentFetch`

Do not reintroduce deleted feature hook aliases such as `useTaskDetailView`,
`useTaskInputData`, `useBoardView`, or `useThreadInputController` at the root.
Those belong under their owning feature.

### `dashboard/components/ui`

This directory contains reusable UI primitives and wrappers.

Examples:

- dialog/sheet/popover primitives
- buttons, inputs, selects, tabs, switches
- avatar, badges, labels, separators, scroll areas
- sidebar primitives

These are not business owners. They are rendering primitives.

### `dashboard/components/viewers`

This directory contains reusable content viewers.

Examples:

- `MarkdownViewer`
- `HtmlViewer`
- `PdfViewer`
- `ImageViewer`

These are intentionally shared presentation modules.

### `dashboard/lib`

`dashboard/lib` holds cross-feature helpers and client-side support utilities.

Responsibilities:

- parsing and utility helpers
- runtime helpers shared by shell/features
- shared TS types and view helpers
- Convex provider wrapper at `dashboard/lib/convex/provider.tsx`

Representative modules:

- `searchParser`
- `cron-parser`
- `flowLayout`
- `planUtils`
- `gatewaySleepRuntime`
- `chatSyncRuntime`
- `lib/convex/provider.tsx`

### `dashboard/convex`

`dashboard/convex` contains Convex functions, schema, and query/mutation
behavior for the dashboard backend.

Representative modules:

- `tasks.ts`
- `steps.ts`
- `messages.ts`
- `boards.ts`
- `agents.ts`
- `settings.ts`
- `schema.ts`
- `convex/lib/*`

`dashboard/convex/lib` is where reusable Convex-side domain helpers live for:

- lifecycle transitions
- workflow helpers
- read models
- thread rules
- workflow contract helpers

This layer is the dashboard-side backend, not just a frontend helper folder.

## Shared Workflow Contract

The shared workflow contract is defined in:

- `shared/workflow/workflow_spec.json`

Its job is to keep backend and dashboard aligned on:

- task statuses
- step statuses
- allowed transitions
- workflow action mappings
- workflow-specific message semantics

Consumers:

- backend: `mc/domain/workflow_contract.py`
- dashboard: `dashboard/convex/lib/workflowContract.ts`

If workflow rules change, they should change here first, then propagate through
the adapters.

## Canonical Imports

Preferred backend imports:

- `from mc.runtime import TaskOrchestrator, run_gateway`
- `from mc.contexts.planning import TaskPlanner, PlanMaterializer`
- `from mc.contexts.execution import TaskExecutor, StepDispatcher`
- `from mc.contexts.conversation import ChatHandler, ConversationService`
- `from mc.contexts.review import ReviewHandler`
- `from mc.bridge import ConvexBridge`

Preferred dashboard imports:

- pages and shell import feature entrypoints from `dashboard/features/*`
- feature components import feature hooks and shared UI primitives
- feature hooks import `convex/`, feature-local helpers, and cross-feature
  helpers from `dashboard/lib`

Avoid:

- removed root backend aliases such as `mc.executor`, `mc.gateway`,
  `mc.planner`, `mc.ask_user`, `mc.mentions`, `mc.services`, `mc.workers`
- dashboard feature components importing `convex/react` directly when a feature
  hook should own that access
- dashboard hooks importing feature UI components

## Main Runtime and UI Flows

### Backend task flow

At a high level:

1. runtime/orchestrator picks up task work
2. planning context shapes and negotiates plans when needed
3. execution context executes tasks and steps
4. conversation and review contexts respond to user and review actions
5. bridge persists state and events in Convex

### Conversation flow

Conversation-related work typically flows like this:

1. thread state is assembled
2. chat handler receives or routes input
3. intent resolution decides whether the flow is normal chat, plan chat,
   mention-driven, or ask-user-related
4. bridge and workflow rules persist the resulting state changes

### Dashboard task detail flow

Task detail UI typically flows like this:

1. `DashboardLayout` opens a task by setting `selectedTaskId`
2. `features/tasks/components/TaskDetailSheet` becomes the owner of the detail
   experience
3. `useTaskDetailView` provides read models and display state
4. `useTaskDetailActions` and more focused task hooks provide mutations/actions
5. tab-specific components render thread, config, files, and execution plan
   views

### Dashboard board flow

Board interaction typically flows like this:

1. `BoardProvider` owns board-scoped app state
2. `BoardSelector` and board feature hooks drive active board changes
3. `KanbanBoard` and board hooks derive columns, filters, and interactions
4. task clicks open the task detail sheet

## Guardrails and Enforcement

Architecture rules are enforced by tests, not only by convention.

Backend guardrails:

- `tests/mc/test_architecture.py`
- `tests/mc/test_module_reorganization.py`
- `tests/mc/infrastructure/test_boundary.py`

Dashboard guardrails:

- `dashboard/tests/architecture.test.ts`

What these guardrails enforce today:

- foundation backend modules do not import `mc.runtime.gateway`
- protected backend layers do not depend on removed root modules
- runtime-facing backend modules do not reach into private execution internals
  arbitrarily
- `mc.bridge` owns the public bridge API directly
- the backend root stays minimal
- removed legacy backend packages remain deleted
- dashboard feature directories and canonical entrypoints exist
- removed wrapper files stay deleted
- dashboard feature components avoid direct `convex/react` imports
- dashboard hooks do not import feature UI components
- dashboard feature owners do not import removed root hook aliases

## Current Boundaries and Expectations

When adding new backend code:

- put orchestration in `runtime` only if it is truly runtime composition
- put business behavior in the appropriate `contexts/*`
- put reusable execution orchestration in `application/execution`
- put pure rules in `domain`
- put storage access in `bridge`
- put environment/provider/filesystem concerns in `infrastructure`

When adding new dashboard code:

- put workflow-specific behavior under the owning `features/<feature>/`
- put shared widgets in `components/` only if they are genuinely cross-feature
- put UI primitives in `components/ui`
- put reusable viewers in `components/viewers`
- keep feature components free of direct `convex/react` usage unless the
  architecture tests explicitly allow it

## Anti-Patterns

The following are considered regressions:

1. Reintroducing removed backend root aliases or legacy packages.
2. Letting runtime modules become owners of business rules.
3. Adding direct Convex SDK usage outside `mc.bridge` on the backend.
4. Adding direct `convex/react` calls to dashboard feature components.
5. Importing feature UI components from hooks.
6. Recreating wrapper files that obscure real ownership.
7. Duplicating workflow rules instead of using the shared contract.

## Summary

Mission Control is organized around explicit ownership:

- backend runtime composes
- backend contexts own behavior
- shared backend layers hold reusable logic, storage access, and infrastructure
- dashboard features own workflow-specific UI and hooks
- shared UI and viewer layers stay generic
- a shared workflow contract keeps both sides aligned

The architecture is healthiest when new code respects those ownership lines and
uses the guardrails as hard boundaries rather than optional guidance.
