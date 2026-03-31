import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

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

function makeParams(sessionId: string) {
  return { params: Promise.resolve({ sessionId }) };
}

function makeReq(sessionId: string) {
  return new NextRequest(`http://localhost/api/live/sessions/${sessionId}/meta`);
}

describe("GET /api/live/sessions/[sessionId]/meta", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.unstubAllEnvs();
  });

  it("returns transcript metadata from OPEN_CONTROL_LIVE_HOME when present", async () => {
    vi.stubEnv("OPEN_CONTROL_LIVE_HOME", "/runtime/live");
    mockReadFile
      .mockResolvedValueOnce(
        JSON.stringify({
          sessionId: "session-1",
          taskId: "task-1",
          stepId: "step-1",
        }),
      )
      .mockResolvedValueOnce(
        JSON.stringify({
          sessionId: "session-1",
          taskId: "task-1",
          stepId: "step-1",
          status: "attached",
          eventCount: 2,
        }),
      );

    const response = await GET(makeReq("session-1"), makeParams("session-1"));

    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({
      sessionId: "session-1",
      taskId: "task-1",
      stepId: "step-1",
      status: "attached",
      eventCount: 2,
    });
    expect(mockReadFile).toHaveBeenNthCalledWith(
      1,
      "/runtime/live/session-index/session-1.json",
      "utf-8",
    );
    expect(mockReadFile).toHaveBeenNthCalledWith(
      2,
      "/runtime/live/sessions/task-1/step-1/session-1/meta.json",
      "utf-8",
    );
  });

  it("accepts punctuated session ids and resolves the sanitized file path", async () => {
    vi.stubEnv("OPEN_CONTROL_LIVE_HOME", "/runtime/live");
    mockReadFile
      .mockResolvedValueOnce(
        JSON.stringify({
          sessionId: "interactive_session:claude",
          taskId: "task-1",
          stepId: "step-1",
        }),
      )
      .mockResolvedValueOnce(
        JSON.stringify({
          sessionId: "interactive_session:claude",
          taskId: "task-1",
          stepId: "step-1",
          status: "attached",
          eventCount: 1,
        }),
      );

    const response = await GET(
      makeReq("interactive_session:claude"),
      makeParams("interactive_session:claude"),
    );

    expect(response.status).toBe(200);
    expect(mockReadFile).toHaveBeenNthCalledWith(
      1,
      "/runtime/live/session-index/interactive_session_claude.json",
      "utf-8",
    );
    expect(mockReadFile).toHaveBeenNthCalledWith(
      2,
      "/runtime/live/sessions/task-1/step-1/interactive_session_claude/meta.json",
      "utf-8",
    );
  });

  it("returns 404 when the transcript metadata file is missing", async () => {
    mockReadFile.mockRejectedValue(Object.assign(new Error("missing"), { code: "ENOENT" }));

    const response = await GET(makeReq("session-1"), makeParams("session-1"));

    expect(response.status).toBe(404);
    expect(await response.json()).toEqual({ error: "Transcript not found" });
  });

  it("returns 400 when the sessionId is invalid", async () => {
    const response = await GET(makeReq("../bad"), makeParams("../bad"));

    expect(response.status).toBe(400);
    expect(await response.json()).toEqual({ error: "Invalid sessionId" });
  });
});
