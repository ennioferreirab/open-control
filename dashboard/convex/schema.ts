import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

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
export const interactiveProviderValidator = v.union(v.literal("claude-code"), v.literal("codex"));

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
    createdAt: v.string(),
    deletedAt: v.optional(v.string()),
    startedAt: v.optional(v.string()),
    completedAt: v.optional(v.string()),
    errorMessage: v.optional(v.string()),
    attachedFiles: v.optional(v.array(v.string())),
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
    lastActiveAt: v.optional(v.string()),
    deletedAt: v.optional(v.string()),
    memoryContent: v.optional(v.string()),
    historyContent: v.optional(v.string()),
    sessionData: v.optional(v.string()),
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
  })
    .index("by_sessionId", ["sessionId"])
    .index("by_agentName", ["agentName"])
    .index("by_provider", ["provider"])
    .index("by_status", ["status"]),
});
