import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";

const mockSessions = [
  {
    _id: "sess1",
    _creationTime: 1000,
    sessionId: "s-1",
    agentName: "remote-1",
    status: "active",
  },
];

let lastQueryArgs: unknown = undefined;

vi.mock("convex/react", () => ({
  useQuery: (_ref: string, args?: unknown) => {
    lastQueryArgs = args;
    if (args === "skip") return undefined;
    return mockSessions;
  },
}));

vi.mock("../../convex/_generated/api", () => ({
  api: {
    terminalSessions: {
      listSessions: "terminalSessions:listSessions",
    },
  },
}));

import { useAgentSidebarItemState } from "@/features/agents/hooks/useAgentSidebarItemState";

describe("useAgentSidebarItemState", () => {
  it("returns terminal sessions when enabled is true", () => {
    const { result } = renderHook(() =>
      useAgentSidebarItemState("remote-1", true),
    );

    expect(result.current.terminalSessions).toEqual(mockSessions);
  });

  it("returns undefined when enabled is false (skip query)", () => {
    const { result } = renderHook(() =>
      useAgentSidebarItemState("remote-1", false),
    );

    expect(result.current.terminalSessions).toBeUndefined();
    expect(lastQueryArgs).toBe("skip");
  });

  it("passes agentName to the query when enabled", () => {
    renderHook(() => useAgentSidebarItemState("remote-1", true));

    expect(lastQueryArgs).toEqual({ agentName: "remote-1" });
  });
});
