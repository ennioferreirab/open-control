import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { TerminalPanel } from "./TerminalPanel";

const mockSend = vi.fn().mockResolvedValue(undefined);
const mockWake = vi.fn().mockResolvedValue(undefined);
const mockRename = vi.fn().mockResolvedValue(undefined);

vi.mock("@/features/terminal/hooks/useTerminalPanelState", () => ({
  useTerminalPanelState: (sessionId: string, agentName?: string) => ({
    session: mockSession,
    displayName: agentName || sessionId,
    send: mockSend,
    wake: mockWake,
    rename: mockRename,
  }),
}));

const baseSession = {
  sessionId: "session-1",
  status: "idle" as const,
  sleepMode: false,
  output: "line 1",
};
let mockSession: typeof baseSession | null | undefined = undefined;

function mockTerminalQueries(session: typeof baseSession) {
  mockSession = session;
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
    mockSession = undefined;
    mockSend.mockClear();
    mockWake.mockClear();
    mockRename.mockClear();
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
