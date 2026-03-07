import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { AgentSidebarItem, getInitials, getAvatarColor } from "./AgentSidebarItem";
import type { AgentSidebarItemStateData } from "@/hooks/useAgentSidebarItemState";

const defaultHookData: AgentSidebarItemStateData = {
  terminalSessions: [],
};

vi.mock("@/hooks/useAgentSidebarItemState", () => ({
  useAgentSidebarItemState: () => defaultHookData,
}));

vi.mock("@/components/BoardContext", () => ({
  useBoard: () => ({
    toggleTerminal: vi.fn(),
    openTerminals: [],
  }),
}));

// Track the mock state so tests can control collapsed/expanded
let mockSidebarState: "expanded" | "collapsed" = "expanded";

// Mock the sidebar UI component to provide useSidebar context
vi.mock("@/components/ui/sidebar", () => ({
  useSidebar: () => ({
    state: mockSidebarState,
    open: mockSidebarState === "expanded",
    isMobile: false,
  }),
  SidebarMenuItem: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
    <li {...props}>{children}</li>
  ),
  SidebarMenuButton: ({
    children,
    tooltip,
    size,
    ...props
  }: React.PropsWithChildren<{ tooltip?: string; size?: string } & Record<string, unknown>>) => {
    void size;
    return (
      <div data-testid="menu-button" data-tooltip={tooltip} {...props}>
        {children}
      </div>
    );
  },
}));

const baseAgent = {
  _id: "agent1" as never,
  _creationTime: 1000,
  name: "code-monkey",
  displayName: "Code Monkey",
  role: "Developer",
  skills: ["typescript"],
  status: "active" as const,
};

describe("getInitials", () => {
  it("extracts first letters of first two words", () => {
    expect(getInitials("Code Monkey")).toBe("CM");
  });

  it("extracts first two letters of a single word", () => {
    expect(getInitials("Alpha")).toBe("AL");
  });

  it("handles extra whitespace", () => {
    expect(getInitials("  Code   Monkey  ")).toBe("CM");
  });

  it("uppercases the initials", () => {
    expect(getInitials("code monkey")).toBe("CM");
  });

  it("handles three-word names by taking first two", () => {
    expect(getInitials("The Code Monkey")).toBe("TC");
  });
});

describe("getAvatarColor", () => {
  it("returns a consistent color for the same name", () => {
    const color1 = getAvatarColor("alpha");
    const color2 = getAvatarColor("alpha");
    expect(color1).toBe(color2);
  });

  it("returns a Tailwind bg-* class", () => {
    const color = getAvatarColor("test-agent");
    expect(color).toMatch(/^bg-\w+-500$/);
  });

  it("returns different colors for different names", () => {
    const colors = new Set(
      ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta"].map(getAvatarColor)
    );
    // With 8 distinct names we expect at least a few different colors
    expect(colors.size).toBeGreaterThan(1);
  });
});

describe("AgentSidebarItem", () => {
  afterEach(() => {
    cleanup();
    mockSidebarState = "expanded";
  });

  it("renders avatar, name, role, and status dot in expanded mode", () => {
    render(<AgentSidebarItem agent={baseAgent} />);
    expect(screen.getByText("CM")).toBeInTheDocument();
    expect(screen.getByText("Code Monkey")).toBeInTheDocument();
    expect(screen.getByText("Developer")).toBeInTheDocument();
  });

  it("renders active status dot with blue styling", () => {
    const { container } = render(
      <AgentSidebarItem agent={{ ...baseAgent, status: "active" }} />
    );
    const dot = container.querySelector(".bg-blue-500");
    expect(dot).not.toBeNull();
  });

  it("renders idle status dot with gray styling", () => {
    const { container } = render(
      <AgentSidebarItem agent={{ ...baseAgent, status: "idle" }} />
    );
    const dot = container.querySelector(".bg-muted-foreground");
    expect(dot).not.toBeNull();
  });

  it("renders crashed status dot with red styling", () => {
    const { container } = render(
      <AgentSidebarItem agent={{ ...baseAgent, status: "crashed" }} />
    );
    const dot = container.querySelector(".bg-red-500");
    expect(dot).not.toBeNull();
  });

  it("provides tooltip content in collapsed mode", () => {
    mockSidebarState = "collapsed";
    render(<AgentSidebarItem agent={baseAgent} />);
    const button = screen.getByTestId("menu-button");
    expect(button.getAttribute("data-tooltip")).toBe(
      "Code Monkey - Developer - active"
    );
  });

  it("does not show name/role text in collapsed mode", () => {
    mockSidebarState = "collapsed";
    render(<AgentSidebarItem agent={baseAgent} />);
    expect(screen.queryByText("Code Monkey")).not.toBeInTheDocument();
    expect(screen.queryByText("Developer")).not.toBeInTheDocument();
  });

  it("applies transition-colors duration-200 to status dot", () => {
    const { container } = render(<AgentSidebarItem agent={baseAgent} />);
    const dot = container.querySelector(".transition-colors.duration-200");
    expect(dot).not.toBeNull();
  });

  // --- Disabled (deactivated) agent tests ---

  it("renders solid red dot without glow when enabled is false", () => {
    const { container } = render(
      <AgentSidebarItem agent={{ ...baseAgent, enabled: false }} />
    );
    const dot = container.querySelector(".bg-red-500");
    expect(dot).not.toBeNull();
    // Should NOT have glow shadow
    expect(dot!.className).not.toContain("shadow-[0_0_6px");
  });

  it("renders dimmed text when agent is disabled", () => {
    const { container } = render(
      <AgentSidebarItem agent={{ ...baseAgent, enabled: false }} />
    );
    const textContainer = container.querySelector(".opacity-60");
    expect(textContainer).not.toBeNull();
    expect(textContainer!.className).toContain("text-muted-foreground");
  });

  it("shows Deactivated in tooltip when agent is disabled", () => {
    render(
      <AgentSidebarItem agent={{ ...baseAgent, enabled: false }} />
    );
    expect(screen.getByText("Code Monkey")).toBeInTheDocument();
  });

  it("shows Deactivated in tooltip in collapsed mode when disabled", () => {
    mockSidebarState = "collapsed";
    render(
      <AgentSidebarItem agent={{ ...baseAgent, enabled: false }} />
    );
    const button = screen.getByTestId("menu-button");
    expect(button.getAttribute("data-tooltip")).toBe(
      "Code Monkey - Developer - Deactivated"
    );
  });

  it("renders red dot in collapsed mode when disabled", () => {
    mockSidebarState = "collapsed";
    const { container } = render(
      <AgentSidebarItem agent={{ ...baseAgent, enabled: false }} />
    );
    const dot = container.querySelector(".bg-red-500");
    expect(dot).not.toBeNull();
    expect(dot!.className).not.toContain("shadow-[0_0_6px");
  });

  it("uses runtime status when enabled is true", () => {
    const { container } = render(
      <AgentSidebarItem agent={{ ...baseAgent, enabled: true, status: "active" }} />
    );
    const dot = container.querySelector(".bg-blue-500");
    expect(dot).not.toBeNull();
    // Should have glow
    expect(dot!.className).toContain("shadow-[0_0_6px");
  });

  it("uses runtime status when enabled is undefined (backward compat)", () => {
    const { container } = render(
      <AgentSidebarItem agent={{ ...baseAgent, status: "crashed" }} />
    );
    const dot = container.querySelector(".bg-red-500");
    expect(dot).not.toBeNull();
    // Crashed has glow
    expect(dot!.className).toContain("shadow-[0_0_6px");
  });

  it("does not dim text when agent is enabled", () => {
    const { container } = render(
      <AgentSidebarItem agent={{ ...baseAgent, enabled: true }} />
    );
    expect(container.querySelector(".opacity-60")).toBeNull();
  });
});
