import { describe, expect, it } from "vitest";
import {
  CANONICAL_PHASES,
  isCanonicalPhase,
  parseAuthoringResponse,
  type AgentGraphPatch,
  type AuthoringPhase,
  type AuthoringResponse,
} from "./authoringContract";

describe("authoringContract", () => {
  describe("CANONICAL_PHASES", () => {
    it("contains exactly the four canonical phases", () => {
      expect(CANONICAL_PHASES).toContain("discovery");
      expect(CANONICAL_PHASES).toContain("proposal");
      expect(CANONICAL_PHASES).toContain("refinement");
      expect(CANONICAL_PHASES).toContain("approval");
      expect(CANONICAL_PHASES).toHaveLength(4);
    });
  });

  describe("isCanonicalPhase", () => {
    it("returns true for valid phases", () => {
      const phases: AuthoringPhase[] = ["discovery", "proposal", "refinement", "approval"];
      for (const phase of phases) {
        expect(isCanonicalPhase(phase)).toBe(true);
      }
    });

    it("returns false for non-canonical phases", () => {
      expect(isCanonicalPhase("ideation")).toBe(false);
      expect(isCanonicalPhase("brainstorm")).toBe(false);
      expect(isCanonicalPhase("")).toBe(false);
      expect(isCanonicalPhase("team_design")).toBe(false);
    });
  });

  describe("parseAuthoringResponse - agent mode", () => {
    it("parses a valid agent authoring payload", () => {
      const raw = {
        assistant_message: "Here is your researcher agent.",
        phase: "proposal",
        draft_graph_patch: {
          agents: [{ key: "researcher", role: "Researcher" }],
        },
        unresolved_questions: ["What data sources?"],
        preview: {},
        readiness: 0.5,
        mode: "agent",
      };

      const result = parseAuthoringResponse<AgentGraphPatch>(raw);

      expect(result.assistantMessage).toBe("Here is your researcher agent.");
      expect(result.phase).toBe("proposal");
      expect(result.draftGraphPatch).toEqual({
        agents: [{ key: "researcher", role: "Researcher" }],
      });
      expect(result.unresolvedQuestions).toEqual(["What data sources?"]);
      expect(result.readiness).toBe(0.5);
    });

    it("maps snake_case backend keys to camelCase frontend keys", () => {
      const raw = {
        assistant_message: "Hello",
        phase: "discovery",
        draft_graph_patch: {},
        unresolved_questions: [],
        preview: { foo: "bar" },
        readiness: 0.0,
        mode: "agent",
      };

      const result = parseAuthoringResponse(raw);

      expect(result).toHaveProperty("assistantMessage");
      expect(result).toHaveProperty("phase");
      expect(result).toHaveProperty("draftGraphPatch");
      expect(result).toHaveProperty("unresolvedQuestions");
      expect(result).toHaveProperty("preview");
      expect(result).toHaveProperty("readiness");
    });
  });

  describe("parseAuthoringResponse - error handling", () => {
    it("throws when phase is not canonical", () => {
      const raw = {
        assistant_message: "msg",
        phase: "ideation",
        draft_graph_patch: {},
        unresolved_questions: [],
        preview: {},
        readiness: 0.0,
        mode: "agent",
      };

      expect(() => parseAuthoringResponse(raw)).toThrow();
    });

    it("throws when assistant_message is missing", () => {
      const raw = {
        phase: "discovery",
        draft_graph_patch: {},
        unresolved_questions: [],
        preview: {},
        readiness: 0.0,
        mode: "agent",
      };

      expect(() => parseAuthoringResponse(raw)).toThrow();
    });
  });

  describe("TypeScript types", () => {
    it("AuthoringResponse is correctly typed", () => {
      const resp: AuthoringResponse<AgentGraphPatch> = {
        assistantMessage: "test",
        phase: "discovery",
        draftGraphPatch: { agents: [] },
        unresolvedQuestions: [],
        preview: {},
        readiness: 0,
      };
      expect(resp.phase).toBe("discovery");
    });
  });
});
