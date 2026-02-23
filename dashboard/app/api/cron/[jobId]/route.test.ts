import { describe, it, expect, vi, beforeEach } from "vitest";

const mockReadFile = vi.hoisted(() => vi.fn());
const mockWriteFile = vi.hoisted(() => vi.fn());
const mockRename = vi.hoisted(() => vi.fn());
const mockUnlink = vi.hoisted(() => vi.fn());

vi.mock("os", () => ({
  default: { homedir: () => "/home/test" },
  homedir: () => "/home/test",
}));
vi.mock("fs/promises", () => ({
  default: { readFile: mockReadFile, writeFile: mockWriteFile, rename: mockRename, unlink: mockUnlink },
  readFile: mockReadFile,
  writeFile: mockWriteFile,
  rename: mockRename,
  unlink: mockUnlink,
}));

import { DELETE } from "./route";
import { NextRequest } from "next/server";

const EXPECTED_PATH = "/home/test/.nanobot/cron/jobs.json";
const EXPECTED_TMP = `${EXPECTED_PATH}.tmp`;

const SAMPLE_JOB = {
  id: "abc123",
  name: "Test Job",
  enabled: true,
  schedule: { kind: "every", everyMs: 60000, atMs: null, expr: null, tz: null },
  payload: { kind: "agent_turn", message: "Hello", deliver: true, channel: null, to: null },
  state: { nextRunAtMs: null, lastRunAtMs: null, lastStatus: null, lastError: null },
  createdAtMs: 0,
  updatedAtMs: 0,
  deleteAfterRun: false,
};

function makeParams(jobId: string) {
  return { params: Promise.resolve({ jobId }) };
}

function makeReq() {
  return new NextRequest("http://localhost/api/cron/abc123", { method: "DELETE" });
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("DELETE /api/cron/[jobId]", () => {
  it("deletes job and returns success when jobId found", async () => {
    const fileData = { version: 1, jobs: [SAMPLE_JOB] };
    mockReadFile.mockResolvedValue(JSON.stringify(fileData));
    mockWriteFile.mockResolvedValue(undefined);
    mockRename.mockResolvedValue(undefined);

    const res = await DELETE(makeReq(), makeParams("abc123"));
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.success).toBe(true);

    expect(mockWriteFile).toHaveBeenCalledWith(
      EXPECTED_TMP,
      expect.stringContaining('"jobs": []'),
      "utf-8",
    );
    expect(mockRename).toHaveBeenCalledWith(EXPECTED_TMP, EXPECTED_PATH);
  });

  it("returns 404 when jobId not found in jobs array", async () => {
    mockReadFile.mockResolvedValue(JSON.stringify({ version: 1, jobs: [SAMPLE_JOB] }));

    const res = await DELETE(makeReq(), makeParams("nonexistent"));
    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.error).toBe("Job not found");
    expect(mockWriteFile).not.toHaveBeenCalled();
  });

  it("returns 404 when file does not exist (ENOENT)", async () => {
    const err = Object.assign(new Error("ENOENT"), { code: "ENOENT" });
    mockReadFile.mockRejectedValue(err);

    const res = await DELETE(makeReq(), makeParams("abc123"));
    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.error).toBe("Job not found");
  });

  it("returns 404 when file is empty", async () => {
    mockReadFile.mockResolvedValue("   ");

    const res = await DELETE(makeReq(), makeParams("abc123"));
    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.error).toBe("Job not found");
  });

  it("returns 500 on filesystem write error", async () => {
    mockReadFile.mockResolvedValue(JSON.stringify({ version: 1, jobs: [SAMPLE_JOB] }));
    const err = Object.assign(new Error("Permission denied"), { code: "EACCES" });
    mockWriteFile.mockRejectedValue(err);
    mockUnlink.mockResolvedValue(undefined);

    const res = await DELETE(makeReq(), makeParams("abc123"));
    expect(res.status).toBe(500);
    const body = await res.json();
    expect(body.error).toBe("Failed to delete cron job");
  });

  it("reads from correct file path", async () => {
    mockReadFile.mockResolvedValue(JSON.stringify({ version: 1, jobs: [SAMPLE_JOB] }));
    mockWriteFile.mockResolvedValue(undefined);
    mockRename.mockResolvedValue(undefined);

    await DELETE(makeReq(), makeParams("abc123"));
    expect(mockReadFile).toHaveBeenCalledWith(EXPECTED_PATH, "utf-8");
  });
});
