import { describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";

vi.mock("convex/react", () => ({
  useQuery: () => [
    {
      _id: "agent-1",
      _creationTime: 1,
      name: "worker",
      displayName: "Worker",
      enabled: true,
      role: "developer",
    },
    {
      _id: "agent-2",
      _creationTime: 2,
      name: "terminal",
      displayName: "Terminal",
      enabled: true,
      role: "remote-terminal",
    },
  ],
}));

vi.mock("../convex/_generated/api", () => ({
  api: {
    agents: {
      list: "agents:list",
    },
  },
}));

import { useSelectableAgents } from "./useSelectableAgents";

describe("useSelectableAgents", () => {
  it("filters out remote-terminal agents from chat/delegation lists", () => {
    const { result } = renderHook(() => useSelectableAgents());

    expect(result.current?.map((agent) => agent.name)).toEqual(["worker"]);
  });
});
