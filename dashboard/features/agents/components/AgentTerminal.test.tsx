import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AgentTerminal } from "./AgentTerminal";

const mockOpen = vi.fn();
const mockLoadAddon = vi.fn();
const mockWrite = vi.fn();
const mockDispose = vi.fn();
const mockFit = vi.fn();
const mockOnDataDispose = vi.fn();

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

    onData() {
      return { dispose: mockOnDataDispose };
    }
  },
}));

vi.mock("@xterm/addon-fit", () => ({
  FitAddon: class {
    fit = mockFit;
    dispose = vi.fn();
  },
}));

describe("AgentTerminal", () => {
  beforeEach(() => {
    socketInstance = null;
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

  it("renders a terminal container div", () => {
    render(<AgentTerminal agentName="nanobot" provider="claude-code" />);
    expect(screen.getByTestId("agent-terminal-container")).toBeInTheDocument();
  });

  it("shows a connecting status while the interactive session is attaching", async () => {
    render(<AgentTerminal agentName="nanobot" provider="claude-code" />);

    expect(screen.getByText(/connecting terminal/i)).toBeInTheDocument();

    await waitFor(() => expect(socketInstance).not.toBeNull());
    expect(socketInstance?.url).toContain("agentName=nanobot");
    expect(socketInstance?.url).toContain("scopeKind=chat");
  });

  it("shows an error when the interactive runtime rejects the session", async () => {
    render(<AgentTerminal agentName="nanobot" provider="claude-code" />);

    await waitFor(() => expect(socketInstance).not.toBeNull());

    await act(async () => {
      socketInstance?.onmessage?.(
        new MessageEvent("message", {
          data: JSON.stringify({
            type: "error",
            message: "Interactive agent 'nanobot' could not be loaded.",
          }),
        }),
      );
    });

    expect(screen.getByRole("alert")).toHaveTextContent("could not be loaded");
  });
});
