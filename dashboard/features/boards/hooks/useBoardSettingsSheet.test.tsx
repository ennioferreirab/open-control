import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";

const mockUpdateBoard = vi.fn();
const mockDeleteBoard = vi.fn();
const mockSetActiveBoardId = vi.fn();
const mockFetch = vi.fn();

global.fetch = mockFetch;

vi.mock("convex/react", () => ({
  useMutation: (ref: string) => {
    if (ref === "boards:update") return mockUpdateBoard;
    if (ref === "boards:softDelete") return mockDeleteBoard;
    return vi.fn();
  },
  useQuery: (ref: string, args?: unknown) => {
    if (args === "skip") return undefined;
    if (ref === "boards:getById") {
      return {
        _id: "board1",
        name: "default",
        displayName: "Default",
        description: "Main board",
        enabledAgents: [],
        agentMemoryModes: [],
        isDefault: true,
      };
    }
    if (ref === "agents:list") {
      return [];
    }
    if (ref === "boards:getDefault") {
      return { _id: "board1", name: "default", displayName: "Default" };
    }
    return undefined;
  },
}));

vi.mock("@/convex/_generated/api", () => ({
  api: {
    boards: {
      getById: "boards:getById",
      getDefault: "boards:getDefault",
      update: "boards:update",
      softDelete: "boards:softDelete",
    },
    agents: {
      list: "agents:list",
    },
  },
}));

vi.mock("@/components/BoardContext", () => ({
  useBoard: () => ({
    activeBoardId: "board1",
    setActiveBoardId: mockSetActiveBoardId,
  }),
}));

import { useBoardSettingsSheet } from "./useBoardSettingsSheet";

describe("useBoardSettingsSheet", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue([
        {
          name: "brief.md",
          path: "templates/brief.md",
          size: 128,
          type: "text/markdown",
        },
      ]),
    });
  });

  it("loads board artifacts for the active board", async () => {
    const { result } = renderHook(() => useBoardSettingsSheet(vi.fn()));

    await waitFor(() => {
      expect(result.current.artifacts).toEqual([
        expect.objectContaining({ name: "brief.md", path: "templates/brief.md" }),
      ]);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/boards/default/artifacts",
      expect.objectContaining({
        signal: expect.any(AbortSignal),
      }),
    );
  });

  it("uploads board artifacts and refreshes the list", async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue([]),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue({
          files: [
            {
              name: "playbook.md",
              path: "playbook.md",
              size: 77,
              type: "text/markdown",
            },
          ],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue([
          {
            name: "playbook.md",
            path: "playbook.md",
            size: 77,
            type: "text/markdown",
          },
        ]),
      });

    const { result } = renderHook(() => useBoardSettingsSheet(vi.fn()));
    await waitFor(() => expect(result.current.artifacts).toEqual([]));

    const file = new File(["# playbook"], "playbook.md", { type: "text/markdown" });

    await act(async () => {
      await result.current.uploadArtifacts([file]);
    });

    expect(mockFetch).toHaveBeenNthCalledWith(
      2,
      "/api/boards/default/artifacts",
      expect.objectContaining({
        body: expect.any(FormData),
        method: "POST",
      }),
    );

    await waitFor(() => {
      expect(result.current.artifacts).toEqual([expect.objectContaining({ path: "playbook.md" })]);
    });
  });

  it("opens and closes a selected artifact", async () => {
    const { result } = renderHook(() => useBoardSettingsSheet(vi.fn()));

    await waitFor(() => expect(result.current.artifacts).toHaveLength(1));

    act(() => {
      result.current.openArtifact(result.current.artifacts[0]!);
    });
    expect(result.current.selectedArtifact?.path).toBe("templates/brief.md");

    act(() => {
      result.current.closeArtifactViewer();
    });
    expect(result.current.selectedArtifact).toBeNull();
  });
});
