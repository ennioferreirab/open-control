import { describe, it, expect } from "vitest";
import { hasCycle, recalcParallelGroups, type PlanStep } from "./planUtils";

function makeStep(overrides: Partial<PlanStep> & { tempId: string }): PlanStep {
  return {
    title: overrides.tempId,
    description: overrides.tempId,
    assignedAgent: "general-agent",
    blockedBy: [],
    parallelGroup: 0,
    order: 0,
    ...overrides,
  };
}

describe("hasCycle", () => {
  it("returns false for valid dependency (A -> B, propose B -> C)", () => {
    // A -> B means B.blockedBy = [A]
    // Propose B -> C means C.blockedBy should include B
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [] }),
      makeStep({ tempId: "B", blockedBy: ["A"] }),
      makeStep({ tempId: "C", blockedBy: [] }),
    ];
    // Propose adding B as blocker for C (B -> C)
    expect(hasCycle(steps, { stepTempId: "C", blockerTempId: "B" })).toBe(false);
  });

  it("returns true for direct cycle (A -> B exists, propose B -> A)", () => {
    // A -> B means B.blockedBy = [A]
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [] }),
      makeStep({ tempId: "B", blockedBy: ["A"] }),
    ];
    // Propose adding B as blocker for A (B -> A) — would create A -> B -> A
    expect(hasCycle(steps, { stepTempId: "A", blockerTempId: "B" })).toBe(true);
  });

  it("returns true for transitive cycle (A -> B -> C exists, propose C -> A)", () => {
    // A -> B -> C means B.blockedBy=[A], C.blockedBy=[B]
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [] }),
      makeStep({ tempId: "B", blockedBy: ["A"] }),
      makeStep({ tempId: "C", blockedBy: ["B"] }),
    ];
    // Propose adding C as blocker for A (C -> A) — would create A -> B -> C -> A
    expect(hasCycle(steps, { stepTempId: "A", blockerTempId: "C" })).toBe(true);
  });

  it("returns false when no steps have dependencies", () => {
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [] }),
      makeStep({ tempId: "B", blockedBy: [] }),
      makeStep({ tempId: "C", blockedBy: [] }),
    ];
    // Propose adding A as blocker for B (A -> B) — no existing edges, no cycle
    expect(hasCycle(steps, { stepTempId: "B", blockerTempId: "A" })).toBe(false);
  });

  it("handles self-dependency (propose A -> A)", () => {
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [] }),
    ];
    expect(hasCycle(steps, { stepTempId: "A", blockerTempId: "A" })).toBe(true);
  });

  it("returns false for a valid multi-level dependency (diamond pattern, add new valid edge)", () => {
    // A(0), B(1 blocked by A), C(1 blocked by A), D(2 blocked by B and C)
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [] }),
      makeStep({ tempId: "B", blockedBy: ["A"] }),
      makeStep({ tempId: "C", blockedBy: ["A"] }),
      makeStep({ tempId: "D", blockedBy: ["B", "C"] }),
    ];
    // Adding a new step E blocked by D — no cycle
    const stepsWithE = [...steps, makeStep({ tempId: "E", blockedBy: [] })];
    expect(hasCycle(stepsWithE, { stepTempId: "E", blockerTempId: "D" })).toBe(false);
  });
});

describe("recalcParallelGroups", () => {
  it("assigns group 0 to steps with no blockers", () => {
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [] }),
      makeStep({ tempId: "B", blockedBy: [] }),
    ];
    const result = recalcParallelGroups(steps);
    expect(result.find((s) => s.tempId === "A")!.parallelGroup).toBe(0);
    expect(result.find((s) => s.tempId === "B")!.parallelGroup).toBe(0);
  });

  it("assigns sequential groups in a chain (A(0) -> B(1) -> C(2))", () => {
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [] }),
      makeStep({ tempId: "B", blockedBy: ["A"] }),
      makeStep({ tempId: "C", blockedBy: ["B"] }),
    ];
    const result = recalcParallelGroups(steps);
    expect(result.find((s) => s.tempId === "A")!.parallelGroup).toBe(0);
    expect(result.find((s) => s.tempId === "B")!.parallelGroup).toBe(1);
    expect(result.find((s) => s.tempId === "C")!.parallelGroup).toBe(2);
  });

  it("assigns same group to parallel steps (A(0) and B(0) both with no blockers)", () => {
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [] }),
      makeStep({ tempId: "B", blockedBy: [] }),
      makeStep({ tempId: "C", blockedBy: ["A", "B"] }),
    ];
    const result = recalcParallelGroups(steps);
    expect(result.find((s) => s.tempId === "A")!.parallelGroup).toBe(0);
    expect(result.find((s) => s.tempId === "B")!.parallelGroup).toBe(0);
    expect(result.find((s) => s.tempId === "C")!.parallelGroup).toBe(1);
  });

  it("handles diamond dependency (A(0), B(1), C(1), D(2))", () => {
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [] }),
      makeStep({ tempId: "B", blockedBy: ["A"] }),
      makeStep({ tempId: "C", blockedBy: ["A"] }),
      makeStep({ tempId: "D", blockedBy: ["B", "C"] }),
    ];
    const result = recalcParallelGroups(steps);
    expect(result.find((s) => s.tempId === "A")!.parallelGroup).toBe(0);
    expect(result.find((s) => s.tempId === "B")!.parallelGroup).toBe(1);
    expect(result.find((s) => s.tempId === "C")!.parallelGroup).toBe(1);
    expect(result.find((s) => s.tempId === "D")!.parallelGroup).toBe(2);
  });

  it("does not mutate the original steps array", () => {
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [], parallelGroup: 99 }),
    ];
    const result = recalcParallelGroups(steps);
    expect(result[0].parallelGroup).toBe(0);
    expect(steps[0].parallelGroup).toBe(99); // original unchanged
  });

  it("handles dangling blockedBy reference (non-existent tempId) gracefully", () => {
    // Step B references a non-existent step "Z" as a blocker
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [] }),
      makeStep({ tempId: "B", blockedBy: ["Z"] }),
    ];
    const result = recalcParallelGroups(steps);
    // "Z" is not in the step map, so getLevel("Z") returns 0
    // Therefore B gets group 0 + 1 = 1
    expect(result.find((s) => s.tempId === "A")!.parallelGroup).toBe(0);
    expect(result.find((s) => s.tempId === "B")!.parallelGroup).toBe(1);
  });

  it("does not stack overflow when blockedBy data contains a cycle", () => {
    // Corrupted data: A blockedBy B and B blockedBy A (should not happen
    // normally since hasCycle prevents it, but the backend could provide
    // invalid data).
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: ["B"] }),
      makeStep({ tempId: "B", blockedBy: ["A"] }),
    ];
    // Should not throw a "Maximum call stack size exceeded" error
    expect(() => recalcParallelGroups(steps)).not.toThrow();
    const result = recalcParallelGroups(steps);
    // Both get a finite parallelGroup (exact values depend on traversal
    // order, but must be finite numbers)
    expect(Number.isFinite(result[0].parallelGroup)).toBe(true);
    expect(Number.isFinite(result[1].parallelGroup)).toBe(true);
  });
});
