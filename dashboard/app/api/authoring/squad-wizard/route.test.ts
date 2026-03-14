import { beforeEach, describe, expect, it, vi } from "vitest";

const mockExecFn = vi.hoisted(() => vi.fn());
const mockWriteFile = vi.hoisted(() => vi.fn());
const mockUnlink = vi.hoisted(() => vi.fn());

vi.mock("child_process", () => ({
  default: { exec: mockExecFn },
  exec: mockExecFn,
}));

vi.mock("util", () => ({
  default: { promisify: () => mockExecFn },
  promisify: () => mockExecFn,
}));

vi.mock("fs/promises", () => ({
  default: {
    writeFile: mockWriteFile,
    unlink: mockUnlink,
  },
  writeFile: mockWriteFile,
  unlink: mockUnlink,
}));

vi.mock("os", () => ({
  default: { tmpdir: () => "/tmp" },
  tmpdir: () => "/tmp",
}));

vi.mock("crypto", () => ({
  default: { randomUUID: () => "test-uuid" },
  randomUUID: () => "test-uuid",
}));

import { POST } from "./route";

const VALID_SQUAD_RESPONSE = JSON.stringify({
  assistant_message: "Here is your squad proposal.",
  phase: "proposal",
  draft_graph_patch: {
    squad: { outcome: "Grow an expert personal brand" },
    agents: [{ key: "researcher", role: "Researcher" }],
    workflows: [{ key: "default", steps: [] }],
  },
  unresolved_questions: [],
  preview: { squad_name: "brand-squad" },
  readiness: 0.6,
  mode: "squad",
});

beforeEach(() => {
  vi.clearAllMocks();
  mockWriteFile.mockResolvedValue(undefined);
  mockUnlink.mockResolvedValue(undefined);
  mockExecFn.mockResolvedValue({ stdout: VALID_SQUAD_RESPONSE, stderr: "" });
});

describe("POST /api/authoring/squad-wizard", () => {
  it("returns structured squad authoring response with canonical phase", async () => {
    const req = new Request("http://localhost/api/authoring/squad-wizard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: [{ role: "user", content: "Create a brand squad" }],
        phase: "proposal",
      }),
    });

    const res = await POST(req as never);
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body).toHaveProperty("assistant_message");
    expect(body).toHaveProperty("phase");
    expect(["discovery", "proposal", "refinement", "approval"]).toContain(body.phase);
    expect(body).toHaveProperty("draft_graph_patch");
    expect(body).toHaveProperty("unresolved_questions");
    expect(body).toHaveProperty("readiness");
  });

  it("returns graph patch with squad/agents/workflows keys, not flat strings", async () => {
    const req = new Request("http://localhost/api/authoring/squad-wizard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: [{ role: "user", content: "Build a brand squad" }],
        phase: "proposal",
      }),
    });

    const res = await POST(req as never);
    const body = await res.json();

    expect(res.status).toBe(200);
    const patch = body.draft_graph_patch;
    expect(typeof patch).toBe("object");
    // Must NOT be flat strings (old contract)
    expect(typeof patch).not.toBe("string");
    expect(patch).not.toHaveProperty("team_design");
    expect(patch).not.toHaveProperty("workflow_design");
    // Must be structured graph patch
    expect(patch).toHaveProperty("squad");
    expect(patch).toHaveProperty("agents");
    expect(patch).toHaveProperty("workflows");
  });

  it("returns 400 when no user message is present", async () => {
    const req = new Request("http://localhost/api/authoring/squad-wizard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: [], phase: "discovery" }),
    });

    const res = await POST(req as never);
    expect(res.status).toBe(400);
  });

  it("returns 400 when phase is not canonical", async () => {
    const req = new Request("http://localhost/api/authoring/squad-wizard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: [{ role: "user", content: "hello" }],
        phase: "brainstorm",
      }),
    });

    const res = await POST(req as never);
    expect(res.status).toBe(400);
  });
});
