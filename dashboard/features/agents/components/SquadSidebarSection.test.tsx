import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SquadSidebarSection } from "./SquadSidebarSection";
import type { Doc } from "@/convex/_generated/dataModel";

// Mock sidebar primitives to avoid SidebarProvider context requirements
vi.mock("@/components/ui/sidebar", () => ({
  SidebarGroup: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  SidebarGroupLabel: ({ children, className }: React.PropsWithChildren<{ className?: string }>) => (
    <div className={className}>{children}</div>
  ),
  SidebarMenu: ({ children }: React.PropsWithChildren) => <ul>{children}</ul>,
  SidebarMenuItem: ({ children }: React.PropsWithChildren) => <li>{children}</li>,
  SidebarMenuButton: ({
    children,
    onClick,
  }: React.PropsWithChildren<{
    onClick?: () => void;
    size?: string;
    tooltip?: string;
    className?: string;
  }>) => <button onClick={onClick}>{children}</button>,
}));

// Mock the hook
vi.mock("@/features/agents/hooks/useSquadSidebarData", () => ({
  useSquadSidebarData: vi.fn(),
}));

import { useSquadSidebarData } from "@/features/agents/hooks/useSquadSidebarData";

const mockUseSquadSidebarData = vi.mocked(useSquadSidebarData);

describe("SquadSidebarSection", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders Squads section label", () => {
    mockUseSquadSidebarData.mockReturnValue({
      squads: [],
      archivedSquads: [],
      isLoading: false,
      archiveSquad: vi.fn(),
      unarchiveSquad: vi.fn(),
    });
    render(<SquadSidebarSection onSelectSquad={vi.fn()} />);
    expect(screen.getByText("Squads")).toBeInTheDocument();
  });

  it("renders empty state when no squads exist", () => {
    mockUseSquadSidebarData.mockReturnValue({
      squads: [],
      archivedSquads: [],
      isLoading: false,
      archiveSquad: vi.fn(),
      unarchiveSquad: vi.fn(),
    });
    render(<SquadSidebarSection onSelectSquad={vi.fn()} />);
    expect(screen.getByText(/no squads/i)).toBeInTheDocument();
  });

  it("renders squad items when squads are loaded", () => {
    const mockSquads = [
      {
        _id: "sq1" as never,
        _creationTime: 0,
        name: "alpha-squad",
        displayName: "Alpha Squad",
        description: "First squad",
        status: "published" as const,
        version: 1,
        agentSpecIds: [],
        createdAt: "2026-01-01",
        updatedAt: "2026-01-01",
      },
    ] as Doc<"squadSpecs">[];
    mockUseSquadSidebarData.mockReturnValue({
      squads: mockSquads,
      archivedSquads: [],
      isLoading: false,
      archiveSquad: vi.fn(),
      unarchiveSquad: vi.fn(),
    });
    render(<SquadSidebarSection onSelectSquad={vi.fn()} />);
    expect(screen.getByText("Alpha Squad")).toBeInTheDocument();
  });

  it("calls onSelectSquad when a squad item is clicked", async () => {
    const handleSelect = vi.fn();
    const mockSquads = [
      {
        _id: "sq1" as never,
        _creationTime: 0,
        name: "alpha-squad",
        displayName: "Alpha Squad",
        status: "published" as const,
        version: 1,
        agentSpecIds: [],
        createdAt: "2026-01-01",
        updatedAt: "2026-01-01",
      },
    ] as Doc<"squadSpecs">[];
    mockUseSquadSidebarData.mockReturnValue({
      squads: mockSquads,
      archivedSquads: [],
      isLoading: false,
      archiveSquad: vi.fn(),
      unarchiveSquad: vi.fn(),
    });
    render(<SquadSidebarSection onSelectSquad={handleSelect} />);
    await userEvent.click(screen.getByText("Alpha Squad"));
    expect(handleSelect).toHaveBeenCalledWith("sq1");
  });
});
