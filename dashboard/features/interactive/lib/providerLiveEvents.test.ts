import { describe, expect, it } from "vitest";

import {
  classifyProviderEventCategory,
  buildProviderLiveEvent,
  buildProviderLiveEvents,
  buildGroupedTimeline,
  SKILL_TOOL_NAMES,
  type ProviderLiveEvent,
} from "./providerLiveEvents";

function makeEvent(overrides: Partial<ProviderLiveEvent> = {}): ProviderLiveEvent {
  return {
    id: "evt-default",
    kind: "text",
    category: "text",
    title: "Response",
    body: "test body",
    timestamp: "2026-03-18T10:00:00.000Z",
    requiresAction: false,
    ...overrides,
  };
}

describe("classifyProviderEventCategory", () => {
  it("classifies tool_use as tool", () => {
    expect(classifyProviderEventCategory({ kind: "tool_use", toolName: "WebSearch" })).toBe("tool");
  });

  it("classifies session_id as system", () => {
    expect(classifyProviderEventCategory({ kind: "session_id" })).toBe("system");
  });

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
      body: "",
      toolName: "Read",
      toolInput: "/tmp/file.txt",
      requiresAction: false,
    });
  });

  it("builds a structured session id event", () => {
    const event = buildProviderLiveEvent({
      _id: "evt-session",
      kind: "session_id",
      ts: "2026-03-15T10:01:00.000Z",
      summary: "c8332f85-b01e-46a4-a6e4-6443f0ee75ab",
    });

    expect(event).toMatchObject({
      id: "evt-session",
      category: "system",
      title: "Session ID",
      body: "c8332f85-b01e-46a4-a6e4-6443f0ee75ab",
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

describe("canonical metadata support (Story 2.1)", () => {
  it("classifies by sourceType when present, bypassing heuristic path", () => {
    expect(
      classifyProviderEventCategory({ kind: "text", toolName: undefined, sourceType: "assistant" }),
    ).toBe("text");
    expect(
      classifyProviderEventCategory({ kind: "text", toolName: undefined, sourceType: "result" }),
    ).toBe("result");
    expect(
      classifyProviderEventCategory({ kind: "text", toolName: undefined, sourceType: "system" }),
    ).toBe("system");
    expect(
      classifyProviderEventCategory({ kind: "text", toolName: undefined, sourceType: "tool_use" }),
    ).toBe("tool");
    expect(
      classifyProviderEventCategory({ kind: "text", toolName: undefined, sourceType: "error" }),
    ).toBe("error");
  });

  it("classifies tool_use sourceType with skill toolName as skill", () => {
    expect(
      classifyProviderEventCategory({ kind: "text", toolName: "dispatch_agent", sourceType: "tool_use" }),
    ).toBe("skill");
  });

  it("falls through to heuristic when sourceType is not recognized", () => {
    expect(
      classifyProviderEventCategory({ kind: "turn_completed", toolName: undefined, sourceType: "unknown_future" }),
    ).toBe("result");
  });

  it("falls through to heuristic when sourceType is undefined", () => {
    expect(
      classifyProviderEventCategory({ kind: "error", toolName: undefined, sourceType: undefined }),
    ).toBe("error");
  });

  it("propagates canonical fields through buildProviderLiveEvent", () => {
    const event = buildProviderLiveEvent({
      _id: "evt-canonical",
      kind: "tool_use",
      ts: "2026-03-18T10:00:00.000Z",
      toolName: "Read",
      sourceType: "tool_use",
      sourceSubtype: "Read",
      groupKey: "turn-abc",
      rawText: "Read /src/index.ts",
      rawJson: '{"path":"/src/index.ts"}',
    });

    expect(event.sourceType).toBe("tool_use");
    expect(event.sourceSubtype).toBe("Read");
    expect(event.groupKey).toBe("turn-abc");
    expect(event.rawText).toBe("Read /src/index.ts");
    expect(event.rawJson).toBe('{"path":"/src/index.ts"}');
  });

  it("prefers rawText over summary for body when both present", () => {
    const event = buildProviderLiveEvent({
      _id: "evt-raw",
      kind: "text",
      ts: "2026-03-18T10:00:00.000Z",
      summary: "legacy summary",
      rawText: "canonical raw text",
      sourceType: "assistant",
    });

    expect(event.body).toBe("canonical raw text");
  });

  it("falls back to summary when rawText is not present (legacy row)", () => {
    const event = buildProviderLiveEvent({
      _id: "evt-legacy",
      kind: "text",
      ts: "2026-03-18T10:00:00.000Z",
      summary: "legacy summary",
    });

    expect(event.body).toBe("legacy summary");
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

  it("filters machine-payload text noise from the live stream", () => {
    const events = buildProviderLiveEvents([
      {
        _id: "machine-1",
        kind: "text",
        ts: "2026-03-15T10:00:00.000Z",
        summary:
          '{"type":"rate_limit_event","rate_limit_info":{"status":"allowed"},"session_id":"abc"}',
      },
      {
        _id: "human-1",
        kind: "text",
        ts: "2026-03-15T10:01:00.000Z",
        summary: "Readable response from the agent.",
      },
    ]);

    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({
      id: "human-1",
      category: "text",
      body: "Readable response from the agent.",
    });
  });

  it("drops duplicate text that is immediately superseded by a matching result event", () => {
    const duplicateBody = "Compound interest grows because interest earns interest.";
    const events = buildProviderLiveEvents([
      {
        _id: "text-1",
        kind: "text",
        ts: "2026-03-15T10:00:00.000Z",
        summary: duplicateBody,
      },
      {
        _id: "result-1",
        kind: "result",
        ts: "2026-03-15T10:01:00.000Z",
        summary: duplicateBody,
      },
    ]);

    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({
      id: "result-1",
      category: "result",
      body: duplicateBody,
    });
  });
});

describe("buildGroupedTimeline", () => {
  it("returns empty array for empty input", () => {
    expect(buildGroupedTimeline([])).toEqual([]);
  });

  it("groups consecutive events with the same groupKey", () => {
    const events: ProviderLiveEvent[] = [
      makeEvent({ id: "e1", groupKey: "turn-1", category: "system" }),
      makeEvent({ id: "e2", groupKey: "turn-1", category: "tool" }),
      makeEvent({ id: "e3", groupKey: "turn-1", category: "result" }),
    ];
    const nodes = buildGroupedTimeline(events);
    expect(nodes).toHaveLength(1);
    expect(nodes[0].isGroup).toBe(true);
    expect(nodes[0].events).toHaveLength(3);
    expect(nodes[0].groupKey).toBe("turn-1");
  });

  it("uses first non-system category as primaryCategory", () => {
    const events: ProviderLiveEvent[] = [
      makeEvent({ id: "e1", groupKey: "turn-1", category: "system" }),
      makeEvent({ id: "e2", groupKey: "turn-1", category: "tool" }),
    ];
    const nodes = buildGroupedTimeline(events);
    expect(nodes[0].primaryCategory).toBe("tool");
  });

  it("renders events without groupKey as standalone nodes", () => {
    const events: ProviderLiveEvent[] = [
      makeEvent({ id: "e1" }),
      makeEvent({ id: "e2" }),
    ];
    const nodes = buildGroupedTimeline(events);
    expect(nodes).toHaveLength(2);
    expect(nodes[0].isGroup).toBe(false);
    expect(nodes[1].isGroup).toBe(false);
  });

  it("breaks groups when a different groupKey appears", () => {
    const events: ProviderLiveEvent[] = [
      makeEvent({ id: "e1", groupKey: "turn-1", category: "tool" }),
      makeEvent({ id: "e2", groupKey: "turn-2", category: "tool" }),
      makeEvent({ id: "e3", groupKey: "turn-1", category: "result" }),
    ];
    const nodes = buildGroupedTimeline(events);
    expect(nodes).toHaveLength(3);
    expect(nodes[0].groupKey).toBe("turn-1");
    expect(nodes[1].groupKey).toBe("turn-2");
    expect(nodes[2].groupKey).toBe("turn-1");
  });

  it("handles mixed grouped and standalone events in chronological order", () => {
    const events: ProviderLiveEvent[] = [
      makeEvent({ id: "e1", groupKey: "turn-1", category: "system" }),
      makeEvent({ id: "e2", groupKey: "turn-1", category: "tool" }),
      makeEvent({ id: "e3" }), // standalone
      makeEvent({ id: "e4", groupKey: "turn-2", category: "result" }),
    ];
    const nodes = buildGroupedTimeline(events);
    expect(nodes).toHaveLength(3);
    expect(nodes[0].isGroup).toBe(true);
    expect(nodes[0].events).toHaveLength(2);
    expect(nodes[1].isGroup).toBe(false);
    expect(nodes[2].isGroup).toBe(false); // single-event group is not a group
  });

  it("treats a single event with groupKey as a non-group node", () => {
    const events: ProviderLiveEvent[] = [
      makeEvent({ id: "e1", groupKey: "turn-1", category: "tool" }),
    ];
    const nodes = buildGroupedTimeline(events);
    expect(nodes).toHaveLength(1);
    expect(nodes[0].isGroup).toBe(false);
    expect(nodes[0].groupKey).toBe("turn-1");
  });
});
