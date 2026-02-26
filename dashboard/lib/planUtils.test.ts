import { describe, it, expect } from "vitest";
import {
  hasCycle,
  recalcParallelGroups,
  recalcOrderFromDAG,
  insertSequentialStep,
  insertParallelStep,
  swapStepPositions,
  insertMergeStep,
  type PlanStep,
} from "./planUtils";

function makeStep(overrides: Partial<PlanStep> & { tempId: string }): PlanStep {
  return {
    title: overrides.tempId,
    description: overrides.tempId,
    assignedAgent: "nanobot",
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

describe("recalcOrderFromDAG", () => {
  it("assigns order based on topological sort of dependencies", () => {
    const steps: PlanStep[] = [
      makeStep({ tempId: "C", blockedBy: ["B"], order: 0 }),
      makeStep({ tempId: "A", blockedBy: [], order: 1 }),
      makeStep({ tempId: "B", blockedBy: ["A"], order: 2 }),
    ];
    const result = recalcOrderFromDAG(steps);
    const orderA = result.find((s) => s.tempId === "A")!.order;
    const orderB = result.find((s) => s.tempId === "B")!.order;
    const orderC = result.find((s) => s.tempId === "C")!.order;
    // A must come before B, B must come before C
    expect(orderA).toBeLessThan(orderB);
    expect(orderB).toBeLessThan(orderC);
  });

  it("assigns consecutive orders starting from 0", () => {
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [], order: 5 }),
      makeStep({ tempId: "B", blockedBy: ["A"], order: 10 }),
    ];
    const result = recalcOrderFromDAG(steps);
    expect(result.find((s) => s.tempId === "A")!.order).toBe(0);
    expect(result.find((s) => s.tempId === "B")!.order).toBe(1);
  });

  it("preserves array order for steps at the same level", () => {
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [], order: 0 }),
      makeStep({ tempId: "B", blockedBy: [], order: 1 }),
      makeStep({ tempId: "C", blockedBy: [], order: 2 }),
    ];
    const result = recalcOrderFromDAG(steps);
    // All are roots — should preserve original array order
    expect(result.find((s) => s.tempId === "A")!.order).toBe(0);
    expect(result.find((s) => s.tempId === "B")!.order).toBe(1);
    expect(result.find((s) => s.tempId === "C")!.order).toBe(2);
  });

  it("handles diamond dependency pattern", () => {
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [], order: 0 }),
      makeStep({ tempId: "B", blockedBy: ["A"], order: 1 }),
      makeStep({ tempId: "C", blockedBy: ["A"], order: 2 }),
      makeStep({ tempId: "D", blockedBy: ["B", "C"], order: 3 }),
    ];
    const result = recalcOrderFromDAG(steps);
    const orderA = result.find((s) => s.tempId === "A")!.order;
    const orderB = result.find((s) => s.tempId === "B")!.order;
    const orderC = result.find((s) => s.tempId === "C")!.order;
    const orderD = result.find((s) => s.tempId === "D")!.order;
    expect(orderA).toBeLessThan(orderB);
    expect(orderA).toBeLessThan(orderC);
    expect(orderB).toBeLessThan(orderD);
    expect(orderC).toBeLessThan(orderD);
  });

  it("does not mutate the original steps array", () => {
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [], order: 99 }),
    ];
    const result = recalcOrderFromDAG(steps);
    expect(result[0].order).toBe(0);
    expect(steps[0].order).toBe(99);
  });

  it("handles dangling blockedBy reference gracefully", () => {
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: ["Z"], order: 0 }),
      makeStep({ tempId: "B", blockedBy: [], order: 1 }),
    ];
    // Should not throw
    expect(() => recalcOrderFromDAG(steps)).not.toThrow();
  });

  it("handles cyclic dependencies without infinite loop", () => {
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: ["B"], order: 0 }),
      makeStep({ tempId: "B", blockedBy: ["A"], order: 1 }),
    ];
    expect(() => recalcOrderFromDAG(steps)).not.toThrow();
    const result = recalcOrderFromDAG(steps);
    expect(result).toHaveLength(2);
  });
});

describe("insertSequentialStep", () => {
  it("inserts between a step and its single downstream dependent", () => {
    // A → B (B.blockedBy = [A])
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [] }),
      makeStep({ tempId: "B", blockedBy: ["A"] }),
    ];
    const { steps: result, newStep } = insertSequentialStep(steps, "A");
    // New step should be blocked by A
    expect(newStep.blockedBy).toEqual(["A"]);
    // B should now be blocked by the new step, not A
    const b = result.find((s) => s.tempId === "B")!;
    expect(b.blockedBy).toContain(newStep.tempId);
    expect(b.blockedBy).not.toContain("A");
  });

  it("inserts between a step and multiple downstream dependents", () => {
    // A → B, A → C
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [] }),
      makeStep({ tempId: "B", blockedBy: ["A"] }),
      makeStep({ tempId: "C", blockedBy: ["A"] }),
    ];
    const { steps: result, newStep } = insertSequentialStep(steps, "A");
    const b = result.find((s) => s.tempId === "B")!;
    const c = result.find((s) => s.tempId === "C")!;
    // Both B and C now depend on newStep
    expect(b.blockedBy).toContain(newStep.tempId);
    expect(c.blockedBy).toContain(newStep.tempId);
    expect(b.blockedBy).not.toContain("A");
    expect(c.blockedBy).not.toContain("A");
  });

  it("inserts after a leaf node (no downstream dependents)", () => {
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [] }),
      makeStep({ tempId: "B", blockedBy: ["A"] }),
    ];
    const { steps: result, newStep } = insertSequentialStep(steps, "B");
    // New step blocked by B, no rewiring needed
    expect(newStep.blockedBy).toEqual(["B"]);
    expect(result).toHaveLength(3);
    // B should be unchanged
    const b = result.find((s) => s.tempId === "B")!;
    expect(b.blockedBy).toEqual(["A"]);
  });

  it("inserts after a root step with no blockers", () => {
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [] }),
    ];
    const { steps: result, newStep } = insertSequentialStep(steps, "A");
    expect(newStep.blockedBy).toEqual(["A"]);
    expect(result).toHaveLength(2);
  });

  it("recalculates parallelGroups and order", () => {
    // A → B
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [] }),
      makeStep({ tempId: "B", blockedBy: ["A"] }),
    ];
    const { steps: result, newStep } = insertSequentialStep(steps, "A");
    const a = result.find((s) => s.tempId === "A")!;
    const n = result.find((s) => s.tempId === newStep.tempId)!;
    const b = result.find((s) => s.tempId === "B")!;
    // Chain: A(0) → New(1) → B(2)
    expect(a.parallelGroup).toBe(0);
    expect(n.parallelGroup).toBe(1);
    expect(b.parallelGroup).toBe(2);
    expect(a.order).toBeLessThan(n.order);
    expect(n.order).toBeLessThan(b.order);
  });
});

describe("insertParallelStep", () => {
  it("creates a step with the same blockers as the source", () => {
    // X → A → Y
    const steps: PlanStep[] = [
      makeStep({ tempId: "X", blockedBy: [] }),
      makeStep({ tempId: "A", blockedBy: ["X"] }),
      makeStep({ tempId: "Y", blockedBy: ["A"] }),
    ];
    const { newStep } = insertParallelStep(steps, "A");
    // New step should have same blockers as A
    expect(newStep.blockedBy).toEqual(["X"]);
  });

  it("adds new step to downstream dependents' blockedBy", () => {
    // X → A → Y
    const steps: PlanStep[] = [
      makeStep({ tempId: "X", blockedBy: [] }),
      makeStep({ tempId: "A", blockedBy: ["X"] }),
      makeStep({ tempId: "Y", blockedBy: ["A"] }),
    ];
    const { steps: result, newStep } = insertParallelStep(steps, "A");
    const y = result.find((s) => s.tempId === "Y")!;
    // Y should now be blocked by both A and the new step
    expect(y.blockedBy).toContain("A");
    expect(y.blockedBy).toContain(newStep.tempId);
  });

  it("handles root step (no blockers) — new step is also a root", () => {
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [] }),
      makeStep({ tempId: "B", blockedBy: ["A"] }),
    ];
    const { newStep } = insertParallelStep(steps, "A");
    expect(newStep.blockedBy).toEqual([]);
  });

  it("handles step with multiple downstreams", () => {
    // A → B, A → C
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [] }),
      makeStep({ tempId: "B", blockedBy: ["A"] }),
      makeStep({ tempId: "C", blockedBy: ["A"] }),
    ];
    const { steps: result, newStep } = insertParallelStep(steps, "A");
    const b = result.find((s) => s.tempId === "B")!;
    const c = result.find((s) => s.tempId === "C")!;
    // Both B and C should also depend on newStep
    expect(b.blockedBy).toContain(newStep.tempId);
    expect(c.blockedBy).toContain(newStep.tempId);
  });

  it("places new step at same parallelGroup as source", () => {
    const steps: PlanStep[] = [
      makeStep({ tempId: "X", blockedBy: [] }),
      makeStep({ tempId: "A", blockedBy: ["X"] }),
    ];
    const { steps: result, newStep } = insertParallelStep(steps, "A");
    const a = result.find((s) => s.tempId === "A")!;
    const n = result.find((s) => s.tempId === newStep.tempId)!;
    expect(n.parallelGroup).toBe(a.parallelGroup);
  });
});

describe("swapStepPositions", () => {
  it("swaps two independent steps' positions", () => {
    // A(root), B(root), C blocked by A, D blocked by B
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [] }),
      makeStep({ tempId: "B", blockedBy: [] }),
      makeStep({ tempId: "C", blockedBy: ["A"] }),
      makeStep({ tempId: "D", blockedBy: ["B"] }),
    ];
    const result = swapStepPositions(steps, "A", "B");
    const c = result.find((s) => s.tempId === "C")!;
    const d = result.find((s) => s.tempId === "D")!;
    // After swap: C should be blocked by B, D should be blocked by A
    expect(c.blockedBy).toEqual(["B"]);
    expect(d.blockedBy).toEqual(["A"]);
  });

  it("swaps adjacent steps (A → B becomes B → A)", () => {
    // A → B (B.blockedBy = [A])
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [] }),
      makeStep({ tempId: "B", blockedBy: ["A"] }),
    ];
    const result = swapStepPositions(steps, "A", "B");
    const a = result.find((s) => s.tempId === "A")!;
    const b = result.find((s) => s.tempId === "B")!;
    // After swap: B should have no blockers (was A's), A should be blocked by B
    expect(b.blockedBy).toEqual([]);
    expect(a.blockedBy).toEqual(["B"]);
  });

  it("swaps steps at different DAG levels", () => {
    // A → B → C
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [] }),
      makeStep({ tempId: "B", blockedBy: ["A"] }),
      makeStep({ tempId: "C", blockedBy: ["B"] }),
    ];
    const result = swapStepPositions(steps, "A", "C");
    const a = result.find((s) => s.tempId === "A")!;
    const b = result.find((s) => s.tempId === "B")!;
    const c = result.find((s) => s.tempId === "C")!;
    // After swap: C gets A's blockedBy (empty), A gets C's blockedBy (B), B stays blocked by C
    expect(c.blockedBy).toEqual([]);
    expect(a.blockedBy).toEqual(["B"]);
    expect(b.blockedBy).toEqual(["C"]);
  });

  it("returns original steps if a tempId is not found", () => {
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [] }),
    ];
    const result = swapStepPositions(steps, "A", "Z");
    expect(result).toEqual(steps);
  });
});

describe("insertMergeStep", () => {
  it("creates a step blocked by all parallel steps at the same group", () => {
    // A(group 0), B(group 0) — two parallel roots
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [], parallelGroup: 0 }),
      makeStep({ tempId: "B", blockedBy: [], parallelGroup: 0 }),
    ];
    const { newStep } = insertMergeStep(steps, "A");
    expect(newStep.blockedBy).toContain("A");
    expect(newStep.blockedBy).toContain("B");
    expect(newStep.blockedBy).toHaveLength(2);
  });

  it("rewires downstream dependents to depend on the merge step", () => {
    // A(group 0), B(group 0), C depends on A, D depends on B
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [], parallelGroup: 0 }),
      makeStep({ tempId: "B", blockedBy: [], parallelGroup: 0 }),
      makeStep({ tempId: "C", blockedBy: ["A"], parallelGroup: 1 }),
      makeStep({ tempId: "D", blockedBy: ["B"], parallelGroup: 1 }),
    ];
    const { steps: result, newStep } = insertMergeStep(steps, "A");
    const c = result.find((s) => s.tempId === "C")!;
    const d = result.find((s) => s.tempId === "D")!;
    // C and D should now depend on merge step, not A/B
    expect(c.blockedBy).toContain(newStep.tempId);
    expect(c.blockedBy).not.toContain("A");
    expect(d.blockedBy).toContain(newStep.tempId);
    expect(d.blockedBy).not.toContain("B");
  });

  it("shared downstream step is rewired once to merge step", () => {
    // A(group 0), B(group 0) both → C
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [], parallelGroup: 0 }),
      makeStep({ tempId: "B", blockedBy: [], parallelGroup: 0 }),
      makeStep({ tempId: "C", blockedBy: ["A", "B"], parallelGroup: 1 }),
    ];
    const { steps: result, newStep } = insertMergeStep(steps, "B");
    const c = result.find((s) => s.tempId === "C")!;
    expect(c.blockedBy).toEqual([newStep.tempId]);
  });

  it("merge step gets a higher parallelGroup than the parallel steps", () => {
    const steps: PlanStep[] = [
      makeStep({ tempId: "A", blockedBy: [], parallelGroup: 0 }),
      makeStep({ tempId: "B", blockedBy: [], parallelGroup: 0 }),
    ];
    const { steps: result, newStep } = insertMergeStep(steps, "A");
    const a = result.find((s) => s.tempId === "A")!;
    const n = result.find((s) => s.tempId === newStep.tempId)!;
    expect(n.parallelGroup).toBeGreaterThan(a.parallelGroup);
  });

  it("throws if tempId is not found", () => {
    const steps: PlanStep[] = [makeStep({ tempId: "A", blockedBy: [] })];
    expect(() => insertMergeStep(steps, "Z")).toThrow();
  });
});
