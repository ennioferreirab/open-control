import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("convex/react", () => ({
  useMutation: vi.fn(),
}));

vi.mock("@/convex/_generated/api", () => ({
  api: {
    squadSpecs: {
      updatePublishedGraph: "squadSpecs:updatePublishedGraph",
    },
  },
}));

import { useMutation } from "convex/react";
import { useUpdatePublishedSquad } from "./useUpdatePublishedSquad";
import type { Id } from "@/convex/_generated/dataModel";

const mockUseMutation = vi.mocked(useMutation);

describe("useUpdatePublishedSquad", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("binds the published squad update mutation", () => {
    const mockPublish = vi.fn().mockResolvedValue("squad-1");
    mockUseMutation.mockReturnValue(mockPublish);

    renderHook(() => useUpdatePublishedSquad());

    expect(mockUseMutation).toHaveBeenCalledWith("squadSpecs:updatePublishedGraph");
  });

  it("publishes the provided graph payload", async () => {
    const mockPublish = vi.fn().mockResolvedValue("squad-1");
    mockUseMutation.mockReturnValue(mockPublish);
    const { result } = renderHook(() => useUpdatePublishedSquad());

    await act(async () => {
      await result.current.publish({
        squadSpecId: "squad-1" as Id<"squadSpecs">,
        graph: {
          squad: {
            name: "review-squad",
            displayName: "Review Squad",
          },
          agents: [],
          workflows: [],
        },
      });
    });

    expect(mockPublish).toHaveBeenCalledWith({
      squadSpecId: "squad-1",
      graph: {
        squad: {
          name: "review-squad",
          displayName: "Review Squad",
        },
        agents: [],
        workflows: [],
      },
    });
  });

  it("tracks isPublishing around the mutation", async () => {
    let resolvePublish!: (value: Id<"squadSpecs">) => void;
    const pendingPublish = new Promise<Id<"squadSpecs">>((resolve) => {
      resolvePublish = resolve;
    });
    const mockPublish = vi.fn().mockReturnValue(pendingPublish);
    mockUseMutation.mockReturnValue(mockPublish);
    const { result } = renderHook(() => useUpdatePublishedSquad());

    act(() => {
      void result.current.publish({
        squadSpecId: "squad-1" as Id<"squadSpecs">,
        graph: {
          squad: {
            name: "review-squad",
            displayName: "Review Squad",
          },
          agents: [],
          workflows: [],
        },
      });
    });

    await waitFor(() => expect(result.current.isPublishing).toBe(true));

    act(() => {
      resolvePublish("squad-1" as Id<"squadSpecs">);
    });

    await waitFor(() => expect(result.current.isPublishing).toBe(false));
  });
});
