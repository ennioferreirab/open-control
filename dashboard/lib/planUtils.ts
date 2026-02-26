/**
 * Pure utility functions for plan editing logic.
 * No React, no Convex, no UI dependencies.
 */

export type { PlanStep } from "./types";
import type { PlanStep } from "./types";

/**
 * Insert a new step sequentially after the given step.
 * The new step sits between `afterTempId` and all its downstream dependents.
 */
export function insertSequentialStep(
  steps: PlanStep[],
  afterTempId: string
): { steps: PlanStep[]; newStep: PlanStep } {
  const newTempId = `step_new_${Date.now()}`;
  const newStep: PlanStep = {
    tempId: newTempId,
    title: "",
    description: "",
    assignedAgent: "nanobot",
    blockedBy: [afterTempId],
    parallelGroup: 0,
    order: 0,
  };

  // Rewire downstream dependents: any step that has afterTempId in blockedBy
  // should now depend on newStep instead
  const updatedSteps = steps.map((s) => {
    if (!s.blockedBy.includes(afterTempId)) return s;
    return {
      ...s,
      blockedBy: s.blockedBy.map((id) => (id === afterTempId ? newTempId : id)),
    };
  });

  const result = recalcOrderFromDAG(recalcParallelGroups([...updatedSteps, newStep]));
  return { steps: result, newStep: result.find((s) => s.tempId === newTempId)! };
}

/**
 * Insert a new step in parallel with the given step.
 * The new step shares the same blockers and downstream dependents.
 */
export function insertParallelStep(
  steps: PlanStep[],
  parallelToTempId: string
): { steps: PlanStep[]; newStep: PlanStep } {
  const sourceStep = steps.find((s) => s.tempId === parallelToTempId);
  if (!sourceStep) throw new Error(`Step ${parallelToTempId} not found`);

  const newTempId = `step_new_${Date.now()}`;
  const newStep: PlanStep = {
    tempId: newTempId,
    title: "",
    description: "",
    assignedAgent: "nanobot",
    blockedBy: [...sourceStep.blockedBy],
    parallelGroup: 0,
    order: 0,
  };

  // Add newStep to blockedBy of all downstream dependents of the source
  const updatedSteps = steps.map((s) => {
    if (!s.blockedBy.includes(parallelToTempId)) return s;
    return {
      ...s,
      blockedBy: [...s.blockedBy, newTempId],
    };
  });

  const result = recalcOrderFromDAG(recalcParallelGroups([...updatedSteps, newStep]));
  return { steps: result, newStep: result.find((s) => s.tempId === newTempId)! };
}

/**
 * Swap two steps' positions in the DAG by swapping their blockedBy arrays
 * and updating all references to them in other steps.
 */
export function swapStepPositions(
  steps: PlanStep[],
  tempIdA: string,
  tempIdB: string
): PlanStep[] {
  const stepA = steps.find((s) => s.tempId === tempIdA);
  const stepB = steps.find((s) => s.tempId === tempIdB);
  if (!stepA || !stepB) return steps;

  const swapped = steps.map((s) => {
    if (s.tempId === tempIdA) {
      // A gets B's blockedBy, but replace any self-references
      return {
        ...s,
        blockedBy: stepB.blockedBy.map((id) =>
          id === tempIdA ? tempIdB : id === tempIdB ? tempIdA : id
        ),
      };
    }
    if (s.tempId === tempIdB) {
      // B gets A's blockedBy, but replace any self-references
      return {
        ...s,
        blockedBy: stepA.blockedBy.map((id) =>
          id === tempIdA ? tempIdB : id === tempIdB ? tempIdA : id
        ),
      };
    }
    // For all other steps, swap references in blockedBy
    return {
      ...s,
      blockedBy: s.blockedBy.map((id) =>
        id === tempIdA ? tempIdB : id === tempIdB ? tempIdA : id
      ),
    };
  });

  return recalcOrderFromDAG(recalcParallelGroups(swapped));
}

/**
 * Insert a merge step that converges all parallel steps at the same DAG level
 * into a single downstream step.
 *
 * All steps at the same parallelGroup as `tempId` become blockers of the new step.
 * Any existing downstream dependents of those parallel steps are rewired to depend
 * on the new merge step instead.
 */
export function insertMergeStep(
  steps: PlanStep[],
  tempId: string
): { steps: PlanStep[]; newStep: PlanStep } {
  const sourceStep = steps.find((s) => s.tempId === tempId);
  if (!sourceStep) throw new Error(`Step ${tempId} not found`);

  const group = sourceStep.parallelGroup;
  const parallelSteps = steps.filter((s) => s.parallelGroup === group);
  const parallelIds = new Set(parallelSteps.map((s) => s.tempId));

  const newTempId = `step_new_${Date.now()}`;
  const newStep: PlanStep = {
    tempId: newTempId,
    title: "",
    description: "",
    assignedAgent: "nanobot",
    blockedBy: parallelSteps.map((s) => s.tempId),
    parallelGroup: 0,
    order: 0,
  };

  // Rewire: any step that depends on any of the parallel steps now depends on the merge step
  const updatedSteps = steps.map((s) => {
    const hasParallelDep = s.blockedBy.some((id) => parallelIds.has(id));
    if (!hasParallelDep) return s;
    const cleaned = s.blockedBy.filter((id) => !parallelIds.has(id));
    return { ...s, blockedBy: [...cleaned, newTempId] };
  });

  const result = recalcOrderFromDAG(recalcParallelGroups([...updatedSteps, newStep]));
  return { steps: result, newStep: result.find((s) => s.tempId === newTempId)! };
}

/**
 * Checks if adding a proposed dependency edge would create a cycle.
 *
 * The dependency direction: step.blockedBy = [A, B] means A -> step and B -> step
 * (A and B must complete before step can run).
 *
 * When the user proposes that stepTempId should be blocked by blockerTempId,
 * we add edge blockerTempId -> stepTempId. We then check if stepTempId can
 * already reach blockerTempId in the graph. If so, adding the edge would create a cycle.
 *
 * @param steps - Current plan steps
 * @param proposed - Proposed new dependency edge
 * @returns true if adding the edge would create a cycle
 */
export function hasCycle(
  steps: PlanStep[],
  proposed: { stepTempId: string; blockerTempId: string }
): boolean {
  // Self-dependency is always a cycle
  if (proposed.stepTempId === proposed.blockerTempId) return true;

  // Build adjacency: blocker -> dependents
  // step.blockedBy = [X, Y] means edges X -> step, Y -> step
  const adj = new Map<string, string[]>();
  for (const s of steps) {
    for (const blocker of s.blockedBy) {
      const deps = adj.get(blocker) ?? [];
      deps.push(s.tempId);
      adj.set(blocker, deps);
    }
  }
  // Add proposed edge: blockerTempId -> stepTempId
  const deps = adj.get(proposed.blockerTempId) ?? [];
  deps.push(proposed.stepTempId);
  adj.set(proposed.blockerTempId, deps);

  // DFS from stepTempId: can we reach blockerTempId?
  // If yes, adding blockerTempId -> stepTempId creates a cycle.
  const visited = new Set<string>();
  function dfs(node: string): boolean {
    if (node === proposed.blockerTempId) return true;
    if (visited.has(node)) return false;
    visited.add(node);
    for (const neighbor of adj.get(node) ?? []) {
      if (dfs(neighbor)) return true;
    }
    return false;
  }
  return dfs(proposed.stepTempId);
}

/**
 * Recalculates parallelGroup values after reorder or dependency changes.
 *
 * Steps with no blockers get group 0.
 * Steps whose blockers are all in group N get group N+1.
 * Steps with multiple blockers get max(blocker groups) + 1.
 * This is equivalent to the longest path from a root node in a DAG.
 *
 * @param steps - Current plan steps
 * @returns New steps array with updated parallelGroup values
 */
export function recalcParallelGroups(steps: PlanStep[]): PlanStep[] {
  const stepMap = new Map(steps.map((s) => [s.tempId, s]));
  const levels = new Map<string, number>();
  // Guard against infinite recursion if blockedBy data contains a cycle
  // (e.g., corrupted backend data). Nodes currently being visited are
  // tracked in `visiting`; if we re-enter one, we treat it as level 0.
  const visiting = new Set<string>();

  function getLevel(tempId: string): number {
    if (levels.has(tempId)) return levels.get(tempId)!;
    if (visiting.has(tempId)) return 0; // break cycle
    const step = stepMap.get(tempId);
    if (!step || step.blockedBy.length === 0) {
      levels.set(tempId, 0);
      return 0;
    }
    visiting.add(tempId);
    const maxBlocker = Math.max(...step.blockedBy.map((id) => getLevel(id)));
    visiting.delete(tempId);
    const level = maxBlocker + 1;
    levels.set(tempId, level);
    return level;
  }

  for (const s of steps) getLevel(s.tempId);

  return steps.map((s) => ({
    ...s,
    parallelGroup: levels.get(s.tempId) ?? 0,
  }));
}

/**
 * Topological sort (Kahn's algorithm) to compute `order` from the DAG.
 * Steps with no blockers get the lowest orders; dependents come after.
 * Within the same level, original array order is preserved.
 *
 * @param steps - Current plan steps
 * @returns New steps array with updated `order` values (0-indexed)
 */
export function recalcOrderFromDAG(steps: PlanStep[]): PlanStep[] {
  const stepMap = new Map(steps.map((s) => [s.tempId, s]));
  const inDegree = new Map<string, number>();
  const adj = new Map<string, string[]>();

  for (const s of steps) {
    inDegree.set(s.tempId, 0);
    adj.set(s.tempId, []);
  }

  for (const s of steps) {
    for (const blocker of s.blockedBy) {
      if (stepMap.has(blocker)) {
        const targets = adj.get(blocker)!;
        targets.push(s.tempId);
        inDegree.set(s.tempId, (inDegree.get(s.tempId) ?? 0) + 1);
      }
    }
  }

  // Seed queue with zero in-degree nodes, preserving original order
  const queue: string[] = steps
    .filter((s) => (inDegree.get(s.tempId) ?? 0) === 0)
    .map((s) => s.tempId);

  const sorted: string[] = [];
  while (queue.length > 0) {
    const current = queue.shift()!;
    sorted.push(current);
    for (const neighbor of adj.get(current) ?? []) {
      const deg = (inDegree.get(neighbor) ?? 1) - 1;
      inDegree.set(neighbor, deg);
      if (deg === 0) {
        queue.push(neighbor);
      }
    }
  }

  // If cycle detected (sorted.length < steps.length), append remaining
  if (sorted.length < steps.length) {
    for (const s of steps) {
      if (!sorted.includes(s.tempId)) {
        sorted.push(s.tempId);
      }
    }
  }

  const orderMap = new Map(sorted.map((id, i) => [id, i]));
  return steps.map((s) => ({
    ...s,
    order: orderMap.get(s.tempId) ?? s.order,
  }));
}
