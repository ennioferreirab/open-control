import { describe, expect, it } from "vitest";

import { selectProviderSessionStatus, normalizeProviderEvents } from "./useProviderSession";

describe("selectProviderSessionStatus", () => {
  it("returns loading when the session is undefined (still fetching)", () => {
    expect(selectProviderSessionStatus(undefined)).toBe("loading");
  });

  it("returns idle when there is no active session", () => {
    expect(selectProviderSessionStatus(null)).toBe("idle");
  });

  it("returns streaming for an attached active session", () => {
    expect(selectProviderSessionStatus("attached")).toBe("streaming");
  });

  it("returns streaming for a detached session that is still running", () => {
    expect(selectProviderSessionStatus("detached")).toBe("streaming");
  });

  it("returns completed for an ended session", () => {
    expect(selectProviderSessionStatus("ended")).toBe("completed");
  });

  it("returns error for an errored session", () => {
    expect(selectProviderSessionStatus("error")).toBe("error");
  });
});

describe("normalizeProviderEvents", () => {
  it("returns an empty array when there are no activity entries", () => {
    expect(normalizeProviderEvents([])).toEqual([]);
  });

  it("normalizes activity entries into structured live events", () => {
    const events = normalizeProviderEvents([
      {
        _id: "act-1",
        kind: "approval_requested",
        ts: "2026-03-15T10:00:00.000Z",
        summary: "Need permission to run tests",
        requiresAction: true,
      },
    ]);

    expect(events[0]).toMatchObject({
      id: "act-1",
      kind: "approval_requested",
      category: "action",
      body: "Need permission to run tests",
      requiresAction: true,
    });
  });

  it("includes category, body, toolName, toolInput fields", () => {
    const events = normalizeProviderEvents([
      {
        _id: "act-2",
        kind: "item_started",
        ts: "2026-03-15T10:01:00.000Z",
        toolName: "Read",
        toolInput: "/tmp/file.txt",
      },
    ]);

    expect(events[0]).toMatchObject({
      id: "act-2",
      category: "tool",
      toolName: "Read",
      toolInput: "/tmp/file.txt",
    });
  });

  it("classifies session_failed as error category", () => {
    const events = normalizeProviderEvents([
      {
        _id: "act-3",
        kind: "session_failed",
        ts: "2026-03-15T10:02:00.000Z",
        error: "Provider timed out",
      },
    ]);

    expect(events[0]).toMatchObject({
      id: "act-3",
      category: "error",
      body: "Provider timed out",
    });
  });

  it("falls back safely when summary, error, and toolName are all absent", () => {
    const events = normalizeProviderEvents([
      { _id: "act-4", kind: "session_ready", ts: "2026-03-15T10:03:00.000Z" },
    ]);

    expect(events[0]).toMatchObject({
      id: "act-4",
      category: "system",
      body: "",
    });
  });
});
