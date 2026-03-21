import { internalMutation, internalQuery, mutation, query } from "./_generated/server";
import type { Id } from "./_generated/dataModel";
import type { MutationCtx } from "./_generated/server";
import { ConvexError, v } from "convex/values";

import { createTask } from "./lib/taskMetadata";
import { logActivity } from "./lib/workflowHelpers";
import {
  buildCommentMessagePayload,
  buildTaskCreationPayload,
  validateInboundStatus,
} from "./lib/integrationSync";

// ---------------------------------------------------------------------------
// integrationConfigs mutations
// ---------------------------------------------------------------------------

/**
 * Create a new integration config record.
 */
export const createConfig = internalMutation({
  args: {
    platform: v.string(),
    name: v.string(),
    enabled: v.boolean(),
    boardId: v.id("boards"),
    apiKey: v.string(),
    webhookSecret: v.optional(v.string()),
    webhookId: v.optional(v.string()),
    externalProjectId: v.optional(v.string()),
    externalProjectName: v.optional(v.string()),
    statusMapping: v.optional(v.any()),
    syncDirection: v.union(
      v.literal("inbound_only"),
      v.literal("outbound_only"),
      v.literal("bidirectional"),
    ),
    threadMirroring: v.optional(v.boolean()),
    syncAttachments: v.optional(v.boolean()),
    syncLabels: v.optional(v.boolean()),
  },
  handler: async (ctx, args) => {
    const now = new Date().toISOString();
    return await ctx.db.insert("integrationConfigs", {
      platform: args.platform,
      name: args.name,
      enabled: args.enabled,
      boardId: args.boardId,
      apiKey: args.apiKey,
      webhookSecret: args.webhookSecret,
      webhookId: args.webhookId,
      externalProjectId: args.externalProjectId,
      externalProjectName: args.externalProjectName,
      statusMapping: args.statusMapping,
      syncDirection: args.syncDirection,
      threadMirroring: args.threadMirroring,
      syncAttachments: args.syncAttachments,
      syncLabels: args.syncLabels,
      createdAt: now,
      updatedAt: now,
    });
  },
});

/**
 * Update fields on an existing integration config.
 */
export const updateConfig = internalMutation({
  args: {
    configId: v.id("integrationConfigs"),
    enabled: v.optional(v.boolean()),
    apiKey: v.optional(v.string()),
    webhookSecret: v.optional(v.string()),
    webhookId: v.optional(v.string()),
    externalProjectId: v.optional(v.string()),
    externalProjectName: v.optional(v.string()),
    statusMapping: v.optional(v.any()),
    syncDirection: v.optional(
      v.union(v.literal("inbound_only"), v.literal("outbound_only"), v.literal("bidirectional")),
    ),
    threadMirroring: v.optional(v.boolean()),
    syncAttachments: v.optional(v.boolean()),
    syncLabels: v.optional(v.boolean()),
    lastSyncAt: v.optional(v.string()),
    lastError: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const config = await ctx.db.get(args.configId);
    if (!config) {
      throw new ConvexError("Integration config not found");
    }
    const { configId, ...fields } = args;
    await ctx.db.patch(configId, {
      ...fields,
      updatedAt: new Date().toISOString(),
    });
  },
});

// ---------------------------------------------------------------------------
// integrationConfigs queries
// ---------------------------------------------------------------------------

/**
 * Return all configs for a given platform.
 */
export const getConfigsByPlatform = internalQuery({
  args: { platform: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("integrationConfigs")
      .withIndex("by_platform", (q) => q.eq("platform", args.platform))
      .collect();
  },
});

/**
 * Return all enabled integration configs across all platforms.
 *
 * Full table scan + JS filter is acceptable here because integrationConfigs
 * is a small table (one record per integration). No single-field index on
 * `enabled` exists; the compound `by_platform_enabled` index requires a
 * platform prefix.
 */
export const getEnabledConfigs = internalQuery({
  args: {},
  handler: async (ctx) => {
    const all = await ctx.db.query("integrationConfigs").collect();
    return all.filter((c) => c.enabled);
  },
});

// ---------------------------------------------------------------------------
// integrationMappings mutations
// ---------------------------------------------------------------------------

/**
 * Create or update an integration mapping.
 * Looks up existing mapping by configId + externalType + externalId.
 * Creates if not found; patches if found.
 */
export const upsertMapping = internalMutation({
  args: {
    configId: v.id("integrationConfigs"),
    platform: v.string(),
    externalId: v.string(),
    externalType: v.string(),
    internalId: v.string(),
    internalType: v.string(),
    externalUrl: v.optional(v.string()),
    metadata: v.optional(v.any()),
  },
  handler: async (ctx, args) => {
    const now = new Date().toISOString();
    const existing = await ctx.db
      .query("integrationMappings")
      .withIndex("by_config_external", (q) =>
        q
          .eq("configId", args.configId)
          .eq("externalType", args.externalType)
          .eq("externalId", args.externalId),
      )
      .first();

    if (existing) {
      await ctx.db.patch(existing._id, {
        internalId: args.internalId,
        internalType: args.internalType,
        externalUrl: args.externalUrl,
        metadata: args.metadata,
        updatedAt: now,
      });
      return existing._id;
    }

    return await ctx.db.insert("integrationMappings", {
      configId: args.configId,
      platform: args.platform,
      externalId: args.externalId,
      externalType: args.externalType,
      internalId: args.internalId,
      internalType: args.internalType,
      externalUrl: args.externalUrl,
      metadata: args.metadata,
      createdAt: now,
      updatedAt: now,
    });
  },
});

// ---------------------------------------------------------------------------
// integrationMappings queries
// ---------------------------------------------------------------------------

/**
 * Look up a mapping by configId + externalType + externalId.
 */
export const getMappingByExternal = internalQuery({
  args: {
    configId: v.id("integrationConfigs"),
    externalType: v.string(),
    externalId: v.string(),
  },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("integrationMappings")
      .withIndex("by_config_external", (q) =>
        q
          .eq("configId", args.configId)
          .eq("externalType", args.externalType)
          .eq("externalId", args.externalId),
      )
      .first();
  },
});

/**
 * Look up a mapping by configId + internalType + internalId.
 */
export const getMappingByInternal = internalQuery({
  args: {
    configId: v.id("integrationConfigs"),
    internalType: v.string(),
    internalId: v.string(),
  },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("integrationMappings")
      .withIndex("by_config_internal", (q) =>
        q
          .eq("configId", args.configId)
          .eq("internalType", args.internalType)
          .eq("internalId", args.internalId),
      )
      .first();
  },
});

/**
 * Return all mappings for a given internalId.
 */
export const getMappingsByInternalId = internalQuery({
  args: { internalId: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("integrationMappings")
      .withIndex("by_internalId", (q) => q.eq("internalId", args.internalId))
      .collect();
  },
});

// ---------------------------------------------------------------------------
// integrationEvents mutations
// ---------------------------------------------------------------------------

/**
 * Create an integration event record.
 */
export const createEvent = internalMutation({
  args: {
    configId: v.id("integrationConfigs"),
    eventId: v.string(),
    eventType: v.string(),
    direction: v.union(v.literal("inbound"), v.literal("outbound")),
    status: v.union(
      v.literal("pending"),
      v.literal("processed"),
      v.literal("failed"),
      v.literal("skipped"),
    ),
    externalId: v.optional(v.string()),
    internalId: v.optional(v.string()),
    payload: v.optional(v.any()),
    errorMessage: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const now = new Date().toISOString();
    return await ctx.db.insert("integrationEvents", {
      configId: args.configId,
      eventId: args.eventId,
      eventType: args.eventType,
      direction: args.direction,
      status: args.status,
      externalId: args.externalId,
      internalId: args.internalId,
      payload: args.payload,
      errorMessage: args.errorMessage,
      createdAt: now,
    });
  },
});

/**
 * Mark an integration event as processed.
 */
export const markEventProcessed = internalMutation({
  args: { eventId: v.id("integrationEvents") },
  handler: async (ctx, args) => {
    const event = await ctx.db.get(args.eventId);
    if (!event) {
      throw new ConvexError("Integration event not found");
    }
    await ctx.db.patch(args.eventId, {
      status: "processed",
      processedAt: new Date().toISOString(),
    });
  },
});

// ---------------------------------------------------------------------------
// integrationEvents queries
// ---------------------------------------------------------------------------

/**
 * List pending events for a given config.
 */
export const listPendingEventsByConfig = internalQuery({
  args: { configId: v.id("integrationConfigs") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("integrationEvents")
      .withIndex("by_config_status", (q) => q.eq("configId", args.configId).eq("status", "pending"))
      .collect();
  },
});

// ---------------------------------------------------------------------------
// Inbound sync mutations
// ---------------------------------------------------------------------------

/**
 * Atomically create a task and an integrationMapping from an inbound issue.
 *
 * Accepts a Linear (or other platform) issue event, creates the task in "inbox"
 * status, then records the mapping between the external issue ID and the new
 * internal task ID. The caller is responsible for applying the external status
 * as a separate step if needed.
 */
export const processInboundIssue = internalMutation({
  args: {
    configId: v.id("integrationConfigs"),
    platform: v.string(),
    externalId: v.string(),
    externalUrl: v.optional(v.string()),
    title: v.string(),
    description: v.optional(v.string()),
    status: v.string(),
    boardId: v.id("boards"),
    tags: v.optional(v.array(v.string())),
  },
  handler: async (ctx, args) => {
    const now = new Date().toISOString();

    // Build and insert task using shared task creation logic
    const payload = buildTaskCreationPayload(
      {
        title: args.title,
        description: args.description,
        status: args.status,
        boardId: args.boardId,
        tags: args.tags,
      },
      now,
    );

    const taskId = await createTask(ctx, {
      title: payload.title,
      description: payload.description,
      isManual: payload.isManual,
      boardId: payload.boardId,
      tags: payload.tags,
    });

    // Record mapping: externalId (issue) → internalId (task)
    const mappingId = await ctx.db.insert("integrationMappings", {
      configId: args.configId,
      platform: args.platform,
      externalId: args.externalId,
      externalType: "issue",
      internalId: String(taskId),
      internalType: "task",
      externalUrl: args.externalUrl,
      createdAt: now,
      updatedAt: now,
    });

    await logActivity(ctx, {
      taskId,
      eventType: "integration_sync_inbound",
      description: `Task created from inbound ${args.platform} issue ${args.externalId}`,
      timestamp: now,
    });

    return { taskId, mappingId };
  },
});

/**
 * Apply an inbound status change from an external platform to a task.
 *
 * Looks up the mapping by configId + externalId. If no mapping is found,
 * records a "skipped" event and returns. Otherwise patches the task status.
 */
export const processInboundStatusChange = internalMutation({
  args: {
    configId: v.id("integrationConfigs"),
    platform: v.string(),
    externalId: v.string(),
    newStatus: v.string(),
    eventId: v.string(),
  },
  handler: async (ctx, args) => {
    const now = new Date().toISOString();

    // Resolve mapping
    const mapping = await ctx.db
      .query("integrationMappings")
      .withIndex("by_config_external", (q) =>
        q
          .eq("configId", args.configId)
          .eq("externalType", "issue")
          .eq("externalId", args.externalId),
      )
      .first();

    if (!mapping) {
      // Record skipped event — no mapping exists for this external issue
      await ctx.db.insert("integrationEvents", {
        configId: args.configId,
        eventId: args.eventId,
        eventType: "issue.status_changed",
        direction: "inbound",
        status: "skipped",
        externalId: args.externalId,
        errorMessage: `No mapping found for external issue ${args.externalId}`,
        createdAt: now,
      });
      return { skipped: true };
    }

    const taskId = mapping.internalId as Id<"tasks">;
    const task = await ctx.db.get(taskId);
    if (!task) {
      throw new ConvexError(`Task ${String(taskId)} referenced by mapping not found`);
    }

    // Validate the inbound status before applying
    const validatedStatus = validateInboundStatus(args.newStatus) as
      | "inbox"
      | "assigned"
      | "in_progress"
      | "review"
      | "done";

    await ctx.db.patch(taskId, {
      status: validatedStatus,
      updatedAt: now,
    });

    await logActivity(ctx, {
      taskId,
      eventType: "integration_sync_inbound",
      description: `Status updated to "${args.newStatus}" from inbound ${args.platform} event`,
      timestamp: now,
    });

    return { skipped: false, taskId };
  },
});

/**
 * Create a message on a task thread from an inbound comment event.
 *
 * Looks up the mapping by configId + externalId (issue type). If no mapping
 * is found, records a "skipped" event and returns.
 */
export const processInboundComment = internalMutation({
  args: {
    configId: v.id("integrationConfigs"),
    platform: v.string(),
    externalId: v.string(),
    content: v.string(),
    authorName: v.optional(v.string()),
    eventId: v.string(),
  },
  handler: async (ctx, args) => {
    const now = new Date().toISOString();

    // Resolve mapping for the issue that contains the comment
    const mapping = await ctx.db
      .query("integrationMappings")
      .withIndex("by_config_external", (q) =>
        q
          .eq("configId", args.configId)
          .eq("externalType", "issue")
          .eq("externalId", args.externalId),
      )
      .first();

    if (!mapping) {
      await ctx.db.insert("integrationEvents", {
        configId: args.configId,
        eventId: args.eventId,
        eventType: "comment.created",
        direction: "inbound",
        status: "skipped",
        externalId: args.externalId,
        errorMessage: `No mapping found for external issue ${args.externalId}`,
        createdAt: now,
      });
      return { skipped: true };
    }

    const taskId = mapping.internalId as Id<"tasks">;
    const task = await ctx.db.get(taskId);
    if (!task) {
      throw new ConvexError(`Task ${String(taskId)} referenced by mapping not found`);
    }

    const msgPayload = buildCommentMessagePayload(
      { content: args.content, authorName: args.authorName },
      now,
    );

    const messageId = await ctx.db.insert("messages", {
      taskId,
      authorName: msgPayload.authorName,
      authorType: msgPayload.authorType,
      content: msgPayload.content,
      messageType: msgPayload.messageType,
      type: msgPayload.type,
      timestamp: msgPayload.timestamp,
    });

    await logActivity(ctx, {
      taskId,
      eventType: "integration_sync_inbound",
      description: `Comment from ${args.platform} synced to task thread`,
      timestamp: now,
    });

    return { skipped: false, taskId, messageId };
  },
});

// ---------------------------------------------------------------------------
// Outbound sync query
// ---------------------------------------------------------------------------

/**
 * Return messages and activities since a given timestamp for tasks that
 * have integration mappings (i.e., are linked to an external platform).
 *
 * This is the key query for the outbound sync worker. It returns:
 * - messages posted since sinceTimestamp on tasks that have mappings
 * - activities since sinceTimestamp on tasks that have mappings
 *
 * The caller is responsible for filtering by platform/configId using
 * the mapping data returned alongside each record.
 */
export const getOutboundPending = internalQuery({
  args: {
    sinceTimestamp: v.string(),
    configId: v.id("integrationConfigs"),
  },
  handler: async (ctx, args) => {
    // Fetch all mappings for this config (issue type → task)
    const mappings = await ctx.db
      .query("integrationMappings")
      .withIndex("by_config_internal", (q) =>
        q.eq("configId", args.configId).eq("internalType", "task"),
      )
      .collect();

    if (mappings.length === 0) {
      return { messages: [], activities: [] };
    }

    const internalIds = new Set(mappings.map((m) => m.internalId));
    const mappingByInternalId = new Map(mappings.map((m) => [m.internalId, m]));

    // Fetch recent messages and filter to mapped tasks
    const recentMessages = await ctx.db
      .query("messages")
      .withIndex("by_authorType_timestamp", (q) =>
        q.eq("authorType", "user").gte("timestamp", args.sinceTimestamp),
      )
      .collect();

    const mappedMessages = recentMessages
      .filter((msg) => internalIds.has(String(msg.taskId)))
      .map((msg) => ({
        message: msg,
        mapping: mappingByInternalId.get(String(msg.taskId))!,
      }));

    // Fetch recent activities and filter to mapped tasks
    const recentActivities = await ctx.db
      .query("activities")
      .withIndex("by_timestamp", (q) => q.gte("timestamp", args.sinceTimestamp))
      .collect();

    const mappedActivities = recentActivities
      .filter((act) => act.taskId !== undefined && internalIds.has(String(act.taskId)))
      .map((act) => ({
        activity: act,
        mapping: mappingByInternalId.get(String(act.taskId!))!,
      }));

    return { messages: mappedMessages, activities: mappedActivities };
  },
});

// ---------------------------------------------------------------------------
// Public mutations — called by webhook API route (with admin auth)
// ---------------------------------------------------------------------------

/**
 * Find the first enabled Linear config and its board, or use default board.
 * Used by webhook handlers that don't know the configId.
 */
async function resolveLinearConfig(ctx: Pick<MutationCtx, "db">) {
  const config = await ctx.db
    .query("integrationConfigs")
    .withIndex("by_platform", (q) => q.eq("platform", "linear"))
    .first();

  if (!config || !config.enabled) {
    // Fall back to default board with no config tracking
    const board = await ctx.db
      .query("boards")
      .withIndex("by_isDefault", (q) => q.eq("isDefault", true))
      .first();
    return { config: null, boardId: board?._id ?? null };
  }

  return { config, boardId: config.boardId };
}

/**
 * Find a task by its external platform mapping.
 */
async function findMappedTask(
  ctx: Pick<MutationCtx, "db">,
  platform: string,
  externalId: string,
): Promise<{ taskId: Id<"tasks">; configId: Id<"integrationConfigs"> } | null> {
  // Try to find via integrationMappings table
  const mapping = await ctx.db
    .query("integrationMappings")
    .withIndex("by_platform_external", (q) =>
      q.eq("platform", platform).eq("externalId", externalId).eq("externalType", "issue"),
    )
    .first();

  if (mapping) {
    return {
      taskId: mapping.internalId as Id<"tasks">,
      configId: mapping.configId,
    };
  }

  return null;
}

/**
 * Webhook handler: process an inbound issue creation.
 * Auto-discovers Linear config and board. Idempotent.
 */
export const webhookProcessIssue = mutation({
  args: {
    platform: v.string(),
    externalId: v.string(),
    externalUrl: v.optional(v.string()),
    title: v.string(),
    description: v.optional(v.string()),
    status: v.optional(v.string()),
    tags: v.optional(v.array(v.string())),
    timestamp: v.string(),
  },
  handler: async (ctx, args) => {
    // Idempotency: check if already mapped
    const existing = await findMappedTask(ctx, args.platform, args.externalId);
    if (existing) {
      return { taskId: existing.taskId, created: false };
    }

    const { config, boardId } = await resolveLinearConfig(ctx);
    if (!boardId) {
      throw new ConvexError(
        "No board available for inbound issue. Configure a Linear integration or create a default board.",
      );
    }

    const now = new Date().toISOString();
    const taskPayload = buildTaskCreationPayload(
      {
        title: args.title,
        description: args.description,
        status: args.status ?? "inbox",
        boardId,
        tags: args.tags,
      },
      now,
    );

    // Append external URL to description
    let description = taskPayload.description ?? "";
    if (args.externalUrl) {
      const urlLine = `[${args.platform} issue](${args.externalUrl})`;
      description = description ? `${description}\n\n${urlLine}` : urlLine;
    }

    const taskId = await createTask(ctx, {
      title: taskPayload.title,
      description: description || undefined,
      isManual: taskPayload.isManual,
      boardId: taskPayload.boardId,
      tags: taskPayload.tags,
    });

    // Record mapping if we have a config
    if (config) {
      await ctx.db.insert("integrationMappings", {
        configId: config._id,
        platform: args.platform,
        externalId: args.externalId,
        externalType: "issue",
        internalId: String(taskId),
        internalType: "task",
        externalUrl: args.externalUrl,
        createdAt: now,
        updatedAt: now,
      });

      await logActivity(ctx, {
        taskId,
        eventType: "integration_sync_inbound",
        description: `Task created from inbound ${args.platform} issue ${args.externalId}`,
        timestamp: now,
      });
    }

    return { taskId, created: true };
  },
});

/**
 * Webhook handler: process an inbound status change.
 * Auto-discovers mapping by platform + externalId.
 */
export const webhookProcessStatusChange = mutation({
  args: {
    platform: v.string(),
    externalId: v.string(),
    newStatus: v.string(),
    timestamp: v.string(),
  },
  handler: async (ctx, args) => {
    const mapped = await findMappedTask(ctx, args.platform, args.externalId);
    if (!mapped) {
      return { updated: false, reason: "task_not_found" };
    }

    const task = await ctx.db.get(mapped.taskId);
    if (!task) {
      return { updated: false, reason: "task_deleted" };
    }

    const validatedStatus = validateInboundStatus(args.newStatus);
    if (task.status === validatedStatus) {
      return { updated: false, reason: "already_at_status" };
    }

    const now = new Date().toISOString();
    await ctx.db.patch(mapped.taskId, {
      status: validatedStatus as "inbox" | "assigned" | "in_progress" | "review" | "done",
      previousStatus: task.status,
      updatedAt: now,
      stateVersion: (task.stateVersion ?? 1) + 1,
    });

    await logActivity(ctx, {
      taskId: mapped.taskId,
      eventType: "integration_sync_inbound",
      description: `Status updated to "${args.newStatus}" from inbound ${args.platform} event`,
      timestamp: now,
    });

    return { updated: true, taskId: mapped.taskId };
  },
});

/**
 * Webhook handler: process an inbound comment.
 * Auto-discovers mapping by platform + externalId.
 */
export const webhookProcessComment = mutation({
  args: {
    platform: v.string(),
    externalId: v.string(),
    authorName: v.string(),
    content: v.string(),
    timestamp: v.string(),
  },
  handler: async (ctx, args) => {
    const mapped = await findMappedTask(ctx, args.platform, args.externalId);
    if (!mapped) {
      return { inserted: false, reason: "task_not_found" };
    }

    const task = await ctx.db.get(mapped.taskId);
    if (!task) {
      return { inserted: false, reason: "task_deleted" };
    }

    const msgPayload = buildCommentMessagePayload(
      { content: args.content, authorName: args.authorName },
      args.timestamp,
    );

    const messageId = await ctx.db.insert("messages", {
      taskId: mapped.taskId,
      authorName: msgPayload.authorName,
      authorType: msgPayload.authorType,
      content: msgPayload.content,
      messageType: msgPayload.messageType,
      type: msgPayload.type,
      timestamp: msgPayload.timestamp,
    });

    await logActivity(ctx, {
      taskId: mapped.taskId,
      eventType: "integration_sync_inbound",
      description: `Comment from ${args.platform} synced to task thread`,
      timestamp: args.timestamp,
    });

    return { inserted: true, messageId };
  },
});

// ---------------------------------------------------------------------------
// Public config mutations — called by settings UI
// ---------------------------------------------------------------------------

/**
 * Get the Linear integration config (for settings UI).
 */
export const getLinearConfig = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db
      .query("integrationConfigs")
      .withIndex("by_platform", (q) => q.eq("platform", "linear"))
      .first();
  },
});

/**
 * Create or update Linear integration config (for settings UI).
 *
 * boardId is required by the schema. When creating a new config without an
 * explicit boardId the handler falls back to the default board. If no default
 * board exists either, the mutation throws.
 */
export const upsertLinearConfig = mutation({
  args: {
    apiKey: v.string(),
    webhookSecret: v.optional(v.string()),
    boardId: v.optional(v.id("boards")),
    enabled: v.boolean(),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("integrationConfigs")
      .withIndex("by_platform", (q) => q.eq("platform", "linear"))
      .first();

    const now = new Date().toISOString();

    if (existing) {
      // Only patch boardId when explicitly provided (avoid clearing a required field)
      const patch: Record<string, unknown> = {
        apiKey: args.apiKey,
        webhookSecret: args.webhookSecret,
        enabled: args.enabled,
        updatedAt: now,
      };
      if (args.boardId !== undefined) {
        patch.boardId = args.boardId;
      }
      await ctx.db.patch(existing._id, patch);
      return existing._id;
    }

    // Resolve boardId: use provided value or fall back to default board
    let boardId = args.boardId;
    if (!boardId) {
      const defaultBoard = await ctx.db
        .query("boards")
        .withIndex("by_isDefault", (q) => q.eq("isDefault", true))
        .first();
      if (!defaultBoard) {
        throw new ConvexError(
          "boardId is required when creating a new integration config. No default board found.",
        );
      }
      boardId = defaultBoard._id;
    }

    return await ctx.db.insert("integrationConfigs", {
      platform: "linear",
      name: "Linear",
      apiKey: args.apiKey,
      webhookSecret: args.webhookSecret,
      boardId,
      enabled: args.enabled,
      syncDirection: "bidirectional" as const,
      createdAt: now,
      updatedAt: now,
    });
  },
});

/**
 * Toggle Linear integration enabled/disabled (for settings UI).
 */
export const toggleLinearEnabled = mutation({
  args: { enabled: v.boolean() },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("integrationConfigs")
      .withIndex("by_platform", (q) => q.eq("platform", "linear"))
      .first();

    if (!existing) {
      throw new ConvexError("Linear integration not configured. Save the API key first.");
    }

    await ctx.db.patch(existing._id, {
      enabled: args.enabled,
      updatedAt: new Date().toISOString(),
    });
  },
});
