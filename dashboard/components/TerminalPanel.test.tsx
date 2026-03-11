import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { TerminalPanel } from "./TerminalPanel";

const mockUseQuery = vi.fn();
const mockMutation = vi.fn().mockResolvedValue(undefined);

vi.mock("convex/react", () => ({
  useQuery: (...args: unknown[]) => mockUseQuery(...args),
  useMutation: () => mockMutation,
}));

const baseSession = {
  sessionId: "session-1",
  status: "idle" as const,
  sleepMode: false,
  output: "line 1",
};

function mockTerminalQueries(session: typeof baseSession) {
  mockUseQuery.mockImplementation((_queryRef: unknown, args: unknown) => {
    if (args === "skip") return undefined;
    if (
      typeof args === "object" &&
      args !== null &&
      "sessionId" in (args as Record<string, unknown>)
    ) {
      return session;
    }
    if (typeof args === "object" && args !== null && "name" in (args as Record<string, unknown>)) {
      return null;
    }
    return undefined;
  });
}

function setScrollMetrics(
  element: HTMLElement,
  metrics: { clientHeight: number; scrollHeight: number },
) {
  Object.defineProperty(element, "clientHeight", {
    configurable: true,
    value: metrics.clientHeight,
  });
  Object.defineProperty(element, "scrollHeight", {
    configurable: true,
    value: metrics.scrollHeight,
  });
}

describe("TerminalPanel", () => {
  afterEach(() => {
    cleanup();
    mockUseQuery.mockReset();
    mockMutation.mockClear();
  });

  it("auto-scrolls the terminal output when already at the bottom", async () => {
    let session = { ...baseSession, output: "line 1" };
    mockTerminalQueries(session);

    const { getByTestId, rerender } = render(
      <TerminalPanel sessionId="session-1" agentName="remote-agent" />,
    );

    const output = getByTestId("terminal-output");
    setScrollMetrics(output, { clientHeight: 200, scrollHeight: 600 });
    output.scrollTop = 400;
    fireEvent.scroll(output);

    session = { ...session, output: "line 1\nline 2" };
    mockTerminalQueries(session);
    rerender(<TerminalPanel sessionId="session-1" agentName="remote-agent" />);

    setScrollMetrics(output, { clientHeight: 200, scrollHeight: 800 });

    await waitFor(() => {
      expect(output.scrollTop).toBe(600);
    });
  });

  it("preserves the user's scroll position when they are reading older output", async () => {
    let session = { ...baseSession, output: "line 1\nline 2\nline 3" };
    mockTerminalQueries(session);

    const { getByTestId, rerender } = render(
      <TerminalPanel sessionId="session-1" agentName="remote-agent" />,
    );

    const output = getByTestId("terminal-output");
    setScrollMetrics(output, { clientHeight: 200, scrollHeight: 600 });
    output.scrollTop = 100;
    fireEvent.scroll(output);

    session = { ...session, output: "line 1\nline 2\nline 3\nline 4" };
    mockTerminalQueries(session);
    rerender(<TerminalPanel sessionId="session-1" agentName="remote-agent" />);

    setScrollMetrics(output, { clientHeight: 200, scrollHeight: 800 });

    await waitFor(() => {
      expect(output.scrollTop).toBe(100);
    });
  });
});
