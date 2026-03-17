import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { mockReactMutation } from "@/tests/helpers/mockConvex";

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
    const mockPublish = mockReactMutation(async () => "squad-1");
    mockUseMutation.mockReturnValue(mockPublish);

    renderHook(() => useUpdatePublishedSquad());

    expect(mockUseMutation).toHaveBeenCalledWith("squadSpecs:updatePublishedGraph");
  });

  it("publishes the provided graph payload", async () => {
    const mockPublish = mockReactMutation(async () => "squad-1");
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
          reviewPolicy: "Lead review required",
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
        reviewPolicy: "Lead review required",
      },
    });
  });

  it("tracks isPublishing around the mutation", async () => {
    let resolvePublish!: (value: Id<"squadSpecs">) => void;
    const pendingPublish = new Promise<Id<"squadSpecs">>((resolve) => {
      resolvePublish = resolve;
    });
    const mockPublish = mockReactMutation(() => pendingPublish);
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
