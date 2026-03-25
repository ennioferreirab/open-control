import { ConvexError } from "convex/values";

/**
 * Validates that all step cross-references within a workflow are internally consistent.
 * MUST be called in every insertion/publish path. No exceptions.
 *
 * Checks:
 * - Every `dependsOn` item references an existing step key
 * - Review steps have a non-empty `onReject`
 * - Review step `onReject` target references an existing step key
 *
 * @param steps - Array of steps with key, type, and optional dependsOn/onReject fields
 * @param context - Human-readable context string for error messages (e.g. "workflow 'brand-delivery'")
 */
export function validateWorkflowStepReferences(
  steps: Array<{ key: string; type: string; dependsOn?: string[]; onReject?: string }>,
  context: string,
): void {
  const stepKeys = new Set(steps.map((s) => s.key));

  for (const step of steps) {
    // dependsOn must reference existing step keys
    if (step.dependsOn) {
      for (const dep of step.dependsOn) {
        if (!stepKeys.has(dep)) {
          throw new ConvexError(
            `Step "${step.key}" in ${context} has invalid dependsOn target "${dep}". ` +
              `Valid step keys: [${[...stepKeys].join(", ")}]`,
          );
        }
      }
    }

    // review steps: onReject must be non-empty and reference an existing step key
    if (step.type === "review") {
      if (!step.onReject || step.onReject.trim().length === 0) {
        throw new ConvexError(
          `Review step "${step.key}" in ${context} requires onReject. ` +
            `Valid step keys: [${[...stepKeys].join(", ")}]`,
        );
      }
      if (!stepKeys.has(step.onReject)) {
        throw new ConvexError(
          `Review step "${step.key}" in ${context} has invalid onReject target "${step.onReject}". ` +
            `Valid step keys: [${[...stepKeys].join(", ")}]`,
        );
      }
    }
  }
}
