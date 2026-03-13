import { describe, expect, it, vi } from "vitest";

import { publishProjection, upsertByName } from "./agents";

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
  return (
    upsertByName as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
    }
  )._handler;
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

  it("skips updating soul for compiled agents (compiledFromSpecId is set)", async () => {
    const handler = getHandler();
    const { ctx, patches } = makeCtx({
      _id: "agent-doc-id",
      name: "compiled-agent",
      prompt: "compiled prompt",
      soul: "compiled soul from spec",
      skills: ["skill-a"],
      compiledFromSpecId: "spec-id-xyz",
    });

    await handler(ctx, {
      name: "compiled-agent",
      displayName: "Compiled Agent",
      role: "Worker",
      prompt: "YAML prompt — should not overwrite",
      soul: "YAML soul — should not overwrite",
      skills: ["skill-a"],
    });

    const agentPatch = patches[0]?.patch;
    expect(agentPatch?.soul).toBeUndefined();
    expect(agentPatch?.prompt).toBeUndefined();
  });

  it("updates soul for non-compiled agents from YAML", async () => {
    const handler = getHandler();
    const { ctx, patches } = makeCtx({
      _id: "agent-doc-id",
      name: "yaml-agent",
      prompt: "some prompt",
      soul: "old soul",
      skills: [],
    });

    await handler(ctx, {
      name: "yaml-agent",
      displayName: "YAML Agent",
      role: "Worker",
      soul: "new soul from YAML",
      skills: [],
    });

    const agentPatch = patches[0]?.patch;
    expect(agentPatch?.soul).toBe("new soul from YAML");
  });
});

// ---------------------------------------------------------------------------
// agents.publishProjection
// ---------------------------------------------------------------------------

function getPublishHandler() {
  return (
    publishProjection as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
    }
  )._handler;
}

const baseProjectionArgs = {
  name: "code-reviewer",
  displayName: "Code Reviewer",
  role: "Senior Code Reviewer",
  prompt: "You are a Code Reviewer...",
  soul: "You care deeply about quality.",
  skills: ["git", "code-review"],
  compiledFromSpecId: "spec-id-abc",
  compiledFromVersion: 3,
  compiledAt: "2026-03-13T10:00:00.000Z",
};

describe("agents.publishProjection", () => {
  it("patches an existing agent with prompt, soul, and projection metadata", async () => {
    const { ctx, patches } = makeCtx({
      _id: "agent-existing-id",
      name: "code-reviewer",
      prompt: "old prompt",
      skills: ["git"],
    });

    const handler = getPublishHandler();
    await handler(ctx, baseProjectionArgs);

    const agentPatch = patches[0]?.patch;
    expect(agentPatch).toBeDefined();
    expect(agentPatch?.prompt).toBe("You are a Code Reviewer...");
    expect(agentPatch?.soul).toBe("You care deeply about quality.");
    expect(agentPatch?.compiledFromSpecId).toBe("spec-id-abc");
    expect(agentPatch?.compiledFromVersion).toBe(3);
    expect(agentPatch?.compiledAt).toBe("2026-03-13T10:00:00.000Z");
  });

  it("inserts a new agent when it does not exist yet", async () => {
    const { ctx, inserts } = makeCtx(undefined);

    const handler = getPublishHandler();
    await handler(ctx, baseProjectionArgs);

    const inserted = inserts.find((i) => (i as Record<string, unknown>).name === "code-reviewer");
    expect(inserted).toBeDefined();
    expect(inserted?.compiledFromSpecId).toBe("spec-id-abc");
    expect(inserted?.compiledFromVersion).toBe(3);
    expect(inserted?.compiledAt).toBe("2026-03-13T10:00:00.000Z");
    expect(inserted?.prompt).toBe("You are a Code Reviewer...");
    expect(inserted?.soul).toBe("You care deeply about quality.");
  });

  it("always overwrites prompt on publish (projection takes authority)", async () => {
    // publishProjection differs from upsertByName: it always writes prompt
    const { ctx, patches } = makeCtx({
      _id: "agent-existing-id",
      name: "code-reviewer",
      prompt: "a pre-existing prompt that should be replaced",
      skills: ["git"],
    });

    const handler = getPublishHandler();
    await handler(ctx, baseProjectionArgs);

    const agentPatch = patches[0]?.patch;
    expect(agentPatch?.prompt).toBe("You are a Code Reviewer...");
  });

  it("always overwrites soul on publish", async () => {
    const { ctx, patches } = makeCtx({
      _id: "agent-existing-id",
      name: "code-reviewer",
      soul: "old soul text",
      prompt: "old prompt",
      skills: [],
    });

    const handler = getPublishHandler();
    await handler(ctx, baseProjectionArgs);

    const agentPatch = patches[0]?.patch;
    expect(agentPatch?.soul).toBe("You care deeply about quality.");
  });

  it("carries over model when provided", async () => {
    const { ctx, patches } = makeCtx({
      _id: "agent-existing-id",
      name: "code-reviewer",
      prompt: "old",
      skills: [],
    });

    const handler = getPublishHandler();
    await handler(ctx, { ...baseProjectionArgs, model: "claude-sonnet-4-6" });

    const agentPatch = patches[0]?.patch;
    expect(agentPatch?.model).toBe("claude-sonnet-4-6");
  });

  it("carries over skills from the projection", async () => {
    const { ctx, patches } = makeCtx({
      _id: "agent-existing-id",
      name: "code-reviewer",
      prompt: "old",
      skills: ["old-skill"],
    });

    const handler = getPublishHandler();
    await handler(ctx, baseProjectionArgs);

    const agentPatch = patches[0]?.patch;
    expect(agentPatch?.skills).toEqual(["git", "code-review"]);
  });

  it("throws when publishing to a soft-deleted agent", async () => {
    const { ctx } = makeCtx({
      _id: "agent-deleted-id",
      name: "code-reviewer",
      prompt: "old prompt",
      skills: [],
      deletedAt: "2026-01-01T00:00:00.000Z",
    });

    const handler = getPublishHandler();
    await expect(handler(ctx, baseProjectionArgs)).rejects.toThrow(
      "Cannot publish projection to deleted agent",
    );
  });

  it("writes an activity event after publish", async () => {
    const { ctx, inserts } = makeCtx({
      _id: "agent-existing-id",
      name: "code-reviewer",
      prompt: "old",
      skills: [],
    });

    const handler = getPublishHandler();
    await handler(ctx, baseProjectionArgs);

    const activity = inserts.find(
      (i) => (i as Record<string, unknown>).eventType === "agent_config_updated",
    );
    expect(activity).toBeDefined();
  });
});
