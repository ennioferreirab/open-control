import { describe, expect, it, vi } from "vitest";

import { create } from "./agentSpecs";

type InsertCall = Record<string, unknown>;

function makeCtx(existingSpec?: { _id: string; name: string; [key: string]: unknown }) {
  const inserts: InsertCall[] = [];

  const first = vi.fn(async () => existingSpec ?? null);
  const withIndex = vi.fn(() => ({ first }));
  const query = vi.fn(() => ({ withIndex }));
  const insert = vi.fn(async (_table: string, value: Record<string, unknown>) => {
    inserts.push(value);
    return "new-spec-id";
  });

  return {
    ctx: { db: { query, insert } },
    inserts,
  };
}

function getCreateHandler() {
  return (
    create as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<string>;
    }
  )._handler;
}

describe("agentSpecs.create", () => {
  it("inserts a new agent spec when no duplicate name exists", async () => {
    const handler = getCreateHandler();
    const { ctx, inserts } = makeCtx(undefined);

    await handler(ctx, {
      name: "my-agent",
      displayName: "My Agent",
      role: "Developer",
    });

    expect(inserts).toHaveLength(1);
    expect(inserts[0]).toMatchObject({
      name: "my-agent",
      displayName: "My Agent",
      role: "Developer",
      status: "draft",
      version: 1,
    });
  });

  it("throws when an agent spec with the same name already exists", async () => {
    const handler = getCreateHandler();
    const { ctx } = makeCtx({ _id: "existing-id", name: "my-agent" });

    await expect(
      handler(ctx, {
        name: "my-agent",
        displayName: "My Agent",
        role: "Developer",
      }),
    ).rejects.toThrow("A spec with this name already exists");
  });

  it("sets status to draft and version to 1 on creation", async () => {
    const handler = getCreateHandler();
    const { ctx, inserts } = makeCtx(undefined);

    await handler(ctx, {
      name: "fresh-agent",
      displayName: "Fresh Agent",
      role: "Analyst",
    });

    expect(inserts[0]?.status).toBe("draft");
    expect(inserts[0]?.version).toBe(1);
  });

  it("stores createdAt and updatedAt timestamps", async () => {
    const handler = getCreateHandler();
    const { ctx, inserts } = makeCtx(undefined);

    await handler(ctx, {
      name: "timestamped-agent",
      displayName: "Timestamped Agent",
      role: "Logger",
    });

    expect(typeof inserts[0]?.createdAt).toBe("string");
    expect(typeof inserts[0]?.updatedAt).toBe("string");
  });
});
