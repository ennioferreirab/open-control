import { afterEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";

import {
  normalizeProviderEvents,
  selectProviderSessionStatus,
  useProviderSession,
} from "./useProviderSession";

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
        seq: 1,
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
        seq: 2,
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
        seq: 3,
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
      { _id: "act-4", seq: 4, kind: "session_ready", ts: "2026-03-15T10:03:00.000Z" },
    ]);

    expect(events[0]).toMatchObject({
      id: "act-4",
      category: "system",
      body: "",
    });
  });
});

describe("useProviderSession", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("treats a missing transcript as an empty event list without crashing", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: "Transcript not found" }), { status: 404 }),
    );

    const { result } = renderHook(() =>
      useProviderSession({
        sessionId: "session-1",
        agentName: "agent-alpha",
        provider: "claude-code",
        status: "attached",
      } as never),
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.events).toEqual([]);
    expect(result.current.groupedTimeline).toEqual([]);
    expect(result.current.status).toBe("streaming");
  });

  it("skips network requests when session metadata says there is no transcript", async () => {
    const fetchSpy = vi.spyOn(global, "fetch");

    const { result } = renderHook(() =>
      useProviderSession({
        sessionId: "session-no-live",
        agentName: "agent-alpha",
        provider: "claude-code",
        status: "attached",
        hasLiveTranscript: false,
      } as never),
    );

    await act(async () => {
      await Promise.resolve();
    });

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.events).toEqual([]);
  });

  it("stops polling after the transcript events endpoint returns 404", async () => {
    let pollCallback: (() => void) | null = null;
    vi.spyOn(window, "setInterval").mockImplementation(((callback: TimerHandler) => {
      pollCallback = callback as () => void;
      return 1 as unknown as number;
    }) as typeof window.setInterval);
    vi.spyOn(window, "clearInterval").mockImplementation(() => {});

    const fetchSpy = vi.spyOn(global, "fetch");
    fetchSpy
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ hasLiveTranscript: true }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ error: "Transcript not found" }), { status: 404 }),
      );

    const { result } = renderHook(() =>
      useProviderSession({
        sessionId: "session-404",
        agentName: "agent-alpha",
        provider: "claude-code",
        status: "attached",
      } as never),
    );

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(result.current.isLoading).toBe(false);

    await act(async () => {
      pollCallback?.();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(result.current.events).toEqual([]);
  });

  it("deduplicates overlapping incremental events by seq", async () => {
    let pollCallback: (() => void) | null = null;
    vi.spyOn(window, "setInterval").mockImplementation(((callback: TimerHandler) => {
      pollCallback = callback as () => void;
      return 1 as unknown as number;
    }) as typeof window.setInterval);
    vi.spyOn(window, "clearInterval").mockImplementation(() => {});

    const fetchSpy = vi.spyOn(global, "fetch");
    fetchSpy
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ hasLiveTranscript: true }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            events: [
              { seq: 1, kind: "session_ready", ts: "2026-03-31T10:00:00.000Z" },
              { seq: 2, kind: "turn_started", ts: "2026-03-31T10:00:01.000Z" },
            ],
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            events: [
              { seq: 2, kind: "turn_started", ts: "2026-03-31T10:00:01.000Z" },
              { seq: 3, kind: "turn_completed", ts: "2026-03-31T10:00:02.000Z" },
            ],
          }),
          { status: 200 },
        ),
      );

    const { result } = renderHook(() =>
      useProviderSession({
        sessionId: "session-dedupe",
        agentName: "agent-alpha",
        provider: "claude-code",
        status: "attached",
      } as never),
    );

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(result.current.events.map((event) => event.id)).toEqual([
      "session-dedupe:1",
      "session-dedupe:2",
    ]);

    await act(async () => {
      pollCallback?.();
      await Promise.resolve();
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(result.current.events.map((event) => event.id)).toEqual([
        "session-dedupe:1",
        "session-dedupe:2",
        "session-dedupe:3",
      ]);
    });
  });
});
