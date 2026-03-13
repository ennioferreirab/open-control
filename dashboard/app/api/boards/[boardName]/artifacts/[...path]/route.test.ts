import { beforeEach, describe, expect, it, vi } from "vitest";

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

function makeReq(boardName: string, path: string) {
  return new NextRequest(`http://localhost/api/boards/${boardName}/artifacts/${path}`);
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("GET /api/boards/[boardName]/artifacts/[...path]", () => {
  it("reads a board artifact file", async () => {
    mockReadFile.mockResolvedValue(Buffer.from("# Brief"));

    const res = await GET(makeReq("default", "templates/brief.md"), {
      params: Promise.resolve({ boardName: "default", path: ["templates", "brief.md"] }),
    });

    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toBe("text/markdown; charset=utf-8");
    expect(mockReadFile).toHaveBeenCalledWith(
      "/home/test/.nanobot/boards/default/artifacts/templates/brief.md",
    );
  });
});
