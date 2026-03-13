import { describe, expect, it } from "vitest";

import {
  compileAgentSpec,
  compilePromptFromSpec,
  compileSoulFromSpec,
  type AgentSpecInput,
} from "./specCompiler";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const minimalSpec: AgentSpecInput = {
  name: "code-reviewer",
  displayName: "Code Reviewer",
  role: "Senior Code Reviewer",
  responsibilities: ["Review pull requests", "Enforce code quality standards"],
  skills: ["git", "code-review"],
};

const fullSpec: AgentSpecInput = {
  name: "code-reviewer",
  displayName: "Code Reviewer",
  role: "Senior Code Reviewer",
  responsibilities: [
    "Review pull requests for code quality",
    "Enforce style guidelines",
    "Identify security vulnerabilities",
  ],
  nonGoals: ["Write new features", "Manage project timelines"],
  principles: ["Prioritize readability", "Be constructive not destructive"],
  voiceGuidance: "Be concise and actionable.",
  antiPatterns: ["nitpicking trivial style issues", "approving unclear logic"],
  outputContract: "Return structured review with verdict and line-level comments.",
  toolPolicy: "Use only code analysis tools; do not execute arbitrary commands.",
  memoryPolicy: "Keep summaries of recurring issues per project.",
  skills: ["git", "code-review", "static-analysis"],
  model: "claude-sonnet-4-6",
  soul: "You care deeply about engineering quality and helping teams grow.",
};

// ---------------------------------------------------------------------------
// compilePromptFromSpec
// ---------------------------------------------------------------------------

describe("compilePromptFromSpec", () => {
  it("includes the role in the compiled prompt", () => {
    const prompt = compilePromptFromSpec(minimalSpec);
    expect(prompt).toContain("Senior Code Reviewer");
  });

  it("includes responsibilities in the compiled prompt", () => {
    const prompt = compilePromptFromSpec(fullSpec);
    expect(prompt).toContain("Review pull requests for code quality");
    expect(prompt).toContain("Enforce style guidelines");
  });

  it("includes non-goals when present", () => {
    const prompt = compilePromptFromSpec(fullSpec);
    expect(prompt).toContain("Write new features");
    expect(prompt).toContain("Manage project timelines");
  });

  it("includes voice guidance when present", () => {
    const prompt = compilePromptFromSpec(fullSpec);
    expect(prompt).toContain("Be concise and actionable.");
  });

  it("includes anti-patterns when present", () => {
    const prompt = compilePromptFromSpec(fullSpec);
    expect(prompt).toContain("nitpicking trivial style issues");
  });

  it("includes output contract when present", () => {
    const prompt = compilePromptFromSpec(fullSpec);
    expect(prompt).toContain("structured review with verdict");
  });

  it("includes tool policy when present", () => {
    const prompt = compilePromptFromSpec(fullSpec);
    expect(prompt).toContain("code analysis tools");
  });

  it("includes memory policy when present", () => {
    const prompt = compilePromptFromSpec(fullSpec);
    expect(prompt).toContain("summaries of recurring issues");
  });

  it("produces a non-empty prompt from minimal spec", () => {
    const prompt = compilePromptFromSpec(minimalSpec);
    expect(prompt.trim().length).toBeGreaterThan(0);
  });

  it("does not include undefined sections as empty lines", () => {
    const prompt = compilePromptFromSpec(minimalSpec);
    // Should not have consecutive blank lines or 'undefined'
    expect(prompt).not.toContain("undefined");
  });
});

// ---------------------------------------------------------------------------
// compileSoulFromSpec
// ---------------------------------------------------------------------------

describe("compileSoulFromSpec", () => {
  it("returns the explicit soul string when provided", () => {
    const soul = compileSoulFromSpec(fullSpec);
    expect(soul).toBe("You care deeply about engineering quality and helping teams grow.");
  });

  it("generates a default soul from role when no soul is provided", () => {
    const soul = compileSoulFromSpec(minimalSpec);
    expect(soul).toBeTruthy();
    expect(soul).toContain("Senior Code Reviewer");
  });
});

// ---------------------------------------------------------------------------
// compileAgentSpec
// ---------------------------------------------------------------------------

describe("compileAgentSpec", () => {
  it("returns a runtime payload with the expected shape", () => {
    const result = compileAgentSpec(minimalSpec, "spec-id-123", 1);
    expect(result).toHaveProperty("name");
    expect(result).toHaveProperty("displayName");
    expect(result).toHaveProperty("role");
    expect(result).toHaveProperty("prompt");
    expect(result).toHaveProperty("soul");
    expect(result).toHaveProperty("skills");
    expect(result).toHaveProperty("compiledFromSpecId");
    expect(result).toHaveProperty("compiledFromVersion");
    expect(result).toHaveProperty("compiledAt");
  });

  it("sets compiledFromSpecId from the passed spec id", () => {
    const result = compileAgentSpec(minimalSpec, "spec-abc", 2);
    expect(result.compiledFromSpecId).toBe("spec-abc");
  });

  it("sets compiledFromVersion from the passed version number", () => {
    const result = compileAgentSpec(minimalSpec, "spec-abc", 7);
    expect(result.compiledFromVersion).toBe(7);
  });

  it("sets compiledAt to a valid ISO 8601 timestamp when not provided", () => {
    const result = compileAgentSpec(minimalSpec, "spec-abc", 1);
    expect(() => new Date(result.compiledAt).toISOString()).not.toThrow();
  });

  it("uses the provided compiledAt timestamp for deterministic output", () => {
    const fixedTimestamp = "2026-01-15T12:00:00.000Z";
    const result = compileAgentSpec(minimalSpec, "spec-abc", 1, fixedTimestamp);
    expect(result.compiledAt).toBe(fixedTimestamp);
  });

  it("falls back to current time when compiledAt is not provided", () => {
    const before = Date.now();
    const result = compileAgentSpec(minimalSpec, "spec-abc", 1);
    const after = Date.now();
    const compiledAtMs = new Date(result.compiledAt).getTime();
    expect(compiledAtMs).toBeGreaterThanOrEqual(before);
    expect(compiledAtMs).toBeLessThanOrEqual(after);
  });

  it("carries over name and displayName from spec", () => {
    const result = compileAgentSpec(fullSpec, "spec-id", 1);
    expect(result.name).toBe("code-reviewer");
    expect(result.displayName).toBe("Code Reviewer");
  });

  it("carries over model from spec when present", () => {
    const result = compileAgentSpec(fullSpec, "spec-id", 1);
    expect(result.model).toBe("claude-sonnet-4-6");
  });

  it("carries over skills from spec", () => {
    const result = compileAgentSpec(fullSpec, "spec-id", 1);
    expect(result.skills).toEqual(["git", "code-review", "static-analysis"]);
  });

  it("does not include authoring-only fields like responsibilities in the result", () => {
    const result = compileAgentSpec(fullSpec, "spec-id", 1) as Record<string, unknown>;
    // responsibilities, nonGoals, principles, etc. should not be in the projection
    expect(result.responsibilities).toBeUndefined();
    expect(result.nonGoals).toBeUndefined();
    expect(result.principles).toBeUndefined();
    expect(result.antiPatterns).toBeUndefined();
    expect(result.outputContract).toBeUndefined();
    expect(result.toolPolicy).toBeUndefined();
    expect(result.memoryPolicy).toBeUndefined();
    expect(result.voiceGuidance).toBeUndefined();
  });

  it("compiles a non-empty prompt from the spec", () => {
    const result = compileAgentSpec(fullSpec, "spec-id", 1);
    expect(result.prompt.trim().length).toBeGreaterThan(0);
  });

  it("compiles a non-empty soul from the spec", () => {
    const result = compileAgentSpec(fullSpec, "spec-id", 1);
    expect(result.soul.trim().length).toBeGreaterThan(0);
  });
});
