import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock convex/react before importing the hook
vi.mock("convex/react", () => ({
  useMutation: vi.fn(),
}));

// Mock the generated API so we can reference it without a real Convex deployment
vi.mock("@/convex/_generated/api", () => ({
  api: {
    squadSpecs: {
      publishGraph: "squadSpecs:publishGraph",
    },
  },
}));

import { useMutation } from "convex/react";
import { useCreateSquadDraft } from "./useCreateSquadDraft";

const mockUseMutation = vi.mocked(useMutation);

describe("useCreateSquadDraft", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("initializes with empty draft and not saving", () => {
    const mockMutate = vi.fn().mockResolvedValue("squad-spec-id-1");
    mockUseMutation.mockReturnValue(mockMutate);

    const { result } = renderHook(() => useCreateSquadDraft());

    expect(result.current.draft.name).toBe("");
    expect(result.current.isSaving).toBe(false);
  });

  it("updateDraft merges partial changes into draft state", () => {
    const mockMutate = vi.fn().mockResolvedValue("squad-spec-id-1");
    mockUseMutation.mockReturnValue(mockMutate);

    const { result } = renderHook(() => useCreateSquadDraft());

    act(() => {
      result.current.updateDraft({ name: "personal-brand-squad" });
    });

    expect(result.current.draft.name).toBe("personal-brand-squad");
  });

  it("publishDraft calls the publishGraph mutation — not a plain create", async () => {
    const mockMutate = vi.fn().mockResolvedValue("squad-spec-id-1");
    mockUseMutation.mockReturnValue(mockMutate);

    const { result } = renderHook(() => useCreateSquadDraft());

    act(() => {
      result.current.updateDraft({
        name: "personal-brand-squad",
        displayName: "Personal Brand Squad",
      });
    });

    await act(async () => {
      await result.current.publishDraft();
    });

    // useMutation must have been called with the publishGraph reference
    expect(mockUseMutation).toHaveBeenCalledWith("squadSpecs:publishGraph");
    // And the mutation itself must have been invoked
    expect(mockMutate).toHaveBeenCalledTimes(1);
  });

  it("publishDraft does not pass agentSpecIds: [] as a hardcoded empty array", async () => {
    const mockMutate = vi.fn().mockResolvedValue("squad-spec-id-1");
    mockUseMutation.mockReturnValue(mockMutate);

    const { result } = renderHook(() => useCreateSquadDraft());

    act(() => {
      result.current.updateDraft({
        name: "personal-brand-squad",
        displayName: "Personal Brand Squad",
      });
    });

    await act(async () => {
      await result.current.publishDraft();
    });

    // The mutation argument must NOT contain agentSpecIds: []
    const callArg = mockMutate.mock.calls[0]?.[0] as Record<string, unknown> | undefined;
    expect(callArg).toBeDefined();
    expect(callArg!.agentSpecIds).toBeUndefined();
  });

  it("publishDraft passes a graph object to the mutation", async () => {
    const mockMutate = vi.fn().mockResolvedValue("squad-spec-id-1");
    mockUseMutation.mockReturnValue(mockMutate);

    const { result } = renderHook(() => useCreateSquadDraft());

    act(() => {
      result.current.updateDraft({
        name: "personal-brand-squad",
        displayName: "Personal Brand Squad",
        description: "My brand squad",
      });
    });

    await act(async () => {
      await result.current.publishDraft();
    });

    const callArg = mockMutate.mock.calls[0]?.[0] as Record<string, unknown> | undefined;
    expect(callArg).toBeDefined();
    // The argument should have a graph key with squad info
    expect(callArg!.graph).toBeDefined();
    const graph = callArg!.graph as Record<string, unknown>;
    expect(graph.squad).toBeDefined();
  });

  it("publishDraft returns null when name is empty", async () => {
    const mockMutate = vi.fn().mockResolvedValue("squad-spec-id-1");
    mockUseMutation.mockReturnValue(mockMutate);

    const { result } = renderHook(() => useCreateSquadDraft());

    let returnVal: string | null = "not-null";
    await act(async () => {
      returnVal = await result.current.publishDraft();
    });

    expect(returnVal).toBeNull();
    expect(mockMutate).not.toHaveBeenCalled();
  });

  it("publishDraft returns the draft name on success", async () => {
    const mockMutate = vi.fn().mockResolvedValue("squad-spec-id-1");
    mockUseMutation.mockReturnValue(mockMutate);

    const { result } = renderHook(() => useCreateSquadDraft());

    act(() => {
      result.current.updateDraft({
        name: "my-squad",
        displayName: "My Squad",
      });
    });

    let returnVal: string | null = null;
    await act(async () => {
      returnVal = await result.current.publishDraft();
    });

    await waitFor(() => expect(result.current.isSaving).toBe(false));

    expect(returnVal).toBe("my-squad");
  });

  it("publishDraft returns null on mutation error", async () => {
    const mockMutate = vi.fn().mockRejectedValue(new Error("Mutation failed"));
    mockUseMutation.mockReturnValue(mockMutate);

    const { result } = renderHook(() => useCreateSquadDraft());

    act(() => {
      result.current.updateDraft({ name: "my-squad", displayName: "My Squad" });
    });

    let returnVal: string | null = "not-null";
    await act(async () => {
      returnVal = await result.current.publishDraft();
    });

    expect(returnVal).toBeNull();
  });

  it("sets isSaving to true during the mutation and false after", async () => {
    let resolveMutation!: (value: string) => void;
    const pendingPromise = new Promise<string>((resolve) => {
      resolveMutation = resolve;
    });
    const mockMutate = vi.fn().mockReturnValue(pendingPromise);
    mockUseMutation.mockReturnValue(mockMutate);

    const { result } = renderHook(() => useCreateSquadDraft());

    act(() => {
      result.current.updateDraft({ name: "my-squad", displayName: "My Squad" });
    });

    // Start publish without awaiting — isSaving should be true
    act(() => {
      void result.current.publishDraft();
    });

    await waitFor(() => expect(result.current.isSaving).toBe(true));

    // Resolve the mutation
    act(() => {
      resolveMutation("squad-spec-id-1");
    });

    await waitFor(() => expect(result.current.isSaving).toBe(false));
  });
});
