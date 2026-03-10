/**
 * Converts PlanStep[] into React Flow nodes/edges and applies dagre layout.
 */

import dagre from "@dagrejs/dagre";
import type { Node, Edge } from "@xyflow/react";
import type { PlanStep } from "./types";

export interface FlowLayoutOptions {
  nodeWidth?: number;
  nodeHeight?: number;
  rankSep?: number;
  nodeSep?: number;
  direction?: "TB" | "LR";
}

const DEFAULTS: Required<FlowLayoutOptions> = {
  nodeWidth: 220,
  nodeHeight: 80,
  rankSep: 120,
  nodeSep: 60,
  direction: "LR",
};

const START_NODE_ID = "__start__";
const END_NODE_ID = "__end__";
const START_END_WIDTH = 120;
const START_END_HEIGHT = 50;

/**
 * Convert PlanStep[] into React Flow nodes and edges.
 * Injects START and END terminal nodes connected to root/leaf steps.
 */
export function stepsToNodesAndEdges(
  steps: PlanStep[],
  options?: FlowLayoutOptions,
): { nodes: Node[]; edges: Edge[] } {
  const opts = { ...DEFAULTS, ...options };

  const startNode: Node = {
    id: START_NODE_ID,
    type: "start",
    data: {},
    position: { x: 0, y: 0 },
    width: START_END_WIDTH,
    height: START_END_HEIGHT,
    selectable: false,
    draggable: false,
    deletable: false,
  };

  const endNode: Node = {
    id: END_NODE_ID,
    type: "end",
    data: {},
    position: { x: 0, y: 0 },
    width: START_END_WIDTH,
    height: START_END_HEIGHT,
    selectable: false,
    draggable: false,
    deletable: false,
  };

  if (steps.length === 0) {
    return {
      nodes: [startNode, endNode],
      edges: [
        { id: `e-${START_NODE_ID}-${END_NODE_ID}`, source: START_NODE_ID, target: END_NODE_ID },
      ],
    };
  }

  const nodes: Node[] = steps.map((step) => ({
    id: step.tempId,
    type: "flowStep",
    data: { step },
    position: { x: 0, y: 0 },
    width: opts.nodeWidth,
    height: opts.nodeHeight,
  }));

  const edges: Edge[] = [];
  for (const step of steps) {
    for (const blockerId of step.blockedBy) {
      edges.push({
        id: `e-${blockerId}-${step.tempId}`,
        source: blockerId,
        target: step.tempId,
        animated: false,
      });
    }
  }

  // Root steps: no dependencies → connect from START
  const rootSteps = steps.filter((s) => s.blockedBy.length === 0);
  for (const step of rootSteps) {
    edges.push({
      id: `e-${START_NODE_ID}-${step.tempId}`,
      source: START_NODE_ID,
      target: step.tempId,
      animated: false,
    });
  }

  // Leaf steps: not referenced by any other step's blockedBy → connect to END
  const referencedByOthers = new Set(steps.flatMap((s) => s.blockedBy));
  const leafSteps = steps.filter((s) => !referencedByOthers.has(s.tempId));
  for (const step of leafSteps) {
    edges.push({
      id: `e-${step.tempId}-${END_NODE_ID}`,
      source: step.tempId,
      target: END_NODE_ID,
      animated: false,
    });
  }

  return { nodes: [startNode, ...nodes, endNode], edges };
}

/**
 * Position nodes using dagre (left-to-right layout).
 * Respects per-node width/height for accurate sizing of START/END nodes.
 */
export function layoutWithDagre(nodes: Node[], edges: Edge[], options?: FlowLayoutOptions): Node[] {
  const opts = { ...DEFAULTS, ...options };

  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({
    rankdir: opts.direction,
    ranksep: opts.rankSep,
    nodesep: opts.nodeSep,
  });

  for (const node of nodes) {
    g.setNode(node.id, {
      width: node.width ?? opts.nodeWidth,
      height: node.height ?? opts.nodeHeight,
    });
  }

  for (const edge of edges) {
    g.setEdge(edge.source, edge.target);
  }

  dagre.layout(g);

  return nodes.map((node) => {
    const nodeWithPosition = g.node(node.id);
    const w = node.width ?? opts.nodeWidth;
    const h = node.height ?? opts.nodeHeight;
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - w / 2,
        y: nodeWithPosition.y - h / 2,
      },
    };
  });
}
