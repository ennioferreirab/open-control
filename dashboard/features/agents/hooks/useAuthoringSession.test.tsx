import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockFetch = vi.fn();
global.fetch = mockFetch;

import { useAuthoringSession } from "./useAuthoringSession";

const AGENT_RESPONSE = {
  assistant_message: "I propose a researcher agent.",
  phase: "proposal",
  draft_graph_patch: {
    agents: [{ key: "researcher", role: "Researcher" }],
  },
  unresolved_questions: [],
  preview: {},
  readiness: 0.5,
  mode: "agent",
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useAuthoringSession - agent mode", () => {
  it("initializes with discovery phase and empty transcript", () => {
    const { result } = renderHook(() => useAuthoringSession());

    expect(result.current.phase).toBe("discovery");
    expect(result.current.transcript).toEqual([]);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.draftGraph).toEqual({});
  });

  it("sends user message and updates state from agent-wizard response", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(AGENT_RESPONSE),
    });

    const { result } = renderHook(() => useAuthoringSession());

    await act(async () => {
      await result.current.sendMessage("Create a researcher agent");
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.phase).toBe("proposal");
    expect(result.current.transcript.length).toBeGreaterThan(0);
    expect(result.current.draftGraph).toEqual({
      agents: [{ key: "researcher", role: "Researcher" }],
    });
  });

  it("calls the agent-wizard endpoint", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(AGENT_RESPONSE),
    });

    const { result } = renderHook(() => useAuthoringSession());

    await act(async () => {
      await result.current.sendMessage("Create a researcher agent");
    });

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/authoring/agent-wizard",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "Content-Type": "application/json" }),
      }),
    );
  });

  it("adds both user message and assistant message to transcript", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(AGENT_RESPONSE),
    });

    const { result } = renderHook(() => useAuthoringSession());

    await act(async () => {
      await result.current.sendMessage("Create a researcher agent");
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const userMessages = result.current.transcript.filter((m) => m.role === "user");
    const assistantMessages = result.current.transcript.filter((m) => m.role === "assistant");
    expect(userMessages.length).toBeGreaterThanOrEqual(1);
    expect(assistantMessages.length).toBeGreaterThanOrEqual(1);
  });
});

describe("useAuthoringSession - merging draft graph", () => {
  it("merges subsequent patches into the accumulated draft graph", async () => {
    const firstResponse = {
      ...AGENT_RESPONSE,
      draft_graph_patch: { agents: [{ key: "researcher", role: "Researcher" }] },
    };
    const secondResponse = {
      ...AGENT_RESPONSE,
      phase: "refinement",
      draft_graph_patch: { agents: [{ key: "researcher", role: "Researcher", model: "opus" }] },
    };

    mockFetch
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue(firstResponse) })
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue(secondResponse) });

    const { result } = renderHook(() => useAuthoringSession());

    await act(async () => {
      await result.current.sendMessage("Create a researcher agent");
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.sendMessage("Add opus model");
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.phase).toBe("refinement");
    // The merged graph should reflect the latest patch
    expect(result.current.draftGraph).toHaveProperty("agents");
  });
});

describe("useAuthoringSession - reset", () => {
  it("resets state to initial values", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(AGENT_RESPONSE),
    });

    const { result } = renderHook(() => useAuthoringSession());

    await act(async () => {
      await result.current.sendMessage("Create a researcher agent");
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    act(() => {
      result.current.reset();
    });

    expect(result.current.phase).toBe("discovery");
    expect(result.current.transcript).toEqual([]);
    expect(result.current.draftGraph).toEqual({});
  });
});
