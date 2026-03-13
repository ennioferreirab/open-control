import type { Doc, Id } from "./_generated/dataModel";
import { internalMutation, internalQuery, mutation, query } from "./_generated/server";
import type { MutationCtx } from "./_generated/server";
import { ConvexError, v } from "convex/values";

import {
  interactiveSessionCapabilityValidator,
  interactiveSessionControlModeValidator,
  interactiveSessionScopeKindValidator,
  interactiveSessionStatusValidator,
} from "./schema";

function omitAttachToken<T extends { attachToken?: string }>(session: T): Omit<T, "attachToken"> {
  const safeSession = { ...session };
  delete safeSession.attachToken;
  return safeSession;
}

type InteractiveSessionDoc = Doc<"interactiveSessions">;
type TaskDoc = Doc<"tasks">;
type StepDoc = Doc<"steps">;

export const upsert = internalMutation({
  args: {
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
    createdAt: v.optional(v.string()),
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
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("interactiveSessions")
      .withIndex("by_sessionId", (q) => q.eq("sessionId", args.sessionId))
      .first();

    if (existing) {
      await ctx.db.patch(existing._id, {
        agentName: args.agentName,
        provider: args.provider,
        scopeKind: args.scopeKind,
        scopeId: args.scopeId,
        surface: args.surface,
        tmuxSession: args.tmuxSession,
        status: args.status,
        capabilities: args.capabilities,
        attachToken: args.attachToken,
        updatedAt: args.updatedAt,
        lastActiveAt: args.lastActiveAt,
        endedAt: args.endedAt,
        taskId: args.taskId,
        stepId: args.stepId,
        supervisionState: args.supervisionState,
        activeTurnId: args.activeTurnId,
        activeItemId: args.activeItemId,
        lastEventKind: args.lastEventKind,
        lastEventAt: args.lastEventAt,
        lastError: args.lastError,
        summary: args.summary,
        finalResult: args.finalResult,
        finalResultSource: args.finalResultSource,
        finalResultAt: args.finalResultAt,
        controlMode: args.controlMode,
        manualTakeoverAt: args.manualTakeoverAt,
        manualCompletionRequestedAt: args.manualCompletionRequestedAt,
      });
      return;
    }

    await ctx.db.insert("interactiveSessions", {
      sessionId: args.sessionId,
      agentName: args.agentName,
      provider: args.provider,
      scopeKind: args.scopeKind,
      scopeId: args.scopeId,
      surface: args.surface,
      tmuxSession: args.tmuxSession,
      status: args.status,
      capabilities: args.capabilities,
      attachToken: args.attachToken,
      createdAt: args.createdAt ?? args.updatedAt,
      updatedAt: args.updatedAt,
      lastActiveAt: args.lastActiveAt,
      endedAt: args.endedAt,
      taskId: args.taskId,
      stepId: args.stepId,
      supervisionState: args.supervisionState,
      activeTurnId: args.activeTurnId,
      activeItemId: args.activeItemId,
      lastEventKind: args.lastEventKind,
      lastEventAt: args.lastEventAt,
      lastError: args.lastError,
      summary: args.summary,
      finalResult: args.finalResult,
      finalResultSource: args.finalResultSource,
      finalResultAt: args.finalResultAt,
      controlMode: args.controlMode,
      manualTakeoverAt: args.manualTakeoverAt,
      manualCompletionRequestedAt: args.manualCompletionRequestedAt,
    });
  },
});

export const get = query({
  args: { sessionId: v.string() },
  handler: async (ctx, args) => {
    const session = await ctx.db
      .query("interactiveSessions")
      .withIndex("by_sessionId", (q) => q.eq("sessionId", args.sessionId))
      .first();
    if (!session) {
      return null;
    }
    return omitAttachToken(session);
  },
});

export const getForRuntime = internalQuery({
  args: { sessionId: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("interactiveSessions")
      .withIndex("by_sessionId", (q) => q.eq("sessionId", args.sessionId))
      .first();
  },
});

export const listSessions = query({
  args: {
    agentName: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const agentName = args.agentName;
    if (typeof agentName === "string") {
      const sessions = await ctx.db
        .query("interactiveSessions")
        .withIndex("by_agentName", (q) => q.eq("agentName", agentName))
        .collect();
      return sessions.map(omitAttachToken);
    }

    const sessions = await ctx.db.query("interactiveSessions").collect();
    return sessions.map(omitAttachToken);
  },
});

export const listForRuntime = internalQuery({
  args: {
    agentName: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const agentName = args.agentName;
    if (typeof agentName === "string") {
      return await ctx.db
        .query("interactiveSessions")
        .withIndex("by_agentName", (q) => q.eq("agentName", agentName))
        .collect();
    }

    return await ctx.db.query("interactiveSessions").collect();
  },
});

async function requireSessionForControl(
  ctx: MutationCtx,
  args: {
    sessionId: string;
    taskId: Id<"tasks">;
    stepId: Id<"steps">;
    agentName: string;
    provider: string;
  },
): Promise<{
  session: InteractiveSessionDoc;
  task: TaskDoc;
  step: StepDoc;
}> {
  const session = await ctx.db
    .query("interactiveSessions")
    .withIndex("by_sessionId", (q) => q.eq("sessionId", args.sessionId))
    .first();
  if (!session) {
    throw new ConvexError("Interactive session not found");
  }
  if (session.taskId !== args.taskId || session.stepId !== args.stepId) {
    throw new ConvexError("Interactive session does not match the active task step");
  }
  if (session.agentName !== args.agentName || session.provider !== args.provider) {
    throw new ConvexError("Interactive session does not match the expected agent/provider");
  }

  const [task, step] = await Promise.all([ctx.db.get(args.taskId), ctx.db.get(args.stepId)]);
  if (!task) {
    throw new ConvexError("Task not found");
  }
  if (!step) {
    throw new ConvexError("Step not found");
  }
  return {
    session,
    task,
    step,
  };
}

export const requestHumanTakeover = mutation({
  args: {
    sessionId: v.string(),
    taskId: v.id("tasks"),
    stepId: v.id("steps"),
    agentName: v.string(),
    provider: v.string(),
  },
  handler: async (ctx, args) => {
    const { session, task, step } = await requireSessionForControl(ctx, args);
    const timestamp = new Date().toISOString();

    await ctx.db.patch(session._id, {
      controlMode: "human",
      manualTakeoverAt: timestamp,
      updatedAt: timestamp,
    });
    await ctx.db.patch(task._id, {
      status: "review",
      updatedAt: timestamp,
    });
    await ctx.db.patch(step._id, {
      status: "review",
    });
    await ctx.db.insert("activities", {
      taskId: task._id,
      agentName: args.agentName,
      eventType: "review_requested",
      description: `Human operator took over the Live session for step "${step.title}".`,
      timestamp,
    });
    await ctx.db.insert("messages", {
      taskId: task._id,
      stepId: step._id,
      authorName: "System",
      authorType: "system",
      content: `Human operator took over Live execution for step "${step.title}".`,
      messageType: "system_event",
      type: "comment",
      timestamp,
    });
    return { sessionId: session.sessionId, controlMode: "human" };
  },
});

export const resumeAgentControl = mutation({
  args: {
    sessionId: v.string(),
    taskId: v.id("tasks"),
    stepId: v.id("steps"),
    agentName: v.string(),
    provider: v.string(),
  },
  handler: async (ctx, args) => {
    const { session, task, step } = await requireSessionForControl(ctx, args);
    const timestamp = new Date().toISOString();

    await ctx.db.patch(session._id, {
      controlMode: "agent",
      updatedAt: timestamp,
    });
    await ctx.db.patch(task._id, {
      status: "in_progress",
      updatedAt: timestamp,
    });
    await ctx.db.patch(step._id, {
      status: "running",
      startedAt: step.startedAt ?? timestamp,
      errorMessage: undefined,
    });
    await ctx.db.insert("activities", {
      taskId: task._id,
      agentName: args.agentName,
      eventType: "step_started",
      description: `Live session returned to agent control for step "${step.title}".`,
      timestamp,
    });
    return { sessionId: session.sessionId, controlMode: "agent" };
  },
});

export const markManualStepDone = mutation({
  args: {
    sessionId: v.string(),
    taskId: v.id("tasks"),
    stepId: v.id("steps"),
    agentName: v.string(),
    provider: v.string(),
    content: v.string(),
  },
  handler: async (ctx, args) => {
    const { session, task, step } = await requireSessionForControl(ctx, args);
    const timestamp = new Date().toISOString();
    const content = args.content.trim();
    if (!content) {
      throw new ConvexError("Manual step completion requires non-empty content");
    }

    await ctx.db.patch(session._id, {
      controlMode: "human",
      finalResult: content,
      finalResultSource: "human-takeover",
      finalResultAt: timestamp,
      manualCompletionRequestedAt: timestamp,
      updatedAt: timestamp,
    });
    await ctx.db.insert("messages", {
      taskId: task._id,
      stepId: step._id,
      authorName: "Human operator",
      authorType: "system",
      content: `Human intervention completed this step manually.\n\n${content}`,
      messageType: "system_event",
      type: "comment",
      timestamp,
    });
    await ctx.db.insert("activities", {
      taskId: task._id,
      agentName: args.agentName,
      eventType: "step_completed",
      description: `Human operator completed step "${step.title}" manually from Live.`,
      timestamp,
    });
    return {
      sessionId: session.sessionId,
      stepId: step._id,
      finalResultSource: "human-takeover",
    };
  },
});
