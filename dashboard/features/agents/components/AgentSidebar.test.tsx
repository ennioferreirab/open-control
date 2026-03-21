import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Id } from "@/convex/_generated/dataModel";

vi.mock("@/components/ui/sidebar", () => ({
  Sidebar: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  SidebarContent: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  SidebarFooter: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  SidebarGroup: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  SidebarGroupLabel: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  SidebarHeader: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  SidebarMenu: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  SidebarMenuButton: ({
    children,
    onClick,
    tooltip,
  }: React.PropsWithChildren<{ onClick?: () => void; tooltip?: string }>) => (
    <button onClick={onClick} aria-label={tooltip}>
      {children}
    </button>
  ),
  SidebarMenuItem: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  SidebarTrigger: () => <button type="button">Trigger</button>,
  useSidebar: () => ({ state: "expanded", isMobile: false }),
}));

vi.mock("@/features/agents/hooks/useAgentSidebarData", () => ({
  useAgentSidebarData: vi.fn().mockReturnValue({
    deletedAgents: [],
    isAgentsLoading: false,
    regularAgents: [],
    remoteAgents: [],
    restoreAgent: vi.fn(),
    softDeleteAgent: vi.fn(),
    systemAgents: [],
  }),
}));

vi.mock("@/features/agents/hooks/useSquadSidebarData", () => ({
  useSquadSidebarData: () => ({
    archiveSquad: vi.fn(),
    archivedSquads: [],
    squads: [],
    isLoading: false,
    unarchiveSquad: vi.fn(),
  }),
}));

vi.mock("@/components/BoardContext", () => ({
  useBoard: () => ({
    activeBoardId: null,
  }),
}));

vi.mock("@/features/agents/components/AgentConfigSheet", () => ({
  AgentConfigSheet: () => null,
}));

vi.mock("@/features/agents/components/AgentSidebarItem", () => ({
  AgentSidebarItem: ({
    agent,
    onClick,
  }: {
    agent: { _id: string; displayName: string; name: string };
    onClick?: () => void;
  }) => (
    <button onClick={onClick} data-testid={`agent-item-${agent._id}`}>
      {agent.displayName}
    </button>
  ),
}));

vi.mock("@/features/agents/components/AgentAuthoringWizard", () => ({
  AgentAuthoringWizard: ({ open }: { open: boolean }) =>
    open ? <div data-testid="agent-authoring-wizard" /> : null,
}));

vi.mock("@/features/agents/components/DeleteAgentsDialog", () => ({
  DeleteAgentsDialog: () => null,
}));

vi.mock("@/features/agents/components/DeleteSquadDialog", () => ({
  DeleteSquadDialog: () => null,
}));

vi.mock("@/features/agents/components/SquadDetailSheet", () => ({
  SquadDetailSheet: () => null,
}));

vi.mock("@/features/agents/components/SquadSidebarSection", () => ({
  SquadSidebarSection: ({ filterQuery }: { filterQuery?: string }) => (
    <div data-testid="squad-sidebar-section" data-filter-query={filterQuery ?? ""} />
  ),
}));

vi.mock("@/features/agents/hooks/useNanobotProvider", () => ({
  useNanobotProvider: () => "claude-code",
}));

vi.mock("@/features/agents/components/AgentTerminal", () => ({
  AgentTerminal: () => <div data-testid="agent-terminal-container" />,
}));

import { useAgentSidebarData } from "@/features/agents/hooks/useAgentSidebarData";
import { AgentSidebar } from "./AgentSidebar";

describe("AgentSidebar", () => {
  beforeEach(() => {
    vi.mocked(useAgentSidebarData).mockReturnValue({
      deletedAgents: [],
      isAgentsLoading: false,
      regularAgents: [],
      remoteAgents: [],
      restoreAgent: vi.fn(),
      softDeleteAgent: vi.fn(),
      systemAgents: [],
    });
    // Reset body attributes left by Radix UI portals (dialogs, popovers) from prior test suites.
    document.body.removeAttribute("data-scroll-locked");
    document.body.style.removeProperty("pointer-events");
  });

  afterEach(() => {
    cleanup();
  });

  it("opens the squad authoring wizard when Create Squad is clicked", async () => {
    render(<AgentSidebar />);

    await userEvent.click(screen.getByRole("button", { name: /create agent or squad/i }));
    await userEvent.click(screen.getByRole("button", { name: /create squad/i }));

    expect(screen.getByText("Create Squad")).toBeInTheDocument();
    expect(screen.getByTestId("agent-terminal-container")).toBeInTheDocument();
  });

  it("filters regularAgents by displayName", async () => {
    vi.mocked(useAgentSidebarData).mockReturnValue({
      deletedAgents: [],
      isAgentsLoading: false,
      regularAgents: [
        {
          _id: "a1" as Id<"agents">,
          _creationTime: 0,
          name: "post-writer",
          displayName: "Post Writer",
          role: "Writer",
          skills: [],
          status: "idle" as const,
          enabled: true,
          isSystem: false,
        },
        {
          _id: "a2" as Id<"agents">,
          _creationTime: 0,
          name: "research-agent",
          displayName: "Research Agent",
          role: "Researcher",
          skills: [],
          status: "idle" as const,
          enabled: true,
          isSystem: false,
        },
      ],
      remoteAgents: [],
      restoreAgent: vi.fn(),
      softDeleteAgent: vi.fn(),
      systemAgents: [],
    });

    render(<AgentSidebar />);

    const input = screen.getByPlaceholderText(/search agents/i);
    await userEvent.type(input, "Post");

    expect(screen.getByText("Post Writer")).toBeInTheDocument();
    expect(screen.queryByText("Research Agent")).not.toBeInTheDocument();
  });

  it("filters regularAgents by @name", async () => {
    vi.mocked(useAgentSidebarData).mockReturnValue({
      deletedAgents: [],
      isAgentsLoading: false,
      regularAgents: [
        {
          _id: "a1" as Id<"agents">,
          _creationTime: 0,
          name: "post-writer",
          displayName: "Post Writer",
          role: "Writer",
          skills: [],
          status: "idle" as const,
          enabled: true,
          isSystem: false,
        },
        {
          _id: "a2" as Id<"agents">,
          _creationTime: 0,
          name: "research-agent",
          displayName: "Research Agent",
          role: "Researcher",
          skills: [],
          status: "idle" as const,
          enabled: true,
          isSystem: false,
        },
      ],
      remoteAgents: [],
      restoreAgent: vi.fn(),
      softDeleteAgent: vi.fn(),
      systemAgents: [],
    });

    render(<AgentSidebar />);

    const input = screen.getByPlaceholderText(/search agents/i);
    await userEvent.type(input, "@post-writer");

    expect(screen.getByText("Post Writer")).toBeInTheDocument();
    expect(screen.queryByText("Research Agent")).not.toBeInTheDocument();
  });

  it("passes filterQuery to SquadSidebarSection", async () => {
    render(<AgentSidebar />);

    const input = screen.getByPlaceholderText(/search agents/i);
    await userEvent.type(input, "content");

    const squadSection = screen.getByTestId("squad-sidebar-section");
    expect(squadSection).toHaveAttribute("data-filter-query", "content");
  });
});
