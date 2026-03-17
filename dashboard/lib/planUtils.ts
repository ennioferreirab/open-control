/**
 * Pure functions for graph-aware plan step insertion.
 * Each function returns a new EditablePlanStep[] with the transformation applied.
 */

import type { EditablePlanStep } from "./types";

export type StepData = Partial<Pick<EditablePlanStep, "title" | "description" | "assignedAgent">>;

function blockersKey(blockedBy: string[]): string {
  return [...new Set(blockedBy)].sort().join("|");
}

/** Generate the next unique tempId for a step. */
function nextTempId(steps: EditablePlanStep[]): string {
  const existingIds = new Set(steps.map((s) => s.tempId));
  const existingNums = steps
    .map((s) => s.tempId)
    .filter((id) => /^step_\d+$/.test(id))
    .map((id) => parseInt(id.replace("step_", ""), 10));
  let nextNum = existingNums.length > 0 ? Math.max(...existingNums) + 1 : steps.length + 1;
  // Guard against collisions with existing IDs of any format
  while (existingIds.has(`step_${nextNum}`)) {
    nextNum++;
  }
  return `step_${nextNum}`;
}

/**
 * Return the IDs that can be merged with `tempId`.
 * Merge scope is limited to steps in the same fork: same parallelGroup and same blockers.
 */
export function getMergeableSiblingIds(steps: EditablePlanStep[], tempId: string): string[] {
  const sourceStep = steps.find((s) => s.tempId === tempId);
  if (!sourceStep) return [];

  const sourceBlockersKey = blockersKey(sourceStep.blockedBy);
  return steps
    .filter(
      (step) =>
        step.parallelGroup === sourceStep.parallelGroup &&
        blockersKey(step.blockedBy) === sourceBlockersKey,
    )
    .map((step) => step.tempId);
}

/**
 * Insert a step sequentially after `afterTempId`.
 * Downstream steps that depended on `afterTempId` are rerouted through the new step.
 */
export function insertSequentialStep(
  steps: EditablePlanStep[],
  afterTempId: string,
  stepData?: StepData,
): EditablePlanStep[] {
  const sourceStep = steps.find((s) => s.tempId === afterTempId);
  if (!sourceStep) return steps;

  const newId = nextTempId(steps);
  const maxOrder = steps.reduce((max, s) => Math.max(max, s.order), 0);

  const newStep: EditablePlanStep = {
    tempId: newId,
    title: stepData?.title ?? "",
    description: stepData?.description ?? "",
    assignedAgent: stepData?.assignedAgent ?? "nanobot",
    blockedBy: [afterTempId],
    parallelGroup: sourceStep.parallelGroup + 1,
    order: maxOrder + 1,
  };

  // Reroute downstream: steps that depended on afterTempId now depend on newId
  const updatedSteps = steps.map((s) => {
    if (s.blockedBy.includes(afterTempId)) {
      return {
        ...s,
        blockedBy: s.blockedBy.map((id) => (id === afterTempId ? newId : id)),
      };
    }
    return s;
  });

  return [...updatedSteps, newStep];
}

/**
 * Insert a step parallel to `parallelToTempId`.
 * The new step shares the same blockers as the source step.
 */
export function insertParallelStep(
  steps: EditablePlanStep[],
  parallelToTempId: string,
  stepData?: StepData,
): EditablePlanStep[] {
  const sourceStep = steps.find((s) => s.tempId === parallelToTempId);
  if (!sourceStep) return steps;

  const newId = nextTempId(steps);
  const maxOrder = steps.reduce((max, s) => Math.max(max, s.order), 0);

  const newStep: EditablePlanStep = {
    tempId: newId,
    title: stepData?.title ?? "",
    description: stepData?.description ?? "",
    assignedAgent: stepData?.assignedAgent ?? "nanobot",
    blockedBy: [...sourceStep.blockedBy],
    parallelGroup: sourceStep.parallelGroup,
    order: maxOrder + 1,
  };

  return [...steps, newStep];
}

/**
 * Insert a merge step that depends on all siblings in the parallel group of `tempId`.
 * Downstream steps that depended on any sibling are rerouted through the merge step.
 */
export function insertMergeStep(
  steps: EditablePlanStep[],
  tempId: string,
  stepData?: StepData,
): EditablePlanStep[] {
  const sourceStep = steps.find((s) => s.tempId === tempId);
  if (!sourceStep) return steps;

  const mergeableSiblingIds = getMergeableSiblingIds(steps, tempId);
  if (mergeableSiblingIds.length < 2) return steps;
  const siblingIds = new Set(mergeableSiblingIds);

  const newId = nextTempId(steps);
  const maxOrder = steps.reduce((max, s) => Math.max(max, s.order), 0);

  const newStep: EditablePlanStep = {
    tempId: newId,
    title: stepData?.title ?? "",
    description: stepData?.description ?? "",
    assignedAgent: stepData?.assignedAgent ?? "nanobot",
    blockedBy: [...siblingIds],
    parallelGroup: sourceStep.parallelGroup + 1,
    order: maxOrder + 1,
  };

  // Reroute downstream: steps that depended on any sibling now depend on newId
  const updatedSteps = steps.map((s) => {
    if (siblingIds.has(s.tempId)) return s; // Don't modify siblings themselves
    const reroutedBlockers = s.blockedBy.some((id) => siblingIds.has(id));
    if (reroutedBlockers) {
      return {
        ...s,
        blockedBy: [...s.blockedBy.filter((id) => !siblingIds.has(id)), newId],
      };
    }
    return s;
  });

  return [...updatedSteps, newStep];
}
