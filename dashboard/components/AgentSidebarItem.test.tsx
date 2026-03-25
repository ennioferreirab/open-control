import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { AgentSidebarItem } from "@/features/agents/components/AgentSidebarItem";
import { getInitials, getAvatarColor } from "@/lib/agentUtils";
import type { AgentSidebarItemStateData } from "@/features/agents/hooks/useAgentSidebarItemState";

const defaultHookData: AgentSidebarItemStateData = {
  terminalSessions: [],
};

vi.mock("@/features/agents/hooks/useAgentSidebarItemState", () => ({
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
      ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta"].map(getAvatarColor),
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

  it("renders avatar initials and name in expanded mode", () => {
    render(<AgentSidebarItem agent={baseAgent} />);
    expect(screen.getByText("CM")).toBeInTheDocument();
    expect(screen.getByText("code-monkey")).toBeInTheDocument();
  });

  it("provides tooltip content in collapsed mode", () => {
    mockSidebarState = "collapsed";
    render(<AgentSidebarItem agent={baseAgent} />);
    const button = screen.getByTestId("menu-button");
    expect(button.getAttribute("data-tooltip")).toBe("code-monkey - Developer - active");
  });

  it("does not show name/role text in collapsed mode", () => {
    mockSidebarState = "collapsed";
    render(<AgentSidebarItem agent={baseAgent} />);
    expect(screen.queryByText("code-monkey")).not.toBeInTheDocument();
    expect(screen.queryByText("Developer")).not.toBeInTheDocument();
  });

  // --- Disabled (deactivated) agent tests ---

  it("shows Deactivated in tooltip in collapsed mode when disabled", () => {
    mockSidebarState = "collapsed";
    render(<AgentSidebarItem agent={{ ...baseAgent, enabled: false }} />);
    const button = screen.getByTestId("menu-button");
    expect(button.getAttribute("data-tooltip")).toBe("code-monkey - Developer - Deactivated");
  });
});
