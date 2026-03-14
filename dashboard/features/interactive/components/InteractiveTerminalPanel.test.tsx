import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { InteractiveTerminalPanel } from "./InteractiveTerminalPanel";

const mockClipboardWriteText = vi.fn();
const mockOpen = vi.fn();
const mockLoadAddon = vi.fn();
const mockWrite = vi.fn();
const mockDispose = vi.fn();
const mockFit = vi.fn();
const mockOnDataDispose = vi.fn();
const terminalOnDataHandlers: Array<(data: string) => void> = [];
const mockAttachCustomKeyEventHandler = vi.fn();
const mockRequestTakeover = vi.fn();
const mockResumeAgent = vi.fn();
const mockMarkDone = vi.fn();

let socketInstance: FakeWebSocket | null = null;
let terminalCustomKeyEventHandler: ((event: KeyboardEvent) => boolean) | null = null;
let terminalHasSelection = false;
let terminalSelection = "";
let terminalOptions: Record<string, unknown> | null = null;

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

    constructor(options: Record<string, unknown>) {
      terminalOptions = options;
    }

    open = mockOpen;
    loadAddon = mockLoadAddon;
    write = mockWrite;
    dispose = mockDispose;
    hasSelection = () => terminalHasSelection;
    getSelection = () => terminalSelection;
    attachCustomKeyEventHandler = (handler: (event: KeyboardEvent) => boolean) => {
      terminalCustomKeyEventHandler = handler;
      mockAttachCustomKeyEventHandler(handler);
    };

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

vi.mock("@/features/interactive/hooks/useInteractiveTakeoverControls", () => ({
  useInteractiveTakeoverControls: () => ({
    requestTakeover: mockRequestTakeover,
    resumeAgent: mockResumeAgent,
    markDone: mockMarkDone,
    isRequestingTakeover: false,
    isResumingAgent: false,
    isMarkingDone: false,
  }),
}));

describe("InteractiveTerminalPanel", () => {
  beforeEach(() => {
    socketInstance = null;
    terminalOnDataHandlers.length = 0;
    terminalCustomKeyEventHandler = null;
    terminalHasSelection = false;
    terminalSelection = "";
    terminalOptions = null;
    mockClipboardWriteText.mockClear();
    mockOpen.mockClear();
    mockLoadAddon.mockClear();
    mockWrite.mockClear();
    mockDispose.mockClear();
    mockFit.mockClear();
    mockOnDataDispose.mockClear();
    mockAttachCustomKeyEventHandler.mockClear();
    mockRequestTakeover.mockClear();
    mockResumeAgent.mockClear();
    mockMarkDone.mockClear();

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
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: mockClipboardWriteText },
    });
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("connects to the interactive runtime with chat-scoped session parameters", async () => {
    render(<InteractiveTerminalPanel agentName="claude-pair" provider="claude-code" />);

    await waitFor(() => expect(socketInstance).not.toBeNull());

    expect(socketInstance?.url).toContain("provider=claude-code");
    expect(socketInstance?.url).toContain("agentName=claude-pair");
    expect(socketInstance?.url).toContain("scopeKind=chat");
    expect(socketInstance?.url).toContain("scopeId=chat%3Aclaude-pair");
    expect(terminalOptions?.convertEol).toBe(true);
  });

  it("connects to the interactive runtime with task-scoped session parameters", async () => {
    render(
      <InteractiveTerminalPanel
        agentName="claude-pair"
        provider="claude-code"
        scopeKind="task"
        scopeId="task-123"
        surface="step"
        taskId="task-123"
      />,
    );

    await waitFor(() => expect(socketInstance).not.toBeNull());

    expect(socketInstance?.url).toContain("scopeKind=task");
    expect(socketInstance?.url).toContain("scopeId=task-123");
    expect(socketInstance?.url).toContain("surface=step");
    expect(socketInstance?.url).toContain("taskId=task-123");
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
  });

  it("fits and sends a resize event after attaching to the runtime", async () => {
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

    expect(mockFit).toHaveBeenCalled();
    expect(socketInstance?.sent).toContain(
      JSON.stringify({ type: "resize", columns: 120, rows: 40 }),
    );
  });

  it("ignores close events from stale sockets after reconnecting the effect", async () => {
    vi.useFakeTimers();
    const { rerender } = render(
      <InteractiveTerminalPanel agentName="claude-pair" provider="claude-code" />,
    );

    expect(socketInstance).not.toBeNull();
    const firstSocket = socketInstance;

    rerender(<InteractiveTerminalPanel agentName="claude-pair" provider="codex" />);

    expect(socketInstance).not.toBe(firstSocket);
    const secondSocket = socketInstance;

    await act(async () => {
      firstSocket?.onclose?.();
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(socketInstance).toBe(secondSocket);
  });

  it("does not forward terminal input until human takeover is active", async () => {
    render(
      <InteractiveTerminalPanel
        agentName="claude-pair"
        provider="claude-code"
        scopeKind="task"
        scopeId="task-123"
        surface="step"
        taskId="task-123"
      />,
    );

    await waitFor(() => expect(socketInstance).not.toBeNull());

    await act(async () => {
      socketInstance?.onopen?.();
      terminalOnDataHandlers[0]?.("ls");
    });

    expect(socketInstance?.sent).toEqual([]);
  });

  it("forwards terminal input immediately for chat-scoped sessions", async () => {
    render(<InteractiveTerminalPanel agentName="claude-pair" provider="claude-code" />);

    await waitFor(() => expect(socketInstance).not.toBeNull());

    await act(async () => {
      socketInstance?.onopen?.();
      terminalOnDataHandlers[0]?.("ls");
    });

    expect(socketInstance?.sent).toContain(JSON.stringify({ type: "input", data: "ls" }));
  });

  it("copies the current terminal selection with ctrl+c instead of sending SIGINT", async () => {
    render(<InteractiveTerminalPanel agentName="claude-pair" provider="claude-code" />);

    await waitFor(() => expect(socketInstance).not.toBeNull());

    terminalHasSelection = true;
    terminalSelection = "texto selecionado";
    const preventDefault = vi.fn();

    const allowed = terminalCustomKeyEventHandler?.({
      key: "c",
      ctrlKey: true,
      metaKey: false,
      altKey: false,
      preventDefault,
    } as unknown as KeyboardEvent);
    await Promise.resolve();

    expect(allowed).toBe(false);
    expect(preventDefault).toHaveBeenCalledOnce();
    expect(mockClipboardWriteText).toHaveBeenCalledWith("texto selecionado");
    expect(socketInstance?.sent).toEqual([]);
  });

  it("requests takeover for the exact live execution session and unlocks done controls", async () => {
    render(
      <InteractiveTerminalPanel
        agentName="claude-pair"
        provider="claude-code"
        scopeKind="task"
        scopeId="task-123"
        surface="step"
        taskId="task-123"
        liveSessionId="interactive_session:claude"
        activeStepId={"step-123" as never}
      />,
    );

    await waitFor(() => expect(socketInstance).not.toBeNull());

    const takeoverButton = await screen.findByRole("button", { name: "Take over" });

    await act(async () => {
      takeoverButton.click();
    });

    expect(mockRequestTakeover).toHaveBeenCalledWith({
      sessionId: "interactive_session:claude",
      taskId: "task-123",
      stepId: "step-123",
      agentName: "claude-pair",
      provider: "claude-code",
    });
  });
});
