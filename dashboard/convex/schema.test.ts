import { describe, expect, it } from "vitest";

import {
  interactiveSessionCapabilityValidator,
  interactiveSessionScopeKindValidator,
  interactiveSessionStatusValidator,
  reviewScopeValidator,
  routingModeValidator,
  specStatusValidator,
  taskFileMetadataValidator,
  workModeValidator,
  workflowStepTypeValidator,
} from "./schema";

describe("taskFileMetadataValidator", () => {
  it("accepts restoredAt as an optional legacy field", () => {
    expect(taskFileMetadataValidator.kind).toBe("object");
    expect(taskFileMetadataValidator.fields.restoredAt?.kind).toBe("string");
    expect(taskFileMetadataValidator.fields.restoredAt?.isOptional).toBe("optional");
    expect(taskFileMetadataValidator.fields.uploadedAt.isOptional).toBe("required");
  });
});

describe("spec status validator", () => {
  it("defines draft, published, and archived as valid spec statuses", () => {
    expect(specStatusValidator.kind).toBe("union");
    expect(specStatusValidator.members).toHaveLength(3);
    expect(specStatusValidator.members.map((m: { value?: string }) => m.value)).toEqual([
      "draft",
      "published",
      "archived",
    ]);
  });
});

describe("reviewScopeValidator", () => {
  it("defines agent, workflow, and execution as valid review scopes", () => {
    expect(reviewScopeValidator.kind).toBe("union");
    expect(reviewScopeValidator.members).toHaveLength(3);
    expect(reviewScopeValidator.members.map((m: { value?: string }) => m.value)).toEqual([
      "agent",
      "workflow",
      "execution",
    ]);
  });
});

describe("workflowStepTypeValidator", () => {
  it("defines 4 step types for workflow specs", () => {
    expect(workflowStepTypeValidator.kind).toBe("union");
    expect(workflowStepTypeValidator.members).toHaveLength(4);
    expect(workflowStepTypeValidator.members.map((m: { value?: string }) => m.value)).toEqual([
      "agent",
      "human",
      "review",
      "system",
    ]);
  });
});

describe("workModeValidator", () => {
  it("defines direct_delegate and ai_workflow as task work modes", () => {
    expect(workModeValidator.kind).toBe("union");
    expect(workModeValidator.members).toHaveLength(2);
    expect(workModeValidator.members.map((m: { value?: string }) => m.value)).toEqual([
      "direct_delegate",
      "ai_workflow",
    ]);
  });
});

describe("routingModeValidator", () => {
  it("keeps legacy lead_agent readable during rollout while writing orchestrator_agent going forward", () => {
    expect(routingModeValidator.kind).toBe("union");
    expect(routingModeValidator.members).toHaveLength(4);
    expect(routingModeValidator.members.map((m: { value?: string }) => m.value)).toEqual([
      "lead_agent",
      "orchestrator_agent",
      "workflow",
      "human",
    ]);
  });
});

describe("interactive session validators", () => {
  it("defines the supported interactive session status values", () => {
    expect(interactiveSessionStatusValidator.kind).toBe("union");
    expect(interactiveSessionStatusValidator.members).toHaveLength(5);
  });

  it("defines a narrow scope kind contract for interactive sessions", () => {
    expect(interactiveSessionScopeKindValidator.kind).toBe("union");
    expect(interactiveSessionScopeKindValidator.members).toHaveLength(3);
  });

  it("defines capability values separately from terminal session transport", () => {
    expect(interactiveSessionCapabilityValidator.kind).toBe("union");
    expect(interactiveSessionCapabilityValidator.members).toHaveLength(5);
    expect(
      interactiveSessionCapabilityValidator.members.map(
        (member: { value?: string }) => member.value,
      ),
    ).toEqual(["tui", "autocomplete", "interactive-prompts", "commands", "mcp-tools"]);
  });
});
