import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NextRequest } from "next/server";

const mockReadFile = vi.hoisted(() => vi.fn());
const mockWriteFile = vi.hoisted(() => vi.fn());
const mockMkdir = vi.hoisted(() => vi.fn());

vi.mock("os", () => ({
  default: { homedir: () => "/home/test" },
  homedir: () => "/home/test",
}));

vi.mock("fs/promises", () => ({
  default: {
    readFile: mockReadFile,
    writeFile: mockWriteFile,
    mkdir: mockMkdir,
  },
  readFile: mockReadFile,
  writeFile: mockWriteFile,
  mkdir: mockMkdir,
}));

import { PUT } from "./route";

const CONFIG_PATH = "/home/test/.nanobot/agents/youtube-summarizer/config.yaml";

beforeEach(() => {
  vi.resetAllMocks();
  mockMkdir.mockResolvedValue(undefined);
  mockWriteFile.mockResolvedValue(undefined);
});

describe("PUT /api/agents/[agentName]/config", () => {
  it("persists an explicit empty skills list instead of dropping the field", async () => {
    mockReadFile.mockResolvedValue(
      [
        "name: youtube-summarizer",
        "role: Summarizer",
        "prompt: test",
        "skills:",
        "  - legacy-skill",
      ].join("\n"),
    );

    const req = new Request("http://localhost/api/agents/youtube-summarizer/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        role: "Summarizer",
        prompt: "updated prompt",
        skills: [],
      }),
    });

<<<<<<< HEAD
    const res = await PUT(req as any, {
=======
    const res = await PUT(req as NextRequest, {
>>>>>>> worktree-agent-aacc91e7
      params: Promise.resolve({ agentName: "youtube-summarizer" }),
    });

    expect(res.status).toBe(204);
    expect(mockWriteFile).toHaveBeenCalledWith(
      CONFIG_PATH,
      expect.stringContaining("skills: []"),
      "utf-8",
    );
  });
});
