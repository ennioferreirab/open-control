import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AgentSidebar } from "./AgentSidebar";

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
}));

vi.mock("@/features/agents/hooks/useAgentSidebarData", () => ({
  useAgentSidebarData: () => ({
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

vi.mock("@/features/agents/components/AgentAuthoringWizard", () => ({
  AgentAuthoringWizard: ({ open }: { open: boolean }) =>
    open ? <div data-testid="agent-authoring-wizard" /> : null,
}));

vi.mock("@/features/agents/components/SquadDetailSheet", () => ({
  SquadDetailSheet: () => null,
}));

vi.mock("@/features/agents/components/SquadSidebarSection", () => ({
  SquadSidebarSection: () => null,
}));

vi.mock("@/features/agents/hooks/useNanobotProvider", () => ({
  useNanobotProvider: () => "claude-code",
}));

vi.mock("@/features/agents/components/AgentTerminal", () => ({
  AgentTerminal: () => <div data-testid="agent-terminal-container" />,
}));

describe("AgentSidebar", () => {
  it("opens the squad authoring wizard when Create Squad is clicked", async () => {
    render(<AgentSidebar />);

    await userEvent.click(screen.getByRole("button", { name: /create agent or squad/i }));
    await userEvent.click(screen.getByRole("button", { name: /create squad/i }));

    expect(screen.getByText("Create Squad")).toBeInTheDocument();
    expect(screen.getByTestId("agent-terminal-container")).toBeInTheDocument();
  });
});
