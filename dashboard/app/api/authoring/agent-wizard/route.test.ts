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
  return new NextRequest("http://localhost/api/authoring/agent-wizard", {
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

describe("POST /api/authoring/agent-wizard", () => {
  it("returns structured authoring response, not raw YAML", async () => {
    const structuredResponse = {
      question: "What is the primary purpose of this agent?",
      draft_patch: { fields: { purpose: "Finance tracking" } },
      phase: "purpose",
      readiness: 0.0,
      summary_sections: {},
      recommended_next_phase: "operating_context",
    };
    mockExecPromise.mockResolvedValue({
      stdout: JSON.stringify(structuredResponse),
      stderr: "",
    });

    const req = makeRequest({
      messages: [{ role: "user", content: "I want a finance agent" }],
      current_spec: {},
      phase: "purpose",
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
      phase: "purpose",
    });

    const res = await POST(req);
    expect(res.status).toBe(400);
  });

  it("forwards current_spec and phase to Python backend", async () => {
    const structuredResponse = {
      question: "Describe the operating context",
      draft_patch: { fields: {} },
      phase: "operating_context",
      readiness: 0.2,
      summary_sections: { purpose: "Finance" },
      recommended_next_phase: "working_style",
    };
    mockExecPromise.mockResolvedValue({
      stdout: JSON.stringify(structuredResponse),
      stderr: "",
    });

    const req = makeRequest({
      messages: [{ role: "user", content: "Finance agent for banking" }],
      current_spec: { purpose: "Finance tracking" },
      phase: "operating_context",
    });

    const res = await POST(req);
    expect(res.status).toBe(200);

    // Verify the Python script was invoked with the input data
    expect(mockWriteFile).toHaveBeenCalled();
    const inputWriteCall = mockWriteFile.mock.calls.find(
      (call: string[]) => call[0] && String(call[0]).includes("input"),
    );
    if (inputWriteCall) {
      const inputData = JSON.parse(inputWriteCall[1] as string);
      expect(inputData.current_spec).toEqual({ purpose: "Finance tracking" });
      expect(inputData.phase).toBe("operating_context");
    }
  });

  it("returns fallback structured response when Python exec fails", async () => {
    mockExecPromise.mockRejectedValue(new Error("Python failed"));

    const req = makeRequest({
      messages: [{ role: "user", content: "I want an agent" }],
      current_spec: {},
      phase: "purpose",
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
