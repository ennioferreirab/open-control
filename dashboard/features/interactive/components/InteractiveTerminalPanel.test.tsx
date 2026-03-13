import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { InteractiveTerminalPanel } from "./InteractiveTerminalPanel";

const mockOpen = vi.fn();
const mockLoadAddon = vi.fn();
const mockWrite = vi.fn();
const mockDispose = vi.fn();
const mockFit = vi.fn();
const mockOnDataDispose = vi.fn();
const terminalOnDataHandlers: Array<(data: string) => void> = [];

let socketInstance: FakeWebSocket | null = null;

class FakeWebSocket {
  static OPEN = 1;
  static lastInstance: FakeWebSocket | null = null;

  public readyState = FakeWebSocket.OPEN;
  public binaryType = "blob";
  public onopen: (() => void) | null = null;
  public onclose: (() => void) | null = null;
  public onerror: (() => void) | null = null;
  public onmessage: ((event: MessageEvent) => void) | null = null;
  public sent: string[] = [];

  constructor(public readonly url: string) {
    FakeWebSocket.lastInstance = this;
    socketInstance = FakeWebSocket.lastInstance;
  }

  send(message: string) {
    this.sent.push(message);
  }

  close() {
    this.onclose?.();
  }
}

vi.mock("@xterm/xterm", () => ({
  Terminal: class {
    cols = 120;
    rows = 40;

    open = mockOpen;
    loadAddon = mockLoadAddon;
    write = mockWrite;
    dispose = mockDispose;

    onData(handler: (data: string) => void) {
      terminalOnDataHandlers.push(handler);
      return { dispose: mockOnDataDispose };
    }
  },
}));

vi.mock("@xterm/addon-fit", () => ({
  FitAddon: class {
    fit = mockFit;
  },
}));

describe("InteractiveTerminalPanel", () => {
  beforeEach(() => {
    socketInstance = null;
    terminalOnDataHandlers.length = 0;
    mockOpen.mockClear();
    mockLoadAddon.mockClear();
    mockWrite.mockClear();
    mockDispose.mockClear();
    mockFit.mockClear();
    mockOnDataDispose.mockClear();

    Object.defineProperty(window, "WebSocket", {
      configurable: true,
      value: FakeWebSocket,
    });
    Object.defineProperty(window, "ResizeObserver", {
      configurable: true,
      value: class {
        observe() {}
        disconnect() {}
      },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("connects to the interactive runtime with chat-scoped session parameters", async () => {
    render(<InteractiveTerminalPanel agentName="claude-pair" provider="claude-code" />);

    await waitFor(() => expect(socketInstance).not.toBeNull());

    expect(socketInstance?.url).toContain("provider=claude-code");
    expect(socketInstance?.url).toContain("agentName=claude-pair");
    expect(socketInstance?.url).toContain("scopeKind=chat");
    expect(socketInstance?.url).toContain("scopeId=chat%3Aclaude-pair");
  });

  it("shows connected status and surfaces runtime errors", async () => {
    render(<InteractiveTerminalPanel agentName="claude-pair" provider="claude-code" />);

    await waitFor(() => expect(socketInstance).not.toBeNull());

    await act(async () => {
      socketInstance?.onopen?.();
      socketInstance?.onmessage?.(
        new MessageEvent("message", {
          data: JSON.stringify({
            type: "attached",
            sessionId: "interactive_session:claude",
            attachToken: "attach-token-123",
          }),
        }),
      );
    });

    expect(await screen.findByText("Connected")).toBeInTheDocument();

    await act(async () => {
      socketInstance?.onmessage?.(
        new MessageEvent("message", {
          data: JSON.stringify({
            type: "error",
            message: "Claude Code binary 'claude' is not available on PATH.",
          }),
        }),
      );
    });

    expect(await screen.findByRole("alert")).toHaveTextContent("not available on PATH");
  });

  it("reuses the attach token when reconnecting to an existing session", async () => {
    vi.useFakeTimers();
    render(<InteractiveTerminalPanel agentName="claude-pair" provider="claude-code" />);

    await act(async () => {});
    const firstSocket = socketInstance;
    expect(firstSocket).not.toBeNull();

    await act(async () => {
      firstSocket?.onmessage?.(
        new MessageEvent("message", {
          data: JSON.stringify({
            type: "attached",
            sessionId: "interactive_session:claude",
            attachToken: "attach-token-123",
          }),
        }),
      );
      firstSocket?.onclose?.();
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(socketInstance).not.toBe(firstSocket);
    expect(socketInstance?.url).toContain("sessionId=interactive_session%3Aclaude");
    expect(socketInstance?.url).toContain("attachToken=attach-token-123");
    vi.useRealTimers();
  });
});
