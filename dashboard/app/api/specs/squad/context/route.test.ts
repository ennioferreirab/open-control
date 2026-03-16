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
  it("returns active reusable agents with their active skills and available skills catalog", async () => {
    mockQuery.mockImplementation((name: string) => {
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
            available: true,
          },
          {
            name: "private-skill",
            description: "Not available",
            available: false,
          },
        ]);
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
        },
      ],
    });
  });

  it("returns 500 when the context query fails", async () => {
    mockQuery.mockRejectedValue(new Error("boom"));

    const response = await GET();
    const body = await response.json();

    expect(response.status).toBe(500);
    expect(body).toEqual({ error: "boom" });
  });
});
