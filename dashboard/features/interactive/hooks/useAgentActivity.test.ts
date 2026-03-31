import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useAgentActivity } from "./useAgentActivity";

describe("useAgentActivity", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("stops polling after the transcript endpoint returns 404", async () => {
    let pollCallback: (() => void) | null = null;
    vi.spyOn(window, "setInterval").mockImplementation(((callback: TimerHandler) => {
      pollCallback = callback as () => void;
      return 1 as unknown as number;
    }) as typeof window.setInterval);
    vi.spyOn(window, "clearInterval").mockImplementation(() => {});

    const fetchSpy = vi
      .spyOn(global, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify({ error: "Transcript not found" }), { status: 404 }),
      );

    const { result } = renderHook(() => useAgentActivity("session-404"));

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(result.current.isLoading).toBe(false);

    await act(async () => {
      pollCallback?.();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(result.current.events).toEqual([]);
  });

  it("skips network requests when session metadata says there is no transcript", async () => {
    const fetchSpy = vi.spyOn(global, "fetch");

    const { result } = renderHook(() => useAgentActivity("session-no-live", false));

    await act(async () => {
      await Promise.resolve();
    });

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(result.current.isLoading).toBe(false);
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

    const { result } = renderHook(() => useAgentActivity("session-dedupe"));

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(result.current.events).toHaveLength(2);

    await act(async () => {
      pollCallback?.();
      await Promise.resolve();
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(result.current.events.map((event) => event.seq)).toEqual([1, 2, 3]);
    });
  });
});
