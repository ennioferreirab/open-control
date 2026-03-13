import { beforeEach, describe, expect, it, vi } from "vitest";

const mockReaddir = vi.hoisted(() => vi.fn());
const mockStat = vi.hoisted(() => vi.fn());
const mockMkdir = vi.hoisted(() => vi.fn());
const mockRename = vi.hoisted(() => vi.fn());
const mockRm = vi.hoisted(() => vi.fn());
const mockWriteFile = vi.hoisted(() => vi.fn());

vi.mock("os", () => ({
  default: { homedir: () => "/home/test" },
  homedir: () => "/home/test",
}));
vi.mock("fs/promises", () => ({
  default: {
    mkdir: mockMkdir,
    readdir: mockReaddir,
    rename: mockRename,
    rm: mockRm,
    stat: mockStat,
    writeFile: mockWriteFile,
  },
  mkdir: mockMkdir,
  readdir: mockReaddir,
  rename: mockRename,
  rm: mockRm,
  stat: mockStat,
  writeFile: mockWriteFile,
}));

import { GET, POST } from "./route";
import { NextRequest } from "next/server";

function makeReq(boardName: string) {
  return new NextRequest(`http://localhost/api/boards/${boardName}/artifacts`);
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("GET /api/boards/[boardName]/artifacts", () => {
  it("lists board-scoped artifact files recursively", async () => {
    mockReaddir
      .mockResolvedValueOnce([
        { name: "templates", isDirectory: () => true, isFile: () => false },
        { name: "guide.md", isDirectory: () => false, isFile: () => true },
      ])
      .mockResolvedValueOnce([{ name: "brief.md", isDirectory: () => false, isFile: () => true }]);
    mockStat.mockResolvedValueOnce({ size: 42 }).mockResolvedValueOnce({ size: 128 });

    const res = await GET(makeReq("default"), {
      params: Promise.resolve({ boardName: "default" }),
    });

    expect(res.status).toBe(200);
    await expect(res.json()).resolves.toEqual([
      expect.objectContaining({ name: "guide.md", path: "guide.md", size: 128 }),
      expect.objectContaining({ name: "brief.md", path: "templates/brief.md", size: 42 }),
    ]);
  });
});

describe("POST /api/boards/[boardName]/artifacts", () => {
  it("uploads files into the board artifacts directory", async () => {
    const formData = new FormData();
    formData.append("files", new File(["hello"], "brief.md", { type: "text/markdown" }));

    const req = new NextRequest("http://localhost/api/boards/default/artifacts", {
      method: "POST",
    });
    vi.spyOn(req, "formData").mockResolvedValue(formData);

    const res = await POST(req, {
      params: Promise.resolve({ boardName: "default" }),
    });

    expect(res.status).toBe(200);
    await expect(res.json()).resolves.toEqual({
      files: [
        expect.objectContaining({
          name: "brief.md",
          path: "brief.md",
          size: 5,
          type: "text/markdown",
        }),
      ],
    });
    expect(mockMkdir).toHaveBeenCalledWith("/home/test/.nanobot/boards/default/artifacts", {
      recursive: true,
    });
    expect(mockWriteFile).toHaveBeenCalledWith(
      "/home/test/.nanobot/boards/default/artifacts/brief.md.tmp",
      expect.any(Buffer),
    );
    expect(mockRename).toHaveBeenCalledWith(
      "/home/test/.nanobot/boards/default/artifacts/brief.md.tmp",
      "/home/test/.nanobot/boards/default/artifacts/brief.md",
    );
  });
});
