import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  boards: defineTable({
    name: v.string(),
    displayName: v.string(),
    description: v.optional(v.string()),
    enabledAgents: v.array(v.string()),
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
    trustLevel: v.union(
      v.literal("autonomous"),
      v.literal("agent_reviewed"),
      v.literal("human_approved"),
    ),
    reviewers: v.optional(v.array(v.string())),
    tags: v.optional(v.array(v.string())),
    taskTimeout: v.optional(v.number()),
    interAgentTimeout: v.optional(v.number()),
    executionPlan: v.optional(v.any()),
    stalledAt: v.optional(v.string()),
    isManual: v.optional(v.boolean()),
    deletedAt: v.optional(v.string()),
    previousStatus: v.optional(v.string()),
    boardId: v.optional(v.id("boards")),
    cronParentTaskId: v.optional(v.string()),
    files: v.optional(v.array(v.object({
      name: v.string(),
      type: v.string(),
      size: v.number(),
      subfolder: v.string(),
      uploadedAt: v.string(),
    }))),
    createdAt: v.string(),
    updatedAt: v.string(),
  })
    .index("by_status", ["status"])
    .index("by_boardId", ["boardId"]),

  messages: defineTable({
    taskId: v.id("tasks"),
    authorName: v.string(),
    authorType: v.union(
      v.literal("agent"),
      v.literal("user"),
      v.literal("system"),
    ),
    content: v.string(),
    messageType: v.union(
      v.literal("work"),
      v.literal("review_feedback"),
      v.literal("approval"),
      v.literal("denial"),
      v.literal("system_event"),
      v.literal("user_message"),
    ),
    timestamp: v.string(),
  }).index("by_taskId", ["taskId"]),

  agents: defineTable({
    name: v.string(),
    displayName: v.string(),
    role: v.string(),
    prompt: v.optional(v.string()),
    soul: v.optional(v.string()),
    skills: v.array(v.string()),
    status: v.union(
      v.literal("active"),
      v.literal("idle"),
      v.literal("crashed"),
    ),
    enabled: v.optional(v.boolean()),
    isSystem: v.optional(v.boolean()),
    model: v.optional(v.string()),
    variables: v.optional(v.array(v.object({ name: v.string(), value: v.string() }))),
    lastActiveAt: v.optional(v.string()),
    deletedAt: v.optional(v.string()),
  })
    .index("by_name", ["name"])
    .index("by_status", ["status"]),

  activities: defineTable({
    taskId: v.optional(v.id("tasks")),
    agentName: v.optional(v.string()),
    eventType: v.union(
      v.literal("task_created"),
      v.literal("task_assigned"),
      v.literal("task_started"),
      v.literal("task_completed"),
      v.literal("task_crashed"),
      v.literal("task_retrying"),
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
      v.literal("bulk_clear_done"),
      v.literal("manual_task_status_changed"),
      v.literal("file_attached"),
      v.literal("agent_output"),
      v.literal("board_created"),
      v.literal("board_updated"),
      v.literal("board_deleted"),
      v.literal("thread_message_sent"),
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
  }).index("by_name", ["name"]),

  settings: defineTable({
    key: v.string(),
    value: v.string(),
  }).index("by_key", ["key"]),
});
