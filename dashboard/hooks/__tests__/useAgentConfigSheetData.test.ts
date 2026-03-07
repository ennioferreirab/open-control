import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

const mockUpdateConfig = vi.fn();
const mockSetEnabled = vi.fn();

vi.mock("convex/react", () => ({
  useMutation: (ref: string) => {
    if (ref === "agents:updateConfig") return mockUpdateConfig;
    if (ref === "agents:setEnabled") return mockSetEnabled;
    return vi.fn();
  },
  useQuery: (ref: string, args?: unknown) => {
    if (args === "skip") return undefined;
    if (ref === "agents:getByName") {
      return {
        _id: "agent1",
        _creationTime: 1000,
        name: "test-agent",
        displayName: "Test Agent",
        role: "Developer",
        prompt: "You are a developer.",
        skills: ["github"],
        model: "claude-sonnet-4-6",
        status: "active",
        enabled: true,
      };
    }
    if (ref === "settings:get") {
      const typedArgs = args as { key?: string } | undefined;
      if (typedArgs?.key === "connected_models") {
        return JSON.stringify(["claude-sonnet-4-6", "claude-opus-4-6"]);
      }
      if (typedArgs?.key === "model_tiers") {
        return JSON.stringify({ "standard-low": "claude-haiku-4-5" });
      }
    }
    return undefined;
  },
}));

vi.mock("../../convex/_generated/api", () => ({
  api: {
    agents: {
      getByName: "agents:getByName",
      updateConfig: "agents:updateConfig",
      setEnabled: "agents:setEnabled",
    },
    settings: { get: "settings:get" },
  },
}));

import { useAgentConfigSheetData } from "../useAgentConfigSheetData";

describe("useAgentConfigSheetData", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUpdateConfig.mockResolvedValue(undefined);
    mockSetEnabled.mockResolvedValue(undefined);
  });

  it("returns agent data when agentName is provided", () => {
    const { result } = renderHook(() =>
      useAgentConfigSheetData("test-agent"),
    );

    expect(result.current.agent).toBeDefined();
    expect(result.current.agent?.name).toBe("test-agent");
  });

  it("returns undefined agent when agentName is null", () => {
    const { result } = renderHook(() => useAgentConfigSheetData(null));

    expect(result.current.agent).toBeUndefined();
  });

  it("parses connected models from JSON setting", () => {
    const { result } = renderHook(() =>
      useAgentConfigSheetData("test-agent"),
    );

    expect(result.current.connectedModels).toEqual([
      "claude-sonnet-4-6",
      "claude-opus-4-6",
    ]);
  });

  it("parses model tiers from JSON setting", () => {
    const { result } = renderHook(() =>
      useAgentConfigSheetData("test-agent"),
    );

    expect(result.current.modelTiers).toEqual({
      "standard-low": "claude-haiku-4-5",
    });
  });

  it("updateConfig wraps the Convex mutation", async () => {
    const { result } = renderHook(() =>
      useAgentConfigSheetData("test-agent"),
    );

    await act(async () => {
      await result.current.updateConfig({
        name: "test-agent",
        role: "Senior Developer",
      });
    });

    expect(mockUpdateConfig).toHaveBeenCalledWith({
      name: "test-agent",
      role: "Senior Developer",
    });
  });

  it("setEnabled wraps the Convex mutation", async () => {
    const { result } = renderHook(() =>
      useAgentConfigSheetData("test-agent"),
    );

    await act(async () => {
      await result.current.setEnabled({
        agentName: "test-agent",
        enabled: false,
      });
    });

    expect(mockSetEnabled).toHaveBeenCalledWith({
      agentName: "test-agent",
      enabled: false,
    });
  });
});
