import { describe, expect, it } from "vitest";

import {
  classifyProviderEventCategory,
  buildProviderLiveEvent,
  buildProviderLiveEvents,
  SKILL_TOOL_NAMES,
} from "./providerLiveEvents";

describe("classifyProviderEventCategory", () => {
  it("classifies item_started with toolName as tool", () => {
    expect(classifyProviderEventCategory({ kind: "item_started", toolName: "Read" })).toBe("tool");
  });

  it("classifies item_started with skill toolName as skill", () => {
    for (const name of SKILL_TOOL_NAMES) {
      expect(classifyProviderEventCategory({ kind: "item_started", toolName: name })).toBe("skill");
    }
  });

  it("classifies item_completed as result", () => {
    expect(classifyProviderEventCategory({ kind: "item_completed" })).toBe("result");
  });

  it("classifies turn_completed as result", () => {
    expect(classifyProviderEventCategory({ kind: "turn_completed" })).toBe("result");
  });

  it("classifies approval_requested as action", () => {
    expect(classifyProviderEventCategory({ kind: "approval_requested" })).toBe("action");
  });

  it("classifies user_input_requested as action", () => {
    expect(classifyProviderEventCategory({ kind: "user_input_requested" })).toBe("action");
  });

  it("classifies ask_user_requested as action", () => {
    expect(classifyProviderEventCategory({ kind: "ask_user_requested" })).toBe("action");
  });

  it("classifies paused_for_review as action", () => {
    expect(classifyProviderEventCategory({ kind: "paused_for_review" })).toBe("action");
  });

  it("classifies session_failed as error", () => {
    expect(classifyProviderEventCategory({ kind: "session_failed" })).toBe("error");
  });

  it("classifies session_started as system", () => {
    expect(classifyProviderEventCategory({ kind: "session_started" })).toBe("system");
  });

  it("classifies session_ready as system", () => {
    expect(classifyProviderEventCategory({ kind: "session_ready" })).toBe("system");
  });

  it("classifies session_stopped as system", () => {
    expect(classifyProviderEventCategory({ kind: "session_stopped" })).toBe("system");
  });

  it("classifies turn_started as system", () => {
    expect(classifyProviderEventCategory({ kind: "turn_started" })).toBe("system");
  });

  it("classifies turn_updated as system", () => {
    expect(classifyProviderEventCategory({ kind: "turn_updated" })).toBe("system");
  });

  it("falls back to text for unknown kind", () => {
    expect(classifyProviderEventCategory({ kind: "something_unknown" })).toBe("text");
  });

  it("falls back to text when kind is missing", () => {
    expect(classifyProviderEventCategory({ kind: "" })).toBe("text");
  });
});

describe("buildProviderLiveEvent", () => {
  it("builds a structured result event from turn_completed", () => {
    const event = buildProviderLiveEvent({
      _id: "evt-1",
      kind: "turn_completed",
      ts: "2026-03-15T10:00:00.000Z",
      summary: "Implemented the fix",
    });

    expect(event).toMatchObject({
      id: "evt-1",
      kind: "turn_completed",
      category: "result",
      body: "Implemented the fix",
      timestamp: "2026-03-15T10:00:00.000Z",
      requiresAction: false,
    });
  });

  it("builds a structured tool event from item_started with toolName", () => {
    const event = buildProviderLiveEvent({
      _id: "evt-2",
      kind: "item_started",
      ts: "2026-03-15T10:01:00.000Z",
      toolName: "Read",
      toolInput: "/tmp/file.txt",
    });

    expect(event).toMatchObject({
      id: "evt-2",
      kind: "item_started",
      category: "tool",
      title: "Read",
      toolName: "Read",
      toolInput: "/tmp/file.txt",
      requiresAction: false,
    });
  });

  it("builds a structured action event from approval_requested", () => {
    const event = buildProviderLiveEvent({
      _id: "evt-3",
      kind: "approval_requested",
      ts: "2026-03-15T10:02:00.000Z",
      summary: "Need permission to run tests",
      requiresAction: true,
    });

    expect(event).toMatchObject({
      id: "evt-3",
      kind: "approval_requested",
      category: "action",
      body: "Need permission to run tests",
      requiresAction: true,
    });
  });

  it("builds a structured error event from session_failed", () => {
    const event = buildProviderLiveEvent({
      _id: "evt-4",
      kind: "session_failed",
      ts: "2026-03-15T10:03:00.000Z",
      error: "Connection timed out",
    });

    expect(event).toMatchObject({
      id: "evt-4",
      kind: "session_failed",
      category: "error",
      body: "Connection timed out",
    });
  });

  it("falls back to empty body safely when no summary/error/toolName", () => {
    const event = buildProviderLiveEvent({
      _id: "evt-5",
      kind: "session_ready",
      ts: "2026-03-15T10:04:00.000Z",
    });

    expect(event).toMatchObject({
      id: "evt-5",
      category: "system",
      body: "",
    });
  });
});

describe("buildProviderLiveEvents", () => {
  it("maps multiple raw entries into structured events", () => {
    const events = buildProviderLiveEvents([
      {
        _id: "a",
        kind: "session_ready",
        ts: "2026-03-15T10:00:00.000Z",
      },
      {
        _id: "b",
        kind: "turn_completed",
        ts: "2026-03-15T10:01:00.000Z",
        summary: "Done",
      },
    ]);

    expect(events).toHaveLength(2);
    expect(events[0].category).toBe("system");
    expect(events[1].category).toBe("result");
  });

  it("returns an empty array for empty input", () => {
    expect(buildProviderLiveEvents([])).toEqual([]);
  });
});
