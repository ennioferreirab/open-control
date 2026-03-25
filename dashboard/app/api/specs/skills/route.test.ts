import { beforeEach, describe, expect, it, vi } from "vitest";

const mockQuery = vi.hoisted(() => vi.fn());
const mockMutation = vi.hoisted(() => vi.fn());
const mockSetAdminAuth = vi.hoisted(() => vi.fn());
const mockWriteSkillToDisk = vi.hoisted(() => vi.fn());

vi.mock("convex/browser", () => ({
  ConvexHttpClient: class MockConvexHttpClient {
    query = mockQuery;
    mutation = mockMutation;
    setAdminAuth = mockSetAdminAuth;
  },
}));

vi.mock("@/lib/skillDiskWriter", () => ({
  writeSkillToDisk: mockWriteSkillToDisk,
}));

import { GET, POST } from "./route";

beforeEach(() => {
  vi.resetAllMocks();
  process.env.NEXT_PUBLIC_CONVEX_URL = "https://example.convex.cloud";
  process.env.CONVEX_ADMIN_KEY = "test-admin-key";
});

function makeGetRequest(url = "http://localhost:3000/api/specs/skills") {
  return new Request(url) as Parameters<typeof GET>[0];
}

function makePostRequest(body: Record<string, unknown>) {
  return new Request("http://localhost:3000/api/specs/skills", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }) as Parameters<typeof POST>[0];
}

describe("GET /api/specs/skills", () => {
  it("returns all skills with parsed metadata", async () => {
    mockQuery.mockResolvedValue([
      {
        name: "writing",
        description: "Create clear written content",
        source: "workspace",
        always: false,
        available: true,
        supportedProviders: ["claude-code", "nanobot"],
        requires: "OPENAI_API_KEY",
        metadata: '{"categories":["content"]}',
      },
      {
        name: "private-skill",
        description: "Not available",
        source: "builtin",
        available: false,
        supportedProviders: ["claude-code"],
      },
    ]);

    const response = await GET(makeGetRequest());
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(mockSetAdminAuth).toHaveBeenCalledWith("test-admin-key");
    expect(body).toEqual({
      skills: [
        {
          name: "writing",
          description: "Create clear written content",
          source: "workspace",
          always: false,
          available: true,
          supportedProviders: ["claude-code", "nanobot"],
          requires: "OPENAI_API_KEY",
          metadata: { categories: ["content"] },
        },
        {
          name: "private-skill",
          description: "Not available",
          source: "builtin",
          always: false,
          available: false,
          supportedProviders: ["claude-code"],
          requires: null,
          metadata: null,
        },
      ],
    });
  });

  it("filters to available-only when ?available=true", async () => {
    mockQuery.mockResolvedValue([
      {
        name: "writing",
        description: "Create clear written content",
        source: "workspace",
        available: true,
        supportedProviders: ["claude-code"],
      },
      {
        name: "private-skill",
        description: "Not available",
        source: "builtin",
        available: false,
        supportedProviders: ["claude-code"],
      },
    ]);

    const response = await GET(
      makeGetRequest("http://localhost:3000/api/specs/skills?available=true"),
    );
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.skills).toHaveLength(1);
    expect(body.skills[0].name).toBe("writing");
  });

  it("returns 500 when query fails", async () => {
    mockQuery.mockRejectedValue(new Error("boom"));

    const response = await GET(makeGetRequest());
    const body = await response.json();

    expect(response.status).toBe(500);
    expect(body).toEqual({ error: "boom" });
  });
});

describe("POST /api/specs/skills", () => {
  it("registers a skill and writes SKILL.md to disk", async () => {
    mockMutation.mockResolvedValue(undefined);

    const response = await POST(
      makePostRequest({
        name: "my-skill",
        description: "Does something useful",
        content: "# My Skill\nDo the thing.",
      }),
    );
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body).toEqual({ success: true, name: "my-skill" });

    // Verify disk write
    expect(mockWriteSkillToDisk).toHaveBeenCalledWith(
      "my-skill",
      "Does something useful",
      "# My Skill\nDo the thing.",
      { always: false, metadata: undefined },
    );

    // Verify Convex mutation
    expect(mockMutation).toHaveBeenCalledWith("skills:upsertByName", {
      name: "my-skill",
      description: "Does something useful",
      content: "# My Skill\nDo the thing.",
      source: "workspace",
      supportedProviders: ["claude-code"],
      available: true,
      metadata: undefined,
      always: undefined,
      requires: undefined,
    });
  });

  it("passes always option to disk writer when true", async () => {
    mockMutation.mockResolvedValue(undefined);

    await POST(
      makePostRequest({
        name: "x",
        description: "y",
        content: "z",
        always: true,
      }),
    );

    expect(mockWriteSkillToDisk).toHaveBeenCalledWith(
      "x",
      "y",
      "z",
      expect.objectContaining({ always: true }),
    );
  });

  it("passes metadata option to disk writer when provided", async () => {
    mockMutation.mockResolvedValue(undefined);

    await POST(
      makePostRequest({
        name: "x",
        description: "y",
        content: "z",
        metadata: '{"cat":"tools"}',
      }),
    );

    expect(mockWriteSkillToDisk).toHaveBeenCalledWith(
      "x",
      "y",
      "z",
      expect.objectContaining({ metadata: '{"cat":"tools"}' }),
    );
  });

  it("disk write happens before Convex mutation", async () => {
    const callOrder: string[] = [];
    mockWriteSkillToDisk.mockImplementation(() => callOrder.push("disk"));
    mockMutation.mockImplementation(() => {
      callOrder.push("convex");
      return Promise.resolve();
    });

    await POST(makePostRequest({ name: "x", description: "y", content: "z" }));

    expect(callOrder).toEqual(["disk", "convex"]);
  });

  it("returns 500 when disk write fails (Convex not called)", async () => {
    mockWriteSkillToDisk.mockImplementation(() => {
      throw new Error("disk full");
    });

    const response = await POST(makePostRequest({ name: "x", description: "y", content: "z" }));
    const body = await response.json();

    expect(response.status).toBe(500);
    expect(body.error).toBe("disk full");
    expect(mockMutation).not.toHaveBeenCalled();
  });

  it("registers a skill with all optional fields", async () => {
    mockMutation.mockResolvedValue(undefined);

    const response = await POST(
      makePostRequest({
        name: "full-skill",
        description: "Full skill",
        content: "# Full",
        source: "builtin",
        supportedProviders: ["claude-code", "nanobot"],
        available: true,
        always: true,
        requires: "SOME_KEY",
        metadata: '{"category":"tools"}',
      }),
    );
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body).toEqual({ success: true, name: "full-skill" });
    expect(mockMutation).toHaveBeenCalledWith("skills:upsertByName", {
      name: "full-skill",
      description: "Full skill",
      content: "# Full",
      source: "builtin",
      supportedProviders: ["claude-code", "nanobot"],
      available: true,
      always: true,
      requires: "SOME_KEY",
      metadata: '{"category":"tools"}',
    });
  });

  it("returns 400 when name is missing", async () => {
    const response = await POST(makePostRequest({ description: "x", content: "y" }));
    const body = await response.json();

    expect(response.status).toBe(400);
    expect(body.error).toContain("name");
  });

  it("returns 400 when description is missing", async () => {
    const response = await POST(makePostRequest({ name: "x", content: "y" }));
    const body = await response.json();

    expect(response.status).toBe(400);
    expect(body.error).toContain("description");
  });

  it("returns 400 when content is missing", async () => {
    const response = await POST(makePostRequest({ name: "x", description: "y" }));
    const body = await response.json();

    expect(response.status).toBe(400);
    expect(body.error).toContain("content");
  });

  it("returns 400 for invalid source", async () => {
    const response = await POST(
      makePostRequest({
        name: "x",
        description: "y",
        content: "z",
        source: "invalid",
      }),
    );
    const body = await response.json();

    expect(response.status).toBe(400);
    expect(body.error).toContain("source");
  });

  it("serializes object metadata to JSON string", async () => {
    mockMutation.mockResolvedValue(undefined);

    await POST(
      makePostRequest({
        name: "x",
        description: "y",
        content: "z",
        metadata: { category: "tools" },
      }),
    );

    expect(mockMutation).toHaveBeenCalledWith(
      "skills:upsertByName",
      expect.objectContaining({ metadata: '{"category":"tools"}' }),
    );
  });

  it("returns 500 when mutation fails", async () => {
    mockMutation.mockRejectedValue(new Error("mutation failed"));

    const response = await POST(makePostRequest({ name: "x", description: "y", content: "z" }));
    const body = await response.json();

    expect(response.status).toBe(500);
    expect(body.error).toBe("mutation failed");
  });
});
