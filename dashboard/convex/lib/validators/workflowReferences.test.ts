import { describe, expect, it } from "vitest";

import { validateWorkflowStepReferences } from "./workflowReferences";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const CONTEXT = "workflow 'brand-delivery'";

// ---------------------------------------------------------------------------
// dependsOn validation
// ---------------------------------------------------------------------------

describe("validateWorkflowStepReferences — dependsOn", () => {
  it("passes when dependsOn references a valid step key", () => {
    expect(() =>
      validateWorkflowStepReferences(
        [
          { key: "research", type: "agent" },
          { key: "write", type: "agent", dependsOn: ["research"] },
        ],
        CONTEXT,
      ),
    ).not.toThrow();
  });

  it("throws ConvexError when dependsOn references an invalid step key", () => {
    expect(() =>
      validateWorkflowStepReferences(
        [
          { key: "research", type: "agent" },
          { key: "write", type: "agent", dependsOn: ["nonexistent-step"] },
        ],
        CONTEXT,
      ),
    ).toThrow(/invalid dependsOn target "nonexistent-step"/);
  });

  it("includes the list of valid step keys in the dependsOn error message", () => {
    expect(() =>
      validateWorkflowStepReferences(
        [
          { key: "research", type: "agent" },
          { key: "write", type: "agent", dependsOn: ["missing"] },
        ],
        CONTEXT,
      ),
    ).toThrow(/Valid step keys: \[research, write\]/);
  });

  it("passes when steps have no dependsOn", () => {
    expect(() =>
      validateWorkflowStepReferences(
        [
          { key: "step-a", type: "agent" },
          { key: "step-b", type: "agent" },
        ],
        CONTEXT,
      ),
    ).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// onReject validation for review steps
// ---------------------------------------------------------------------------

describe("validateWorkflowStepReferences — review step onReject", () => {
  it("passes when review step onReject references a valid step key", () => {
    expect(() =>
      validateWorkflowStepReferences(
        [
          { key: "write", type: "agent" },
          { key: "review", type: "review", onReject: "write" },
        ],
        CONTEXT,
      ),
    ).not.toThrow();
  });

  it("throws ConvexError when review step onReject references an invalid step key", () => {
    expect(() =>
      validateWorkflowStepReferences(
        [
          { key: "write", type: "agent" },
          { key: "review", type: "review", onReject: "nonexistent-step" },
        ],
        CONTEXT,
      ),
    ).toThrow(/invalid onReject target "nonexistent-step"/);
  });

  it("throws ConvexError when onReject is a descriptive phrase instead of a step key", () => {
    expect(() =>
      validateWorkflowStepReferences(
        [
          { key: "assets", type: "agent" },
          { key: "review", type: "review", onReject: "Return to assets step for rework" },
        ],
        CONTEXT,
      ),
    ).toThrow(/invalid onReject target "Return to assets step for rework"/);
  });

  it("includes the list of valid step keys in the onReject error message", () => {
    expect(() =>
      validateWorkflowStepReferences(
        [
          { key: "write", type: "agent" },
          { key: "review", type: "review", onReject: "bad-step" },
        ],
        CONTEXT,
      ),
    ).toThrow(/Valid step keys: \[write, review\]/);
  });

  it("throws ConvexError when review step has no onReject", () => {
    expect(() =>
      validateWorkflowStepReferences(
        [
          { key: "write", type: "agent" },
          { key: "review", type: "review" },
        ],
        CONTEXT,
      ),
    ).toThrow(/requires onReject/);
  });

  it("throws ConvexError when review step has empty string onReject", () => {
    expect(() =>
      validateWorkflowStepReferences(
        [
          { key: "write", type: "agent" },
          { key: "review", type: "review", onReject: "   " },
        ],
        CONTEXT,
      ),
    ).toThrow(/requires onReject/);
  });
});

// ---------------------------------------------------------------------------
// Non-review step with onReject — should be ignored
// ---------------------------------------------------------------------------

describe("validateWorkflowStepReferences — non-review step onReject ignored", () => {
  it("does not validate onReject for agent-type steps", () => {
    expect(() =>
      validateWorkflowStepReferences(
        [{ key: "write", type: "agent", onReject: "some-arbitrary-string" }],
        CONTEXT,
      ),
    ).not.toThrow();
  });

  it("does not validate onReject for human-type steps", () => {
    expect(() =>
      validateWorkflowStepReferences(
        [{ key: "approve", type: "human", onReject: "not-a-real-step" }],
        CONTEXT,
      ),
    ).not.toThrow();
  });

  it("does not validate onReject for system-type steps", () => {
    expect(() =>
      validateWorkflowStepReferences(
        [{ key: "notify", type: "system", onReject: "also-not-real" }],
        CONTEXT,
      ),
    ).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// Edge cases
// ---------------------------------------------------------------------------

describe("validateWorkflowStepReferences — edge cases", () => {
  it("passes for an empty steps array", () => {
    expect(() => validateWorkflowStepReferences([], CONTEXT)).not.toThrow();
  });

  it("includes the context string in error messages", () => {
    const customContext = "workflow 'my-custom-flow'";
    expect(() =>
      validateWorkflowStepReferences([{ key: "review", type: "review" }], customContext),
    ).toThrow(customContext);
  });
});
