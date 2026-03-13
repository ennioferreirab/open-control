import { describe, expect, it } from "vitest";

import {
  interactiveSessionCapabilityValidator,
  interactiveSessionScopeKindValidator,
  interactiveSessionStatusValidator,
  taskFileMetadataValidator,
} from "./schema";

describe("taskFileMetadataValidator", () => {
  it("accepts restoredAt as an optional legacy field", () => {
    expect(taskFileMetadataValidator.kind).toBe("object");
    expect(taskFileMetadataValidator.fields.restoredAt?.kind).toBe("string");
    expect(taskFileMetadataValidator.fields.restoredAt?.isOptional).toBe("optional");
    expect(taskFileMetadataValidator.fields.uploadedAt.isOptional).toBe("required");
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
