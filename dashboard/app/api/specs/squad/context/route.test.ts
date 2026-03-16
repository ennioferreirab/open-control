import { beforeEach, describe, expect, it, vi } from "vitest";

const mockQuery = vi.hoisted(() => vi.fn());
const mockSetAdminAuth = vi.hoisted(() => vi.fn());

vi.mock("convex/browser", () => ({
  ConvexHttpClient: class MockConvexHttpClient {
    query = mockQuery;
    setAdminAuth = mockSetAdminAuth;
  },
}));

import { GET } from "./route";

beforeEach(() => {
  vi.resetAllMocks();
  process.env.NEXT_PUBLIC_CONVEX_URL = "https://example.convex.cloud";
  process.env.CONVEX_ADMIN_KEY = "test-admin-key";
});

describe("GET /api/specs/squad/context", () => {
  it("returns active reusable agents plus full skill catalog metadata for skills-first discovery", async () => {
    mockQuery.mockImplementation((name: string, args?: Record<string, unknown>) => {
      if (name === "agents:list") {
        return Promise.resolve([
          {
            name: "writer-agent",
            displayName: "Writer Agent",
            role: "Content writer",
            prompt: "Write concise content",
            model: "claude-sonnet-4-6",
            skills: ["writing", "editing"],
            soul: "Writer soul",
            enabled: true,
            isSystem: false,
          },
          {
            name: "remote-terminal",
            displayName: "Remote Terminal",
            role: "remote-terminal",
            skills: ["ssh"],
            enabled: true,
            isSystem: false,
          },
          {
            name: "lead-agent",
            displayName: "Lead Agent",
            role: "Coordinator",
            skills: ["planning"],
            enabled: true,
            isSystem: true,
          },
        ]);
      }

      if (name === "skills:list") {
        return Promise.resolve([
          {
            name: "writing",
            description: "Create clear written content",
            source: "workspace",
            always: false,
            available: true,
            supportedProviders: ["claude-code", "nanobot"],
            requires: "OPENAI_API_KEY",
            metadata: '{"categories":["content","writing"]}',
          },
          {
            name: "private-skill",
            description: "Not available",
            source: "builtin",
            available: false,
            supportedProviders: ["claude-code", "codex", "nanobot"],
          },
        ]);
      }

      if (name === "reviewSpecs:listByStatus") {
        expect(args).toEqual({ status: "published" });
        return Promise.resolve([
          {
            _id: "review-spec-1",
            name: "brief-quality-check",
            scope: "task_output",
            approvalThreshold: 0.8,
            reviewerPolicy: "Senior reviewer",
            rejectionRoutingPolicy: "Return to drafter",
          },
        ]);
      }

      if (name === "settings:get") {
        return Promise.resolve(JSON.stringify(["claude-sonnet-4-6", "claude-opus-4-6"]));
      }

      throw new Error(`Unexpected query ${name}`);
    });

    const response = await GET();
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(mockSetAdminAuth).toHaveBeenCalledWith("test-admin-key");
    expect(body).toEqual({
      activeAgents: [
        {
          name: "writer-agent",
          displayName: "Writer Agent",
          role: "Content writer",
          prompt: "Write concise content",
          model: "claude-sonnet-4-6",
          skills: ["writing", "editing"],
          soul: "Writer soul",
        },
      ],
      availableSkills: [
        {
          name: "writing",
          description: "Create clear written content",
          source: "workspace",
          always: false,
          supportedProviders: ["claude-code", "nanobot"],
          requires: "OPENAI_API_KEY",
          metadata: { categories: ["content", "writing"] },
        },
      ],
      knownSkills: [
        {
          name: "writing",
          description: "Create clear written content",
          source: "workspace",
          always: false,
          available: true,
          supportedProviders: ["claude-code", "nanobot"],
          requires: "OPENAI_API_KEY",
          metadata: { categories: ["content", "writing"] },
        },
        {
          name: "private-skill",
          description: "Not available",
          source: "builtin",
          always: false,
          available: false,
          supportedProviders: ["claude-code", "codex", "nanobot"],
          requires: null,
          metadata: null,
        },
      ],
      availableReviewSpecs: [
        {
          id: "review-spec-1",
          name: "brief-quality-check",
          scope: "task_output",
          approvalThreshold: 0.8,
          reviewerPolicy: "Senior reviewer",
          rejectionRoutingPolicy: "Return to drafter",
        },
      ],
      availableModels: ["claude-sonnet-4-6", "claude-opus-4-6"],
    });
  });

  it("falls back to raw metadata string when skill metadata is not valid JSON", async () => {
    mockQuery.mockImplementation((name: string) => {
      if (name === "agents:list") {
        return Promise.resolve([]);
      }

      if (name === "skills:list") {
        return Promise.resolve([
          {
            name: "skill-creator",
            description: "Create new skills",
            source: "builtin",
            available: true,
            supportedProviders: ["claude-code", "codex", "nanobot"],
            metadata: "not-json",
          },
        ]);
      }

      if (name === "reviewSpecs:listByStatus") {
        return Promise.resolve([]);
      }

      if (name === "settings:get") {
        return Promise.resolve(null);
      }

      throw new Error(`Unexpected query ${name}`);
    });

    const response = await GET();
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.availableSkills).toEqual([
      {
        name: "skill-creator",
        description: "Create new skills",
        source: "builtin",
        always: false,
        supportedProviders: ["claude-code", "codex", "nanobot"],
        requires: null,
        metadata: "not-json",
      },
    ]);
    expect(body.knownSkills).toEqual([
      {
        name: "skill-creator",
        description: "Create new skills",
        source: "builtin",
        always: false,
        available: true,
        supportedProviders: ["claude-code", "codex", "nanobot"],
        requires: null,
        metadata: "not-json",
      },
    ]);
    expect(body.availableReviewSpecs).toEqual([]);
  });

  it("returns 500 when the context query fails", async () => {
    mockQuery.mockRejectedValue(new Error("boom"));

    const response = await GET();
    const body = await response.json();

    expect(response.status).toBe(500);
    expect(body).toEqual({ error: "boom" });
  });
});
