import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { usePlanEditorState } from "./usePlanEditorState";
import type { ExecutionPlan } from "@/lib/types";

const makePlan = (generatedAt = "2026-01-01T00:00:00Z"): ExecutionPlan => ({
  steps: [
    {
      tempId: "s1",
      title: "Step 1",
      description: "Do something",
      assignedAgent: "agent-alpha",
      blockedBy: [],
      parallelGroup: 0,
      order: 1,
    },
  ],
  generatedAt,
  generatedBy: "lead-agent",
});

describe("usePlanEditorState", () => {
  it("returns server plan as activePlan when no local edits", () => {
    const plan = makePlan();
    const { result } = renderHook(() => usePlanEditorState(plan, false));
    expect(result.current.activePlan).toBe(plan);
    expect(result.current.localPlan).toBeUndefined();
    expect(result.current.isDirty).toBe(false);
  });

  it("returns localPlan as activePlan when local edits exist", () => {
    const serverPlan = makePlan();
    const { result } = renderHook(() => usePlanEditorState(serverPlan, false));

    const localPlan = makePlan("2026-01-02T00:00:00Z");
    act(() => {
      result.current.setLocalPlan(localPlan);
    });

    expect(result.current.activePlan).toBe(localPlan);
    expect(result.current.isDirty).toBe(true);
  });

  it("defaults activeTab to 'thread' when not awaiting kickoff", () => {
    const { result } = renderHook(() => usePlanEditorState(undefined, false));
    expect(result.current.activeTab).toBe("thread");
  });

  it("defaults activeTab to 'plan' when awaiting kickoff", () => {
    const { result } = renderHook(() =>
      usePlanEditorState(makePlan(), true),
    );
    expect(result.current.activeTab).toBe("plan");
  });

  it("auto-switches to plan tab when isAwaitingKickoff becomes true", () => {
    const { result, rerender } = renderHook(
      ({ plan, awaiting }: { plan: ExecutionPlan | undefined; awaiting: boolean }) =>
        usePlanEditorState(plan, awaiting),
      { initialProps: { plan: makePlan(), awaiting: false } },
    );
    expect(result.current.activeTab).toBe("thread");

    rerender({ plan: makePlan(), awaiting: true });
    expect(result.current.activeTab).toBe("plan");
  });

  it("allows manual tab switching", () => {
    const { result } = renderHook(() => usePlanEditorState(undefined, false));
    act(() => {
      result.current.setActiveTab("config");
    });
    expect(result.current.activeTab).toBe("config");
  });

  it("resets local plan when server generatedAt changes", () => {
    const plan1 = makePlan("2026-01-01T00:00:00Z");
    const plan2 = makePlan("2026-01-02T00:00:00Z");

    const { result, rerender } = renderHook(
      ({ plan }: { plan: ExecutionPlan }) => usePlanEditorState(plan, false),
      { initialProps: { plan: plan1 } },
    );

    // Set local edits
    act(() => {
      result.current.setLocalPlan(makePlan("local-edit"));
    });
    expect(result.current.isDirty).toBe(true);

    // Server plan updates with new generatedAt
    rerender({ plan: plan2 });
    expect(result.current.localPlan).toBeUndefined();
    expect(result.current.isDirty).toBe(false);
  });

  it("does not reset local plan when server plan has same generatedAt", () => {
    const plan = makePlan();
    const { result, rerender } = renderHook(
      ({ p }: { p: ExecutionPlan }) => usePlanEditorState(p, false),
      { initialProps: { p: plan } },
    );

    const localEdits = makePlan("local");
    act(() => {
      result.current.setLocalPlan(localEdits);
    });
    expect(result.current.isDirty).toBe(true);

    // Re-render with same generatedAt
    rerender({ p: { ...plan } });
    expect(result.current.isDirty).toBe(true);
  });

  // Validation tests
  it("validate returns error for undefined plan", () => {
    const { result } = renderHook(() => usePlanEditorState(undefined, false));
    const errors = result.current.validate(undefined);
    expect(errors).toContain("No plan to validate");
  });

  it("validate returns error for empty steps", () => {
    const { result } = renderHook(() => usePlanEditorState(undefined, false));
    const plan: ExecutionPlan = {
      steps: [],
      generatedAt: "2026-01-01T00:00:00Z",
      generatedBy: "lead-agent",
    };
    const errors = result.current.validate(plan);
    expect(errors).toContain("Plan must have at least one step");
  });

  it("validate returns empty array for valid plan", () => {
    const { result } = renderHook(() => usePlanEditorState(undefined, false));
    const errors = result.current.validate(makePlan());
    expect(errors).toEqual([]);
  });

  it("validate catches steps without title or description", () => {
    const { result } = renderHook(() => usePlanEditorState(undefined, false));
    const plan: ExecutionPlan = {
      steps: [
        {
          tempId: "s1",
          title: "",
          description: "",
          assignedAgent: "a",
          blockedBy: [],
          parallelGroup: 0,
          order: 1,
        },
      ],
      generatedAt: "2026-01-01T00:00:00Z",
      generatedBy: "lead-agent",
    };
    const errors = result.current.validate(plan);
    expect(errors.length).toBeGreaterThan(0);
    expect(errors[0]).toContain("s1");
  });

  it("handles undefined taskExecutionPlan gracefully", () => {
    const { result } = renderHook(() => usePlanEditorState(undefined, false));
    expect(result.current.activePlan).toBeUndefined();
    expect(result.current.isDirty).toBe(false);
  });
});
