# Database Schema Reference

Convex schema defined in `dashboard/convex/schema.ts`. All 26 tables with fields, types, and indexes.

For how these tables relate to runtime services, see [`service_architecture.md`](service_architecture.md). For field naming conventions across layers, see [`code_conventions/cross_service_naming.md`](code_conventions/cross_service_naming.md).

---

## Core Task Execution

### `boards`

Task organization containers (kanban-like).

| Field | Type | Notes |
|-------|------|-------|
| `name` | `v.string()` | Kebab-case unique name |
| `displayName` | `v.string()` | |
| `description` | `v.optional(v.string())` | |
| `enabledAgents` | `v.array(v.string())` | Agent names enabled for this board |
| `agentMemoryModes` | `v.optional(v.array(v.object({...})))` | Per-agent `"clean"` or `"with_history"` |
| `isDefault` | `v.optional(v.boolean())` | |
| `createdAt` | `v.string()` | ISO 8601 |
| `updatedAt` | `v.string()` | ISO 8601 |
| `deletedAt` | `v.optional(v.string())` | Soft delete |

**Indexes:** `by_name` `["name"]`, `by_isDefault` `["isDefault"]`

---

### `tasks`

Core task records with status lifecycle and execution plans.

| Field | Type | Notes |
|-------|------|-------|
| `title` | `v.string()` | |
| `description` | `v.optional(v.string())` | |
| `status` | `taskStatusValidator` | `ready\|inbox\|assigned\|in_progress\|review\|done\|failed\|retrying\|crashed\|deleted` |
| `assignedAgent` | `v.optional(v.string())` | |
| `trustLevel` | `v.union("autonomous", "human_approved")` | |
| `reviewers` | `v.optional(v.array(v.string()))` | |
| `tags` | `v.optional(v.array(v.string()))` | |
| `taskTimeout` | `v.optional(v.number())` | Milliseconds |
| `interAgentTimeout` | `v.optional(v.number())` | Milliseconds |
| `executionPlan` | `v.optional(v.any())` | Polymorphic plan shape |
| `supervisionMode` | `v.optional(v.union("autonomous", "supervised"))` | |
| `stalledAt` | `v.optional(v.string())` | |
| `isManual` | `v.optional(v.boolean())` | |
| `isFavorite` | `v.optional(v.boolean())` | |
| `autoTitle` | `v.optional(v.boolean())` | |
| `awaitingKickoff` | `v.optional(v.boolean())` | Supervised task pending approval |
| `reviewPhase` | `v.optional(v.union("plan_review", "execution_pause", "final_approval"))` | |
| `stateVersion` | `v.optional(v.number())` | Optimistic concurrency |
| `deletedAt` | `v.optional(v.string())` | Soft delete |
| `previousStatus` | `v.optional(v.string())` | For restore |
| `activeCronJobId` | `v.optional(v.string())` | Parent cron job |
| `boardId` | `v.optional(v.id("boards"))` | |
| `cronParentTaskId` | `v.optional(v.string())` | |
| `sourceAgent` | `v.optional(v.string())` | |
| `isMergeTask` | `v.optional(v.boolean())` | |
| `mergeSourceTaskIds` | `v.optional(v.array(v.id("tasks")))` | |
| `mergeSourceLabels` | `v.optional(v.array(v.string()))` | |
| `mergedIntoTaskId` | `v.optional(v.id("tasks"))` | Reverse ref |
| `mergePreviousStatus` | `v.optional(v.string())` | |
| `mergeLockedAt` | `v.optional(v.string())` | |
| `files` | `taskFilesValidator` | `v.optional(v.array(taskFileMetadataValidator))` |
| `workMode` | `v.optional(workModeValidator)` | `"direct_delegate"` or `"ai_workflow"` |
| `routingMode` | `v.optional(routingModeValidator)` | `"lead_agent"`, `"workflow"`, or `"human"` |
| `routingDecision` | `v.optional(v.any())` | |
| `squadSpecId` | `v.optional(v.id("squadSpecs"))` | |
| `workflowSpecId` | `v.optional(v.id("workflowSpecs"))` | |
| `createdAt` | `v.string()` | |
| `updatedAt` | `v.string()` | |

**Indexes:** `by_status` `["status"]`, `by_boardId` `["boardId"]`
**Search indexes:** `search_title` on `"title"` filter `["boardId"]`, `search_description` on `"description"` filter `["boardId"]`

---

### `steps`

Sub-steps within tasks, with dependencies and parallel groups.

| Field | Type | Notes |
|-------|------|-------|
| `taskId` | `v.id("tasks")` | |
| `title` | `v.string()` | |
| `description` | `v.string()` | |
| `assignedAgent` | `v.string()` | Agent name or `"human"` |
| `status` | `stepStatusValidator` | `planned\|assigned\|running\|review\|completed\|crashed\|blocked\|waiting_human\|deleted` |
| `blockedBy` | `v.optional(v.array(v.id("steps")))` | Dependency list |
| `parallelGroup` | `v.number()` | |
| `order` | `v.number()` | Sequence within task |
| `stateVersion` | `v.optional(v.number())` | Optimistic concurrency |
| `createdAt` | `v.string()` | |
| `deletedAt` | `v.optional(v.string())` | |
| `startedAt` | `v.optional(v.string())` | |
| `completedAt` | `v.optional(v.string())` | |
| `errorMessage` | `v.optional(v.string())` | |
| `attachedFiles` | `v.optional(v.array(v.string()))` | |
| `workflowStepId` | `v.optional(v.string())` | Ref to workflow spec step |
| `workflowStepType` | `v.optional(workflowStepTypeValidator)` | `agent\|human\|checkpoint\|review\|system` |
| `agentId` | `v.optional(v.id("agents"))` | |
| `reviewSpecId` | `v.optional(v.id("reviewSpecs"))` | |
| `onRejectStepId` | `v.optional(v.string())` | Fallback on rejection |

**Indexes:** `by_taskId` `["taskId"]`, `by_status` `["status"]`

---

### `messages`

Unified task thread for all communication.

| Field | Type | Notes |
|-------|------|-------|
| `taskId` | `v.id("tasks")` | |
| `stepId` | `v.optional(v.id("steps"))` | |
| `authorName` | `v.string()` | |
| `authorType` | `v.union("agent", "user", "system")` | |
| `content` | `v.string()` | |
| `messageType` | `v.union(...)` | Legacy: `work\|review_feedback\|approval\|denial\|system_event\|user_message\|comment` |
| `type` | `v.optional(v.union(...))` | New: `step_completion\|user_message\|system_error\|lead_agent_plan\|lead_agent_chat\|comment` |
| `artifacts` | `v.optional(v.array(v.object({...})))` | `{path, action: created\|modified\|deleted, description?, diff?}` |
| `fileAttachments` | `v.optional(v.array(v.object({...})))` | `{name, type, size}` |
| `planReview` | `v.optional(v.object({...}))` | `{kind: request\|feedback\|decision, planGeneratedAt, decision?}` |
| `leadAgentConversation` | `v.optional(v.boolean())` | |
| `timestamp` | `v.string()` | |

**Indexes:** `by_taskId` `["taskId"]`, `by_authorType_timestamp` `["authorType", "timestamp"]`

---

### `activities`

Event log for all system state changes.

| Field | Type | Notes |
|-------|------|-------|
| `taskId` | `v.optional(v.id("tasks"))` | |
| `agentName` | `v.optional(v.string())` | |
| `eventType` | `activityEventTypeValidator` | See `cross_service_naming.md` |
| `description` | `v.string()` | |
| `timestamp` | `v.string()` | |

**Indexes:** `by_taskId` `["taskId"]`, `by_timestamp` `["timestamp"]`

---

## Agent & Runtime

### `agents`

Agent registry with config, status, and metrics.

| Field | Type | Notes |
|-------|------|-------|
| `name` | `v.string()` | Unique identifier |
| `displayName` | `v.string()` | |
| `role` | `v.string()` | |
| `prompt` | `v.optional(v.string())` | |
| `soul` | `v.optional(v.string())` | |
| `skills` | `v.array(v.string())` | |
| `status` | `agentStatusValidator` | `active\|idle\|crashed` |
| `enabled` | `v.optional(v.boolean())` | |
| `isSystem` | `v.optional(v.boolean())` | |
| `model` | `v.optional(v.string())` | Tier reference or concrete model |
| `reasoningLevel` | `v.optional(v.string())` | |
| `interactiveProvider` | `v.optional(interactiveProviderValidator)` | |
| `claudeCodeOpts` | `v.optional(v.object({...}))` | `{permissionMode?, maxBudgetUsd?, maxTurns?}` |
| `variables` | `v.optional(v.array(v.object({...})))` | `{name, value}` |
| `tasksExecuted` | `v.optional(v.number())` | |
| `stepsExecuted` | `v.optional(v.number())` | |
| `lastTaskExecutedAt` | `v.optional(v.string())` | |
| `lastStepExecutedAt` | `v.optional(v.string())` | |
| `lastActiveAt` | `v.optional(v.string())` | |
| `deletedAt` | `v.optional(v.string())` | Soft delete |
| `memoryContent` | `v.optional(v.string())` | Archived memory |
| `historyContent` | `v.optional(v.string())` | Archived history |
| `sessionData` | `v.optional(v.string())` | Archived session |
| `compiledFromSpecId` | `v.optional(v.string())` | |
| `compiledFromVersion` | `v.optional(v.number())` | |
| `compiledAt` | `v.optional(v.string())` | |

**Indexes:** `by_name` `["name"]`, `by_status` `["status"]`

---

### `skills`

Reusable skill definitions.

| Field | Type | Notes |
|-------|------|-------|
| `name` | `v.string()` | |
| `description` | `v.string()` | |
| `content` | `v.string()` | Markdown content |
| `metadata` | `v.optional(v.string())` | |
| `source` | `v.union("builtin", "workspace")` | |
| `supportedProviders` | `v.optional(v.array(skillProviderValidator))` | |
| `always` | `v.optional(v.boolean())` | Always-on skill |
| `available` | `v.boolean()` | |
| `requires` | `v.optional(v.string())` | |

**Indexes:** `by_name` `["name"]`

---

### `settings`

Global key-value configuration.

| Field | Type |
|-------|------|
| `key` | `v.string()` |
| `value` | `v.string()` |

**Indexes:** `by_key` `["key"]`

---

### `chats`

Agent-to-user direct chat messages.

| Field | Type | Notes |
|-------|------|-------|
| `agentName` | `v.string()` | |
| `authorName` | `v.string()` | |
| `authorType` | `v.union("user", "agent")` | |
| `content` | `v.string()` | |
| `status` | `v.optional(v.union("pending", "processing", "done"))` | |
| `timestamp` | `v.string()` | |

**Indexes:** `by_agentName` `["agentName"]`, `by_status` `["status"]`, `by_timestamp` `["timestamp"]`

---

## Concurrency & Reliability

### `runtimeClaims`

Distributed lease-based locking.

| Field | Type | Notes |
|-------|------|-------|
| `claimKind` | `v.string()` | |
| `entityType` | `v.string()` | |
| `entityId` | `v.string()` | |
| `ownerId` | `v.string()` | |
| `leaseExpiresAt` | `v.string()` | |
| `metadata` | `v.optional(v.any())` | |
| `createdAt` | `v.string()` | |
| `updatedAt` | `v.string()` | |

**Indexes:** `by_claimKey` `["claimKind", "entityType", "entityId"]`, `by_leaseExpiresAt` `["leaseExpiresAt"]`

---

### `runtimeReceipts`

Mutation idempotency tracking.

| Field | Type | Notes |
|-------|------|-------|
| `idempotencyKey` | `v.string()` | |
| `scope` | `v.string()` | e.g., `"messages:create"` |
| `entityType` | `v.optional(v.string())` | |
| `entityId` | `v.optional(v.string())` | |
| `response` | `v.any()` | Cached mutation response |
| `createdAt` | `v.string()` | |
| `updatedAt` | `v.string()` | |

**Indexes:** `by_idempotencyKey` `["idempotencyKey"]`

---

## Execution & Interaction

### `executionSessions`

Session records for agent execution runs.

| Field | Type | Notes |
|-------|------|-------|
| `sessionId` | `v.string()` | |
| `taskId` | `v.id("tasks")` | |
| `stepId` | `v.optional(v.id("steps"))` | |
| `agentName` | `v.string()` | |
| `provider` | `v.string()` | |
| `state` | `executionInteractionStateValidator` | |
| `lastProgressMessage` | `v.optional(v.string())` | |
| `lastProgressPercentage` | `v.optional(v.number())` | |
| `finalResult` | `v.optional(v.string())` | |
| `finalResultSource` | `v.optional(v.string())` | |
| `createdAt` | `v.string()` | |
| `updatedAt` | `v.string()` | |
| `completedAt` | `v.optional(v.string())` | |
| `crashedAt` | `v.optional(v.string())` | |

**Indexes:** `by_sessionId` `["sessionId"]`, `by_taskId` `["taskId"]`, `by_stepId` `["stepId"]`, `by_taskId_state` `["taskId", "state"]`

---

### `executionInteractions`

Sequence of interactions within a session.

| Field | Type | Notes |
|-------|------|-------|
| `sessionId` | `v.string()` | |
| `taskId` | `v.id("tasks")` | |
| `stepId` | `v.optional(v.id("steps"))` | |
| `seq` | `v.number()` | Sequence number |
| `kind` | `v.string()` | |
| `payload` | `v.optional(v.any())` | |
| `createdAt` | `v.string()` | |
| `agentName` | `v.optional(v.string())` | |
| `provider` | `v.optional(v.string())` | |

**Indexes:** `by_sessionId_seq` `["sessionId", "seq"]`, `by_taskId` `["taskId"]`

---

### `executionQuestions`

User input questions raised during execution.

| Field | Type | Notes |
|-------|------|-------|
| `questionId` | `v.string()` | |
| `sessionId` | `v.string()` | |
| `taskId` | `v.id("tasks")` | |
| `stepId` | `v.optional(v.id("steps"))` | |
| `agentName` | `v.string()` | |
| `provider` | `v.string()` | |
| `question` | `v.optional(v.string())` | |
| `options` | `v.optional(v.array(v.string()))` | |
| `questions` | `v.optional(v.any())` | |
| `status` | `v.union("pending", "answered", "cancelled", "expired")` | |
| `answer` | `v.optional(v.string())` | |
| `createdAt` | `v.string()` | |
| `answeredAt` | `v.optional(v.string())` | |

**Indexes:** `by_questionId` `["questionId"]`, `by_taskId_status` `["taskId", "status"]`, `by_sessionId_status` `["sessionId", "status"]`

---

### `interactiveSessions`

Live interactive session metadata with control mode.

| Field | Type | Notes |
|-------|------|-------|
| `sessionId` | `v.string()` | |
| `agentName` | `v.string()` | |
| `provider` | `v.string()` | |
| `scopeKind` | `interactiveSessionScopeKindValidator` | |
| `scopeId` | `v.optional(v.string())` | |
| `surface` | `v.string()` | |
| `tmuxSession` | `v.string()` | |
| `status` | `interactiveSessionStatusValidator` | |
| `capabilities` | `v.array(interactiveSessionCapabilityValidator)` | |
| `attachToken` | `v.optional(v.string())` | |
| `createdAt` | `v.string()` | |
| `updatedAt` | `v.string()` | |
| `lastActiveAt` | `v.optional(v.string())` | |
| `endedAt` | `v.optional(v.string())` | |
| `taskId` | `v.optional(v.string())` | |
| `stepId` | `v.optional(v.string())` | |
| `supervisionState` | `v.optional(v.string())` | |
| `activeTurnId` | `v.optional(v.string())` | |
| `activeItemId` | `v.optional(v.string())` | |
| `lastEventKind` | `v.optional(v.string())` | |
| `lastEventAt` | `v.optional(v.string())` | |
| `lastError` | `v.optional(v.string())` | |
| `summary` | `v.optional(v.string())` | |
| `finalResult` | `v.optional(v.string())` | |
| `finalResultSource` | `v.optional(v.string())` | |
| `finalResultAt` | `v.optional(v.string())` | |
| `controlMode` | `v.optional(interactiveSessionControlModeValidator)` | `agent\|human` |
| `manualTakeoverAt` | `v.optional(v.string())` | |
| `manualCompletionRequestedAt` | `v.optional(v.string())` | |
| `bootstrapPrompt` | `v.optional(v.string())` | |
| `providerSessionId` | `v.optional(v.string())` | |
| `lastControlCommand` | `v.optional(v.string())` | |
| `lastControlOutcome` | `v.optional(v.string())` | |
| `lastControlError` | `v.optional(v.string())` | |

**Indexes:** `by_sessionId` `["sessionId"]`, `by_agentName` `["agentName"]`, `by_provider` `["provider"]`, `by_status` `["status"]`

---

### `sessionActivityLog`

Session-level event log for interactive sessions.

| Field | Type | Notes |
|-------|------|-------|
| `sessionId` | `v.string()` | |
| `seq` | `v.number()` | |
| `kind` | `v.string()` | |
| `ts` | `v.string()` | |
| `toolName` | `v.optional(v.string())` | |
| `toolInput` | `v.optional(v.string())` | |
| `filePath` | `v.optional(v.string())` | |
| `summary` | `v.optional(v.string())` | |
| `error` | `v.optional(v.string())` | |
| `turnId` | `v.optional(v.string())` | |
| `itemId` | `v.optional(v.string())` | |
| `stepId` | `v.optional(v.string())` | |
| `agentName` | `v.optional(v.string())` | |
| `provider` | `v.optional(v.string())` | |
| `requiresAction` | `v.optional(v.boolean())` | |

**Indexes:** `by_session` `["sessionId"]`, `by_session_seq` `["sessionId", "seq"]`

---

### `terminalSessions`

Remote terminal agent session state.

| Field | Type | Notes |
|-------|------|-------|
| `sessionId` | `v.string()` | |
| `output` | `v.string()` | Current screen content |
| `updatedAt` | `v.string()` | |
| `pendingInput` | `v.optional(v.string())` | Input waiting to be sent |
| `status` | `v.optional(v.union("idle", "processing", "error"))` | |
| `agentName` | `v.optional(v.string())` | |
| `sleepMode` | `v.optional(v.boolean())` | |
| `wakeSignal` | `v.optional(v.boolean())` | |

**Indexes:** `by_sessionId` `["sessionId"]`, `by_agentName` `["agentName"]`

---

## Specs & Templates

### `agentSpecs`

Agent specification templates (draft → published → archived).

| Field | Type | Notes |
|-------|------|-------|
| `name` | `v.string()` | |
| `displayName` | `v.string()` | |
| `role` | `v.string()` | |
| `purpose` | `v.optional(v.string())` | |
| `nonGoals` | `v.optional(v.array(v.string()))` | |
| `responsibilities` | `v.optional(v.array(v.string()))` | |
| `principles` | `v.optional(v.array(v.string()))` | |
| `workingStyle` | `v.optional(v.string())` | |
| `qualityRules` | `v.optional(v.array(v.string()))` | |
| `antiPatterns` | `v.optional(v.array(v.string()))` | |
| `outputContract` | `v.optional(v.string())` | |
| `toolPolicy` | `v.optional(v.string())` | |
| `memoryPolicy` | `v.optional(v.string())` | |
| `executionPolicy` | `v.optional(v.string())` | |
| `reviewPolicyRef` | `v.optional(v.string())` | |
| `skills` | `v.optional(v.array(v.string()))` | |
| `model` | `v.optional(v.string())` | |
| `status` | `v.union("draft", "published", "archived")` | |
| `version` | `v.number()` | |
| `compiledAgentId` | `v.optional(v.id("agents"))` | |
| `compiledAt` | `v.optional(v.string())` | |
| `createdAt` | `v.string()` | |
| `updatedAt` | `v.string()` | |

**Indexes:** `by_name` `["name"]`, `by_status` `["status"]`

---

### `squadSpecs`

Squad specification templates defining teams of agents.

| Field | Type | Notes |
|-------|------|-------|
| `name` | `v.string()` | |
| `displayName` | `v.string()` | |
| `description` | `v.optional(v.string())` | |
| `outcome` | `v.optional(v.string())` | |
| `reviewPolicy` | `v.optional(v.string())` | |
| `agentIds` | `v.optional(v.array(v.id("agents")))` | |
| `agentSpecIds` | `v.optional(v.array(v.id("agentSpecs")))` | |
| `defaultWorkflowSpecId` | `v.optional(v.id("workflowSpecs"))` | |
| `status` | `v.union("draft", "published", "archived")` | |
| `version` | `v.number()` | |
| `tags` | `v.optional(v.array(v.string()))` | |
| `publishedAt` | `v.optional(v.string())` | |
| `createdAt` | `v.string()` | |
| `updatedAt` | `v.string()` | |

**Indexes:** `by_name` `["name"]`, `by_status` `["status"]`

---

### `workflowSpecs`

Workflow templates defining step sequences with dependencies.

| Field | Type | Notes |
|-------|------|-------|
| `squadSpecId` | `v.id("squadSpecs")` | Parent squad |
| `name` | `v.string()` | |
| `description` | `v.optional(v.string())` | |
| `steps` | `v.array(v.object({...}))` | `{id, title, type, agentId?, agentSpecId?, reviewSpecId?, description?, inputs?, outputs?, dependsOn?, onReject?}` |
| `exitCriteria` | `v.optional(v.string())` | |
| `executionPolicy` | `v.optional(v.string())` | |
| `reviewSpecId` | `v.optional(v.id("reviewSpecs"))` | |
| `onRejectDefault` | `v.optional(v.string())` | |
| `onReject` | `v.optional(v.object({...}))` | `{returnToStep, maxRetries?}` |
| `status` | `v.union("draft", "published", "archived")` | |
| `version` | `v.number()` | |
| `publishedAt` | `v.optional(v.string())` | |
| `createdAt` | `v.string()` | |
| `updatedAt` | `v.string()` | |

**Indexes:** `by_squadSpecId` `["squadSpecId"]`, `by_status` `["status"]`

---

### `reviewSpecs`

Review criteria and approval thresholds.

| Field | Type | Notes |
|-------|------|-------|
| `name` | `v.string()` | |
| `scope` | `v.union("agent", "workflow", "execution")` | |
| `criteria` | `v.array(v.object({...}))` | `{id, label, weight, description?}` |
| `vetoConditions` | `v.optional(v.array(v.string()))` | |
| `approvalThreshold` | `v.number()` | |
| `feedbackContract` | `v.optional(v.string())` | |
| `reviewerPolicy` | `v.optional(v.string())` | |
| `rejectionRoutingPolicy` | `v.optional(v.string())` | |
| `status` | `v.union("draft", "published", "archived")` | |
| `version` | `v.number()` | |
| `createdAt` | `v.string()` | |
| `updatedAt` | `v.string()` | |

**Indexes:** `by_name` `["name"]`, `by_status` `["status"]`

---

### `workflowRuns`

Provenance records linking task execution to workflow instances.

| Field | Type | Notes |
|-------|------|-------|
| `taskId` | `v.id("tasks")` | |
| `squadSpecId` | `v.id("squadSpecs")` | |
| `workflowSpecId` | `v.id("workflowSpecs")` | |
| `boardId` | `v.id("boards")` | |
| `status` | `workflowRunStatusValidator` | |
| `launchedAt` | `v.string()` | |
| `completedAt` | `v.optional(v.string())` | |
| `stepMapping` | `v.optional(v.record(v.string(), v.string()))` | Workflow step ID → Convex step ID |

**Indexes:** `by_taskId` `["taskId"]`, `by_status` `["status"]`

---

### `boardSquadBindings`

Links boards to squads with per-board workflow overrides.

| Field | Type | Notes |
|-------|------|-------|
| `boardId` | `v.id("boards")` | |
| `squadSpecId` | `v.id("squadSpecs")` | |
| `enabled` | `v.boolean()` | |
| `defaultWorkflowSpecIdOverride` | `v.optional(v.id("workflowSpecs"))` | |
| `createdAt` | `v.string()` | |
| `updatedAt` | `v.string()` | |

**Indexes:** `by_boardId` `["boardId"]`, `by_squadSpecId` `["squadSpecId"]`, `by_boardId_squadSpecId` `["boardId", "squadSpecId"]`

---

## Tags & Metadata

### `taskTags`

Custom tag definitions.

| Field | Type |
|-------|------|
| `name` | `v.string()` |
| `color` | `v.string()` |
| `attributeIds` | `v.optional(v.array(v.id("tagAttributes")))` |

**Indexes:** `by_name` `["name"]`

---

### `tagAttributes`

Tag attribute schemas.

| Field | Type | Notes |
|-------|------|-------|
| `name` | `v.string()` | |
| `type` | `v.union("text", "number", "date", "select")` | |
| `options` | `v.optional(v.array(v.string()))` | For `"select"` type |
| `createdAt` | `v.string()` | |

**Indexes:** `by_name` `["name"]`

---

### `tagAttributeValues`

Tag attribute values on individual tasks.

| Field | Type |
|-------|------|
| `taskId` | `v.id("tasks")` |
| `tagName` | `v.string()` |
| `attributeId` | `v.id("tagAttributes")` |
| `value` | `v.string()` |
| `updatedAt` | `v.string()` |

**Indexes:** `by_taskId` `["taskId"]`, `by_taskId_tagName` `["taskId", "tagName"]`, `by_attributeId` `["attributeId"]`, `by_tagName` `["tagName"]`

---

## Table Relationships

```text
boards
  └── tasks (boardId)
      ├── steps (taskId)
      │   └── messages (stepId, optional)
      ├── messages (taskId)
      ├── activities (taskId)
      ├── executionSessions (taskId)
      │   ├── executionInteractions (sessionId)
      │   └── sessionActivityLog (sessionId)
      ├── executionQuestions (taskId)
      └── workflowRuns (taskId)

squadSpecs
  ├── workflowSpecs (squadSpecId)
  ├── boardSquadBindings (squadSpecId)
  └── agentSpecs (compiled into agents)

agents
  ├── interactiveSessions (agentName)
  ├── terminalSessions (agentName)
  └── chats (agentName)

taskTags
  └── tagAttributes (attributeIds)
      └── tagAttributeValues (attributeId, taskId)
```
