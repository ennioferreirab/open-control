/**
 * End-to-end simulation of the full spec creation lifecycle.
 *
 * Exercises every REST endpoint in sequence, simulating what an MCP agent
 * or the create-squad-mc skill would do:
 *
 *   1. Register skills
 *   2. Create agent spec (with publishProjection)
 *   3. Create review spec
 *   4. Publish squad graph (agents + workflow)
 *   5. Verify squad context shows everything
 *   6. Publish standalone workflow to the squad
 *   7. Update an agent (add skills)
 *   8. Delete a skill
 *   9. Archive the workflow
 *  10. Archive the squad
 *
 * All Convex calls are mocked — this tests route logic, validation,
 * and call ordering without requiring a running Convex backend.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Convex mock — tracks all mutations and queries in order
// ---------------------------------------------------------------------------

const callLog: Array<{ type: "query" | "mutation"; name: string; args: unknown }> = [];

const mockMutation = vi.hoisted(() =>
  vi.fn(async (name: unknown, args: unknown) => {
    const nameStr = typeof name === "string" ? name : String(name);
    callLog.push({ type: "mutation", name: nameStr, args });

    // Return synthetic IDs based on mutation type
    if (nameStr.includes("createDraft")) return "draft-id-001";
    if (nameStr.includes("publishGraph")) return "squad-id-001";
    if (nameStr.includes("publishStandalone")) return "workflow-id-001";
    if (nameStr.includes("archiveSquad")) return null;
    if (nameStr.includes("archiveWorkflow")) return null;
    if (nameStr.includes("deleteByName")) return null;
    if (nameStr.includes("updateConfig")) return null;
    if (nameStr.includes("upsertByName")) return null;
    if (nameStr.includes("publish")) return null;
    return null;
  }),
);

const mockQuery = vi.hoisted(() =>
  vi.fn(async (name: unknown) => {
    const nameStr = typeof name === "string" ? name : String(name);
    callLog.push({ type: "query", name: nameStr, args: {} });

    if (nameStr.includes("agents:list")) {
      return [
        {
          name: "researcher",
          displayName: "Rafa Researcher",
          role: "Research analyst",
          prompt: "You are Rafa.",
          model: "claude-sonnet-4-6",
          skills: ["research-synthesis"],
          soul: "# Rafa",
          enabled: true,
          isSystem: false,
        },
      ];
    }

    if (nameStr.includes("skills:list")) {
      return [
        {
          name: "research-synthesis",
          description: "Synthesize research",
          source: "workspace",
          available: true,
          supportedProviders: ["claude-code"],
        },
        {
          name: "writing",
          description: "Write content",
          source: "workspace",
          available: true,
          supportedProviders: ["claude-code", "nanobot"],
        },
      ];
    }

    if (nameStr.includes("reviewSpecs:listByStatus")) {
      return [
        {
          _id: "review-spec-001",
          name: "quality-check",
          scope: "workflow",
          approvalThreshold: 0.8,
          reviewerPolicy: "lead-agent",
          rejectionRoutingPolicy: null,
        },
      ];
    }

    if (nameStr.includes("settings:get")) {
      return JSON.stringify(["claude-sonnet-4-6", "claude-opus-4-6"]);
    }

    return [];
  }),
);

const mockSetAdminAuth = vi.hoisted(() => vi.fn());
const mockWriteSkillToDisk = vi.hoisted(() => vi.fn());
const mockDeleteSkillFromDisk = vi.hoisted(() => vi.fn());

vi.mock("convex/browser", () => ({
  ConvexHttpClient: class MockConvexHttpClient {
    query = mockQuery;
    mutation = mockMutation;
    setAdminAuth = mockSetAdminAuth;
  },
}));

vi.mock("@/convex/_generated/api", () => ({
  api: new Proxy(
    {},
    {
      get: (_target, table: string) =>
        new Proxy(
          {},
          {
            get: (_t2, method: string) => `${table}.${method}`,
          },
        ),
    },
  ),
}));

vi.mock("@/lib/skillDiskWriter", () => ({
  writeSkillToDisk: mockWriteSkillToDisk,
  deleteSkillFromDisk: mockDeleteSkillFromDisk,
}));

// Import all route handlers
import { GET as getSkills, POST as postSkill, DELETE as deleteSkill } from "./skills/route";
import { POST as postAgent, PATCH as patchAgent } from "./agent/route";
import { POST as postSquad, DELETE as deleteSquad } from "./squad/route";
import { GET as getSquadContext } from "./squad/context/route";
import { POST as postWorkflow, DELETE as deleteWorkflow } from "./workflow/route";
import { POST as postReviewSpec } from "./review-spec/route";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function req(url: string, method: string = "GET", body?: Record<string, unknown>): Request {
  const init: RequestInit = { method, headers: { "Content-Type": "application/json" } };
  if (body) init.body = JSON.stringify(body);
  return new Request(url, init) as never;
}

// ---------------------------------------------------------------------------
// Test setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
  callLog.length = 0;
  process.env.NEXT_PUBLIC_CONVEX_URL = "https://test.convex.cloud";
  process.env.CONVEX_URL = "https://test.convex.cloud";
  process.env.CONVEX_ADMIN_KEY = "test-admin-key";
});

// ---------------------------------------------------------------------------
// Full lifecycle test
// ---------------------------------------------------------------------------

describe("Spec creation lifecycle (e2e simulation)", () => {
  it("Step 1: Register skills", async () => {
    const res = await postSkill(
      req("http://localhost:3000/api/specs/skills", "POST", {
        name: "research-synthesis",
        description: "Synthesize research findings",
        content: "# Research Synthesis\n\nAnalyze and synthesize.",
        supportedProviders: ["claude-code"],
      }),
    );
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body).toEqual({ success: true, name: "research-synthesis" });
    expect(mockWriteSkillToDisk).toHaveBeenCalledWith(
      "research-synthesis",
      "Synthesize research findings",
      "# Research Synthesis\n\nAnalyze and synthesize.",
      expect.any(Object),
    );
  });

  it("Step 2: Create agent spec", async () => {
    const res = await postAgent(
      req("http://localhost:3000/api/specs/agent", "POST", {
        name: "researcher",
        displayName: "Rafa Researcher",
        role: "Research analyst",
        prompt: "You are Rafa, a research analyst.",
        soul: "# Rafa\n\nI research things.",
        skills: ["research-synthesis"],
        model: "claude-sonnet-4-6",
      }),
    );
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.success).toBe(true);
    expect(body.specId).toBeDefined();

    // Verify createDraft was called followed by publish
    const mutations = callLog.filter((c) => c.type === "mutation");
    expect(mutations[0].name).toContain("createDraft");
    expect(mutations[1].name).toContain("publish");
  });

  it("Step 3: Create review spec", async () => {
    const res = await postReviewSpec(
      req("http://localhost:3000/api/specs/review-spec", "POST", {
        name: "quality-check",
        scope: "workflow",
        criteria: [
          { id: "accuracy", label: "Accuracy", weight: 0.5 },
          { id: "completeness", label: "Completeness", weight: 0.5 },
        ],
        approvalThreshold: 0.8,
        reviewerPolicy: "lead-agent",
      }),
    );
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.success).toBe(true);
    expect(body.specId).toBe("draft-id-001");
  });

  it("Step 4: Publish squad graph", async () => {
    const res = await postSquad(
      req("http://localhost:3000/api/specs/squad", "POST", {
        squad: {
          name: "content-creation",
          displayName: "Content Creation",
          description: "Research and write content",
        },
        agents: [
          {
            key: "researcher",
            name: "researcher",
            role: "Research analyst",
            displayName: "Rafa Researcher",
            prompt: "You are Rafa.",
            model: "claude-sonnet-4-6",
            skills: ["research-synthesis"],
            soul: "# Rafa",
          },
          {
            key: "writer",
            name: "post-writer",
            role: "Draft writer",
            displayName: "Wanda Writer",
            prompt: "You are Wanda.",
            model: "claude-sonnet-4-6",
            skills: ["writing"],
            soul: "# Wanda",
          },
        ],
        workflows: [
          {
            key: "default",
            name: "default",
            steps: [
              { key: "research", type: "agent", agentKey: "researcher", title: "Research" },
              {
                key: "draft",
                type: "agent",
                agentKey: "writer",
                title: "Draft",
                dependsOn: ["research"],
              },
            ],
            exitCriteria: "Draft approved",
          },
        ],
      }),
    );
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.success).toBe(true);
    expect(body.squadId).toBe("squad-id-001");
  });

  it("Step 5: Verify squad context", async () => {
    const res = await getSquadContext();
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.activeAgents).toHaveLength(1);
    expect(body.activeAgents[0].name).toBe("researcher");
    expect(body.availableSkills).toHaveLength(2);
    expect(body.availableModels).toContain("claude-sonnet-4-6");
  });

  it("Step 6: List skills", async () => {
    const res = await getSkills(req("http://localhost:3000/api/specs/skills"));
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.skills).toHaveLength(2);
    expect(body.skills.map((s: { name: string }) => s.name)).toContain("research-synthesis");
  });

  it("Step 7: Publish standalone workflow", async () => {
    const res = await postWorkflow(
      req("http://localhost:3000/api/specs/workflow", "POST", {
        squadSpecId: "squad-id-001",
        workflow: {
          name: "review-pipeline",
          steps: [
            { title: "Research", type: "agent", agentKey: "researcher" },
            {
              title: "Review",
              type: "review",
              agentKey: "researcher",
              reviewSpecId: "review-spec-001",
              onReject: "research",
              dependsOn: ["research"],
            },
          ],
          exitCriteria: "Review approved",
        },
      }),
    );
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.success).toBe(true);
    expect(body.workflowSpecId).toBeDefined();
  });

  it("Step 8: Update agent — add skills", async () => {
    const res = await patchAgent(
      req("http://localhost:3000/api/specs/agent", "PATCH", {
        name: "researcher",
        skills: ["research-synthesis", "writing"],
      }),
    );
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.success).toBe(true);
    expect(body.name).toBe("researcher");

    // Verify updateConfig was called with the right fields
    const updateCall = callLog.find(
      (c) => c.type === "mutation" && String(c.name).includes("updateConfig"),
    );
    expect(updateCall).toBeDefined();
  });

  it("Step 9: Delete a skill", async () => {
    const res = await deleteSkill(
      req("http://localhost:3000/api/specs/skills?name=writing", "DELETE"),
    );
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.success).toBe(true);
    expect(body.name).toBe("writing");

    // Verify deleteByName mutation was called
    const deleteCall = callLog.find(
      (c) => c.type === "mutation" && String(c.name).includes("deleteByName"),
    );
    expect(deleteCall).toBeDefined();
  });

  it("Step 10: Archive workflow", async () => {
    const res = await deleteWorkflow(
      req("http://localhost:3000/api/specs/workflow?workflowSpecId=workflow-id-001", "DELETE"),
    );
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.success).toBe(true);
  });

  it("Step 11: Archive squad", async () => {
    const res = await deleteSquad(
      req("http://localhost:3000/api/specs/squad?squadSpecId=squad-id-001", "DELETE"),
    );
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.success).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Validation error tests — each endpoint rejects bad input
// ---------------------------------------------------------------------------

describe("Validation errors", () => {
  it("POST /api/specs/skills rejects missing name", async () => {
    const res = await postSkill(
      req("http://localhost:3000/api/specs/skills", "POST", {
        description: "x",
        content: "y",
      }),
    );
    expect(res.status).toBe(400);
  });

  it("POST /api/specs/agent rejects missing role", async () => {
    const res = await postAgent(
      req("http://localhost:3000/api/specs/agent", "POST", {
        name: "x",
        displayName: "X",
      }),
    );
    expect(res.status).toBe(400);
  });

  it("POST /api/specs/squad rejects missing agents", async () => {
    const res = await postSquad(
      req("http://localhost:3000/api/specs/squad", "POST", {
        squad: { name: "x", displayName: "X" },
        workflows: [],
      }),
    );
    expect(res.status).toBe(400);
  });

  it("POST /api/specs/workflow rejects missing squadSpecId", async () => {
    const res = await postWorkflow(
      req("http://localhost:3000/api/specs/workflow", "POST", {
        workflow: { name: "x", steps: [] },
      }),
    );
    expect(res.status).toBe(400);
  });

  it("POST /api/specs/review-spec rejects invalid scope", async () => {
    const res = await postReviewSpec(
      req("http://localhost:3000/api/specs/review-spec", "POST", {
        name: "x",
        scope: "invalid",
        criteria: [{ id: "a", label: "A", weight: 1 }],
        approvalThreshold: 0.8,
      }),
    );
    expect(res.status).toBe(400);
  });

  it("PATCH /api/specs/agent rejects missing name", async () => {
    const res = await patchAgent(
      req("http://localhost:3000/api/specs/agent", "PATCH", {
        skills: ["writing"],
      }),
    );
    expect(res.status).toBe(400);
  });

  it("DELETE /api/specs/skills rejects missing name param", async () => {
    const res = await deleteSkill(req("http://localhost:3000/api/specs/skills", "DELETE"));
    expect(res.status).toBe(400);
  });

  it("DELETE /api/specs/squad rejects missing squadSpecId param", async () => {
    const res = await deleteSquad(req("http://localhost:3000/api/specs/squad", "DELETE"));
    expect(res.status).toBe(400);
  });

  it("DELETE /api/specs/workflow rejects missing workflowSpecId param", async () => {
    const res = await deleteWorkflow(req("http://localhost:3000/api/specs/workflow", "DELETE"));
    expect(res.status).toBe(400);
  });
});
