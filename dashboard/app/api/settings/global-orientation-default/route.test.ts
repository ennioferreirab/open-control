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

const EXPECTED_PATH = "/home/test/.nanobot/mc/agent-orientation.md";

beforeEach(() => {
  vi.resetAllMocks();
});

describe("GET /api/settings/global-orientation-default", () => {
  it("returns trimmed orientation text from the local file", async () => {
    mockReadFile.mockResolvedValue("  Global instructions  \n");

    const response = await GET();

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ prompt: "Global instructions" });
    expect(mockReadFile).toHaveBeenCalledWith(EXPECTED_PATH, "utf-8");
  });

  it("returns an empty prompt when the file does not exist", async () => {
    const err = Object.assign(new Error("ENOENT"), { code: "ENOENT" });
    mockReadFile.mockRejectedValue(err);

    const response = await GET();

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ prompt: "" });
  });

  it("returns 500 on unexpected filesystem errors", async () => {
    const err = Object.assign(new Error("EACCES"), { code: "EACCES" });
    mockReadFile.mockRejectedValue(err);

    const response = await GET();

    expect(response.status).toBe(500);
  });

  it("reads from OPEN_CONTROL_HOME when configured", async () => {
    vi.stubEnv("OPEN_CONTROL_HOME", "/runtime/open-control");
    mockReadFile.mockResolvedValue("Open Control instructions");

    const response = await GET();

    expect(response.status).toBe(200);
    expect(mockReadFile).toHaveBeenCalledWith(
      "/runtime/open-control/mc/agent-orientation.md",
      "utf-8",
    );
    vi.unstubAllEnvs();
  });
});
