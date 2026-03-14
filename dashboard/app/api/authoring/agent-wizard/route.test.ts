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

const VALID_AGENT_RESPONSE = JSON.stringify({
  assistant_message: "Here is your researcher agent.",
  phase: "proposal",
  draft_graph_patch: {
    agents: [{ key: "researcher", role: "Researcher" }],
  },
  unresolved_questions: [],
  preview: {},
  readiness: 0.5,
  mode: "agent",
});

beforeEach(() => {
  vi.clearAllMocks();
  mockWriteFile.mockResolvedValue(undefined);
  mockUnlink.mockResolvedValue(undefined);
  mockExecFn.mockResolvedValue({ stdout: VALID_AGENT_RESPONSE, stderr: "" });
});

describe("POST /api/authoring/agent-wizard", () => {
  it("returns structured authoring response with canonical phase", async () => {
    const req = new Request("http://localhost/api/authoring/agent-wizard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: [{ role: "user", content: "Create a researcher agent" }],
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

  it("returns draft_graph_patch with agents array for agent mode", async () => {
    const req = new Request("http://localhost/api/authoring/agent-wizard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: [{ role: "user", content: "I want a coding agent" }],
        phase: "discovery",
      }),
    });

    const res = await POST(req as never);
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body).toHaveProperty("draft_graph_patch");
    // draft_graph_patch is an object (not a flat string)
    expect(typeof body.draft_graph_patch).toBe("object");
  });

  it("returns 400 when no user message is present", async () => {
    const req = new Request("http://localhost/api/authoring/agent-wizard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: [], phase: "discovery" }),
    });

    const res = await POST(req as never);
    expect(res.status).toBe(400);
  });

  it("returns 400 when phase is not canonical", async () => {
    const req = new Request("http://localhost/api/authoring/agent-wizard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: [{ role: "user", content: "hello" }],
        phase: "ideation",
      }),
    });

    const res = await POST(req as never);
    expect(res.status).toBe(400);
  });
});
