import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { AgentTerminal } from "./AgentTerminal";

// Mock xterm
vi.mock("@xterm/xterm", () => {
  function Terminal() {
    return {
      open: vi.fn(),
      onData: vi.fn(() => ({ dispose: vi.fn() })),
      onResize: vi.fn(),
      dispose: vi.fn(),
      cols: 120,
      rows: 40,
      write: vi.fn(),
      loadAddon: vi.fn(),
    };
  }
  return { Terminal };
});

vi.mock("@xterm/addon-fit", () => {
  function FitAddon() {
    return {
      fit: vi.fn(),
      dispose: vi.fn(),
    };
  }
  return { FitAddon };
});

describe("AgentTerminal", () => {
  it("renders a terminal container div", () => {
    render(<AgentTerminal agentName="nanobot" provider="claude-code" />);
    const container = screen.getByTestId("agent-terminal-container");
    expect(container).toBeInTheDocument();
  });
});
