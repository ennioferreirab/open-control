import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock child_process exec to avoid actually running Python
const mockExecPromise = vi.hoisted(() => vi.fn());
const mockWriteFile = vi.hoisted(() => vi.fn());
const mockUnlink = vi.hoisted(() => vi.fn());

vi.mock("child_process", () => ({
  default: { exec: vi.fn() },
  exec: vi.fn(),
}));

vi.mock("util", () => ({
  default: { promisify: () => mockExecPromise },
  promisify: () => mockExecPromise,
}));

vi.mock("fs/promises", () => ({
  default: { writeFile: mockWriteFile, unlink: mockUnlink },
  writeFile: mockWriteFile,
  unlink: mockUnlink,
}));

vi.mock("crypto", () => ({
  default: { randomUUID: () => "test-uuid-1234" },
  randomUUID: () => "test-uuid-1234",
}));

import { POST } from "./route";

function makeRequest(body: unknown): NextRequest {
  return new NextRequest("http://localhost/api/authoring/squad-wizard", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
}

beforeEach(() => {
  vi.resetAllMocks();
  mockWriteFile.mockResolvedValue(undefined);
  mockUnlink.mockResolvedValue(undefined);
});

describe("POST /api/authoring/squad-wizard", () => {
  it("returns structured squad authoring response", async () => {
    const structuredResponse = {
      question: "How many agents should be in your squad?",
      draft_patch: { fields: { team_design: "3 specialized agents" } },
      phase: "team_design",
      readiness: 0.0,
      summary_sections: {},
      recommended_next_phase: "workflow_design",
    };
    mockExecPromise.mockResolvedValue({
      stdout: JSON.stringify(structuredResponse),
      stderr: "",
    });

    const req = makeRequest({
      messages: [{ role: "user", content: "I need a research squad" }],
      current_spec: {},
      phase: "team_design",
    });

    const res = await POST(req);
    expect(res.status).toBe(200);

    const body = await res.json();
    // Must return structured fields
    expect(body).toHaveProperty("question");
    expect(body).toHaveProperty("draft_patch");
    expect(body).toHaveProperty("phase");
    expect(body).toHaveProperty("readiness");
    expect(body).toHaveProperty("summary_sections");
    expect(body).toHaveProperty("recommended_next_phase");
    // Must NOT have a raw yaml field
    expect(body).not.toHaveProperty("yaml");
  });

  it("returns 400 when no user message is present", async () => {
    const req = makeRequest({
      messages: [],
      current_spec: {},
      phase: "team_design",
    });

    const res = await POST(req);
    expect(res.status).toBe(400);
  });

  it("can refine agents, workflows, and review policy together", async () => {
    const refinedResponse = {
      question: "How should the review process work for the squad's outputs?",
      draft_patch: {
        fields: {
          workflow_design: "Sequential with 3 steps: research, draft, review",
        },
      },
      phase: "review_design",
      readiness: 0.5,
      summary_sections: {
        team_design: "Lead, researcher, writer",
        workflow_design: "Sequential pipeline",
      },
      recommended_next_phase: "approval",
    };
    mockExecPromise.mockResolvedValue({
      stdout: JSON.stringify(refinedResponse),
      stderr: "",
    });

    const req = makeRequest({
      messages: [
        { role: "user", content: "I need a research squad" },
        { role: "assistant", content: "How many agents?" },
        { role: "user", content: "3 agents: lead, researcher, writer" },
        { role: "assistant", content: "What workflow?" },
        { role: "user", content: "Sequential pipeline with review" },
      ],
      current_spec: {
        team_design: "Lead, researcher, writer",
        workflow_design: "Sequential pipeline",
      },
      phase: "review_design",
    });

    const res = await POST(req);
    expect(res.status).toBe(200);

    const body = await res.json();
    expect(body.phase).toBe("review_design");
    expect(body.summary_sections).toHaveProperty("team_design");
    expect(body.summary_sections).toHaveProperty("workflow_design");
  });

  it("returns fallback structured response when Python exec fails", async () => {
    mockExecPromise.mockRejectedValue(new Error("Python failed"));

    const req = makeRequest({
      messages: [{ role: "user", content: "I need a squad" }],
      current_spec: {},
      phase: "team_design",
    });

    const res = await POST(req);
    expect(res.status).toBe(200);

    const body = await res.json();
    // Even on failure, must return structured response, not raw YAML
    expect(body).toHaveProperty("question");
    expect(body).not.toHaveProperty("yaml");
  });

  it("returns 500 on malformed request body", async () => {
    const req = makeRequest("not-valid-json");

    const res = await POST(req);
    expect(res.status).toBe(500);
  });
});
