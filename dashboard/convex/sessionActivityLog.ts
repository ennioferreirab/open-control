import { internalMutation, query } from "./_generated/server";
import { v } from "convex/values";

const TOOL_INPUT_MAX = 2000;
const SUMMARY_MAX = 1000;
const ERROR_MAX = 2000;
const RAW_TEXT_MAX = 4000;
const RAW_JSON_MAX = 8000;

export const append = internalMutation({
  args: {
    sessionId: v.string(),
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
    sourceType: v.optional(v.string()),
    sourceSubtype: v.optional(v.string()),
    groupKey: v.optional(v.string()),
    rawText: v.optional(v.string()),
    rawJson: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const last = await ctx.db
      .query("sessionActivityLog")
      .withIndex("by_session_seq", (q) => q.eq("sessionId", args.sessionId))
      .order("desc")
      .take(1);

    const maxSeq = last.length > 0 ? last[0].seq : 0;
    const seq = maxSeq + 1;

    await ctx.db.insert("sessionActivityLog", {
      sessionId: args.sessionId,
      seq,
      kind: args.kind,
      ts: args.ts,
      toolName: args.toolName,
      toolInput: args.toolInput !== undefined ? args.toolInput.slice(0, TOOL_INPUT_MAX) : undefined,
      filePath: args.filePath,
      summary: args.summary !== undefined ? args.summary.slice(0, SUMMARY_MAX) : undefined,
      error: args.error !== undefined ? args.error.slice(0, ERROR_MAX) : undefined,
      turnId: args.turnId,
      itemId: args.itemId,
      stepId: args.stepId,
      agentName: args.agentName,
      provider: args.provider,
      requiresAction: args.requiresAction,
      sourceType: args.sourceType,
      sourceSubtype: args.sourceSubtype,
      groupKey: args.groupKey,
      rawText: args.rawText !== undefined ? args.rawText.slice(0, RAW_TEXT_MAX) : undefined,
      rawJson: args.rawJson !== undefined ? args.rawJson.slice(0, RAW_JSON_MAX) : undefined,
    });
  },
});

export const listForSession = query({
  args: { sessionId: v.string() },
  handler: async (ctx, args) => {
    const events = await ctx.db
      .query("sessionActivityLog")
      .withIndex("by_session_seq", (q) => q.eq("sessionId", args.sessionId))
      .order("asc")
      .take(500);

    return events;
  },
});
