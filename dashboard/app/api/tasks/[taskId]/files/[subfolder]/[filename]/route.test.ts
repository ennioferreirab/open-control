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
import { NextRequest } from "next/server";

function makeParams(taskId: string, subfolder: string, filename: string) {
  return { params: Promise.resolve({ taskId, subfolder, filename }) };
}

function makeReq(taskId: string, subfolder: string, filename: string) {
  return new NextRequest(
    `http://localhost/api/tasks/${taskId}/files/${subfolder}/${filename}`,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("GET /api/tasks/[taskId]/files/[subfolder]/[filename]", () => {
  // ── Happy path: MIME types ──────────────────────────────────────────────────

  it("returns 200 with Content-Type application/pdf for .pdf", async () => {
    const buf = Buffer.from("PDF bytes");
    mockReadFile.mockResolvedValue(buf);
    const res = await GET(makeReq("task-1", "output", "report.pdf"), makeParams("task-1", "output", "report.pdf"));
    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toBe("application/pdf");
  });

  it("returns 200 with Content-Type text/markdown for .md", async () => {
    const buf = Buffer.from("# Hello");
    mockReadFile.mockResolvedValue(buf);
    const res = await GET(makeReq("task-1", "output", "README.md"), makeParams("task-1", "output", "README.md"));
    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toBe("text/markdown; charset=utf-8");
  });

  it("returns 200 with Content-Type text/x-python for .py", async () => {
    const buf = Buffer.from("print('hello')");
    mockReadFile.mockResolvedValue(buf);
    const res = await GET(makeReq("task-1", "output", "script.py"), makeParams("task-1", "output", "script.py"));
    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toBe("text/x-python; charset=utf-8");
  });

  it("returns 200 with Content-Type application/json for .json", async () => {
    const buf = Buffer.from('{"key":"val"}');
    mockReadFile.mockResolvedValue(buf);
    const res = await GET(makeReq("task-1", "output", "data.json"), makeParams("task-1", "output", "data.json"));
    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toBe("application/json; charset=utf-8");
  });

  it("returns 200 with Content-Type image/png for .png", async () => {
    const buf = Buffer.from([0x89, 0x50, 0x4e, 0x47]);
    mockReadFile.mockResolvedValue(buf);
    const res = await GET(makeReq("task-1", "attachments", "photo.png"), makeParams("task-1", "attachments", "photo.png"));
    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toBe("image/png");
  });

  // ── Response headers ────────────────────────────────────────────────────────

  it("includes Content-Disposition with encoded filename", async () => {
    const buf = Buffer.from("data");
    mockReadFile.mockResolvedValue(buf);
    const res = await GET(makeReq("task-1", "output", "my file.pdf"), makeParams("task-1", "output", "my file.pdf"));
    // Note: filename validation rejects "/" and "\", but spaces are OK
    const cd = res.headers.get("Content-Disposition");
    expect(cd).toBeTruthy();
    expect(cd).toContain("my%20file.pdf");
    expect(cd).toMatch(/^inline; filename="/);
  });

  it("sets Content-Length to buffer byte count", async () => {
    const buf = Buffer.from("hello world");
    mockReadFile.mockResolvedValue(buf);
    const res = await GET(makeReq("task-1", "output", "note.txt"), makeParams("task-1", "output", "note.txt"));
    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Length")).toBe(String(buf.length));
  });

  it("sets Cache-Control to private, max-age=60", async () => {
    const buf = Buffer.from("data");
    mockReadFile.mockResolvedValue(buf);
    const res = await GET(makeReq("task-1", "output", "file.txt"), makeParams("task-1", "output", "file.txt"));
    expect(res.status).toBe(200);
    expect(res.headers.get("Cache-Control")).toBe("private, max-age=60");
  });

  // ── Error handling ──────────────────────────────────────────────────────────

  it("returns 404 with { error: 'File not found' } when file does not exist (ENOENT)", async () => {
    const err = Object.assign(new Error("ENOENT: no such file"), { code: "ENOENT" });
    mockReadFile.mockRejectedValue(err);
    const res = await GET(makeReq("task-1", "output", "missing.txt"), makeParams("task-1", "output", "missing.txt"));
    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.error).toBe("File not found");
  });

  it("returns 500 on non-ENOENT filesystem error", async () => {
    const err = Object.assign(new Error("Permission denied"), { code: "EACCES" });
    mockReadFile.mockRejectedValue(err);
    const res = await GET(makeReq("task-1", "output", "protected.txt"), makeParams("task-1", "output", "protected.txt"));
    expect(res.status).toBe(500);
    const body = await res.json();
    expect(body.error).toBe("Failed to read file");
  });

  // ── taskId validation ───────────────────────────────────────────────────────

  it("returns 400 for taskId containing '/'", async () => {
    const res = await GET(makeReq("task/evil", "output", "file.txt"), makeParams("task/evil", "output", "file.txt"));
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe("Invalid taskId");
  });

  it("returns 400 for taskId containing '..'", async () => {
    const res = await GET(makeReq("task..evil", "output", "file.txt"), makeParams("task..evil", "output", "file.txt"));
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe("Invalid taskId");
  });

  it("returns 400 for taskId containing spaces", async () => {
    const res = await GET(makeReq("task id", "output", "file.txt"), makeParams("task id", "output", "file.txt"));
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe("Invalid taskId");
  });

  it("accepts valid taskId with alphanumeric, hyphens, underscores", async () => {
    const buf = Buffer.from("ok");
    mockReadFile.mockResolvedValue(buf);
    const res = await GET(makeReq("task_1-abc", "output", "file.txt"), makeParams("task_1-abc", "output", "file.txt"));
    expect(res.status).toBe(200);
  });

  // ── subfolder validation ────────────────────────────────────────────────────

  it("returns 400 for subfolder 'secrets'", async () => {
    const res = await GET(makeReq("task-1", "secrets", "file.txt"), makeParams("task-1", "secrets", "file.txt"));
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe("Invalid subfolder");
  });

  it("returns 400 for subfolder '..'", async () => {
    const res = await GET(makeReq("task-1", "..", "file.txt"), makeParams("task-1", "..", "file.txt"));
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe("Invalid subfolder");
  });

  it("accepts subfolder 'attachments'", async () => {
    const buf = Buffer.from("ok");
    mockReadFile.mockResolvedValue(buf);
    const res = await GET(makeReq("task-1", "attachments", "img.png"), makeParams("task-1", "attachments", "img.png"));
    expect(res.status).toBe(200);
  });

  it("accepts subfolder 'output'", async () => {
    const buf = Buffer.from("ok");
    mockReadFile.mockResolvedValue(buf);
    const res = await GET(makeReq("task-1", "output", "result.json"), makeParams("task-1", "output", "result.json"));
    expect(res.status).toBe(200);
  });

  // ── filename validation ─────────────────────────────────────────────────────

  it("returns 400 for filename containing '..'", async () => {
    const res = await GET(makeReq("task-1", "output", ".."), makeParams("task-1", "output", ".."));
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe("Invalid filename");
  });

  it("returns 400 for filename containing '/'", async () => {
    const res = await GET(makeReq("task-1", "output", "sub/file.txt"), makeParams("task-1", "output", "sub/file.txt"));
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe("Invalid filename");
  });

  it("returns 400 for filename containing '\\'", async () => {
    const res = await GET(makeReq("task-1", "output", "sub\\file.txt"), makeParams("task-1", "output", "sub\\file.txt"));
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe("Invalid filename");
  });

  it("returns 400 for filename containing '../' path traversal", async () => {
    const res = await GET(makeReq("task-1", "output", "../etc/passwd"), makeParams("task-1", "output", "../etc/passwd"));
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe("Invalid filename");
  });

  it("accepts filename with consecutive dots that is not path traversal", async () => {
    const buf = Buffer.from("ok");
    mockReadFile.mockResolvedValue(buf);
    const res = await GET(makeReq("task-1", "output", "file..txt"), makeParams("task-1", "output", "file..txt"));
    expect(res.status).toBe(200);
  });

  it("does not access filesystem when taskId validation fails", async () => {
    await GET(makeReq("bad/id", "output", "file.txt"), makeParams("bad/id", "output", "file.txt"));
    expect(mockReadFile).not.toHaveBeenCalled();
  });

  it("does not access filesystem when subfolder validation fails", async () => {
    await GET(makeReq("task-1", "evil", "file.txt"), makeParams("task-1", "evil", "file.txt"));
    expect(mockReadFile).not.toHaveBeenCalled();
  });

  it("does not access filesystem when filename validation fails", async () => {
    await GET(makeReq("task-1", "output", ".."), makeParams("task-1", "output", ".."));
    expect(mockReadFile).not.toHaveBeenCalled();
  });

  // ── MIME detection ──────────────────────────────────────────────────────────

  it("returns application/octet-stream for unknown extension", async () => {
    const buf = Buffer.from("binary data");
    mockReadFile.mockResolvedValue(buf);
    const res = await GET(makeReq("task-1", "output", "archive.xyz"), makeParams("task-1", "output", "archive.xyz"));
    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toBe("application/octet-stream");
  });

  it("returns application/octet-stream for file with no extension", async () => {
    const buf = Buffer.from("binary data");
    mockReadFile.mockResolvedValue(buf);
    const res = await GET(makeReq("task-1", "output", "Makefile"), makeParams("task-1", "output", "Makefile"));
    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toBe("application/octet-stream");
  });

  it("is case-insensitive for MIME extension matching (.PDF → application/pdf)", async () => {
    const buf = Buffer.from("PDF bytes");
    mockReadFile.mockResolvedValue(buf);
    const res = await GET(makeReq("task-1", "output", "REPORT.PDF"), makeParams("task-1", "output", "REPORT.PDF"));
    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toBe("application/pdf");
  });

  // ── Correct file path assembly ──────────────────────────────────────────────

  it("assembles correct file path from homedir + .nanobot/tasks/{taskId}/{subfolder}/{filename}", async () => {
    const buf = Buffer.from("data");
    mockReadFile.mockResolvedValue(buf);
    await GET(makeReq("my-task", "attachments", "doc.pdf"), makeParams("my-task", "attachments", "doc.pdf"));
    expect(mockReadFile).toHaveBeenCalledWith("/home/test/.nanobot/tasks/my-task/attachments/doc.pdf");
  });

  // ── Additional MIME coverage ────────────────────────────────────────────────

  it("returns correct Content-Type for .ts", async () => {
    const buf = Buffer.from("const x = 1;");
    mockReadFile.mockResolvedValue(buf);
    const res = await GET(makeReq("t", "output", "index.ts"), makeParams("t", "output", "index.ts"));
    expect(res.headers.get("Content-Type")).toBe("text/typescript; charset=utf-8");
  });

  it("returns correct Content-Type for .csv", async () => {
    const buf = Buffer.from("a,b,c");
    mockReadFile.mockResolvedValue(buf);
    const res = await GET(makeReq("t", "output", "data.csv"), makeParams("t", "output", "data.csv"));
    expect(res.headers.get("Content-Type")).toBe("text/csv; charset=utf-8");
  });

  it("returns correct Content-Type for .yaml", async () => {
    const buf = Buffer.from("key: val");
    mockReadFile.mockResolvedValue(buf);
    const res = await GET(makeReq("t", "output", "config.yaml"), makeParams("t", "output", "config.yaml"));
    expect(res.headers.get("Content-Type")).toBe("text/yaml; charset=utf-8");
  });

  it("returns correct Content-Type for .svg", async () => {
    const buf = Buffer.from("<svg/>");
    mockReadFile.mockResolvedValue(buf);
    const res = await GET(makeReq("t", "output", "icon.svg"), makeParams("t", "output", "icon.svg"));
    expect(res.headers.get("Content-Type")).toBe("image/svg+xml");
  });

  it("returns correct Content-Type for .sh", async () => {
    const buf = Buffer.from("#!/bin/sh");
    mockReadFile.mockResolvedValue(buf);
    const res = await GET(makeReq("t", "output", "run.sh"), makeParams("t", "output", "run.sh"));
    expect(res.headers.get("Content-Type")).toBe("text/x-sh; charset=utf-8");
  });

  it("returns correct Content-Type for .log", async () => {
    const buf = Buffer.from("2026-01-01 INFO start");
    mockReadFile.mockResolvedValue(buf);
    const res = await GET(makeReq("t", "output", "app.log"), makeParams("t", "output", "app.log"));
    expect(res.headers.get("Content-Type")).toBe("text/plain; charset=utf-8");
  });
});
