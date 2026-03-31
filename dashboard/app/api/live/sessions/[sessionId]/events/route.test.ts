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

function makeReq(sessionId: string, afterSeq?: number) {
  const url = new URL(`http://localhost/api/live/sessions/${sessionId}/events`);
  if (afterSeq !== undefined) {
    url.searchParams.set("afterSeq", String(afterSeq));
  }
  return new NextRequest(url);
}

describe("GET /api/live/sessions/[sessionId]/events", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.unstubAllEnvs();
  });

  it("returns events newer than afterSeq", async () => {
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
        [
          JSON.stringify({ seq: 1, kind: "session_ready", ts: "2026-03-30T09:59:00.000Z" }),
          JSON.stringify({ seq: 2, kind: "turn_started", ts: "2026-03-30T10:00:00.000Z" }),
          JSON.stringify({ seq: 3, kind: "turn_completed", ts: "2026-03-30T10:01:00.000Z" }),
        ].join("\n"),
      );

    const response = await GET(makeReq("session-1", 2), makeParams("session-1"));

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      events: [{ seq: 3, kind: "turn_completed", ts: "2026-03-30T10:01:00.000Z" }],
    });
    expect(mockReadFile).toHaveBeenNthCalledWith(
      1,
      "/runtime/live/session-index/session-1.json",
      "utf-8",
    );
    expect(mockReadFile).toHaveBeenNthCalledWith(
      2,
      "/runtime/live/sessions/task-1/step-1/session-1/events.jsonl",
      "utf-8",
    );
  });

  it("accepts punctuated session ids and resolves the sanitized event path", async () => {
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
        [JSON.stringify({ seq: 1, kind: "session_ready", ts: "2026-03-30T09:59:00.000Z" })].join(
          "\n",
        ),
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
      "/runtime/live/sessions/task-1/step-1/interactive_session_claude/events.jsonl",
      "utf-8",
    );
  });

  it("returns 404 when the transcript events file is missing", async () => {
    mockReadFile.mockRejectedValue(Object.assign(new Error("missing"), { code: "ENOENT" }));

    const response = await GET(makeReq("session-1"), makeParams("session-1"));

    expect(response.status).toBe(404);
    expect(await response.json()).toEqual({ error: "Transcript not found" });
  });

  it("returns 400 for invalid afterSeq", async () => {
    const url = new URL("http://localhost/api/live/sessions/session-1/events");
    url.searchParams.set("afterSeq", "-2");

    const response = await GET(new NextRequest(url), makeParams("session-1"));

    expect(response.status).toBe(400);
    expect(await response.json()).toEqual({ error: "Invalid afterSeq" });
  });
});
