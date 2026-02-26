import { describe, it, expect } from "vitest";
import { stepsToNodesAndEdges, layoutWithDagre } from "./flowLayout";
import type { PlanStep } from "./types";

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

describe("stepsToNodesAndEdges", () => {
  it("creates one flowStep node per step (plus START/END terminals)", () => {
    const steps = [
      makeStep({ tempId: "A" }),
      makeStep({ tempId: "B" }),
      makeStep({ tempId: "C" }),
    ];
    const { nodes } = stepsToNodesAndEdges(steps);
    const stepNodes = nodes.filter((n) => n.type === "flowStep");
    expect(stepNodes).toHaveLength(3);
    // START and END terminals are also present
    expect(nodes.find((n) => n.id === "__start__")).toBeDefined();
    expect(nodes.find((n) => n.id === "__end__")).toBeDefined();
  });

  it("creates edges from blockedBy", () => {
    const steps = [
      makeStep({ tempId: "A" }),
      makeStep({ tempId: "B", blockedBy: ["A"] }),
      makeStep({ tempId: "C", blockedBy: ["A", "B"] }),
    ];
    const { edges } = stepsToNodesAndEdges(steps);
    // Filter to step-to-step edges only
    const stepEdges = edges.filter(
      (e) => e.source !== "__start__" && e.target !== "__end__" && e.source !== "__start__"
    );
    const depEdges = stepEdges.filter(
      (e) => e.source !== "__start__" && e.target !== "__end__"
    );
    expect(depEdges).toHaveLength(3);
    expect(depEdges[0]).toMatchObject({ source: "A", target: "B" });
    expect(depEdges[1]).toMatchObject({ source: "A", target: "C" });
    expect(depEdges[2]).toMatchObject({ source: "B", target: "C" });
  });

  it("uses flowStep node type for step nodes", () => {
    const steps = [makeStep({ tempId: "A" })];
    const { nodes } = stepsToNodesAndEdges(steps);
    const stepNode = nodes.find((n) => n.id === "A")!;
    expect(stepNode.type).toBe("flowStep");
  });

  it("stores step data in node.data", () => {
    const steps = [makeStep({ tempId: "A", title: "My Step" })];
    const { nodes } = stepsToNodesAndEdges(steps);
    const stepNode = nodes.find((n) => n.id === "A")!;
    const data = stepNode.data as { step: PlanStep };
    expect(data.step.title).toBe("My Step");
    expect(data.step.tempId).toBe("A");
  });

  it("returns START/END with a direct edge when steps is empty", () => {
    const { nodes, edges } = stepsToNodesAndEdges([]);
    expect(nodes).toHaveLength(2);
    expect(nodes[0].id).toBe("__start__");
    expect(nodes[1].id).toBe("__end__");
    expect(edges).toHaveLength(1);
    expect(edges[0]).toMatchObject({ source: "__start__", target: "__end__" });
  });

  it("connects START to root steps and leaf steps to END", () => {
    const steps = [
      makeStep({ tempId: "A" }),
      makeStep({ tempId: "B", blockedBy: ["A"] }),
    ];
    const { edges } = stepsToNodesAndEdges(steps);
    expect(edges.find((e) => e.source === "__start__" && e.target === "A")).toBeDefined();
    expect(edges.find((e) => e.source === "B" && e.target === "__end__")).toBeDefined();
  });

  it("START/END nodes are non-interactive", () => {
    const { nodes } = stepsToNodesAndEdges([makeStep({ tempId: "A" })]);
    const startNode = nodes.find((n) => n.id === "__start__")!;
    const endNode = nodes.find((n) => n.id === "__end__")!;
    expect(startNode.selectable).toBe(false);
    expect(startNode.draggable).toBe(false);
    expect(startNode.deletable).toBe(false);
    expect(endNode.selectable).toBe(false);
    expect(endNode.draggable).toBe(false);
    expect(endNode.deletable).toBe(false);
  });
});

describe("layoutWithDagre", () => {
  it("positions nodes with valid x/y coordinates", () => {
    const steps = [
      makeStep({ tempId: "A" }),
      makeStep({ tempId: "B", blockedBy: ["A"] }),
    ];
    const { nodes, edges } = stepsToNodesAndEdges(steps);
    const positioned = layoutWithDagre(nodes, edges);

    // 2 step nodes + 2 terminal nodes
    expect(positioned).toHaveLength(4);
    for (const node of positioned) {
      expect(typeof node.position.x).toBe("number");
      expect(typeof node.position.y).toBe("number");
      expect(Number.isFinite(node.position.x)).toBe(true);
      expect(Number.isFinite(node.position.y)).toBe(true);
    }
  });

  it("places dependent nodes to the right of their blockers (LR direction)", () => {
    const steps = [
      makeStep({ tempId: "A" }),
      makeStep({ tempId: "B", blockedBy: ["A"] }),
    ];
    const { nodes, edges } = stepsToNodesAndEdges(steps);
    const positioned = layoutWithDagre(nodes, edges);

    const nodeA = positioned.find((n) => n.id === "A")!;
    const nodeB = positioned.find((n) => n.id === "B")!;
    expect(nodeB.position.x).toBeGreaterThan(nodeA.position.x);
  });

  it("places parallel nodes at the same x level (same rank in LR)", () => {
    const steps = [
      makeStep({ tempId: "A" }),
      makeStep({ tempId: "B", blockedBy: ["A"] }),
      makeStep({ tempId: "C", blockedBy: ["A"] }),
    ];
    const { nodes, edges } = stepsToNodesAndEdges(steps);
    const positioned = layoutWithDagre(nodes, edges);

    const nodeB = positioned.find((n) => n.id === "B")!;
    const nodeC = positioned.find((n) => n.id === "C")!;
    expect(nodeB.position.x).toBe(nodeC.position.x);
  });

  it("handles diamond dependency pattern", () => {
    const steps = [
      makeStep({ tempId: "A" }),
      makeStep({ tempId: "B", blockedBy: ["A"] }),
      makeStep({ tempId: "C", blockedBy: ["A"] }),
      makeStep({ tempId: "D", blockedBy: ["B", "C"] }),
    ];
    const { nodes, edges } = stepsToNodesAndEdges(steps);
    const positioned = layoutWithDagre(nodes, edges);

    const nodeA = positioned.find((n) => n.id === "A")!;
    const nodeB = positioned.find((n) => n.id === "B")!;
    const nodeD = positioned.find((n) => n.id === "D")!;

    // A at left, B/C in middle, D at right
    expect(nodeB.position.x).toBeGreaterThan(nodeA.position.x);
    expect(nodeD.position.x).toBeGreaterThan(nodeB.position.x);
  });

  it("does not mutate original nodes", () => {
    const steps = [makeStep({ tempId: "A" })];
    const { nodes, edges } = stepsToNodesAndEdges(steps);
    const originalX = nodes[0].position.x;
    const originalY = nodes[0].position.y;
    layoutWithDagre(nodes, edges);
    expect(nodes[0].position.x).toBe(originalX);
    expect(nodes[0].position.y).toBe(originalY);
  });
});
