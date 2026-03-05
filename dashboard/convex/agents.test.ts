import { describe, expect, it, vi } from "vitest";

import { upsertByName } from "./agents";

type PatchCall = {
  id: string;
  patch: Record<string, unknown>;
};

function makeCtx(existingAgent?: {
  _id: string;
  name: string;
  prompt?: string;
  variables?: unknown[];
  [key: string]: unknown;
}) {
  const patches: PatchCall[] = [];
  const inserts: Record<string, unknown>[] = [];

  const first = vi.fn(async () => existingAgent ?? null);
  const withIndex = vi.fn(() => ({ first }));
  const query = vi.fn(() => ({ withIndex }));
  const patch = vi.fn(async (id: string, p: Record<string, unknown>) => {
    patches.push({ id, patch: p });
  });
  const insert = vi.fn(async (_table: string, value: Record<string, unknown>) => {
    inserts.push(value);
    return "new-agent-id";
  });

  return {
    ctx: { db: { query, patch, insert } },
    patches,
    inserts,
  };
}

function getHandler() {
  return (upsertByName as unknown as {
    _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
  })._handler;
}

describe("agents.upsertByName", () => {
  it("preserves existing Convex prompt when agent already exists (Convex is source of truth)", async () => {
    const handler = getHandler();
    const existingPrompt = "Convex-edited prompt with {{p_channel_list}}";
    const { ctx, patches } = makeCtx({
      _id: "agent-doc-id",
      name: "youtube-summarizer",
      prompt: existingPrompt,
    });

    await handler(ctx, {
      name: "youtube-summarizer",
      displayName: "YouTube Summarizer",
      role: "Summarizer",
      prompt: "YAML prompt — should NOT overwrite Convex",
      skills: [],
    });

    const agentPatch = patches[0]?.patch;
    expect(agentPatch).toBeDefined();
    // prompt must NOT be updated when agent already has one in Convex
    expect(agentPatch?.prompt).toBeUndefined();
  });

  it("sets prompt on first INSERT when agent does not exist yet", async () => {
    const handler = getHandler();
    const { ctx, inserts } = makeCtx(undefined); // no existing agent

    await handler(ctx, {
      name: "new-agent",
      displayName: "New Agent",
      role: "Helper",
      prompt: "Initial prompt from YAML",
      skills: [],
    });

    const agentInsert = inserts.find((i) => (i as Record<string, unknown>).name === "new-agent");
    expect(agentInsert).toBeDefined();
    expect(agentInsert?.prompt).toBe("Initial prompt from YAML");
  });

  it("preserves existing Convex variables when agent already exists", async () => {
    const handler = getHandler();
    const existingVariables = [{ name: "p_channel_list", value: "https://youtube.com/@AIJasonZ" }];
    const { ctx, patches } = makeCtx({
      _id: "agent-doc-id",
      name: "youtube-summarizer",
      prompt: "some prompt",
      variables: existingVariables,
    });

    await handler(ctx, {
      name: "youtube-summarizer",
      displayName: "YouTube Summarizer",
      role: "Summarizer",
      prompt: "YAML prompt",
      skills: [],
    });

    // variables must not be touched by upsertByName (they are Convex-only)
    const agentPatch = patches[0]?.patch;
    expect(agentPatch?.variables).toBeUndefined();
  });

  it("preserves existing Convex skills when agent already exists", async () => {
    const handler = getHandler();
    const { ctx, patches } = makeCtx({
      _id: "agent-doc-id",
      name: "youtube-summarizer",
      prompt: "some prompt",
      skills: ["youtube-watcher", "cron"],
    });

    await handler(ctx, {
      name: "youtube-summarizer",
      displayName: "YouTube Summarizer",
      role: "Summarizer",
      prompt: "YAML prompt",
      skills: ["legacy-yaml-skill"],
    });

    const agentPatch = patches[0]?.patch;
    expect(agentPatch?.skills).toBeUndefined();
  });

  it("bootstraps skills from YAML when existing agent has none yet", async () => {
    const handler = getHandler();
    const { ctx, patches } = makeCtx({
      _id: "agent-doc-id",
      name: "youtube-summarizer",
      prompt: "some prompt",
      skills: [],
    });

    await handler(ctx, {
      name: "youtube-summarizer",
      displayName: "YouTube Summarizer",
      role: "Summarizer",
      prompt: "YAML prompt",
      skills: ["youtube-watcher", "cron"],
    });

    const agentPatch = patches[0]?.patch;
    expect(agentPatch?.skills).toEqual(["youtube-watcher", "cron"]);
  });
});
