import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

// ---------------------------------------------------------------------------
// Agent Spec V2 validators
// ---------------------------------------------------------------------------

export const specStatusValidator = v.union(
  v.literal("draft"),
  v.literal("published"),
  v.literal("archived"),
);

export const reviewScopeValidator = v.union(
  v.literal("agent"),
  v.literal("workflow"),
  v.literal("execution"),
);

export const workflowStepTypeValidator = v.union(
  v.literal("agent"),
  v.literal("human"),
  v.literal("checkpoint"),
  v.literal("review"),
  v.literal("system"),
);

export const workModeValidator = v.union(v.literal("direct_delegate"), v.literal("ai_workflow"));

export const routingModeValidator = v.union(
  v.literal("lead_agent"),
  v.literal("workflow"),
  v.literal("human"),
);

export const taskFileMetadataValidator = v.object({
  name: v.string(),
  type: v.string(),
  size: v.number(),
  subfolder: v.string(),
  uploadedAt: v.string(),
  restoredAt: v.optional(v.string()),
});

export const taskFilesValidator = v.optional(v.array(taskFileMetadataValidator));
export const interactiveSessionStatusValidator = v.union(
  v.literal("ready"),
  v.literal("attached"),
  v.literal("detached"),
  v.literal("ended"),
  v.literal("error"),
);
export const interactiveSessionScopeKindValidator = v.union(
  v.literal("chat"),
  v.literal("task"),
  v.literal("workspace"),
);
export const interactiveSessionCapabilityValidator = v.union(
  v.literal("tui"),
  v.literal("autocomplete"),
  v.literal("interactive-prompts"),
  v.literal("commands"),
  v.literal("mcp-tools"),
);
export const interactiveSessionControlModeValidator = v.union(
  v.literal("agent"),
  v.literal("human"),
);
export const interactiveProviderValidator = v.union(
  v.literal("claude-code"),
  v.literal("codex"),
  v.literal("mc"),
);
export const executionInteractionStateValidator = v.union(
  v.literal("running"),
  v.literal("waiting_user_input"),
  v.literal("ready_to_resume"),
  v.literal("paused"),
  v.literal("completed"),
  v.literal("crashed"),
);
export const skillProviderValidator = v.union(
  v.literal("claude-code"),
  v.literal("codex"),
  v.literal("nanobot"),
);

export default defineSchema({
  boards: defineTable({
    name: v.string(),
    displayName: v.string(),
    description: v.optional(v.string()),
    enabledAgents: v.array(v.string()),
    agentMemoryModes: v.optional(
      v.array(
        v.object({
          agentName: v.string(),
          mode: v.union(v.literal("clean"), v.literal("with_history")),
        }),
      ),
    ),
    isDefault: v.optional(v.boolean()),
    createdAt: v.string(),
    updatedAt: v.string(),
    deletedAt: v.optional(v.string()),
  })
    .index("by_name", ["name"])
    .index("by_isDefault", ["isDefault"]),

  tasks: defineTable({
    title: v.string(),
    description: v.optional(v.string()),
    status: v.union(
      v.literal("planning"),
      v.literal("ready"),
      v.literal("failed"),
      v.literal("inbox"),
      v.literal("assigned"),
      v.literal("in_progress"),
      v.literal("review"),
      v.literal("done"),
      v.literal("retrying"),
      v.literal("crashed"),
      v.literal("deleted"),
    ),
    assignedAgent: v.optional(v.string()),
    trustLevel: v.union(v.literal("autonomous"), v.literal("human_approved")),
    reviewers: v.optional(v.array(v.string())),
    tags: v.optional(v.array(v.string())),
    taskTimeout: v.optional(v.number()),
    interAgentTimeout: v.optional(v.number()),
    executionPlan: v.optional(v.any()),
    supervisionMode: v.optional(v.union(v.literal("autonomous"), v.literal("supervised"))),
    stalledAt: v.optional(v.string()),
    isManual: v.optional(v.boolean()),
    isFavorite: v.optional(v.boolean()),
    autoTitle: v.optional(v.boolean()),
    awaitingKickoff: v.optional(v.boolean()),
    reviewPhase: v.optional(
      v.union(v.literal("plan_review"), v.literal("execution_pause"), v.literal("final_approval")),
    ),
    stateVersion: v.optional(v.number()),
    deletedAt: v.optional(v.string()),
    previousStatus: v.optional(v.string()),
    activeCronJobId: v.optional(v.string()),
    boardId: v.optional(v.id("boards")),
    cronParentTaskId: v.optional(v.string()),
    sourceAgent: v.optional(v.string()),
    isMergeTask: v.optional(v.boolean()),
    mergeSourceTaskIds: v.optional(v.array(v.id("tasks"))),
    mergeSourceLabels: v.optional(v.array(v.string())),
    mergedIntoTaskId: v.optional(v.id("tasks")),
    mergePreviousStatus: v.optional(v.string()),
    mergeLockedAt: v.optional(v.string()),
    files: taskFilesValidator,
    // Execution scaffolding fields (optional, no behavior change yet)
    workMode: v.optional(workModeValidator),
    routingMode: v.optional(routingModeValidator),
    routingDecision: v.optional(v.any()),
    squadSpecId: v.optional(v.id("squadSpecs")),
    workflowSpecId: v.optional(v.id("workflowSpecs")),
    createdAt: v.string(),
    updatedAt: v.string(),
  })
    .index("by_status", ["status"])
    .index("by_boardId", ["boardId"])
    .searchIndex("search_title", {
      searchField: "title",
      filterFields: ["boardId"],
    })
    .searchIndex("search_description", {
      searchField: "description",
      filterFields: ["boardId"],
    }),

  steps: defineTable({
    taskId: v.id("tasks"),
    title: v.string(),
    description: v.string(),
    assignedAgent: v.string(),
    status: v.union(
      v.literal("planned"),
      v.literal("assigned"),
      v.literal("running"),
      v.literal("review"),
      v.literal("completed"),
      v.literal("crashed"),
      v.literal("blocked"),
      v.literal("waiting_human"),
      v.literal("deleted"),
    ),
    blockedBy: v.optional(v.array(v.id("steps"))),
    parallelGroup: v.number(),
    order: v.number(),
    stateVersion: v.optional(v.number()),
    createdAt: v.string(),
    deletedAt: v.optional(v.string()),
    startedAt: v.optional(v.string()),
    completedAt: v.optional(v.string()),
    errorMessage: v.optional(v.string()),
    attachedFiles: v.optional(v.array(v.string())),
    // Workflow metadata — set only when the step was materialized from a workflowSpec.
    workflowStepId: v.optional(v.string()),
    workflowStepType: v.optional(workflowStepTypeValidator),
    agentId: v.optional(v.id("agents")),
    reviewSpecId: v.optional(v.id("reviewSpecs")),
    onRejectStepId: v.optional(v.string()),
  })
    .index("by_taskId", ["taskId"])
    .index("by_status", ["status"]),

  messages: defineTable({
    taskId: v.id("tasks"),
    stepId: v.optional(v.id("steps")),
    authorName: v.string(),
    authorType: v.union(v.literal("agent"), v.literal("user"), v.literal("system")),
    content: v.string(),
    messageType: v.union(
      v.literal("work"),
      v.literal("review_feedback"),
      v.literal("approval"),
      v.literal("denial"),
      v.literal("system_event"),
      v.literal("user_message"),
      v.literal("comment"),
    ),
    type: v.optional(
      v.union(
        v.literal("step_completion"),
        v.literal("user_message"),
        v.literal("system_error"),
        v.literal("lead_agent_plan"),
        v.literal("lead_agent_chat"),
        v.literal("comment"),
      ),
    ),
    artifacts: v.optional(
      v.array(
        v.object({
          path: v.string(),
          action: v.union(v.literal("created"), v.literal("modified"), v.literal("deleted")),
          description: v.optional(v.string()),
          diff: v.optional(v.string()),
        }),
      ),
    ),
    fileAttachments: v.optional(
      v.array(
        v.object({
          name: v.string(),
          type: v.string(),
          size: v.number(),
        }),
      ),
    ),
    planReview: v.optional(
      v.object({
        kind: v.union(v.literal("request"), v.literal("feedback"), v.literal("decision")),
        planGeneratedAt: v.string(),
        decision: v.optional(v.union(v.literal("approved"), v.literal("rejected"))),
      }),
    ),
    leadAgentConversation: v.optional(v.boolean()),
    timestamp: v.string(),
  })
    .index("by_taskId", ["taskId"])
    .index("by_authorType_timestamp", ["authorType", "timestamp"]),

  runtimeClaims: defineTable({
    claimKind: v.string(),
    entityType: v.string(),
    entityId: v.string(),
    ownerId: v.string(),
    leaseExpiresAt: v.string(),
    metadata: v.optional(v.any()),
    createdAt: v.string(),
    updatedAt: v.string(),
  })
    .index("by_claimKey", ["claimKind", "entityType", "entityId"])
    .index("by_leaseExpiresAt", ["leaseExpiresAt"]),

  runtimeReceipts: defineTable({
    idempotencyKey: v.string(),
    scope: v.string(),
    entityType: v.optional(v.string()),
    entityId: v.optional(v.string()),
    response: v.any(),
    createdAt: v.string(),
    updatedAt: v.string(),
  }).index("by_idempotencyKey", ["idempotencyKey"]),

  agents: defineTable({
    name: v.string(),
    displayName: v.string(),
    role: v.string(),
    prompt: v.optional(v.string()),
    soul: v.optional(v.string()),
    skills: v.array(v.string()),
    status: v.union(v.literal("active"), v.literal("idle"), v.literal("crashed")),
    enabled: v.optional(v.boolean()),
    isSystem: v.optional(v.boolean()),
    model: v.optional(v.string()),
    reasoningLevel: v.optional(v.string()),
    interactiveProvider: v.optional(interactiveProviderValidator),
    claudeCodeOpts: v.optional(
      v.object({
        permissionMode: v.optional(v.string()),
        maxBudgetUsd: v.optional(v.number()),
        maxTurns: v.optional(v.number()),
      }),
    ),
    variables: v.optional(v.array(v.object({ name: v.string(), value: v.string() }))),
    tasksExecuted: v.optional(v.number()),
    stepsExecuted: v.optional(v.number()),
    lastTaskExecutedAt: v.optional(v.string()),
    lastStepExecutedAt: v.optional(v.string()),
    lastActiveAt: v.optional(v.string()),
    deletedAt: v.optional(v.string()),
    memoryContent: v.optional(v.string()),
    historyContent: v.optional(v.string()),
    sessionData: v.optional(v.string()),
    // Runtime projection metadata — set only when this record was compiled from an agentSpec.
    compiledFromSpecId: v.optional(v.string()),
    compiledFromVersion: v.optional(v.number()),
    compiledAt: v.optional(v.string()),
  })
    .index("by_name", ["name"])
    .index("by_status", ["status"]),

  activities: defineTable({
    taskId: v.optional(v.id("tasks")),
    agentName: v.optional(v.string()),
    eventType: v.union(
      v.literal("task_created"),
      v.literal("task_planning"),
      v.literal("task_failed"),
      v.literal("task_assigned"),
      v.literal("task_started"),
      v.literal("task_completed"),
      v.literal("task_crashed"),
      v.literal("task_retrying"),
      v.literal("task_reassigned"),
      v.literal("review_requested"),
      v.literal("review_feedback"),
      v.literal("review_approved"),
      v.literal("hitl_requested"),
      v.literal("hitl_approved"),
      v.literal("hitl_denied"),
      v.literal("agent_connected"),
      v.literal("agent_disconnected"),
      v.literal("agent_crashed"),
      v.literal("system_error"),
      v.literal("task_deleted"),
      v.literal("task_restored"),
      v.literal("agent_config_updated"),
      v.literal("agent_activated"),
      v.literal("agent_deactivated"),
      v.literal("agent_deleted"),
      v.literal("agent_restored"),
      v.literal("bulk_clear_done"),
      v.literal("manual_task_status_changed"),
      v.literal("file_attached"),
      v.literal("task_merged"),
      v.literal("agent_output"),
      v.literal("board_created"),
      v.literal("board_updated"),
      v.literal("board_deleted"),
      v.literal("thread_message_sent"),
      v.literal("task_dispatch_started"),
      v.literal("step_dispatched"),
      v.literal("step_started"),
      v.literal("step_completed"),
      v.literal("step_created"),
      v.literal("step_status_changed"),
      v.literal("step_unblocked"),
      v.literal("step_retrying"),
    ),
    description: v.string(),
    timestamp: v.string(),
  })
    .index("by_taskId", ["taskId"])
    .index("by_timestamp", ["timestamp"]),

  skills: defineTable({
    name: v.string(),
    description: v.string(),
    content: v.string(),
    metadata: v.optional(v.string()),
    source: v.union(v.literal("builtin"), v.literal("workspace")),
    supportedProviders: v.optional(v.array(skillProviderValidator)),
    always: v.optional(v.boolean()),
    available: v.boolean(),
    requires: v.optional(v.string()),
  }).index("by_name", ["name"]),

  taskTags: defineTable({
    name: v.string(),
    color: v.string(), // one of: blue|green|red|amber|violet|pink|orange|teal
    attributeIds: v.optional(v.array(v.id("tagAttributes"))),
  }).index("by_name", ["name"]),

  chats: defineTable({
    agentName: v.string(),
    authorName: v.string(),
    authorType: v.union(v.literal("user"), v.literal("agent")),
    content: v.string(),
    status: v.optional(v.union(v.literal("pending"), v.literal("processing"), v.literal("done"))),
    timestamp: v.string(),
  })
    .index("by_agentName", ["agentName"])
    .index("by_status", ["status"])
    .index("by_timestamp", ["timestamp"]),

  tagAttributes: defineTable({
    name: v.string(),
    type: v.union(v.literal("text"), v.literal("number"), v.literal("date"), v.literal("select")),
    options: v.optional(v.array(v.string())),
    createdAt: v.string(),
  }).index("by_name", ["name"]),

  tagAttributeValues: defineTable({
    taskId: v.id("tasks"),
    tagName: v.string(),
    attributeId: v.id("tagAttributes"),
    value: v.string(),
    updatedAt: v.string(),
  })
    .index("by_taskId", ["taskId"])
    .index("by_taskId_tagName", ["taskId", "tagName"])
    .index("by_attributeId", ["attributeId"])
    .index("by_tagName", ["tagName"]),

  settings: defineTable({
    key: v.string(),
    value: v.string(),
  }).index("by_key", ["key"]),

  terminalSessions: defineTable({
    sessionId: v.string(),
    output: v.string(),
    updatedAt: v.string(),
    pendingInput: v.optional(v.string()),
    status: v.optional(v.union(v.literal("idle"), v.literal("processing"), v.literal("error"))),
    agentName: v.optional(v.string()),
    sleepMode: v.optional(v.boolean()),
    wakeSignal: v.optional(v.boolean()),
  })
    .index("by_sessionId", ["sessionId"])
    .index("by_agentName", ["agentName"]),

  agentSpecs: defineTable({
    name: v.string(),
    displayName: v.string(),
    role: v.string(),
    purpose: v.optional(v.string()),
    nonGoals: v.optional(v.array(v.string())),
    responsibilities: v.optional(v.array(v.string())),
    principles: v.optional(v.array(v.string())),
    workingStyle: v.optional(v.string()),
    qualityRules: v.optional(v.array(v.string())),
    antiPatterns: v.optional(v.array(v.string())),
    outputContract: v.optional(v.string()),
    toolPolicy: v.optional(v.string()),
    memoryPolicy: v.optional(v.string()),
    executionPolicy: v.optional(v.string()),
    reviewPolicyRef: v.optional(v.string()),
    skills: v.optional(v.array(v.string())),
    model: v.optional(v.string()),
    status: v.union(v.literal("draft"), v.literal("published"), v.literal("archived")),
    version: v.number(),
    compiledAgentId: v.optional(v.id("agents")),
    compiledAt: v.optional(v.string()),
    createdAt: v.string(),
    updatedAt: v.string(),
  })
    .index("by_name", ["name"])
    .index("by_status", ["status"]),

  squadSpecs: defineTable({
    name: v.string(),
    displayName: v.string(),
    description: v.optional(v.string()),
    outcome: v.optional(v.string()),
    reviewPolicy: v.optional(v.string()),
    // Legacy published squads may still carry agentSpecIds until they are republished.
    agentIds: v.optional(v.array(v.id("agents"))),
    agentSpecIds: v.optional(v.array(v.id("agentSpecs"))),
    defaultWorkflowSpecId: v.optional(v.id("workflowSpecs")),
    status: v.union(v.literal("draft"), v.literal("published"), v.literal("archived")),
    version: v.number(),
    tags: v.optional(v.array(v.string())),
    publishedAt: v.optional(v.string()),
    createdAt: v.string(),
    updatedAt: v.string(),
  })
    .index("by_name", ["name"])
    .index("by_status", ["status"]),

  workflowSpecs: defineTable({
    squadSpecId: v.id("squadSpecs"),
    name: v.string(),
    description: v.optional(v.string()),
    steps: v.array(
      v.object({
        id: v.string(),
        title: v.string(),
        type: v.union(
          v.literal("agent"),
          v.literal("human"),
          v.literal("checkpoint"),
          v.literal("review"),
          v.literal("system"),
        ),
        agentId: v.optional(v.id("agents")),
        agentSpecId: v.optional(v.id("agentSpecs")),
        reviewSpecId: v.optional(v.id("reviewSpecs")),
        description: v.optional(v.string()),
        inputs: v.optional(v.array(v.string())),
        outputs: v.optional(v.array(v.string())),
        dependsOn: v.optional(v.array(v.string())),
        onReject: v.optional(v.string()),
      }),
    ),
    exitCriteria: v.optional(v.string()),
    executionPolicy: v.optional(v.string()),
    reviewSpecId: v.optional(v.id("reviewSpecs")),
    onRejectDefault: v.optional(v.string()),
    onReject: v.optional(
      v.object({
        returnToStep: v.string(),
        maxRetries: v.optional(v.number()),
      }),
    ),
    status: v.union(v.literal("draft"), v.literal("published"), v.literal("archived")),
    version: v.number(),
    publishedAt: v.optional(v.string()),
    createdAt: v.string(),
    updatedAt: v.string(),
  })
    .index("by_squadSpecId", ["squadSpecId"])
    .index("by_status", ["status"]),

  reviewSpecs: defineTable({
    name: v.string(),
    scope: v.union(v.literal("agent"), v.literal("workflow"), v.literal("execution")),
    criteria: v.array(
      v.object({
        id: v.string(),
        label: v.string(),
        weight: v.number(),
        description: v.optional(v.string()),
      }),
    ),
    vetoConditions: v.optional(v.array(v.string())),
    approvalThreshold: v.number(),
    feedbackContract: v.optional(v.string()),
    reviewerPolicy: v.optional(v.string()),
    rejectionRoutingPolicy: v.optional(v.string()),
    status: v.union(v.literal("draft"), v.literal("published"), v.literal("archived")),
    version: v.number(),
    createdAt: v.string(),
    updatedAt: v.string(),
  })
    .index("by_name", ["name"])
    .index("by_status", ["status"]),

  workflowRuns: defineTable({
    taskId: v.id("tasks"),
    squadSpecId: v.id("squadSpecs"),
    workflowSpecId: v.id("workflowSpecs"),
    boardId: v.id("boards"),
    status: v.union(
      v.literal("active"),
      v.literal("completed"),
      v.literal("failed"),
      v.literal("paused"),
    ),
    launchedAt: v.string(),
    completedAt: v.optional(v.string()),
    stepMapping: v.optional(v.any()),
  })
    .index("by_taskId", ["taskId"])
    .index("by_status", ["status"]),

  executionSessions: defineTable({
    sessionId: v.string(),
    taskId: v.id("tasks"),
    stepId: v.optional(v.id("steps")),
    agentName: v.string(),
    provider: v.string(),
    state: executionInteractionStateValidator,
    lastProgressMessage: v.optional(v.string()),
    lastProgressPercentage: v.optional(v.number()),
    finalResult: v.optional(v.string()),
    finalResultSource: v.optional(v.string()),
    createdAt: v.string(),
    updatedAt: v.string(),
    completedAt: v.optional(v.string()),
    crashedAt: v.optional(v.string()),
  })
    .index("by_sessionId", ["sessionId"])
    .index("by_taskId", ["taskId"])
    .index("by_stepId", ["stepId"])
    .index("by_taskId_state", ["taskId", "state"]),

  executionInteractions: defineTable({
    sessionId: v.string(),
    taskId: v.id("tasks"),
    stepId: v.optional(v.id("steps")),
    seq: v.number(),
    kind: v.string(),
    payload: v.optional(v.any()),
    createdAt: v.string(),
    agentName: v.optional(v.string()),
    provider: v.optional(v.string()),
  })
    .index("by_sessionId_seq", ["sessionId", "seq"])
    .index("by_taskId", ["taskId"]),

  executionQuestions: defineTable({
    questionId: v.string(),
    sessionId: v.string(),
    taskId: v.id("tasks"),
    stepId: v.optional(v.id("steps")),
    agentName: v.string(),
    provider: v.string(),
    question: v.optional(v.string()),
    options: v.optional(v.array(v.string())),
    questions: v.optional(v.any()),
    status: v.union(
      v.literal("pending"),
      v.literal("answered"),
      v.literal("cancelled"),
      v.literal("expired"),
    ),
    answer: v.optional(v.string()),
    createdAt: v.string(),
    answeredAt: v.optional(v.string()),
  })
    .index("by_questionId", ["questionId"])
    .index("by_taskId_status", ["taskId", "status"])
    .index("by_sessionId_status", ["sessionId", "status"]),

  boardSquadBindings: defineTable({
    boardId: v.id("boards"),
    squadSpecId: v.id("squadSpecs"),
    enabled: v.boolean(),
    defaultWorkflowSpecIdOverride: v.optional(v.id("workflowSpecs")),
    createdAt: v.string(),
    updatedAt: v.string(),
  })
    .index("by_boardId", ["boardId"])
    .index("by_squadSpecId", ["squadSpecId"])
    .index("by_boardId_squadSpecId", ["boardId", "squadSpecId"]),

  sessionActivityLog: defineTable({
    sessionId: v.string(),
    seq: v.number(),
    kind: v.string(),
    ts: v.string(),
    toolName: v.optional(v.string()),
    toolInput: v.optional(v.string()),
    filePath: v.optional(v.string()),
    summary: v.optional(v.string()),
    error: v.optional(v.string()),
    turnId: v.optional(v.string()),
    itemId: v.optional(v.string()),
    stepId: v.optional(v.string()),
    agentName: v.optional(v.string()),
    provider: v.optional(v.string()),
    requiresAction: v.optional(v.boolean()),
  })
    .index("by_session", ["sessionId"])
    .index("by_session_seq", ["sessionId", "seq"]),

  interactiveSessions: defineTable({
    sessionId: v.string(),
    agentName: v.string(),
    provider: v.string(),
    scopeKind: interactiveSessionScopeKindValidator,
    scopeId: v.optional(v.string()),
    surface: v.string(),
    tmuxSession: v.string(),
    status: interactiveSessionStatusValidator,
    capabilities: v.array(interactiveSessionCapabilityValidator),
    attachToken: v.optional(v.string()),
    createdAt: v.string(),
    updatedAt: v.string(),
    lastActiveAt: v.optional(v.string()),
    endedAt: v.optional(v.string()),
    taskId: v.optional(v.string()),
    stepId: v.optional(v.string()),
    supervisionState: v.optional(v.string()),
    activeTurnId: v.optional(v.string()),
    activeItemId: v.optional(v.string()),
    lastEventKind: v.optional(v.string()),
    lastEventAt: v.optional(v.string()),
    lastError: v.optional(v.string()),
    summary: v.optional(v.string()),
    finalResult: v.optional(v.string()),
    finalResultSource: v.optional(v.string()),
    finalResultAt: v.optional(v.string()),
    controlMode: v.optional(interactiveSessionControlModeValidator),
    manualTakeoverAt: v.optional(v.string()),
    manualCompletionRequestedAt: v.optional(v.string()),
    // Provider-CLI metadata (Stories 28-19, 28-22, 28-26)
    bootstrapPrompt: v.optional(v.string()),
    providerSessionId: v.optional(v.string()),
    lastControlCommand: v.optional(v.string()),
    lastControlOutcome: v.optional(v.string()),
    lastControlError: v.optional(v.string()),
  })
    .index("by_sessionId", ["sessionId"])
    .index("by_agentName", ["agentName"])
    .index("by_provider", ["provider"])
    .index("by_status", ["status"]),
});
