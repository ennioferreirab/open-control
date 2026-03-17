import { describe, expect, it } from "vitest";

import {
  isValidTransition,
  getAllowedTransitions,
  getUniversalTransitions,
  isValidStepTransition,
  getStepAllowedTransitions,
  isMentionSafe,
  getTaskTransitionEvent,
  getStepTransitionEvent,
  TASK_STATUSES,
  STEP_STATUSES,
  THREAD_MESSAGE_TYPES,
} from "./workflowContract";

// ---------------------------------------------------------------------------
// Status constants
// ---------------------------------------------------------------------------

describe("TASK_STATUSES", () => {
  it("contains all expected task statuses", () => {
    const expected = [
      "planning",
      "ready",
      "failed",
      "inbox",
      "assigned",
      "in_progress",
      "review",
      "done",
      "retrying",
      "crashed",
    ];
    for (const s of expected) {
      expect(TASK_STATUSES).toContain(s);
    }
  });

  it("has exactly 11 statuses", () => {
    expect(TASK_STATUSES).toHaveLength(11);
  });
});

describe("STEP_STATUSES", () => {
  it("contains all expected step statuses", () => {
    const expected = [
      "planned",
      "assigned",
      "running",
      "review",
      "completed",
      "crashed",
      "blocked",
      "waiting_human",
      "deleted",
    ];
    for (const s of expected) {
      expect(STEP_STATUSES).toContain(s);
    }
  });

  it("has exactly 9 statuses", () => {
    expect(STEP_STATUSES).toHaveLength(9);
  });
});

describe("THREAD_MESSAGE_TYPES", () => {
  it("contains expected thread message types", () => {
    expect(THREAD_MESSAGE_TYPES).toContain("step_completion");
    expect(THREAD_MESSAGE_TYPES).toContain("user_message");
    expect(THREAD_MESSAGE_TYPES).toContain("system_error");
    expect(THREAD_MESSAGE_TYPES).toContain("lead_agent_plan");
    expect(THREAD_MESSAGE_TYPES).toContain("lead_agent_chat");
  });
});

// ---------------------------------------------------------------------------
// isValidTransition (task)
// ---------------------------------------------------------------------------

describe("isValidTransition", () => {
  it("allows inbox -> assigned", () => {
    expect(isValidTransition("inbox", "assigned")).toBe(true);
  });

  it("allows assigned -> in_progress", () => {
    expect(isValidTransition("assigned", "in_progress")).toBe(true);
  });

  it("allows in_progress -> review", () => {
    expect(isValidTransition("in_progress", "review")).toBe(true);
  });

  it("allows in_progress -> done", () => {
    expect(isValidTransition("in_progress", "done")).toBe(true);
  });

  it("allows review -> done", () => {
    expect(isValidTransition("review", "done")).toBe(true);
  });

  it("allows review -> inbox", () => {
    expect(isValidTransition("review", "inbox")).toBe(true);
  });

  it("allows review -> in_progress", () => {
    expect(isValidTransition("review", "in_progress")).toBe(true);
  });

  it("allows crashed -> inbox", () => {
    expect(isValidTransition("crashed", "inbox")).toBe(true);
  });

  it("allows crashed -> assigned", () => {
    expect(isValidTransition("crashed", "assigned")).toBe(true);
  });

  it("allows done -> assigned", () => {
    expect(isValidTransition("done", "assigned")).toBe(true);
  });

  it("allows planning -> review", () => {
    expect(isValidTransition("planning", "review")).toBe(true);
  });

  it("allows planning -> failed", () => {
    expect(isValidTransition("planning", "failed")).toBe(true);
  });

  it("allows planning -> ready", () => {
    expect(isValidTransition("planning", "ready")).toBe(true);
  });

  it("allows planning -> in_progress", () => {
    expect(isValidTransition("planning", "in_progress")).toBe(true);
  });

  it("allows inbox -> planning", () => {
    expect(isValidTransition("inbox", "planning")).toBe(true);
  });

  // Universal targets
  it("allows any -> retrying (universal)", () => {
    for (const status of TASK_STATUSES) {
      expect(isValidTransition(status, "retrying")).toBe(true);
    }
  });

  it("allows any -> crashed (universal)", () => {
    for (const status of TASK_STATUSES) {
      expect(isValidTransition(status, "crashed")).toBe(true);
    }
  });

  it("allows any -> deleted (universal)", () => {
    for (const status of TASK_STATUSES) {
      expect(isValidTransition(status, "deleted")).toBe(true);
    }
  });

  // Invalid transitions
  it("rejects inbox -> done", () => {
    expect(isValidTransition("inbox", "done")).toBe(false);
  });

  it("rejects inbox -> in_progress", () => {
    expect(isValidTransition("inbox", "in_progress")).toBe(false);
  });

  it("rejects unknown status", () => {
    expect(isValidTransition("nonexistent", "assigned")).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// getAllowedTransitions
// ---------------------------------------------------------------------------

describe("getAllowedTransitions", () => {
  it("returns allowed transitions for inbox", () => {
    const allowed = getAllowedTransitions("inbox");
    expect(allowed).toContain("assigned");
    expect(allowed).toContain("planning");
  });

  it("returns allowed transitions for assigned", () => {
    const allowed = getAllowedTransitions("assigned");
    expect(allowed).toContain("in_progress");
  });

  it("returns empty for unknown status", () => {
    expect(getAllowedTransitions("nonexistent")).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// getUniversalTransitions
// ---------------------------------------------------------------------------

describe("getUniversalTransitions", () => {
  it("contains retrying", () => {
    expect(getUniversalTransitions()).toContain("retrying");
  });

  it("contains crashed", () => {
    expect(getUniversalTransitions()).toContain("crashed");
  });

  it("contains deleted", () => {
    expect(getUniversalTransitions()).toContain("deleted");
  });
});

// ---------------------------------------------------------------------------
// getTaskTransitionEvent
// ---------------------------------------------------------------------------

describe("getTaskTransitionEvent", () => {
  it("returns task_assigned for inbox->assigned", () => {
    expect(getTaskTransitionEvent("inbox", "assigned")).toBe("task_assigned");
  });

  it("returns task_started for assigned->in_progress", () => {
    expect(getTaskTransitionEvent("assigned", "in_progress")).toBe("task_started");
  });

  it("returns review_requested for in_progress->review", () => {
    expect(getTaskTransitionEvent("in_progress", "review")).toBe("review_requested");
  });

  it("returns task_retrying for universal retrying target", () => {
    expect(getTaskTransitionEvent("in_progress", "retrying")).toBe("task_retrying");
  });

  it("returns task_crashed for universal crashed target", () => {
    expect(getTaskTransitionEvent("assigned", "crashed")).toBe("task_crashed");
  });

  it("returns undefined for unmapped transition", () => {
    expect(getTaskTransitionEvent("done", "inbox")).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// isValidStepTransition
// ---------------------------------------------------------------------------

describe("isValidStepTransition", () => {
  it("allows planned -> assigned", () => {
    expect(isValidStepTransition("planned", "assigned")).toBe(true);
  });

  it("allows planned -> blocked", () => {
    expect(isValidStepTransition("planned", "blocked")).toBe(true);
  });

  it("allows assigned -> running", () => {
    expect(isValidStepTransition("assigned", "running")).toBe(true);
  });

  it("allows assigned -> completed", () => {
    expect(isValidStepTransition("assigned", "completed")).toBe(true);
  });

  it("allows assigned -> crashed", () => {
    expect(isValidStepTransition("assigned", "crashed")).toBe(true);
  });

  it("allows assigned -> blocked", () => {
    expect(isValidStepTransition("assigned", "blocked")).toBe(true);
  });

  it("allows assigned -> waiting_human", () => {
    expect(isValidStepTransition("assigned", "waiting_human")).toBe(true);
  });

  it("allows assigned -> review", () => {
    expect(isValidStepTransition("assigned", "review")).toBe(true);
  });

  it("allows running -> completed", () => {
    expect(isValidStepTransition("running", "completed")).toBe(true);
  });

  it("allows running -> review", () => {
    expect(isValidStepTransition("running", "review")).toBe(true);
  });

  it("allows review -> running", () => {
    expect(isValidStepTransition("review", "running")).toBe(true);
  });

  it("allows review -> completed", () => {
    expect(isValidStepTransition("review", "completed")).toBe(true);
  });

  it("allows running -> crashed", () => {
    expect(isValidStepTransition("running", "crashed")).toBe(true);
  });

  it("allows review -> crashed", () => {
    expect(isValidStepTransition("review", "crashed")).toBe(true);
  });

  it("allows crashed -> assigned", () => {
    expect(isValidStepTransition("crashed", "assigned")).toBe(true);
  });

  it("allows blocked -> assigned", () => {
    expect(isValidStepTransition("blocked", "assigned")).toBe(true);
  });

  it("allows waiting_human -> completed", () => {
    expect(isValidStepTransition("waiting_human", "completed")).toBe(true);
  });

  it("allows waiting_human -> crashed", () => {
    expect(isValidStepTransition("waiting_human", "crashed")).toBe(true);
  });

  // Invalid
  it("rejects completed -> running", () => {
    expect(isValidStepTransition("completed", "running")).toBe(false);
  });

  it("rejects running -> planned", () => {
    expect(isValidStepTransition("running", "planned")).toBe(false);
  });

  it("rejects unknown step status", () => {
    expect(isValidStepTransition("nonexistent", "assigned")).toBe(false);
  });

  it("completed has no transitions", () => {
    for (const s of STEP_STATUSES) {
      if (s === "completed") continue;
      expect(isValidStepTransition("completed", s)).toBe(false);
    }
  });
});

// ---------------------------------------------------------------------------
// getStepAllowedTransitions
// ---------------------------------------------------------------------------

describe("getStepAllowedTransitions", () => {
  it("returns correct transitions for planned", () => {
    expect(new Set(getStepAllowedTransitions("planned"))).toEqual(new Set(["assigned", "blocked"]));
  });

  it("returns empty for completed", () => {
    expect(getStepAllowedTransitions("completed")).toEqual([]);
  });

  it("returns empty for deleted", () => {
    expect(getStepAllowedTransitions("deleted")).toEqual([]);
  });

  it("returns empty for unknown status", () => {
    expect(getStepAllowedTransitions("nonexistent")).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// getStepTransitionEvent
// ---------------------------------------------------------------------------

describe("getStepTransitionEvent", () => {
  it("returns step_dispatched for planned->assigned", () => {
    expect(getStepTransitionEvent("planned", "assigned")).toBe("step_dispatched");
  });

  it("returns step_started for assigned->running", () => {
    expect(getStepTransitionEvent("assigned", "running")).toBe("step_started");
  });

  it("returns review_requested for running->review", () => {
    expect(getStepTransitionEvent("running", "review")).toBe("review_requested");
  });

  it("returns step_completed for running->completed", () => {
    expect(getStepTransitionEvent("running", "completed")).toBe("step_completed");
  });

  it("returns system_error for running->crashed", () => {
    expect(getStepTransitionEvent("running", "crashed")).toBe("system_error");
  });

  it("returns undefined for unmapped step transition", () => {
    expect(getStepTransitionEvent("completed", "running")).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// isMentionSafe
// ---------------------------------------------------------------------------

describe("isMentionSafe", () => {
  it("returns true for inbox", () => {
    expect(isMentionSafe("inbox")).toBe(true);
  });

  it("returns true for assigned", () => {
    expect(isMentionSafe("assigned")).toBe(true);
  });

  it("returns true for in_progress", () => {
    expect(isMentionSafe("in_progress")).toBe(true);
  });

  it("returns true for review", () => {
    expect(isMentionSafe("review")).toBe(true);
  });

  it("returns true for done", () => {
    expect(isMentionSafe("done")).toBe(true);
  });

  it("returns true for crashed", () => {
    expect(isMentionSafe("crashed")).toBe(true);
  });

  it("returns true for retrying", () => {
    expect(isMentionSafe("retrying")).toBe(true);
  });

  it("returns false for planning", () => {
    expect(isMentionSafe("planning")).toBe(false);
  });

  it("returns false for ready", () => {
    expect(isMentionSafe("ready")).toBe(false);
  });

  it("returns false for failed", () => {
    expect(isMentionSafe("failed")).toBe(false);
  });

  it("returns false for unknown status", () => {
    expect(isMentionSafe("nonexistent")).toBe(false);
  });
});
