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

  it("maps activity entries to normalized events with id, text, and kind", () => {
    const events = normalizeProviderEvents([
      { _id: "act-1", kind: "text", summary: "Hello from provider" },
      { _id: "act-2", kind: "result", summary: "Step completed" },
    ]);

    expect(events).toHaveLength(2);
    expect(events[0]).toEqual({ id: "act-1", text: "Hello from provider", kind: "text" });
    expect(events[1]).toEqual({ id: "act-2", text: "Step completed", kind: "result" });
  });

  it("uses tool name and input when summary is missing", () => {
    const events = normalizeProviderEvents([
      { _id: "act-1", kind: "tool_use", toolName: "Read", toolInput: "/tmp/file.txt" },
    ]);

    expect(events[0].text).toBe("Read: /tmp/file.txt");
  });
});
