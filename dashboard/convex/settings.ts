import { mutation, query } from "./_generated/server";
import { v } from "convex/values";
import { isChatHandlerRuntime } from "../lib/chatSyncRuntime";
import { isGatewaySleepRuntime } from "../lib/gatewaySleepRuntime";

function parseJson<T>(value: string | undefined | null): T | null {
  if (!value) {
    return null;
  }

  try {
    return JSON.parse(value) as T;
  } catch {
    return null;
  }
}

export const list = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db.query("settings").collect();
  },
});

export const get = query({
  args: { key: v.string() },
  handler: async (ctx, args) => {
    const setting = await ctx.db
      .query("settings")
      .withIndex("by_key", (q) => q.eq("key", args.key))
      .first();
    return setting?.value ?? null;
  },
});

export const getChatHandlerRuntime = query({
  args: {},
  handler: async (ctx) => {
    const setting = await ctx.db
      .query("settings")
      .withIndex("by_key", (q) => q.eq("key", "chat_handler_runtime"))
      .first();

    if (!setting?.value) {
      return null;
    }

    try {
      const parsed = JSON.parse(setting.value);
      return isChatHandlerRuntime(parsed) ? parsed : null;
    } catch {
      return null;
    }
  },
});

export const getGatewaySleepRuntime = query({
  args: {},
  handler: async (ctx) => {
    const setting = await ctx.db
      .query("settings")
      .withIndex("by_key", (q) => q.eq("key", "gateway_sleep_runtime"))
      .first();

    const parsed = parseJson<unknown>(setting?.value);
    return isGatewaySleepRuntime(parsed) ? parsed : null;
  },
});

export const getGatewaySleepControl = query({
  args: {},
  handler: async (ctx) => {
    const setting = await ctx.db
      .query("settings")
      .withIndex("by_key", (q) => q.eq("key", "gateway_sleep_control"))
      .first();

    const parsed = parseJson<Record<string, unknown>>(setting?.value);
    if (
      !parsed ||
      (parsed.mode !== "sleep" && parsed.mode !== "active") ||
      typeof parsed.requestedAt !== "string"
    ) {
      return null;
    }

    return parsed;
  },
});

export const set = mutation({
  args: {
    key: v.string(),
    value: v.string(),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("settings")
      .withIndex("by_key", (q) => q.eq("key", args.key))
      .first();

    if (existing) {
      await ctx.db.patch(existing._id, { value: args.value });
    } else {
      await ctx.db.insert("settings", { key: args.key, value: args.value });
    }
  },
});

export const requestGatewaySleepMode = mutation({
  args: {
    mode: v.union(v.literal("sleep"), v.literal("active")),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("settings")
      .withIndex("by_key", (q) => q.eq("key", "gateway_sleep_control"))
      .first();

    const value = JSON.stringify({
      mode: args.mode,
      requestedAt: new Date().toISOString(),
    });

    if (existing) {
      await ctx.db.patch(existing._id, { value });
    } else {
      await ctx.db.insert("settings", { key: "gateway_sleep_control", value });
    }
  },
});
