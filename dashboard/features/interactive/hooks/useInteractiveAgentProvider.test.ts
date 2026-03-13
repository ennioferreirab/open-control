import { describe, expect, it } from "vitest";

import { getInteractiveAgentProvider } from "./useInteractiveAgentProvider";

describe("getInteractiveAgentProvider", () => {
  it("prefers an explicit interactive provider contract", () => {
    expect(
      getInteractiveAgentProvider({
        interactiveProvider: "codex",
        model: "cc/claude-sonnet-4-6",
        claudeCodeOpts: undefined,
      }),
    ).toBe("codex");
  });

  it("keeps legacy Claude detection for existing agents", () => {
    expect(
      getInteractiveAgentProvider({
        interactiveProvider: undefined,
        model: "cc/claude-sonnet-4-6",
        claudeCodeOpts: undefined,
      }),
    ).toBe("claude-code");
  });

  it("detects OpenAI Codex model prefixes without UI branching changes", () => {
    expect(
      getInteractiveAgentProvider({
        interactiveProvider: undefined,
        model: "openai-codex/gpt-5.4",
        claudeCodeOpts: undefined,
      }),
    ).toBe("codex");
  });

  it("prefers Codex model detection over legacy Claude options", () => {
    expect(
      getInteractiveAgentProvider({
        interactiveProvider: undefined,
        model: "openai-codex/gpt-5.4",
        claudeCodeOpts: { permissionMode: "acceptEdits" },
      }),
    ).toBe("codex");
  });

  it("returns null for non-interactive agents", () => {
    expect(
      getInteractiveAgentProvider({
        interactiveProvider: undefined,
        model: "anthropic/claude-sonnet-4-6",
        claudeCodeOpts: undefined,
      }),
    ).toBeNull();
  });
});
