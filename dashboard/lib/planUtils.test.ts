import { describe, it, expect } from "vitest";
import {
  insertSequentialStep,
  insertParallelStep,
  insertMergeStep,
  getMergeableSiblingIds,
} from "./planUtils";
import type { EditablePlanStep } from "./types";

function makeStep(overrides: Partial<EditablePlanStep> = {}): EditablePlanStep {
  return {
    tempId: "step_1",
    title: "Step One",
    description: "First step",
    assignedAgent: "nanobot",
    blockedBy: [],
    parallelGroup: 1,
    order: 1,
    ...overrides,
  };
}

describe("insertSequentialStep", () => {
  it("inserts a step after the source with the source as its blocker", () => {
    const steps = [makeStep({ tempId: "step_1", order: 1 })];
    const result = insertSequentialStep(steps, "step_1");

    expect(result).toHaveLength(2);
    const newStep = result.find((s) => s.tempId !== "step_1")!;
    expect(newStep.blockedBy).toEqual(["step_1"]);
    expect(newStep.title).toBe("");
    expect(newStep.assignedAgent).toBe("nanobot");
  });

  it("uses stepData when provided", () => {
    const steps = [makeStep({ tempId: "step_1", order: 1 })];
    const result = insertSequentialStep(steps, "step_1", {
      title: "My Step",
      description: "My Description",
      assignedAgent: "agent-a",
    });

    const newStep = result.find((s) => s.tempId !== "step_1")!;
    expect(newStep.title).toBe("My Step");
    expect(newStep.description).toBe("My Description");
    expect(newStep.assignedAgent).toBe("agent-a");
  });

  it("reroutes downstream dependencies through the new step", () => {
    const steps = [
      makeStep({ tempId: "step_1", order: 1, parallelGroup: 1 }),
      makeStep({ tempId: "step_2", order: 2, parallelGroup: 2, blockedBy: ["step_1"] }),
    ];
    const result = insertSequentialStep(steps, "step_1");

    // step_2 should now depend on the new step, not step_1
    const step2 = result.find((s) => s.tempId === "step_2")!;
    const newStep = result.find((s) => s.tempId !== "step_1" && s.tempId !== "step_2")!;
    expect(step2.blockedBy).toEqual([newStep.tempId]);
    expect(newStep.blockedBy).toEqual(["step_1"]);
  });

  it("returns original steps when source not found", () => {
    const steps = [makeStep({ tempId: "step_1" })];
    const result = insertSequentialStep(steps, "nonexistent");
    expect(result).toEqual(steps);
  });

  it("without stepData maintains backward compatibility", () => {
    const steps = [makeStep({ tempId: "step_1", order: 1 })];
    const result = insertSequentialStep(steps, "step_1");
    const newStep = result.find((s) => s.tempId !== "step_1")!;
    expect(newStep.title).toBe("");
    expect(newStep.description).toBe("");
    expect(newStep.assignedAgent).toBe("nanobot");
  });
});

describe("insertParallelStep", () => {
  it("inserts a step with the same blockers as the source", () => {
    const steps = [
      makeStep({ tempId: "step_1", order: 1, parallelGroup: 1 }),
      makeStep({
        tempId: "step_2",
        order: 2,
        parallelGroup: 2,
        blockedBy: ["step_1"],
      }),
    ];
    const result = insertParallelStep(steps, "step_2");

    expect(result).toHaveLength(3);
    const newStep = result.find((s) => s.tempId !== "step_1" && s.tempId !== "step_2")!;
    expect(newStep.blockedBy).toEqual(["step_1"]);
    expect(newStep.parallelGroup).toBe(2);
  });

  it("uses stepData when provided", () => {
    const steps = [makeStep({ tempId: "step_1", order: 1 })];
    const result = insertParallelStep(steps, "step_1", {
      title: "Parallel Task",
      description: "Do in parallel",
      assignedAgent: "agent-b",
    });

    const newStep = result.find((s) => s.tempId !== "step_1")!;
    expect(newStep.title).toBe("Parallel Task");
    expect(newStep.description).toBe("Do in parallel");
    expect(newStep.assignedAgent).toBe("agent-b");
  });

  it("does not reroute any dependencies", () => {
    const steps = [
      makeStep({ tempId: "step_1", order: 1, parallelGroup: 1 }),
      makeStep({
        tempId: "step_2",
        order: 2,
        parallelGroup: 2,
        blockedBy: ["step_1"],
      }),
      makeStep({
        tempId: "step_3",
        order: 3,
        parallelGroup: 3,
        blockedBy: ["step_2"],
      }),
    ];
    const result = insertParallelStep(steps, "step_2");

    // step_3 should still depend on step_2 (unchanged)
    const step3 = result.find((s) => s.tempId === "step_3")!;
    expect(step3.blockedBy).toEqual(["step_2"]);
  });

  it("returns original steps when source not found", () => {
    const steps = [makeStep({ tempId: "step_1" })];
    const result = insertParallelStep(steps, "nonexistent");
    expect(result).toEqual(steps);
  });

  it("without stepData maintains backward compatibility", () => {
    const steps = [makeStep({ tempId: "step_1", order: 1 })];
    const result = insertParallelStep(steps, "step_1");
    const newStep = result.find((s) => s.tempId !== "step_1")!;
    expect(newStep.title).toBe("");
    expect(newStep.description).toBe("");
    expect(newStep.assignedAgent).toBe("nanobot");
  });
});

describe("insertMergeStep", () => {
  it("creates a step that depends on all parallel siblings", () => {
    const steps = [
      makeStep({ tempId: "step_1", order: 1, parallelGroup: 1 }),
      makeStep({ tempId: "step_2", order: 2, parallelGroup: 2, blockedBy: ["step_1"] }),
      makeStep({ tempId: "step_3", order: 2, parallelGroup: 2, blockedBy: ["step_1"] }),
    ];
    const result = insertMergeStep(steps, "step_2");

    const mergeStep = result.find(
      (s) => s.tempId !== "step_1" && s.tempId !== "step_2" && s.tempId !== "step_3",
    )!;
    expect(mergeStep.blockedBy).toContain("step_2");
    expect(mergeStep.blockedBy).toContain("step_3");
    expect(mergeStep.blockedBy).toHaveLength(2);
    expect(mergeStep.parallelGroup).toBe(3); // sourceGroup + 1
  });

  it("uses stepData when provided", () => {
    const steps = [
      makeStep({ tempId: "step_1", order: 1, parallelGroup: 1 }),
      makeStep({ tempId: "step_2", order: 2, parallelGroup: 1, blockedBy: [] }),
    ];
    const result = insertMergeStep(steps, "step_1", {
      title: "Merge Results",
      description: "Combine outputs",
      assignedAgent: "agent-c",
    });

    const mergeStep = result.find((s) => s.tempId !== "step_1" && s.tempId !== "step_2")!;
    expect(mergeStep.title).toBe("Merge Results");
    expect(mergeStep.description).toBe("Combine outputs");
    expect(mergeStep.assignedAgent).toBe("agent-c");
  });

  it("reroutes downstream dependencies from siblings to merge step", () => {
    const steps = [
      makeStep({ tempId: "step_1", order: 1, parallelGroup: 1 }),
      makeStep({ tempId: "step_2", order: 2, parallelGroup: 2, blockedBy: ["step_1"] }),
      makeStep({ tempId: "step_3", order: 2, parallelGroup: 2, blockedBy: ["step_1"] }),
      makeStep({ tempId: "step_4", order: 3, parallelGroup: 3, blockedBy: ["step_2"] }),
    ];
    const result = insertMergeStep(steps, "step_2");

    const mergeStep = result.find(
      (s) =>
        s.tempId !== "step_1" &&
        s.tempId !== "step_2" &&
        s.tempId !== "step_3" &&
        s.tempId !== "step_4",
    )!;
    // step_4 should now depend on merge step, not step_2
    const step4 = result.find((s) => s.tempId === "step_4")!;
    expect(step4.blockedBy).toContain(mergeStep.tempId);
    expect(step4.blockedBy).not.toContain("step_2");
  });

  it("reroutes downstream step depending on multiple siblings into single merge dep", () => {
    const steps = [
      makeStep({ tempId: "step_1", order: 1, parallelGroup: 1 }),
      makeStep({ tempId: "step_2", order: 2, parallelGroup: 2, blockedBy: ["step_1"] }),
      makeStep({ tempId: "step_3", order: 2, parallelGroup: 2, blockedBy: ["step_1"] }),
      makeStep({
        tempId: "step_4",
        order: 3,
        parallelGroup: 3,
        blockedBy: ["step_2", "step_3"],
      }),
    ];
    const result = insertMergeStep(steps, "step_2");

    const mergeStep = result.find(
      (s) => !["step_1", "step_2", "step_3", "step_4"].includes(s.tempId),
    )!;
    const step4 = result.find((s) => s.tempId === "step_4")!;
    // Both sibling deps replaced by single merge dep (no duplicates)
    expect(step4.blockedBy).toEqual([mergeStep.tempId]);
  });

  it("merges only siblings from the same fork when another fork shares the parallel group", () => {
    const steps = [
      makeStep({ tempId: "step_1", order: 1, parallelGroup: 1 }),
      makeStep({ tempId: "step_2", order: 2, parallelGroup: 2, blockedBy: ["step_1"] }),
      makeStep({ tempId: "step_3", order: 2, parallelGroup: 2, blockedBy: ["step_1"] }),
      makeStep({ tempId: "step_4", order: 2, parallelGroup: 2, blockedBy: ["step_99"] }),
      makeStep({ tempId: "step_5", order: 2, parallelGroup: 2, blockedBy: ["step_99"] }),
    ];

    const result = insertMergeStep(steps, "step_2");

    const mergeStep = result.find(
      (s) => !["step_1", "step_2", "step_3", "step_4", "step_5"].includes(s.tempId),
    )!;
    expect(mergeStep.blockedBy).toEqual(["step_2", "step_3"]);
  });

  it("reroutes only downstream dependencies from the merged fork", () => {
    const steps = [
      makeStep({ tempId: "step_1", order: 1, parallelGroup: 1 }),
      makeStep({ tempId: "step_2", order: 2, parallelGroup: 2, blockedBy: ["step_1"] }),
      makeStep({ tempId: "step_3", order: 2, parallelGroup: 2, blockedBy: ["step_1"] }),
      makeStep({ tempId: "step_4", order: 2, parallelGroup: 2, blockedBy: ["step_99"] }),
      makeStep({ tempId: "step_5", order: 2, parallelGroup: 2, blockedBy: ["step_99"] }),
      makeStep({ tempId: "step_6", order: 3, parallelGroup: 3, blockedBy: ["step_2"] }),
      makeStep({ tempId: "step_7", order: 3, parallelGroup: 3, blockedBy: ["step_4"] }),
    ];

    const result = insertMergeStep(steps, "step_2");

    const mergeStep = result.find(
      (s) => !["step_1", "step_2", "step_3", "step_4", "step_5", "step_6", "step_7"].includes(s.tempId),
    )!;
    const mergedDownstream = result.find((s) => s.tempId === "step_6")!;
    const unrelatedDownstream = result.find((s) => s.tempId === "step_7")!;

    expect(mergedDownstream.blockedBy).toEqual([mergeStep.tempId]);
    expect(unrelatedDownstream.blockedBy).toEqual(["step_4"]);
  });

  it("returns original steps when source not found", () => {
    const steps = [makeStep({ tempId: "step_1" })];
    const result = insertMergeStep(steps, "nonexistent");
    expect(result).toEqual(steps);
  });

  it("returns original steps when there is no mergeable sibling in the same fork", () => {
    const steps = [
      makeStep({ tempId: "step_1", order: 1, parallelGroup: 1 }),
      makeStep({ tempId: "step_2", order: 2, parallelGroup: 2, blockedBy: ["step_1"] }),
      makeStep({ tempId: "step_3", order: 2, parallelGroup: 2, blockedBy: ["step_99"] }),
    ];

    const result = insertMergeStep(steps, "step_2");
    expect(result).toEqual(steps);
  });

  it("without stepData maintains backward compatibility", () => {
    const steps = [
      makeStep({ tempId: "step_1", order: 1, parallelGroup: 1 }),
      makeStep({ tempId: "step_2", order: 1, parallelGroup: 1 }),
    ];
    const result = insertMergeStep(steps, "step_1");
    const mergeStep = result.find((s) => s.tempId !== "step_1" && s.tempId !== "step_2")!;
    expect(mergeStep.title).toBe("");
    expect(mergeStep.description).toBe("");
    expect(mergeStep.assignedAgent).toBe("nanobot");
  });
});

describe("getMergeableSiblingIds", () => {
  it("returns only siblings sharing both parallelGroup and blockers", () => {
    const steps = [
      makeStep({ tempId: "step_1", order: 1, parallelGroup: 1 }),
      makeStep({ tempId: "step_2", order: 2, parallelGroup: 2, blockedBy: ["step_1"] }),
      makeStep({ tempId: "step_3", order: 2, parallelGroup: 2, blockedBy: ["step_1"] }),
      makeStep({ tempId: "step_4", order: 2, parallelGroup: 2, blockedBy: ["step_99"] }),
    ];

    expect(getMergeableSiblingIds(steps, "step_2")).toEqual(["step_2", "step_3"]);
  });

  it("returns only the source id when there is no same-fork sibling", () => {
    const steps = [
      makeStep({ tempId: "step_1", order: 1, parallelGroup: 1 }),
      makeStep({ tempId: "step_2", order: 2, parallelGroup: 2, blockedBy: ["step_1"] }),
      makeStep({ tempId: "step_3", order: 2, parallelGroup: 2, blockedBy: ["step_99"] }),
    ];

    expect(getMergeableSiblingIds(steps, "step_2")).toEqual(["step_2"]);
  });
});
