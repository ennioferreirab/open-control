import { describe, it, expect, vi, beforeEach } from "vitest";

const mockReadFile = vi.hoisted(() => vi.fn());

vi.mock("os", () => ({
  default: { homedir: () => "/home/test" },
  homedir: () => "/home/test",
}));
vi.mock("fs/promises", () => ({
  default: { readFile: mockReadFile },
  readFile: mockReadFile,
}));

import { GET } from "./route";

const EXPECTED_PATH = "/home/test/.nanobot/cron/jobs.json";

const SAMPLE_JOB = {
  id: "abc123",
  name: "Test Job",
  enabled: true,
  schedule: { kind: "every", everyMs: 60000, atMs: null, expr: null, tz: null },
  payload: { kind: "agent_turn", message: "Hello", deliver: true, channel: null, to: null },
  state: {
    nextRunAtMs: null,
    lastRunAtMs: null,
    lastStatus: null,
    lastError: null,
    lastTaskId: "task-1",
  },
  createdAtMs: 0,
  updatedAtMs: 0,
  deleteAfterRun: false,
};

beforeEach(() => {
  vi.resetAllMocks();
});

describe("GET /api/cron", () => {
  it("returns jobs list when file exists with valid JSON", async () => {
    mockReadFile.mockResolvedValue(JSON.stringify({ version: 1, jobs: [SAMPLE_JOB] }));
    const res = await GET();
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.jobs).toHaveLength(1);
    expect(body.jobs[0].name).toBe("Test Job");
    expect(mockReadFile).toHaveBeenCalledWith(EXPECTED_PATH, "utf-8");
  });

  it("returns empty jobs array when file does not exist (ENOENT)", async () => {
    const err = Object.assign(new Error("ENOENT"), { code: "ENOENT" });
    mockReadFile.mockRejectedValue(err);
    const res = await GET();
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.jobs).toEqual([]);
  });

  it("returns empty jobs array when file is empty", async () => {
    mockReadFile.mockResolvedValue("   ");
    const res = await GET();
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.jobs).toEqual([]);
  });

  it("returns empty jobs array when JSON has no jobs field", async () => {
    mockReadFile.mockResolvedValue(JSON.stringify({ version: 1 }));
    const res = await GET();
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.jobs).toEqual([]);
  });

  it("returns 500 on unexpected filesystem error", async () => {
    const err = Object.assign(new Error("Permission denied"), { code: "EACCES" });
    mockReadFile.mockRejectedValue(err);
    const res = await GET();
    expect(res.status).toBe(500);
    const body = await res.json();
    expect(body.error).toBeTruthy();
  });

  it("returns 500 on malformed JSON", async () => {
    mockReadFile.mockResolvedValue("{ invalid json }");
    const res = await GET();
    expect(res.status).toBe(500);
  });

  it("normalizes legacy flat-format jobs into nested schedule/payload/state", async () => {
    const legacyJob = {
      id: "legacy-1",
      cron_expr: "55 16 * * *",
      tz: "America/Sao_Paulo",
      message: "Boa tarde!",
      created_at: "2026-02-23T16:52:00-03:00",
      enabled: true,
    };
    mockReadFile.mockResolvedValue(JSON.stringify({ version: 1, jobs: [legacyJob] }));
    const res = await GET();
    expect(res.status).toBe(200);
    const body = await res.json();
    const job = body.jobs[0];
    expect(job.id).toBe("legacy-1");
    expect(job.schedule).toEqual({
      kind: "cron",
      expr: "55 16 * * *",
      tz: "America/Sao_Paulo",
      atMs: null,
      everyMs: null,
    });
    expect(job.payload.message).toBe("Boa tarde!");
    expect(job.state.lastStatus).toBeNull();
    expect(job.state.lastTaskId).toBeNull();
  });
});
