import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

const mockDeleteStep = vi.fn();
const mockAcceptHumanStep = vi.fn();
const mockManualMoveStep = vi.fn();

vi.mock("convex/react", () => ({
  useMutation: (ref: string) => {
    if (ref === "steps:deleteStep") return mockDeleteStep;
    if (ref === "steps:acceptHumanStep") return mockAcceptHumanStep;
    if (ref === "steps:manualMoveStep") return mockManualMoveStep;
    return vi.fn();
  },
}));

vi.mock("../../convex/_generated/api", () => ({
  api: {
    steps: {
      deleteStep: "steps:deleteStep",
      acceptHumanStep: "steps:acceptHumanStep",
      manualMoveStep: "steps:manualMoveStep",
    },
  },
}));

import { useStepCardActions } from "../useStepCardActions";

describe("useStepCardActions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockDeleteStep.mockResolvedValue(undefined);
    mockAcceptHumanStep.mockResolvedValue(undefined);
    mockManualMoveStep.mockResolvedValue(undefined);
  });

  it("returns semantic functions for all step actions", () => {
    const { result } = renderHook(() => useStepCardActions());

    expect(typeof result.current.deleteStep).toBe("function");
    expect(typeof result.current.acceptHumanStep).toBe("function");
    expect(typeof result.current.manualMoveStep).toBe("function");
  });

  it("deleteStep wraps the Convex mutation", async () => {
    const { result } = renderHook(() => useStepCardActions());

    await act(async () => {
      await result.current.deleteStep({ stepId: "step1" as never });
    });

    expect(mockDeleteStep).toHaveBeenCalledWith({ stepId: "step1" });
  });

  it("acceptHumanStep wraps the Convex mutation", async () => {
    const { result } = renderHook(() => useStepCardActions());

    await act(async () => {
      await result.current.acceptHumanStep({ stepId: "step1" as never });
    });

    expect(mockAcceptHumanStep).toHaveBeenCalledWith({ stepId: "step1" });
  });

  it("manualMoveStep wraps the Convex mutation", async () => {
    const { result } = renderHook(() => useStepCardActions());

    await act(async () => {
      await result.current.manualMoveStep({
        stepId: "step1" as never,
        newStatus: "completed",
      });
    });

    expect(mockManualMoveStep).toHaveBeenCalledWith({
      stepId: "step1",
      newStatus: "completed",
    });
  });
});
